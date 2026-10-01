import json

import pytest

from crl_markdown.cache import CachedConverter
from crl_markdown.pipeline import Options, convert_pdf
from tests.test_pipeline import converter  # noqa: F401 — fixture reutilizada


def test_cached_extraction_checks_pdf_and_document_hash(tmp_path, converter):  # noqa: F811
    pdf = tmp_path / "exemplo.pdf"
    pdf.write_bytes(b"fixture")
    convert_pdf(pdf, tmp_path / "out/exemplo.md", converter, Options())
    cache = CachedConverter(tmp_path / "out")
    report = convert_pdf(pdf, tmp_path / "new/exemplo.md", cache, Options())
    assert report["cached_extraction"] is True
    pdf.write_bytes(b"alterado")
    with pytest.raises(ValueError, match="hash"):
        cache.convert(pdf)
    pdf.write_bytes(b"fixture")
    path = tmp_path / "out/_auditoria/exemplo.docling.json"
    document = json.loads(path.read_text("utf-8"))
    document["name"] = "alterado"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="alterada"):
        cache.convert(pdf)
