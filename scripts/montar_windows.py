"""Só para quem distribui: montar Python/Tk, wheels e modelos antes de compilar."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from instalar_offline import install_command, sha256, verify


def runtime_files(source, destination):
    """Copiar a distribuição CPython completa; dependências vêm só das wheels fixadas."""
    for name in ("python.exe", "pythonw.exe", "python313.dll", "vcruntime140.dll", "LICENSE.txt"):
        if not (source / name).is_file():
            raise ValueError(f"Python de preparação incompleto: falta {name}.")
    for name in ("Lib", "DLLs", "tcl"):
        if not (source / name).is_dir():
            raise ValueError(f"Python de preparação sem {name}; use CPython completo com Tcl/Tk.")
    destination.mkdir()
    for path in source.iterdir():
        if path.is_file() and (path.suffix.lower() == ".dll" or path.name in (
                "python.exe", "pythonw.exe", "LICENSE.txt")):
            shutil.copy2(path, destination / path.name)
    for name in ("Lib", "DLLs", "tcl"):
        shutil.copytree(source / name, destination / name,
                        ignore=shutil.ignore_patterns("site-packages", "__pycache__", "test", "tests"))
    # A localização do runtime não depende do registo, PATH ou outro Python.
    (destination / "python313._pth").write_text(
        ".\nLib\nDLLs\nLib/site-packages\nimport site\n", encoding="ascii")


def build(package, destination):
    if sys.platform != "win32" or platform.machine().lower() != "amd64" or sys.version_info[:2] != (3, 13):
        raise ValueError("Preparar em Windows x64, com CPython 3.13 completo.")
    manifest = verify(package)
    if not manifest["ocr"]:
        raise ValueError("A distribuição completa exige também os modelos OCR.")
    if destination.exists():
        raise ValueError("Escolha uma pasta nova para a distribuição.")
    destination.mkdir(parents=True)
    runtime = destination / "python"
    runtime_files(Path(sys.base_prefix), runtime)
    resources = destination / "recursos"
    resources.mkdir()
    for name in ("modelos", "vocabularios"):
        shutil.copytree(package / name, resources / name)
    for name in ("smoke.pdf", "siglas.csv", "siglas.manifest.json"):
        shutil.copy2(package / name, resources / name)
    root = Path(__file__).resolve().parents[1]
    shutil.copy2(root / "LICENSE", destination / "LICENCA-CRL.txt")
    shutil.copy2(root / "docs/operacao/instalacao-windows.md", destination / "LEIA-PRIMEIRO.md")
    python = runtime / "python.exe"
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("PYTHON", "PIP_"))}
    environment.update(PIP_CONFIG_FILE=os.devnull, PIP_NO_INDEX="1",
                       PIP_DISABLE_PIP_VERSION_CHECK="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    commands = [[str(python), "-I", "-m", "ensurepip"], install_command(python, package),
                [str(python), "-I", "-m", "pip", "check"]]
    for command in commands:
        subprocess.run(command, env=environment, cwd=resources, check=True, timeout=1800)
    (destination / "distribuicao.json").write_text(json.dumps({
        "schema": 1, "version": manifest["versions"]["crl-pdf-markdown"],
        "python": platform.python_version(), "versions": manifest["versions"],
        "source_revision": manifest.get("source_revision"), "validation": "candidato_por_validar",
        "files": {path.relative_to(destination).as_posix(): sha256(path)
                  for path in sorted(destination.rglob("*")) if path.is_file()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Runtime pronto. Executar release_check após mudar de pasta; só depois compilar o instalador.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pacote", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    build(args.pacote.absolute(), args.saida.absolute())
