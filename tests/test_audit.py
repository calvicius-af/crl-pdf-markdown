from collections import Counter

from crl_markdown.audit import amounts, audit_pdf, pdf_amounts
from crl_markdown.legacy.extractor import estruturar
from tests.pdf_sintetico import escrever_pdf, pagina_bte


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
