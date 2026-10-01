"""Docling → regras CCT comprovadas → Markdown legível, sem codificação temática."""

import html
import re
from collections import Counter
from dataclasses import dataclass

from .legacy import extractor as rules
from .legacy import extractor_docling as docling_rules
from .legacy.mobiliario import e_mobiliario, sem_prefixo_de_cabecalho
from .quality import Finding, normalize, parser
from .textrepair import repair_wrapped


@dataclass
class Prepared:
    markdown: str
    plain: str
    structure: dict
    structured_text: str
    findings: list[Finding]
    generated_headings: list[str]
    reordered: bool
    tables: int


def escape_text(text: str) -> str:
    # Evita que números legais sejam renumerados pelo importador CommonMark.
    for char in "\\`*_[]<>":
        text = text.replace(char, "\\" + char)
    text = re.sub(r"^(\s*\d+)([.)])(?=\s)", r"\1\\\2", text)
    return re.sub(r"^([#>])", r"\\\1", text)


def plain_markdown(markdown: str, generated_headings=()) -> str:
    """Conteúdo visível do ficheiro FINAL, excluindo só os títulos acrescentados."""
    lines = markdown.splitlines()
    for heading in generated_headings:
        if heading in lines:
            lines.remove(heading)
    text = []
    for token in parser().parse("\n".join(lines)):
        if token.type == "inline" and token.children:
            value = ""
            for child in token.children:
                if child.type in {"text", "code_inline"}:
                    value += html.unescape(child.content)
                elif child.type in {"softbreak", "hardbreak"}:
                    value += "\n"
            text.append(value)
        elif token.type in {"code_block", "fence"}:
            text.append(token.content)
    return "\n".join(text) + "\n"


def table_rows(table, findings=None, reference_words=()) -> list[list[str]]:
    """Grelha retangular: uma célula por posição; spans não duplicam os valores."""
    # Usar table_cells, porque .grid sobrescreve silenciosamente células quando
    # o Docling atribui spans sobrepostos (Empresa Metropolitana, página 34).
    height = max(
        [table.data.num_rows] + [c.start_row_offset_idx + 1 for c in table.data.table_cells]
    )
    width = max(
        [table.data.num_cols] + [c.start_col_offset_idx + 1 for c in table.data.table_cells]
    )
    rows = [["" for _ in range(width)] for _ in range(height)]
    occupied, overlap = set(), False
    for cell in table.data.table_cells:
        position = (cell.start_row_offset_idx, cell.start_col_offset_idx)
        region = {
            (row, col)
            for row in range(cell.start_row_offset_idx, cell.end_row_offset_idx)
            for col in range(cell.start_col_offset_idx, cell.end_col_offset_idx)
        }
        overlap = overlap or bool(region & occupied)
        occupied.update(region)
        value = rules._texto_celula(repair_wrapped(html.unescape(cell.text or ""), reference_words))
        previous = rows[position[0]][position[1]]
        rows[position[0]][position[1]] = previous + " / " + value if previous else value
    if overlap and findings is not None:
        findings.append(
            Finding(
                "TABLE_OVERLAP",
                0,
                "Células com posições sobrepostas: todos os textos foram preservados, "
                "mas a correspondência entre linhas e colunas exige revisão.",
                "error",
            )
        )
    return rows


def table_markdown(rows: list[list[str]]) -> str:
    encoded = [[escape_text(cell).replace("|", r"\|") for cell in row] for row in rows]
    lines = ["| " + " | ".join(row) + " |" for row in encoded]
    lines.insert(1, "| " + " | ".join("---" for _ in rows[0]) + " |")
    return "\n".join(lines)


def item_text(item, findings, reference_words=()) -> str | None:
    from docling_core.types.doc import ListItem

    label = getattr(getattr(item, "label", None), "value", "")
    if label in {"page_header", "page_footer"}:
        return None
    text = repair_wrapped(html.unescape(item.text or ""), reference_words)
    # As mesmas regras estreitas de limpeza do projeto original.
    cleaned = docling_rules.limpar_texto_item(text)
    if cleaned is None:
        # Um número isolado no corpo pode ser conteúdo; a geometria/mobiliário
        # e os rótulos acima identificam cabeçalhos e rodapés de forma separada.
        if text.strip().isdigit():
            cleaned = text.strip()
        else:
            return None
    cleaned = sem_prefixo_de_cabecalho(cleaned)
    if not cleaned or e_mobiliario(cleaned):
        return None
    cleaned = docling_rules.RE_ALINEA_FUNDIDA.sub(r";\n\1", cleaned)
    if isinstance(item, ListItem):
        # O Docling pode acrescentar uma bala por cima de um marcador original.
        cleaned = re.sub(r"^[-•]\s+(?=\d+(?:\s*[-–—.)]|[A-ZÀ-Ú])|[a-zà-ú]\))", "", cleaned)
        if docling_rules.RE_NUMERO_COLADO_LISTA.match(cleaned):
            cleaned = docling_rules.RE_NUMERO_COLADO_LISTA.sub(r"\1- ", cleaned)
        elif not docling_rules.RE_MARCADOR_PROPRIO.match(cleaned):
            original = html.unescape(getattr(item, "orig", "") or "").strip()
            match = re.match(r"^(\d+\s*[-–—.)]|[a-zà-ú]\)|[ivxl]+\))\s*", original)
            marker = match.group(1) if match else (getattr(item, "marker", "") or "").strip()
            if not marker:
                findings.append(
                    Finding(
                        "LIST_MARKER", 0, "Item de lista sem marcador recuperável; conferir no PDF."
                    )
                )
                marker = "-"
            cleaned = marker + " " + cleaned
    return cleaned


def is_bte_margin_picture(item, document):
    """Pequeno logótipo centrado no topo, apenas em páginas identificadas como BTE."""
    from docling_core.types.doc import CoordOrigin

    if not item.prov:
        return False
    for prov in item.prov:
        page = document.pages.get(prov.page_no)
        if page is None:
            return False
        header = any(
            any(p.page_no == prov.page_no for p in text.prov)
            and (
                "Boletim do Trabalho e Emprego" in text.text
                or re.fullmatch(r"BTE\s+\d+.*", text.text)
            )
            for text in document.texts
        )
        if not header:
            return False
        box = prov.bbox.to_top_left_origin(page.size.height)
        if box.coord_origin != CoordOrigin.TOPLEFT:
            return False
        width, height = page.size.width, page.size.height
        if not (
            0 <= box.t < box.b <= height * 0.075
            and width * 0.43 <= box.l < box.r <= width * 0.57
            and (box.r - box.l) * (box.b - box.t) <= width * height * 0.005
        ):
            return False
    return True


def prepare(document, doc_id: str, *, subtype="desconhecido", reference_words=()) -> Prepared:
    from docling_core.types.doc import PictureItem, TableItem, TextItem

    findings = []
    ordered = docling_rules._itens_ordenados(document)
    original = [item for item, _ in document.iterate_items()]
    reordered = [id(item) for item in ordered] != [id(item) for item in original]
    stream, table_data = [], {}
    for item in ordered:
        if isinstance(item, PictureItem):
            if is_bte_margin_picture(item, document):
                continue
            page = item.prov[0].page_no if item.prov else "?"
            findings.append(Finding("IMAGE", 0, f"Página {page}: figura sem transcrição textual."))
        elif isinstance(item, TableItem):
            rows = table_rows(item, findings, reference_words)
            if not rows or not any(cell for row in rows for cell in row):
                findings.append(Finding("TABLE_EMPTY", 0, "Tabela Docling sem conteúdo.", "error"))
                continue
            # APSolutions (ISSUE-0016): o Docling confundiu o título da
            # cláusula e os números 1–12 omitidos com uma grelha de duas colunas.
            single = [next((value for value in row if value), "") for row in rows]
            if (
                len(rows) > 1
                and all(sum(bool(value) for value in row) <= 1 for row in rows)
                and rules._titulo_candidato(single[0])
                and all(rules.RE_MARCADOR_LISTA.match(value) for value in single[1:])
            ):
                stream.extend(single)
                findings.append(
                    Finding(
                        "TABLE_AS_TEXT",
                        0,
                        "Título e números legais numa tabela de uma célula por linha "
                        "foram recuperados como texto.",
                        "info",
                    )
                )
                continue
            key = f"CRLTABLE{len(table_data)} | CRLTABLEEND"
            table_data[key] = rows
            stream.extend([rules.MARCA_TABELA_INI, key, rules.MARCA_TABELA_FIM])
            if any(cell.row_span > 1 or cell.col_span > 1 for cell in item.data.table_cells):
                findings.append(
                    Finding(
                        "TABLE_SPAN",
                        0,
                        f"Tabela {len(table_data)}: células unidas; "
                        "continuações vazias preservam a grelha. Conferir no PDF.",
                    )
                )
        elif isinstance(item, TextItem):
            text = item_text(item, findings, reference_words)
            if text:
                stream.extend(text.splitlines())
    if not stream:
        raise RuntimeError("Docling não extraiu texto nem tabelas.")
    source = "\n".join(stream) + "\n"
    nodes, text = rules.estruturar(source, doc_id, subtipo=subtype)
    # A sanidade trabalha com texto e tabelas reais, sem placeholders internos.
    expanded = source
    for key, rows in table_data.items():
        expanded = expanded.replace(key, "\n".join(" | ".join(row) for row in rows))
    structure, structured_text = rules.estruturar(expanded, doc_id, subtipo=subtype)

    by_id = {node["id"]: node for node in nodes["nos"]}

    def level(node):
        parent = by_id.get(node.get("pai"))
        return min(6, level(parent) + 1) if parent else 2

    output, generated = [], []
    for node in nodes["nos"]:
        if not node.get("folha", True):
            continue
        body = text[node["char_start"] : node["char_end"]].strip().splitlines()
        if node["tipo"] in {"clausula", "artigo", "capitulo", "seccao", "anexo"}:
            output.append("#" * level(node) + " " + escape_text(node["rotulo"]))
            body = body[1:]
        elif node["tipo"] == "preambulo":
            heading = "## Preâmbulo"
            if body and rules.RE_PREAMBULO_LINHA.fullmatch(body[0].strip()):
                heading = "## " + escape_text(body[0])
                body = body[1:]
            else:
                generated.append(heading)
            output.append(heading)
        elif node["rotulo"] in {"ASSINATURAS", "TEXTO CONSOLIDADO"}:
            heading = "## " + node["rotulo"].capitalize()
            output.append(heading)
            if body and body[0].upper() == node["rotulo"]:
                body = body[1:]
            else:
                generated.append(heading)
        for line in body:
            output.append(
                table_markdown(table_data[line]) if line in table_data else escape_text(line)
            )
    markdown = normalize("\n\n".join(output) + "\n")
    plain = plain_markdown(markdown, generated)

    # Cada palavra do texto estruturado deve sobreviver à renderização.
    # A proteção das tabelas usa grelhas completas e não a versão plana com spans.
    def words(value):
        return Counter(re.findall(r"\w+", html.unescape(value)))

    if words(structured_text) != words(plain):
        findings.append(
            Finding(
                "RENDER_CONTENT",
                0,
                "Renderização alterou a contagem de palavras; rever o documento.",
                "error",
            )
        )
    return Prepared(
        markdown, plain, structure, structured_text, findings, generated, reordered, len(table_data)
    )
