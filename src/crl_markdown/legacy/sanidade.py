"""Controlos de sanidade da extração — canários de defeitos estruturais.

Não substituem a revisão humana: apanham as falhas que se detetam sem
conhecer o conteúdo, e que na prática denunciam problemas de ordem de
leitura ou de perda de texto. Os avisos vão para o relatório da corrida.

Os dois controlos nasceram da revisão MaxQDA de 2026-08-25, onde ambos
os sintomas apareceram: uma cláusula ficou sem conteúdo (o texto tinha
sido colocado antes do próprio cabeçalho) e dois documentos tinham
matéria depois da nota de depósito legal.
"""
import re

# nota de depósito do art. 494.º CT: fecha SEMPRE uma convenção publicada
# ("Depositado em 23 de janeiro…", "Depositado a 17 de julho…"). Pode vir
# colada à assinatura na mesma linha ("…Rosa Depositado a 7 de agosto…"),
# porque o extrator une a assinatura e a nota que o PDF traz seguidas.
RE_DEPOSITO = re.compile(r"^Depositad[oa]\s+(?:em|a)\s+\d", re.IGNORECASE)
RE_DEPOSITO_MID = re.compile(
    r"^.*\bDepositad[oa]\s+(?:em|a)\s+\d", re.IGNORECASE)
# retificações: publicam a correção de outra convenção e referem-se ao
# depósito desta — não têm nota de depósito própria (AE-ALT-RECT no
# registo; confirmação do utilizador na importação MaxQDA de 2026-09-17)
RE_RETIFICACAO = re.compile(
    r"\bRECT\b|[-–]RECT$|retifica", re.IGNORECASE)
# "( Revogado. )" fecha a frase tanto como "Revogado." — o fecho pode
# vir separado por espaços. Um ordinal abreviado também fecha: a redação
# não põe outro ponto depois de «34.ª» ou «4.º» («… a que se referem as
# cláusulas 34.ª a 36.ª»). Na corrida de 2025 eram 80 dos 134 corpos «sem
# frase terminada em ponto».
RE_FRASE_FECHADA = re.compile(r"(?:[.!?]|\d\.?\s?[ªº])[\s)\]»”\"']*$")
_TIPOS_COM_CORPO = ("clausula", "artigo")
# Um artigo de alteração apresenta as cláusulas que se seguem: «As cláusulas
# 5.ª e 7.ª passam a ter a redação seguinte:». Termina em dois pontos porque
# o texto que anuncia vem nos nós seguintes, e não por estar truncado.
RE_ANUNCIO = re.compile(
    r"(reda[çc][ãa]o|termos seguintes|forma seguinte|seguinte teor"
    r"|aditad[oa]s?|republicad[oa]s?)\b[^:]*:$", re.IGNORECASE)


def clausulas_sem_corpo(doc: dict, texto: str,
                        referencia: list[str] | None = None) -> list[str]:
    """Cláusulas e artigos cujo corpo não tem uma única frase terminada.

    Um cabeçalho seguido logo de outro cabeçalho é o sintoma clássico de
    conteúdo deslocado; um corpo sem qualquer ponto final é quase sempre
    texto truncado. A exceção é o artigo que anuncia as cláusulas seguintes
    («passam a ter a redação seguinte:») e é seguido por elas (issue #83). Uma
    enumeração que acaba em dois pontos sem nada a seguir continua a contar:
    é o caso típico das alíneas perdidas.

    `referencia` são as palavras do PDF, sem o mobiliário, pela ordem da
    leitura independente (`Medida.palavras_referencia`). Um corpo que acaba em
    dois pontos e é seguido por um cabeçalho está como foi publicado quando o
    PDF também passa das últimas palavras do corpo diretamente às primeiras do
    cabeçalho: a família SETAAB de 2025 fecha a «Parentalidade» em
    «nomeadamente:» e passa à cláusula seguinte. A prova é local: se o PDF
    tem alguma coisa entre os dois (as alíneas que se perderam), o aviso
    fica, seja qual for a cobertura do documento (revisão do PR #92).
    """
    comecos = {no["char_start"]: no for no in doc.get("nos", [])}
    falhas = []
    for no in doc.get("nos", []):
        if no.get("tipo") not in _TIPOS_COM_CORPO or not no.get("folha", True):
            continue
        bruto = texto[no["char_start"]:no["char_end"]]
        # a primeira linha é o próprio rótulo
        corpo = "\n".join(bruto.split("\n")[1:]).strip()
        if not corpo:
            falhas.append(f"{no['rotulo']}: sem conteúdo")
        elif not any(RE_FRASE_FECHADA.search(l) for l in corpo.split("\n") if l.strip()):
            if (_anuncia_o_que_segue(no, corpo, comecos) or _corpo_sem_frases(bruto)
                    or _dois_pontos_como_no_pdf(no, corpo, comecos, referencia)):
                continue
            falhas.append(f"{no['rotulo']}: corpo sem frase terminada em ponto")
    return falhas


# um corpo que não se escreve em frases: uma tabela, uma fórmula, ou o texto
# omitido de propósito numa alteração («(…)»). Na corrida de 2025, «Cálculo
# da remuneração» (RH = …), «Mapas de horário» e «Cláusula transitória (…)»
# davam o aviso de corpo sem frase terminada em ponto.
RE_SEM_FRASES = re.compile(r" \| |\(\s*(?:\.\s*){3}\)|\(\s*…\s*\)|\[\s*(?:\.\s*){3}\]|[=×]")


def _corpo_sem_frases(bruto: str) -> bool:
    return bool(RE_SEM_FRASES.search(bruto))


_TIPOS_CABECALHO = ("clausula", "artigo", "anexo", "capitulo", "seccao")


# palavras do fim do corpo e do início do cabeçalho que têm de estar seguidas
# no PDF
PALAVRAS_DO_FIM = 6
PALAVRAS_DO_CABECALHO = 3


def _dois_pontos_como_no_pdf(no: dict, corpo: str, comecos: dict,
                             referencia: list[str] | None) -> bool:
    """O corpo acaba em dois pontos e, no PDF, o cabeçalho seguinte vem logo a seguir."""
    from .completude import palavras

    seguinte = comecos.get(no["char_end"])
    if (not referencia or not corpo.rstrip().endswith(":") or seguinte is None
            or seguinte.get("tipo") not in _TIPOS_CABECALHO):
        return False
    fim = palavras(corpo)[-PALAVRAS_DO_FIM:]
    cabeca = palavras(seguinte.get("rotulo", ""))[:PALAVRAS_DO_CABECALHO]
    if not fim or not cabeca:
        return False
    esperado = fim + cabeca
    n = len(esperado)
    return any(referencia[i:i + n] == esperado
               for i in range(len(referencia) - n + 1) if referencia[i] == esperado[0])


def _anuncia_o_que_segue(no: dict, corpo: str, comecos: dict) -> bool:
    """Artigo que anuncia cláusulas e é seguido, logo a seguir, por uma."""
    seguinte = comecos.get(no["char_end"])
    return (no.get("tipo") == "artigo"
            and seguinte is not None and seguinte.get("tipo") == "clausula"
            and bool(RE_ANUNCIO.search(corpo.split("\n")[-1].strip())))


def deposito_no_fim(texto: str, e_retificacao: bool = False) -> str | None:
    """Verifica que a nota de depósito legal fecha o documento.

    Retificações (confirmação de 2026-09-17): não têm nota de depósito
    própria — referem-se ao depósito da convenção que retificam. O
    subtipo AE-ALT-RECT (ou equivalente) desliga o controlo.
    """
    linhas = [l.strip() for l in texto.split("\n") if l.strip()]
    if not linhas:
        return "documento vazio"
    if e_retificacao:
        return None
    # a nota pode vir colada à assinatura ("Rosa Depositado a 7…")
    posicao = next((i for i, l in enumerate(linhas)
                     if RE_DEPOSITO.match(l) or RE_DEPOSITO_MID.match(l)), None)
    if posicao is None:
        return "sem nota de depósito (art. 494.º CT) — documento truncado?"
    # a nota pode continuar na linha seguinte, quando o PDF a parte num
    # sítio que a junção de linhas não une; conta até fechar a frase
    fim = posicao
    while (fim + 1 < len(linhas) and fim - posicao < 2
           and not RE_FRASE_FECHADA.search(linhas[fim])):
        fim += 1
    depois = linhas[fim + 1:]
    if depois:
        # a linha diz o que é: uma tabela que ficou para o fim, o título do
        # documento seguinte, uma assinatura (corrida de 2025: 74 avisos que
        # não diziam qual era a linha)
        primeira = depois[0] if len(depois[0]) <= 80 else depois[0][:77] + "…"
        return (f"{len(depois)} linha(s) depois da nota de depósito "
                f"— ordem de leitura suspeita (a primeira: «{primeira}»)")
    return None


AVISO_RETIFICACAO_SEM_ARTICULADO = (
    "retificação sem articulado próprio: zero cláusulas é o esperado")
AVISO_SEM_ESTRUTURA = (
    "nenhuma cláusula ou artigo reconhecido: estrutura não reconhecida pelo "
    "extrator, ou documento sem articulado — verificar o PDF")
AVISO_ALTERACAO_SALARIAL_SEM_ARTICULADO = (
    "alteração salarial sem articulado: o texto tem só números e tabelas, sem "
    "nenhuma linha com a forma de cláusula ou artigo — zero cláusulas é o esperado")


# O título do BTE fecha com o subtipo depois de um travessão: «Acordo de
# empresa entre a CARRISTUR … e a ASPTC - Retificação». Procura-se só no
# bloco do título, antes do primeiro cabeçalho estrutural, para que uma
# menção a «retificação» no corpo de uma convenção não conte.
RE_TITULO_RETIFICACAO = re.compile(r"\s[-–—]\s*re(?:c)?tifica[çc][ãa]o\b", re.IGNORECASE)
RE_TITULO_ALTERACAO_SALARIAL = re.compile(r"\s[-–—]\s*altera[çc][ãa]o\s+salarial\b",
                                          re.IGNORECASE)
# uma linha que começa como um cabeçalho de cláusula ou artigo, e que o
# extrator não reconheceu (fora das tabelas, onde «Cláusula | Designação» é
# o cabeçalho das tabelas de valores)
RE_FORMA_DE_CABECALHO = re.compile(r"^(?:Cl[aá]usula|CL[AÁ]USULA|Artigo|ARTIGO)\s")
RE_CABECALHO_ESTRUTURAL = re.compile(
    r"^(?:Cl[aá]usula|CL[AÁ]USULA|Artigo|ARTIGO|CAP[IÍ]TULO|T[IÍ]TULO)\b")
MAX_LINHAS_TITULO = 8


def _linhas_do_titulo(texto: str) -> list[str]:
    linhas: list[str] = []
    for linha in texto.split("\n"):
        linha = linha.strip()
        if not linha:
            continue
        if RE_CABECALHO_ESTRUTURAL.match(linha) or len(linhas) >= MAX_LINHAS_TITULO:
            break
        linhas.append(linha)
    return linhas


def titulo_de_retificacao(texto: str) -> bool:
    """O título do documento diz «- Retificação»?"""
    return any(RE_TITULO_RETIFICACAO.search(l) for l in _linhas_do_titulo(texto))


def alteracao_salarial_sem_articulado(texto: str) -> bool:
    """Uma alteração salarial que não tem nenhuma linha com forma de cabeçalho.

    DHL de 2025: o título diz «- Alteração salarial e outras» e o texto são
    números e uma tabela. Sem nenhuma linha que comece por «Cláusula» ou
    «Artigo» fora das tabelas, não há cabeçalho que o extrator tenha deixado
    escapar.
    """
    return (any(RE_TITULO_ALTERACAO_SALARIAL.search(l) for l in _linhas_do_titulo(texto))
            and not any(RE_FORMA_DE_CABECALHO.match(l) and " | " not in l
                        for l in texto.split("\n")))


def e_retificacao(doc: dict, texto: str = "") -> bool:
    """Pelo subtipo do schema, pelo tipo IRCT (AE-ALT-RECT etc., que o
    pipeline põe no doc como 'tipo_registo') ou pelo título do documento.

    O título é o que não depende do nome do ficheiro nem do registo da
    recolha: um corpus nomeado no esquema de 2025 (`26_PR_011_…`) não traz o
    tipo no nome, e a retificação tem de ser reconhecida na mesma (revisão do
    PR #88).
    """
    return bool(RE_RETIFICACAO.search(doc.get("subtipo", ""))
                or RE_RETIFICACAO.search(doc.get("tipo_registo", ""))
                or titulo_de_retificacao(texto))


def sem_articulado(doc: dict, texto: str = "") -> str | None:
    """Zero cláusulas nunca fica ambíguo (ISSUE-0014, issue #64).

    Numa retificação é o resultado certo: a retificação corrige outra
    convenção e não tem articulado próprio. Noutro documento pode ser um
    defeito do extrator ou um documento sem articulado, e diz-se isso, sem
    sugerir truncagem.
    """
    if any(no.get("tipo") in _TIPOS_COM_CORPO for no in doc.get("nos", [])):
        return None
    if e_retificacao(doc, texto):
        return AVISO_RETIFICACAO_SEM_ARTICULADO
    if alteracao_salarial_sem_articulado(texto):
        return AVISO_ALTERACAO_SALARIAL_SEM_ARTICULADO
    return AVISO_SEM_ESTRUTURA


def verificar(doc: dict, texto: str, referencia: list[str] | None = None,
              paginas_imagem: list[int] | None = None) -> list[str]:
    """Todos os controlos; devolve a lista de avisos (vazia = tudo bem).

    `referencia`: as palavras do PDF pela leitura independente da completude
    (ver `clausulas_sem_corpo`). `paginas_imagem`: as páginas do PDF com uma
    imagem grande (ver `auditoria.tabelas_esperadas`).
    """
    from .auditoria import tabelas_esperadas

    avisos = []
    aviso = sem_articulado(doc, texto)
    if aviso:
        avisos.append(aviso)
    aviso = deposito_no_fim(texto, e_retificacao=e_retificacao(doc, texto))
    if aviso:
        avisos.append(aviso)
    vazias = clausulas_sem_corpo(doc, texto, referencia)
    if vazias:
        avisos.append(f"{len(vazias)} cláusula(s)/artigo(s) sem corpo válido: "
                      + "; ".join(vazias[:5])
                      + (" …" if len(vazias) > 5 else ""))
    sem_tabela = tabelas_esperadas(doc, texto, paginas_imagem)
    if sem_tabela:
        avisos.extend(sem_tabela[:5]
                      + (["…"] if len(sem_tabela) > 5 else []))
    return avisos
