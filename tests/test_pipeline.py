import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from crl_markdown import pipeline
from crl_markdown.cli import main
from crl_markdown.pipeline import Options, apply_offline, convert_pdf, discover, run


@pytest.fixture
def converter(monkeypatch):
    from docling_core.types.doc import DocItemLabel, DoclingDocument, TableCell, TableData

    monkeypatch.setattr("crl_markdown.pipeline.version", lambda _: "test")
    doc = DoclingDocument(name="Convenção")
    doc.add_text(label=DocItemLabel.TITLE, text="Convenção")
    doc.add_text(label=DocItemLabel.TEXT, text="Cláusula 1.ª — Retribuição de 1 250,00 €.")
    values = [["Categoria", "Valor"], ["Técnico", "1 250,00 €"]]
    table_cells = [
        TableCell(
            text=text,
            column_header=row == 0,
            start_row_offset_idx=row,
            end_row_offset_idx=row + 1,
            start_col_offset_idx=col,
            end_col_offset_idx=col + 1,
        )
        for row, values_row in enumerate(values)
        for col, text in enumerate(values_row)
    ]
    doc.add_table(data=TableData(num_rows=2, num_cols=2, table_cells=table_cells))
    return SimpleNamespace(
        convert=lambda _: SimpleNamespace(status=SimpleNamespace(value="success"), document=doc)
    )


def test_actual_docling_export_and_audit(tmp_path, converter):
    pdf = tmp_path / "entrada.pdf"
    pdf.write_bytes(b"fixture")
    target = tmp_path / "out" / "entrada.md"
    report = convert_pdf(pdf, target, converter, Options())
    text = target.read_text(encoding="utf-8")
    assert "Técnico" in text and "1 250,00 €" in text
    assert report["tables"] == 1
    assert len(report["source_sha256"]) == 64
    saved = json.loads((target.parent / "_auditoria/entrada.qualidade.json").read_text("utf-8"))
    assert saved == report
    assert (target.parent / "_auditoria/entrada.docling.md").exists()
    assert not list(target.parent.rglob("*.qdpx"))
    with pytest.raises(FileExistsError):
        convert_pdf(pdf, target, converter, Options())


def test_partial_conversion_never_published(tmp_path):
    pdf = tmp_path / "entrada.pdf"
    pdf.write_bytes(b"fixture")
    converter = SimpleNamespace(convert=lambda _: SimpleNamespace(status="partial_success"))
    target = tmp_path / "out" / "entrada.md"
    with pytest.raises(RuntimeError, match="incompleta"):
        convert_pdf(pdf, target, converter, Options())
    assert not target.exists()


def test_missing_title_identified_and_empty_export_rejected(tmp_path, converter):
    from docling_core.types.doc import DocItemLabel, DoclingDocument

    pdf = tmp_path / "Origem_exemplo.pdf"
    pdf.write_bytes(b"fixture")
    doc = DoclingDocument(name="sem título")
    doc.add_text(label=DocItemLabel.TEXT, text="Conteúdo extraído.")
    converter.convert = lambda _: SimpleNamespace(status="success", document=doc)
    report = convert_pdf(pdf, tmp_path / "out/doc.md", converter, Options())
    assert report["title_from_filename"] is True
    assert (tmp_path / "out/doc.md").read_text("utf-8").startswith("# Origem exemplo\n")
    converter.convert = lambda _: SimpleNamespace(
        status="success", document=DoclingDocument(name="empty")
    )
    with pytest.raises(RuntimeError, match="não extraiu"):
        convert_pdf(pdf, tmp_path / "out/empty.md", converter, Options())
    assert not (tmp_path / "out/empty.md").exists()


def test_merged_cell_warning(tmp_path, converter):
    pdf = tmp_path / "entrada.pdf"
    pdf.write_bytes(b"fixture")
    converter.convert(pdf).document.tables[0].data.table_cells[0].col_span = 2
    report = convert_pdf(pdf, tmp_path / "out/doc.md", converter, Options())
    assert "TABLE_SPAN" in [finding["rule"] for finding in report["findings"]]


def test_batch_nested_paths_and_continues_on_failure(tmp_path, converter):
    inputs = tmp_path / "inputs"
    (inputs / "nested").mkdir(parents=True)
    (inputs / "bad.pdf").write_bytes(b"bad")
    (inputs / "nested/good.PDF").write_bytes(b"good")
    original = converter.convert

    def convert(path):
        if path.name == "bad.pdf":
            raise RuntimeError("PDF inválido")
        return original(path)

    converter.convert = convert
    reports = run(inputs, tmp_path / "out", Options(), converter=converter, progress=lambda _: None)
    assert [r["state"] for r in reports][0] == "falhou"
    assert (tmp_path / "out/nested/good.md").exists()


def test_case_collisions_rejected(tmp_path, converter):
    (tmp_path / "same.pdf").touch()
    (tmp_path / "same.PDF").touch()
    if len(discover(tmp_path)) != 2:
        pytest.skip("Filesystem ignores case")
    with pytest.raises(ValueError, match="colidem"):
        run(tmp_path, tmp_path / "out", Options(), converter=converter)


@pytest.mark.parametrize("initial", [None, "0", "1"])
def test_offline_mode_does_not_persist_between_runs(monkeypatch, initial):
    # A interface corre várias conversões no mesmo processo: desmarcar o modo
    # offline tem de repor o ambiente com que a sessão arrancou.
    constants = SimpleNamespace(HF_HUB_OFFLINE=False)
    monkeypatch.setitem(sys.modules, "huggingface_hub.constants", constants)
    monkeypatch.setattr(
        pipeline, "INITIAL_OFFLINE_ENV", {key: initial for key in pipeline.OFFLINE_KEYS}
    )
    for key in pipeline.OFFLINE_KEYS:
        if initial is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, initial)

    apply_offline(True)
    assert all(os.environ[key] == "1" for key in pipeline.OFFLINE_KEYS)
    assert constants.HF_HUB_OFFLINE is True

    apply_offline(False)
    assert all(os.environ.get(key) == initial for key in pipeline.OFFLINE_KEYS)
    assert constants.HF_HUB_OFFLINE is (initial == "1")


def test_cli_lint_exit_codes(tmp_path):
    path = tmp_path / "documento.md"
    path.write_text("# Título\n\n### Cláusula\n", encoding="utf-8")
    assert main(["lint", str(path)]) == 0
    assert main(["lint", str(path), "--strict"]) == 2
    path.write_text("| A | B |\n", encoding="utf-8")
    assert main(["lint", str(path)]) == 1
    assert main(["lint", str(tmp_path / "missing.md")]) == 1


@pytest.mark.skipif(not os.environ.get("CRL_TEST_MODELS"), reason="Modelos locais não indicados")
def test_real_pdf_conversion(tmp_path):
    from crl_markdown.pipeline import make_converter
    from tests.pdf_sintetico import escrever_pdf, grelha

    lines = [
        (50, 780, "CONVENCAO DE TESTE"),
        (50, 740, "Texto para importacao no MAXQDA."),
        (60, 675, "Categoria"),
        (260, 675, "Valor"),
        (60, 640, "Tecnico"),
        (260, 640, "1250,00 EUR"),
        (60, 605, "Auxiliar"),
        (260, 605, "1000,00 EUR"),
    ]
    lines += grelha(50, 590, [200, 200], [35, 35, 35])
    pdf = escrever_pdf(tmp_path / "teste.pdf", [lines])
    options = Options(models=Path(os.environ["CRL_TEST_MODELS"]), offline=True)
    report = convert_pdf(pdf, tmp_path / "out/teste.md", make_converter(options), options)
    text = (tmp_path / "out/teste.md").read_text("utf-8")
    assert report["tables"] >= 1
    assert "1250,00" in text and "1000,00" in text
    assert "MAXQDA" in text
