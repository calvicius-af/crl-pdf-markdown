"""Ensaio técnico do runtime distribuído. Não substitui o ensaio humano na estação."""

import argparse
import hashlib
import json
import sys
from importlib.metadata import version
from pathlib import Path


def block_network():
    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto"}:
            raise RuntimeError("O ensaio offline tentou usar a rede: " + event)
    sys.addaudithook(audit)


def converter(options):
    # Executado dentro de cada processo spawn, além do processo principal.
    block_network()
    from .desktop import prepare_environment
    prepare_environment()
    from .pipeline import make_converter
    result = make_converter(options)
    if options.ocr:
        from docling.datamodel.base_models import InputFormat
        result.format_to_options[InputFormat.PDF].pipeline_options.ocr_options.force_full_page_ocr = True
    return result


def verify_files(root):
    manifest = json.loads((root / "distribuicao.json").read_text(encoding="utf-8"))
    for name, digest in manifest["files"].items():
        path = root / name
        if not path.is_file():
            raise ValueError("Ficheiro da distribuição em falta ou alterado: " + name)
        with path.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual != digest:
            raise ValueError("Ficheiro da distribuição em falta ou alterado: " + name)
    for package, expected in manifest["versions"].items():
        if version(package) != expected:
            raise ValueError("Versão inesperada: " + package)
    return manifest


def check(output, source=None):
    from .desktop import prepare_environment
    resources = prepare_environment()
    manifest = verify_files(resources.parent)
    block_network()
    import tkinter as tk
    window = tk.Tk()
    window.withdraw()
    window.update()
    window.destroy()
    from .pipeline import Options, run
    from .release_check import converter as factory
    for ocr in (False, True):
        target = output / ("ocr" if ocr else "texto")
        reports = run(source or resources / "smoke.pdf", target,
                      Options(models=resources / "modelos", offline=True, ocr=ocr),
                      converter_factory=factory)
        if len(reports) != 1 or reports[0]["state"] == "falhou":
            raise RuntimeError("O PDF de teste não foi convertido.")
        texts = [p.read_text(encoding="utf-8") for p in target.glob("*.md")]
        if not any(all(token in text for token in ("CRL", "Categoria", "123.45", "678.90")) for text in texts):
            raise RuntimeError("O Markdown de teste não preservou o título e os valores.")
    (output / "ensaio.json").write_text(json.dumps({"version": manifest["version"],
        "source_revision": manifest.get("source_revision"), "sockets_blocked": True,
        "ocr": True, "tk": True, "status": "ensaio_tecnico_passou",
        "station_acceptance": "pendente"}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, help="Cópia do smoke.pdf, por exemplo em L:")
    args = parser.parse_args()
    try:
        check(args.out, args.source)
    except Exception:
        import traceback
        # pythonw não tem stderr; conservar a causa mesmo sem chegar ao pipeline.
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "falha_ensaio.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
