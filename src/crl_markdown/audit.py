"""Completude e sanidade, medidas sobre o conteúdo do Markdown final."""

import re
from collections import Counter
from dataclasses import fields
from pathlib import Path

from .legacy import auditoria, completude, sanidade
from .quality import Finding

AMOUNT = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:[ .\u00a0]\d{3})+|\d+)[,.]\d{2}(?!\d)")


def amounts(text: str) -> Counter:
    def canonical(value):
        value = re.sub(r"[ \u00a0]", "", value)
        return value.replace(".", "") if "," in value else value.replace(".", ",")

    return Counter(canonical(match) for match in AMOUNT.findall(text))


def pdf_amounts(pdf: Path) -> Counter:
    """Auditor monetário com geometria: «nível 2 | 920,00» não é «2 920,00»."""
    import pdfplumber

    result = Counter()
    with pdfplumber.open(pdf) as document:
        for page in document.pages:
            words = page.dedupe_chars().extract_words(
                line_dir_rotated="ltr", char_dir_rotated="btt"
            )
            for index, word in enumerate(words):
                value = word["text"]
                if index and re.fullmatch(r"\d{3}[,.]\d{2}", value):
                    prev = words[index - 1]
                    direction = word.get("direction", "ltr")
                    if direction == "ltr":
                        gap = word["x0"] - prev["x1"]
                        aligned = abs(word["top"] - prev["top"]) < 2
                    elif direction == "btt":
                        gap = prev["top"] - word["bottom"]
                        aligned = abs(word["x0"] - prev["x0"]) < 2
                    else:
                        gap, aligned = 100, False
                    if (
                        re.fullmatch(r"\d{1,3}", prev["text"])
                        and aligned
                        and 0 <= gap <= 4
                        and prev.get("direction", "ltr") == direction
                    ):
                        value = prev["text"] + value
                result.update(amounts(value))
    return result


def audit_pdf(
    pdf: Path,
    plain: str,
    structure: dict,
    structured_text: str,
    exported_tables: int,
    *,
    reference=None,
):
    try:
        pages, blind_pages = reference if reference is not None else completude.ler_referencia(pdf)
        measure = completude.medir(pdf.stem, pages, plain)
        measure.paginas_cegas = blind_pages
    except Exception as exc:
        measure = completude.Medida(pdf.stem, erro=f"{type(exc).__name__}: {exc}")
    findings = []
    if measure.erro:
        findings.append(
            Finding(
                "COMPLETENESS_UNAVAILABLE", 0, f"Completude não medida: {measure.erro}", "error"
            )
        )
    elif measure.veredicto != "OK":
        findings.append(
            Finding(
                "COMPLETENESS",
                0,
                f"{measure.veredicto}: cobertura {measure.cobertura:.2%}, "
                f"excesso {measure.excesso:.2%}, ordem {measure.ordem:.2%}.",
                "error" if measure.veredicto == "FALHA" else "warning",
            )
        )
    if not measure.erro and not measure.palavras_pdf:
        findings.append(
            Finding(
                "REFERENCE_EMPTY",
                0,
                "PDF sem camada textual para comparação independente; "
                "a completude do OCR não está comprovada.",
                "error",
            )
        )
    reference = " ".join(measure.palavras_referencia)
    # A comparação monetária não pode usar palavras tokenizadas, que perdem vírgulas.
    missing_amounts, extra_amounts = Counter(), Counter()
    table_count, image_pages = None, []
    try:
        expected, actual = pdf_amounts(pdf), amounts(plain)
        missing_amounts, extra_amounts = expected - actual, actual - expected
        if missing_amounts or extra_amounts:
            findings.append(
                Finding(
                    "AMOUNTS",
                    0,
                    f"Montantes em falta: {dict(missing_amounts)}; "
                    f"montantes adicionais: {dict(extra_amounts)}.",
                    "error",
                )
            )
        table_count = auditoria.contar_tabelas_pdfplumber(pdf)
        image_pages = auditoria.paginas_com_imagem(pdf)
        for message in auditoria.divergencias(table_count, exported_tables):
            findings.append(Finding("TABLE_AUDIT", 0, message))
        if table_count and not exported_tables:
            findings.append(
                Finding(
                    "TABLES_MISSING",
                    0,
                    "O auditor deteta tabelas, mas o Markdown não contém nenhuma.",
                    "error",
                )
            )
    except Exception as exc:
        findings.append(Finding("TABLE_AUDIT_UNAVAILABLE", 0, str(exc), "error"))
    if reference or structured_text:
        for message in sanidade.verificar(
            structure, structured_text, measure.palavras_referencia, image_pages
        ):
            rule = "STRUCTURE"
            severity = "warning"
            if message.startswith(
                (
                    sanidade.AVISO_RETIFICACAO_SEM_ARTICULADO,
                    sanidade.AVISO_ALTERACAO_SALARIAL_SEM_ARTICULADO,
                )
            ):
                severity = "info"
            findings.append(Finding(rule, 0, message, severity))
    report = {field.name: getattr(measure, field.name) for field in fields(measure)}
    report = {
        key: dict(value) if isinstance(value, Counter) else value for key, value in report.items()
    }
    report.update(
        cobertura=measure.cobertura,
        excesso=measure.excesso,
        veredicto=measure.veredicto,
        reference_engine="PDFium",
        fallback_pages=measure.paginas_cegas,
        reference_independent=not bool(measure.paginas_cegas),
        audited_content="final_markdown_visible_text",
        amounts_missing=dict(missing_amounts),
        amounts_extra=dict(extra_amounts),
        amounts_engine="pdfplumber_words_geometric",
        reference_tables=table_count,
    )
    report.pop("palavras_referencia", None)
    return report, findings, completude.diagnostico([measure])
