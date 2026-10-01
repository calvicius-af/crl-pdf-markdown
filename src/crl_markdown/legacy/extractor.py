"""Extrator Fase 1: PDF do BTE → doc.json + texto plano.

Evolui o preprocessador V2 com as correções pedidas no gate da Fase 0:
- junção de linhas que não pára em maiúsculas (só pontuação forte ou
  marcadores estruturais justificam manter a quebra);
- rótulo de cláusula/capítulo fundido com o título numa só linha;
- hierarquia capítulo/secção/cláusula/anexo/artigo com nós-pai.

O texto final é uma sequência de "folhas" contíguas (preâmbulo, cabeçalhos
de capítulo/secção/anexo, cláusulas, artigos) cuja concatenação reconstrói
o texto na íntegra (propriedade zero-perda).
"""
import re
from collections import Counter
from pathlib import Path

from .mobiliario import RE_RODAPE_PARTIDO, e_mobiliario, sem_prefixo_de_cabecalho

RE_CAPITULO = re.compile(r"^(?:CAP[IÍ]TULO|T[IÍ]TULO)\s+([IVXLCD]+|\d+)\b(.*)$")
# «SECÇÃO» ou «Secção», nunca em minúsculas: uma remissão partida pelo PDF
# («… o previsto na subsecção XI da\nsecção II do capítulo II do Código do
# Trabalho.») abria uma secção falsa e deixava a cláusula a meio (FNOP de 2025)
RE_SECCAO = re.compile(r"^(?:SEC[ÇC][AÃ]O|Sec[çc][ãa]o)\s+([IVXLCD]+|\d+)\b(.*)$")
# «ANEXO III», «ANEXO 2», e com letra: «ANEXO A» (NAV), «ANEXO II-A» (Autoridade
# de Seguros de 2025). A letra é uma só, seguida de fim de palavra: «ANEXO
# Tabela…» não tem número.
RE_ANEXO = re.compile(
    r"^ANEXO\s+((?:[IVXLCD]+|\d+)(?:\s*-\s*[A-Z](?![\wÀ-ÿ]))?|[A-Z](?![\wÀ-ÿ]))?\b(.*)$")
# numeração por extenso: só designadores a sério. Qualquer palavra servia
# antes, o que transformava o título do CAPÍTULO XV do AguasNorte
# ("Cláusula geral e transitória") numa cláusula vazia — mas restringir só
# a ordinais deixava cair "Artigo único"/"Cláusula única", que é redação
# corrente quando o instrumento tem um só artigo (EMARP 2025, anexo I)
_ORDINAL = (r"(?:primeir|segund|terceir|quart|quint|sext|s[eé]tim|oitav|non"
            r"|d[eé]cim|vig[eé]sim|trig[eé]sim|quadrag[eé]sim|quinquag[eé]sim"
            r"|sexag[eé]sim|sept?uag[eé]sim|octog[eé]sim|nonag[eé]sim"
            r"|cent[eé]sim)[oa]")
_UNICO = r"[úu]nic[oa]"
# designadores de posição, em vez de número: nas revisões parciais o BTE abre
# com "Cláusula prévia Âmbito de revisão", que fixa o que a revisão altera.
# Lista fechada, pela mesma razão que levou a restringir os ordinais: com
# "qualquer palavra" a seguir, o título do CAPÍTULO XV do AguasNorte
# ("Cláusula geral e transitória") voltava a virar uma cláusula vazia.
# O guarda final exige fim de linha ou uma maiúscula a seguir (o título da
# cláusula): sem ele, "previa" sem acento é a forma verbal de "prever" e uma
# linha de prosa passaria a cabeçalho. O (?-i:…) é preciso porque o grupo da
# numeração é aplicado dentro de (?i:…), que tornaria [A-ZÀ-Ú] inútil
# «Cláusula de revisão» (EMPORDEF de 2025) é da mesma família: a cláusula de
# uma revisão parcial nomeada pela função, sozinha na linha
_DESIGNADOR = r"(?:pr[ée]vi[oa]|preliminar|de\s+revis[ãa]o)(?=\s*$|\s+(?-i:[A-ZÀ-Ú«(]))"
# numeração em romanos, só ou com o número dentro do capítulo: a EPAL numera
# as cláusulas por capítulo («Cláusula VII-8 Ajudas de custo»). Os romanos são
# maiúsculos e acabam a palavra, para que «Cláusula civil» não passe.
_ROMANO = r"(?-i:[IVXLC]+)(?:-\d+)?(?![\wÀ-ÿ])"
# "12.ª", "16.ª-A", "décima segunda", "único", "prévia", "VII-8"
_NUMERACAO = (rf"\d+\.?[ªº]?(?:-[A-Z])?|{_UNICO}|{_DESIGNADOR}|{_ROMANO}"
              rf"|{_ORDINAL}(?:\s+{_ORDINAL})?")
# a palavra-chave tem de vir capitalizada: no BTE os cabeçalhos são
# "Cláusula 1.ª" ou "CLÁUSULA 1.ª", nunca minúsculos. Com IGNORECASE, uma
# remissão partida pelo PDF ("… nos termos do\nartigo 253.º do Código do
# Trabalho…") virava um nó falso que roubava o corpo à cláusula real —
# 4 casos nos 6 documentos de 2025, um deles com 3746 caracteres.
# A numeração continua indiferente a maiúsculas (grupo com (?i:…)).
RE_CLAUSULA = re.compile(
    rf"^(?:Cl[aá]usula|CL[AÁ]USULA)\s+((?i:{_NUMERACAO}))\s*(.*)$")
# um cabeçalho só com o designador, sem número nem título: «Artigo de
# revisão». Logo a seguir a «Artigo 1.º», é o título dele (AEVP e APHP de
# 2025), e não outro artigo
RE_SO_DESIGNADOR = re.compile(
    rf"^(?:Cl[aá]usula|CL[AÁ]USULA|Artigo|ARTIGO)\s+(?i:{_DESIGNADOR})\s*$")
RE_ARTIGO = re.compile(
    rf"^(?:Artigo|ARTIGO)\s+((?i:{_NUMERACAO}))\s*(.*)$")

_RE_HEADINGS = [
    ("capitulo", RE_CAPITULO),
    ("seccao", RE_SECCAO),
    ("anexo", RE_ANEXO),
    ("clausula", RE_CLAUSULA),
    ("artigo", RE_ARTIGO),
]

# marcadores que justificam manter a quebra de linha antes deles
_MARCADOR_LISTA = r"\d+\s*[-–—.)]|[a-z]\)|[ivxl]+\)|[-–—•§]\s?"
# "Declaração" (ISSUE-0015, ponto 3): quando uma parte assina em representação
# de outras, o PDF traz uma declaração própria a identificá-las — sem isto,
# cola-se ao nome do signatário anterior, como se fosse o mesmo bloco
# Com maiúscula, como os cabeçalhos: em minúsculas, é uma remissão que o PDF
# partiu («… o previsto na subsecção XI da\nsecção II do capítulo II do Código
# do Trabalho.», FNOP de 2025), e a linha junta-se à anterior.
_MARCADOR_ESTRUTURAL = (r"(?-i:Cl[aá]usula\s|CL[AÁ]USULA\s|Artigo\s|ARTIGO\s"
                        r"|CAP[IÍ]TULO\s|Cap[ií]tulo\s|SEC[ÇC][AÃ]O\s|Sec[çc][ãa]o\s"
                        r"|ANEXO\b|Anexo\b|NOTA\b|Nota\b|DECLARA[ÇC][ÃA]O\b|Declara[çc][ãa]o\b)")
RE_MARCADOR = re.compile(
    rf"^(?:{_MARCADOR_LISTA}|{_MARCADOR_ESTRUTURAL})", re.IGNORECASE)
# só os de lista: uma linha que comece por "Cláusula" mas não seja um
# cabeçalho a sério ainda pode ser o título do cabeçalho anterior
RE_MARCADOR_LISTA = re.compile(rf"^(?:{_MARCADOR_LISTA})", re.IGNORECASE)
# pontuação forte, tolerando o fecho de parêntesis/aspas que a segue:
# "(Valores em euros.)" termina a frase tanto como "Valores em euros."
RE_PONTUACAO_FORTE = re.compile(r"""[.!?:;][)\]»”"']*\s*$""")
# ordinal separado do número pelo PDF: "Artigo 1. º", "12. º ano"
RE_ORDINAL_SEPARADO = re.compile(r"(\d)\s*\.\s+([ºª])")
# número de parágrafo que perdeu o separador: "3São considerados…" (o PDF
# tem "3- São"); exige maiúscula a seguir para não tocar em "12.º" ou "2025".
# A maiúscula sozinha basta — não se exige uma minúscula a seguir a ela, para
# apanhar também siglas/palavras de uma letra coladas ao número (ISSUE-0016,
# ponto 7: "3A EMEM deve…", em que "A" fica isolado antes do espaço)
RE_NUMERO_SEM_SEPARADOR = re.compile(r"(?m)^(\d+(?:\.\d+)?)(?=[A-ZÀ-Ú])")
# fim do bloco de título de uma convenção: o BTE fecha-o sempre com o
# subtipo oficial, e o que vier a seguir já é o corpo do documento
RE_FIM_TITULO_CONVENCAO = re.compile(
    r"(?:revis[ãa]o\s+(?:global|parcial)"
    r"|altera[çc][ãa]o\s+salarial(?:\s+e\s+outras?)?"
    # «- Alteração» sozinho (CARRIS, APDL, EMAS Beja, VIMAGUA de 2025), só
    # com o travessão antes: uma frase que acabe em «alteração» não conta
    r"|[-–—]\s*altera[çc][ãa]o"
    r"|(?:e\s+)?texto\s+consolidado"
    r"|acordo\s+de\s+ades[ãa]o"
    r"|1\.?[ªa]\s+conven[çc][ãa]o)\s*$", re.IGNORECASE)
# o bloco de título vive no cabeçalho do documento; a regra acima só lá
# se aplica, para não partir frases do corpo que acabem nas mesmas palavras
LINHAS_DO_CABECALHO = 20
RE_TRAVESSAO_INICIAL = re.compile(r"^\s*[-–—]\s*\S")
# uma linha só com um numeral romano é o número de um capítulo sem a palavra
# CAPÍTULO («… - STMO» / «I» / «Área, âmbito, vigência…», ULSAS de 2025): não se
# cola à linha anterior
RE_SO_ROMANO = re.compile(r"^\s*[IVXLC]{1,5}\s*$")
RE_PONTUACAO_FINAL = re.compile(r"[.:;,!?][)\]»”\"']*\s*$")
# continuação de enumeração de alíneas partida pelo PDF: "b) e c) do número…"
# (minúscula ou conjunção após o parêntesis — uma alínea real começa por maiúscula)
RE_ALINEA_CONTINUACAO = re.compile(r"^[a-z]\)\s+(?:e\b|ou\b|[a-zà-ú])")
RE_ASSINATURA = re.compile(r"^(Pel[ao]s?\s|Depositado em\b|Pel['´]\s?)", re.IGNORECASE)
# data de outorga por extenso: "Lisboa, 12 de maio de 2025."
RE_DATA_OUTORGA = re.compile(
    r"^[A-ZÀ-Ú][\wà-ÿ\s]*,\s+\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}\s*\.?\s*$")
RE_MARCA_CONSOLIDADO = re.compile(r"^Texto consolidado\b")
RE_PREAMBULO_LINHA = re.compile(r"^Pre[âa]mbulo\s*$", re.IGNORECASE)

# sentinelas internas que delimitam tabelas durante a normalização
MARCA_TABELA_INI = "\x02TABELA"
MARCA_TABELA_FIM = "\x03TABELA"
# Fronteira entre as duas colunas de uma página. Só existe entre a extração da
# página e a remoção do mobiliário, que a usa para saber onde começa e acaba
# cada coluna, e a retira. Nunca chega ao texto final.
MARCA_COLUNA = "\x04COLUNA"


def _e_cabecalho(linha: str) -> bool:
    return (any(rx.match(linha) for _, rx in _RE_HEADINGS)
            or bool(RE_PREAMBULO_LINHA.match(linha)))


def juntar_linhas(texto: str) -> str:
    """Une quebras de linha a meio de frase.

    Mantém a quebra apenas quando a linha atual termina em pontuação forte,
    a linha atual ou a seguinte é um cabeçalho estrutural, ou a seguinte
    começa com marcador de lista/número. Ao contrário do V2, uma maiúscula
    no início da linha seguinte NÃO impede a junção (feedback do gate F0).
    """
    linhas = texto.split("\n")
    resultado: list[str] = []
    protegidas: set[int] = set()  # linhas de título — não recebem junções
    em_tabela = False
    for linha in linhas:
        atual = linha.rstrip()
        if atual == MARCA_TABELA_INI:
            em_tabela = True
            resultado.append(atual)
            continue
        if atual == MARCA_TABELA_FIM:
            em_tabela = False
            resultado.append(atual)
            continue
        if em_tabela:
            resultado.append(atual)
            continue
        if not resultado or not resultado[-1] or resultado[-1] == MARCA_TABELA_FIM:
            resultado.append(atual)
            continue
        anterior = resultado[-1]
        # linha curta imediatamente após cabeçalho = título ("Âmbito").
        # O limite é 90, o mesmo de `_titulo_candidato` (ISSUE-0017): um
        # limite mais apertado aqui, sem razão para ser diferente, fundia
        # títulos legítimos com o corpo só por terem mais de 60 caracteres
        # ("Organização de serviços de segurança, higiene e saúde no
        # trabalho", com 65, virava início da Cláusula 68.ª sem título).
        # A vírgula final continua a excluir: um título não deixa a frase a
        # meio, ao contrário do início de um parágrafo de corpo (memo 23:
        # "Cumpre … qualquer organização,\npressupõe respostas coletivas.")
        e_titulo = (_e_cabecalho(anterior) and atual
                    and len(atual) <= 90
                    and not atual.endswith(",")
                    and not RE_PONTUACAO_FORTE.search(atual)
                    and not _e_cabecalho(atual)
                    and not RE_MARCADOR.match(atual))
        # memo 4 (06/07): "…alíneas a),\nb) e c) do número…" é continuação,
        # não uma alínea nova — junta-se apesar do marcador
        continuacao_alinea = (RE_ALINEA_CONTINUACAO.match(atual)
                              and anterior.endswith(","))
        # bloco de título da convenção: "… - Revisão global" fecha o
        # título, o que vier a seguir é o preâmbulo (memo 21/23)
        fim_do_titulo = (len(resultado) <= LINHAS_DO_CABECALHO
                         and RE_FIM_TITULO_CONVENCAO.search(anterior))
        # #29: no cabeçalho do documento, o título e o preâmbulo partem-se
        # antes do travessão que liga a sigla ao nome («… Afins» / «- SETAAB -
        # Revisão global», «… e o SINDETELCO» / «- Sindicato Democrático…»).
        # O travessão aí não abre um item de lista: a linha anterior não acaba
        # em pontuação nem é ela própria um item. No corpo, as listas com
        # travessão ficam como estão.
        continuacao_titulo = (len(resultado) <= LINHAS_DO_CABECALHO
                              and RE_TRAVESSAO_INICIAL.match(atual)
                              and not RE_PONTUACAO_FINAL.search(anterior)
                              and not RE_MARCADOR_LISTA.match(anterior)
                              and not _e_cabecalho(anterior))
        manter = (
            not atual
            or RE_PONTUACAO_FORTE.search(anterior)
            or _e_cabecalho(anterior)
            or _e_cabecalho(atual)
            or RE_SO_ROMANO.match(atual)
            or (RE_MARCADOR.match(atual) and not continuacao_alinea
                and not continuacao_titulo)
            or anterior.isupper()
            or fim_do_titulo
            or (len(resultado) - 1) in protegidas
        )
        if manter:
            resultado.append(atual)
            if e_titulo:
                protegidas.add(len(resultado) - 1)
        else:
            resultado[-1] = anterior + " " + atual.strip()
    return "\n".join(resultado)


def _titulo_candidato(linha: str) -> bool:
    """Linha curta que serve de título a um cabeçalho (ex.: "Âmbito").

    Uma data de outorga nunca é título (ISSUE-0018): quando a tabela de um
    anexo não produz conteúdo, o cabeçalho ("ANEXO III") fica seguido, sem
    nada entre os dois, pela data que assina o documento ("Maia, 14 de
    julho de 2026.") — sem este guarda, essa data virava o título do anexo.
    """
    linha = linha.strip()
    return (0 < len(linha) <= 90
            and not _e_cabecalho(linha)
            and not RE_MARCADOR_LISTA.match(linha)
            and not RE_DATA_OUTORGA.match(linha)
            and not RE_REVOGADA.match(linha)
            and not RE_OMISSAO.match(linha)
            and not _e_frase(linha))


def _e_frase(linha: str) -> bool:
    """Uma frase acabada, longa de mais para título: é o corpo.

    «Artigo 7.º» numa linha e «Serão ainda sujeitos ao teste todos os
    trabalhadores que o solicitem.» na seguinte: a frase virava o título e o
    artigo ficava sem conteúdo (ADIPA, Caravela, RTP, corrida de 2025).
    """
    return bool(RE_FRASE_ACABADA.search(linha)) and len(linha.split()) >= MIN_PALAVRAS_FRASE


def _normalizar_rotulo(tipo: str, m: re.Match, titulo_extra: str | None) -> str:
    linha = m.group(0).strip()
    resto = (m.group(2) if m.lastindex and m.lastindex >= 2 else "") or ""
    resto = resto.strip(" -–—:")
    if resto:
        # o que vem antes do resto, pela posição: `linha.split(resto)` partia
        # no primeiro sítio onde o resto aparece, e em «ANEXO A» o «A» é a
        # primeira letra de «ANEXO» — o rótulo ficava « - A», e a palavra
        # ANEXO saía do texto (NAV e Autoridade de Seguros de 2025)
        base = m.group(0)[:m.start(2) - m.start(0)].strip(" -–—:")
        rotulo = f"{base} - {resto}"
    elif titulo_extra:
        rotulo = f"{linha.strip(' -–—:')} - {titulo_extra.strip()}"
    else:
        rotulo = linha
    return rotulo


# o que se segue ao número de uma cláusula numa remissão ou numa lista, e
# nunca num cabeçalho: «Cláusula 44.ª, número 2 - Valor das despesas…» (tabela
# de valores dos seguros), «Cláusula 28.ª - Deslocações em serviço - 16,55 €;»
# (lista de valores de uma alteração salarial)
RE_RESTO_DE_REMISSAO = re.compile(r"^\s*[,;]")
RE_FIM_DE_ITEM = re.compile(r"[,;]\s*$")
# um valor em euros no resto da linha: um título de cláusula nunca o traz
# («Cláusula 29.ª - Viagens em serviço - 71,65 €.»)
RE_VALOR_EM_EUROS = re.compile(r"\d,\d{2}\s*€|€\s*\d")
# o corpo que vem na linha do cabeçalho: uma frase acabada, longa de mais para
# ser um título, ou só «Revogada.»
RE_FRASE_ACABADA = re.compile(r"""[.!?:][)\]»”"']*\s*$""")
RE_REVOGADA = re.compile(r"^[(\[]?\s*revogad[oa]s?\s*\.?\s*[)\]]?$", re.IGNORECASE)
# o texto omitido de uma alteração: «(...)», «[…]». No fim da linha do
# cabeçalho, é o corpo: «Cláusula 37.ª - Cláusula transitória (Anterior
# cláusula 35.ª) (...)» (APDL de 2025) ficava sem conteúdo
_OMISSAO = r"[(\[]\s*(?:(?:\.\s*){3}|…)\s*[)\]]"
RE_OMISSAO = re.compile(rf"^{_OMISSAO}\s*\.?$")
RE_OMISSAO_FIM = re.compile(rf"\s*{_OMISSAO}\s*\.?$")
MAX_TITULO = 90
# uma frase acabada com estas palavras já não é um título: «As decisões dos
# árbitros são tomadas por maioria.» (8), «Devem existir, em locais
# apropriados, lavabos suficientes.» (7). O limite de 90 caracteres deixava
# passar 13 artigos na corrida de 2025.
MIN_PALAVRAS_FRASE = 7


def _linha_de_tabela(linha: str, na_tabela: bool) -> bool:
    """Uma linha de tabela com várias células: nunca é cabeçalho nem título."""
    return na_tabela and " | " in linha


def _nao_e_cabecalho(tipo: str, linha: str, resto: str, na_tabela: bool,
                     item_anterior: bool = False) -> bool:
    """Uma linha com a forma de um cabeçalho que não o é.

    Na corrida de 2025, linhas de tabelas e de listas com «Cláusula N.ª» à
    cabeça viravam cláusulas vazias, e roubavam o texto à cláusula a que
    pertenciam (seguros STAS e SINAPSA, GROQUIFAR, Caravela).

    O último item de uma lista acaba em ponto, como um título pode acabar:
    distingue-se por trazer um valor em euros, ou por vir logo a seguir a
    outro item da mesma forma (`item_anterior`). Sem isto, «Cláusula 29.ª -
    Viagens em serviço - 71,65 €.» abria uma cláusula falsa e separava o fim
    da lista do artigo a que pertence (revisão do PR #90).
    """
    if _linha_de_tabela(linha, na_tabela):
        return True
    if tipo not in ("clausula", "artigo"):
        return False
    return bool(RE_RESTO_DE_REMISSAO.match(resto) or RE_FIM_DE_ITEM.search(linha)
                or RE_VALOR_EM_EUROS.search(resto) or item_anterior)


def _e_corpo(resto: str) -> bool:
    """O resto da linha do cabeçalho é corpo, e não o título."""
    resto = resto.strip(" -–—:")
    return bool(RE_REVOGADA.match(resto) or RE_OMISSAO.match(resto) or _e_frase(resto)
                or (len(resto) > MAX_TITULO and RE_FRASE_ACABADA.search(resto)))


def estruturar(texto: str, doc_id: str, subtipo: str = "desconhecido") -> tuple[dict, str]:
    """Constrói doc.json a partir do texto normalizado."""
    # "Artigo 1. º" → "Artigo 1.º": o espaço a mais partia o rótulo em
    # duas metades ("Artigo 1. - º") e escondia o ordinal no corpo
    texto = RE_ORDINAL_SEPARADO.sub(r"\1.\2", texto)
    # "3São considerados…" → "3- São considerados…" (repõe o que o PDF tem)
    texto = RE_NUMERO_SEM_SEPARADOR.sub(r"\1- ", texto)
    linhas: list[str] = []
    em_tabela: set[int] = set()     # linhas que vêm de uma tabela
    dentro = False
    for linha in juntar_linhas(texto).split("\n"):
        if linha in (MARCA_TABELA_INI, MARCA_TABELA_FIM):
            dentro = linha == MARCA_TABELA_INI
        elif linha.strip():
            if dentro:
                em_tabela.add(len(linhas))
            linhas.append(linha)

    # 1.ª passagem: identificar cabeçalhos e fundir títulos na mesma linha
    eventos: list[tuple[str | None, str]] = []  # (tipo_cabecalho | None, linha)
    i = 0
    item_anterior = False   # a linha anterior era um item de lista «Cláusula N.ª …;»
    while i < len(linhas):
        linha = linhas[i].strip()
        tipo_encontrado = None
        rotulo = linha
        corpo_na_linha = None
        e_item = False
        for tipo_cabecalho, rx in _RE_HEADINGS:
            m = rx.match(linha)
            if not m:
                continue
            resto = (m.group(2) if m.lastindex and m.lastindex >= 2 else "") or ""
            if _nao_e_cabecalho(tipo_cabecalho, linha, resto, i in em_tabela, item_anterior):
                e_item = tipo_cabecalho in ("clausula", "artigo") and i not in em_tabela
                break
            tipo_encontrado = tipo_cabecalho
            titulo_extra = None
            if tipo_cabecalho in ("clausula", "artigo") and _e_corpo(resto):
                # «Artigo 7.º Serão ainda sujeitos ao teste todos os
                # trabalhadores que o solicitem.»: o corpo vem na linha do
                # cabeçalho, e não é o título
                corpo_na_linha = resto.strip(" -–—:")
                rotulo = linha[:m.start(2)].strip(" -–—:")
                break
            omissao = RE_OMISSAO_FIM.search(resto)
            if tipo_cabecalho in ("clausula", "artigo") and omissao:
                # o título e, a seguir, o texto omitido
                corpo_na_linha = omissao.group(0).strip()
                titulo = resto[:omissao.start()].strip(" -–—:")
                base = linha[:m.start(2)].strip(" -–—:")
                rotulo = f"{base} - {titulo}" if titulo else base
                break
            if not resto.strip(" -–—:"):
                # título na(s) linha(s) seguinte(s)?
                j = i + 1
                while j < len(linhas) and not linhas[j].strip():
                    j += 1
                # uma linha de tabela com várias células nunca é o título:
                # «ANEXO III» seguido da grelha de carreiras dava «ANEXO III -
                # | Carreira de Direção Geral» (382 de 2026, ISSUE-0018)
                if j < len(linhas) and not _linha_de_tabela(linhas[j], j in em_tabela) and (
                        _titulo_candidato(linhas[j])
                        or (tipo_cabecalho in ("clausula", "artigo")
                            and RE_SO_DESIGNADOR.match(linhas[j].strip()))):
                    titulo_extra = linhas[j].strip()
                    i = j  # consome a linha do título
                    # o texto omitido colado ao título pela junção de linhas:
                    # «Cláusula 37.ª» / «Cláusula transitória (Anterior
                    # cláusula 35.ª) (...)» (APDL de 2025) é título e corpo
                    omissao = RE_OMISSAO_FIM.search(titulo_extra)
                    if tipo_cabecalho in ("clausula", "artigo") and omissao:
                        corpo_na_linha = omissao.group(0).strip()
                        titulo_extra = titulo_extra[:omissao.start()].strip() or None
            rotulo = _normalizar_rotulo(tipo_cabecalho, m, titulo_extra)
            break
        eventos.append((tipo_encontrado, rotulo if tipo_encontrado else linhas[i]))
        if corpo_na_linha:
            eventos.append((None, corpo_na_linha))
        # só a linha que fecha em vírgula ou ponto e vírgula anuncia outro item
        item_anterior = e_item and bool(RE_FIM_DE_ITEM.search(linha))
        i += 1

    # 2.ª passagem: montar texto final e nós com offsets
    nos: list[dict] = []
    partes: list[str] = []
    pos = 0
    contexto = {"capitulo": None, "seccao": None, "anexo": None}
    # o anexo aberto: o número, e se é um texto articulado (abre com um
    # capítulo, como os regulamentos de carreiras em anexo)
    anexo_aberto: dict = {"numero": None, "articulado": False}
    no_aberto: dict | None = None

    def emitir(segmento: str):
        nonlocal pos
        partes.append(segmento)
        pos += len(segmento)

    def fechar_no():
        nonlocal no_aberto
        if no_aberto is not None:
            no_aberto["char_end"] = pos
            nos.append(no_aberto)
            no_aberto = None

    em_consolidado = False

    def abrir_no(tipo: str, rotulo: str, pai: str | None):
        nonlocal no_aberto
        fechar_no()
        no_aberto = {
            "id": f"n{len(nos)}",
            "tipo": tipo,
            "rotulo": rotulo,
            "char_start": pos,
            "char_end": pos,
            "pai": pai,
            "origem": "consolidado" if em_consolidado else "novo",
            "folha": True,
        }

    abrir_no("preambulo", "PREÂMBULO", None)
    for tipo, linha in eventos:
        if tipo is None:
            # marca explícita de republicação: vale em qualquer subtipo
            # (memo 19 — o GENERALI é revisão global com texto consolidado)
            if not em_consolidado and RE_MARCA_CONSOLIDADO.match(linha.strip()):
                em_consolidado = True
                contexto.update(capitulo=None, seccao=None, anexo=None)
                abrir_no("bloco", "TEXTO CONSOLIDADO", None)
            emitir(linha + "\n")
            continue
        if tipo in ("capitulo", "seccao", "anexo"):
            # padrão ACIP: sem marca explícita, a republicação começa no
            # primeiro capítulo/título depois dos artigos de alteração
            ha_artigo = (any(n["tipo"] == "artigo" for n in nos)
                         or (no_aberto is not None and no_aberto["tipo"] == "artigo"))
            if (not em_consolidado
                    and subtipo in ("revisao_parcial_com_consolidado",
                                    "texto_consolidado")
                    and tipo == "capitulo"
                    and ha_artigo):
                em_consolidado = True
                contexto.update(anexo=None)
            if tipo == "capitulo":
                # Um anexo que abre logo com um capítulo é um texto articulado
                # (o regulamento de carreiras da NAV, dos CARRIS, do INOVA):
                # os capítulos são dele. Sem isto, ficavam soltos, o anexo
                # vazio, e a auditoria dava a tabela do regulamento «fora do
                # nó» (corrida de 2025). Um capítulo depois do corpo de um
                # anexo continua a fechá-lo.
                anexo_vazio = (contexto["anexo"] is not None and no_aberto is not None
                               and no_aberto["pai"] == contexto["anexo"]
                               and no_aberto["char_start"] == pos)
                if contexto["anexo"] and (anexo_vazio or anexo_aberto["articulado"]):
                    anexo_aberto["articulado"] = True
                    contexto.update(capitulo=None, seccao=None)
                    pai = contexto["anexo"]
                else:
                    contexto.update(capitulo=None, seccao=None, anexo=None)
                    pai = None
            elif tipo == "seccao":
                contexto["seccao"] = None
                pai = contexto["capitulo"] or contexto["anexo"]
            else:
                # «ANEXO I - (A)» com o «ANEXO I» aberto é uma parte dele
                # (INATEL de 2025: a tabela salarial vinha em I-(A) e I-(B))
                m_anexo = RE_ANEXO.match(linha)
                numero = re.sub(r"\s", "", m_anexo.group(1) or "") if m_anexo else ""
                # «ANEXO II-A» e «ANEXO II-B» são partes do «ANEXO II», se
                # estiver aberto; sem ele, são anexos irmãos
                if (contexto["anexo"] and numero
                        and numero.split("-")[0] == anexo_aberto["numero"]):
                    pai = contexto["anexo"]
                    contexto.update(capitulo=None, seccao=None)
                else:
                    contexto.update(capitulo=None, seccao=None, anexo=None)
                    anexo_aberto.update(numero=numero, articulado=False)
                    pai = None
            abrir_no(tipo, linha, pai)
            emitir(linha + "\n")
            fechar_no()
            if not (tipo == "anexo" and pai is not None):
                contexto[tipo] = nos[-1]["id"]
            # nó "bloco" absorve conteúdo até ao próximo cabeçalho
            # (ex.: anexos sem cláusulas/artigos — não pode ficar órfão)
            abrir_no("bloco", f"Corpo de {linha}", nos[-1]["id"])
        else:  # clausula | artigo
            # o capítulo antes do anexo: num anexo articulado, o capítulo é
            # do anexo e o artigo é do capítulo
            pai = (contexto["seccao"] or contexto["capitulo"]
                   or contexto["anexo"])
            abrir_no(tipo, linha, pai)
            emitir(linha + "\n")
    fechar_no()

    # descartar preâmbulo vazio
    nos = [n for n in nos if n["char_end"] > n["char_start"]]

    texto_final = "".join(partes)
    _destacar_assinaturas(nos, texto_final)
    nos.extend(_subsegmentar_paragrafos(nos, texto_final))
    doc = {
        "versao_schema": "0.1",
        "doc_id": doc_id,
        "tipo": "CCT",
        "subtipo": subtipo,
        "nos": nos,
    }
    return doc, texto_final


# palavras de ligação que um nome de entidade traz em minúsculas
_LIGACAO = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "na",
            "no", "nas", "nos", "para", "por", "com", "à", "ao", "aos", "às"}
# uma assinatura nomeia a entidade com maiúsculas; mesmo «Pelos outorgantes:»
# ou «Pela entidade empregadora:» têm poucas palavras em minúsculas
MAX_MINUSCULAS_ASSINATURA = 3
RE_PALAVRA_MINUSCULA = re.compile(r"(?<![\w-])[a-zà-ÿ][\wà-ÿ]*")


def _e_linha_assinatura(linha: str) -> bool:
    """«Pela Generali Seguros, SA:», «Pelo Sindicato … - SITEMAQ:».

    Curta ou terminada em dois pontos, e a nomear uma entidade. «Pelo presente
    instrumento, […] as partes acordam alterar o teor do artigo 32.º-A, que
    passará a ter a seguinte redação:» também acaba em dois pontos, mas é uma
    frase: abria o bloco das assinaturas a meio da cláusula (LPFP de 2025).
    """
    linha = linha.strip()
    if not RE_ASSINATURA.match(linha):
        return False
    if linha.startswith("Depositad"):
        return True
    minusculas = [p for p in RE_PALAVRA_MINUSCULA.findall(linha) if p not in _LIGACAO]
    return ((linha.endswith(":") or len(linha) < 60)
            and len(minusculas) <= MAX_MINUSCULAS_ASSINATURA)


def _inicio_assinaturas(linhas: list[str]) -> int | None:
    """Índice da linha onde começa o bloco de assinaturas, se existir.

    Padrões (memos 20/24-28 de 06/07): data por extenso seguida de
    "Pela/Pelo/Pelas/Pelos …" nas linhas seguintes, ou diretamente as
    linhas "Pel…" (nalgumas convenções a data vem depois das assinaturas).
    """
    for i, linha in enumerate(linhas):
        l = linha.strip()
        if _e_linha_assinatura(l):
            return i
        if RE_DATA_OUTORGA.match(l) and any(
                _e_linha_assinatura(s.strip()) for s in linhas[i + 1:i + 5]):
            return i
    return None


def _destacar_assinaturas(nos: list[dict], texto: str) -> None:
    """Separa blocos de assinaturas em qualquer ponto do documento.

    As assinaturas aparecem no fim, mas também a meio — entre as alterações
    e o texto consolidado (memo 20). Ficam em nós próprios ASSINATURAS,
    fora dos segmentos temáticos.
    """
    for no in list(nos):
        if no["tipo"] not in ("clausula", "artigo", "bloco", "preambulo"):
            continue
        if no["rotulo"] in ("ASSINATURAS", "TEXTO CONSOLIDADO"):
            continue
        linhas = texto[no["char_start"]:no["char_end"]].split("\n")
        idx = _inicio_assinaturas(linhas)
        if idx is None or idx == 0:
            continue
        inicio_ass = no["char_start"] + sum(len(l) + 1 for l in linhas[:idx])
        if inicio_ass >= no["char_end"]:
            continue
        fim = no["char_end"]
        no["char_end"] = inicio_ass
        nos.append({
            "id": f"n{len(nos)}ass",
            "tipo": "bloco",
            "rotulo": "ASSINATURAS",
            "char_start": inicio_ass,
            "char_end": fim,
            "pai": None,
            "origem": no.get("origem", "novo"),
            "folha": True,
        })
    # manter a ordem de leitura (a propriedade zero-perda percorre as folhas)
    nos.sort(key=lambda n: (n["char_start"], n["char_end"]))


RE_PARAGRAFO = re.compile(r"^(?:\d+\s*[-–—.)]|[a-z]\)|[ivxl]+\)|[-–—•§]\s?)")


def _subsegmentar_paragrafos(nos: list[dict], texto: str) -> list[dict]:
    """Cria nós 'paragrafo' (números/alíneas) dentro de cláusulas e artigos.

    Convenção do CRL para 2025: a cláusula inteira recebe o código _identif;
    os números/alíneas recebem os subcódigos. Estes nós não são folhas
    (a propriedade zero-perda continua medida sobre as folhas).
    """
    novos = []
    for no in nos:
        if no["tipo"] not in ("clausula", "artigo"):
            continue
        corpo = texto[no["char_start"]:no["char_end"]]
        pos_linha = no["char_start"]
        atual: dict | None = None
        seq = 0
        for linha in corpo.split("\n"):
            if RE_PARAGRAFO.match(linha.strip()):
                if atual is not None:
                    atual["char_end"] = pos_linha
                    novos.append(atual)
                seq += 1
                atual = {
                    "id": f"{no['id']}p{seq}",
                    "tipo": "paragrafo",
                    "rotulo": linha.strip()[:60],
                    "char_start": pos_linha,
                    "char_end": pos_linha,
                    "pai": no["id"],
                    "origem": no.get("origem", "novo"),
                    "folha": False,
                }
            pos_linha += len(linha) + 1
        if atual is not None:
            atual["char_end"] = min(pos_linha, no["char_end"])
            novos.append(atual)
    return novos


# ---------- PDF ----------

RE_HIFEN_CELULA = re.compile(r"-\s*\n\s*(?=[a-zà-ú])")


def _texto_celula(texto: str) -> str:
    """Uma célula numa linha: a hifenização junta-se como no corpo do texto
    («estratégi-\nco» → «estratégico»), as outras quebras passam a espaço."""
    return re.sub(r"[ \t]*\n[ \t]*", " ", RE_HIFEN_CELULA.sub("", texto)).strip()


def _formatar_tabela(linhas_tabela: list[list[str | None]]) -> str:
    """Converte uma tabela do pdfplumber em linhas 'célula | célula | célula'.

    A informação tabular deve manter estrutura analisável (pedido do CRL);
    células vazias ficam em branco mas as colunas mantêm a posição.
    """
    linhas = []
    for row in linhas_tabela:
        celulas = [_texto_celula(c or "") for c in row]
        if any(celulas):
            linhas.append(" | ".join(celulas))
    return "\n".join(linhas)


# ---------- geometria quase direita (#42) ----------
#
# Uma página desenhada com uma rotação de 90º que não é exata (matriz
# (0,01; 8; -8; 0,01) em vez de (0; 8; -8; 0)) engana o pdfplumber em duas
# coisas. As letras contam como direitas, porque a flag `upright` só olha ao
# sinal dos termos da matriz, e são lidas ao contrário e partidas («F ol g a
# s»). Os traços da grelha ficam uns centésimos de ponto tortos, deixam de
# ser horizontais ou verticais, e a tabela não é detetada. Nas escalas do
# TINITA de 2025, metade das páginas era assim. A regra: o sentido de uma
# letra é o eixo dominante da matriz; um traço quase direito é direito.
TRACO_QUASE_DIREITO = 0.5


def _direita(c) -> bool:
    """A letra está escrita na horizontal (direita ou virada 180º)?"""
    a, b, c_, d = c["matrix"][:4]
    return abs(a) + abs(d) >= abs(b) + abs(c_)


MESMA_LINHA_DE_BASE = 1.0


def _horizontal(c) -> bool:
    """Escrita na horizontal e direita (nem rodada nem virada)."""
    a, b, c_, d = c["matrix"][:4]
    return a > 0 and d > 0 and abs(b) + abs(c_) < abs(a) + abs(d)


def _sem_espacos_sobre_letras(letras: list[dict]) -> list[dict]:
    """Um espaço de outra fonte desenhado por cima de uma letra não separa palavras.

    Sobra de uma camada de texto escondida (GESAMB de 2025: um espaço de outra
    fonte por cima do «o» de «obrigam» dava «o brigam»). Conta quando mais de
    metade da largura do espaço cai sobre a letra e os dois estão na mesma
    linha de base: duas linhas entrelaçadas têm linhas de base diferentes, e
    os espaços de uma caem sobre as letras da outra. A fonte tem de ser outra:
    no texto justificado, o espaço da própria linha é desenhado mais largo do
    que o avanço e cai sobre a letra seguinte («A suspensão» ficava
    «Asuspensão», ADIPA de 2025). Só no texto na horizontal:
    no texto rodado, a linha corre na vertical, e os espaços entre algarismos
    das grelhas deitadas do CARRIS saíam («1 220,00» ficava «1220,00»).
    """
    from collections import defaultdict

    faixas = defaultdict(list)
    for c in letras:
        if not c["text"].isspace() and _horizontal(c):
            faixas[int(c["top"] // 4)].append(c)

    def sobre_letra(e) -> bool:
        largura = e["x1"] - e["x0"]
        if largura <= 0 or not _horizontal(e):
            return False
        faixa = int(e["top"] // 4)
        return any(c["fontname"] != e["fontname"]
                   and min(e["x1"], c["x1"]) - max(e["x0"], c["x0"]) > largura / 2
                   and abs(e["matrix"][5] - c["matrix"][5]) < MESMA_LINHA_DE_BASE
                   for f in (faixa - 1, faixa, faixa + 1) for c in faixas[f])
    return [c for c in letras if not (c["text"].isspace() and sobre_letra(c))]


def normalizar_pagina(pag) -> None:
    """Corrige, na própria página, o sentido das letras e os traços quase direitos.

    Mexe nos objetos de que derivam todas as vistas da página (`crop`,
    `filter`, `dedupe_chars`), e por isso tem de correr antes delas. Tira
    também as letras que estão todas fora da página: não se veem (GESAMB e
    MaiaAmbiente de 2025, ver cct/recorte.py).
    """
    x0, topo, x1, fundo = pag.bbox
    letras = [c for c in pag.objects.get("char", [])
              if c["x1"] > x0 and c["x0"] < x1 and c["bottom"] > topo and c["top"] < fundo]
    pag.objects["char"] = _sem_espacos_sobre_letras(letras)
    for c in pag.objects["char"]:
        c["upright"] = _direita(c)
    for traco in pag.objects.get("line", []):
        largura, altura = traco["x1"] - traco["x0"], traco["bottom"] - traco["top"]
        if 0 < altura <= TRACO_QUASE_DIREITO < largura:
            meio = (traco["top"] + traco["bottom"]) / 2
            traco["doctop"] += meio - traco["top"]
            traco["y0"] = traco["y1"] = (traco["y0"] + traco["y1"]) / 2
            traco["top"] = traco["bottom"] = meio
            traco["height"] = 0
        elif 0 < largura <= TRACO_QUASE_DIREITO < altura:
            meio = (traco["x0"] + traco["x1"]) / 2
            traco["x0"] = traco["x1"] = meio
            traco["width"] = 0


# ---------- texto rodado (ISSUE-0020, #42) ----------
#
# Tabelas e escalas desenhadas a 90º numa página que não declara rotação: o
# pdfplumber, por omissão, lê cada palavra ao contrário («sagloF»). Desde a
# 0.11 sabe lê-las no sentido certo (`char_dir_rotated`); falta agrupar as
# palavras em linhas e pôr as tabelas de pé. Só se ativa numa página com texto
# rodado: as outras seguem o caminho de sempre. Basta uma palavra: nas grelhas
# de carreiras da AGEAS de 2025, a única palavra rodada da página é a célula
# vertical «Gestão» (6 letras), e o mínimo de 10 deixava-a em «oãtseG».
MIN_CARACTERES_RODADOS = 3


def _sentido_rodado(obj) -> str | None:
    """«btt» (lê-se de baixo para cima), «ttb» (de cima para baixo) ou None."""
    a, b, c, d = obj["matrix"][:4]
    if abs(a) > 0.1 or abs(d) > 0.1:
        return None
    return "btt" if b > 0 else "ttb"


# uma página só deixa de se cortar em colunas com texto rodado a sério; uma
# palavra vertical numa célula não conta
MIN_RODADOS_SEM_COLUNAS = 10


def _sentido_da_pagina(pag, minimo: int = MIN_CARACTERES_RODADOS) -> str | None:
    sentidos = Counter(
        s for c in pag.chars
        if not c.get("upright", True) and c["text"].strip()
        and (s := _sentido_rodado(c)))
    if sum(sentidos.values()) < minimo:
        return None
    return sentidos.most_common(1)[0][0]


def _opcoes(sentido: str) -> dict:
    # btt: as linhas seguem da esquerda para a direita; ttb: da direita para a esquerda
    return {"char_dir_rotated": sentido,
            "line_dir_rotated": "ltr" if sentido == "btt" else "rtl"}


def _linhas_rodadas(area, sentido: str) -> str:
    """O texto rodado de uma área, uma linha por linha do documento."""
    palavras = [w for w in area.extract_words(**_opcoes(sentido))
                if not w.get("upright", True)]
    palavras.sort(key=lambda w: w["x0"], reverse=sentido == "ttb")
    linhas: list[list[dict]] = []
    for w in palavras:
        if linhas and abs(linhas[-1][0]["x0"] - w["x0"]) <= 2:
            linhas[-1].append(w)
        else:
            linhas.append([w])
    return "\n".join(
        " ".join(w["text"] for w in sorted(
            linha, key=lambda w: w["top"], reverse=sentido == "btt"))
        for linha in linhas)


# Duas linhas a menos de 3 pt uma da outra (a tolerância do pdfplumber) e que
# ocupam a mesma largura fundem-se numa só, letra a letra: «ECma vriggoors d
# deesd» é «Em vigor desde» com «Cargos de Direção» (ANACOM, Lusitânia e GESAMB
# na corrida de 2025). Acontece em cabeçalhos de tabela e em caixas de texto
# sobrepostas. O PDFium lê-as bem, porque segue a ordem do conteúdo.
Y_TOLERANCIA = 3
MIN_SOBREPOSICOES = 3
MIN_LETRAS_LINHA = 4


def _tolerancia_vertical(area) -> float:
    """A tolerância vertical que separa linhas entrelaçadas, ou a normal.

    Numa linha a sério, as letras seguem-se sem se sobreporem; quando duas
    linhas se fundem, letras de uma caem em cima de letras da outra, com
    outra altura. A tolerância passa a metade da menor dessas distâncias.

    Só conta quando, separadas, as letras formam linhas a sério (de
    `MIN_LETRAS_LINHA` letras ou mais, com quase todas as letras). Letras
    escritas em escada, uma a uma, também se sobrepõem com alturas
    diferentes: nas escalas do TINITA, separá-las dava uma letra por linha e
    baralhava as palavras (corrida de 2025 no ramo do PR #90).
    """
    from pdfplumber.utils import cluster_objects

    chars = [c for c in area.chars if c["text"].strip() and c.get("upright", True)]
    distancias = []
    for linha in cluster_objects(chars, "top", Y_TOLERANCIA):
        linha = sorted(linha, key=lambda c: c["x0"])
        sobrepostas = [abs(b["top"] - a["top"]) for a, b in zip(linha, linha[1:])
                       if a["x1"] - b["x0"] > 0.3 * min(a["width"], b["width"])
                       and abs(b["top"] - a["top"]) > 0.3]
        if len(sobrepostas) < MIN_SOBREPOSICOES:
            continue
        tolerancia = min(sobrepostas) / 2
        partes = [len(p) for p in cluster_objects(linha, "top", tolerancia)]
        cheias = [n for n in partes if n >= MIN_LETRAS_LINHA]
        if len(cheias) >= 2 and sum(cheias) >= 0.8 * len(linha):
            distancias.append(tolerancia)
    return min(distancias) if distancias else Y_TOLERANCIA


def _virado(o) -> bool:
    """Carácter escrito de pernas para o ar (rodado 180º).

    O pdfplumber dá-o como direito e lê-o da esquerda para a direita, ao
    contrário da escrita: «oã etniuges lacse oa ossecA» é «Acesso ao escalão
    seguinte» (CARRIS de 2025, esquemas das carreiras; grelhas da RTP).
    """
    if o.get("object_type") != "char":
        return False
    a, _b, _c, d = o["matrix"][:4]
    return a < -0.1 and d < -0.1


# a escrita de um texto virado: da direita para a esquerda, linhas de baixo
# para cima; e o resultado escrito como qualquer outro texto
OPCOES_VIRADO = {"char_dir": "rtl", "line_dir": "btt",
                 "char_dir_render": "ltr", "line_dir_render": "ttb"}


def _extrair_texto(area) -> str:
    """`extract_text`, sem fundir linhas entrelaçadas e com o texto virado lido no sentido certo."""
    if not any(_virado(c) for c in area.chars):
        return area.extract_text(y_tolerance=_tolerancia_vertical(area)) or ""
    direito = area.filter(lambda o: not _virado(o))
    virado = area.filter(lambda o: o.get("object_type") != "char" or _virado(o))
    partes = (direito.extract_text(y_tolerance=_tolerancia_vertical(direito)) or "",
              virado.extract_text(**OPCOES_VIRADO) or "")
    return "\n".join(t for t in partes if t.strip())


def _texto(area, sentido: str | None) -> str:
    """O texto de uma área: direito como sempre, e o rodado à parte, no fim."""
    if sentido is None:
        return _extrair_texto(area)
    direito = _extrair_texto(area.filter(lambda o: o.get("object_type") != "char"
                                         or o.get("upright", True)))
    return "\n".join(t for t in (direito, _linhas_rodadas(area, sentido)) if t.strip())


# Uma tabela é toda rodada (e põe-se de pé) só quando quase todo o texto dela
# está a 90º; uma grelha direita com cabeçalhos verticais (382) não é.
TABELA_RODADA = 0.8


def _celula(pag, cel, sentido: str | None, fora: tuple = ()) -> str:
    """O texto de uma célula, no sentido em que ela está escrita.

    Um carácter pertence à célula pelo seu centro, como no Table.extract do
    pdfplumber: o within_bbox perdia os que tocam no traço da grelha. Os que
    caem numa das caixas `fora` (tabelas dentro desta) não são dela.
    """
    a, b, c, d = cel

    def no_centro(o) -> bool:
        if o.get("object_type") != "char":
            return False
        cx, cy = (o["x0"] + o["x1"]) / 2, (o["top"] + o["bottom"]) / 2
        return (a <= cx < c and b <= cy < d
                and not any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in fora))
    area = pag.filter(no_centro)
    if sentido and _rodada(area):
        return _texto_celula(_linhas_rodadas(area, sentido))
    return _texto_celula(_extrair_texto(area))


def _dados_tabela(tab, sentido: str | None) -> list:
    """As células da tabela, cada uma lida no seu sentido; uma tabela toda
    rodada é posta de pé.

    Rodada no sentido «btt», o cabeçalho está à esquerda da página e a
    primeira coluna em baixo; no sentido «ttb», à direita e em cima.
    """
    interiores = tuple(getattr(tab, "interiores", ()))
    if sentido is None and not interiores:
        return tab.extract()
    x0, t0, x1, t1 = tab.bbox
    dentro = [c for c in tab.page.chars
              if x0 <= c["x0"] <= x1 and t0 <= c["top"] <= t1 and c["text"].strip()]
    rodados = sum(1 for c in dentro if not c.get("upright", True))
    celulas = [[None if cel is None else _celula(tab.page, cel, sentido, interiores)
                for cel in linha.cells] for linha in tab.rows]
    if not celulas or rodados < TABELA_RODADA * len(dentro):
        return celulas
    n_linhas, n_colunas = len(celulas), max(len(r) for r in celulas)
    celulas = [r + [None] * (n_colunas - len(r)) for r in celulas]
    if sentido == "btt":
        return [[celulas[n_linhas - 1 - j][i] for j in range(n_linhas)]
                for i in range(n_colunas)]
    return [[celulas[j][n_colunas - 1 - i] for j in range(n_linhas)]
            for i in range(n_colunas)]


def _rodada(area) -> bool:
    """A maior parte dos caracteres da área está rodada."""
    chars = [c for c in area.chars if c["text"].strip()]
    return bool(chars) and sum(1 for c in chars if not c.get("upright", True)) * 2 > len(chars)


def _zona(pag, bbox):
    """As letras de uma zona da página, cada uma pelo seu centro.

    O `crop` apanha todas as letras que tocam na zona. Entre duas tabelas, ou
    entre uma tabela e o texto, a fronteira passa rente a uma linha, e as
    letras dela entravam nas duas zonas: nas grelhas deitadas do INOVA de
    2025, a linha de valores «1.080,00 €» saía outra vez, entrelaçada com a
    linha seguinte («1.080400,,0000 €€»). Como nas células, uma letra
    pertence a uma zona só, a do seu centro.
    """
    a, b, c, d = bbox

    def dentro(o) -> bool:
        if o.get("object_type") != "char":
            return o["x0"] < c and o["x1"] > a and o["top"] < d and o["bottom"] > b
        return a <= (o["x0"] + o["x1"]) / 2 < c and b <= (o["top"] + o["bottom"]) / 2 < d
    return pag.filter(dentro)


def _fora_das_tabelas(area, tabelas):
    """A área sem os caracteres que pertencem a alguma tabela.

    O texto de uma tabela lê-se na tabela; uma faixa ou um lado que o
    apanhasse repetia-o (382, p34: várias grelhas rodadas lado a lado).
    """
    caixas = [t.bbox for t in tabelas]

    def fora(o) -> bool:
        if o.get("object_type") != "char":
            return True
        cx, cy = (o["x0"] + o["x1"]) / 2, (o["top"] + o["bottom"]) / 2
        return not any(a <= cx <= c and b <= cy <= d for a, b, c, d in caixas)
    return area.filter(fora)


def _ao_lado(pag, tab, tabelas, sentido: str | None) -> tuple[str, str]:
    """O texto à esquerda e à direita de uma tabela, na altura dela.

    As bandas só cobriam o que está acima e abaixo das tabelas; o que estava
    ao lado perdia-se. Nas páginas rodadas dos CARRISTUR é o título e o
    «Deve ler-se:», à esquerda da grelha.
    """
    x0, t0, x1, t1 = tab.bbox
    lados = []
    for a, c in ((pag.bbox[0], x0), (x1, pag.bbox[2])):
        if c - a < 5:
            lados.append("")
            continue
        lados.append(_texto(_fora_das_tabelas(_zona(pag, (a, t0, c, t1)), tabelas), sentido))
    return lados[0], lados[1]


def _grelha_atravessa(pag, meio: float) -> bool:
    """Há traços de tabela a cruzar a goteira no corpo da página?

    Uma tabela com a coluna do meio vazia parece uma página em duas colunas
    (377, «Enquadramento das profissões»; 384 e 385, grelhas largas): cortá-la
    ao meio separava as colunas e partia os títulos centrados («ANEX» | «O II»).
    Os traços do cabeçalho e do rodapé (10% de cima e de baixo) não contam.
    """
    topo, fundo = pag.bbox[1], pag.bbox[3]
    margem = (fundo - topo) * 0.1
    cruzam = sum(1 for e in pag.horizontal_edges
                 if e["x0"] < meio - 10 and e["x1"] > meio + 10
                 and topo + margem < e["top"] < fundo - margem)
    return cruzam >= 2


# Heurística das duas colunas (#27), sobre as palavras da página:
# abaixo de 40 palavras (uma página de assinaturas, um anexo curto) não há
# texto que chegue para decidir, e a página lê-se inteira
MIN_PALAVRAS_COLUNAS = 40
# a goteira: 5 pt para cada lado do meio da página
GOTEIRA_PT = 5
# numa página em colunas, quase nenhuma palavra atravessa a goteira; os
# títulos centrados atravessam, e são poucos: acima de 2%, é coluna única
MAX_ATRAVESSAM_GOTEIRA = 0.02
# e cada metade tem pelo menos um quarto das palavras: uma tabela encostada à
# esquerda, com a direita vazia, não é uma página em colunas
MIN_PALAVRAS_POR_COLUNA = 0.25


def _duas_colunas(pag) -> float | None:
    """Devolve o x da goteira se a página estiver em duas colunas (BTE antigo).

    Heurística: poucas palavras atravessam a faixa central, ambas as
    metades têm texto substancial e nenhuma grelha de tabela cruza o meio.
    """
    palavras = pag.extract_words()
    if len(palavras) < MIN_PALAVRAS_COLUNAS:
        return None
    meio = (pag.bbox[0] + pag.bbox[2]) / 2
    atravessam = sum(1 for w in palavras
                     if w["x0"] < meio - GOTEIRA_PT < meio + GOTEIRA_PT < w["x1"])
    esquerda = sum(1 for w in palavras if w["x1"] <= meio)
    direita = sum(1 for w in palavras if w["x0"] >= meio)
    total = len(palavras)
    if (atravessam / total < MAX_ATRAVESSAM_GOTEIRA
            and esquerda / total > MIN_PALAVRAS_POR_COLUNA
            and direita / total > MIN_PALAVRAS_POR_COLUNA
            and not _grelha_atravessa(pag, meio)
            and not _tabela_atravessa(pag, meio)):
        return meio
    return None


# uma tabela com esta fração da sua área dentro de outra está dentro dela
TABELA_CONTIDA = 0.9


def _tabelas(pag) -> list:
    """As tabelas da página; cada uma sabe que tabelas tem dentro de si.

    Numa grelha em escada (a tabela salarial do EPAL de 2025), o pdfplumber
    deteta a tabela de fora e outras dentro dela, e as células da de fora
    liam também o texto das de dentro: saía duas vezes (695 palavras a
    mais). Uma letra pertence à tabela mais pequena que a contém: a de fora
    guarda em `interiores` as células das de dentro e não as lê. Deitar fora
    as de dentro não servia: nas grelhas rodadas do 382 são elas que têm a
    estrutura.
    """
    tabelas = pag.find_tables()

    def area(b) -> float:
        return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])

    def dentro(t, outra) -> bool:
        a, b = t.bbox, outra.bbox
        comum = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
        return area(b) > area(a) and area(comum) >= TABELA_CONTIDA * area(a)
    # as células das de dentro, e não as caixas: uma letra na caixa de uma
    # tabela de dentro mas fora das células dela só a de fora a lê (EPAL, as
    # etiquetas da escada)
    for t in tabelas:
        t.interiores = [c for o in tabelas if o is not t and dentro(o, t)
                        for c in o.cells if c is not None]
    return tabelas


def _tabela_atravessa(pag, meio: float) -> bool:
    """Há uma tabela detetada que se estende pelos dois lados do meio?

    Quando a fronteira entre duas colunas da grelha cai sobre o meio da
    página, nenhum traço horizontal atravessa a goteira (384 e 385, p4:
    «ANEX» | «O II», «Gr» | «upos profissionais»).
    """
    return any(t.bbox[0] < meio - 20 and t.bbox[2] > meio + 20
               for t in _tabelas(pag))


def _extrair_pagina_deitada(pag, sentido: str) -> str:
    """Uma página impressa de lado (a maior parte do texto a 90º).

    É o mesmo algoritmo das páginas direitas, no referencial da leitura: as
    faixas são verticais e seguem a ordem das linhas rodadas (da esquerda para
    a direita em «btt», ao contrário em «ttb»). Cortar em faixas horizontais,
    como numa página direita, partia as linhas rodadas nas fronteiras.
    """
    x_ini, topo, x_fim, fundo = pag.bbox
    tabelas = sorted(_tabelas(pag), key=lambda t: t.bbox[0], reverse=sentido == "ttb")
    # o texto direito da página (o cabeçalho do BTE, uma nota) lê-se de uma
    # vez: as faixas verticais partiam-no («Boletim do Trabalh» | «ho e …»)
    direito = _extrair_texto(_fora_das_tabelas(pag, tabelas).filter(
        lambda o: o.get("object_type") != "char" or o.get("upright", True)))
    partes = [direito] if direito.strip() else []

    def juntar(area) -> None:
        txt = _linhas_rodadas(_fora_das_tabelas(area, tabelas), sentido)
        if txt.strip():
            partes.append(txt)

    # posição já lida, na direção da leitura
    pos = x_ini if sentido == "btt" else x_fim
    for tab in tabelas:
        x0, t0, x1, t1 = tab.bbox
        antes = (pos, x0) if sentido == "btt" else (x1, pos)
        if antes[1] - antes[0] > 1:
            juntar(_zona(pag, (antes[0], topo, antes[1], fundo)))
        # ao lado da tabela, na leitura: em «btt», a esquerda lógica é o fundo
        # da página; em «ttb», é o topo
        baixo = (x0, t1, x1, fundo) if fundo - t1 > 1 else None
        cima = (x0, topo, x1, t0) if t0 - topo > 1 else None
        primeiro, segundo = (baixo, cima) if sentido == "btt" else (cima, baixo)
        if primeiro:
            juntar(_zona(pag, primeiro))
        dados = _dados_tabela(tab, sentido)
        corpo = _formatar_tabela(dados) if dados else ""
        if corpo:
            partes.append(f"{MARCA_TABELA_INI}\n{corpo}\n{MARCA_TABELA_FIM}")
        if segundo:
            juntar(_zona(pag, segundo))
        pos = max(pos, x1) if sentido == "btt" else min(pos, x0)
    resto = (pos, x_fim) if sentido == "btt" else (x_ini, pos)
    if resto[1] - resto[0] > 1:
        juntar(_zona(pag, (resto[0], topo, resto[1], fundo)))
    return "\n".join(partes)


# Uma faixa em colunas acaba também num espaço em branco que atravessa a
# página inteira, as duas colunas vazias à mesma altura, desta ordem de
# grandeza em alturas de linha: é uma mudança de secção, e não o espaço entre
# parágrafos (ISSUE-0006; boletim 28 de 2021, p44)
SALTO_DE_SECCAO = 3.0


# Numa linha que atravessa a goteira, o espaço entre a última letra à esquerda
# e a primeira à direita é o de uma palavra; entre duas colunas é bem maior.
GOTEIRA_MINIMA = 8


def _faixas_de_colunas(pag, goteira: float) -> list[tuple[float, float, bool]] | None:
    """Faixas horizontais de uma página em colunas: (topo, fundo, larga).

    Nas páginas finais de 2025 as assinaturas vêm em duas colunas, mas o fim
    do texto e a nota de depósito ocupam a largura toda. Cortar a página
    inteira ao meio partia essas linhas em duas metades, lidas em sítios
    diferentes: «livro n.º 13, com o n.º 253/2025, nos termos do artigo …»
    ficava depois da nota (74 avisos de «linhas depois da nota de depósito»).
    Devolve `None` quando nenhuma linha atravessa a goteira: a página é toda
    em colunas.
    """
    from pdfplumber.utils import cluster_objects

    chars = [c for c in pag.chars if c["text"].strip() and c.get("upright", True)]
    linhas = []
    for linha in cluster_objects(chars, "top", Y_TOLERANCIA):
        esquerda = [c for c in linha if (c["x0"] + c["x1"]) / 2 < goteira]
        direita = [c for c in linha if (c["x0"] + c["x1"]) / 2 >= goteira]
        larga = bool(esquerda and direita) and _atravessa(esquerda, direita)
        linhas.append((min(c["top"] for c in linha), max(c["bottom"] for c in linha), larga))
    linhas.sort()
    if not any(larga for *_, larga in linhas):
        return None
    # a altura típica de uma linha, para medir os espaços em branco
    alturas = sorted(fundo - topo for topo, fundo, _ in linhas)
    salto_de_seccao = SALTO_DE_SECCAO * alturas[len(alturas) // 2]
    faixas: list[list] = []
    for topo, fundo, larga in linhas:
        # «DECISÕES ARBITRAIS», curto e encostado à esquerda, por baixo de um
        # bloco em colunas: sem isto lia-se entre a coluna esquerda e a direita
        mudanca_de_seccao = (faixas and not larga and not faixas[-1][2]
                             and topo - faixas[-1][1] >= salto_de_seccao)
        if faixas and faixas[-1][2] == larga and not mudanca_de_seccao:
            faixas[-1][1] = max(faixas[-1][1], fundo)
        else:
            faixas.append([topo, fundo, larga])
    # as fronteiras ficam a meio do espaço entre faixas; as pontas, na página
    limites = [pag.bbox[1]] + [(a[1] + b[0]) / 2 for a, b in zip(faixas, faixas[1:])] + [pag.bbox[3]]
    return [(limites[i], limites[i + 1], f[2]) for i, f in enumerate(faixas)]


def _atravessa(esquerda: list, direita: list) -> bool:
    """A linha continua de uma coluna para a outra, como texto corrido?

    O espaço na goteira tem de ser um espaço entre palavras da própria linha:
    não maior do que o maior desses espaços. Dois títulos lado a lado, um em
    cada coluna, estão perto da goteira mas mais afastados do que as suas
    palavras (Lusitânia-STAS de 2025: «ANEXO VI ANEXO VI Tabela de
    correspondência … Tabela de correspondência …»).
    """
    salto = min(c["x0"] for c in direita) - max(c["x1"] for c in esquerda)
    if salto >= GOTEIRA_MINIMA:
        return False
    espacos = []
    for lado in (esquerda, direita):
        ordenados = sorted(lado, key=lambda c: c["x0"])
        espacos += [b["x0"] - a["x1"] for a, b in zip(ordenados, ordenados[1:])
                    if b["x0"] - a["x1"] > 0.8]
    return salto <= max(espacos, default=0) * 1.2 or salto <= 1


def _extrair_em_colunas(pag, goteira: float) -> str:
    """Uma página em duas colunas, com as linhas de largura inteira no seu sítio.

    O texto sai por faixas, de cima para baixo; numa faixa em colunas lê-se
    a esquerda e depois a direita. A marca de coluna separa os segmentos, para
    a remoção do mobiliário ver o topo e o fundo de cada um.
    """
    x0, _topo, x1, _fundo = pag.bbox
    faixas = _faixas_de_colunas(pag, goteira) or [(pag.bbox[1], pag.bbox[3], False)]
    segmentos: list[list[str]] = [[]]
    for topo, fundo, larga in faixas:
        if larga:
            segmentos[-1].append(_extrair_pagina(pag.crop((x0, topo, x1, fundo)), colunas=False))
            continue
        segmentos[-1].append(_extrair_pagina(pag.crop((x0, topo, goteira, fundo)), colunas=False))
        segmentos.append([_extrair_pagina(pag.crop((goteira, topo, x1, fundo)), colunas=False)])
    return f"\n{MARCA_COLUNA}\n".join(
        t for t in ("\n".join(p for p in seg if p.strip()) for seg in segmentos) if t.strip())


def _extrair_pagina(pag, colunas: bool = True) -> str:
    """Extrai uma página intercalando bandas de texto e tabelas na ordem de leitura.

    O BTE é de coluna única: fatiamos a página em bandas horizontais entre
    as tabelas detetadas; o texto de cada banda sai com extract_text e as
    tabelas saem estruturadas entre sentinelas MARCA_TABELA_*. Uma página com
    texto rodado a 90º não se corta em colunas e lê-se no sentido certo.
    """
    sentido = _sentido_da_pagina(pag)
    if sentido and _rodada(pag):
        return _extrair_pagina_deitada(pag, sentido)
    rodada_a_serio = sentido and _sentido_da_pagina(pag, MIN_RODADOS_SEM_COLUNAS)
    goteira = None if rodada_a_serio or not colunas else _duas_colunas(pag)
    if goteira is not None:
        return _extrair_em_colunas(pag, goteira)

    tabelas = sorted(_tabelas(pag), key=lambda t: t.bbox[1])
    if not tabelas:
        return _texto(pag, sentido)

    partes = []
    topo = pag.bbox[1]
    for tab in tabelas:
        x0, t0, x1, t1 = tab.bbox
        if t0 > topo:
            banda = _fora_das_tabelas(_zona(pag, (pag.bbox[0], topo, pag.bbox[2], t0)), tabelas)
            txt = _texto(banda, sentido)
            if txt.strip():
                partes.append(txt)
        esquerda, direita = _ao_lado(pag, tab, tabelas, sentido)
        if esquerda.strip():
            partes.append(esquerda)
        dados = _dados_tabela(tab, sentido)
        if dados:
            corpo = _formatar_tabela(dados)
            if corpo:
                partes.append(f"{MARCA_TABELA_INI}\n{corpo}\n{MARCA_TABELA_FIM}")
        if direita.strip():
            partes.append(direita)
        topo = max(topo, t1)
    if topo < pag.bbox[3]:
        banda = _fora_das_tabelas(_zona(pag, (pag.bbox[0], topo, pag.bbox[2], pag.bbox[3])),
                                  tabelas)
        txt = _texto(banda, sentido)
        if txt.strip():
            partes.append(txt)
    return "\n".join(partes)


# Linhas no topo e no fundo de cada página (ou coluna) onde o BTE põe o seu
# mobiliário: cabeçalho com o número do boletim, número da página, rodapé.
ZONA_MOBILIARIO = 3


def _segmentos(pagina: str) -> list[list[str]]:
    """As colunas de uma página, sem a marca que as separa."""
    segmentos: list[list[str]] = [[]]
    for linha in pagina.split("\n"):
        if linha.strip() == MARCA_COLUNA:
            segmentos.append([])
        else:
            segmentos[-1].append(linha)
    return segmentos


def _texto_fora_de_tabela(linhas: list[str]) -> list[int]:
    """Índices das linhas não vazias, fora das tabelas e das suas marcas."""
    fora = []
    em_tabela = False
    for i, linha in enumerate(linhas):
        limpa = linha.strip()
        if limpa == MARCA_TABELA_INI:
            em_tabela = True
        elif limpa == MARCA_TABELA_FIM:
            em_tabela = False
        elif limpa and not em_tabela:
            fora.append(i)
    return fora


def _nas_margens(linhas: list[str]) -> set[int]:
    """Índices das linhas de texto no topo ou no fundo de uma coluna.

    As linhas de tabela contam para a posição, mas nunca são mobiliário: um
    rodapé depois de uma tabela no fim da página está na margem; uma linha
    entre duas tabelas a meio da página não está.
    """
    cheias = [i for i, l in enumerate(linhas) if l.strip()]
    # numa página curta, três linhas de cada lado eram a página inteira, e
    # uma frase do corpo repetida entre páginas curtas desaparecia
    zona = max(1, min(ZONA_MOBILIARIO, len(cheias) // 4))
    margens = set(cheias[:zona] + cheias[-zona:])
    return margens.intersection(_texto_fora_de_tabela(linhas))


def _remover_cabecalhos_rodapes(paginas: list[str]) -> list[str]:
    """Remove o mobiliário do BTE sem tocar no corpo nem nas tabelas.

    Mobiliário é o que se repete no topo ou no fundo das páginas: uma linha
    de texto que aparece nas margens de metade das páginas (e de três, pelo
    menos), um número de página sozinho nas margens, ou uma linha inteira de
    cabeçalho, data ou rodapé do BTE em qualquer sítio (`cct/mobiliario.py`).
    A posição conta: antes, qualquer linha repetida em 30% das páginas
    desaparecia, incluindo frases legítimas do corpo (issue #47).

    O limiar de repetição era 30% das páginas, com um mínimo de duas. Num
    documento curto, duas páginas bastavam: no CIMPOR de 2025 (8 páginas) as
    tabelas de cada ano, com o mesmo título e as mesmas notas, perdiam o
    título e as notas na segunda e na terceira vez; no SCML-SDPGL (4
    páginas), a assinatura do mesmo mandatário em dois blocos. O mobiliário
    do BTE já se reconhece pelo conteúdo; a regra da repetição fica para o
    que se repete em quase todas as páginas.
    """
    colunas = [_segmentos(pag) for pag in paginas]
    contagem: Counter[str] = Counter()
    for segmentos in colunas:
        contagem.update({seg[i].strip() for seg in segmentos for i in _nas_margens(seg)})
    limiar = max(3, -(-len(paginas) // 2))
    repetidas = {l for l, c in contagem.items() if c >= limiar}
    limpas = []
    for segmentos in colunas:
        linhas = []
        for seg in segmentos:
            margens = _nas_margens(seg)
            texto = set(_texto_fora_de_tabela(seg))
            for i, linha in enumerate(seg):
                limpa = linha.strip()
                # cabeçalho, data e rodapé do BTE em linha própria, em
                # qualquer sítio: nas páginas de 2026 nem sempre se repetem
                # o bastante para a regra das margens os apanhar (os
                # CARRISTUR têm três páginas e o cabeçalho só na primeira)
                if i in texto and e_mobiliario(limpa):
                    continue
                if i in texto and (resto := sem_prefixo_de_cabecalho(limpa)) != limpa:
                    # cabeçalho e data na mesma linha, às vezes com o título
                    # a seguir (CARRISTUR, primeira página)
                    if resto:
                        linhas.append(resto)
                    continue
                if i in margens and (limpa in repetidas or re.fullmatch(r"\d+", limpa)
                                     or RE_RODAPE_PARTIDO.match(limpa)):
                    continue
                linhas.append(linha)
        limpas.append("\n".join(linhas))
    return limpas


def extrair_pdf(pdf_path: Path, paginas: tuple[int, int] | None = None,
                doc_id: str | None = None,
                subtipo: str = "desconhecido") -> tuple[dict, str]:
    """Extrai uma convenção de um PDF do BTE (intervalo de páginas 0-based, fim exclusivo)."""
    import pdfplumber
    import pypdfium2 as pdfium

    from .recorte import letras_escondidas, tirar_escondidas

    from .limites import verificar_pdf

    pdf_path = Path(pdf_path)
    textos = []
    # corrompido, protegido ou excessivo: falha já, com o que fazer (#25)
    verificar_pdf(pdf_path)
    documento = pdfium.PdfDocument(str(pdf_path))
    try:
        with pdfplumber.open(pdf_path) as pdf:
            inicio = 0 if paginas is None else paginas[0]
            pags = pdf.pages if paginas is None else pdf.pages[paginas[0]:paginas[1]]
            for n, pag in enumerate(pags, inicio):
                # o texto recortado não se vê e não entra (cct/recorte.py)
                pagina = documento[n]
                try:
                    tirar_escondidas(pag, letras_escondidas(pagina))
                finally:
                    pagina.close()
                normalizar_pagina(pag)
                # negrito simulado: o mesmo carácter desenhado duas vezes, quase
                # no mesmo sítio («CCaarrrreeiirraa», 382); fica um
                t = _extrair_pagina(pag.dedupe_chars())
                if t.strip():
                    textos.append(t)
    finally:
        documento.close()
    if not textos:
        raise ValueError(f"Sem texto extraível em {pdf_path} — PDF digitalizado?")

    textos = _remover_cabecalhos_rodapes(textos)
    bruto = "\n".join(textos)
    bruto = re.sub(r"-\n(?=[a-zà-ú])", "", bruto)          # des-hifenização
    bruto = re.sub(r"[ \t]+\n", "\n", bruto)               # espaços finais
    bruto = re.sub(r"\n{3,}", "\n\n", bruto)

    return estruturar(bruto, doc_id or pdf_path.stem, subtipo=subtipo)
