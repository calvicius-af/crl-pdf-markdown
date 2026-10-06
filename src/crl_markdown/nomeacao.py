# Adaptado de crl-app-cct, commit 5fd8ae848d44274306e1414621ddeabc620ca4c6.
"""Nomeação dos documentos recolhidos, no esquema que o pipeline sabe ler.

Segunda fase da aquisição (a primeira é `cct/recolha.py`). Corre inteiramente
offline e pode repetir-se à vontade: lê o registo, atribui a cada documento um
ordinal estável, deriva as siglas dos outorgantes e copia o PDF para

    data/raw/bte/bte_2026/convencoes/PRI/2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+3.pdf
    data/raw/bte/bte_2026/portarias_extensao/2026_BTE_01_PE_012_0452-2025_27251_ACRAL-CESP.pdf
    data/raw/bte/bte_2025/extensoes/25_PE_001_BTE_31_….pdf         esquema de 2025

Esquema RNC por omissão, obrigatório a partir do corpus de 2026 (ADR-0021), na
forma do ADR-0022; o esquema de 2025 (`26_PR_003_BTE_31_ACRAL_CESP.pdf`) só se
pede com `--esquema pipeline`, para reprocessar um corpo anterior a 2026.

O nome não é decorativo: o `cct/localizador.py` lê dele o ano, o número do BTE e
os tokens das partes; o `cct/comparar.py` deduz o ano; e o cruzamento com as
variáveis do MaxQDA é feito pelos primeiros caracteres. Ver docs/rnc/README.md.

Uso:
  python -m crl_markdown.nomeacao --destino data/raw/bte             # simulação
  python -m crl_markdown.nomeacao --destino data/raw/bte --aplicar
"""
import argparse
import re
import shutil
import time
from pathlib import Path
from typing import Any

from . import ambito as mod_ambito
from .localizador import _sem_acentos
from .recolha import INTERVALO_PERSISTENCIA, REGISTO_OMISSAO, Registo, familia, sha256_ficheiro

RAIZ = Path.cwd()

DESTINO_OMISSAO = RAIZ / "data" / "raw" / "bte"
# O siglas.csv da equipa, na raiz do projeto (não vem no repositório). É onde a
# app grava as siglas confirmadas, e carrega-se sempre que existe: uma sigla
# confirmada uma vez não volta a ser perguntada (#38).
SIGLAS_EQUIPA = RAIZ / "siglas.csv"

# Os esquemas de nome que a aplicação escreve. Ver ADR-0021 e ADR-0022.
#
#   pipeline  26_PR_003_BTE_31_ACRAL_CESP                 o de 2025, até ao corpus de 2025
#   rnc       2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+3  obrigatório a partir de 2026
#
# O `rnc` tem cabeça comum às três famílias (`{ANO}_BTE_{NN}_{X}_{SEQ}`), um
# miolo próprio de cada família e cauda comum (`{CODIRCT}_{SIGLAS}`). O quarto
# campo diz o que o ficheiro é: âmbito numa convenção, tipo numa portaria ou
# adesão. O esquema RNC anterior (ADR-0016, `2026_PRI_377_CCT_27251_BTE_31_…`)
# já não é escrito, mas `cct/localizador.py` continua a lê-lo.
ESQUEMAS = ("pipeline", "rnc")
ESQUEMA_2025 = "pipeline"
ESQUEMA_OMISSAO = "rnc"          # o mesmo das linhas de comando (ADR-0021)

MAX_SIGLAS_RNC = 2     # a primeira patronal e a primeira sindical; o resto em "+N"

# Quarto campo do nome nas famílias que não são convenção: o tipo, num
# vocabulário fechado. Um tipo fora dele não é forçado num nome — fica por
# confirmar, para decisão registada (ADR-0022, «Revisitar quando»).
QUARTO_CAMPO_TIPO = {"extensao": ("PE", "PCT", "PRT"), "adesao": ("AA",),
                     "aviso": ("AVISO", "AV")}

# Enquanto o passo 0 da SPEC-0004 não confirmar, com um índice real, que a
# cadeia de alterações de uma PE ou de um AA aponta para a convenção de base, um
# código obtido por essa via entra no nome mas fica por confirmar. Retirar este
# aviso é a decisão que fecha o passo 0.
AVISO_BASE_PELA_CADEIA = ("código da convenção de base lido da cadeia de "
                          "alterações do índice — confirmar (SPEC-0004, passo 0)")

TOKEN_FAMILIA = {"convencao": "PR", "extensao": "PE",
                 "aviso": "AV", "adesao": "AA"}

# Esquema de 2025: tudo o que não é convenção ia para uma só pasta `extensoes/`,
# cujo único objetivo era ficar fora do `glob("*.pdf")` do pipeline.
SUBPASTA_FAMILIA = {"convencao": "", "extensao": "extensoes",
                    "aviso": "extensoes", "adesao": "extensoes"}

# Esquema RNC: cada família tem a sua pasta. Uma portaria de extensão e um
# acordo de adesão referem-se a uma convenção concreta, mas são actos de
# natureza diferente — a portaria é do Governo, a adesão é de uma parte — e
# nenhum dos dois tem o articulado que a codificação temática pressupõe.
# Juntá-los às convenções faria com que fossem codificados como se fossem uma,
# e isso não dá erro: dá números errados.
#
#   1_fontes/irct/convencoes/PRI|SPE|APU/   ← o pipeline lê daqui
#   1_fontes/irct/portarias_extensao/
#   1_fontes/irct/acordos_adesao/
#
# O âmbito só subdivide as convenções. Numa portaria e num acordo de adesão não
# serve para nada: o que o âmbito decide é se o documento entra no pipeline, e
# nenhum destes entra. Subdividi-los era criar pastas que ninguém usaria para
# responder a pergunta nenhuma. Ver ADR-0018 e docs/rnc/README.md §5.7.
PASTA_FAMILIA = {"convencao": "convencoes", "extensao": "portarias_extensao",
                 "adesao": "acordos_adesao"}
PASTA_FAMILIA_DESCONHECIDA = "por_classificar"

# Famílias em que o âmbito ainda subdivide a pasta.
FAMILIAS_COM_AMBITO = frozenset({"convencao"})

# Famílias que não têm pasta nenhuma: existem só como metadado de outro
# documento. O aviso de projeto de portaria de extensão anuncia uma portaria
# que virá a seguir; guardar o PDF do anúncio ao lado do PDF da portaria é
# guardar duas vezes a mesma informação, e a que interessa — que houve projeto,
# e quando — cabe numa coluna. A linha de catálogo mantém-se: o que não se
# guarda é o ficheiro.
FAMILIAS_SO_METADADO = frozenset({"aviso"})

FAMILIAS_PROCESSAVEIS = frozenset({"convencao"})

ESTADOS_COM_FICHEIRO = {"descarregado", "ja_existente", "inalterado"}

MAX_NOME = 63          # limite de nome de documento do MaxQDA (RF-21)
MAX_SIGLA = 20
MIN_CHAVE_PARCIAL = 12   # ver a nota em sigla(), sobre correspondência parcial


class NomeRNCInvalido(ValueError):
    """Os metadados não permitem um nome RNC íntegro.

    Não é um aviso que a equipa possa aceitar com `--aceitar-heuristicas`: falta
    um campo estrutural do nome (código da convenção de base, referência da
    portaria, tipo conhecido) ou o nome não cabe no limite sem cortar a cabeça.
    Como um nome atribuído não muda, o ficheiro não é escrito.
    """

# `CCT-ALT.20250708.321/2025` → tipo, data, sequencial/ano do documento
# referido. É o formato da cadeia de alterações do índice do BTE.
RE_ALTERA = re.compile(r"^\s*(?P<tipo>[A-Z][A-Z-]*)\.(?P<data>\d{8})\."
                       r"(?P<seq>\d+)/(?P<ano>\d{4})\s*$")

# «Portaria n.º 452/2025», «Portaria n.º 50-A/2025», «Portaria nº 7/2026».
RE_PORTARIA = re.compile(
    r"\bPortaria\s+n\.?\s*[º°o]?\s*(?P<num>\d{1,4})"
    r"(?:\s*-\s*(?P<suf>[A-Za-z]))?\s*/\s*(?P<ano>\d{4})\b", re.IGNORECASE)

# Palavras que não entram numa sigla derivada por recurso.
LIGACOES = {"de", "do", "da", "dos", "das", "e", "em", "a", "o", "as", "os",
            "no", "na", "nos", "nas", "para", "com", "ao", "aos", "à", "às"}
FORMA_JURIDICA = {"sa", "s", "lda", "ldª", "l", "da", "unipessoal", "crl",
                  "sarl", "sgps", "inc", "sucursal", "limitada",
                  "sociedade", "em", "ea", "eim", "ldas"}

# Palavras que quase todas as organizações têm no nome e que, por isso, não
# distinguem ninguém. Só são descartadas se sobrar alguma coisa depois.
GENERICOS = {"sindicato", "sindicatos", "sindical", "sindicais", "associacao",
             "associacoes", "federacao", "confederacao", "uniao", "nacional",
             "nacionais", "trabalhadores", "trabalhadoras", "profissionais",
             "portugues", "portuguesa", "portugueses", "portugal"}

RE_PARENTESES = re.compile(r"\(([^)]{2,30})\)")
RE_FIM_APOS_TRACO = re.compile(r"[-–—]\s*([^-–—,;()]{2,30})\s*$")
RE_INICIO_ANTES_TRACO = re.compile(r"^\s*([^-–—,;()]{2,30}?)\s*[-–—]\s")
RE_ENTRE_TRACOS = re.compile(r"[-–—]\s*([^-–—,;()]{2,30}?)\s*(?=[-–—]|$)")
RE_PARTES_TITULO = re.compile(
    r"\bentre\s+(?:a|o|as|os)?\s*(?P<a>.+?)\s+e\s+(?:a|o|as|os)\s+(?P<b>.+?)\s*$",
    re.IGNORECASE | re.DOTALL)


def _e_sigla(token: str) -> bool:
    """'ACRAL' e 'AEVP' sim; 'Sindicato' e 'L.da' não."""
    limpo = re.sub(r"[^A-Za-z0-9]", "", _sem_acentos(token))
    if len(limpo) < 2 or len(limpo) > MAX_SIGLA:
        return False
    letras = [c for c in limpo if c.isalpha()]
    return bool(letras) and all(c.isupper() for c in letras)


def _limpar_sigla(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", _sem_acentos(token))


def normalizar_sigla(sigla: str) -> str:
    """A sigla como entra no nome e no siglas.csv: só letras e algarismos, sem
    acentos, até MAX_SIGLA. Vazia se não sobrar nada ("!!!", "  ")."""
    return _limpar_sigla(sigla)[:MAX_SIGLA]


def chave_entidade(nome: str) -> str:
    """A regra única de «a mesma entidade» na tabela de siglas: sem acentos nem
    maiúsculas, e sem os espaços e a pontuação à volta. Serve a leitura do
    siglas.csv, a procura da sigla, a gravação e a janela de confirmação."""
    return _sem_acentos((nome or "").strip().strip(" .;,")).lower()


def _camel(nome: str, max_chars: int = MAX_SIGLA) -> str:
    """Recurso quando não há sigla: 'Águas do Norte' → 'AguasNorte'.

    Descarta ligações e formas jurídicas e, se ainda assim sobrar alguma coisa,
    também as palavras genéricas: 'Sindicato Nacional dos Motoristas' vale
    'Motoristas', não 'SindicatoNacional'.
    """
    uteis = []
    # `\w` inclui o `_`, que no nome separa campos: parte-se também por ele.
    for bruto in re.split(r"[^\wÀ-ÿ]+|_+", _sem_acentos(nome)):
        baixo = bruto.lower()
        if not bruto or len(bruto) < 2:
            continue
        if baixo in LIGACOES or baixo in FORMA_JURIDICA:
            continue
        uteis.append(bruto if bruto.isupper() else bruto.capitalize())
    distintivas = [p for p in uteis if p.lower() not in GENERICOS]
    palavras = (distintivas or uteis)[:4]
    saida = ""
    for p in palavras:
        if len(saida) + len(p) > max_chars and saida:
            break
        saida += p
    return saida[:max_chars] or "SemNome"


def sigla(nome: str, tabela: dict[str, str] | None = None) -> tuple[str, str | None]:
    """Sigla de um outorgante. Devolve (sigla, aviso) — aviso quando é derivada."""
    nome = (nome or "").strip(" .;,")
    if not nome:
        return "", "outorgante vazio"
    if tabela:
        chave = chave_entidade(nome)
        if chave in tabela:
            return tabela[chave], None
        # Correspondência parcial, para apanhar as variações de pontuação e os
        # «e outros» que o índice acrescenta. Só com chaves longas, e ganha a
        # mais longa: com uma tabela de milhares de entradas, uma chave curta
        # encaixa por acaso dentro de meio registo e atribui a sigla errada em
        # silêncio — que é precisamente o erro que a tabela existe para evitar.
        melhor = max((k for k in tabela
                      if len(k) >= MIN_CHAVE_PARCIAL and k in chave),
                     key=len, default=None)
        if melhor:
            return tabela[melhor], None
    for regex in (RE_PARENTESES, RE_FIM_APOS_TRACO, RE_INICIO_ANTES_TRACO,
                  RE_ENTRE_TRACOS):
        for m in regex.finditer(nome):
            if _e_sigla(m.group(1)):
                return _limpar_sigla(m.group(1)), None
    return _camel(nome), f"sigla derivada de «{nome[:60]}» — confirmar"


def e_sindical(nome: str) -> bool:
    """Sindical é quem tem 'sindic' no nome.

    Classifica corretamente a CNIS (Confederação Nacional das Instituições de
    Solidariedade) como patronal e a FNSTFPS (Federação Nacional dos Sindicatos
    dos Trabalhadores…) como sindical.
    """
    return "sindic" in _sem_acentos(nome).lower()


def _partes_do_titulo(titulo: str) -> list[str]:
    """'Contrato coletivo entre a X e o Y' → ['X', 'Y'] (para as retificações)."""
    m = RE_PARTES_TITULO.search(re.sub(r"\s+", " ", titulo or ""))
    if not m:
        return []
    partes = []
    for lado in (m.group("a"), m.group("b")):
        # «e Outros Trabalhadores» pode integrar o nome oficial da entidade.
        # Só remover «e outros» quando termina o lado, não a meio do nome.
        lado = re.sub(r"\s+e\s+outr[ao]s?\s*$", "", lado, flags=re.IGNORECASE)
        partes.append(lado.strip(" .,;"))
    return [p for p in partes if p]


def separar_outorgantes(outorgantes: str, titulo: str = "") -> tuple[list[str], list[str]]:
    """Divide os outorgantes em (patronais, sindicais)."""
    nomes = [n.strip() for n in re.split(r"[;\n]", outorgantes or "") if n.strip()]
    if not nomes:
        nomes = _partes_do_titulo(titulo)
    patronais = [n for n in nomes if not e_sindical(n)]
    sindicais = [n for n in nomes if e_sindical(n)]
    return patronais, sindicais


def sequencial_bte(entrada: dict) -> int | None:
    """O «377» de `ID: 377/2026` — a posição do documento na série anual do BTE.

    É o que o esquema RNC usa como número sequencial, em vez do ordinal interno
    da aplicação: é o número pelo qual o documento é citado no próprio boletim e
    nas cadeias de alteração (`CCT-ALT.20250708.321/2025`), pelo que é o único
    que permite ligar um ficheiro ao que o índice diz sobre ele.
    """
    bruto = str(entrada.get("id_dgert") or "").strip()
    m = re.match(r"^\s*(\d+)\s*/\s*(\d{4})\s*$", bruto)
    if m:
        return int(m.group(1))
    return int(m.group(0)) if (m := re.match(r"^\d+$", bruto)) else None


def tipo_normalizado(tipo: str | None) -> str:
    """`CCT-ALT-RECT` a partir do que vier no índice; `SEMTIPO` se vier vazio."""
    limpo = re.sub(r"[^A-Z0-9-]", "", _sem_acentos(tipo or "").upper())
    limpo = re.sub(r"-{2,}", "-", limpo).strip("-")
    return limpo or "SEMTIPO"


def _outorgantes_escolhidos(entrada: dict, maximo: int = MAX_SIGLAS_RNC
                            ) -> tuple[list[str], list[str], list[str]]:
    """Os outorgantes que entram no nome, todos os outorgantes, e os avisos."""
    avisos: list[str] = []
    nomes = [n.strip() for n in re.split(r"[;\n]", entrada.get("outorgantes") or "")
             if n.strip()]
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
        avisos.append(f"só há partes do lado {lado} — o nome usa as "
                      f"{len(escolhidos)} primeira(s) pela ordem do índice; confirmar")
    return escolhidos, nomes, avisos


def siglas_outorgantes(entrada: dict, tabela: dict[str, str] | None = None,
                       maximo: int = MAX_SIGLAS_RNC) -> tuple[list[str], int, list[str]]:
    """A primeira sigla patronal e a primeira sindical, e quantas partes sobram.

    Um de cada lado da mesa, por esta ordem: é o par pelo qual a equipa procura
    uma convenção (ADR-0022). Se só houver partes de um lado — acontece quando
    o nome de um sindicato não diz «sindic», como «FNSTFPS» sozinho —, levam-se
    as `maximo` primeiras pela ordem do índice e fica um aviso, porque o par
    escolhido pode não ser o principal.
    """
    escolhidos, nomes, avisos = _outorgantes_escolhidos(entrada, maximo)
    if not nomes:
        return [], 0, avisos
    siglas: list[str] = []
    for nome in escolhidos:
        s, aviso = sigla(nome, tabela)
        if aviso:
            avisos.append(aviso)
        if s:
            siglas.append(s)
    return siglas, max(0, len(nomes) - len(siglas)), avisos


def referencia_portaria(entrada: dict) -> tuple[int, str, int] | None:
    """`(número, sufixo, ano do DR)` da portaria, ou `None` se não for certo.

    Lê primeiro o campo `portaria_dr` do índice (`452/2025`, `50-A/2025`), se o
    índice o trouxer, e só depois o título. Um ano do DR posterior ao do BTE não
    é possível — a portaria é publicada no DR antes de ser publicitada no BTE —
    e é tratado como leitura errada, não como facto.
    """
    ano_bte = int(entrada.get("ano") or 0)
    for fonte in (entrada.get("portaria_dr"), entrada.get("titulo")):
        texto = str(fonte or "").strip()
        if not texto:
            continue
        m = RE_PORTARIA.search(texto if "ortaria" in texto else f"Portaria n.º {texto}")
        if not m:
            continue
        numero, ano_dr = int(m.group("num")), int(m.group("ano"))
        if numero == 0 or (ano_bte and ano_dr > ano_bte):
            return None
        return numero, (m.group("suf") or "").upper(), ano_dr
    return None


def _codigos(valor) -> list[str]:
    """`"27251; 26760"` → `["27251", "26760"]`, pela ordem, sem repetidos."""
    return list(dict.fromkeys(c for c in (re.sub(r"\D", "", p)
                                          for p in re.split(r"[;,\s]+", str(valor or "")))
                              if c))


def cod_irct_base(entrada: dict) -> str | None:
    """O código IRCT que vai no nome: o da convenção de base, ou `None`.

    Numa convenção é o seu próprio `COD: (IRCT)`. Numa portaria, adesão ou
    aviso é o da convenção a que o documento se refere — lido de uma coluna do
    índice, quando o passo 0 da SPEC-0004 a identificar, ou resolvido pela
    cadeia de alterações (`resolver_convencoes_base`). O `COD: (IRCT)` da
    própria portaria **não** é usado: não se sabe ainda se é o da convenção ou
    um código próprio (README do RNC, §9, tarefa 3).
    """
    fam = entrada.get("familia") or familia(entrada.get("tipo", "")) or "convencao"
    if fam == "convencao":
        codigos = _codigos(entrada.get("cod_irct"))
    else:
        codigos = _codigos(entrada.get("cod_irct_base"))
    return codigos[0] if codigos else None


def resolver_convencoes_base(entradas) -> None:
    """Liga cada PE, AA e aviso ao código IRCT da convenção de base.

    A cadeia de alterações do índice de uma portaria aponta para o documento que
    ela estende (`CCT.20260822.377/2026`). Se esse documento estiver entre as
    `entradas` — o registo acumulado, ou os índices lidos pelo catálogo —, com o
    mesmo tipo e o mesmo `IDDocumento`, o seu código IRCT é o da convenção de
    base. A correspondência é exata ou não há correspondência: um documento de
    base que não esteja entre as entradas deixa o código por resolver, e o nome
    fica por confirmar.

    Um código que tenha vindo diretamente de uma coluna do índice
    (`cod_irct_base_origem == "indice"`) não é substituído.
    """
    entradas = list(entradas)
    convencoes: dict[tuple[str, str], list[dict]] = {}
    for e in entradas:
        if (e.get("familia") or familia(e.get("tipo", ""))) != "convencao":
            continue
        m = re.match(r"^\s*(\d+)\s*/\s*(\d{4})\s*$", str(e.get("id_dgert") or ""))
        if m:
            convencoes.setdefault((str(int(m.group(1))), m.group(2)), []).append(e)
    for e in entradas:
        fam = e.get("familia") or familia(e.get("tipo", ""))
        if fam in (None, "convencao"):
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
                alvos = [c for c in convencoes.get((str(int(m.group("seq"))),
                                                    m.group("ano")), [])
                         if tipo_normalizado(c.get("tipo")) == m.group("tipo")]
            cods = _codigos(alvos[0].get("cod_irct")) if len(alvos) == 1 else []
            if cods:
                codigos.append(cods[0])
            else:
                por_resolver.append(ref.strip())
        codigos = list(dict.fromkeys(codigos))
        e["cod_irct_base"] = "; ".join(codigos)
        e["cod_irct_base_origem"] = "cadeia_do_indice" if codigos else ""
        e["cod_irct_base_por_resolver"] = "; ".join(por_resolver)


def _nome_rnc(entrada: dict, ordinal: int, tabela: dict[str, str] | None,
              vocabulario_ambito: dict[str, str] | None) -> tuple[str, list[str]]:
    """Nome no esquema do ADR-0022.

        convenção   {ANO}_BTE_{NN}_{AMBITO}_{SEQ}_{TIPO}_{CODIRCT}_{SIGLAS}
        portaria    {ANO}_BTE_{NN}_{TIPO}_{SEQ}_{NNNN}-{AAAA}_{CODIRCT}_{SIGLAS}
        adesão      {ANO}_BTE_{NN}_AA_{SEQ}_{CODIRCT}_{SIGLAS}

    Os avisos pedem confirmação humana antes de o ficheiro ser escrito;
    `NomeRNCInvalido` diz que falta um campo estrutural e que o ficheiro não
    pode ser escrito de todo.
    """
    avisos: list[str] = []
    ano = int(entrada.get("ano") or 0)
    num_bte = int(entrada.get("num_bte") or 0)
    tipo = tipo_normalizado(entrada.get("tipo"))
    fam = entrada.get("familia") or familia(entrada.get("tipo", "")) or "convencao"

    seq = sequencial_bte(entrada)
    if seq is None:
        seq = ordinal
        avisos.append("sem «ID: nnn/aaaa» no índice — usado o ordinal interno "
                      f"({ordinal}); o número não corresponde ao do boletim")

    patronais, _sindicais = separar_outorgantes(entrada.get("outorgantes", ""),
                                                entrada.get("titulo", ""))
    amb, origem, aviso_amb = mod_ambito.classificar_com_ine(
        patronais[0] if patronais else entrada.get("titulo", ""),
        entrada.get("tipo", ""), vocabulario_ambito)
    entrada.setdefault("nomeacao", {}).update({"ambito": amb,
                                               "ambito_origem": origem})

    if fam in QUARTO_CAMPO_TIPO:
        # O âmbito não entra no nome de uma portaria nem de uma adesão, pelo
        # que o aviso de âmbito também não pesa aqui: fica no catálogo.
        if tipo not in QUARTO_CAMPO_TIPO[fam]:
            raise NomeRNCInvalido(
                f"tipo {tipo} fora do vocabulário do quarto campo "
                f"({', '.join(QUARTO_CAMPO_TIPO[fam])}) — decisão registada "
                "necessária (ADR-0022)")
        quarto, miolo = tipo, ""
        if fam == "extensao":
            ref = referencia_portaria(entrada)
            if ref is None:
                raise NomeRNCInvalido("sem número e ano da portaria no Diário da "
                                      "República (título ou coluna do índice)")
            numero, sufixo, ano_dr = ref
            miolo = f"_{numero:04d}{sufixo}-{ano_dr:04d}"
            entrada["nomeacao"]["portaria_dr"] = (f"{numero}{'-' + sufixo if sufixo else ''}"
                                                  f"/{ano_dr}")
        cod = cod_irct_base(entrada)
        if cod is None:
            if fam == "aviso":          # sem ficheiro: o nome é só chave de catálogo
                cod = (_codigos(entrada.get("cod_irct")) or ["0"])[0]
            else:
                raise NomeRNCInvalido("sem código IRCT da convenção de base "
                                      "confirmado (SPEC-0004, passo 0)")
        elif fam != "aviso":
            if entrada.get("cod_irct_base_origem") == "cadeia_do_indice":
                avisos.append(AVISO_BASE_PELA_CADEIA)
            todos = _codigos(entrada.get("cod_irct_base"))
            if len(todos) > 1:
                avisos.append(f"refere {len(todos)} convenções ({', '.join(todos)}) — "
                              f"o nome leva a primeira; as restantes estão no catálogo")
    else:
        if aviso_amb:
            avisos.append(aviso_amb)
        if tipo == "SEMTIPO":
            avisos.append("tipo de documento vazio no índice — confirmar")
        quarto, miolo = amb, f"_{tipo}"
        cod = cod_irct_base(entrada)
        if cod is None:
            cod = "0"
            avisos.append("sem COD: (IRCT) no índice — a série da convenção fica "
                          "por identificar")

    siglas, restantes, avisos_siglas = siglas_outorgantes(entrada, tabela)
    avisos.extend(avisos_siglas)
    if not siglas:
        siglas = [_camel(entrada.get("titulo", ""))]
        avisos.append("nome derivado do título — confirmar")

    prefixo = f"{ano:04d}_BTE_{num_bte:02d}_{quarto}_{seq:03d}{miolo}_{cod}_"
    cauda = f"+{restantes}" if restantes else ""
    nome = prefixo + "-".join(siglas) + cauda
    if len(nome) > MAX_NOME:            # encurta as siglas, nunca a cabeça nem o miolo
        folga = MAX_NOME - len(prefixo) - len(cauda) - (len(siglas) - 1)
        if folga < 3 * len(siglas):
            raise NomeRNCInvalido("campos estruturais do nome RNC excedem o limite "
                                  f"de {MAX_NOME} caracteres; confirmar tipo e código IRCT")
        por_sigla = folga // len(siglas)
        nome = prefixo + "-".join(s[:por_sigla] for s in siglas) + cauda
        avisos.append(f"nome encurtado para caber em {MAX_NOME} caracteres")
    return nome, avisos


def nome_documento(entrada: dict, ordinal: int,
                   tabela: dict[str, str] | None = None, *,
                   esquema: str = ESQUEMA_OMISSAO,
                   vocabulario_ambito: dict[str, str] | None = None
                   ) -> tuple[str, list[str]]:
    """Compõe o nome (sem extensão) e devolve os avisos que exigem confirmação."""
    if esquema not in ESQUEMAS:
        raise ValueError(f"esquema de nome desconhecido: {esquema!r} "
                         f"(conhecidos: {', '.join(ESQUEMAS)})")
    if esquema == "rnc":
        return _nome_rnc(entrada, ordinal, tabela, vocabulario_ambito)
    avisos: list[str] = []
    ano = int(entrada.get("ano") or 0)
    num_bte = int(entrada.get("num_bte") or 0)
    fam = entrada.get("familia") or "convencao"
    patronais, sindicais = separar_outorgantes(entrada.get("outorgantes", ""),
                                               entrada.get("titulo", ""))
    lados = []
    for lista, rotulo in ((patronais, "patronal"), (sindicais, "sindical")):
        if not lista:
            avisos.append(f"sem outorgante do lado {rotulo}")
            continue
        s, aviso = sigla(lista[0], tabela)
        if aviso:
            avisos.append(aviso)
        if len(lista) > 1:
            avisos.append(f"{len(lista)} outorgantes do lado {rotulo} "
                          "— o nome usa o primeiro")
        if s:
            lados.append(s)
    if not lados:
        lados = [_camel(entrada.get("titulo", ""))]
        avisos.append("nome derivado do título — confirmar")

    prefixo = (f"{ano % 100:02d}_{TOKEN_FAMILIA.get(fam, 'PR')}_{ordinal:03d}"
               f"_BTE_{num_bte:02d}")
    nome = prefixo + "".join("_" + lado for lado in lados)
    if len(nome) > MAX_NOME:                       # encurta as siglas, não o prefixo
        folga = MAX_NOME - len(prefixo) - len(lados)
        por_lado = max(4, folga // len(lados))
        nome = prefixo + "".join("_" + lado[:por_lado] for lado in lados)
        avisos.append("nome encurtado para caber em 63 caracteres")
    return nome, avisos


def atribuir_ordinais(registo: Registo, familias=("convencao", "extensao",
                                                  "aviso", "adesao")) -> int:
    """Numera os documentos por ano e família, por ordem de (nº BTE, posição).

    Um ordinal já atribuído nunca é recalculado — é o que mantém a continuidade
    com a numeração de 2025 e com o trabalho já feito sobre esses nomes.
    """
    novos = 0
    entradas = [e for e in registo.entradas.values()
                if e.get("familia") in familias
                and (e.get("descarga") or {}).get("estado") in ESTADOS_COM_FICHEIRO]
    grupos: dict[tuple, list[dict]] = {}
    for e in entradas:
        grupos.setdefault((e.get("ano"), e.get("familia")), []).append(e)
    for (_ano, _fam), grupo in grupos.items():
        usados = {o for e in grupo
                  if (o := (e.get("nomeacao") or {}).get("ordinal"))}
        proximo = max(usados) + 1 if usados else 1
        por_atribuir = [e for e in grupo
                        if not (e.get("nomeacao") or {}).get("ordinal")]
        por_atribuir.sort(key=lambda e: (e.get("num_bte") or 0,
                                         e.get("posicao") or 0, e["chave"]))
        for e in por_atribuir:
            e.setdefault("nomeacao", {})["ordinal"] = proximo
            proximo += 1
            novos += 1
    return novos


COLUNAS_NOME = ("nome", "nome_completo", "denominacao",
                "denominacao_da_organizacao", "organizacao")
COLUNAS_SIGLA = ("sigla", "acronimo", "sigla_canonica")
COLUNA_ORIGEM = "origem_sigla"

# Uma sigla que o próprio `_camel()` inventou não é uma sigla confirmada: dá
# «Motoristas» onde a equipa escreveria «SNM». Se entrasse na tabela, calava o
# aviso de «confirmar» e transformava um palpite num facto. Fica no ficheiro,
# para se ver o que falta, mas não é carregada — promove-se editando a coluna
# `origem_sigla` para `equipa` depois de alguém a ter visto.
ORIGENS_IGNORADAS = frozenset({"recurso"})


def carregar_siglas(caminho: Path) -> dict[str, str]:
    """Tabela de siglas fixadas pela equipa → {nome normalizado: sigla}.

    Aceita dois formatos, para que a mesma bandeira `--siglas` sirva tanto a
    lista curta que alguém escreve à mão como o `vocabularios/
    siglas_organizacoes.csv` gerado do registo da DGERT:

    * **sem cabeçalho** — `nome;sigla`, as duas primeiras colunas;
    * **com cabeçalho** — as colunas são encontradas pelo nome (`denominacao`
      e `sigla`, entre outros), seja qual for a ordem em que venham.

    Separador `;`, UTF-8 com ou sem BOM. Linhas incompletas são saltadas em
    silêncio; um ficheiro cujo cabeçalho não tenha nenhuma coluna reconhecível
    é tratado como sendo do formato sem cabeçalho.
    """
    import csv

    tabela: dict[str, str] = {}
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        linhas = [linha for linha in csv.reader(f, delimiter=";") if linha and linha[0].strip()]
    if not linhas:
        return tabela

    i_nome, i_sigla = 0, 1
    cabecalho = [re.sub(r"[^a-z0-9]+", "_", _sem_acentos(c).strip().lower()).strip("_")
                 for c in linhas[0]]
    tem_cabecalho = any(c in COLUNAS_NOME for c in cabecalho)
    if tem_cabecalho:
        i_nome = next(i for i, c in enumerate(cabecalho) if c in COLUNAS_NOME)
        candidatos = [i for i, c in enumerate(cabecalho) if c in COLUNAS_SIGLA]
        if not candidatos:
            return tabela
        i_sigla = candidatos[0]
        linhas = linhas[1:]
    i_origem = (cabecalho.index(COLUNA_ORIGEM)
                if tem_cabecalho and COLUNA_ORIGEM in cabecalho else None)

    for linha in linhas:
        if max(i_nome, i_sigla) >= len(linha):
            continue
        # A origem pode vir composta (`recurso+desambiguada`): compara-se a
        # parte antes do `+`, que é de onde a sigla saiu. Comparar a cadeia
        # inteira deixava passar exatamente as siglas que isto existe para
        # travar — e sem dar erro nenhum.
        if (i_origem is not None and i_origem < len(linha)
                and linha[i_origem].strip().lower().split("+")[0]
                in ORIGENS_IGNORADAS):
            continue
        nome = chave_entidade(linha[i_nome])
        valor = normalizar_sigla(linha[i_sigla])
        if not nome or not valor:
            continue
        if not tem_cabecalho and nome in COLUNAS_NOME:
            continue                       # cabeçalho não declarado
        tabela.setdefault(nome, valor)
    return tabela


def siglas_derivadas(entrada: dict, tabela: dict[str, str] | None = None,
                     esquema: str = ESQUEMA_OMISSAO) -> list[tuple[str, str]]:
    """(outorgante, sigla sugerida) das siglas do nome que foram adivinhadas."""
    if esquema == "rnc":
        escolhidos, _nomes, _avisos = _outorgantes_escolhidos(entrada)
    else:
        patronais, sindicais = separar_outorgantes(entrada.get("outorgantes", ""),
                                                   entrada.get("titulo", ""))
        escolhidos = [lista[0] for lista in (patronais, sindicais) if lista]
    derivadas = []
    for nome in escolhidos:
        s, aviso = sigla(nome, tabela)
        if aviso and s:
            derivadas.append((nome.strip(" .;,"), s))
    return derivadas


def pendentes(registo: Registo, tabela: dict[str, str] | None = None,
              esquema: str = ESQUEMA_OMISSAO) -> list[dict]:
    """Os documentos por confirmar, com as siglas a confirmar e os outros avisos.

    É o que a janela de confirmação da app mostra (#38): para cada documento,
    a sigla sugerida de cada outorgante cuja sigla foi adivinhada, e os
    restantes avisos, que a pessoa vê antes de confirmar.
    """
    lista = []
    for e in registo.entradas.values():
        nomeacao = e.get("nomeacao") or {}
        if nomeacao.get("estado") != "por_confirmar":
            continue
        derivadas = siglas_derivadas(e, tabela, esquema)
        outros = [a for a in nomeacao.get("avisos", []) if "sigla derivada" not in a]
        lista.append({"chave": e["chave"], "doc_id": nomeacao.get("doc_id", ""),
                      "titulo": (e.get("titulo") or "")[:160],
                      "siglas": derivadas, "outros_avisos": outros})
    return sorted(lista, key=lambda p: p["chave"])


def gravar_siglas(caminho: Path, decisoes: dict[str, str]) -> Path:
    """Acrescenta ou atualiza `nome;sigla` no siglas.csv da equipa.

    O ficheiro é criado se não existir e nunca é substituído: as linhas que já
    lá estão ficam, e uma entidade que já lá esteja passa a ter a sigla nova.
    Uma sigla que não sobrevive à normalização é um erro (ValueError), e nada
    é escrito. Escreve-se no formato sem cabeçalho que o `carregar_siglas()` lê.
    """
    import csv
    caminho = Path(caminho)
    linhas: list[list[str]] = []
    if caminho.exists():
        with open(caminho, encoding="utf-8-sig", newline="") as f:
            linhas = [linha for linha in csv.reader(f, delimiter=";") if linha and linha[0].strip()]
    inuteis = [n for n, s in decisoes.items() if n.strip() and not normalizar_sigla(s)]
    if inuteis:
        # nunca descartar em silêncio uma decisão (revisão do PR #96)
        raise ValueError("sigla sem letras nem algarismos para: " + "; ".join(inuteis))
    decisoes = {n.strip(): normalizar_sigla(s) for n, s in decisoes.items() if n.strip()}
    por_chave = {chave_entidade(n): n for n in decisoes}
    vistas = set()
    for linha in linhas:
        chave = chave_entidade(linha[0])
        if chave in por_chave and len(linha) >= 2:
            linha[1] = decisoes[por_chave[chave]]
            vistas.add(chave)
    linhas += [[n, s] for n, s in decisoes.items()
               if chave_entidade(n) not in vistas]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter=";", lineterminator="\n").writerows(linhas)
    return caminho


def tabela_de_siglas(caminhos: list[Path], equipa: Path | None = None) -> dict[str, str]:
    """A tabela de siglas: o siglas.csv da equipa (se existir) e os indicados.

    O da equipa vem primeiro e ganha: é onde ficam as siglas que uma pessoa
    confirmou, uma a uma. Em caso de conflito entre os indicados, ganha o
    primeiro, como sempre.
    """
    equipa = SIGLAS_EQUIPA if equipa is None else equipa
    ordem = ([equipa] if equipa.is_file() else []) + [
        Path(c) for c in caminhos if Path(c).resolve() != equipa.resolve()]
    tabela: dict[str, str] = {}
    for caminho in ordem:
        for nome, s in carregar_siglas(caminho).items():
            tabela.setdefault(nome, s)
    return tabela


def _e_nome_adr0016(nome: str) -> bool:
    from .localizador import interpretar_nome_rnc

    meta = interpretar_nome_rnc(nome or "")
    return meta is not None and meta["esquema"] == "adr0016"


def _concluir_migracao(entrada: dict, anterior: Path, alvo: Path,
                       sha: str | None, resumo: dict) -> None:
    """Apaga o PDF com o nome antigo, se for o mesmo conteúdo, e regista a troca.

    Um ficheiro antigo com conteúdo diferente não é apagado: é um problema a
    ver por uma pessoa, não uma cópia redundante.
    """
    nomeacao = entrada["nomeacao"]
    if anterior.is_file():
        if sha and sha256_ficheiro(anterior) == sha:
            anterior.unlink()
        else:
            resumo["problemas"].append(
                f"{anterior.name}: conteúdo diferente do recolhido — o ficheiro "
                "antigo não foi apagado; verificar")
    resumo["migracoes"].append({
        "nome_anterior": nomeacao.get("doc_id_anterior", anterior.stem),
        "nome_novo": alvo.stem, "sha256": sha or "",
        "id_dgert": entrada.get("id_dgert", ""), "chave": entrada.get("chave", "")})
    nomeacao["migrado_de"] = nomeacao.pop("doc_id_anterior", anterior.stem)
    nomeacao.pop("caminho_anterior", None)


def escrever_correspondencia(migracoes: list[dict], caminho: Path) -> None:
    """Acrescenta as migrações à tabela `nome_anterior;nome_novo;…`.

    É a tabela que `cct.catalogo --correspondencia` usa para passar as colunas
    da equipa do nome antigo para o novo (SPEC-0004, passo 4). Acrescenta em vez
    de substituir, porque uma migração pode fazer-se em várias corridas.
    """
    import csv

    colunas = ["nome_anterior", "nome_novo", "sha256", "id_dgert", "chave"]
    novo = not caminho.exists()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas, delimiter=";", lineterminator="\n")
        if novo:
            w.writeheader()
        w.writerows(migracoes)


def nomear(registo: Registo, destino: Path, *, aplicar: bool = False,
           tabela: dict[str, str] | None = None,
           familias=("convencao", "extensao", "aviso", "adesao"),
           aceitar_heuristicas: bool = False,
           esquema: str = ESQUEMA_OMISSAO,
           vocabulario_ambito: dict[str, str] | None = None,
           migrar: bool = False,
           confirmados: set[str] | None = None) -> dict:
    """Atribui nomes e, com `aplicar=True`, copia os PDFs para o destino.

    Um documento cujo nome tenha avisos de `nome_documento()` (sigla
    derivada por heurística, outorgante em falta, nome do título, nome
    encurtado) fica em estado `por_confirmar` e **não é escrito**, mesmo com
    `aplicar=True` — a confirmação humana que a spec promete tem de acontecer
    antes de o ficheiro existir e o ordinal ficar permanente, não depois.
    `aceitar_heuristicas=True` desliga esta proteção, para quem decide
    conscientemente aceitar o risco (ex.: uma corrida em lote já revista).

    Com `esquema="rnc"` os ficheiros são arrumados em subpastas por âmbito
    (`PRI/`, `SPE/`, `APU/`), para que «não conseguimos processar isto» deixe de
    ser uma nota num documento e passe a ser a estrutura das pastas.

    Um documento já nomeado não muda de nome: um nome novo diferente do que
    está escrito é `conflito`. A única exceção é `migrar=True`, e só para nomes
    do esquema RNC anterior (ADR-0016), que o ADR-0022 manda passar uma vez
    para o esquema novo. Nesse caso o PDF é escrito com o nome novo, o antigo é
    apagado depois de conferido o `sha256`, e a correspondência fica em
    `resumo["migracoes"]` — é dela que o catálogo precisa para não perder as
    colunas da equipa (SPEC-0004, passo 4).

    `confirmados` são as chaves dos documentos que uma pessoa confirmou, um a
    um (a janela de confirmação da app, #38): só esses são processados, e os
    avisos deles não os travam — foram vistos. É a alternativa, documento a
    documento, ao `aceitar_heuristicas`, que vale para a corrida inteira.
    """
    if esquema not in ESQUEMAS:
        raise ValueError(f"esquema de nome desconhecido: {esquema!r} "
                         f"(conhecidos: {', '.join(ESQUEMAS)})")
    resumo: dict[str, Any] = {"ordinais_novos": atribuir_ordinais(registo, familias),
              "por_estado": {}, "avisos": [], "problemas": [], "nomes": [],
              "migracoes": []}
    if esquema == "rnc":
        resolver_convencoes_base(registo.entradas.values())

    def contar(estado):
        resumo["por_estado"][estado] = resumo["por_estado"].get(estado, 0) + 1

    entradas = [e for e in registo.entradas.values()
                if e.get("familia") in familias
                and (e.get("descarga") or {}).get("estado") in ESTADOS_COM_FICHEIRO
                and not (esquema == "rnc"
                         and e.get("familia") in FAMILIAS_SO_METADADO)
                and (confirmados is None or e.get("chave") in confirmados)]
    entradas.sort(key=lambda e: (e.get("ano") or 0, e.get("num_bte") or 0,
                                 (e.get("nomeacao") or {}).get("ordinal") or 0))
    vistos: dict[tuple, list[str]] = {}
    escritos = 0

    try:
        for e in entradas:
            nomeacao = e.setdefault("nomeacao", {})
            sha_recolhido = (e.get("descarga") or {}).get("sha256")
            origem = Path((e.get("descarga") or {}).get("caminho", ""))
            if not origem.exists():
                # O PDF intermédio da recolha é descartável (ADR-0014). Se já
                # houver uma cópia nomeada com o mesmo conteúdo, serve de origem.
                ja_nomeado = Path(nomeacao.get("caminho_anterior")
                                  or nomeacao.get("caminho") or "")
                if (ja_nomeado.name and ja_nomeado.is_file()
                        and sha256_ficheiro(ja_nomeado) == sha_recolhido):
                    origem = ja_nomeado
                else:
                    resumo["problemas"].append(f"{e['chave']}: PDF recolhido não "
                                               f"encontrado ({origem})")
                    nomeacao["estado"] = "sem_origem"
                    contar("sem_origem")
                    continue
            if (not origem.is_file() or not sha_recolhido
                    or sha256_ficheiro(origem) != sha_recolhido):
                nomeacao["estado"] = "sem_origem"
                resumo["problemas"].append(f"{e['chave']}: origem sem hash válido ou alterada")
                contar("sem_origem")
                continue
            try:
                nome, avisos = nome_documento(e, nomeacao["ordinal"], tabela,
                                              esquema=esquema,
                                              vocabulario_ambito=vocabulario_ambito)
            except NomeRNCInvalido as exc:
                nomeacao["estado"] = "por_confirmar"
                nomeacao["avisos"] = [str(exc)]
                resumo["problemas"].append(f"{e['chave']}: {exc} — PDF não escrito")
                contar("por_confirmar")
                continue
            nomeacao = e["nomeacao"]      # _nome_rnc pode ter registado o âmbito
            nome_anterior = nomeacao.get("doc_id")
            if (migrar and nome_anterior and nome_anterior != nome
                    and nomeacao.get("estado") in {"nomeado", "ja_existente", "conflito"}
                    and _e_nome_adr0016(nome_anterior)):
                # Migração do ADR-0022: guarda-se de onde vem, antes de o
                # doc_id passar a ser o novo — sem isto, uma migração que fique
                # por confirmar perdia o rasto do ficheiro antigo.
                nomeacao.setdefault("doc_id_anterior", nome_anterior)
                nomeacao.setdefault("caminho_anterior", nomeacao.get("caminho", ""))
                nomeacao["estado"] = "por_migrar"
            if (nome_anterior and nome_anterior != nome and
                    nomeacao.get("estado") in {"nomeado", "ja_existente", "conflito"}):
                # Um nome já escrito pode estar no MaxQDA e no catálogo.
                # Uma nova tabela de siglas não deve criar outra cópia nem
                # substituir silenciosamente a identidade persistida.
                nomeacao["estado"] = "conflito"
                resumo["problemas"].append(
                    f"{e['chave']}: nome já atribuído {nome_anterior}; "
                    f"novo nome proposto {nome} — migração controlada necessária, "
                    "nenhum PDF escrito")
                contar("conflito")
                continue
            avisos_heuristica = list(avisos)   # antes do aviso de par repetido, abaixo —
                                               # esse é informativo, não indica nome errado
            partes = ("_".join(nome.split("_")[5:]) if esquema == "pipeline"
                      else nome.rsplit("_", 1)[-1])
            chave_par = (e.get("ano"), e.get("familia"), partes)
            vistos.setdefault(chave_par, []).append(nome)
            if len(vistos[chave_par]) > 1:
                avisos.append("outro documento do mesmo par de outorgantes neste ano: "
                              + ", ".join(vistos[chave_par][:-1]))
            if esquema == "rnc":
                fam = e.get("familia")
                pasta = (destino / f"bte_{e['ano']}"
                         / PASTA_FAMILIA.get(fam or "", PASTA_FAMILIA_DESCONHECIDA))
                if fam in FAMILIAS_COM_AMBITO:
                    pasta = pasta / nomeacao.get("ambito", mod_ambito.OMISSAO)
            else:
                subpasta = SUBPASTA_FAMILIA.get(e["familia"], "")
                pasta = destino / f"bte_{e['ano']}" / subpasta if subpasta \
                    else destino / f"bte_{e['ano']}"
            alvo = pasta / f"{nome}.pdf"
            nomeacao.update({"doc_id": nome, "caminho": str(alvo), "avisos": avisos})
            resumo["nomes"].append((e["chave"], nome))
            resumo["avisos"].extend(f"{nome}: {a}" for a in avisos)

            anterior: Path | None = Path(nomeacao.get("caminho_anterior") or "")
            if anterior is not None and (not anterior.name or anterior == alvo):
                anterior = None

            if alvo.exists():
                if sha256_ficheiro(alvo) == sha_recolhido:
                    nomeacao["estado"] = "ja_existente"
                    contar("ja_existente")
                    if aplicar and anterior is not None:
                        _concluir_migracao(e, anterior, alvo, sha_recolhido, resumo)
                else:
                    nomeacao["estado"] = "conflito"
                    resumo["problemas"].append(
                        f"{nome}: já existe um ficheiro diferente no destino — não foi escrito")
                    contar("conflito")
                continue

            if avisos_heuristica and not (aceitar_heuristicas or confirmados):
                nomeacao["estado"] = "por_confirmar"
                contar("por_confirmar")
                continue

            if not aplicar:
                estado = "por_migrar" if anterior is not None else "por_nomear"
                nomeacao["estado"] = estado
                contar(estado)
                continue

            pasta.mkdir(parents=True, exist_ok=True)
            temp = alvo.with_suffix(".pdf.part")
            shutil.copyfile(origem, temp)
            temp.replace(alvo)
            nomeacao.update({"estado": "nomeado",
                             "data": time.strftime("%Y-%m-%dT%H:%M:%S")})
            contar("nomeado")
            if anterior is not None:
                _concluir_migracao(e, anterior, alvo, sha_recolhido, resumo)
            escritos += 1
            if escritos % INTERVALO_PERSISTENCIA == 0:
                registo.guardar()
    finally:
        registo.guardar()
    return resumo


def familia_do_nome(nome: str) -> str | None:
    """A família documental que um nome de ficheiro declara, ou `None`.

    Lê os três esquemas: no do ADR-0022 pelo quarto campo
    (`2026_BTE_01_PE_012_…` → `extensao`), no do ADR-0016 pelo tipo
    (`2026_PRI_401_PE_…` → `extensao`) e no de 2025 pelo token da família
    (`26_PE_001_BTE_31_…` → `extensao`). Serve para que quem consome uma pasta
    de PDF possa recusar o que não devia lá estar, em vez de o processar.
    """
    from .localizador import RE_DOC_ID, interpretar_nome_rnc

    meta = interpretar_nome_rnc(nome)
    if meta:
        return meta["familia"] or familia(meta["tipo"])
    m = RE_DOC_ID.match(nome.strip())
    if not m:
        return None
    token = nome.split("_")[1]
    for fam, tok in TOKEN_FAMILIA.items():
        if tok == token:
            return fam
    return None


def texto_resumo(resumo: dict, *, aplicar: bool) -> str:
    linhas = ["== Nomeação"]
    linhas.append(f"  ordinais novos atribuídos: {resumo['ordinais_novos']}")
    for estado, n in sorted(resumo["por_estado"].items()):
        linhas.append(f"    {estado}: {n}")
    if not aplicar and resumo["por_estado"].get("por_nomear"):
        linhas.append("  (simulação — repetir com --aplicar para escrever)")
    if resumo["por_estado"].get("por_confirmar"):
        linhas.append("  (siglas por confirmar — corrigir com --siglas, ou aceitar "
                      "conscientemente o risco com --aceitar-heuristicas)")
    if resumo.get("migracoes"):
        linhas.append(f"  migrados do esquema do ADR-0016 ({len(resumo['migracoes'])}):")
        linhas.extend(f"    {m['nome_anterior']} → {m['nome_novo']}"
                      for m in resumo["migracoes"])
    if resumo["avisos"]:
        linhas.append(f"  a confirmar ({len(resumo['avisos'])}):")
        linhas.extend(f"    {a}" for a in resumo["avisos"])
    if resumo["problemas"]:
        linhas.append("  PROBLEMAS:")
        linhas.extend(f"    {p}" for p in resumo["problemas"])
    return "\n".join(linhas)


def add_arguments(p):
    """Argumentos partilhados pela CLI principal e pelo módulo."""
    p.add_argument("--registo", default=str(REGISTO_OMISSAO))
    p.add_argument("--destino", default=str(DESTINO_OMISSAO))
    p.add_argument("--siglas", action="append", default=[],
                   help="CSV de siglas fixadas ('nome;sigla', ou o "
                        "vocabularios/siglas_organizacoes.csv). Repetível: em "
                        "caso de conflito ganha o primeiro ficheiro indicado.")
    p.add_argument("--esquema", choices=ESQUEMAS, default="rnc",
                   help="esquema de nome: 'rnc' (obrigatório a partir do "
                        "corpus de 2026, ver ADR-0021) ou 'pipeline' (o de "
                        "2025, só para corpos anteriores)")
    p.add_argument("--ambitos", help="CSV 'nome;ambito' de empregadores com "
                                     "âmbito conhecido (só com --esquema rnc)")
    p.add_argument("--familias", default="convencao,extensao,aviso,adesao")
    p.add_argument("--aplicar", action="store_true",
                   help="escreve mesmo (por omissão só simula)")
    p.add_argument("--aceitar-heuristicas", action="store_true",
                   help="escreve mesmo os documentos com sigla derivada por "
                        "heurística, sem esperar por confirmação humana "
                        "(--siglas) — usar com critério")
    p.add_argument("--confirmar", action="append", default=[], metavar="CHAVE",
                   help="processa só este documento, confirmado por uma pessoa "
                        "(os avisos dele não o travam); repetível — é o que a "
                        "janela de confirmação da app usa")



def rename(args):

    registo = Registo.carregar(Path(args.registo))
    if not registo.entradas:
        raise ValueError(f"Registo vazio ({args.registo}) — correr primeiro "
                         "python -m crl_markdown collect")
    # Validar aqui, e não dentro de `carregar_siglas`, para que a função
    # continue a poder ser usada em testes com caminhos construídos. O
    # `siglas.csv` é conhecimento da equipa e não vem no repositório (PR #39):
    # a mensagem tem de dizer isso, porque um traceback não o diria.
    for caminho in args.siglas:
        caminho = Path(caminho)
        if not caminho.is_file():
            raise ValueError(
                f"PAROU AQUI: não encontrei o ficheiro de siglas '{caminho}'\n"
                "  → o siglas.csv é conhecimento da equipa e não vem no\n"
                "    repositório: copiar docs/operacao/siglas.exemplo.csv\n"
                "    para a raiz do projeto, editar, e repetir")
    tabela = tabela_de_siglas(args.siglas)
    voc_ambito = (mod_ambito.carregar_vocabulario(Path(args.ambitos))
                  if args.ambitos else mod_ambito.carregar_vocabulario())
    resumo = nomear(registo, Path(args.destino), aplicar=args.aplicar,
                    tabela=tabela or None,
                    familias=tuple(f.strip() for f in args.familias.split(",") if f.strip()),
                    aceitar_heuristicas=args.aceitar_heuristicas,
                    esquema=args.esquema, vocabulario_ambito=voc_ambito,
                    confirmados=set(args.confirmar) or None)
    print(texto_resumo(resumo, aplicar=args.aplicar))
    return 1 if resumo["problemas"] else 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Nomeação RNC dos PDFs recolhidos")
    add_arguments(p)
    return rename(p.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
