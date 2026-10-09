"""Nomeação dos documentos recolhidos no esquema de nomes do RNC (ADR-0022).

Portado de crl-app-cct (cct/nomeacao.py, commit 5fd8ae8), só com o esquema
obrigatório a partir do corpus de 2026; o esquema de 2025 e a migração do
ADR-0016 ficam no projeto original. Corre offline e pode repetir-se: lê o
registo da recolha, deriva as siglas dos outorgantes e copia cada PDF para

    data/raw/bte/bte_2026/convencoes/PRI/2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+3.pdf
    data/raw/bte/bte_2026/portarias_extensao/2026_BTE_01_PE_012_0452-2025_27251_ACRAL-CESP.pdf
    data/raw/bte/bte_2026/acordos_adesao/2026_BTE_12_AA_412_27251_ABC-CESP.pdf
    data/raw/bte/bte_2026/acordaos/2026_BTE_05_JUR_101_27251_ACRAL-CESP.pdf

Esquema: cabeça comum `{ANO}_BTE_{NN}_{X}_{SEQ}`, miolo próprio de cada família
e cauda comum `{CODIRCT}_{SIGLA1}-{SIGLA2}[+N]`, até 63 caracteres (limite do
MAXQDA). Um nome atribuído não muda: um documento sem os dados de que o nome
precisa, ou com siglas adivinhadas, fica `por_confirmar` e não é escrito.
"""

import csv
import re
import shutil
import time
from pathlib import Path
from typing import Any

from . import ambito as mod_ambito
from .recolha import INTERVALO_PERSISTENCIA, Registo, familia, sem_acentos, sha256_ficheiro

# O siglas.csv da equipa, na pasta de trabalho (não vem no repositório). Uma
# sigla confirmada uma vez não volta a ser perguntada.
SIGLAS_EQUIPA = Path("siglas.csv")
# As siglas do registo de organizações da DGERT, versionadas com o código.
SIGLAS_DGERT = Path(__file__).resolve().parent / "vocabularios" / "siglas_organizacoes.csv"

MAX_SIGLAS = 2  # a primeira patronal e a primeira sindical; o resto em "+N"

# Quarto campo do nome nas famílias que não são convenção: o tipo, num
# vocabulário fechado. Um tipo fora dele não é forçado num nome; fica por
# confirmar, para decisão registada (ADR-0022, «Revisitar quando»).
#
# Acórdãos: decisão da equipa de 2026-10-09. Família própria; `JUR`
# (jurisprudência), e não `AC`, para não se confundir com ACT nem com acordo.
QUARTO_CAMPO_TIPO = {
    "extensao": ("PE", "PCT", "PRT"),
    "adesao": ("AA",),
    "acordao": ("JUR",),
    "aviso": ("AVISO", "AV"),
}
# Tipos que o índice escreve por extenso → código do quarto campo.
TIPO_POR_EXTENSO = {"ADESAO": "AA", "ACORDAO": "JUR"}

AVISO_BASE_PELA_CADEIA = (
    "código da convenção de base lido da cadeia de alterações do índice — "
    "confirmar (SPEC-0004, passo 0)"
)

# Cada família tem a sua pasta; o âmbito só subdivide as convenções, que são o
# que o pipeline temático lê. Portarias, adesões e acórdãos referem-se a uma
# convenção, mas não têm o articulado que a codificação pressupõe.
PASTA_FAMILIA = {
    "convencao": "convencoes",
    "extensao": "portarias_extensao",
    "adesao": "acordos_adesao",
    "acordao": "acordaos",
}
PASTA_FAMILIA_DESCONHECIDA = "por_classificar"
FAMILIAS_COM_AMBITO = frozenset({"convencao"})
# O aviso existe só como metadado de outro documento: tem linha no catálogo,
# não tem ficheiro.
FAMILIAS_SO_METADADO = frozenset({"aviso"})

ESTADOS_COM_FICHEIRO = {"descarregado", "ja_existente", "inalterado"}

MAX_NOME = 63  # limite de nome de documento do MAXQDA
MAX_SIGLA = 20
MIN_CHAVE_PARCIAL = 12  # ver a nota em sigla(), sobre correspondência parcial


class NomeRNCInvalido(ValueError):
    """Os metadados não permitem um nome íntegro: falta um campo estrutural
    (código da convenção de base, referência da portaria, tipo conhecido) ou o
    nome não cabe no limite sem cortar a cabeça. O ficheiro não é escrito."""


# `CCT-ALT.20250708.321/2025` → tipo, data, sequencial/ano do documento referido.
RE_ALTERA = re.compile(
    r"^\s*(?P<tipo>[A-Z][A-Z-]*)\.(?P<data>\d{8})\.(?P<seq>\d+)/(?P<ano>\d{4})\s*$"
)

# «Portaria n.º 452/2025», «Portaria n.º 50-A/2025», «Portaria nº 7/2026».
RE_PORTARIA = re.compile(
    r"\bPortaria\s+n\.?\s*[º°o]?\s*(?P<num>\d{1,4})"
    r"(?:\s*-\s*(?P<suf>[A-Za-z]))?\s*/\s*(?P<ano>\d{4})\b",
    re.IGNORECASE,
)

LIGACOES = {"de", "do", "da", "dos", "das", "e", "em", "a", "o", "as", "os",
            "no", "na", "nos", "nas", "para", "com", "ao", "aos", "à", "às"}  # fmt: skip
FORMA_JURIDICA = {"sa", "s", "lda", "ldª", "l", "da", "unipessoal", "crl",
                  "sarl", "sgps", "inc", "sucursal", "limitada",
                  "sociedade", "em", "ea", "eim", "ldas"}  # fmt: skip
# Palavras que quase todas as organizações têm e que não distinguem ninguém.
GENERICOS = {"sindicato", "sindicatos", "sindical", "sindicais", "associacao",
             "associacoes", "federacao", "confederacao", "uniao", "nacional",
             "nacionais", "trabalhadores", "trabalhadoras", "profissionais",
             "portugues", "portuguesa", "portugueses", "portugal"}  # fmt: skip

RE_PARENTESES = re.compile(r"\(([^)]{2,30})\)")
RE_FORMA_NO_FIM = re.compile(
    r"(?:,?\s*(?:S\.?\s*A\.?|L\.?da\.?|Lda|CRL|E\.?\s*P\.?\s*E\.?|E\.?\s*M\.?"
    r"|E\.?\s*I\.?\s*M\.?|Unipessoal))+\s*$",
    re.IGNORECASE,
)
RE_FIM_APOS_TRACO = re.compile(r"[-–—]\s*([^-–—,;()]{2,30})\s*$")
RE_INICIO_ANTES_TRACO = re.compile(r"^\s*([^-–—,;()]{2,30}?)\s*[-–—]\s")
RE_ENTRE_TRACOS = re.compile(r"[-–—]\s*([^-–—,;()]{2,30}?)\s*(?=[-–—]|$)")
RE_PARTES_TITULO = re.compile(
    r"\bentre\s+(?:a|o|as|os)?\s*(?P<a>.+?)\s+e\s+(?:a|o|as|os)\s+(?P<b>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


# ------------------------------------------------------------------- siglas


def _e_sigla(token: str) -> bool:
    """'ACRAL' e 'AEVP' sim; 'Sindicato' e 'L.da' não."""
    limpo = re.sub(r"[^A-Za-z0-9]", "", sem_acentos(token))
    if len(limpo) < 2 or len(limpo) > MAX_SIGLA:
        return False
    letras = [c for c in limpo if c.isalpha()]
    return bool(letras) and all(c.isupper() for c in letras)


def _limpar_sigla(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", sem_acentos(token))


def normalizar_sigla(valor: str) -> str:
    """A sigla como entra no nome: só letras e algarismos, sem acentos."""
    return _limpar_sigla(valor)[:MAX_SIGLA]


def chave_entidade(nome: str) -> str:
    """A regra única de «a mesma entidade» na tabela de siglas."""
    return sem_acentos((nome or "").strip().strip(" .;,")).lower()


def _camel(nome: str, max_chars: int = MAX_SIGLA) -> str:
    """Recurso quando não há sigla: 'Águas do Norte' → 'AguasNorte'."""
    uteis = []
    for bruto in re.split(r"[^\wÀ-ÿ]+|_+", sem_acentos(nome)):
        baixo = bruto.lower()
        if not bruto or len(bruto) < 2:
            continue
        if baixo in LIGACOES or baixo in FORMA_JURIDICA:
            continue
        uteis.append(bruto if bruto.isupper() else bruto.capitalize())
    distintivas = [p for p in uteis if p.lower() not in GENERICOS]
    saida = ""
    for p in (distintivas or uteis)[:4]:
        if len(saida) + len(p) > max_chars and saida:
            break
        saida += p
    return saida[:max_chars] or "SemNome"


def sigla(nome: str, tabela: dict[str, str] | None = None) -> tuple[str, str | None]:
    """Sigla de um outorgante. Devolve (sigla, aviso); há aviso quando é derivada."""
    nome = (nome or "").strip(" .;,")
    if not nome:
        return "", "outorgante vazio"
    if tabela:
        chave = chave_entidade(nome)
        if chave in tabela:
            return tabela[chave], None
        # Correspondência parcial, só com chaves longas e ganha a mais longa:
        # numa tabela de milhares de entradas, uma chave curta encaixa por
        # acaso dentro de outro nome e daria a sigla errada em silêncio.
        melhor = max(
            (k for k in tabela if len(k) >= MIN_CHAVE_PARCIAL and k in chave),
            key=len,
            default=None,
        )
        if melhor:
            return tabela[melhor], None
    # A forma jurídica no fim esconde a sigla que vem antes dela:
    # «Imprensa Nacional - Casa da Moeda, SA - INCM, SA» tem a sigla INCM.
    sem_forma = RE_FORMA_NO_FIM.sub("", nome)
    for texto in dict.fromkeys((nome, sem_forma)):
        for regex in (RE_PARENTESES, RE_FIM_APOS_TRACO, RE_INICIO_ANTES_TRACO, RE_ENTRE_TRACOS):
            for m in regex.finditer(texto):
                if _e_sigla(m.group(1)):
                    return _limpar_sigla(m.group(1)), None
    return _camel(nome), f"sigla derivada de «{nome[:60]}» — confirmar"


def e_sindical(nome: str) -> bool:
    """Sindical é quem tem 'sindic' no nome."""
    return "sindic" in sem_acentos(nome).lower()


def _partes_do_titulo(titulo: str) -> list[str]:
    """'Contrato coletivo entre a X e o Y' → ['X', 'Y'] (para as retificações)."""
    m = RE_PARTES_TITULO.search(re.sub(r"\s+", " ", titulo or ""))
    if not m:
        return []
    partes = []
    for lado in (m.group("a"), m.group("b")):
        lado = re.sub(r"\s+e\s+outr[ao]s?\s*$", "", lado, flags=re.IGNORECASE)
        partes.append(lado.strip(" .,;"))
    return [p for p in partes if p]


def separar_outorgantes(outorgantes: str, titulo: str = "") -> tuple[list[str], list[str]]:
    """Divide os outorgantes em (patronais, sindicais)."""
    nomes = [n.strip() for n in re.split(r"[;\n]", outorgantes or "") if n.strip()]
    if not nomes:
        nomes = _partes_do_titulo(titulo)
    return [n for n in nomes if not e_sindical(n)], [n for n in nomes if e_sindical(n)]


def _outorgantes_escolhidos(entrada: dict, maximo: int = MAX_SIGLAS):
    """Os outorgantes que entram no nome, todos os outorgantes, e os avisos."""
    avisos: list[str] = []
    nomes = [n.strip() for n in re.split(r"[;\n]", entrada.get("outorgantes") or "") if n.strip()]
    if not nomes:
        nomes = _partes_do_titulo(entrada.get("titulo", ""))
        if nomes:
            avisos.append("outorgantes lidos do título — confirmar")
    if not nomes:
        return [], [], avisos + ["sem outorgantes no índice nem no título"]
    patronais = [n for n in nomes if not e_sindical(n)]
    sindicais = [n for n in nomes if e_sindical(n)]
    if patronais and sindicais:
        escolhidos = [patronais[0], sindicais[0]][:maximo]
    else:
        escolhidos = nomes[:maximo]
        lado = "patronal" if patronais else "sindical"
        avisos.append(
            f"só há partes do lado {lado} — o nome usa as {len(escolhidos)} "
            "primeira(s) pela ordem do índice; confirmar"
        )
    return escolhidos, nomes, avisos


def siglas_outorgantes(entrada: dict, tabela: dict[str, str] | None = None):
    """A primeira sigla patronal e a primeira sindical, e quantas partes sobram."""
    escolhidos, nomes, avisos = _outorgantes_escolhidos(entrada)
    if not nomes:
        return [], 0, avisos
    siglas: list[str] = []
    for nome in escolhidos:
        valor, aviso = sigla(nome, tabela)
        if aviso:
            avisos.append(aviso)
        if valor:
            siglas.append(valor)
    return siglas, max(0, len(nomes) - len(siglas)), avisos


COLUNAS_NOME = ("nome", "nome_completo", "denominacao", "denominacao_da_organizacao", "organizacao")
COLUNAS_SIGLA = ("sigla", "acronimo", "sigla_canonica")
COLUNA_ORIGEM = "origem_sigla"
# Uma sigla inventada por _camel() não é uma sigla confirmada; não se carrega.
ORIGENS_IGNORADAS = frozenset({"recurso"})


def carregar_siglas(caminho: Path) -> dict[str, str]:
    """Tabela de siglas → {nome normalizado: sigla}.

    Aceita `nome;sigla` sem cabeçalho (o siglas.csv da equipa) ou um CSV com
    cabeçalho, com as colunas encontradas pelo nome (o
    `vocabularios/siglas_organizacoes.csv`). Separador `;`, UTF-8 com ou sem BOM.
    """
    tabela: dict[str, str] = {}
    try:
        texto = Path(caminho).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        # O Excel em Windows guarda «CSV (separado por ponto e vírgula)» em cp1252.
        texto = Path(caminho).read_text(encoding="cp1252")
    linhas = [
        linha
        for linha in csv.reader(texto.splitlines(), delimiter=";")
        if linha and linha[0].strip()
    ]
    if not linhas:
        return tabela
    i_nome, i_sigla = 0, 1
    cabecalho = [
        re.sub(r"[^a-z0-9]+", "_", sem_acentos(c).strip().lower()).strip("_") for c in linhas[0]
    ]
    tem_cabecalho = any(c in COLUNAS_NOME for c in cabecalho)
    if tem_cabecalho:
        i_nome = next(i for i, c in enumerate(cabecalho) if c in COLUNAS_NOME)
        candidatos = [i for i, c in enumerate(cabecalho) if c in COLUNAS_SIGLA]
        if not candidatos:
            return tabela
        i_sigla = candidatos[0]
        linhas = linhas[1:]
    i_origem = (
        cabecalho.index(COLUNA_ORIGEM) if tem_cabecalho and COLUNA_ORIGEM in cabecalho else None
    )
    for linha in linhas:
        if max(i_nome, i_sigla) >= len(linha):
            continue
        # A origem pode vir composta (`recurso+desambiguada`): conta a primeira parte.
        if (
            i_origem is not None
            and i_origem < len(linha)
            and linha[i_origem].strip().lower().split("+")[0] in ORIGENS_IGNORADAS
        ):
            continue
        nome = chave_entidade(linha[i_nome])
        valor = normalizar_sigla(linha[i_sigla])
        if nome and valor:
            tabela.setdefault(nome, valor)
    return tabela


def tabela_de_siglas(caminhos=(), *, equipa: Path = SIGLAS_EQUIPA, dgert: bool = True):
    """O siglas.csv da equipa primeiro (ganha), depois os indicados e o da DGERT."""
    ordem = [Path(equipa)] if Path(equipa).is_file() else []
    ordem += [Path(c) for c in caminhos]
    if dgert and SIGLAS_DGERT.is_file():
        ordem.append(SIGLAS_DGERT)
    tabela: dict[str, str] = {}
    for caminho in ordem:
        for nome, valor in carregar_siglas(caminho).items():
            tabela.setdefault(nome, valor)
    return tabela


def siglas_derivadas(entrada: dict, tabela: dict[str, str] | None = None):
    """(outorgante, sigla sugerida) das siglas do nome que foram adivinhadas."""
    escolhidos, _nomes, _avisos = _outorgantes_escolhidos(entrada)
    derivadas = []
    for nome in escolhidos:
        valor, aviso = sigla(nome, tabela)
        if aviso and valor:
            derivadas.append((nome.strip(" .;,"), valor))
    return derivadas


def escrever_siglas_pendentes(pendentes: dict, caminho: Path) -> Path | None:
    """Escreve `nome;sigla;documentos;atencao` das siglas adivinhadas, para revisão.

    O ficheiro é refeito a cada corrida e apagado quando não há pendentes. As
    duas primeiras colunas têm o formato do siglas.csv da equipa: revistas e
    corrigidas, as linhas passam para lá, ou o ficheiro inteiro entra numa
    corrida com `--siglas`. Escreve-se com BOM, para o Excel abrir os acentos.
    """
    caminho = Path(caminho)
    if not pendentes:
        caminho.unlink(missing_ok=True)
        return None
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";", lineterminator="\n")
        # A mesma sigla sugerida para entidades diferentes daria a dois
        # outorgantes distintos o mesmo nome; assinala-se para decidir.
        por_sigla: dict[str, list[str]] = {}
        for nome, dados in pendentes.items():
            por_sigla.setdefault(dados["sigla"], []).append(nome)
        escritor.writerow(["nome", "sigla", "documentos", "atencao"])
        for nome, dados in sorted(pendentes.items(), key=lambda i: (-len(i[1]["documentos"]), i[0])):
            outros = [n for n in por_sigla[dados["sigla"]] if n != nome]
            atencao = ("mesma sigla sugerida para: " + "; ".join(outros)) if outros else ""
            escritor.writerow([nome, dados["sigla"], " ".join(dados["documentos"]), atencao])
    return caminho


# ------------------------------------------------------------------- campos


def sequencial_bte(entrada: dict) -> int | None:
    """O «377» de `ID: 377/2026`: a posição do documento na série anual do BTE."""
    bruto = str(entrada.get("id_dgert") or "").strip()
    m = re.match(r"^\s*(\d+)\s*/\s*(\d{4})\s*$", bruto)
    if m:
        return int(m.group(1))
    return int(bruto) if re.match(r"^\d+$", bruto) else None


def tipo_normalizado(tipo: str | None) -> str:
    """`CCT-ALT-RECT` a partir do que vier no índice; `SEMTIPO` se vier vazio."""
    limpo = re.sub(r"[^A-Z0-9-]", "", sem_acentos(tipo or "").upper())
    limpo = re.sub(r"-{2,}", "-", limpo).strip("-")
    return limpo or "SEMTIPO"


def referencia_portaria(entrada: dict) -> tuple[int, str, int] | None:
    """`(número, sufixo, ano do DR)` da portaria, ou `None` se não for certo."""
    ano_bte = int(entrada.get("ano") or 0)
    for fonte in (entrada.get("portaria_dr"), entrada.get("titulo")):
        texto = str(fonte or "").strip()
        if not texto:
            continue
        m = RE_PORTARIA.search(texto if "ortaria" in texto else f"Portaria n.º {texto}")
        if not m:
            continue
        numero, ano_dr = int(m.group("num")), int(m.group("ano"))
        # A portaria sai no DR antes de ser publicitada no BTE.
        if numero == 0 or (ano_bte and ano_dr > ano_bte):
            return None
        return numero, (m.group("suf") or "").upper(), ano_dr
    return None


def _codigos(valor) -> list[str]:
    """`"27251; 26760"` → `["27251", "26760"]`, pela ordem, sem repetidos."""
    partes = (re.sub(r"\D", "", p) for p in re.split(r"[;,\s]+", str(valor or "")))
    return list(dict.fromkeys(c for c in partes if c))


def _familia(entrada: dict) -> str:
    return entrada.get("familia") or familia(entrada.get("tipo", "")) or "convencao"


def cod_irct_base(entrada: dict) -> str | None:
    """O código IRCT do nome: o próprio numa convenção, o da convenção de base
    nas outras famílias (resolvido por `resolver_convencoes_base`)."""
    campo = "cod_irct" if _familia(entrada) == "convencao" else "cod_irct_base"
    codigos = _codigos(entrada.get(campo))
    return codigos[0] if codigos else None


def resolver_convencoes_base(entradas) -> None:
    """Liga cada documento que não é convenção ao código da convenção de base.

    A cadeia de alterações do índice (`CCT.20260822.377/2026`) aponta para o
    documento de base. Se ele estiver entre as `entradas`, com o mesmo tipo e o
    mesmo `IDDocumento`, o seu código IRCT é o da base. Sem correspondência
    exata, o código fica por resolver e o nome por confirmar.
    """
    entradas = list(entradas)
    convencoes: dict[tuple[str, str], list[dict]] = {}
    for e in entradas:
        if _familia(e) != "convencao":
            continue
        m = re.match(r"^\s*(\d+)\s*/\s*(\d{4})\s*$", str(e.get("id_dgert") or ""))
        if m:
            convencoes.setdefault((str(int(m.group(1))), m.group(2)), []).append(e)
    for e in entradas:
        if _familia(e) == "convencao":
            continue
        if e.get("cod_irct_base") and e.get("cod_irct_base_origem") != "cadeia_do_indice":
            e.setdefault("cod_irct_base_origem", "indice")
            continue
        codigos: list[str] = []
        por_resolver: list[str] = []
        for ref in re.split(r"[;\n]", e.get("altera") or ""):
            if not ref.strip():
                continue
            m = RE_ALTERA.match(ref)
            alvos = []
            if m:
                alvos = [
                    c
                    for c in convencoes.get((str(int(m.group("seq"))), m.group("ano")), [])
                    if tipo_normalizado(c.get("tipo")) == m.group("tipo")
                ]
            cods = _codigos(alvos[0].get("cod_irct")) if len(alvos) == 1 else []
            if cods:
                codigos.append(cods[0])
            else:
                por_resolver.append(ref.strip())
        codigos = list(dict.fromkeys(codigos))
        e["cod_irct_base"] = "; ".join(codigos)
        e["cod_irct_base_origem"] = "cadeia_do_indice" if codigos else ""
        e["cod_irct_base_por_resolver"] = "; ".join(por_resolver)


# --------------------------------------------------------------------- nome


def nome_documento(
    entrada: dict, ordinal: int, tabela: dict[str, str] | None = None, *, vocabulario_ambito=None
) -> tuple[str, list[str]]:
    """Nome (sem extensão) no esquema do ADR-0022 e os avisos a confirmar.

        convenção   {ANO}_BTE_{NN}_{AMBITO}_{SEQ}_{TIPO}_{CODIRCT}_{SIGLAS}
        portaria    {ANO}_BTE_{NN}_{TIPO}_{SEQ}_{NNNN}-{AAAA}_{CODIRCT}_{SIGLAS}
        adesão      {ANO}_BTE_{NN}_AA_{SEQ}_{CODIRCT}_{SIGLAS}
        acórdão     {ANO}_BTE_{NN}_JUR_{SEQ}_{CODIRCT}_{SIGLAS}

    `NomeRNCInvalido` diz que falta um campo estrutural e que o ficheiro não
    pode ser escrito de todo. Sem `vocabulario_ambito`, usa o do pacote.
    """
    if vocabulario_ambito is None:
        vocabulario_ambito = mod_ambito.vocabulario_por_omissao()
    avisos: list[str] = []
    ano = int(entrada.get("ano") or 0)
    num_bte = int(entrada.get("num_bte") or 0)
    tipo = tipo_normalizado(entrada.get("tipo"))
    fam = _familia(entrada)

    seq = sequencial_bte(entrada)
    if seq is None:
        seq = ordinal
        avisos.append(
            f"sem «ID: nnn/aaaa» no índice — usado o ordinal interno ({ordinal}); "
            "o número não corresponde ao do boletim"
        )

    patronais, _sindicais = separar_outorgantes(
        entrada.get("outorgantes", ""), entrada.get("titulo", "")
    )
    amb, origem, aviso_amb = mod_ambito.classificar_com_ine(
        patronais[0] if patronais else entrada.get("titulo", ""),
        entrada.get("tipo", ""),
        vocabulario_ambito,
    )
    entrada.setdefault("nomeacao", {}).update({"ambito": amb, "ambito_origem": origem})

    if fam in QUARTO_CAMPO_TIPO:
        # O âmbito não entra no nome destas famílias; fica no catálogo.
        quarto = TIPO_POR_EXTENSO.get(tipo.split("-")[0], tipo)
        if quarto not in QUARTO_CAMPO_TIPO[fam]:
            raise NomeRNCInvalido(
                f"tipo {tipo} fora do vocabulário do quarto campo "
                f"({', '.join(QUARTO_CAMPO_TIPO[fam])}) — decisão registada necessária"
            )
        miolo = ""
        if fam == "extensao":
            ref = referencia_portaria(entrada)
            if ref is None:
                raise NomeRNCInvalido(
                    "sem número e ano da portaria no Diário da República "
                    "(título ou coluna do índice)"
                )
            numero, sufixo, ano_dr = ref
            miolo = f"_{numero:04d}{sufixo}-{ano_dr:04d}"
            entrada["nomeacao"]["portaria_dr"] = (
                f"{numero}{'-' + sufixo if sufixo else ''}/{ano_dr}"
            )
        cod = cod_irct_base(entrada)
        if cod is None:
            if fam == "aviso":  # sem ficheiro: o nome é só chave de catálogo
                cod = (_codigos(entrada.get("cod_irct")) or ["0"])[0]
            else:
                raise NomeRNCInvalido(
                    "sem código IRCT da convenção de base confirmado (SPEC-0004, passo 0)"
                )
        elif fam != "aviso":
            if entrada.get("cod_irct_base_origem") == "cadeia_do_indice":
                avisos.append(AVISO_BASE_PELA_CADEIA)
            todos = _codigos(entrada.get("cod_irct_base"))
            if len(todos) > 1:
                avisos.append(
                    f"refere {len(todos)} convenções ({', '.join(todos)}) — o nome "
                    "leva a primeira; as restantes estão no catálogo"
                )
    else:
        if aviso_amb:
            avisos.append(aviso_amb)
        if tipo == "SEMTIPO":
            avisos.append("tipo de documento vazio no índice — confirmar")
        quarto, miolo = amb, f"_{tipo}"
        cod = cod_irct_base(entrada)
        if cod is None:
            cod = "0"
            avisos.append("sem COD: (IRCT) no índice — a série da convenção fica por identificar")

    siglas, restantes, avisos_siglas = siglas_outorgantes(entrada, tabela)
    avisos.extend(avisos_siglas)
    if not siglas:
        siglas = [_camel(entrada.get("titulo", ""))]
        avisos.append("nome derivado do título — confirmar")

    prefixo = f"{ano:04d}_BTE_{num_bte:02d}_{quarto}_{seq:03d}{miolo}_{cod}_"
    cauda = f"+{restantes}" if restantes else ""
    nome = prefixo + "-".join(siglas) + cauda
    if len(nome) > MAX_NOME:  # encurta as siglas, nunca a cabeça nem o miolo
        folga = MAX_NOME - len(prefixo) - len(cauda) - (len(siglas) - 1)
        if folga < 3 * len(siglas):
            raise NomeRNCInvalido(
                f"campos estruturais do nome excedem o limite de {MAX_NOME} caracteres; "
                "confirmar tipo e código IRCT"
            )
        por_sigla = folga // len(siglas)
        nome = prefixo + "-".join(s[:por_sigla] for s in siglas) + cauda
        avisos.append(f"nome encurtado para caber em {MAX_NOME} caracteres")
    return nome, avisos


def atribuir_ordinais(registo: Registo, familias) -> int:
    """Numera os documentos por ano e família; um ordinal atribuído não muda.

    O ordinal só entra no nome quando falta o `IDDocumento` (com aviso).
    """
    novos = 0
    grupos: dict[tuple, list[dict]] = {}
    for e in registo.entradas.values():
        if (
            e.get("familia") in familias
            and (e.get("descarga") or {}).get("estado") in ESTADOS_COM_FICHEIRO
        ):
            grupos.setdefault((e.get("ano"), e.get("familia")), []).append(e)
    for grupo in grupos.values():
        usados = {o for e in grupo if (o := (e.get("nomeacao") or {}).get("ordinal"))}
        proximo = max(usados) + 1 if usados else 1
        por_atribuir = [e for e in grupo if not (e.get("nomeacao") or {}).get("ordinal")]
        por_atribuir.sort(key=lambda e: (e.get("num_bte") or 0, e.get("posicao") or 0, e["chave"]))
        for e in por_atribuir:
            e.setdefault("nomeacao", {})["ordinal"] = proximo
            proximo += 1
            novos += 1
    return novos


# ------------------------------------------------------------------ nomear


def nomear(
    registo: Registo,
    destino: Path,
    *,
    aplicar: bool = False,
    tabela: dict[str, str] | None = None,
    familias=("convencao", "extensao", "adesao", "acordao"),
    aceitar_heuristicas: bool = False,
    vocabulario_ambito: dict[str, str] | None = None,
) -> dict:
    """Atribui nomes e, com `aplicar=True`, copia os PDFs para o destino.

    Um documento com avisos (sigla derivada, outorgante em falta, nome do
    título, nome encurtado, código de base lido da cadeia) fica `por_confirmar`
    e não é escrito: a confirmação tem de acontecer antes de o nome existir,
    porque um nome atribuído não muda. `aceitar_heuristicas=True` desliga esta
    proteção para uma corrida já revista. Um nome novo diferente do que já foi
    escrito é `conflito` e não substitui nada. Sem `vocabulario_ambito`, usa o
    `empregadores_ambito.csv` do pacote.
    """
    if vocabulario_ambito is None:
        vocabulario_ambito = mod_ambito.vocabulario_por_omissao()
    resumo: dict[str, Any] = {
        "ordinais_novos": atribuir_ordinais(registo, familias),
        "por_estado": {},
        "avisos": [],
        "problemas": [],
        "nomes": [],
        "siglas_pendentes": {},
    }
    resolver_convencoes_base(registo.entradas.values())

    def contar(estado):
        resumo["por_estado"][estado] = resumo["por_estado"].get(estado, 0) + 1

    entradas = [
        e
        for e in registo.entradas.values()
        if e.get("familia") in familias
        and e.get("familia") not in FAMILIAS_SO_METADADO
        and (e.get("descarga") or {}).get("estado") in ESTADOS_COM_FICHEIRO
    ]
    entradas.sort(
        key=lambda e: (
            e.get("ano") or 0,
            e.get("num_bte") or 0,
            (e.get("nomeacao") or {}).get("ordinal") or 0,
        )
    )
    vistos: dict[tuple, list[str]] = {}
    escritos = 0
    try:
        for e in entradas:
            nomeacao = e.setdefault("nomeacao", {})
            sha_recolhido = (e.get("descarga") or {}).get("sha256")
            origem = Path((e.get("descarga") or {}).get("caminho", ""))
            if not origem.is_file():
                # A cópia da recolha é descartável; uma cópia nomeada com o
                # mesmo conteúdo serve de origem.
                ja_nomeado = Path(nomeacao.get("caminho") or "")
                if (
                    ja_nomeado.name
                    and ja_nomeado.is_file()
                    and sha256_ficheiro(ja_nomeado) == sha_recolhido
                ):
                    origem = ja_nomeado
                else:
                    resumo["problemas"].append(
                        f"{e['chave']}: PDF recolhido não encontrado ({origem})"
                    )
                    contar("sem_origem")
                    continue
            try:
                nome, avisos = nome_documento(
                    e, nomeacao["ordinal"], tabela, vocabulario_ambito=vocabulario_ambito
                )
            except NomeRNCInvalido as exc:
                nomeacao["estado"] = "por_confirmar"
                nomeacao["avisos"] = [str(exc)]
                resumo["problemas"].append(f"{e['chave']}: {exc} — PDF não escrito")
                contar("por_confirmar")
                continue
            nome_anterior = nomeacao.get("doc_id")
            if (
                nome_anterior
                and nome_anterior != nome
                and nomeacao.get("estado") in {"nomeado", "ja_existente", "conflito"}
            ):
                # Um nome já escrito pode estar no MAXQDA: não se cria outra
                # cópia nem se substitui a identidade em silêncio.
                nomeacao["estado"] = "conflito"
                resumo["problemas"].append(
                    f"{e['chave']}: nome já atribuído {nome_anterior}; novo nome proposto "
                    f"{nome} — nenhum PDF escrito"
                )
                contar("conflito")
                continue
            avisos_heuristica = list(avisos)
            chave_par = (e.get("ano"), e.get("familia"), nome.rsplit("_", 1)[-1])
            vistos.setdefault(chave_par, []).append(nome)
            if len(vistos[chave_par]) > 1:
                avisos.append(
                    "outro documento do mesmo par de outorgantes neste ano: "
                    + ", ".join(vistos[chave_par][:-1])
                )
            fam = e.get("familia") or ""
            pasta = destino / f"bte_{e['ano']}" / PASTA_FAMILIA.get(fam, PASTA_FAMILIA_DESCONHECIDA)
            if fam in FAMILIAS_COM_AMBITO:
                pasta = pasta / nomeacao.get("ambito", mod_ambito.OMISSAO)
            alvo = pasta / f"{nome}.pdf"
            nomeacao.update({"doc_id": nome, "caminho": str(alvo), "avisos": avisos})
            resumo["nomes"].append((e["chave"], nome))
            resumo["avisos"].extend(f"{nome}: {a}" for a in avisos)

            if alvo.exists():
                if sha256_ficheiro(alvo) == sha_recolhido:
                    nomeacao["estado"] = "ja_existente"
                    contar("ja_existente")
                else:
                    nomeacao["estado"] = "conflito"
                    resumo["problemas"].append(
                        f"{nome}: já existe um ficheiro diferente no destino — não foi escrito"
                    )
                    contar("conflito")
                continue
            if avisos_heuristica and not aceitar_heuristicas:
                nomeacao["estado"] = "por_confirmar"
                contar("por_confirmar")
                for outorgante, sugerida in siglas_derivadas(e, tabela):
                    pendente = resumo["siglas_pendentes"].setdefault(
                        outorgante, {"sigla": sugerida, "documentos": []}
                    )
                    pendente["documentos"].append(nome)
                continue
            if not aplicar:
                nomeacao["estado"] = "por_nomear"
                contar("por_nomear")
                continue
            pasta.mkdir(parents=True, exist_ok=True)
            temp = alvo.with_suffix(".pdf.part")
            shutil.copyfile(origem, temp)
            temp.replace(alvo)
            nomeacao.update({"estado": "nomeado", "data": time.strftime("%Y-%m-%dT%H:%M:%S")})
            contar("nomeado")
            escritos += 1
            if escritos % INTERVALO_PERSISTENCIA == 0:
                registo.guardar()
    finally:
        registo.guardar()
    return resumo


def texto_resumo(resumo: dict) -> str:
    linhas = ["== Nomeação (esquema do RNC, ADR-0022)"]
    for estado, n in sorted(resumo["por_estado"].items()):
        linhas.append(f"    {estado}: {n}")
    if not resumo["por_estado"]:
        linhas.append("    nenhum PDF recolhido para nomear")
    if resumo["por_estado"].get("por_confirmar"):
        linhas.append(
            "  (por confirmar: acrescentar as siglas em falta ao siglas.csv da equipa e "
            "repetir, ou aceitar conscientemente o risco com --aceitar-heuristicas)"
        )
    if resumo.get("ficheiro_siglas_pendentes"):
        linhas.append(
            f"  siglas adivinhadas para rever: {len(resumo['siglas_pendentes'])} em "
            f"{resumo['ficheiro_siglas_pendentes']}"
        )
    if resumo["avisos"]:
        linhas.append(f"  a confirmar ({len(resumo['avisos'])}):")
        linhas.extend(f"    {a}" for a in resumo["avisos"])
    if resumo["problemas"]:
        linhas.append("  PROBLEMAS:")
        linhas.extend(f"    {p}" for p in resumo["problemas"])
    return "\n".join(linhas)
