from docling_core.types.doc import DocItemLabel, DoclingDocument, TableCell, TableData

from crl_markdown.document import plain_markdown, prepare
from crl_markdown.quality import cells, lint, parser


def convention():
    doc = DoclingDocument(name="Convenção")
    doc.add_text(label=DocItemLabel.TITLE, text="Acordo de empresa - Revisão global")
    doc.add_text(label=DocItemLabel.TEXT, text="As partes acordam no presente instrumento.")
    doc.add_heading(text="CAPÍTULO I", level=1)
    doc.add_heading(text="Disposições gerais", level=1)
    doc.add_heading(text="Cláusula 1.ª", level=1)
    doc.add_heading(text="Área e âmbito", level=1)
    doc.add_list_item(text="Aplica-se a todos os trabalhadores.", marker="1-", enumerated=True)
    doc.add_list_item(text="2Sem prejuízo dos direitos adquiridos.", marker="", enumerated=True)
    doc.add_list_item(text="Ter habilitações exigidas para a função;", marker="a)")
    return doc


def test_clause_title_preamble_and_numbered_list_preserve_visible_markers():
    prepared = prepare(convention(), "exemplo")
    assert "### Cláusula 1.ª - Área e âmbito\n" in prepared.markdown
    assert "## Preâmbulo\n" in prepared.markdown
    assert "As partes acordam no presente instrumento." in prepared.markdown
    assert "1- Aplica-se" in prepared.markdown
    assert "2- Sem prejuízo" in prepared.markdown
    assert "a) Ter habilitações" in prepared.markdown
    assert not any(
        token.type in {"bullet_list_open", "ordered_list_open"}
        for token in parser().parse(prepared.markdown)
    )
    assert prepared.plain == plain_markdown(prepared.markdown, prepared.generated_headings)
    assert not any(f.severity == "error" for f in prepared.findings)


def test_native_numbered_markers_are_displayed_without_renumbering():
    doc = convention()
    doc.add_list_item(text="Mantém o número original.", marker="7.", enumerated=True)
    prepared = prepare(doc, "exemplo")
    assert "7\\. Mantém" in prepared.markdown
    assert "7. Mantém" in prepared.plain
    assert not any(token.type == "ordered_list_open" for token in parser().parse(prepared.markdown))


def test_legal_title_between_sixty_and_ninety_characters_issue17():
    doc = convention()
    doc.add_heading(text="Cláusula 68.ª", level=1)
    title = "Organização de serviços de segurança, higiene e saúde no trabalho"
    doc.add_heading(text=title, level=1)
    doc.add_text(label=DocItemLabel.TEXT, text="Independentemente do número de trabalhadores.")
    prepared = prepare(doc, "exemplo")
    assert "### Cláusula 68.ª - " + title + "\n" in prepared.markdown
    assert "\n\nIndependentemente do número" in prepared.markdown


def test_explicit_preamble_entities_and_signatures_are_preserved():
    doc = DoclingDocument(name="Convenção")
    for value in (
        "Preâmbulo",
        "As partes acordam o seguinte.",
        "Cláusula 1.ª",
        "Área &#x20;e âmbito",
        "1- A convenção aplica-se a todos.",
        "Lisboa, 12 de maio de 2026.",
        "Pela Entidade:",
        "Ana Silva, mandatária.",
    ):
        doc.add_text(label=DocItemLabel.TEXT, text=value)
    prepared = prepare(doc, "exemplo")
    assert prepared.markdown.count("## Preâmbulo") == 1
    assert "Cláusula 1.ª - Área e âmbito" in prepared.markdown
    assert "## Assinaturas" in prepared.markdown
    assert "Lisboa, 12 de maio de 2026." in prepared.markdown
    assert "Ana Silva, mandatária." in prepared.markdown
    assert not any(f.rule == "RENDER_CONTENT" for f in prepared.findings)


def test_rectangular_merged_table_does_not_repeat_cells_or_drop_values():
    doc = convention()
    cells_data = [
        TableCell(
            text="Competência",
            col_span=2,
            start_row_offset_idx=0,
            end_row_offset_idx=1,
            start_col_offset_idx=0,
            end_col_offset_idx=2,
        ),
        TableCell(
            text="Valor",
            start_row_offset_idx=0,
            end_row_offset_idx=1,
            start_col_offset_idx=2,
            end_col_offset_idx=3,
        ),
        *[
            TableCell(
                text=value,
                start_row_offset_idx=1,
                end_row_offset_idx=2,
                start_col_offset_idx=col,
                end_col_offset_idx=col + 1,
            )
            for col, value in enumerate(["A|B", "n.a.", "1 250,00 €"])
        ],
    ]
    doc.add_table(data=TableData(num_rows=2, num_cols=3, table_cells=cells_data))
    prepared = prepare(doc, "exemplo")
    rows = [cells(line) for line in prepared.markdown.splitlines() if line.startswith("|")]
    assert all(len(row) == 3 for row in rows)
    assert prepared.markdown.count("Competência") == 1
    assert "A|B" in prepared.plain and "1 250,00 €" in prepared.plain
    assert not any(
        f.rule in {"MD056", "RENDER_CONTENT"} for f in lint(prepared.markdown) + prepared.findings
    )


def test_prose_mistaken_for_table_recovered_issue16_apsolutions():
    doc = convention()
    doc.add_heading(text="Cláusula 33.ª", level=1)
    values = ["(Prémio de permanência)", *[f"{i}- (...)" for i in range(1, 13)]]
    table_cells = [
        TableCell(
            text=value,
            start_row_offset_idx=row,
            end_row_offset_idx=row + 1,
            start_col_offset_idx=1 if row == 0 else 0,
            end_col_offset_idx=2 if row == 0 else 1,
        )
        for row, value in enumerate(values)
    ]
    doc.add_table(data=TableData(num_rows=13, num_cols=2, table_cells=table_cells))
    prepared = prepare(doc, "exemplo")
    assert "### Cláusula 33.ª - (Prémio de permanência)" in prepared.markdown
    assert "12- (...)" in prepared.markdown
    assert prepared.tables == 0
    assert not any(f.severity == "error" for f in prepared.findings)


def test_annex_title_never_absorbs_table_header_or_outorga_date_issue18():
    doc = convention()
    doc.add_heading(text="ANEXO III", level=1)
    doc.add_table(
        data=TableData(
            num_rows=2,
            num_cols=2,
            table_cells=[
                TableCell(
                    text=value,
                    start_row_offset_idx=row,
                    end_row_offset_idx=row + 1,
                    start_col_offset_idx=col,
                    end_col_offset_idx=col + 1,
                )
                for row, values in enumerate([["Carreira", "Valor"], ["Técnico", "1000,00"]])
                for col, value in enumerate(values)
            ],
        )
    )
    doc.add_text(label=DocItemLabel.TEXT, text="Maia, 14 de julho de 2026.")
    prepared = prepare(doc, "exemplo")
    assert "## ANEXO III\n" in prepared.markdown
    assert "ANEXO III -" not in prepared.markdown
    assert "Maia, 14 de julho de 2026." in prepared.markdown


def test_overlapping_spans_never_hide_values_issue18_metropolitana():
    doc = convention()
    doc.add_table(
        data=TableData(
            num_rows=2,
            num_cols=2,
            table_cells=[
                TableCell(
                    text="Categoria",
                    row_span=2,
                    start_row_offset_idx=0,
                    end_row_offset_idx=2,
                    start_col_offset_idx=0,
                    end_col_offset_idx=1,
                ),
                TableCell(
                    text="Valor",
                    start_row_offset_idx=0,
                    end_row_offset_idx=1,
                    start_col_offset_idx=1,
                    end_col_offset_idx=2,
                ),
                TableCell(
                    text="2.841,09",
                    start_row_offset_idx=1,
                    end_row_offset_idx=2,
                    start_col_offset_idx=0,
                    end_col_offset_idx=1,
                ),
                TableCell(
                    text="2.896,39",
                    start_row_offset_idx=1,
                    end_row_offset_idx=2,
                    start_col_offset_idx=1,
                    end_col_offset_idx=2,
                ),
            ],
        )
    )
    prepared = prepare(doc, "exemplo")
    assert all(
        prepared.markdown.count(value) == 1 for value in ("Categoria", "2.841,09", "2.896,39")
    )
    assert any(f.rule == "TABLE_OVERLAP" and f.severity == "error" for f in prepared.findings)
