"""Correções conservadoras e verificações de Markdown, sem reescrever o conteúdo."""

import re
from dataclasses import asdict, dataclass

from markdown_it import MarkdownIt


@dataclass(frozen=True)
class Finding:
    rule: str
    line: int
    message: str
    severity: str = "warning"

    def to_dict(self):
        return asdict(self)


def parser():
    return MarkdownIt("commonmark", {"html": True}).enable("table")


def cells(line: str) -> list[str]:
    """Separadores não escapados; não partir pipes literais."""
    # Scanner conserva exatamente os caracteres, incluindo barras invertidas.
    parts = []
    start = 0
    escapes = 0
    for index, char in enumerate(line):
        if char == "|" and escapes % 2 == 0:
            parts.append(line[start:index].strip())
            start = index + 1
        escapes = escapes + 1 if char == "\\" else 0
    parts.append(line[start:].strip())
    if line.lstrip().startswith("|"):
        parts.pop(0)
    if line.rstrip().endswith("|") and start == len(line.rstrip()):
        parts.pop()
    return parts


def normalize(markdown: str) -> str:
    """Normaliza apenas fora de código; espaços de quebra de linha são preservados."""
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    tokens = parser().parse("\n".join(lines))
    protected = set()
    boundaries = set()
    tables = {}
    for token in tokens:
        if token.map is None:
            continue
        start, end = token.map
        if token.type in {"fence", "code_block", "html_block"}:
            protected.update(range(start, end))
        if token.type in {"heading_open", "table_open"} and token.level == 0:
            boundaries.update((start, end))
        if token.type == "table_open" and token.level == 0:
            tables[start] = end

    for index, line in enumerate(lines):
        if index not in protected:
            lines[index] = line.expandtabs(4)

    # Alinhamento visual: só tabelas regulares, sem acrescentar/apagar células.
    for start, end in tables.items():
        rows = [cells(line) for line in lines[start:end]]
        if not rows or any(len(row) != len(rows[0]) for row in rows):
            continue
        widths = [max(3, *(len(row[col]) for row in rows)) for col in range(len(rows[0]))]
        for offset, row in enumerate(rows):
            if offset == 1:
                formatted = []
                for cell, width in zip(row, widths):
                    left, right = cell.startswith(":"), cell.endswith(":")
                    formatted.append(
                        (":" if left else "")
                        + "-" * (width - left - right)
                        + (":" if right else "")
                    )
            else:
                formatted = [cell.ljust(width) for cell, width in zip(row, widths)]
            lines[start + offset] = "| " + " | ".join(formatted) + " |"

    output = []
    for index, line in enumerate(lines):
        if index in boundaries and output and output[-1].strip() and line.strip():
            output.append("")
        if index not in protected:
            # Dois espaços finais têm significado no CommonMark.
            hard_break = bool(line.strip()) and line.endswith("  ")
            line = line.rstrip() + ("  " if hard_break else "")
            if not line and (not output or not output[-1]):
                continue
        output.append(line)
    return "\n".join(output).strip("\n") + "\n"


def lint(markdown: str) -> list[Finding]:
    lines = markdown.splitlines()
    tokens = parser().parse(markdown)
    findings = []
    protected = set()
    tables = set()
    last_heading = 0
    meaningful = False
    for token in tokens:
        if token.map is None:
            continue
        start, end = token.map
        if token.type in {"fence", "code_block"}:
            protected.update(range(start, end))
            meaningful = True
        if token.type in {"paragraph_open", "table_open", "heading_open"}:
            meaningful = True
        if token.type == "heading_open":
            level = int(token.tag[1:])
            if level > (last_heading or 0) + 1:
                findings.append(Finding("MD001", start + 1, "Salto de nível no título."))
            last_heading = level
        if token.type == "table_open":
            tables.update(range(start, end))
            rows = [cells(line) for line in lines[start:end]]
            for index, row in enumerate(rows):
                if len(row) != len(rows[0]):
                    findings.append(
                        Finding(
                            "MD056",
                            start + index + 1,
                            "Número de células diferente do cabeçalho.",
                            "error",
                        )
                    )
            if len(rows[0]) > 8:
                findings.append(
                    Finding(
                        "TABLE_WIDE", start + 1, "Tabela com mais de oito colunas; rever no MAXQDA."
                    )
                )
        if token.type in {"html_block", "html_inline"} and not token.content.lstrip().startswith(
            "<!--"
        ):
            findings.append(Finding("MD033", start + 1, "HTML requer revisão na importação."))
        if token.type == "inline" and token.children:
            for child in token.children:
                if child.type == "image":
                    findings.append(
                        Finding(
                            "IMAGE", start + 1, "Imagem externa: conteúdo não incluído no Markdown."
                        )
                    )
                if child.type == "html_inline" and not child.content.startswith("<!--"):
                    findings.append(
                        Finding("MD033", start + 1, "HTML requer revisão na importação.")
                    )
    if not meaningful:
        findings.append(Finding("EMPTY", 1, "Documento sem texto ou tabelas.", "error"))
    for index, line in enumerate(lines):
        if index in protected:
            continue
        if index not in tables and re.match(r"^\s*\|.*\|\s*$", line):
            findings.append(
                Finding(
                    "TABLE_UNPARSED",
                    index + 1,
                    "Linha tabular sem tabela Markdown válida.",
                    "error",
                )
            )
        if "\ufffd" in line:
            findings.append(
                Finding("UNICODE", index + 1, "Carácter de substituição Unicode.", "error")
            )
        if "<!-- image -->" in line:
            findings.append(Finding("IMAGE", index + 1, "Figura do PDF sem transcrição textual."))
    return findings
