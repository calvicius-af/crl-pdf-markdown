import pytest

from crl_markdown.quality import cells, lint, normalize, parser


def rules(markdown):
    return {f.rule for f in lint(markdown)}


def test_preserves_content_and_aligns_tables():
    raw = "# Convenção\nTexto: 1 234,50 €.\n|Categoria|Valor|\n|---|---|\n|Técnico|1 234,50 €|\n\nFim.\n"
    result = normalize(raw)
    assert normalize(result) == result
    before = [t.content for t in parser().parse(raw) if t.type == "inline"]
    after = [t.content for t in parser().parse(result) if t.type == "inline"]
    assert before == after
    assert "\n\n| Categoria" in result
    assert "\n\nFim." in result
    assert not lint(result)


@pytest.mark.parametrize(
    "row,expected",
    [
        ("| A | B |", ["A", "B"]),
        (r"| A\|B | C |", [r"A\|B", "C"]),
        ("A | B", ["A", "B"]),
        ("| | 0 |", ["", "0"]),
        ("| A | B |  ", ["A", "B"]),
    ],
)
def test_table_cells(row, expected):
    assert cells(row) == expected


def test_bad_table_never_discards_extra_values():
    raw = "| A | B |\n| --- | --- |\n| 10 | 20 | 30 |\n"
    result = normalize(raw)
    assert "30" in result
    assert "MD056" in rules(result)


def test_preserves_code_spaces_and_blank_lines():
    raw = "# Documento\n\n```text\n| A | B |  \n\n\n## literal\n```\n"
    assert normalize(raw) == raw
    assert not lint(raw)


def test_preserves_numbering_hard_breaks_and_legal_markers():
    raw = "# Convenção\r\n\r\n3. Direito  \r\n   Continuação\r\n\r\na) Primeiro;\r\nb) Segundo.\r\n"
    result = normalize(raw)
    assert "3. Direito  \n" in result
    assert "   Continuação" in result
    assert "a) Primeiro;\nb) Segundo." in result


def test_heading_gaps_reported_without_changing_hierarchy():
    raw = "# Título\n\n### Cláusula\n"
    assert "MD001" in rules(raw)
    assert "### Cláusula" in normalize(raw)


def test_empty_image_html_and_unicode():
    assert "EMPTY" in rules("<!-- image -->\n")
    assert "IMAGE" in rules("Texto\n\n<!-- image -->\n")
    assert "MD033" in rules("Texto<br>continuação\n")
    assert "UNICODE" in rules("Extração \ufffd\n")
    assert "IMAGE" in rules("![Figura](missing.png)\n")


def test_malformed_and_wide_tables():
    assert "TABLE_UNPARSED" in rules("| Categoria | Valor |\n| A | 42 |\n")
    table = "\n".join("| " + " | ".join([value] * 9) + " |" for value in ("A", "---", "42"))
    assert "TABLE_WIDE" in rules(table)


def test_alignment_and_empty_cells_preserved():
    raw = "| A | B |\n| :--- | ---: |\n| | 0 |\n"
    result = normalize(raw)
    assert cells(result.splitlines()[2]) == ["", "0"]
    assert cells(result.splitlines()[1])[0].startswith(":")
    assert cells(result.splitlines()[1])[1].endswith(":")


def test_legal_readability_regressions_also_detected_on_existing_markdown():
    assert "LEGAL_LIST_BULLET" in rules("- 2Sem prejuízo dos direitos.\n")
    assert "LEGAL_LIST_BULLET" in rules("- g) Direito a férias.\n")
    assert "CLAUSE_TITLE_SPLIT" in rules("**Cláusula 1.ª**\n\nÁrea e âmbito\n")
    assert "CLAUSE_TITLE_SPLIT" not in rules("## Cláusula 1.ª - Área e âmbito\n\n1- Aplica-se a todos.\n")
