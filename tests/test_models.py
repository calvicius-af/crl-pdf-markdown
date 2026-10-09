import json
from pathlib import Path

import pytest

from crl_markdown import models
from crl_markdown.cli import main
from crl_markdown.pipeline import Options, check_models


def _model_folder(root: Path, *, ocr=True) -> Path:
    folder = root / "modelos"
    layout = folder / "docling-project--docling-layout-heron"
    layout.mkdir(parents=True)
    (layout / "model.safetensors").write_bytes(b"pesos do layout")
    if ocr:
        rapid = folder / models.OCR_FOLDER / "torch" / "PP-OCRv6"
        rapid.mkdir(parents=True)
        (rapid / "rec.pth").write_bytes(b"pesos do OCR")
    return folder


def test_manifest_detects_missing_changed_and_extra_files(tmp_path):
    folder = _model_folder(tmp_path)
    manifest = models.write_inventory(folder)
    assert manifest["ocr"] == "torch:iso:pt"
    assert {f["path"] for f in manifest["files"]} == {
        "docling-project--docling-layout-heron/model.safetensors",
        "RapidOcr/torch/PP-OCRv6/rec.pth",
    }
    assert models.verify(folder) == []

    (folder / "docling-project--docling-layout-heron" / "model.safetensors").write_bytes(b"x")
    (folder / "RapidOcr" / "torch" / "PP-OCRv6" / "rec.pth").unlink()
    (folder / "extra.bin").write_bytes(b"?")
    problems = models.verify(folder)
    assert any(p.startswith("alterado") and "model.safetensors" in p for p in problems)
    assert any(p.startswith("em falta") and "rec.pth" in p for p in problems)
    assert any(p.startswith("a mais") and "extra.bin" in p for p in problems)


def test_verify_without_manifest_says_what_to_do(tmp_path):
    problems = models.verify(_model_folder(tmp_path))
    assert len(problems) == 1 and "inventory" in problems[0]


def test_models_cli(tmp_path, monkeypatch, capsys):
    folder = _model_folder(tmp_path)
    assert main(["models", "verify", "--folder", str(folder)]) == 1
    assert main(["models", "inventory", "--folder", str(folder)]) == 0
    assert main(["models", "verify", "--folder", str(folder)]) == 0
    assert "OK" in capsys.readouterr().out

    def fake_download(destination):
        return _model_folder(destination)

    monkeypatch.setattr(models, "download", fake_download)
    target = tmp_path / "nova"
    assert main(["models", "download", "--dest", str(target)]) == 0
    manifest = json.loads((target / "modelos" / models.MANIFEST).read_text("utf-8"))
    assert len(manifest["files"]) == 2


@pytest.mark.parametrize(
    "options, message",
    [
        (lambda folder: Options(ocr=True, offline=True), "requer a pasta de modelos"),
        (lambda folder: Options(ocr=True, models=folder, offline=True), "modelos do OCR"),
    ],
)
def test_ocr_offline_refused_without_ocr_models(tmp_path, options, message):
    # O OCR automático do Docling escolhe o motor pelo que está instalado e, em
    # modo offline, ia buscar à rede os modelos que não estavam na pasta.
    folder = _model_folder(tmp_path, ocr=False)
    with pytest.raises(ValueError, match=message):
        check_models(options(folder))


def test_models_checked_against_manifest_before_conversion(tmp_path):
    folder = _model_folder(tmp_path)
    models.write_inventory(folder)
    check_models(Options(ocr=True, models=folder, offline=True))
    (folder / "RapidOcr" / "torch" / "PP-OCRv6" / "rec.pth").write_bytes(b"cortado")
    with pytest.raises(ValueError, match="não correspondem ao manifesto"):
        check_models(Options(models=folder, offline=True))


def test_without_ocr_no_ocr_models_needed(tmp_path):
    check_models(Options(models=_model_folder(tmp_path, ocr=False), offline=True))
    check_models(Options(offline=True))


def test_converter_uses_fixed_portuguese_ocr_engine(tmp_path):
    pytest.importorskip("docling")
    from docling.datamodel.base_models import InputFormat

    from crl_markdown.pipeline import make_converter

    converter = make_converter(Options(ocr=True, models=_model_folder(tmp_path), offline=True))
    ocr = converter.format_to_options[InputFormat.PDF].pipeline_options.ocr_options
    assert (ocr.kind, ocr.backend) == ("rapidocr", "torch")
    # O Docling normaliza a etiqueta (iso:pt → iso:pt-Latn).
    assert len(ocr.lang) == 1 and ocr.lang[0].startswith("iso:pt")
