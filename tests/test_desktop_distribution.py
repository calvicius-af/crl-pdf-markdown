"""Contratos da configuração persistente, apoio e runtime distribuído."""

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

from crl_markdown import settings
from crl_markdown.diagnostics import export_support


def test_settings_survive_restart_and_unavailable_source(tmp_path):
    values = settings.defaults(tmp_path / "Dados com acentos á")
    # A origem não precisa de estar ligada no momento de guardar.
    values["originals"] = str(tmp_path / "partilha indisponível" / "originais")
    config = tmp_path / "perfil" / "pastas.json"
    settings.save(values, config)
    assert settings.load(config) == values
    assert not Path(values["originals"]).exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Semântica de caminhos Windows")
def test_mapped_drive_spelling_is_preserved(tmp_path):
    values = settings.defaults(tmp_path / "dados")
    values["indices"] = "L:\\Índices CRL"
    config = tmp_path / "pastas.json"
    settings.save(values, config)
    assert settings.load(config)["indices"] == values["indices"]


def test_failed_settings_write_preserves_previous_choice(tmp_path, monkeypatch):
    config = tmp_path / "pastas.json"
    previous = settings.defaults(tmp_path / "antes")
    settings.save(previous, config)

    def deny(*args):
        raise PermissionError("sem escrita")

    monkeypatch.setattr(Path, "replace", deny)
    with pytest.raises(PermissionError):
        settings.save(settings.defaults(tmp_path / "depois"), config)
    assert settings.load(config) == previous
    assert list(tmp_path.iterdir()) == [config]


def test_settings_refuse_program_folder_and_incomplete_data(tmp_path):
    values = settings.defaults(tmp_path / "dados")
    values["markdown"] = str(Path(sys.base_prefix) / "dados")
    with pytest.raises(ValueError, match="fora da pasta do programa"):
        settings.save(values, tmp_path / "pastas.json")
    with pytest.raises(ValueError, match="cinco pastas"):
        settings.validate({"markdown": str(tmp_path)})


def test_support_zip_keeps_traceback_and_redacts_secrets_without_pdf(tmp_path):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"private PDF")
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"error": "token=SEGREDO_SENTINELA_123"}', encoding="utf-8")
    try:
        raise PermissionError("acesso recusado: password=SENHA_SENTINELA_456")
    except PermissionError as error:
        target = tmp_path / "apoio.zip"
        export_support(target, error=error, attachments=[source, manifest], log="token=TOKEN_SENTINELA_789")
    with zipfile.ZipFile(target) as archive:
        data = json.loads(archive.read("apoio.json"))
        assert data["code"] == "CRL-PERMISSOES"
        assert "PermissionError" in data["traceback"]
        assert not any(name.endswith(".pdf") for name in archive.namelist())
        all_text = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist())
        assert all(value not in all_text for value in (
            "SENHA_SENTINELA_456", "SEGREDO_SENTINELA_123", "TOKEN_SENTINELA_789", "private PDF"))


def test_runtime_copy_excludes_builder_packages_but_keeps_tk_and_dlls(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("montar_windows", scripts / "montar_windows.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "python-builder"
    source.mkdir()
    for name in ("python.exe", "pythonw.exe", "python313.dll", "vcruntime140.dll", "LICENSE.txt"):
        (source / name).write_bytes(b"runtime fixture")
    for name in ("Lib/site-packages/foreign", "Lib/tkinter", "DLLs", "tcl/tcl8.6"):
        folder = source / name
        folder.mkdir(parents=True)
        (folder / "resource").write_bytes(b"resource fixture")
    destination = tmp_path / "runtime"
    module.runtime_files(source, destination)
    assert not (destination / "Lib/site-packages").exists()
    assert (destination / "Lib/tkinter/resource").is_file()
    assert (destination / "tcl/tcl8.6/resource").is_file()
    assert str(source) not in (destination / "python313._pth").read_text()


def test_custom_named_folder_is_used_without_relocating_assigned_files(tmp_path):
    from crl_markdown.naming import execute_records, key
    from crl_markdown.workspace import initialize
    from tests.test_rnc import _registry_for_naming

    records = _registry_for_naming(tmp_path)
    root = initialize(tmp_path / "RNC")
    named = tmp_path / "PDFs nomeados"
    table = {key(s): s for s in ["ACRAL", "CESP", "STRUP"]}
    result = execute_records(records, root, table, {}, apply=True, named_root=named)
    assert result[0]["estado"] == "nomeado"
    target = next(named.rglob("*.pdf"))
    assert not list((root / "1_fontes").rglob("*.pdf"))
    # Alterar a configuração não migra os documentos já registados.
    elsewhere = tmp_path / "nova pasta"
    again = execute_records(records, root, table, {}, apply=True, named_root=elsewhere)
    assert again[0]["estado"] == "nomeado"
    assert target.is_file() and not elsewhere.exists()
