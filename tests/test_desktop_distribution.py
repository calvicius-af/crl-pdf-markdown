"""Contratos da configuração persistente, apoio e runtime distribuído."""

import gc
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

from crl_markdown import settings
from crl_markdown.diagnostics import export_support


@pytest.fixture(autouse=True)
def collect_destroyed_tk_windows_on_main_thread():
    # Each GUI test owns a new Tcl interpreter. Collect the previous test's
    # callback cycles here, before a worker can trigger GC on another thread.
    gc.collect()
    yield
    gc.collect()


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
    crt = tmp_path / "Microsoft.VC143.CRT"
    crt.mkdir()
    (crt / "msvcp140.dll").write_bytes(b"CRT fixture")
    with pytest.raises(ValueError, match="CRT incompleta"):
        module.copy_cpp_runtime(destination, crt)
    for name in ("vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll"):
        (crt / name).write_bytes(b"CRT fixture")
    module.copy_cpp_runtime(destination, crt)
    assert (destination / "msvcp140.dll").read_bytes() == b"CRT fixture"


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


@pytest.mark.skipif(sys.platform != "win32", reason="Ensaio da interface do instalador Windows")
def test_first_window_saves_folders_and_conversion_uses_them(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import ttk

    from crl_markdown import app

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Sem ambiente gráfico para o ensaio Tk")
    root.withdraw()
    monkeypatch.setattr(app.tk, "Tk", lambda: root)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "perfil"))
    resources = tmp_path / "recursos"
    resources.mkdir()
    (resources / "smoke.pdf").write_bytes(b"PDF fixture; converter replaced in UI test")
    values = settings.defaults(tmp_path / "dados")
    calls, failures = [], []

    def conversion(source, output, options, **kwargs):
        calls.append((source, output, options))
        return []

    monkeypatch.setattr(app, "run", conversion)

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    def click(text):
        button = next(child for child in descendants(root)
                      if isinstance(child, ttk.Button) and child.cget("text") == text)
        button.invoke()

    def finish():
        try:
            assert calls
            assert calls[0][0] == resources / "smoke.pdf"
            assert calls[0][1] == Path(values["markdown"])
            assert calls[0][2].offline and calls[0][2].models == resources / "modelos"
            assert settings.load() == values
        except BaseException as error:
            failures.append(error)
        finally:
            root.destroy()

    def configure():
        try:
            window = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
            entries = [child for child in descendants(window) if isinstance(child, ttk.Entry)]
            assert len(entries) == 5
            for entry, value in zip(entries, values.values()):
                entry.delete(0, "end")
                entry.insert(0, value)
            click("Guardar e continuar")
            # Aguardar o retorno de wait_window para aplicar a configuração.
            root.after(50, convert)
        except BaseException as error:
            failures.append(error)
            root.destroy()

    def convert():
        try:
            click("Usar PDF de teste incluído")
            click("Construir Markdown")
            root.after(250, finish)
        except BaseException as error:
            failures.append(error)
            root.destroy()

    # Dispara já dentro do wait_window da primeira configuração.
    root.after(200, configure)
    root.after(5000, lambda: (failures.append(AssertionError("Interface não terminou")), root.destroy()))
    app.main(["--installed", "--offline", "--models", str(resources / "modelos")])
    if failures:
        raise failures[0]


@pytest.mark.skipif(sys.platform != "win32", reason="Janela de erro de arranque Windows")
def test_startup_error_is_visible_with_hidden_root():
    import tkinter as tk

    from crl_markdown.diagnostics import support_dialog

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Sem ambiente gráfico")
    root.withdraw()
    visible = []

    def inspect():
        window = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
        visible.append(window.winfo_viewable())
        window.destroy()

    root.after(300, inspect)
    try:
        support_dialog(root, ImportError("biblioteca em falta"), "Abrir CRL")
    finally:
        root.destroy()
    assert visible == [True]


@pytest.mark.skipif(sys.platform != "win32", reason="Disposição da janela Windows")
def test_controls_fit_narrow_window_in_both_tabs(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import ttk

    from crl_markdown import app

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Sem ambiente gráfico")
    monkeypatch.setattr(app.tk, "Tk", lambda: root)
    monkeypatch.setattr(settings, "load", lambda: settings.defaults(tmp_path / "dados"))
    checked = []

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    def inspect():
        root.geometry("750x600")
        # Native Windows map/configure events need the regular event loop too.
        root.update()
        notebook = next(w for w in descendants(root) if isinstance(w, ttk.Notebook))
        try:
            for tab in (0, 1):
                notebook.select(tab)
                root.update()
                assert notebook.winfo_ismapped()
                for widget in descendants(root):
                    if isinstance(widget, ttk.Button) and widget.winfo_ismapped():
                        assert widget.winfo_reqwidth() <= widget.winfo_width()
                        assert widget.winfo_rootx() >= root.winfo_rootx()
                        assert widget.winfo_rootx() + widget.winfo_width() <= root.winfo_rootx() + root.winfo_width()
                        assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height()
                log = next(w for w in descendants(root) if isinstance(w, tk.Text))
                assert log.winfo_height() >= 60
                checked.append(tab)
        finally:
            root.destroy()

    monkeypatch.setattr(root, "mainloop", inspect)
    app.main(["--installed", "--offline", "--models", str(tmp_path / "recursos/modelos")])
    assert checked == [0, 1]


@pytest.mark.skipif(sys.platform != "win32", reason="Relatório da operação atual na GUI Windows")
def test_success_after_failure_does_not_export_the_old_error(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import ttk

    from crl_markdown import app, diagnostics

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Sem ambiente gráfico")
    root.withdraw()
    monkeypatch.setattr(app.tk, "Tk", lambda: root)
    monkeypatch.setattr(settings, "load", lambda: settings.defaults(tmp_path / "dados"))
    resources = tmp_path / "recursos"
    resources.mkdir()
    (resources / "smoke.pdf").write_bytes(b"UI test fixture")
    target = tmp_path / "apoio.zip"
    monkeypatch.setattr(app.filedialog, "asksaveasfilename", lambda **kwargs: str(target))
    monkeypatch.setattr(app.messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(diagnostics, "support_dialog", lambda *args: None)
    calls, failures = [], []

    def run(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("ERRO_ANTIGO_SENTINELA")
        return []

    monkeypatch.setattr(app, "run", run)

    def widgets(parent):
        for child in parent.winfo_children():
            yield child
            yield from widgets(child)

    def button(text):
        return next(w for w in widgets(root) if isinstance(w, ttk.Button) and w.cget("text") == text)

    def start():
        button("Usar PDF de teste incluído").invoke()
        button("Construir Markdown").invoke()
        root.after(50, continue_test)

    def continue_test():
        try:
            if button("Construir Markdown").instate(["disabled"]):
                root.after(50, continue_test)
                return
            if len(calls) == 1:
                button("Construir Markdown").invoke()
                root.after(50, continue_test)
                return
            button("Guardar relatório para o apoio").invoke()
            with zipfile.ZipFile(target) as archive:
                data = json.loads(archive.read("apoio.json"))
                assert "traceback" not in data and "problem" not in data
                assert not any("falha-" in name for name in archive.namelist())
            root.destroy()
        except BaseException as error:
            failures.append(error)
            root.destroy()

    root.after(100, start)
    root.after(15000, lambda: (failures.append(AssertionError(
        f"A GUI não terminou; operações iniciadas: {len(calls)}")), root.destroy()))
    app.main(["--installed", "--offline", "--models", str(resources / "modelos")])
    if failures:
        raise failures[0]
