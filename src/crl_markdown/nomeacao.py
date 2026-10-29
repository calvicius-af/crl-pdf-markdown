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
MAXQDA). Um nome atribuído não muda. Relações exatas e rótulos documentais
derivados não exigem confirmação; identidades ausentes, contraditórias ou
explicitamente recusadas continuam `por_confirmar`.
"""

import csv
import re
from pathlib import Path

from . import ambito as mod_ambito
from . import tipologias
from .recolha import Registo, familia, sem_acentos

# O siglas.csv da equipa, na pasta de trabalho (não vem no repositório). Uma
# sigla confirmada uma vez não volta a ser perguntada.
SIGLAS_EQUIPA = Path("siglas.csv")
# As siglas do registo de organizações da DGERT, versionadas com o código.
SIGLAS_DGERT = Path(__file__).resolve().parent / "vocabularios" / "siglas_organizacoes.csv"
SIGLAS_CONSOLIDADAS = Path(__file__).resolve().parent / "vocabularios" / "siglas.csv"
ESQUEMAS = ("v4", "adr0022")

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
    "cessacao": ("CES-VIG",),
}
# Tipos que o índice escreve por extenso → código do quarto campo.
TIPO_POR_EXTENSO = {"ADESAO": "AA", "ACORDAO": "JUR"}

# Cada família tem a sua pasta; o âmbito só subdivide as convenções, que são o
# que o pipeline temático lê. Portarias, adesões e acórdãos referem-se a uma
# convenção, mas não têm o articulado que a codificação pressupõe.
PASTA_FAMILIA = {
    "convencao": "convencoes",
    "extensao": "portarias_extensao",
    "adesao": "acordos_adesao",
    "acordao": "acordaos",
    "cessacao": "cessacoes_vigencia",
    "aviso": "avisos",
}
PASTA_FAMILIA_DESCONHECIDA = "por_classificar"
FAMILIAS_COM_AMBITO = frozenset({"convencao"})
# O rótulo editorial AVISO não elimina o documento nem o seu conteúdo.
FAMILIAS_SO_METADADO = frozenset()

ESTADOS_COM_FICHEIRO = {"descarregado", "ja_existente", "inalterado"}

MAX_NOME = 63  # limite de nome de documento do MAXQDA
MAX_SIGLA = 20


class NomeRNCInvalido(ValueError):
    """Os metadados não permitem um nome íntegro: falta um campo estrutural
    (código da convenção de base, referência da portaria, tipo conhecido) ou o
    nome não cabe no limite sem cortar a cabeça. O ficheiro não é escrito."""


# `CCT-ALT.20250708.321/2025` → tipo, data, sequencial/ano do documento referido.
RE_ALTERA = re.compile(
    r"^\s*(?P<tipo>[A-Z][A-Z-]*)\.\s*(?P<data>\d{8})\.(?P<seq>\d+)/(?P<ano>\d{4})\s*$"
)

# «Portaria n.º 452/2025», «Portaria n.º 50-A/2025», «Portaria nº 7/2026».
RE_PORTARIA = re.compile(
    r"\bPortaria\s+n\.?\s*[º°o]?\s*(?P<num>\d{1,4})"
    r"(?:\s*-\s*(?P<suf>[A-Za-z]))?\s*/\s*(?P<ano>\d{4})\b"
    r"(?:/(?P<serie>[12]))?(?![\d/])",
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
    r"(?:(?:,\s*|\s+)(?:S\.?\s*A\.?|L\.?da\.?|Lda|CRL|E\.?\s*P\.?\s*E\.?|E\.?\s*M\.?"
    r"|E\.?\s*I\.?\s*M\.?|Unipessoal))+\s*$",
    re.IGNORECASE,
)
RE_FIM_APOS_TRACO = re.compile(r"[-–—]\s*([^-–—,;()]{2,30})\s*$")
RE_INICIO_ANTES_TRACO = re.compile(r"^\s*([^-–—,;()]{2,30}?)\s*[-–—]\s")
RE_ENTRE_TRACOS = re.compile(r"[-–—]\s*([^-–—,;()]{2,30}?)\s*(?=[-–—]|$)")
RE_PARTES_TITULO = re.compile(
    r"\bentre\s+(?:(?:as|os|a|o)\s+)?(?P<a>.+?)\s+e\s+(?:as|os|a|o)\s+(?P<b>.+?)\s*$",
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
    return "".join(c.lower() for c in sem_acentos(nome or "") if c.isalnum())


class TabelaSiglas(dict):
    """Valores seguros e identidades recusadas, para não reabrir um fallback literal."""

    def __init__(self):
        super().__init__()
        self.nomes_pendentes = set()
        self.siglas_pendentes = set()
        self.rotulos = {}
        self.permitir_rotulos = False
        self.siglas_recusadas = set()


def informacao(texto):
    return "INFORMAÇÃO: " + texto


def avisos_bloqueantes(avisos):
    """Uma observação de proveniência não é um pedido de decisão humana."""
    return [aviso for aviso in avisos if not aviso.startswith("INFORMAÇÃO: ")]


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
    nome = re.sub(r"\s+e\s+outr[ao]s?\s*$", "", nome, flags=re.IGNORECASE)
    if not nome:
        return "", "outorgante vazio"
    if tabela is not None:
        chave = chave_entidade(nome)
        if chave in tabela:
            return tabela[chave], None
        if chave in getattr(tabela, "rotulos", {}):
            return tabela.rotulos[chave], informacao(
                f"rótulo documental derivado de «{nome}»; não é uma sigla oficial confirmada")
        if chave in getattr(tabela, "nomes_pendentes", set()):
            return _camel(nome), f"sigla de «{nome[:60]}» pendente ou ambígua no vocabulário — confirmar"
    # A forma jurídica no fim esconde a sigla que vem antes dela:
    # «Imprensa Nacional - Casa da Moeda, SA - INCM, SA» tem a sigla INCM.
    sem_forma = RE_FORMA_NO_FIM.sub("", nome)
    for texto in dict.fromkeys((nome, sem_forma)):
        for regex in (RE_PARENTESES, RE_FIM_APOS_TRACO, RE_INICIO_ANTES_TRACO, RE_ENTRE_TRACOS):
            for m in regex.finditer(texto):
                if _e_sigla(m.group(1)):
                    literal = _limpar_sigla(m.group(1))
                    if literal.casefold() in getattr(tabela, "siglas_recusadas", set()):
                        return literal, f"sigla literal {literal} pendente ou ambígua no vocabulário — confirmar"
                    return literal, None
    if getattr(tabela, "permitir_rotulos", False):
        return _camel(nome), informacao(
            f"rótulo documental derivado de «{nome}»; não é uma sigla oficial confirmada")
    return _camel(nome), f"sigla derivada de «{nome[:60]}» — confirmar"


def e_sindical(nome: str) -> bool:
    """Designações sindicais expressas; uma federação patronal não é sindicato."""
    nome = sem_acentos(nome).lower()
    return "sindic" in nome or any(designacao in nome for designacao in (
        "federacao dos engenheiros", "federacao nacional da educacao",
        "federacao nacional dos professores"))


def _partes_do_titulo(titulo: str) -> list[str]:
    """'Contrato coletivo entre a X e o Y' → ['X', 'Y'] (para as retificações)."""
    texto = re.sub(r"\s+", " ", titulo or "")
    texto = re.split(r"\s[-–—]\s(?:Retifica|Altera|Aviso|Texto consolidado)", texto,
                     maxsplit=1, flags=re.IGNORECASE)[0]
    m = RE_PARTES_TITULO.search(texto)
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
    nomes = list(dict.fromkeys(n.strip() for n in re.split(r"[;\n]", entrada.get("outorgantes") or "") if n.strip()))
    if not nomes:
        nomes = _partes_do_titulo(entrada.get("titulo", ""))
        if nomes:
            avisos.append(informacao("outorgantes lidos dos dois lados explícitos do título"))
    if not nomes:
        return [], [], avisos + ["sem outorgantes no índice nem no título"]
    patronais = [n for n in nomes if not e_sindical(n)]
    sindicais = [n for n in nomes if e_sindical(n)]
    if patronais and sindicais:
        escolhidos = [patronais[0], sindicais[0]][:maximo]
    else:
        escolhidos = nomes[:maximo]
        lado = "patronal" if patronais else "sindical"
        avisos.append(informacao(
            f"só há partes do lado {lado} — o nome usa as {len(escolhidos)} "
            "primeira(s) pela ordem do índice"
        ))
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


def carregar_siglas(caminho: Path) -> dict[str, str]:
    """Tabela de siglas → {nome normalizado: sigla}.

    Aceita `nome;sigla` sem cabeçalho (o siglas.csv da equipa) ou um CSV com
    cabeçalho, com as colunas encontradas pelo nome (o
    `vocabularios/siglas_organizacoes.csv`). Separador `;`, UTF-8 com ou sem BOM.
    """
    tabela = TabelaSiglas()
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
    i_estado = cabecalho.index("estado") if tem_cabecalho and "estado" in cabecalho else None
    claims = {}
    i_origem = (
        cabecalho.index(COLUNA_ORIGEM) if tem_cabecalho and COLUNA_ORIGEM in cabecalho else None
    )
    i_responsavel = cabecalho.index("responsavel") if tem_cabecalho and "responsavel" in cabecalho else None
    tabela.permitir_rotulos = i_origem is not None
    automaticas = {}
    recusados = set()
    for linha in linhas:
        if max(i_nome, i_sigla) >= len(linha):
            continue
        nome = chave_entidade(linha[i_nome])
        valor = normalizar_sigla(linha[i_sigla])
        origem = linha[i_origem].strip().lower().split("+")[0] if i_origem is not None and i_origem < len(linha) else ""
        automatica = i_responsavel is None or i_responsavel >= len(linha) or not linha[i_responsavel].strip()
        estado = linha[i_estado].strip().lower() if i_estado is not None and i_estado < len(linha) else ""
        # As propostas geradas pelo programa não são recusas humanas. Podem
        # servir como rótulos legíveis, sem as promover a siglas oficiais.
        if origem in {"indice", "lista_equipa", "recurso"} and automatica and estado != "confirmada":
            automaticas[nome] = _camel(linha[i_nome])
            continue
        # Uma sigla literal pertence à denominação completa, mesmo que outra
        # entidade use a mesma sigla. O IDDocumento distingue os ficheiros.
        if (origem in {"indice_literal", "registo", "derivada", "correspondencia_exata", "nome_completo_exato"}
                and estado in {"documentada", "ambigua"} and valor and automatica):
            claims.setdefault(nome, set()).add(valor)
            continue
        if i_estado is not None and (i_estado >= len(linha) or linha[i_estado].strip().lower() not in {"confirmada", "documentada"}):
            tabela.nomes_pendentes.add(nome)
            recusados.add(nome)
            if valor:
                tabela.siglas_pendentes.add(valor.casefold())
                if not origem or not automatica:
                    tabela.siglas_recusadas.add(valor.casefold())
            continue
        if nome and valor:
            claims.setdefault(nome, set()).add(valor)
    for nome, valores in claims.items():
        if len(valores) != 1:
            tabela.nomes_pendentes.add(nome)
            tabela.siglas_pendentes.update(valor.casefold() for valor in valores)
        elif nome not in tabela.nomes_pendentes:
            tabela[nome] = next(iter(valores))
    for nome, valor in automaticas.items():
        if nome not in claims and nome not in recusados:
            tabela.nomes_pendentes.discard(nome)
            tabela.rotulos[nome] = valor
    return tabela


def tabela_de_siglas(caminhos=(), *, equipa: Path = SIGLAS_EQUIPA, dgert: bool = True):
    """O siglas.csv da equipa primeiro (ganha), depois os indicados e o da DGERT."""
    ordem = [Path(equipa)] if Path(equipa).is_file() else []
    ordem += [Path(c) for c in caminhos]
    packaged = SIGLAS_CONSOLIDADAS if SIGLAS_CONSOLIDADAS.is_file() else SIGLAS_DGERT
    if dgert and packaged.is_file():
        ordem.append(packaged)
    tabela = TabelaSiglas()
    for caminho in ordem:
        carregada = carregar_siglas(caminho)
        tabela.nomes_pendentes.update(nome for nome in carregada.nomes_pendentes if nome not in tabela)
        tabela.siglas_pendentes.update(carregada.siglas_pendentes)
        tabela.siglas_recusadas.update(carregada.siglas_recusadas)
        tabela.permitir_rotulos |= carregada.permitir_rotulos
        tabela.rotulos.update({nome: valor for nome, valor in carregada.rotulos.items()
                              if nome not in tabela.nomes_pendentes and nome not in tabela})
        for nome, valor in carregada.items():
            if nome not in tabela.nomes_pendentes:
                tabela.setdefault(nome, valor)
    return tabela


def siglas_derivadas(entrada: dict, tabela: dict[str, str] | None = None, *, scheme="adr0022"):
    """(outorgante, sigla sugerida) das siglas do nome que foram adivinhadas."""
    escolhidos, _nomes, _avisos = _outorgantes_escolhidos(entrada)
    if scheme == "v4":
        escolhidos = list(dict.fromkeys(n.strip() for n in re.split(r"[;\n]", entrada.get("outorgantes") or "") if n.strip()))[:3]
    derivadas = []
    for nome in escolhidos:
        valor, aviso = sigla(nome, tabela)
        if aviso and valor and avisos_bloqueantes([aviso]):
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
    for fonte in (entrada.get("portaria_dr"), entrada.get("em_vigor"), entrada.get("titulo")):
        texto = str(fonte or "").strip()
        if not texto:
            continue
        m = RE_PORTARIA.search(texto if "ortaria" in texto else f"Portaria n.º {texto}")
        if not m:
            continue
        if re.match(r"\s*/", texto[m.end():]):
            raise NomeRNCInvalido("Referência de portaria com segmento adicional; confirme a representação completa.")
        numero, ano_dr = int(m.group("num")), int(m.group("ano"))
        # A portaria sai no DR antes de ser publicitada no BTE.
        if numero == 0 or (ano_bte and ano_dr > ano_bte):
            return None
        return numero, (m.group("suf") or "").upper(), ano_dr
    return None


def serie_portaria(entrada):
    for fonte in (entrada.get("portaria_dr"), entrada.get("em_vigor"), entrada.get("titulo")):
        match = RE_PORTARIA.search(str(fonte or ""))
        if match:
            return match.group("serie") or ""
    return ""


def ambito_documento(entrada, vocabulario=None):
    """O regime explícito do documento prevalece sobre a forma do empregador."""
    if entrada.get("ambito_documental"):
        return entrada["ambito_documental"], "metadados:" + entrada["regra_tipologia"], None
    titulo = sem_acentos(entrada.get("titulo", "")).lower()
    if re.search(r"acordo coletivo de [ec]mpregador publico", titulo):
        return "APU", "titulo_acep", None
    patronais = separar_outorgantes(entrada.get("outorgantes", ""), entrada.get("titulo", ""))[0]
    return mod_ambito.classificar_com_ine(patronais[0] if patronais else "",
                                        entrada.get("tipo", ""), vocabulario)


def _codigos(valor) -> list[str]:
    """`"27251; 26760"` → `["27251", "26760"]`, pela ordem, sem repetidos."""
    partes = [p for p in re.split(r"[;,\s]+", str(valor or "").strip()) if p]
    if any(not re.fullmatch(r"\d+", p) for p in partes):
        raise NomeRNCInvalido("Código IRCT inválido; confirme o índice.")
    return list(dict.fromkeys(partes))


def _familia(entrada: dict) -> str:
    return entrada.get("familia") or familia(entrada.get("tipo", "")) or "por_classificar"


def cod_irct_base(entrada: dict) -> str | None:
    """O código IRCT do nome: o próprio numa convenção, o da convenção de base
    nas outras famílias (resolvido por `resolver_convencoes_base`)."""
    campo = "cod_irct" if _familia(entrada) == "convencao" else "cod_irct_base"
    codigos = _codigos(entrada.get(campo))
    if codigos and any(int(codigo) == 0 for codigo in codigos):
        raise NomeRNCInvalido("Código IRCT inválido; não use zero como identidade.")
    if _familia(entrada) == "convencao" and len(codigos) > 1:
        raise NomeRNCInvalido("Múltiplos códigos IRCT na convenção; confirme a identidade documental.")
    return codigos[0] if codigos else None


def resolver_convencoes_base(entradas, regras=None) -> None:
    """Liga cada documento que não é convenção ao código da convenção de base.

    Usa o código associado no índice e cruza-o com referências por tipo e ID
    quando disponíveis. Códigos contraditórios ficam pendentes. Retificações
    herdam os outorgantes da publicação concreta referida, com proveniência.
    """
    entradas = list(entradas)
    tipologias.enriquecer(entradas, regras)
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
            try:
                cods = _codigos(alvos[0].get("cod_irct")) if len(alvos) == 1 else []
            except NomeRNCInvalido:
                cods = []
            if len(cods) == 1 and int(cods[0]) > 0:
                codigos.append(cods[0])
            else:
                por_resolver.append(ref.strip())
        codigos = list(dict.fromkeys(codigos))
        # CodigoGEPDGERT é a identidade da convenção associada no índice,
        # também nas PE/AA/acórdãos. Não exigir que uma base de outro ano
        # esteja repetida no ficheiro anual para conservar esse dado explícito.
        try:
            diretos = _codigos(e.get("cod_irct"))
        except NomeRNCInvalido as error:
            e["relacao_conflito"] = str(error)
            continue
        if diretos and codigos and set(diretos) != set(codigos):
            e["relacao_conflito"] = "Código IRCT do índice difere do código da convenção referida."
            continue
        if diretos:
            codigos = diretos
            por_resolver = []
        e["cod_irct_base"] = "; ".join(codigos)
        e["cod_irct_base_origem"] = "CodigoGEPDGERT" if diretos else "cadeia_do_indice" if codigos else ""
        e["cod_irct_base_por_resolver"] = "; ".join(por_resolver)

    # As retificações referem a publicação concreta. Herdar desse documento,
    # nunca de outra convenção escolhida apenas pela semelhança do título.
    for _ in range(len(entradas)):
        mudou = False
        for e in entradas:
            if "RECT" not in tipo_normalizado(e.get("tipo")) or e.get("outorgantes"):
                continue
            refs = [RE_ALTERA.fullmatch(ref.strip()) for ref in (e.get("altera") or "").split(";") if ref.strip()]
            alvos = []
            for ref in refs:
                if ref:
                    alvos.extend(c for c in convencoes.get((str(int(ref["seq"])), ref["ano"]), [])
                                 if tipo_normalizado(c.get("tipo")) == ref["tipo"])
            if len(alvos) > 1:
                e["relacao_conflito"] = "Retificação com mais de uma convenção retificada candidata."
                continue
            if len(alvos) != 1 or alvos[0] is e or not alvos[0].get("outorgantes"):
                continue
            base = alvos[0]
            if e.get("cod_irct") and base.get("cod_irct") and e["cod_irct"] != base["cod_irct"]:
                e["relacao_conflito"] = "Retificação e convenção retificada têm códigos IRCT diferentes."
                continue
            e["outorgantes"] = base["outorgantes"]
            e["outorgantes_origem"] = "convencao_retificada:" + base["chave"]
            mudou = True
        if not mudou:
            break
    for e in entradas:
        if (e["familia"] == "cessacao" or e["regra_tipologia"].startswith("aviso_")) and not e.get("outorgantes"):
            nomes = _partes_do_titulo(e.get("titulo", ""))
            if nomes:
                e["outorgantes"] = "; ".join(nomes)
                e["outorgantes_origem"] = "titulo_partes_explicitas"
        if _familia(e) == "acordao" and not e.get("outorgantes"):
            # Papéis processuais expressos no título, sem inferir outorgantes
            # pela mera presença de uma sigla no texto do acórdão.
            match = re.search(r"\bAutor\s+(.+?)\s+e\s+a\s+R[ée]\s+(.+?),\s+no\s+dia\b",
                              e.get("titulo", ""), re.IGNORECASE)
            if match:
                e["outorgantes"] = match[2] + "; " + match[1]
                e["outorgantes_origem"] = "titulo_papeis_processuais"
        reference = referencia_portaria(e) if _familia(e) == "extensao" else None
        if reference:
            match = RE_PORTARIA.search(str(e.get("em_vigor") or ""))
            if match:
                e["portaria_dr"] = match[0]
                e["portaria_dr_origem"] = "DocumentosEmVigor"
                date = re.search(r"Diario da Republica.+?\bde\s+(\d{4}-\d{2}-\d{2})",
                                 sem_acentos(e.get("em_vigor", "")), re.IGNORECASE)
                if date:
                    e["data_publicacao_dr"] = date[1]


# --------------------------------------------------------------------- nome


def nome_documento(
    entrada: dict, ordinal: int = 0, tabela: dict[str, str] | None = None, *, vocabulario_ambito=None, scheme="adr0022"
) -> tuple[str, list[str]]:
    """Nome (sem extensão) no esquema do ADR-0022 e os avisos a confirmar.

        convenção   {ANO}_BTE_{NN}_{AMBITO}_{SEQ}_{TIPO}_{CODIRCT}_{SIGLAS}
        portaria    {ANO}_BTE_{NN}_{TIPO}_{SEQ}_{NNNN}-{AAAA}_{CODIRCT}_{SIGLAS}
        adesão      {ANO}_BTE_{NN}_AA_{SEQ}_{CODIRCT}_{SIGLAS}
        acórdão     {ANO}_BTE_{NN}_JUR_{SEQ}_{CODIRCT}_{SIGLAS}

    `ordinal` é conservado apenas na assinatura de compatibilidade; nunca substitui IDDocumento.
    `scheme="v4"` conserva a disposição anterior e até três siglas, para compatibilidade.
    `NomeRNCInvalido` diz que falta um campo estrutural e que o ficheiro não
    pode ser escrito de todo. Sem `vocabulario_ambito`, usa o do pacote.
    """
    if scheme not in ESQUEMAS:
        raise NomeRNCInvalido("Esquema desconhecido; use v4 ou adr0022.")
    if vocabulario_ambito is None:
        vocabulario_ambito = mod_ambito.vocabulario_por_omissao()
    avisos: list[str] = []
    if "tipo_documental" not in entrada:
        entrada = {**entrada, **tipologias.classificar(entrada)}
    if entrada.get("relacao_conflito"):
        raise NomeRNCInvalido(entrada["relacao_conflito"])
    ano = int(entrada.get("ano") or 0)
    num_bte = int(entrada.get("num_bte") or 0)
    tipo_bruto = sem_acentos(str(entrada.get("tipo_documental") or entrada.get("tipo") or "")).strip().upper()
    if not re.fullmatch(r"[A-Z]+(?:-[A-Z]+)*", tipo_bruto):
        raise NomeRNCInvalido("Tipo de documento inválido; confirme o índice.")
    tipo = tipo_normalizado(tipo_bruto)
    fam = _familia(entrada)

    identificador = re.fullmatch(r"(\d+)/(\d{4})", str(entrada.get("id_dgert") or "").strip())
    if not identificador or int(identificador[2]) != ano or int(identificador[1]) < 1:
        raise NomeRNCInvalido("IDDocumento ausente ou diferente do ano; confirme o índice.")
    if not 1 <= num_bte <= 99 or not 1900 <= ano <= 2200:
        raise NomeRNCInvalido("Ano ou número do BTE inválido; confirme o índice.")
    seq = int(identificador[1])
    if fam not in {*PASTA_FAMILIA, "aviso"}:
        raise NomeRNCInvalido("Família documental desconhecida; confirme o índice.")
    if fam == "convencao" and not re.fullmatch(r"(?:CCT|ACT|ACTV|AE|ACEP|ACCE|DA)(?:-[A-Z]+)*", tipo):
        raise NomeRNCInvalido("Tipo de convenção inválido; confirme o índice.")

    amb, origem, aviso_amb = ambito_documento(entrada, vocabulario_ambito)
    if amb not in mod_ambito.VALORES:
        raise NomeRNCInvalido("Âmbito inválido no vocabulário; use PRI, SPE ou APU.")

    if fam in QUARTO_CAMPO_TIPO:
        # O âmbito não entra no nome destas famílias; fica no catálogo.
        quarto = TIPO_POR_EXTENSO.get(tipo.split("-")[0], tipo)
        if fam == "extensao" and tipo.split("-")[0] in QUARTO_CAMPO_TIPO[fam]:
            quarto = tipo.split("-")[0]
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
            serie = serie_portaria(entrada)
            if serie:
                miolo += "-" + serie

        cod = cod_irct_base(entrada)
        if cod is None:
            if fam in {"aviso", "cessacao"}:
                cod = (_codigos(entrada.get("cod_irct")) or [f"DOC{seq}-{ano}"])[0]
                avisos.append(informacao("publicação autónoma; a ausência de uma base no lote não elimina o PDF"))
            else:
                raise NomeRNCInvalido(
                    "sem código IRCT da convenção de base confirmado (SPEC-0004, passo 0)"
                )
        elif fam != "aviso":
            if entrada.get("cod_irct_base_origem") == "cadeia_do_indice":
                avisos.append(informacao("convenção de base identificada pela referência exata do índice"))
            todos = _codigos(entrada.get("cod_irct_base"))
            if len(todos) > 1:
                avisos.append(informacao(
                    f"refere {len(todos)} convenções ({', '.join(todos)}) — o nome "
                    "leva a primeira; as restantes estão no catálogo"
                ))
    else:
        if aviso_amb:
            avisos.append(aviso_amb)
        if tipo == "SEMTIPO":
            avisos.append("tipo de documento vazio no índice — confirmar")
        quarto, miolo = amb, f"_{tipo}"
        cod = cod_irct_base(entrada)
        if cod is None and entrada.get("referencia_acordo_base"):
            numero, ano_base = entrada["referencia_acordo_base"].split("/")
            cod = f"{entrada['tipo_acordo_base']}{numero}-{ano_base}"
        if cod is None and origem == "titulo_acep":
            ref_apu = re.search(r"acordo coletivo de trabalho n\.?\s*[º°o]?\s*(\d+)/(\d{4})",
                                sem_acentos(entrada.get("titulo", "")), re.IGNORECASE)
            if ref_apu:
                cod = f"ACEP{int(ref_apu[1])}-{ref_apu[2]}"
        if cod is None:
            raise NomeRNCInvalido("Código IRCT ausente; confirme o índice.")

    if scheme == "v4":
        nomes = list(dict.fromkeys(n.strip() for n in re.split(r"[;\n]", entrada.get("outorgantes") or "") if n.strip()))
        if not nomes:
            raise NomeRNCInvalido("Outorgantes ausentes; confirme o índice.")
        siglas, avisos_siglas = [], []
        for entidade in nomes[:3]:
            valor, aviso = sigla(entidade, tabela)
            siglas.append(valor)
            if aviso:
                avisos_siglas.append(aviso)
        restantes = max(0, len(nomes) - 3)
        token_tipo = tipo if fam == "convencao" else quarto
        prefixo = f"{ano:04d}_{amb}_{seq:03d}_{token_tipo}_{cod}_BTE_{num_bte:02d}_"
    else:
        siglas, restantes, avisos_siglas = siglas_outorgantes(entrada, tabela)
        if not siglas and (fam in {"aviso", "cessacao"} or fam == "extensao" and quarto in {"PCT", "PRT"}):
            siglas, restantes = [quarto], 0
            avisos_siglas = [informacao("instrumento governamental sem outorgantes convencionais; "
                                        f"marcador de tipo {quarto} na cauda do nome")]
        if not siglas:
            raise NomeRNCInvalido("Outorgantes ausentes; confirme o índice.")
        prefixo = f"{ano:04d}_BTE_{num_bte:02d}_{quarto}_{seq:03d}{miolo}_{cod}_"
    avisos.extend(avisos_siglas)
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
        avisos.append(informacao(f"rótulos encurtados para caber em {MAX_NOME} caracteres"))
    return nome, avisos


# ------------------------------------------------------------------ nomear


def nomear(
    registo: Registo, destino: Path, *, aplicar=False, tabela=None,
    familias=("convencao", "extensao", "adesao", "acordao", "cessacao", "aviso"),
    aceitar_heuristicas=False, vocabulario_ambito=None, scheme="adr0022", workspace=False,
) -> dict:
    """Adaptador de compatibilidade; execução e verificações partilhadas com naming."""
    from .naming import execute_records

    if tabela is None:
        tabela = tabela_de_siglas()
    results = execute_records(registo, destino, tabela,
                              vocabulario_ambito, apply=aplicar, scheme=scheme,
                              families=familias, workspace=workspace,
                              accept_warnings=aceitar_heuristicas)
    resumo = {"ordinais_novos": 0, "por_estado": {}, "avisos": [], "informacoes": [], "problemas": [],
              "nomes": [], "siglas_pendentes": {}}
    for result in results:
        state = result["estado"]
        if state == "proposto":
            state = "por_nomear"
        resumo["por_estado"][state] = resumo["por_estado"].get(state, 0) + 1
        if result["nome"]:
            resumo["nomes"].append((result["chave"], result["nome"]))
        if result["motivo"] and result["motivo"] != "; ".join(result.get("avisos", [])):
            resumo["problemas"].append(f"{result['chave']}: {result['motivo']}")
        blocking = avisos_bloqueantes(result.get("avisos", []))
        resumo["avisos"].extend(blocking)
        resumo["informacoes"].extend(a for a in result.get("avisos", []) if a not in blocking)
        e = registo.entradas[result["chave"]]
        if state == "por_confirmar":
            for entidade, valor in siglas_derivadas(e, tabela, scheme=scheme):
                resumo["siglas_pendentes"].setdefault(entidade, {"sigla": valor, "documentos": []})["documentos"].append(result["nome"])
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
    if resumo.get("informacoes"):
        linhas.append(f"  observações automáticas: {len(resumo['informacoes'])} (proveniência conservada no catálogo)")
    if resumo["avisos"]:
        linhas.append(f"  a confirmar ({len(resumo['avisos'])}):")
        linhas.extend(f"    {a}" for a in resumo["avisos"])
    if resumo["problemas"]:
        linhas.append("  PROBLEMAS:")
        linhas.extend(f"    {p}" for p in resumo["problemas"])
    return "\n".join(linhas)
