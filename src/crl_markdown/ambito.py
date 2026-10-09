"""Âmbito de um IRCT: PRI (privado), SPE (público empresarial), APU (Administração Pública).

Porque existe. A aplicação sabe processar convenções do sector privado e do
sector público empresarial. Não sabe ainda processar as da Administração
Pública — os ACT e ACEP celebrados ao abrigo da LTFP, que são depositados na
DGAEP e não na DGERT. Enquanto assim for, é preciso separar à entrada o que
entra no pipeline do que fica apenas recolhido e catalogado.

O número sequencial do BTE não serve para isso: é uma série única que atravessa
tudo. Daí um campo próprio, com vocabulário fechado de três valores.

Três letras e não duas, deliberadamente: o «PU» usado no ciclo de 2025
significava «público empresarial» mas lia-se como «público». `SPE` e `APU` não
se confundem.

Como se decide, por ordem de fiabilidade:

1. **Vocabulário** — `vocabularios/empregadores_ambito.csv`, lista editável de
   empregadores com âmbito conhecido. Tem prioridade sobre tudo o resto.
2. **Lista do INE** — `vocabularios/entidades_administracao_publica.csv`, as
   entidades do sector institucional S.13. Ver o aviso abaixo: dá um sinal, não
   uma decisão.
3. **Regra** — o tipo `ACEP` é sempre APU; a forma jurídica («, EPE», «, EM»,
   «Empresa Municipal») indica SPE; município, câmara, freguesia, universidade,
   politécnico ou direção-geral indicam APU.
4. **Omissão** — PRI, marcado como não verificado.

**Sobre a lista do INE.** Responde a uma pergunta que não é esta. O INE
classifica por contas nacionais (SEC 2010): uma entidade está em S.13 se for
produtor não mercantil. O RNC classifica por regime laboral: APU são as
entidades cujos trabalhadores estão sob a LTFP e cujos IRCT vão para a DGAEP.
Os critérios divergem nos dois sentidos — o Metropolitano de Lisboa, E.P.E.
está em S.13 mas é SPE para o RNC; a CP e a Carris não estão em S.13 e são SPE
na mesma. Por isso uma entrada da lista com forma jurídica empresarial propõe
**SPE**, nunca APU, e qualquer proposta vinda da lista sai marcada para revisão.

Tudo o que a *regra* classifique como SPE ou APU sai com aviso e fica por rever.
O módulo nunca decide um APU em silêncio: um falso APU retira um documento do
pipeline sem ninguém dar por isso.

Ver docs/rnc/README.md §5.2 e ADR-0016 do crl-app-cct, de onde este módulo foi
portado (commit 5fd8ae8).
"""
import csv
import re
from functools import lru_cache
from pathlib import Path

from .recolha import sem_acentos as _sem_acentos

VALORES = ("PRI", "SPE", "APU")
OMISSAO = "PRI"

_VOCABULARIOS = Path(__file__).resolve().parent / "vocabularios"
VOCABULARIO_OMISSAO = _VOCABULARIOS / "empregadores_ambito.csv"
ENTIDADES_PUBLICAS_OMISSAO = _VOCABULARIOS / "entidades_administracao_publica.csv"

# O sinal que a lista do INE dá → o âmbito que propõe para o RNC.
SINAL_PARA_AMBITO = {"APU": "APU", "SPE_PROVAVEL": "SPE"}

# Formas jurídicas que identificam uma entidade do sector público empresarial.
# Comparadas sobre o nome normalizado (sem acentos, minúsculas), com fronteira
# de palavra à esquerda para não apanhar «, EM» dentro de «ARMAZÉM».
RE_SPE = re.compile(
    r"(?:,\s*e\.?\s*p\.?\s*e\.?\b"          # , EPE  /  , E.P.E.
    r"|,\s*e\.?\s*m\.?\b"                   # , EM   /  , E.M.
    r"|,\s*e\.?\s*i\.?\s*m\.?\b"            # , EIM
    r"|,\s*s\.?\s*p\.?\s*a\.?\b"            # , SPA (sector público administrativo local)
    r"|\bempresa\s+municipal\b"
    r"|\bempresa\s+intermunicipal\b"
    r"|\bempresa\s+metropolitana\b"
    r"|\bservicos?\s+municipaliz\w*\b)")

# Entidades da Administração Pública em sentido estrito.
RE_APU = re.compile(
    r"(?:\bmunicipio\b|\bcamara\s+municipal\b|\bjunta\s+de\s+freguesia\b"
    # «Freguesia de», «da», «do», «das», «dos» e «União das Freguesias de»: só
    # «de» deixava a «Freguesia da Barrosa» em PRI, sem aviso.
    r"|\bfreguesias?\s+d[aeo]s?\b|\buniao\s+(?:das\s+)?freguesias\b"
    r"|\bcomunidade\s+intermunicipal\b"
    r"|\buniversidade\b|\binstituto\s+politecnico\b|\bpolitecnico\b"
    r"|\bdirecao[- ]geral\b|\bsecretaria[- ]geral\b"
    r"|\badministracao\s+regional\b|\bgoverno\s+regional\b"
    r"|\binstituto\s+publico\b)")

TIPOS_APU = ("ACEP",)   # acordo coletivo de empregador público (LTFP)


def _normalizar(nome: str) -> str:
    return re.sub(r"\s+", " ", _sem_acentos(nome or "").lower()).strip()


def _colapsar(nome: str) -> str:
    """Só letras e algarismos: «E. P. E.» e «EPE» passam a ser o mesmo."""
    return re.sub(r"[^a-z0-9]", "", _normalizar(nome))


RE_SIGLA_A_CABECA = re.compile(r"^[a-z0-9.]{2,12}\s*[-–—]\s*(?P<resto>.+)$")


def _chaves(chave: str) -> list[str]:
    """Formas de uma entrada do vocabulário para comparar com o índice.

    O nome completo, sem pontuação nem espaços, e, quando começa por uma sigla
    («STCP - Sociedade de Transportes…»), também o nome sem ela: o índice
    escreve muitas vezes a sigla no fim, entre parênteses, ou não a escreve.
    """
    formas = [_colapsar(chave)]
    m = RE_SIGLA_A_CABECA.match(_normalizar(chave))
    if m and len(_colapsar(m.group("resto"))) >= 12:
        formas.append(_colapsar(m.group("resto")))
    return [f for f in formas if f]


def carregar_vocabulario(caminho: Path | None = None) -> dict[str, str]:
    """Lê `empregadores_ambito.csv` → {nome normalizado: âmbito}.

    Formato: `nome;ambito;fonte;data;responsavel`, separador `;`, UTF-8.
    Linhas com âmbito fora do vocabulário fechado são ignoradas com aviso — é
    preferível cair na regra do que classificar por um valor que ninguém definiu.
    """
    caminho = Path(caminho) if caminho else VOCABULARIO_OMISSAO
    tabela: dict[str, str] = {}
    if not caminho.exists():
        return tabela
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        for linha in csv.reader(f, delimiter=";"):
            if len(linha) < 2 or not linha[0].strip():
                continue
            nome = _normalizar(linha[0])
            if nome in ("nome", "empregador", "denominacao"):
                continue            # cabeçalho
            valor = linha[1].strip().upper()
            if valor not in VALORES:
                print(f"AVISO — âmbito desconhecido em {caminho.name}: "
                      f"{linha[0]!r} → {valor!r} (ignorado)")
                continue
            tabela[nome] = valor
    return tabela


def classificar(empregador: str, tipo: str = "",
                vocabulario: dict[str, str] | None = None
                ) -> tuple[str, str, str | None]:
    """Devolve `(ambito, origem, aviso)`.

    `origem` é `vocabulario`, `regra` ou `omissao`. `aviso` vem preenchido
    sempre que a decisão precisa de confirmação humana — ou seja, sempre que o
    resultado não vem do vocabulário e não é o PRI por omissão.
    """
    tipo_norm = re.sub(r"[^A-Z]", "", (tipo or "").upper())
    nome = _normalizar(empregador)

    if vocabulario:
        if nome in vocabulario:
            return vocabulario[nome], "vocabulario", None
        colapsado = _colapsar(empregador)
        for chave, valor in vocabulario.items():
            for forma in _chaves(chave):
                if forma == colapsado or (len(forma) >= 6 and forma in colapsado):
                    return valor, "vocabulario", None

    if tipo_norm.startswith(TIPOS_APU):
        return "APU", "regra", f"tipo {tipo} → APU por regra — confirmar"
    if RE_APU.search(nome):
        return "APU", "regra", (f"«{empregador[:60]}» classificado APU por regra "
                                "— confirmar antes de excluir do pipeline")
    if RE_SPE.search(nome):
        return "SPE", "regra", (f"«{empregador[:60]}» classificado SPE por regra "
                                "— confirmar")
    return OMISSAO, "omissao", None


@lru_cache(maxsize=1)
def vocabulario_por_omissao() -> dict[str, str]:
    """O `empregadores_ambito.csv` incluído no pacote, lido uma vez por processo.

    É o que a nomeação usa quando não lhe passam outro vocabulário: sem ele, um
    empregador conhecido como a EPAL cai em PRI por omissão, sem aviso, e o nome
    atribuído, que não muda, fica com o âmbito errado.
    """
    return carregar_vocabulario()


def processavel(ambito: str) -> bool:
    """O pipeline lê PRI e SPE. APU recolhe-se e cataloga-se; não se processa."""
    return (ambito or OMISSAO).upper() in ("PRI", "SPE")


def carregar_entidades_publicas(caminho: Path | None = None
                                ) -> dict[str, tuple[str, str]]:
    """Lê a lista do INE → `{nome normalizado: (âmbito proposto, subsector)}`.

    Só entram entradas com nome suficientemente longo para não encaixarem por
    acaso dentro de outro nome: a lista tem 4 241 entidades, e uma chave curta
    encaixa em meio registo e classifica mal em silêncio — que é o oposto do
    que esta lista existe para fazer.
    """
    caminho = Path(caminho) if caminho else ENTIDADES_PUBLICAS_OMISSAO
    tabela: dict[str, tuple[str, str]] = {}
    if not caminho.exists():
        return tabela
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f, delimiter=";"):
            nome = _normalizar(linha.get("nome", ""))
            amb = SINAL_PARA_AMBITO.get((linha.get("sinal") or "").strip().upper())
            if len(nome) >= 10 and amb:
                tabela.setdefault(nome, (amb, linha.get("subsetor", "")))
    return tabela


@lru_cache(maxsize=1)
def entidades_publicas_por_omissao() -> dict[str, tuple[str, str]]:
    """A lista do INE versionada no repositório, lida uma vez por processo.

    Carregada à cabeça (em vez de no `import`) para que quem não usa o esquema
    RNC não pague 4 241 linhas de leitura, e para que os testes possam passar a
    sua própria tabela sem tocar nesta.
    """
    return carregar_entidades_publicas()


def classificar_com_ine(empregador: str, tipo: str = "",
                        vocabulario: dict[str, str] | None = None,
                        entidades_publicas: dict[str, tuple[str, str]] | None = None
                        ) -> tuple[str, str, str | None]:
    """Como `classificar()`, mas consultando também a lista do INE.

    A ordem é a da fiabilidade: o vocabulário da equipa primeiro, a lista do INE
    a seguir, a regra por último. A lista **nunca decide em silêncio** — mesmo
    quando acerta, sai com aviso, porque o critério dela não é o do RNC.
    """
    if vocabulario:
        amb, origem, aviso = classificar(empregador, tipo, vocabulario)
        if origem == "vocabulario":
            return amb, origem, aviso

    if entidades_publicas is None:
        entidades_publicas = entidades_publicas_por_omissao()
    if entidades_publicas:
        nome = _normalizar(empregador)
        chave = max((k for k in entidades_publicas if k in nome),
                    key=len, default=None)
        if chave:
            amb, subsetor = entidades_publicas[chave]
            return amb, "ine", (
                f"«{empregador[:50]}» consta da lista do INE ({subsetor}) — "
                f"proposto {amb}; o critério do INE é de contas nacionais, não "
                "de regime laboral, pelo que tem de ser confirmado")
    return classificar(empregador, tipo, vocabulario)
