"""Regressão do pip ao receber file://localhost/C%24 numa pasta Windows UNC."""

import importlib.util
import nturl2path
from pathlib import Path, PureWindowsPath

import pytest

spec = importlib.util.spec_from_file_location(
    "launch_gui", Path(__file__).parents[1] / "scripts" / "launch_gui.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.mark.parametrize("path, expected", [
    (r"C:\profiles\CRL\pessoal\projeto", r"C:\profiles\CRL\pessoal\projeto"),
    (r"L:\CRL\projeto com espaços", r"L:\CRL\projeto com espaços"),
    (r"\\localhost\C$\profiles\CRL\pessoal\projeto",
     "file://127.0.0.1/C%24/profiles/CRL/pessoal/projeto"),
    (r"\\LOCALHOST\C$\projeto com espaços",
     "file://127.0.0.1/C%24/projeto%20com%20espa%C3%A7os"),
    (r"\\servidor\equipa\projeto", "file://servidor/equipa/projeto"),
])
def test_project_install_reference(path, expected):
    command = launcher.project_install_command("python.exe", PureWindowsPath(path))
    assert command == ["python.exe", "-m", "pip", "install", "-e", expected]


def test_pip_windows_roundtrip_preserves_administrative_share(monkeypatch):
    from pip._internal.utils import urls

    monkeypatch.setattr(urls, "WINDOWS", True)
    monkeypatch.setattr(urls.urllib.request, "url2pathname", nturl2path.url2pathname)
    root = PureWindowsPath(r"\\localhost\C$\profiles\CRL\pessoal\projeto com espaços")
    restored = urls.url_to_path(launcher.project_reference(root))
    assert PureWindowsPath(restored) == PureWindowsPath(
        r"\\127.0.0.1\C$\profiles\CRL\pessoal\projeto com espaços"
    )
    # O endereço anterior perde precisamente a partilha UNC.
    assert not urls.url_to_path(root.as_uri()).startswith("\\\\")
