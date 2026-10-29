import argparse
import json
import sys
from pathlib import Path

from . import models, utf8_output
from .cache import CachedConverter
from .naming import name_records
from .pipeline import Options, run
from .quality import lint
from .recolha import add_arguments, collect
from .workspace import DOCUMENT_FOLDERS, document_source, initialize


def main(argv=None):
    utf8_output()
    parser = argparse.ArgumentParser(description="PDF → Docling → Markdown para MAXQDA")
    commands = parser.add_subparsers(dest="command", required=True)
    collection = commands.add_parser(
        "collect", help="Recolher PDFs a partir dos índices Excel do BTE"
    )
    add_arguments(collection)
    setup = commands.add_parser("init", help="Criar a árvore RNC sem mover ficheiros existentes")
    setup.add_argument("workspace", type=Path)
    naming = commands.add_parser("name", help="Propor ou copiar PDFs com nomes RNC")
    naming.add_argument("--workspace", required=True, type=Path)
    naming.add_argument("--registo", type=Path)
    naming.add_argument("--siglas", type=Path)
    naming.add_argument("--ambitos", type=Path)
    naming.add_argument("--esquema", choices=["adr0022", "v4"], default="adr0022")
    naming.add_argument("--aplicar", action="store_true")
    doctor = commands.add_parser("doctor", help="Verificar instalação e guardar instruções de reparação")
    doctor.add_argument("--models", type=Path)
    doctor.add_argument("--out", type=Path, default=Path("assistencia"))
    convert = commands.add_parser("convert", help="Converter PDF ou pasta recursivamente")
    convert.add_argument("source", type=Path, nargs="?")
    convert.add_argument("--out", type=Path)
    convert.add_argument("--workspace", type=Path, help="Usar convencoes e 2_processamento/texto")
    convert.add_argument("--familia", choices=list(DOCUMENT_FOLDERS), default="convencao",
                         help="Família a converter na pasta RNC; todos inclui cessações e avisos")
    convert.add_argument("--ocr", action="store_true", help="Ativar OCR para PDFs digitalizados")
    convert.add_argument("--models", type=Path, help="Pasta de modelos Docling")
    convert.add_argument("--offline", action="store_true", help="Usar apenas modelos locais")
    convert.add_argument("--timeout", type=float, default=900)
    convert.add_argument("--overwrite", action="store_true")
    convert.add_argument(
        "--docling-cache",
        type=Path,
        help="Reutilizar uma extração Docling auditada, verificando o hash do PDF",
    )
    convert.add_argument("--strict", action="store_true", help="Falhar também quando há avisos")
    model_files = commands.add_parser(
        "models", help="Descarregar e verificar os modelos Docling para uso sem rede"
    )
    models.add_arguments(model_files)
    check = commands.add_parser("lint", help="Validar Markdown existente, sem o modificar")
    check.add_argument("source", type=Path)
    check.add_argument("--strict", action="store_true")
    review = commands.add_parser("review", help="Registar a conferência humana de um documento")
    review.add_argument("--out", type=Path, required=True, help="Pasta da conversão")
    review.add_argument("--document", required=True, help="Caminho relativo do PDF no relatório")
    review.add_argument("--reviewer", required=True)
    review.add_argument("--decision", choices=["aprovado", "rejeitado"], required=True)
    review.add_argument("--scope", choices=["integral", "amostra"], required=True)
    review.add_argument("--notes", default="")
    delivery = commands.add_parser("deliver", help="Entregar Markdown aprovado e relatório metodológico")
    delivery.add_argument("--out", type=Path, required=True, help="Pasta da conversão")
    delivery.add_argument("--destination", type=Path, required=True, help="Nova pasta de entrega")
    audit_again = commands.add_parser('reaudit', help='Reauditar uma extração verificada numa pasta nova')
    audit_again.add_argument('--out', type=Path, required=True)
    audit_again.add_argument('--destination', type=Path)
    audit_again.add_argument('--document')
    audit_again.add_argument('--family', action='append', default=[],
                             help='Primeira subpasta do PDF, por exemplo convencoes; repetível; . para a raiz')
    audit_again.add_argument('--rule', action='append', default=[],
                             help='Regra presente na corrida anterior, por exemplo AMOUNTS; repetível')
    audit_again.add_argument('--status', action='append', default=[],
                             choices=['passed', 'review', 'blocked'],
                             help='Estado automático na corrida anterior; repetível')
    audit_again.add_argument('--dry-run', action='store_true',
                             help='Listar a seleção em JSON sem criar saídas nem carregar modelos')
    audit_again.add_argument('--jobs', type=int, choices=[1, 2], default=2)
    revision = commands.add_parser('revise', help='Criar uma correção separada do original')
    revision.add_argument('--out', type=Path, required=True)
    revision.add_argument('--document', required=True)
    revision.add_argument('--reviewer', required=True)
    revision_audit = commands.add_parser('audit-revision', help='Auditar e publicar uma correção guardada')
    revision_audit.add_argument('revision', type=Path)
    revision_audit.add_argument('--resolutions', type=Path)
    ocr_pages = commands.add_parser('ocr-pages', help='Reextrair só as páginas indicadas com OCR local')
    ocr_pages.add_argument('--out', type=Path, required=True)
    ocr_pages.add_argument('--document', required=True)
    ocr_pages.add_argument('--reviewer', required=True)
    ocr_pages.add_argument('--models', type=Path, required=True)
    ocr_pages.add_argument('--pages', required=True)
    evaluation = commands.add_parser('evaluate', help='Comparar auditorias e casos de referência anotados')
    evaluation.add_argument('--baseline', type=Path, required=True)
    evaluation.add_argument('--candidate', type=Path, required=True)
    evaluation.add_argument('--out', type=Path, required=True)
    evaluation.add_argument('--reference', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'evaluate':
            from .evaluation import evaluate
            data = evaluate(args.baseline, args.candidate, args.out, reference=args.reference)
            print(f'Comparação: {args.out / "comparacao.md"}')
            return int(not data['comparable_complete_corpus'] or any(d['status'] != 'passed'
                       for d in data.get('reference_checks', {}).get('documents', [])))
        if args.command == 'ocr-pages':
            from .page_ocr import parse_pages, reextract_pages
            from .revisions import _record
            from .validation import _verified
            _, _, report = _verified(args.out, _record(args.out, args.document))
            selected = parse_pages(args.pages, report['pages'])
            destination, report = reextract_pages(args.out, args.document, args.reviewer, args.models, selected)
            print(f'OCR dirigido: {destination} ({report["quality_status"]})')
            return int(report['quality_status'] == 'blocked')
        if args.command == 'revise':
            from .revisions import create_revision
            print(create_revision(args.out, args.document, args.reviewer))
            return 0
        if args.command == 'audit-revision':
            from .revisions import audit_revision
            resolutions = json.loads(args.resolutions.read_text(encoding='utf-8')) if args.resolutions else []
            publication, report = audit_revision(args.revision, resolutions=resolutions)
            print(f'Correção auditada: {publication} ({report["quality_status"]})')
            return int(report['quality_status'] == 'blocked')
        if args.command == 'reaudit':
            from .reaudit import plan_reaudit, reaudit
            filters = dict(relative_source=args.document, families=args.family,
                           rules=args.rule, statuses=args.status)
            if args.dry_run:
                _, _, selection = plan_reaudit(args.out, **filters)
                print(json.dumps(selection, ensure_ascii=False, indent=2))
                return 0
            destination, reports = reaudit(args.out, args.destination, **filters, jobs=args.jobs)
            print(f'Reauditoria: {destination}')
            return int(any(r.get('quality_status') == 'blocked' or r.get('state') == 'falhou' for r in reports))
        if args.command == "review":
            from .validation import decide
            print(decide(args.out, args.document, reviewer=args.reviewer,
                         decision=args.decision, scope=args.scope, notes=args.notes))
            return 0
        if args.command == "deliver":
            from .validation import deliver
            print(deliver(args.out, args.destination))
            return 0
        if args.command == "doctor":
            from .doctor import check as check_installation
            ok = check_installation(args.models, args.out)
            print(f"Verificação: {args.out / 'instalacao.md'}")
            return 0 if ok else 1
        if args.command == "init":
            print(f"Pastas prontas: {initialize(args.workspace).resolve()}")
            return 0
        if args.command == "name":
            initialize(args.workspace)
            args.siglas = args.siglas or args.workspace / "0_gestao/vocabularios/siglas.csv"
            args.ambitos = args.ambitos or args.workspace / "0_gestao/vocabularios/empregadores_ambito.csv"
            results = name_records(
                args.registo or args.workspace / "0_gestao/catalogo/registo_bte.jsonl",
                args.workspace, args.siglas, args.ambitos, apply=args.aplicar, scheme=args.esquema,
            )
            print(json.dumps(results, ensure_ascii=False, indent=2))
            print(f"Relatório: {args.workspace / '0_gestao/catalogo/nomeacao.csv'}")
            return 1 if any(row["estado"] == "por_confirmar" for row in results) else 0
        if args.command == "collect":
            return collect(args)
        if args.command == "models":
            return models.run_command(args)
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
            if args.workspace:
                initialize(args.workspace)
                args.source = args.source or document_source(args.workspace, args.familia)
                args.out = args.out or args.workspace / "2_processamento/texto"
            if not args.source or not args.out:
                raise ValueError("Selecione entrada e saída, ou indique --workspace RNC_Dados_AAAA.")
            reports = run(
                args.source,
                args.out,
                Options(args.ocr, args.models, args.offline, args.timeout),
                overwrite=args.overwrite,
                converter=CachedConverter(args.docling_cache, Options(args.ocr, args.models, args.offline, args.timeout)) if args.docling_cache else None,
            )
        if any(
            r.get("state") == "falhou"
            or any(f["severity"] == "error" for f in r.get("findings", []))
            for r in reports
        ):
            return 1
        if args.strict and any(
            f["severity"] != "info" for r in reports for f in r.get("findings", [])
        ):
            return 2
        return 0
    except (ValueError, OSError, ImportError, RuntimeError) as exc:
        if args.command == 'reaudit' and args.dry_run:
            print(f'Erro: {exc}', file=sys.stderr)
            return 1
        from tempfile import gettempdir

        from .diagnostics import save_failure
        folder = (getattr(args, "workspace", None) or getattr(args, "out", None)
                  or Path(gettempdir()) / "CRL-assistencia")
        try:
            report = save_failure(exc, folder / "_assistencia", args.command)
        except OSError:
            report = save_failure(exc, Path(gettempdir()) / "CRL-assistencia", args.command)
        print(f"Erro: {exc}\nComo resolver: {report}", file=sys.stderr)
        return 1
