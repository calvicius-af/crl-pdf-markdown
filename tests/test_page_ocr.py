import hashlib
import json
from types import SimpleNamespace

import pytest
from docling_core.types.doc import BoundingBox, DocItemLabel, DoclingDocument, ProvenanceItem, Size

from crl_markdown.page_ocr import PageOCRConverter, PageOCROptions, parse_pages


def cache_fixture(tmp_path, *, crossing=False):
    pdf = tmp_path / 'source.pdf'
    pdf.write_bytes(b'fixture')
    document = DoclingDocument(name='Original')
    for page in range(1, 4):
        document.add_page(page_no=page, size=Size(width=595, height=842))
        item = document.add_text(label=DocItemLabel.TEXT, text=f'Texto original {page}',
            prov=ProvenanceItem(page_no=page, bbox=BoundingBox(l=10, t=20, r=100, b=10), charspan=(0, 16)))
        if page == 1 and crossing:
            item.prov.append(ProvenanceItem(page_no=2, bbox=BoundingBox(l=10, t=20, r=100, b=10), charspan=(0, 16)))
    cache = tmp_path / 'cache'
    cache.mkdir()
    path = cache / 'source.docling.json'
    path.write_text(json.dumps(document.export_to_dict()))
    (cache / 'source.qualidade.json').write_text(json.dumps({
        'source_sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
        'docling_document_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'docling_version': 'test', 'options': {'ocr': False},
    }))
    return pdf, cache, document


def test_only_selected_page_is_reextracted_and_other_pages_are_identical(tmp_path, monkeypatch):
    monkeypatch.setattr('crl_markdown.page_ocr.version', lambda _: 'test')
    pdf, cache, document = cache_fixture(tmp_path)
    calls = []
    def native(source, *, page_range):
        calls.append((source, page_range))
        result = document.filter(page_nrs={2})
        result.texts[0].text = 'Texto obtido por OCR'
        return SimpleNamespace(status='success', document=result)
    converter = PageOCRConverter(PageOCROptions(ocr=True, selected_pages=(2,), cache_directory=str(cache)),
                                 SimpleNamespace(convert=native))
    result = converter.convert(pdf).document
    assert calls == [(pdf, (2, 2))]
    assert [(t.text, t.prov[0].page_no) for t in result.texts] == [
        ('Texto original 1', 1), ('Texto obtido por OCR', 2), ('Texto original 3', 3)]
    assert converter.extraction_options['reused_pages'] == [1, 3]


def test_crossing_elements_are_not_silently_cut(tmp_path, monkeypatch):
    monkeypatch.setattr('crl_markdown.page_ocr.version', lambda _: 'test')
    pdf, cache, _document = cache_fixture(tmp_path, crossing=True)
    converter = PageOCRConverter(PageOCROptions(ocr=True, selected_pages=(2,), cache_directory=str(cache)),
                                 SimpleNamespace(convert=lambda *a, **k: None))
    with pytest.raises(ValueError, match='atravessa páginas'):
        converter.convert(pdf)


@pytest.mark.parametrize('text', ['0', '4', '3-2', '1-100000000', 'um', '1,,2'])
def test_invalid_page_range_fails_before_extraction(text):
    with pytest.raises(ValueError):
        parse_pages(text, 3)


def test_page_ranges_are_deduplicated():
    assert parse_pages('1,2-3,2', 3) == [1, 2, 3]
