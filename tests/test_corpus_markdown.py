"""Regressões de Markdown nos 14 PDFs reais; falhas conhecidas ficam bloqueadas."""

import hashlib
import json
import os
import re
from pathlib import Path

import pytest

from crl_markdown.cache import CachedConverter
from crl_markdown.pipeline import Options, convert_pdf
from crl_markdown.quality import cells, lint

ROOT = Path(__file__).parent / "corpus"
CASES = json.loads((ROOT / "manifesto.json").read_text("utf-8"))["documentos"]
EXPECTED = json.loads((ROOT / "expectativas.json").read_text("utf-8"))


@pytest.mark.skipif(
    not os.environ.get("CRL_TEST_CORPUS") or not os.environ.get("CRL_TEST_CACHE"),
    reason="Indicar CRL_TEST_CORPUS e CRL_TEST_CACHE para testar os PDFs reais",
)
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"] + " " + case["motivo"][:48])
def test_problematic_pdf_keeps_structure_content_and_quality_gate(case, tmp_path):
    pdf = Path(os.environ["CRL_TEST_CORPUS"]) / (case["nome"] + ".pdf")
    assert pdf.exists(), f"PDF obrigatório em falta: {case['nome']}"
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == case["sha256"]
    converter = CachedConverter(Path(os.environ["CRL_TEST_CACHE"]))
    target = tmp_path / (case["nome"] + ".md")
    report = convert_pdf(pdf, target, converter, Options())
    markdown = target.read_text("utf-8")
    expected = EXPECTED[case["nome"]]
    assert report["structure"]["clauses"] == expected["clauses"]
    assert report["structure"]["annexes"] == expected["annexes"]
    assert report["completeness"]["cobertura"] >= expected["minimum_coverage"]
    assert report["completeness"]["audited_content"] == "final_markdown_visible_text"
    assert not any(f.rule in {"MD001", "MD056", "TABLE_UNPARSED"} for f in lint(markdown))
    assert "## Preâmbulo" in markdown
    assert not re.search(r"(?m)^[-•]\s+\d+[-.)]", markdown)
    assert not re.search(r"(?m)^[-•]\s+[a-z]\)", markdown)
    rows = []
    for line in markdown.splitlines():
        if line.startswith("|"):
            rows.append(cells(line))
        elif rows:
            assert len({len(row) for row in rows}) == 1
            rows = []
    if rows:
        assert len({len(row) for row in rows}) == 1
    if "_381_" in case["nome"]:
        assert (
            "Cláusula 68.ª - Organização de serviços de segurança, higiene e saúde no trabalho"
            in markdown
        )
    if "_382_" in case["nome"]:
        assert all(re.search(r"(?m)^" + marker + r"\) ", markdown) for marker in "ghimn")
        assert "ANEXO III - Maia" not in markdown
    if "_383_" in case["nome"]:
        assert "Cláusula 42.ª - Mudança de categoria/formas de recrutamento" in markdown
        assert "a) Designação e conteúdo funcional" in markdown
        assert "d) Data-limite de apresentação de candidaturas." in markdown
    if "_385_" in case["nome"]:
        assert "Cláusula 33.ª - (Prémio de permanência)" in markdown
    # Estes casos não podem parecer prontos quando as tabelas continuam ambíguas.
    if any(
        "_" + number + "_" in case["nome"]
        for number in ("382", "384", "385", "387", "388", "389", "390")
    ):
        assert report["quality_status"] == "blocked"
        assert any(f["rule"] == "TABLE_OVERLAP" for f in report["findings"])
