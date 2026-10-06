"""Recolha dos documentos do BTE a partir dos ficheiros-índice da DGERT.

A recolha usa a rede apenas quando autorizada explicitamente:
sem `--confirmar-rede` (ou `CRL_RECOLHA_REDE=1`) simula a corrida e diz o que
faria. Só descarrega URLs vindos do índice, e só de anfitriões da lista abaixo —
Adaptado de crl-app-cct, commit 9faa8fef3c73d4a853e0c2f6592ce69ac42b7709.

Entrada:  data/raw/indices/BTE31_2026.xlsx   (índice fornecido por número do BTE)
Saída:    data/interim/recolha/2026/31/00260057.pdf   (nome de origem, imutável)
Registo:  data/registo/registo_bte.jsonl     (uma linha JSON por documento)

Uso:
  python -m crl_markdown.recolha --indices data/raw/indices                  # simulação
  python -m crl_markdown.recolha --indices data/raw/indices --confirmar-rede
"""

import argparse
import hashlib
import json
import math
import os
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zipfile import BadZipFile

from . import utf8_output
from .bte_schema import validar_registo

# Anfitriões públicos do Boletim do Trabalho e Emprego. O antigo bte.gep.msess.gov.pt
# redireciona hoje para bte.dgcp.mtsss.gov.pt; ambos ficam permitidos.
HOSTS_PERMITIDOS = frozenset(
    {
        "bte.dgcp.mtsss.gov.pt",
        "bte.gep.msess.gov.pt",
        "bte.gep.mtsss.gov.pt",
    }
)

USER_AGENT = "CRL-PDF-Markdown/0.2 (Centro de Relacoes Laborais; recolha do BTE)"
TIMEOUT = 60
MAX_BYTES = 200 * 1024 * 1024
TENTATIVAS = 3

# Vocabulário de tipos da DGERT → família. A comparação é feita pelo prefixo do
# tipo normalizado, para apanhar as variantes (-ALT, -RECT, -ALT-RECT).
#
# As famílias não são uma arrumação decorativa: decidem em que pasta o
# documento fica e, por consequência, o que o pipeline lê. Uma portaria de
# extensão e um acordo de adesão referem-se a uma convenção concreta, mas não
# são convenções — não têm o articulado que a codificação temática pressupõe, e
# codificá-los como se fossem contamina qualquer contagem por cláusula.
# A família mantém a classificação usada pelo AppCCT.
#
#   convencao   o articulado em si: CCT, ACT, AE, ACEP, e as decisões arbitrais,
#               que substituem a convenção e têm cláusulas como ela
#   extensao    PE, PCT, PRT — actos do Governo que alargam o âmbito de outro
#   adesao      AA — uma parte adere a uma convenção existente
#   aviso       avisos de projeto de portaria, denúncias, caducidades
#
# A ordem importa: o primeiro prefixo que encaixar ganha, pelo que os prefixos
# mais longos vêm antes dos que os contêm (ACTV antes de ACT, AVISO antes de AV).
PREFIXOS_FAMILIA = [
    ("CCT", "convencao"),
    ("ACTV", "convencao"),
    ("ACEP", "convencao"),
    ("ACT", "convencao"),
    ("AE", "convencao"),
    ("DA", "convencao"),
    ("PE", "extensao"),
    ("PCT", "extensao"),
    ("PRT", "extensao"),
    ("AVISO", "aviso"),
    ("AV", "aviso"),
    ("AA", "adesao"),
]

# Os acordos de adesão passam a ser recolhidos por omissão. Estavam de fora, e
# isso significava que uma adesão publicada no BTE não deixava rasto nenhum —
# nem sequer uma linha no catálogo a dizer que existia.
FAMILIAS_POR_OMISSAO = ("convencao", "extensao", "adesao", "aviso")

REGISTO_OMISSAO = Path("data") / "registo" / "registo_bte.jsonl"
DESTINO_OMISSAO = Path("data") / "interim" / "recolha"
INDICES_OMISSAO = Path("data") / "raw" / "indices"


# ---------------------------------------------------------------- utilitários


def _norm(s) -> str:
    """Minúsculas, sem acentos e sem pontuação — para comparar cabeçalhos."""
    text = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in text.lower() if c.isalnum())


def familia(tipo: str) -> str | None:
    """Família documental de um tipo da DGERT ('CCT-ALT' → 'convencao')."""
    t = _norm(tipo).upper()
    if not t:
        return None
    for prefixo, fam in PREFIXOS_FAMILIA:
        if t.startswith(prefixo):
            return fam
    return None


def sha256_ficheiro(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# ------------------------------------------------------------ leitura do índice

# Cabeçalhos do índice, nos dois dialetos que a DGERT distribui:
#
#   *rótulo*   — cabeçalhos legíveis, com dois pontos ("TIPO DE DOCUMENTO:",
#                "COD: (IRCT)", "OUTORGANTE(S):"). É o dialeto de 2025.
#   *técnico*  — nomes de campo da base ("TipoSubTipoDoc", "CodigoGEPDGERT",
#                "NomePDF", "URLPDF"). É o que vem nos índices de 2026.
#
# Os dois convivem: a normalização de `_norm()` descarta pontuação e acentos, e
# cada campo interno aceita os aliases dos dois lados. Um índice que só traga um
# dos dialetos é lido na mesma; um que traga ambos usa a primeira coluna com
# valor, conforme os índices tratados pelo AppCCT.
COLUNAS = {
    "ano": ["ano"],
    "id_dgert": ["id", "iddocumento"],
    "titulo": ["titulododocumento", "titulo"],
    "tipo": ["tipodedocumento", "tiposubtipodoc"],
    "volume": ["nvolumedoboletim", "novolumedoboletim", "nvolumebte"],
    "num_bte": ["ndoboletim", "nodoboletim", "nbte"],
    "data_bte": ["datadoboletim", "databte"],
    "data_distribuicao": ["datadedistribuicaodoboletim", "datadistribuicaobte"],
    "pagina": ["paginanaversaoescrita", "pagversaoescrita"],
    "cae": ["cae"],
    "cod_irct": ["codirct", "codigogepdgert"],
    "sectores": [
        "sectoresdeactividade",
        "setoresdeatividade",
        "setoresatividade",
        "sectoresatividade",
    ],
    "outorgantes": ["outorgantes", "outorgantes1"],
    "altera": [
        "docsalteradosporeste",
        "docalteradosporeste",
        "docsalteradosporeste2",
        "docalteradosporeste2",
    ],
    "alterado_por": [
        "docsquealteramestes",
        "docsquealteramestee",
        "docsquealterameste",
        "docalterameste",
        "docsalteramestes",
    ],
    "em_vigor": ["documentosemvigor", "docsemvigor"],
    "url_em_vigor": ["linkdocemvigor", "linkparaodocumentoemvigor"],
    "url": ["linkparaodocumentocriado", "linkparaodocumento", "urlpdf"],
    "ficheiro": ["paginacriado", "nomepdf"],
    # Campos opcionais conservados para compatibilidade com registos AppCCT.
    "cod_irct_base": [],
    "portaria_dr": [],
}

# Campos em que várias colunas do índice são partes da mesma informação e não
# alternativas: o índice de 2026 parte a cadeia de alterações em
# `DocAlteradosPorEste` e `DocAlteradosPorEste2`. Juntam-se em vez de se escolher
# a primeira — escolher perdia metade da cadeia, em silêncio.
CAMPOS_ACUMULADOS = frozenset({"altera", "alterado_por"})


def _mapa_colunas(cabecalho: list) -> dict[str, list[int]]:
    """Nome interno → índices das colunas do índice (há cabeçalhos repetidos)."""
    normalizado = [_norm(c) for c in cabecalho]
    mapa: dict[str, list[int]] = {}
    for campo, nomes in COLUNAS.items():
        mapa[campo] = [i for i, n in enumerate(normalizado) if n in nomes]
    return mapa


def ler_indice(xlsx: Path, *, problemas: list[str] | None = None) -> list[dict]:
    """Lê um ficheiro-índice do BTE e devolve um item por documento.

    Tolerante à ordem das colunas e a cabeçalhos repetidos (o índice de 2026 tem
    'TIPO DE DOCUMENTO:' duas vezes, a segunda vazia).
    """
    import openpyxl

    try:
        wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    except (BadZipFile, openpyxl.utils.exceptions.InvalidFileException) as exc:
        raise ValueError(f"Índice Excel inválido: {xlsx.name}") from exc
    try:
        itens: list[dict] = []
        reconhecido = False
        for ws in wb.worksheets:
            linhas = ws.iter_rows(values_only=True)
            try:
                cabecalho = list(next(linhas))
            except StopIteration:
                continue
            mapa = _mapa_colunas(cabecalho)
            if not mapa["titulo"] and not mapa["url"]:
                continue  # folha que não é um índice do BTE
            reconhecido = True
            for posicao, linha in enumerate(linhas, 1):
                item: dict[str, Any] = {}
                for campo, indices in mapa.items():
                    valores = [
                        str(linha[i]).strip()
                        for i in indices
                        if i < len(linha) and linha[i] not in (None, "")
                    ]
                    if campo in CAMPOS_ACUMULADOS:
                        item[campo] = "; ".join(dict.fromkeys(v for v in valores if v))
                    else:
                        item[campo] = valores[0] if valores else ""
                if not (item["titulo"] or item["url"]):
                    continue
                item["indice"] = xlsx.name
                item["folha"] = ws.title
                item["posicao"] = posicao
                item["familia"] = familia(item["tipo"])
                try:
                    _completar(item)
                except ValueError as e:
                    mensagem = f"{xlsx.name} ({ws.title}, posição {posicao}): {e}"
                    if problemas is not None:
                        problemas.append(mensagem)
                    else:
                        print(f"AVISO — linha ignorada em {mensagem}")
                    continue
                itens.append(item)
        if not reconhecido or not itens:
            raise ValueError(f"Sem linhas válidas de índice BTE em {xlsx.name}.")
        return itens
    finally:
        wb.close()


def _nome_seguro(ficheiro: str) -> str:
    """Reduz a um nome de ficheiro simples — sem separadores, sem travessia.

    O valor de origem vem de uma coluna da folha de cálculo do índice (ou de
    um URL), uma fonte externa que pode ter erros de cópia/OCR ou, no limite,
    ser adulterada. `Path(ficheiro).name` descarta qualquer componente de
    directório; o que resta ainda pode ser "" ou ".." (ex.: um URL terminado
    em "/.."), por isso a rejeição explícita a seguir.
    """
    if not ficheiro:
        return ""
    nome = Path(ficheiro).name
    if not nome or nome in (".", "..") or "\\" in nome:
        raise ValueError(f"nome de ficheiro inválido no índice: {ficheiro!r}")
    return nome


def _completar(item: dict) -> None:
    """Deriva ano, número do BTE, ficheiro de origem, URL e chave."""
    item["ano"] = _inteiro(item.get("ano"))
    item["num_bte"] = _inteiro(item.get("num_bte"))
    url = (item.get("url") or "").strip()
    ficheiro = _nome_seguro((item.get("ficheiro") or "").strip())
    if url:
        ficheiro = ficheiro or _nome_seguro(Path(urlparse(url).path).name)
        partes = [p for p in urlparse(url).path.split("/") if p]
        if item["ano"] is None and len(partes) >= 3:
            item["ano"] = _inteiro(partes[-3])
        if item["num_bte"] is None and len(partes) >= 2:
            item["num_bte"] = _inteiro(partes[-2])
    elif ficheiro and item["ano"] and item["num_bte"]:
        url = f"https://bte.dgcp.mtsss.gov.pt/documentos/{item['ano']}/{item['num_bte']}/{ficheiro}"
    if not item["ano"] or not item["num_bte"] or item["ano"] < 1900 or item["num_bte"] < 1:
        raise ValueError("ano ou número BTE ausente ou inválido")
    if not ficheiro or Path(ficheiro).suffix.lower() != ".pdf":
        raise ValueError("nome de PDF ausente ou inválido")
    item["url"] = url
    item["ficheiro"] = ficheiro
    item["chave"] = chave(item)


def _inteiro(v) -> int | None:
    try:
        number = float(str(v).strip())
        return int(number) if number.is_integer() else None
    except (TypeError, ValueError, OverflowError):
        return None


def chave(item: dict) -> str:
    """Identidade estável de um documento: ano/número do BTE/ficheiro de origem."""
    base = (
        Path(item.get("ficheiro") or "").stem
        or _norm(item.get("id_dgert"))
        or _norm(item.get("titulo"))[:40]
    )
    return f"{item.get('ano')}/{item.get('num_bte')}/{base}"


# ------------------------------------------------------------------- registo


class Registo:
    """Registo persistente dos documentos: proveniência e estado de descarga.

    Ficheiro JSONL, uma linha por documento, reescrito de forma atómica. Vive em
    `data/registo/`, separadamente dos PDFs e dos resultados de conversão.
    Campos de nomeação de registos AppCCT existentes são preservados.
    """

    def __init__(self, caminho: Path, entradas: dict[str, dict] | None = None):
        self.caminho = Path(caminho)
        self.entradas: dict[str, dict] = entradas or {}

    @classmethod
    def carregar(cls, caminho: Path) -> "Registo":
        """Carrega o registo, validando cada entrada contra REGISTO_SCHEMA.

        Uma linha inválida (JSON malformado, sem "chave", ou com "ano"/
        "num_bte"/ordinal do tipo errado) é ignorada com um aviso — em vez de
        entrar sem verificação e produzir mais tarde um nome de ficheiro como
        "00_PR_000_BTE_00_…" (ver PR #35, achado nº10) — mas não interrompe a
        leitura do resto do ficheiro.
        """
        import jsonschema

        caminho = Path(caminho)
        entradas: dict[str, dict] = {}
        if caminho.exists():
            for n, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    e = json.loads(linha)
                    validar_registo(e)
                except (json.JSONDecodeError, jsonschema.ValidationError, KeyError) as exc:
                    print(
                        f"AVISO — {caminho.name}, linha {n}: entrada de registo "
                        f"inválida, ignorada: {exc}"
                    )
                    continue
                entradas[e["chave"]] = e  # última linha ganha
        return cls(caminho, entradas)

    def guardar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        temp = self.caminho.with_suffix(self.caminho.suffix + ".part")
        with open(temp, "w", encoding="utf-8", newline="\n") as f:
            for chave_ in sorted(self.entradas):
                f.write(json.dumps(self.entradas[chave_], ensure_ascii=False) + "\n")
        os.replace(temp, self.caminho)

    def get(self, chave_: str) -> dict | None:
        return self.entradas.get(chave_)

    def actualizar(self, item: dict, **campos) -> dict:
        entrada = self.entradas.setdefault(item["chave"], {"chave": item["chave"]})
        for c in (
            "ano",
            "num_bte",
            "volume",
            "id_dgert",
            "tipo",
            "familia",
            "cod_irct",
            "cae",
            "titulo",
            "outorgantes",
            "sectores",
            "url",
            "ficheiro",
            "indice",
            "folha",
            "posicao",
            "pagina",
            "em_vigor",
            "url_em_vigor",
            "data_bte",
            "data_distribuicao",
            "altera",
            "alterado_por",
            "cod_irct_base",
            "portaria_dr",
        ):
            if item.get(c) not in (None, ""):
                entrada[c] = item[c]
        entrada.update(campos)
        return entrada

    def por_familia(self, ano: int, fam: str) -> list[dict]:
        return [
            e for e in self.entradas.values() if e.get("ano") == ano and e.get("familia") == fam
        ]


# ---------------------------------------------------------------------- rede


@dataclass
class Resposta:
    estado: int
    cabecalhos: dict = field(default_factory=dict)
    corpo: bytes = b""


class ErroRede(Exception):
    pass


class ErroURL(ErroRede):
    """URL inválido: não repetir pedidos que não podem ser autorizados."""


def validar_url(url: str) -> str:
    """Recusa tudo o que não seja https para um anfitrião do BTE."""
    try:
        p = urlparse(url)
        port = p.port
    except ValueError as exc:
        raise ErroURL("URL malformado") from exc
    if p.scheme != "https":
        raise ErroURL(f"esquema recusado ({p.scheme or 'nenhum'}): só https")
    if (p.hostname or "").lower() not in HOSTS_PERMITIDOS:
        raise ErroURL(f"anfitrião fora da lista permitida: {p.hostname}")
    if p.username or p.password or port not in (None, 443):
        raise ErroURL("credenciais ou porta não permitidas no URL")
    return url


class _RedireccionamentoVerificado(urllib.request.HTTPRedirectHandler):
    """Revalida o anfitrião a cada redirecionamento (o antigo host redireciona)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validar_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def abridor_urllib(url: str, cabecalhos: dict | None = None) -> Resposta:
    """Transporte real. Injetável: os testes passam outra função em `abridor=`."""
    validar_url(url)
    pedido = urllib.request.Request(url, method="GET")
    pedido.add_header("User-Agent", USER_AGENT)
    for k, v in (cabecalhos or {}).items():
        pedido.add_header(k, v)
    # ProxyHandler por omissão: respeita HTTPS_PROXY das estações do CRL.
    opener = urllib.request.build_opener(_RedireccionamentoVerificado)
    try:
        with opener.open(pedido, timeout=TIMEOUT) as r:
            corpo = r.read(MAX_BYTES + 1)
            if len(corpo) > MAX_BYTES:
                raise ErroRede(f"resposta acima de {MAX_BYTES} bytes")
            return Resposta(r.status, dict(r.headers), corpo)
    except urllib.error.HTTPError as e:
        return Resposta(e.code, dict(e.headers or {}), b"")
    except OSError as e:  # timeout, DNS, TLS
        raise ErroRede(str(e)) from e


# ------------------------------------------------------------------- descarga


def _escrever_atomico(destino: Path, dados: bytes) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temp = destino.with_suffix(destino.suffix + ".part")
    temp.write_bytes(dados)
    os.replace(temp, destino)


def descarregar_item(item: dict, destino_raiz: Path, registo: Registo, *, abridor=None) -> dict:
    """Descarrega um documento, se ainda não estiver cá. Devolve a entrada do registo.

    Estados possíveis: `ja_existente`, `inalterado`, `descarregado`, `falhado`.
    """
    abridor = abridor or abridor_urllib
    anterior = registo.get(item["chave"]) or {}
    descarga = dict(anterior.get("descarga") or {})
    caminho = destino_raiz / str(item["ano"]) / str(item["num_bte"]) / item["ficheiro"]
    raiz_resolvida = destino_raiz.resolve()
    if raiz_resolvida not in caminho.resolve().parents and caminho.resolve() != raiz_resolvida:
        # cinto-e-suspensórios: _nome_seguro() já devia ter impedido isto em
        # _completar(), mas um caminho de escrita nunca deve confiar só numa
        # camada de validação a montante.
        raise ValueError(f"caminho de destino fora de {destino_raiz}: {caminho}")

    if descarga.get("sha256") and caminho.exists():
        if sha256_ficheiro(caminho) == descarga["sha256"]:
            return registo.actualizar(item, descarga={**descarga, "estado": "ja_existente"})

    cabecalhos = {}
    if descarga.get("etag"):
        cabecalhos["If-None-Match"] = descarga["etag"]
    if descarga.get("last_modified"):
        cabecalhos["If-Modified-Since"] = descarga["last_modified"]
    if (
        not caminho.exists()
        or not descarga.get("sha256")
        or (sha256_ficheiro(caminho) != descarga["sha256"])
    ):
        # Falta a cópia neste destino, ou está diferente. Um 304 baseado no
        # ETag anterior não provaria que esta cópia local está correta.
        cabecalhos = {}

    erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            validar_url(item["url"])
            resposta = abridor(item["url"], cabecalhos)
        except ErroRede as e:
            erro = str(e)
            if isinstance(e, ErroURL):
                break  # não vale a pena repetir
            time.sleep(min(2**tentativa, 8))
            continue
        if resposta.estado == 304:
            erro = "HTTP 304 sem cópia local verificada"
            break
        if resposta.estado == 200:
            if not resposta.corpo.startswith(b"%PDF"):
                erro = "a resposta não é um PDF"
                break
            if caminho.exists() and not descarga.get("sha256"):
                if sha256_ficheiro(caminho) != hashlib.sha256(resposta.corpo).hexdigest():
                    erro = "conflito: PDF local sem hash registado; não foi substituído"
                    break
            _escrever_atomico(caminho, resposta.corpo)
            cab = {k.lower(): v for k, v in resposta.cabecalhos.items()}
            return registo.actualizar(
                item,
                descarga={
                    "estado": "descarregado",
                    "data": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "bytes": len(resposta.corpo),
                    "sha256": hashlib.sha256(resposta.corpo).hexdigest(),
                    "etag": cab.get("etag", ""),
                    "last_modified": cab.get("last-modified", ""),
                    "caminho": str(caminho),
                },
            )
        erro = f"HTTP {resposta.estado}"
        if 400 <= resposta.estado < 500:
            break
        time.sleep(min(2**tentativa, 8))

    return registo.actualizar(
        item, descarga={**descarga, "estado": "falhado", "erro": erro or "sem resposta"}
    )


INTERVALO_PERSISTENCIA = 20  # guardar o registo a cada N pedidos de rede,
# não só no fim — uma corrida interrompida a
# meio não deve perder o que já foi descarregado


def recolher(
    indices: list[Path],
    destino: Path,
    registo: Registo,
    *,
    rede: bool = False,
    familias: tuple[str, ...] = FAMILIAS_POR_OMISSAO,
    abridor=None,
    pausa: float = 1.0,
    limite: int | None = None,
) -> dict:
    """Percorre os índices e descarrega o que ainda não está cá.

    Com `rede=False` (omissão) não é aberta nenhuma ligação: os documentos em
    falta ficam com estado `por_descarregar`.

    O registo é guardado a cada `INTERVALO_PERSISTENCIA` pedidos de rede e
    sempre no fim, mesmo em caso de excepção — uma corrida interrompida a
    meio (rede, Ctrl-C, suspensão) não obriga a redescarregar tudo.
    """
    if not math.isfinite(pausa) or pausa < 0 or (limite is not None and limite < 0):
        raise ValueError("Pausa deve ser finita e não negativa; limite não pode ser negativo.")
    abridor = abridor or abridor_urllib
    resumo: dict[str, Any] = {
        "indices": [],
        "por_estado": {},
        "tipos_desconhecidos": {},
        "problemas": [],
        "documentos": 0,
    }
    pedidos = 0

    def contar(estado):
        resumo["por_estado"][estado] = resumo["por_estado"].get(estado, 0) + 1

    try:
        for indice in indices:
            try:
                itens = ler_indice(indice, problemas=resumo["problemas"])
            except (ValueError, OSError) as exc:
                resumo["problemas"].append(f"{indice.name}: {exc}")
                continue
            resumo["indices"].append({"ficheiro": indice.name, "linhas": len(itens)})
            for item in itens:
                resumo["documentos"] += 1
                anterior = (registo.get(item["chave"]) or {}).get("descarga") or {}
                if item["familia"] is None:
                    tipo = item.get("tipo") or "(sem tipo)"
                    resumo["tipos_desconhecidos"][tipo] = (
                        resumo["tipos_desconhecidos"].get(tipo, 0) + 1
                    )
                    registo.actualizar(
                        item,
                        descarga={
                            **anterior,
                            "estado": "ignorado",
                            "motivo": f"tipo desconhecido: {tipo}",
                        },
                    )
                    contar("ignorado")
                    continue
                if item["familia"] not in familias:
                    registo.actualizar(
                        item,
                        descarga={
                            **anterior,
                            "estado": "ignorado",
                            "motivo": f"família fora do âmbito: {item['familia']}",
                        },
                    )
                    contar("ignorado")
                    continue
                if not item["url"]:
                    resumo["problemas"].append(f"{item['chave']}: sem ligação para o documento")
                    registo.actualizar(item, descarga={"estado": "falhado", "erro": "sem URL"})
                    contar("falhado")
                    continue

                caminho_atual = destino / str(item["ano"]) / str(item["num_bte"]) / item["ficheiro"]
                if (
                    anterior.get("sha256")
                    and caminho_atual.is_file()
                    and sha256_ficheiro(caminho_atual) == anterior["sha256"]
                ):
                    registo.actualizar(
                        item,
                        descarga={
                            **anterior,
                            "caminho": str(caminho_atual),
                            "estado": "ja_existente",
                        },
                    )
                    contar("ja_existente")
                    continue

                if not rede:
                    registo.actualizar(item, descarga={**anterior, "estado": "por_descarregar"})
                    contar("por_descarregar")
                    continue

                if limite is not None and pedidos >= limite:
                    registo.actualizar(item, descarga={**anterior, "estado": "por_descarregar"})
                    contar("por_descarregar")
                    continue

                if pedidos and pausa:
                    time.sleep(pausa)
                pedidos += 1
                entrada = descarregar_item(item, destino, registo, abridor=abridor)
                estado = entrada["descarga"]["estado"]
                contar(estado)
                if estado == "falhado":
                    resumo["problemas"].append(
                        f"{item['chave']}: {entrada['descarga'].get('erro')}"
                    )
                if pedidos % INTERVALO_PERSISTENCIA == 0:
                    registo.guardar()
    finally:
        registo.guardar()
    resumo["pedidos_de_rede"] = pedidos
    return resumo


def texto_resumo(resumo: dict, *, rede: bool) -> str:
    linhas = ["== Recolha do BTE"]
    for i in resumo["indices"]:
        linhas.append(f"  índice {i['ficheiro']}: {i['linhas']} documento(s)")
    linhas.append(f"  documentos no total: {resumo['documentos']}")
    for estado, n in sorted(resumo["por_estado"].items()):
        linhas.append(f"    {estado}: {n}")
    linhas.append(
        f"  pedidos de rede: {resumo['pedidos_de_rede']}"
        + ("" if rede else "  (rede desligada — simulação)")
    )
    if resumo["tipos_desconhecidos"]:
        linhas.append("  tipos que a tabela não conhece (não descarregados):")
        for tipo, n in sorted(resumo["tipos_desconhecidos"].items()):
            linhas.append(f"    {tipo}: {n}")
    if resumo["problemas"]:
        linhas.append("  PROBLEMAS:")
        linhas.extend(f"    {p}" for p in resumo["problemas"])
    return "\n".join(linhas)


def main(argv=None):
    utf8_output()
    p = argparse.ArgumentParser(
        prog="crl_markdown.recolha",
        description="Descarrega os documentos do BTE a partir dos ficheiros-índice. "
        "A rede está desligada por omissão.",
    )
    add_arguments(p)
    return collect(p.parse_args(argv))


def add_arguments(p):
    """Argumentos partilhados entre a CLI principal e o módulo autónomo."""
    p.add_argument(
        "--indices",
        default=str(INDICES_OMISSAO),
        help="pasta com os .xlsx dos índices, ou um ficheiro",
    )
    p.add_argument("--destino", default=str(DESTINO_OMISSAO))
    p.add_argument("--registo", default=str(REGISTO_OMISSAO))
    p.add_argument(
        "--familias",
        default=",".join(FAMILIAS_POR_OMISSAO),
        help="famílias a descarregar (convencao,extensao,aviso,adesao)",
    )
    p.add_argument(
        "--confirmar-rede", action="store_true", help="autoriza os pedidos de rede nesta corrida"
    )
    p.add_argument(
        "--pausa",
        type=float,
        default=1.0,
        help="segundos entre pedidos (por civilidade com o servidor)",
    )
    p.add_argument("--limite", type=int, help="máximo de descargas nesta corrida")


def collect(args):
    """Executa a recolha com os argumentos já validados pelo parser."""
    caminho_indices = Path(args.indices)
    if caminho_indices.is_dir():
        indices = sorted(caminho_indices.glob("*.xlsx"))
    else:
        indices = [caminho_indices]
    indices = [i for i in indices if i.is_file() and not i.name.startswith("~$")]
    if not indices:
        raise ValueError(f"Sem ficheiros-índice em {args.indices} (ver README.md, recolha do BTE)")

    familias = tuple(f.strip() for f in args.familias.split(",") if f.strip())
    if not familias or set(familias) - set(FAMILIAS_POR_OMISSAO):
        raise ValueError("Famílias inválidas: usar convencao, extensao, adesao ou aviso.")
    rede = args.confirmar_rede or os.environ.get("CRL_RECOLHA_REDE") == "1"
    registo = Registo.carregar(Path(args.registo))
    resumo = recolher(
        indices,
        Path(args.destino),
        registo,
        rede=rede,
        familias=familias,
        pausa=args.pausa,
        limite=args.limite,
    )
    print(texto_resumo(resumo, rede=rede))
    if not rede and resumo["por_estado"].get("por_descarregar"):
        print("\nPara descarregar mesmo: repetir com --confirmar-rede")
    return 1 if resumo["problemas"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        raise SystemExit(f"Erro: {exc}") from exc
