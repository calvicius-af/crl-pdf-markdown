"""Completude e sanidade, medidas sobre o conteúdo do Markdown final."""

import re
from collections import Counter
from dataclasses import fields
from pathlib import Path

from .legacy import auditoria, completude, sanidade
from .quality import Finding

AMOUNT = re.compile(r"(?<![\d.,])[-−+]?(?:\d{1,3}(?:[ .\u00a0]\d{3})+|\d+)[,.]\d{2}(?!\d)")
SIGNED = re.compile(
    r"(?<![\w.,])[-−+][ \t\u00a0]*(?:\d{1,3}(?:[ .\u00a0]\d{3})+|\d+)(?:[.,]\d+)?"
)


def canonical_number(value: str) -> str:
    value = re.sub(r"[ \t\u00a0]", "", value).replace("−", "-")
    return value.replace(".", "") if "," in value else value.replace(".", ",")


def signed_values(text: str) -> Counter:
    return Counter(canonical_number(v) for v in SIGNED.findall(text))


def amounts(text: str) -> Counter:
    return Counter(canonical_number(v) for v in AMOUNT.findall(text))


def _pdf_numeric_tokens(pdf: Path):
    """Agrupa sinais/milhares contíguos; não concatena colunas afastadas."""
    import pdfplumber

    with pdfplumber.open(pdf) as document:
        for page in document.pages:
            words = page.dedupe_chars().extract_words(
                line_dir_rotated="ltr", char_dir_rotated="btt"
            )
            tokens = []
            for index, word in enumerate(words):
                value = word['text']
                if index:
                    previous = words[index - 1]
                    direction = word.get('direction', 'ltr')
                    if direction == 'ltr':
                        gap = word['x0'] - previous['x1']
                        aligned = abs(word['top'] - previous['top']) < 2
                    elif direction == 'btt':
                        gap = previous['top'] - word['bottom']
                        aligned = abs(word['x0'] - previous['x0']) < 2
                    else:
                        gap, aligned = 100, False
                    close = aligned and 0 <= gap <= 4 and previous.get('direction', 'ltr') == direction
                    sign = tokens[-1] in {'-', '−', '+'} and re.match(r"^\d", value)
                    thousands = (re.fullmatch(r"[-−+]?\d+", tokens[-1])
                                 and re.fullmatch(r"\d{3}(?:[,.]\d{2})?", value))
                    if close and (sign or thousands):
                        tokens[-1] += value
                        continue
                tokens.append(value)
            yield from tokens


def pdf_signed_values(pdf: Path) -> Counter:
    result = Counter()
    for value in _pdf_numeric_tokens(pdf):
        result.update(signed_values(value))
    return result


def pdf_amounts(pdf: Path) -> Counter:
    """Auditor monetário com geometria e sinais, incluindo milhares agrupados."""
    result = Counter()
    for value in _pdf_numeric_tokens(pdf):
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
    critical_missing, critical_extra = Counter(), Counter()
    if not measure.erro:
        # Palavras não detetam 25% -> 25. Conferir sinais do texto da referência,
        # removendo só mobiliário; não confundir escapes/tabelas Markdown com conteúdo.
        reference_text = "\n".join(completude.sem_mobiliario(completude._normalizar(p))[0]
                                   for p in pages)
        def symbols(text):
            return Counter(ch for ch in text if ch in "%‰€$£§<>≤≥≠±")
        def critical_values(value):
            tokens = re.findall(r"\d+(?:[.,]\d+)?\s*[%‰]", value)
            return Counter(re.sub(r"\s+", "", v).replace("−", "-") for v in tokens)

        expected_symbols = symbols(reference_text) + critical_values(reference_text)
        actual_symbols = symbols(plain) + critical_values(plain)
        try:
            expected_symbols += pdf_signed_values(pdf)
            actual_symbols += signed_values(plain)
        except Exception as exc:
            findings.append(Finding("SIGNED_VALUES_UNAVAILABLE", 0,
                                    f"Não foi possível conferir sinais numéricos: {exc}", "error"))
        critical_missing = expected_symbols - actual_symbols
        critical_extra = actual_symbols - expected_symbols
        if critical_missing or critical_extra:
            findings.append(Finding("CRITICAL_SYMBOLS", 0,
                f"Símbolos críticos em falta: {dict(critical_missing)}; "
                f"adicionais: {dict(critical_extra)}. Conferir no PDF.", "error"))
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
        critical_symbols_missing=dict(critical_missing),
        critical_symbols_extra=dict(critical_extra),
        amounts_missing=dict(missing_amounts),
        amounts_extra=dict(extra_amounts),
        amounts_engine="pdfplumber_words_geometric",
        reference_tables=table_count,
    )
    report.pop("palavras_referencia", None)
    return report, findings, completude.diagnostico([measure])
