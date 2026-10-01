"""Conversão local com Docling e saídas Markdown auditáveis."""

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path

from .audit import audit_pdf
from .document import plain_markdown, prepare
from .legacy import completude
from .quality import lint, parser
from .report import new_manifest, write_reports


@dataclass(frozen=True)
class Options:
    ocr: bool = False
    models: Path | None = None
    offline: bool = False
    timeout: float = 900


def make_converter(options: Options):
    if options.timeout <= 0:
        raise ValueError("O tempo máximo deve ser positivo.")
    if options.models and not options.models.is_dir():
        raise ValueError(f"Pasta de modelos inexistente: {options.models}")
    if options.offline:
        for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
            os.environ[key] = "1"
        # A interface pode ter importado huggingface numa corrida anterior.
        import sys

        constants = sys.modules.get("huggingface_hub.constants")
        if constants is not None:
            constants.HF_HUB_OFFLINE = True
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline = PdfPipelineOptions(
        do_ocr=options.ocr,
        do_table_structure=True,
        enable_remote_services=False,
        allow_external_plugins=False,
        document_timeout=options.timeout,
        artifacts_path=options.models,
    )
    pipeline.table_structure_options.mode = TableFormerMode.ACCURATE
    pipeline.table_structure_options.do_cell_matching = True
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)},
    )


def discover(source: Path) -> list[tuple[Path, Path]]:
    if source.is_file() and source.suffix.lower() == ".pdf":
        return [(source, Path(source.stem + ".md"))]
    if source.is_dir():
        files = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
        return [(p, p.relative_to(source).with_suffix(".md")) for p in files]
    raise ValueError("A entrada deve ser um PDF ou uma pasta de PDFs.")


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(content)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def convert_pdf(
    pdf: Path, target: Path, converter, options: Options, overwrite: bool = False
) -> dict:
    raw_target = target.parent / "_auditoria" / (target.stem + ".docling.md")
    report_target = target.parent / "_auditoria" / (target.stem + ".qualidade.json")
    if not overwrite and any(
        p.exists()
        for p in (
            target,
            raw_target,
            report_target,
            raw_target.with_suffix(".json"),
            report_target.with_suffix(".md"),
        )
    ):
        raise FileExistsError(f"Saída já existente: {target}; usar --overwrite para substituir.")
    result = converter.convert(pdf)
    status = getattr(result.status, "value", str(result.status))
    if status != "success":
        raise RuntimeError(f"Conversão incompleta ({status}): {pdf.name}")
    raw = result.document.export_to_markdown(image_placeholder="<!-- image -->")
    subtype = "retificacao" if "-RECT_" in pdf.stem.upper() else "desconhecido"
    reference = None
    reference_words = []
    try:
        reference = completude.ler_referencia(pdf)
        cleaned = completude._juntar_paginas(
            [completude.sem_mobiliario(completude._normalizar(page))[0] for page in reference[0]]
        )
        reference_words = completude.palavras("\n".join(cleaned))
    except Exception:
        # A auditoria reportará a indisponibilidade; não inventar reparações.
        pass
    prepared = prepare(result.document, pdf.stem, subtype=subtype, reference_words=reference_words)
    markdown = prepared.markdown
    title_added = not any(
        token.type == "heading_open" and token.tag == "h1" for token in parser().parse(markdown)
    )
    if title_added:
        title = pdf.stem.replace("_", " ")
        # Nome de ficheiro usado como texto, sem permitir sintaxe Markdown.
        for char in "\\`*_{}[]<>()#!|":
            title = title.replace(char, "\\" + char)
        heading = "# " + title.replace("\n", " ").replace("\r", " ")
        markdown = heading + "\n\n" + markdown
        prepared.generated_headings.append(heading)
    findings = lint(markdown) + prepared.findings
    audit, audit_findings, diagnostic = audit_pdf(
        pdf,
        plain_markdown(markdown, prepared.generated_headings),
        prepared.structure,
        prepared.structured_text,
        prepared.tables,
        reference=reference,
    )
    findings.extend(audit_findings)
    state = "rever" if any(f.severity != "info" for f in findings) else "sem_alertas_automaticos"
    document_json = json.dumps(result.document.export_to_dict(), ensure_ascii=False) + "\n"
    report = {
        "source": str(pdf.resolve()),
        "output": str(target.resolve()),
        "source_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        "docling_version": getattr(converter, "docling_version", None) or version("docling"),
        "docling_document_sha256": hashlib.sha256(document_json.encode("utf-8")).hexdigest(),
        "cached_extraction": hasattr(converter, "extraction_options"),
        "options": getattr(converter, "extraction_options", None)
        or {**asdict(options), "models": str(options.models) if options.models else None},
        "state": state,
        "quality_status": "blocked"
        if any(f.severity == "error" for f in findings)
        else "review"
        if state == "rever"
        else "passed",
        "pages": len(result.document.pages),
        "tables": len(result.document.tables),
        "title_from_filename": title_added,
        "structure": {
            "clauses": sum(n["tipo"] == "clausula" for n in prepared.structure["nos"]),
            "articles": sum(n["tipo"] == "artigo" for n in prepared.structure["nos"]),
            "annexes": sum(n["tipo"] == "anexo" for n in prepared.structure["nos"]),
            "preambles": sum(n["tipo"] == "preambulo" for n in prepared.structure["nos"]),
            "reordered_by_geometry": prepared.reordered,
            "labels": [
                n["rotulo"]
                for n in prepared.structure["nos"]
                if n["tipo"] in {"clausula", "artigo", "anexo", "capitulo", "seccao"}
            ],
        },
        "completeness": audit,
        "findings": [finding.to_dict() for finding in findings],
    }
    atomic_write(raw_target, raw)
    atomic_write(report_target, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    atomic_write(report_target.with_suffix(".md"), diagnostic)
    atomic_write(
        raw_target.with_suffix(".json"),
        document_json,
    )
    atomic_write(target, markdown)
    return report


def run(
    source: Path, output: Path, options: Options, *, overwrite=False, progress=print, converter=None
) -> list[dict]:
    entries = discover(source)
    if not entries:
        raise ValueError("Não foram encontrados PDFs.")
    # Detecta colisões também em volumes Windows/macOS que ignoram maiúsculas.
    names = [str(relative).casefold() for _, relative in entries]
    if len(names) != len(set(names)):
        raise ValueError("PDFs com nomes que colidem na saída Markdown.")
    if any("_auditoria" in relative.parts for _, relative in entries):
        raise ValueError("O nome _auditoria está reservado para os relatórios.")
    manifest = new_manifest(
        source,
        output,
        entries,
        {
            **asdict(options),
            "models": str(options.models) if options.models else None,
            "overwrite": overwrite,
        },
    )
    reports = []
    manifest["status"] = "interrompida"
    try:
        converter = converter if converter is not None else make_converter(options)
        for index, (pdf, relative) in enumerate(entries, 1):
            progress(f"[{index}/{len(entries)}] {pdf.name}")
            try:
                report = convert_pdf(pdf, output / relative, converter, options, overwrite)
            except Exception as exc:
                report = {
                    "source": str(pdf.resolve()),
                    "state": "falhou",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            report = {**manifest["documents"][index - 1], **report}
            manifest["documents"][index - 1] = report
            reports.append(report)
            progress(f"  {report['state']}" + (f": {report['error']}" if "error" in report else ""))
        manifest["status"] = "concluida"
    except BaseException as exc:
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report_path = write_reports(manifest, output, atomic_write)
        progress(f"Relatório consolidado: {report_path.resolve()}")
    return reports
