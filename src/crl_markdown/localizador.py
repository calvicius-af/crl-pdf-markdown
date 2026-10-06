# Adaptado de crl-app-cct, commit 5fd8ae848d44274306e1414621ddeabc620ca4c6.
"""Localiza convenções individuais dentro de um número do BTE.

A amostra de referência identifica documentos como "25_PR_016_BTE_04_EMARP_SINTAP":
o número do BTE (04) dá o ficheiro (bte4_2025.pdf) e os tokens das partes
(EMARP, SINTAP) permitem encontrar a convenção certa dentro do número.

O token depois do ano (aqui "PR") identifica a família documental — "PR" para
convenções, mas cct.nomeacao usa também "PE"/"AV"/"AA" para portarias de
extensão, avisos e acordos de adesão (ver TOKEN_FAMILIA em cct/nomeacao.py).
RE_DOC_ID aceita qualquer sigla de duas letras maiúsculas nessa posição — não
lista as famílias uma a uma, para não ter de ser revisto sempre que
cct.nomeacao ganhar uma família nova.

Desde a adoção da convenção de nomes do RNC há mais dois esquemas. O do
ADR-0016, com o ano por extenso, o âmbito, o número sequencial do BTE, o tipo
tal como vem do índice e o código IRCT:

    2026_PRI_377_CCT_27251_BTE_31_ACRAL-CESP-STRUP+2

e o do ADR-0022, que o substitui a partir do corpus de 2026. Começa sempre por
ano e boletim, e o quarto campo diz o que o ficheiro é: âmbito (PRI, SPE, APU)
numa convenção, tipo (PE, PCT, PRT, AA) numa portaria ou adesão. Termina sempre
no código IRCT da convenção de base e nas duas siglas principais:

    2026_BTE_31_PRI_377_CCT-ALT_27251_ACRAL-CESP+3       convenção
    2026_BTE_01_PE_012_0452-2025_27251_ACRAL-CESP        portaria de extensão
    2026_BTE_12_AA_412_27251_ABC-CESP                    acordo de adesão

`interpretar_doc_id` lê os quatro e devolve sempre a mesma coisa — (ano de dois
dígitos, número do BTE, tokens das partes) — para que nada a jusante tenha de
saber em que esquema o corpus foi nomeado. Um corpus pode ter vários à mistura:
os nomes até 2025 não se alteram (ver docs/adr/0021 e 0022).
"""
import re
import unicodedata

RE_INICIO_CONVENCAO = re.compile(
    r"^(Contrato coletivo|Acordo coletivo|Acordo de empresa|Acordo de adesão)"
    r"\s+(entre|celebrado)", re.MULTILINE)

RE_DOC_ID = re.compile(r"^(\d{2})_[A-Z]{2}_\d+_BTE_(\d+)_(.+?)(?:_TXT)?$")

# Esquema do ADR-0016: {ANO}_{AMBITO}_{SEQ}_{TIPO}_{CODIRCT}_BTE_{NN}_{SIGLAS}
# O tipo vem do índice do BTE e pode ter variantes com hífen (CCT-ALT,
# AE-ALT-RECT); o código IRCT são dígitos; as siglas vêm separadas por hífen e
# podem terminar em "+N" quando há mais outorgantes do que os que cabem no nome.
# Já não é escrito (ADR-0022), mas continua a ser lido. O âmbito é um
# vocabulário fechado: sem isso, `2026_BTE_31_…` do esquema novo encaixava aqui
# com «BTE» no lugar do âmbito.
RE_DOC_ID_RNC = re.compile(
    r"^(\d{4})_(?P<ambito>PRI|SPE|APU)_(?P<seq>\d+)_(?P<tipo>[A-Z][A-Z-]*)"
    r"_(?P<cod>\d+)_BTE_(\d+)_(.+?)(?:_TXT)?$")

# Esquema do ADR-0022: cabeça `{ANO}_BTE_{NN}_{X}_{SEQ}`, miolo próprio de cada
# família, cauda `{CODIRCT}_{SIGLAS}`. O quarto campo é um vocabulário fechado
# em cada padrão, para que um âmbito nunca seja lido como tipo nem o contrário.
_CABECA = r"^(?P<ano>\d{4})_BTE_(?P<num_bte>\d{2,})_"
_CAUDA = r"_(?P<cod>\d+)_(?P<siglas>[^_]+?)(?:_TXT)?$"
RE_DOC_ID_CONVENCAO = re.compile(
    _CABECA + r"(?P<ambito>PRI|SPE|APU)_(?P<seq>\d+)_(?P<tipo>[A-Z][A-Z-]*)" + _CAUDA)
RE_DOC_ID_EXTENSAO = re.compile(
    _CABECA + r"(?P<tipo>PE|PCT|PRT)_(?P<seq>\d+)"
    r"_(?P<portaria>\d{4}[A-Z]?)-(?P<ano_dr>\d{4})" + _CAUDA)
RE_DOC_ID_ADESAO = re.compile(_CABECA + r"(?P<tipo>AA)_(?P<seq>\d+)" + _CAUDA)
# Um aviso não tem ficheiro (ADR-0018): o nome só serve de chave no catálogo,
# com a forma de uma adesão e o tipo no quarto campo.
RE_DOC_ID_AVISO = re.compile(_CABECA + r"(?P<tipo>AVISO|AV)_(?P<seq>\d+)" + _CAUDA)

# Família que cada padrão do ADR-0022 declara pelo quarto campo.
PADROES_ADR0022 = ((RE_DOC_ID_CONVENCAO, "convencao"),
                   (RE_DOC_ID_EXTENSAO, "extensao"),
                   (RE_DOC_ID_ADESAO, "adesao"),
                   (RE_DOC_ID_AVISO, "aviso"))


def _ler_adr0022(doc_id: str) -> tuple[re.Match, str] | tuple[None, None]:
    for regex, fam in PADROES_ADR0022:
        m = regex.match(doc_id)
        if m:
            return m, fam
    return None, None


def _siglas_e_restantes(cauda: str) -> tuple[list[str], int]:
    m = re.search(r"\+(\d+)$", cauda)
    siglas = [s for s in re.sub(r"\+\d+$", "", cauda).split("-") if s]
    return siglas, int(m.group(1)) if m else 0


def _sem_acentos(s) -> str:
    """Remove marcas de acentuação (NFD → descarta categoria 'Mn').

    Implementação partilhada — cct/nomeacao.py e cct/recolha.py importam
    daqui em vez de reimplementar, para não terem três versões da mesma
    normalização a poderem divergir silenciosamente (ver PR #35, achado nº9).
    """
    return "".join(c for c in unicodedata.normalize("NFD", str(s or ""))
                   if unicodedata.category(c) != "Mn")


def _colapsar(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _sem_acentos(s).lower())


def _subtokens(token: str) -> list[str]:
    """Divide tokens camel-case da referência: 'AguasRibatejo' → [aguas, ribatejo]."""
    partes = re.findall(r"[A-ZÀ-Ý]+(?![a-z])|[A-ZÀ-Ý][a-zà-ÿ]+|[a-zà-ÿ]+|\d+", token)
    return [_colapsar(p) for p in partes if len(p) > 1]


def interpretar_doc_id(doc_id: str) -> tuple[int, int, list[str]]:
    """Devolve (ano_2dig, nº BTE, subtokens das partes).

    Aceita os quatro esquemas de nome (2025, ADR-0016 e os três padrões do
    ADR-0022). O ano vem sempre com dois dígitos, mesmo quando o nome o traz por
    extenso, porque é assim que o resto do pipeline o compara — mudar isso
    obrigaria a rever o cruzamento com as variáveis do MaxQDA, que é o que esta
    função existe para não partir.
    """
    doc_id = doc_id.strip()
    m = RE_DOC_ID.match(doc_id)
    if m:
        ano, bte, partes = int(m.group(1)), int(m.group(2)), m.group(3)
    elif (m := RE_DOC_ID_RNC.match(doc_id)):
        ano, bte, partes = int(m.group(1)) % 100, int(m.group(6)), m.group(7)
    else:
        m, _fam = _ler_adr0022(doc_id)
        if not m:
            raise ValueError(f"doc_id não reconhecido: {doc_id}")
        ano, bte, partes = (int(m.group("ano")) % 100, int(m.group("num_bte")),
                            m.group("siglas"))
    tokens = []
    for t in re.split(r"[_-]", partes):
        tokens.extend(_subtokens(re.sub(r"\+\d+$", "", t)))
    return ano, bte, tokens


def interpretar_nome_rnc(doc_id: str) -> dict | None:
    """Metadados que um nome RNC leva, ou None se for do esquema de 2025.

    Lê o esquema do ADR-0016 e o do ADR-0022. Serve para não ter de abrir o
    catálogo quando só se quer saber o âmbito, a família ou o código IRCT de um
    ficheiro que se tem à frente. O catálogo continua a ser a fonte de verdade —
    isto é uma conveniência, não uma segunda fonte.

    `familia` só vem preenchida no esquema do ADR-0022, onde o quarto campo a
    declara; no do ADR-0016 lê-se do `tipo` (ver `cct.recolha.familia`).
    """
    doc_id = doc_id.strip()
    m = RE_DOC_ID_RNC.match(doc_id)
    if m:
        siglas, restantes = _siglas_e_restantes(m.group(7))
        return {"esquema": "adr0016", "ano": int(m.group(1)),
                "ambito": m.group("ambito"), "seq": int(m.group("seq")),
                "tipo": m.group("tipo"), "cod_irct": m.group("cod"),
                "num_bte": int(m.group(6)), "siglas": siglas,
                "outros_outorgantes": restantes, "familia": None,
                "portaria": None, "ano_dr": None}
    m, fam = _ler_adr0022(doc_id)
    if not m:
        return None
    grupos = m.groupdict()
    siglas, restantes = _siglas_e_restantes(grupos["siglas"])
    return {"esquema": "adr0022", "ano": int(grupos["ano"]),
            "ambito": grupos.get("ambito"), "seq": int(grupos["seq"]),
            "tipo": grupos["tipo"], "cod_irct": grupos["cod"],
            "num_bte": int(grupos["num_bte"]), "siglas": siglas,
            "outros_outorgantes": restantes, "familia": fam,
            "portaria": grupos.get("portaria"),
            "ano_dr": int(grupos["ano_dr"]) if grupos.get("ano_dr") else None}

