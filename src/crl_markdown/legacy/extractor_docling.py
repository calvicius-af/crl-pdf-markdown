"""Extrator alternativo: docling → limpeza APP_CCT → doc.json.

Substitui apenas a camada de extração de texto (pdfplumber); a
estruturação hierárquica é a mesma do extrator clássico (estruturar),
pelo que o doc.json e o texto final têm o formato habitual do pipeline.

O texto é montado a partir dos itens do DoclingDocument (não do
Markdown): os cabeçalhos chegam como texto simples — sem os `#` que o
Markdown acrescenta e que sobreviviam à limpeza quando o nível passava
de 6 — e as tabelas são lidas da grelha estruturada, o que permite
emitir uma célula por span em vez das repetições que o Markdown cria
para cada coluna abrangida por um colspan (ISSUE-0003, pontos 1 e 2).

Custo: ~1-1,7 s/página em CPU e download único dos modelos na primeira
corrida — o extrator clássico continua a ser a via rápida.
"""
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .extractor import MARCA_TABELA_FIM, MARCA_TABELA_INI, estruturar


# O que se consome dos objetos do docling, como contrato tipado (#27). O
# docling é opcional: estes Protocol descrevem os atributos que o código lê,
# sem importar o docling_core; os tipos reais satisfazem-nos, e um teste o
# confirma quando o docling está instalado (tests/test_extractor_docling.py).
@runtime_checkable
class CelulaDocling(Protocol):
    """Uma célula da grelha de uma tabela (docling_core TableCell)."""
    text: str
    start_col_offset_idx: int
    start_row_offset_idx: int


@runtime_checkable
class CaixaDocling(Protocol):
    """A caixa de um item (docling_core BoundingBox): l, t, r, b e a origem."""
    l: float  # noqa: E741 — o nome é o do docling
    t: float
    r: float
    b: float
    coord_origin: Any

# mobiliário do BTE que aparece no corpo da página
RE_BTE_CABECALHO = re.compile(r"^Boletim do Trabalho e Emprego\b")
RE_BTE_DATA = re.compile(r"^\d{1,2}\s+(?:de\s+)?[a-zç]+\s+(?:de\s+)?\d{4}$")
# fragmento do cabeçalho partido pelo docling (ISSUE-0019): a linha do
# cabeçalho corrido às vezes chega em item(ns) próprio(s) e sobra só "BE"
# ou "BTE" isolado, sem pontuação. Regra estreita de propósito — "BE" pode
# ser sigla legítima de uma entidade — para não apanhar siglas reais.
RE_BTE_FRAGMENTO = re.compile(r"^BT?E$")
# hífen de translineação que sobrou com espaço: "profis -sional"
RE_HIFEN_SOLTO = re.compile(r"([a-zà-ú]) -([a-zà-ú])")
# item de lista que já traz marcador próprio no texto ("1- …", "a) …",
# "-Executar …" — este último dava "- -Executar" com a bala do docling)
RE_MARCADOR_PROPRIO = re.compile(
    r"^(?:\d+\s*[-–—.)]|[a-zà-ú]\)|[ivxl]+\)|[-–—•·])")
# ListItem em que o docling separou o número do início do texto, sem
# repor separador: "3Idade…", "2Sem prejuízo…" (ISSUE-0016, pontos 8 e 11)
RE_NUMERO_COLADO_LISTA = re.compile(r"^(\d+)(?=[A-ZÀ-Ú])")
# alínea fundida ao parágrafo anterior no mesmo item de texto, sem quebra
# entre as duas: "…da empresa; n) O presente…" (ISSUE-0016, ponto 6b) — a
# regra é estreita (letra única + ")" + maiúscula logo a seguir ao ";") para
# não confundir com uma referência legítima a meio de frase
RE_ALINEA_FUNDIDA = re.compile(r";\s+([a-zà-ú]\)\s+[A-ZÀ-Ú])")

_conversor = None

# Limites e perímetro da conversão (#25). O tempo por documento mede-se no
# #26: 1,75 s por página a quente; 900 s chegam para 500 páginas.
TEMPO_MAX_S = 900.0
# Memória máxima da conversão, em MB (CCT_DOCLING_MEMORIA_MAX_MB; 0 desliga).
# O pico medido no corpus é de 4,4 GB (#26): 10 GB deixam folga e param um PDF
# patológico antes de esgotar uma estação de 16 GB.
MEMORIA_MAX_MB = 10_000.0
# as variáveis que põem o huggingface_hub e o transformers em modo offline, e
# os valores que dizem «ligado»
_VARIAVEIS_OFFLINE = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
_LIGADO = {"1", "true", "yes", "on"}


def memoria_max_mb() -> float:
    valor = os.environ.get("CCT_DOCLING_MEMORIA_MAX_MB")
    return float(valor) if valor else MEMORIA_MAX_MB


def forcar_offline() -> list[str]:
    """Põe o docling em modo offline, seja qual for o ambiente (revisão do PR #95).

    Com a pasta dos modelos, a promessa é que nada vai à rede. Um
    `HF_HUB_OFFLINE=0` já definido no ambiente não pode desfazer isso: as
    variáveis ficam a `1`, e a configuração do `huggingface_hub`, que as lê
    quando é importado, também, se já o tiver sido. Devolve os valores
    contrários que encontrou, para se avisar.
    """
    contrarias = [f"{v}={os.environ[v]}" for v in _VARIAVEIS_OFFLINE
                  if v in os.environ and os.environ[v].strip().lower() not in _LIGADO]
    for variavel in _VARIAVEIS_OFFLINE:
        os.environ[variavel] = "1"
    constantes = sys.modules.get("huggingface_hub.constants")
    if constantes is not None:
        constantes.HF_HUB_OFFLINE = True  # type: ignore[attr-defined]
    return contrarias


def pasta_modelos() -> Path | None:
    """A pasta com os modelos descarregados (CCT_DOCLING_MODELOS), se houver."""
    pasta = os.environ.get("CCT_DOCLING_MODELOS")
    return Path(pasta) if pasta else None


def opcoes_seguras(pasta: Path | None = None) -> dict:
    """As opções do pipeline do docling que definem o perímetro da conversão.

    Nenhum serviço remoto nem plugin externo: o conteúdo dos documentos nunca
    sai da máquina. Um tempo máximo por documento, para que um PDF patológico
    não prenda a corrida. Com a pasta dos modelos, o docling lê-os de lá.

    Com a pasta dos modelos, o OCR fica desligado, a menos que
    `CCT_DOCLING_OCR=1`: os PDF do BTE têm texto, e o OCR automático escolhe o
    motor pelo que está instalado, não pelo que está na pasta. Sem o
    `onnxruntime`, escolhia um motor cujos modelos não estavam lá e ia buscá-los
    à rede (medido a 2026-09-26, com a rede bloqueada).
    """
    tempo = os.environ.get("CCT_DOCLING_TEMPO_MAX_S")
    opcoes: dict = {"enable_remote_services": False, "allow_external_plugins": False,
                    "document_timeout": float(tempo) if tempo else TEMPO_MAX_S}
    if pasta is not None:
        opcoes["artifacts_path"] = str(pasta)
        opcoes["do_ocr"] = os.environ.get("CCT_DOCLING_OCR") == "1"
    return opcoes


def limpar_texto_item(texto: str) -> str | None:
    """Normaliza o texto de um item; devolve None se for para descartar.

    Descarta mobiliário do BTE (cabeçalho corrido, data da edição,
    número de página solto, fragmento "BE"/"BTE" isolado) e repara a
    translineação que o docling deixa com espaço antes do hífen.
    """
    texto = (texto or "").replace("\n", " ").replace("\t", " ")
    texto = re.sub(r"\s{2,}", " ", texto).strip()
    if not texto:
        return None
    if (RE_BTE_CABECALHO.match(texto) or RE_BTE_DATA.match(texto)
            or RE_BTE_FRAGMENTO.fullmatch(texto)
            or re.fullmatch(r"\d+", texto)):
        return None
    return RE_HIFEN_SOLTO.sub(r"\1\2", texto)


def celulas_da_linha(linha: Sequence[CelulaDocling | None],
                     indice_linha: int = 0) -> list[str]:
    """Uma célula por span, a partir de uma linha da grelha do docling.

    A grelha repete a mesma célula em todas as posições que o span
    abrange: nas colunas de um colspan ("Competência | Competência |
    Competência") e nas linhas de um rowspan. Uma célula só é emitida na
    sua posição inicial, dada por start_col_offset_idx e
    start_row_offset_idx em conjunto.

    A continuação de um colspan é omitida; a continuação de um rowspan sai
    como célula vazia, para as colunas à direita não deslizarem para a
    esquerda no texto separado por " | ". Garante-se que nenhuma célula
    se perde e que nenhuma sai repetida; NÃO se garante que todas as
    linhas tenham o mesmo número de células — quando duas linhas têm
    colspans diferentes, emitem contagens diferentes, o que é inerente a
    "uma célula por span".

    Células genuinamente iguais em posições distintas (ex.: "n.a." numa
    tabela salarial) mantêm-se todas — o que as distingue de um span é
    começarem cada uma na sua própria posição.
    """
    saida = []
    for indice, celula in enumerate(linha):
        if celula is None:
            saida.append("")
            continue
        if getattr(celula, "start_col_offset_idx", indice) != indice:
            continue  # continuação horizontal: já emitida nesta linha
        if getattr(celula, "start_row_offset_idx", indice_linha) != indice_linha:
            saida.append("")  # continuação vertical: emitida numa linha acima
            continue
        texto = (getattr(celula, "text", "") or "").replace("\n", " ").strip()
        saida.append(re.sub(r"\s{2,}", " ", texto))
    return saida


def _linhas_de_tabela(tabela) -> list[str]:
    """Tabela do docling → linhas 'célula | célula' (formato do pipeline)."""
    try:
        grelha = tabela.data.grid
    except AttributeError:
        return []
    linhas = []
    for indice_linha, linha in enumerate(grelha):
        celulas = celulas_da_linha(linha, indice_linha)
        if any(celulas):
            linhas.append(" | ".join(celulas))
    return linhas


# origem das coordenadas do docling: o CoordOrigin dele é um enum de
# strings, por isso comparamos pelo nome e não importamos docling_core —
# assim a ordenação (e os seus testes) não arrasta a dependência opcional
ORIGEM_INFERIOR = "BOTTOMLEFT"


def distancia_ao_topo(bbox: CaixaDocling, altura_pagina: float) -> float:
    """Topo do item medido a partir do topo da página (origem indiferente).

    Com origem no canto inferior esquerdo (o que o docling usa nos PDF),
    `t` cresce para cima e tem de ser invertido; com origem no canto
    superior já é a distância ao topo.
    """
    origem = getattr(bbox, "coord_origin", None)
    nome = getattr(origem, "name", origem)
    if nome == ORIGEM_INFERIOR:
        return altura_pagina - bbox.t
    return bbox.t


# Heurística das duas colunas sobre as caixas do docling (#27). As caixas são
# blocos (parágrafos), e não palavras, por isso os limites são mais largos do
# que os do extrator clássico (cct/extractor.py, `_duas_colunas`):
# abaixo de 8 blocos, a página não tem texto que chegue para decidir
MIN_CAIXAS_COLUNAS = 8
# a goteira: 2% da largura para cada lado do meio
GOTEIRA_FRACAO = 0.02
# numa página em colunas, quase nenhum bloco atravessa a goteira (os títulos
# centrados atravessam); acima de 5%, é uma página de coluna única
MAX_CAIXAS_ATRAVESSAM = 0.05
# e cada metade tem pelo menos um quarto dos blocos
MIN_CAIXAS_POR_COLUNA = 0.25


def _duas_colunas(caixas: Sequence[CaixaDocling], largura: float) -> bool:
    """Página em duas colunas? (BTE antigos; os de 2025 são coluna única)"""
    if len(caixas) < MIN_CAIXAS_COLUNAS:
        return False
    meio, tol = largura / 2, largura * GOTEIRA_FRACAO
    atravessam = sum(1 for b in caixas if b.l < meio - tol and b.r > meio + tol)
    esquerda = sum(1 for b in caixas if b.r <= meio + tol)
    direita = sum(1 for b in caixas if b.l >= meio - tol)
    return (atravessam / len(caixas) < MAX_CAIXAS_ATRAVESSAM
            and esquerda / len(caixas) > MIN_CAIXAS_POR_COLUNA
            and direita / len(caixas) > MIN_CAIXAS_POR_COLUNA)


def ordenar_por_leitura(itens: list) -> list:
    """Ordena (item, pagina, bbox) pela ordem de leitura da página.

    O docling emite por vezes blocos fora de sítio — na LAGOSemFORMA o
    conteúdo da cláusula 9.ª aparecia antes do próprio cabeçalho, e a
    cláusula ficava vazia. A geometria é fiável, por isso é ela que manda:
    página, coluna (quando existem duas) e distância ao topo. Itens sem
    geometria herdam a posição do anterior, ficando onde estavam.
    """
    paginas: dict = {}
    for indice, (_item, pagina, bbox, _altura, _largura) in enumerate(itens):
        if bbox is not None:
            paginas.setdefault(pagina, []).append(bbox)
    colunado = {}
    for pagina, caixas in paginas.items():
        largura = next(l for (_i, p, _b, _a, l) in itens if p == pagina)
        colunado[pagina] = _duas_colunas(caixas, largura)

    chaves, ultima = [], (0, 0, 0.0)
    for indice, (_item, pagina, bbox, altura, largura) in enumerate(itens):
        if bbox is None:
            chaves.append((*ultima, indice))
            continue
        coluna = 0
        if colunado.get(pagina) and bbox.l >= largura / 2 - largura * GOTEIRA_FRACAO:
            coluna = 1
        ultima = (pagina, coluna, distancia_ao_topo(bbox, altura))
        chaves.append((*ultima, indice))
    return [itens[i] for i in sorted(range(len(itens)), key=lambda i: chaves[i])]


def _itens_ordenados(documento):
    """Itens do documento pela ordem de leitura geométrica."""
    recolhidos = []
    for item, _nivel in documento.iterate_items():
        pagina, bbox, altura, largura = 0, None, 0.0, 0.0
        prov = getattr(item, "prov", None)
        if prov:
            pagina = prov[0].page_no
            bbox = prov[0].bbox
            pag = documento.pages.get(pagina)
            if pag is not None and pag.size is not None:
                altura, largura = pag.size.height, pag.size.width
        recolhidos.append((item, pagina, bbox, altura, largura))
    return [i[0] for i in ordenar_por_leitura(recolhidos)]


def documento_para_texto(documento) -> str:
    """DoclingDocument → texto plano que o estruturar consome.

    Percorre os itens pela ordem de leitura geométrica: imagens ficam de
    fora, as tabelas saem entre sentinelas MARCA_TABELA_* e o resto sai
    como texto limpo, sem sintaxe de Markdown pelo meio.
    """
    from docling_core.types.doc.document import (
        ListItem, PictureItem, TableItem, TextItem)

    linhas: list[str] = []
    for item in _itens_ordenados(documento):
        if isinstance(item, PictureItem):
            continue
        if isinstance(item, TableItem):
            corpo = _linhas_de_tabela(item)
            if corpo:
                linhas.append(MARCA_TABELA_INI)
                linhas.extend(corpo)
                linhas.append(MARCA_TABELA_FIM)
            continue
        if not isinstance(item, TextItem):
            continue
        texto = limpar_texto_item(item.text)
        if texto is None:
            continue
        texto = RE_ALINEA_FUNDIDA.sub(r";\n\1", texto)
        if isinstance(item, ListItem) and not RE_MARCADOR_PROPRIO.match(texto):
            marcador = (getattr(item, "marker", "") or "").strip()
            if marcador:
                # o docling separou o marcador (ex.: "g)") do texto,
                # em vez de o deixar no início (ISSUE-0016, pontos 6a e 10)
                texto = f"{marcador} {texto}"
            elif RE_NUMERO_COLADO_LISTA.match(texto):
                # número colado ao texto, sem separador: "3Idade…" → "3- Idade…"
                texto = RE_NUMERO_COLADO_LISTA.sub(r"\1- ", texto)
            else:
                texto = f"- {texto}"
        linhas.extend(texto.split("\n"))
    return "\n".join(linhas) + "\n"


def _obter_conversor():
    global _conversor
    if _conversor is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        pasta = pasta_modelos()
        if pasta is not None:
            # os modelos estão na pasta: nada se descarrega, nem se tenta
            contrarias = forcar_offline()
            if contrarias:
                print(f"CCT_DOCLING_MODELOS: modo offline forçado; o ambiente dizia "
                      f"{', '.join(contrarias)}", file=sys.stderr)
        opcoes = PdfPipelineOptions(**opcoes_seguras(pasta))
        _conversor = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opcoes)})
    return _conversor


def _converter(pdf_path: Path, paginas: tuple[int, int] | None):
    from .limites import verificar_pdf
    verificar_pdf(pdf_path)     # corrompido, protegido ou excessivo: falha já
    kwargs: dict = {}
    if paginas is not None:  # 0-based fim-exclusivo → 1-based inclusivo
        kwargs["page_range"] = (paginas[0] + 1, paginas[1])
    # sem o pós-processador docling-hierarchical-pdf: rebenta com
    # page_range e a hierarquia que infere não acrescenta nada — quem
    # reconhece capítulos e cláusulas é o estruturar, e a ordem de
    # leitura vem da geometria (ordenar_por_leitura)
    from .limites import limite_de_memoria
    with limite_de_memoria(memoria_max_mb()):
        resultado = _obter_conversor().convert(str(pdf_path), **kwargs)
    # uma conversão parcial (o tempo máximo acabou, uma página falhou) não
    # passa por completa: o texto teria buracos sem ninguém saber
    estado = getattr(getattr(resultado, "status", None), "value", "success")
    if estado != "success":
        raise ValueError(
            f"{Path(pdf_path).name}: o docling não converteu o documento todo "
            f"({estado}); com o tempo máximo de {opcoes_seguras()['document_timeout']:g} s, "
            "subir CCT_DOCLING_TEMPO_MAX_S ou usar o pdfplumber")
    return resultado


def extrair_pdf_docling(pdf_path: Path, paginas: tuple[int, int] | None = None,
                        doc_id: str | None = None,
                        subtipo: str = "desconhecido") -> tuple[dict, str]:
    """Extrai uma convenção com docling (mesma assinatura de extrair_pdf)."""
    pdf_path = Path(pdf_path)
    resultado = _converter(pdf_path, paginas)
    texto = documento_para_texto(resultado.document)
    if not texto.strip():
        raise ValueError(f"Sem texto extraível em {pdf_path} — PDF digitalizado?")
    return estruturar(texto, doc_id or pdf_path.stem, subtipo=subtipo)
