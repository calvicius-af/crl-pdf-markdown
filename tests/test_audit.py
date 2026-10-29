from collections import Counter

from crl_markdown.audit import amounts, audit_pdf, pdf_amounts
from crl_markdown.legacy.extractor import estruturar
from tests.pdf_sintetico import escrever_pdf, grelha, pagina_bte


def test_amount_normalization():
    assert amounts("1 250,00 2.841,09 967,00 12.50") == Counter(
        {"1250,00": 1, "2841,09": 1, "967,00": 1, "12,50": 1}
    )


def test_independent_pdf_reference_detects_removed_paragraph(tmp_path):
    original = (
        "Cláusula 1.ª - Área e âmbito\n"
        "1- O presente acordo aplica-se a todos os trabalhadores.\n"
        "2- As partes salvaguardam os direitos individuais e coletivos adquiridos.\n"
    )
    pdf = escrever_pdf(tmp_path / "teste.pdf", [pagina_bte(1, original.splitlines())])
    doc, text = estruturar(original, "teste")
    result, findings, _ = audit_pdf(pdf, text, doc, text, 0)
    assert result["cobertura"] == 1.0
    assert result["audited_content"] == "final_markdown_visible_text"
    damaged = text.replace(
        "2- As partes salvaguardam os direitos individuais e coletivos adquiridos.", ""
    )
    result, findings, diagnostic = audit_pdf(pdf, damaged, doc, text, 0)
    assert result["cobertura"] < 0.97
    assert any(f.rule == "COMPLETENESS" and f.severity == "error" for f in findings)
    assert "salvaguardam" in diagnostic


def test_altered_amount_detected_even_in_long_document(tmp_path):
    prose = "\n".join(f"Esta é a linha {i} do documento de teste." for i in range(35))
    original = "Cláusula 1.ª - Remuneração\n" + prose + "\nO montante é 1 250,00 EUR.\n"
    pdf = escrever_pdf(tmp_path / "teste.pdf", [pagina_bte(1, original.splitlines())])
    doc, text = estruturar(original, "teste")
    result, findings, _ = audit_pdf(pdf, text.replace("1 250,00", "1 260,00"), doc, text, 0)
    assert result["cobertura"] > 0.99
    assert result["amounts_missing"] == {"1250,00": 1}
    assert any(f.rule == "AMOUNTS" and f.severity == "error" for f in findings)


def test_numeric_column_not_joined_to_price_and_thousands_not_lost(tmp_path):
    pdf = escrever_pdf(
        tmp_path / "teste.pdf",
        [[(50, 700, "2"), (200, 700, "920,00"), (50, 650, "1 250,00"), (50, 600, "2.841,09")]],
    )
    assert pdf_amounts(pdf) == Counter({"920,00": 1, "1250,00": 1, "2841,09": 1})


def test_empty_independent_reference_never_certifies_completeness(tmp_path):
    pdf = escrever_pdf(tmp_path / "empty.pdf", [[]])
    doc, text = estruturar("Texto proveniente de OCR.", "teste")
    result, findings, _ = audit_pdf(pdf, text, doc, text, 0)
    assert any(f.rule == "REFERENCE_EMPTY" and f.severity == "error" for f in findings)


def test_percent_sign_and_negative_amount_cannot_disappear(tmp_path):
    for number, original, changed in (
        (1, 'O acréscimo é de 25% do total.', 'O acréscimo é de 25 do total.'),
        (2, 'O saldo é -125,00 euros.', 'O saldo é 125,00 euros.'),
        (3, 'A variação é -25%.', 'A variação é 25%.'),
        (4, 'O saldo é - 125,00 euros.', 'O saldo é 125,00 euros.'),
        (5, 'O prazo é < 25 dias.', 'O prazo é > 25 dias.'),
        (6, 'O saldo é –125,00 euros.', 'O saldo é 125,00 euros.'),
        (7, 'O saldo é —125,00 euros.', 'O saldo é 125,00 euros.'),
    ):
        pdf = escrever_pdf(tmp_path / f'simbolos{number}.pdf', [pagina_bte(1, [original])])
        doc, text = estruturar(original, 'teste')
        _, findings, _ = audit_pdf(pdf, changed, doc, text, 0)
        assert any(f.severity == 'error' and f.rule in {'CRITICAL_SYMBOLS', 'AMOUNTS'}
                   for f in findings)


def test_dash_in_another_table_cell_is_not_a_negative_number(tmp_path):
    pdf = escrever_pdf(tmp_path / 'cells.pdf', [[(50,700,'-'),(250,700,'1')]])
    doc, text = estruturar('- | 1', 'teste')
    _, findings, _ = audit_pdf(pdf, '- | 1', doc, text, 0)
    assert not any(f.rule == 'CRITICAL_SYMBOLS' for f in findings)


def test_same_line_table_dash_requires_geometric_proximity(tmp_path):
    # PDFium pode pôr as células na mesma linha, embora estejam muito afastadas.
    pdf = escrever_pdf(tmp_path / 'row.pdf', [[(50,700,'-'),(250,700,'1')]])
    doc, text = estruturar('- | 1', 'teste')
    _, findings, _ = audit_pdf(pdf, '- | 1', doc, text, 0, reference=(['- 1'], []))
    assert not any(f.rule == 'CRITICAL_SYMBOLS' for f in findings)


def test_negative_amount_spacing_normalization_remains_faithful(tmp_path):
    for index, source in enumerate(('- 125,00', '-1 250,00', '- 1 250,00')):
        normalized = source.replace(' ', '')
        original = f'O saldo é {source} euros.'
        pdf = escrever_pdf(tmp_path / f'negative{index}.pdf', [pagina_bte(1, [original])])
        doc, text = estruturar(original, 'teste')
        _, findings, _ = audit_pdf(pdf, f'O saldo é {normalized} euros.', doc, text, 0)
        assert not any(f.rule in {'AMOUNTS', 'CRITICAL_SYMBOLS'} for f in findings)
        _, findings, _ = audit_pdf(pdf, f'O saldo é {normalized[1:]} euros.', doc, text, 0)
        assert any(f.rule in {'AMOUNTS', 'CRITICAL_SYMBOLS'} for f in findings)


def test_formula_operators_preserved_across_spaces_and_pdf_line_wrap(tmp_path):
    pdf = escrever_pdf(tmp_path / 'formula.pdf', [[
        (72, 700, '2000,00 EUR - 1330,00 EUR = 670,00 EUR'),
        (510, 680, '+'), (72, 666, '1330,00 EUR'),
        (72, 640, '2000,00 EUR- 1640,00 EUR = 360,00 EUR'),
    ]])
    original = '2000,00 EUR -1330,00 EUR = 670,00 EUR +1330,00 EUR\n2000,00 EUR-1640,00 EUR = 360,00 EUR'
    doc, text = estruturar(original, 'formula')
    _, findings, _ = audit_pdf(pdf, text, doc, text, 0)
    assert not any(f.rule in {'AMOUNTS', 'CRITICAL_SYMBOLS'} for f in findings)
    damaged = text.replace('-1330,00', '1330,00')
    _, findings, _ = audit_pdf(pdf, damaged, doc, text, 0)
    assert any(f.rule in {'AMOUNTS', 'CRITICAL_SYMBOLS'} for f in findings)


def test_independent_checks_share_one_pdfplumber_read(tmp_path, monkeypatch):
    import pdfplumber
    pdf = escrever_pdf(tmp_path / 'shared.pdf', [pagina_bte(1, ['O saldo é -125,00 euros.'])])
    original_open = pdfplumber.open
    calls = []
    def counted(*args, **kwargs):
        calls.append(args[0])
        return original_open(*args, **kwargs)
    monkeypatch.setattr(pdfplumber, 'open', counted)
    doc, text = estruturar('O saldo é -125,00 euros.', 'shared')
    audit_pdf(pdf, text, doc, text, 0, reference=(['O saldo é -125,00 euros.'], []))
    assert calls == [pdf]


def test_small_salary_rows_and_parenthesized_thousands_are_not_truncated(tmp_path):
    pdf = escrever_pdf(tmp_path / 'small.pdf', [[
        (72, 700, '2 240,31', 'small'), (72, 694, '1 935,14', 'small'),
        (72, 650, 'Valor (1 604,41 EUR) e (1 130,72 EUR).'),
        (72, 620, 'Total 1 000 000,00 EUR.'),
        (72, 600, 'Valores 1 000,00 500,00 EUR.'),
    ]])
    assert pdf_amounts(pdf) == Counter({'2240,31': 1, '1935,14': 1, '1604,41': 1,
                                       '1130,72': 1, '1000000,00': 1, '1000,00': 1, '500,00': 1})


def test_cell_border_separates_dash_from_positive_amount(tmp_path):
    pdf = escrever_pdf(tmp_path / 'border.pdf', [
        grelha(50, 650, [20, 70], [25, 25]) + [
            (52, 685, 'X'), (75, 685, 'Valor'), (66, 660, '-'), (72, 660, '1,00')]])
    assert pdf_amounts(pdf) == Counter({'1,00': 1})


def test_wider_sign_gap_inside_same_drawn_cell_is_preserved(tmp_path):
    from crl_markdown.audit import pdf_signed_values
    pdf = escrever_pdf(tmp_path / 'percent.pdf', [
        grelha(50, 650, [120, 70], [25, 25]) + [
            (55, 685, 'Valor'), (180, 685, 'Nota'), (70, 660, '-'), (85, 660, '70 %')]])
    assert pdf_signed_values(pdf) == Counter({'-70': 1})


def test_dot_leaders_preserve_amounts_and_still_detect_a_changed_value(tmp_path):
    original = 'Almoço/jantar........8,50 EUR; total 1.250,00 EUR.'
    pdf = escrever_pdf(tmp_path / 'leaders.pdf', [pagina_bte(1, [original])])
    doc, text = estruturar(original, 'leaders')
    result, findings, _ = audit_pdf(pdf, text, doc, text, 0)
    assert amounts(original) == Counter({'8,50': 1, '1250,00': 1})
    assert result['amounts_missing'] == result['amounts_extra'] == {}
    assert not any(f.rule == 'AMOUNTS' for f in findings)
    result, findings, _ = audit_pdf(pdf, text.replace('8,50', '18,50'), doc, text, 0)
    assert result['amounts_missing'] == {'8,50': 1}
    assert result['amounts_extra'] == {'18,50': 1}
    assert any(f.rule == 'AMOUNTS' and f.severity == 'error' for f in findings)


def test_overlapping_space_cannot_truncate_the_pdf_numeric_reference(tmp_path):
    import pdfplumber
    # Um espaço escrito sobre o primeiro algarismo faz extract_words separar
    # «9» e «78,49», embora o PDF apresente um único 978,49 (caso ANACOM).
    pdf = escrever_pdf(tmp_path / 'overlapping.pdf', [[
        (50, 700, '1'), (70, 700, '9'), (75.5, 700, '78,49'), (70, 700, ' '),
    ]])
    with pdfplumber.open(pdf) as source:
        words = source.pages[0].dedupe_chars().extract_words(x_tolerance=1, y_tolerance=1)
        assert [w['text'] for w in words] == ['1', '9', '78,49']
    assert pdf_amounts(pdf) == Counter({'978,49': 1})
    doc, text = estruturar('1 | 978,49', 'overlapping')
    result, findings, _ = audit_pdf(pdf, text, doc, text, 0)
    assert not any(f.rule == 'AMOUNTS' for f in findings)
    result, findings, _ = audit_pdf(pdf, '1 | 78,49', doc, text, 0)
    assert result['amounts_missing'] == {'978,49': 1}
    assert result['amounts_extra'] == {'78,49': 1}


def test_numeric_overlap_never_joins_across_a_drawn_cell_boundary(tmp_path):
    pdf = escrever_pdf(tmp_path / 'boundary.pdf', [[
        (70, 700, '9'), (75.5, 700, '78,49'), (70, 700, ' '),
        ('traco', 75.53, 690, 75.53, 715),
    ]])
    assert pdf_amounts(pdf) == Counter({'78,49': 1})


def test_large_overlaps_are_not_interpreted_as_numeric_kerning(tmp_path):
    pdf = escrever_pdf(tmp_path / 'ambiguous.pdf', [[
        (70, 700, '9'), (73, 700, '78,49'), (70, 700, ' '),
    ]])
    assert pdf_amounts(pdf) == Counter({'78,49': 1})


def test_numeric_evidence_matches_complete_values_with_their_signs(tmp_path):
    original = ['O saldo é -500 euros.', 'O limite é 5000 euros.',
                'O almoço custa 8,50 euros.', 'O jantar custa 18,50 euros.',
                'O crédito é +500 euros.']
    pdf = escrever_pdf(tmp_path / 'evidence.pdf', [pagina_bte(1, original)])
    doc, text = estruturar('\n'.join(original), 'evidence')
    result, _, _ = audit_pdf(pdf, text.replace('-500', '').replace(' 8,50', ''), doc, text, 0)
    evidence = result['numeric_evidence']
    assert {value for item in evidence for value in item['values']} == {'-500', '8,50'}
    assert len(evidence) == 2
    assert all('5000' not in item['source_text'] and '18,50' not in item['source_text']
               and '+500' not in item['source_text'] for item in evidence)
