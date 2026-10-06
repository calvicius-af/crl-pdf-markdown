"""Relatório consolidado de uma corrida, incluindo tentativas sem Markdown."""

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from .quality import normalize

STATUS = {
    "passed": "Sem alertas automáticos",
    "review": "Rever",
    "blocked": "Bloqueado",
    "falhou": "Falhou",
    "nao_processado": "Não processado",
}


def status(report):
    return report.get("quality_status", report.get("state", "review"))


def escaped(value):
    text = str(value).replace("\n", " ").replace("\r", " ")
    for char in "\\`*_{}[]<>()#!|":
        text = text.replace(char, "\\" + char)
    return text


def block(value):
    text = str(value)
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}text\n{text}\n{fence}\n"


def link(path, parent, label):
    relative = os.path.relpath(Path(path).resolve(), parent.resolve()).replace(os.sep, "/")
    return f"[{escaped(label)}](<{quote(relative, safe='/.-_~')}>)"


def evidence(key, value):
    if key == "perda_por_pagina":
        return "\n".join(f"- Página {page}: perda de {loss:.3%}." for page, loss in value) + "\n"
    if key in {"em_falta", "a_mais", "amounts_missing", "amounts_extra"}:
        return (
            "\n".join(f"- {escaped(word)}: {count} ocorrência(s)." for word, count in value.items())
            + "\n"
        )
    if key in {"contexto_falta", "contexto_mais"}:
        return "\n".join(
            f"**{escaped(word)}**\n\n" + block(context) for word, context in value.items()
        )
    if key == "trechos_falta":
        return "\n".join(
            f"Página {page} — referência PDF:\n\n"
            + block(original)
            + "\nTexto correspondente na extração:\n\n"
            + block(replacement)
            for page, original, replacement in value
        )
    if key == "trechos_mais":
        return "\n".join(block(text) for text in value)
    if key in {"fallback_pages", "paginas_cegas"}:
        return "Páginas: " + ", ".join(str(page) for page in value) + ".\n"
    if key == "caracteres":
        return (
            "\n".join(
                [
                    "| Classe | Referência PDF | Markdown |",
                    "| --- | --- | --- |",
                    *(
                        f"| {escaped(kind)} | {counts[0]} | {counts[1]} |"
                        for kind, counts in value.items()
                    ),
                ]
            )
            + "\n"
        )
    return block(json.dumps(value, ensure_ascii=False, indent=2))


def diagnostic(manifest, parent, *, detailed=True):
    reports = manifest["documents"]
    counts = Counter(status(r) for r in reports)
    findings = Counter(f["severity"] for r in reports for f in r.get("findings", []))
    lines = [
        "# Relatório de extração — PDF para Markdown",
        "",
        f"Corrida: {manifest['run_id']}  ",
        f"Início (UTC): {manifest['started_at_utc']}  ",
        f"Fim (UTC): {manifest['finished_at_utc']}  ",
        f"Estado da corrida: {escaped(manifest['status'])}",
        "",
        f"Entrada: {escaped(manifest['source'])}  ",
        f"Saída: {escaped(manifest['output'])}",
        "",
        "## Resumo",
        "",
        f"Documentos previstos: **{len(reports)}**. "
        f"Convertidos: **{sum('quality_status' in r for r in reports)}**. "
        f"Falhas: **{counts['falhou']}**. Não processados: **{counts['nao_processado']}**.",
        "",
        f"Sem alertas automáticos: **{counts['passed']}**; "
        f"a rever: **{counts['review']}**; bloqueados: **{counts['blocked']}**.",
        "",
        f"Ocorrências: **{findings['error']} erros**, **{findings['warning']} avisos**, "
        f"**{findings['info']} informações**. Falhas de conversão são contabilizadas à parte.",
        "",
        "Um documento bloqueado pode ter cobertura elevada e continuar com tabelas ou "
        "montantes incorretos. Sem alertas automáticos não equivale a validação manual. "
        "Importar apenas os documentos finais, excluindo a pasta de auditoria.",
        "",
        "## Documentos",
        "",
        "| Documento | Estado | Cobertura | Ordem | Tabelas | Erros / avisos |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for report in reports:
        audit = report.get("completeness", {})
        amounts = Counter(f["severity"] for f in report.get("findings", []))
        name = report["relative_source"]
        location = (
            link(report["output"], parent, name) if "quality_status" in report else escaped(name)
        )
        coverage = audit.get("cobertura")
        order = audit.get("ordem")
        lines.append(
            f"| {location} | {STATUS.get(status(report), escaped(status(report)))} | "
            f"{f'{coverage:.2%}' if coverage is not None else '—'} | "
            f"{f'{order:.2%}' if order is not None else '—'} | "
            f"{report.get('tables', '—')} | {amounts['error']} / {amounts['warning']} |"
        )
    if manifest.get("error"):
        lines += ["", "## Falha da corrida", "", block(manifest["error"])]
    lines += ["", "## Problemas por regra", ""]
    rules = Counter(f["rule"] for r in reports for f in r.get("findings", []))
    if rules:
        lines += ["| Regra | Ocorrências | Documentos afetados |", "| --- | --- | --- |"]
        for rule, count in sorted(rules.items()):
            affected = sum(any(f["rule"] == rule for f in r.get("findings", [])) for r in reports)
            lines.append(f"| {escaped(rule)} | {count} | {affected} |")
    else:
        lines.append("Sem ocorrências de regras. Consultar também as falhas de conversão.")
    if not detailed:
        lines += ["", "## Ações de revisão", ""]
        for report in reports:
            if status(report) in {"passed"}:
                continue
            lines += [f"### {escaped(report['relative_source'])}", ""]
            if report.get("error"):
                lines += [escaped(report["error"]), ""]
            grouped = {}
            for finding in report.get("findings", []):
                if finding["severity"] == "info":
                    continue
                grouped.setdefault((finding["rule"], finding["severity"]), []).append(finding)
            for (rule, severity), items in grouped.items():
                lines.append(
                    f"- **{escaped(rule)}** ({'erro' if severity == 'error' else 'aviso'}, {len(items)} ocorrência(s)): "
                    + escaped(items[0]["message"])
                )
            lines.append("")
        lines += [
            link(parent / "detalhes.md", parent, "Consultar evidências e todas as ocorrências"),
            "",
        ]
        return normalize("\n".join(lines))
    lines += ["", "## Diagnóstico por documento", ""]
    # Dá prioridade aos documentos que impedem a importação validada.
    priority = {"falhou": 0, "nao_processado": 1, "blocked": 2, "review": 3, "passed": 4}
    for report in sorted(reports, key=lambda r: priority.get(status(r), 3)):
        lines += [
            f"### {escaped(report['relative_source'])}",
            "",
            f"Estado: **{STATUS.get(status(report), escaped(status(report)))}**.",
            "",
        ]
        if report.get("error"):
            lines += [block(report["error"])]
        if "quality_status" not in report:
            lines += ["Não foi publicado um Markdown nesta tentativa.", ""]
            continue
        lines += [
            link(report["source"], parent, "PDF de origem")
            + " · "
            + link(report["output"], parent, "Markdown final"),
            "",
        ]
        audit = report.get("completeness", {})
        structure = report.get("structure", {})
        lines += [
            f"Páginas: {report.get('pages', '—')}; tabelas: {report.get('tables', '—')}; "
            f"cláusulas: {structure.get('clauses', '—')}; "
            f"artigos: {structure.get('articles', '—')}; "
            f"anexos: {structure.get('annexes', '—')}; "
            f"preâmbulos: {structure.get('preambles', '—')}.",
            "",
            "#### Todas as ocorrências",
            "",
        ]
        if report.get("findings"):
            for finding in report["findings"]:
                where = f"linha {finding['line']}" if finding.get("line") else "documento"
                severity = {"error": "ERRO", "warning": "AVISO", "info": "INFORMAÇÃO"}
                lines += [
                    f"- **{severity.get(finding['severity'], escaped(finding['severity']))} "
                    f"— {escaped(finding['rule'])}** ({where}): " + escaped(finding["message"])
                ]
        else:
            lines.append("Sem ocorrências automáticas.")
        lines += ["", "#### Completude e evidências", ""]
        if not audit:
            lines += ["Sem medição disponível.", ""]
        else:
            lines += [
                f"Veredicto: {escaped(audit.get('veredicto', '—'))}; "
                f"referência: {escaped(audit.get('reference_engine', '—'))}; "
                f"conteúdo auditado: {escaped(audit.get('audited_content', '—'))}.",
                "",
                f"Palavras de referência: {audit.get('palavras_pdf', '—')}; "
                f"palavras no Markdown: {audit.get('palavras_texto', '—')}; "
                f"excesso: {audit.get('excesso', '—')}.",
                "",
                f"Referência independente: {'sim' if audit.get('reference_independent') else 'não / não indicada'}. "
                f"Auditor de montantes: {escaped(audit.get('amounts_engine', '—'))}. "
                f"Tabelas na referência: {audit.get('reference_tables', '—')}.",
                "",
            ]
            labels = {
                "erro": "Erro da medição",
                "fallback_pages": "Páginas com referência alternativa",
                "paginas_cegas": "Páginas sem referência textual",
                "perda_por_pagina": "Perda por página (página, fração)",
                "em_falta": "Palavras em falta (contagens)",
                "a_mais": "Palavras excedentes (contagens)",
                "amounts_missing": "Montantes em falta (contagens)",
                "amounts_extra": "Montantes excedentes (contagens)",
                "trechos_falta": "Trechos em falta (página, original, substituição)",
                "trechos_mais": "Trechos excedentes",
                "contexto_falta": "Contextos das palavras em falta",
                "contexto_mais": "Contextos das palavras excedentes",
                "invertidas": "Palavras invertidas",
                "residuos": "Resíduos de mobiliário",
                "linhas_longas": "Linhas longas",
                "caracteres": "Comparação de caracteres",
            }
            for key, label in labels.items():
                if audit.get(key):
                    lines += [
                        f"**{label}**",
                        "",
                        evidence(key, audit[key]),
                    ]
        lines += [
            "#### Proveniência",
            "",
            block(
                json.dumps(
                    {
                        key: report[key]
                        for key in (
                            "source_sha256",
                            "markdown_sha256",
                            "docling_document_sha256",
                            "docling_version",
                            "cached_extraction",
                            "options",
                        )
                        if key in report
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            ),
        ]
    return normalize("\n".join(lines))


def new_manifest(source: Path, output: Path, entries, options):
    started = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "run_id": started.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8],
        "started_at_utc": started.isoformat(),
        "source": str(source.resolve()),
        "output": str(output.resolve()),
        "options": options,
        "documents": [
            {
                "source": str(pdf.resolve()),
                "relative_source": (
                    pdf.relative_to(source) if source.is_dir() else Path(pdf.name)
                ).as_posix(),
                "output": str((output / relative).resolve()),
                "state": "nao_processado",
            }
            for pdf, relative in entries
        ],
    }


def write_reports(manifest, output: Path, write):
    manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    records = manifest["documents"]
    manifest["counts"] = dict(Counter(status(r) for r in records))
    manifest["findings_by_severity"] = dict(
        Counter(f["severity"] for r in records for f in r.get("findings", []))
    )
    overview = [f"Corrida: {manifest['run_id']}", f"Documentos previstos: {len(records)}"]
    for report in records:
        overview.append(
            f"\n{report['relative_source']} — {STATUS.get(status(report), status(report))}"
        )
        if report.get("error"):
            overview.append(report["error"])
        for finding in report.get("findings", []):
            overview.append(
                f"{finding['severity']} {finding['rule']} "
                f"linha {finding.get('line', 0)}: {finding['message']}"
            )
    if manifest.get("error"):
        overview += ["\nFalha da corrida:", manifest["error"]]
    for folder in (output / "_auditoria" / "corridas" / manifest["run_id"], output / "_auditoria"):
        write(folder / "diagnostico.md", diagnostic(manifest, folder, detailed=False))
        write(folder / "detalhes.md", diagnostic(manifest, folder))
        write(folder / "relatorio.txt", "\n".join(overview) + "\n")
        write(folder / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return output / "_auditoria" / "diagnostico.md"
