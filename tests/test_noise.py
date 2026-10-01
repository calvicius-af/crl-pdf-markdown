from types import SimpleNamespace

from docling_core.types.doc import BoundingBox, CoordOrigin, DocItemLabel, DoclingDocument

from crl_markdown.document import is_bte_margin_picture, prepare
from crl_markdown.legacy.completude import medir
from crl_markdown.textrepair import repair_wrapped


def test_wrapped_word_requires_independent_evidence_and_preserves_compounds():
    text = "com ex - ceção, tabe- la salarial, guarda-chuva e trabalhador - estudante."
    result = repair_wrapped(text, {"exceção", "tabela"})
    assert result == "com exceção, tabela salarial, guarda-chuva e trabalhador - estudante."
    assert repair_wrapped("ex - ceção", set()) == "ex - ceção"
    assert (
        repair_wrapped("1 - Remuneração; a - b; 1967 - 967", {"ab"})
        == "1 - Remuneração; a - b; 1967 - 967"
    )


def test_real_rendering_repairs_excecao_without_hiding_missing_words():
    doc = DoclingDocument(name="Convenção")
    doc.add_text(label=DocItemLabel.TEXT, text="Cláusula 1.ª - Promoções")
    doc.add_text(label=DocItemLabel.TEXT, text="Com ex - ceção de trabalhadores.")
    prepared = prepare(doc, "teste", reference_words={"exceção"})
    assert "Com exceção de trabalhadores." in prepared.markdown
    result = medir(
        "teste",
        ["Com exceção de trabalhadores. Direitos adquiridos."],
        "Com exceção de trabalhadores.",
    )
    assert not {"ex", "ceção"} & result.a_mais.keys()
    assert "exceção" not in result.em_falta
    assert result.em_falta["Direitos"] == 1


def test_furniture_excluded_but_body_citations_and_numbers_kept():
    body = "Publicado no Boletim do Trabalho e Emprego, n.º 21, de 8 de junho de 2025.\n123\nDireitos adquiridos.\nVigência do acordo."
    page = "Boletim do Trabalho e Emprego 31\n22 agosto 2026\n" + body + "\nBTE 31 | 34"
    result = medir("teste", [page], body)
    assert result.cobertura == 1 and not result.em_falta and not result.a_mais
    assert "31" not in result.palavras_referencia
    assert "123" in result.palavras_referencia and "Boletim" in result.palavras_referencia


def test_logo_requires_bte_context_small_size_and_header_position():
    box = BoundingBox(l=283, t=817, r=312, b=791, coord_origin=CoordOrigin.BOTTOMLEFT)
    prov = SimpleNamespace(page_no=1, bbox=box)
    picture = SimpleNamespace(prov=[prov])
    header = SimpleNamespace(text="Boletim do Trabalho e Emprego 31", prov=[prov])
    document = SimpleNamespace(
        pages={1: SimpleNamespace(size=SimpleNamespace(width=595, height=842))}, texts=[header]
    )
    assert is_bte_margin_picture(picture, document)
    document.texts = []
    assert not is_bte_margin_picture(picture, document)
    document.texts = [header]
    prov.bbox = BoundingBox(l=283, t=500, r=312, b=474, coord_origin=CoordOrigin.BOTTOMLEFT)
    assert not is_bte_margin_picture(picture, document)
    prov.bbox = BoundingBox(l=50, t=817, r=500, b=760, coord_origin=CoordOrigin.BOTTOMLEFT)
    assert not is_bte_margin_picture(picture, document)
