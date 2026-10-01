import argparse
import json
import sys
from pathlib import Path

from .pipeline import Options, run
from .quality import lint


def main(argv=None):
    parser = argparse.ArgumentParser(description="PDF → Docling → Markdown para MAXQDA")
    commands = parser.add_subparsers(dest="command", required=True)
    convert = commands.add_parser("convert", help="Converter PDF ou pasta recursivamente")
    convert.add_argument("source", type=Path)
    convert.add_argument("--out", required=True, type=Path)
    convert.add_argument("--ocr", action="store_true", help="Ativar OCR para PDFs digitalizados")
    convert.add_argument("--models", type=Path, help="Pasta de modelos Docling")
    convert.add_argument("--offline", action="store_true", help="Usar apenas modelos locais")
    convert.add_argument("--timeout", type=float, default=900)
    convert.add_argument("--overwrite", action="store_true")
    convert.add_argument("--strict", action="store_true", help="Falhar também quando há avisos")
    check = commands.add_parser("lint", help="Validar Markdown existente, sem o modificar")
    check.add_argument("source", type=Path)
    check.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "lint":
            files = sorted(args.source.rglob("*.md")) if args.source.is_dir() else [args.source]
            files = [p for p in files if "_auditoria" not in p.parts]
            if not files:
                raise ValueError("Não foram encontrados ficheiros Markdown.")
            reports = []
            for path in files:
                findings = lint(path.read_text(encoding="utf-8"))
                reports.append({"source": str(path), "findings": [f.to_dict() for f in findings]})
            print(json.dumps(reports, ensure_ascii=False, indent=2))
        else:
            reports = run(
                args.source,
                args.out,
                Options(args.ocr, args.models, args.offline, args.timeout),
                overwrite=args.overwrite,
            )
        if any(
            r.get("state") == "falhou"
            or any(f["severity"] == "error" for f in r.get("findings", []))
            for r in reports
        ):
            return 1
        if args.strict and any(r.get("findings") for r in reports):
            return 2
        return 0
    except (ValueError, OSError, ImportError, RuntimeError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
