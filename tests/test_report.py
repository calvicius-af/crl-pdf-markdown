import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from crl_markdown.pipeline import Options, atomic_write, run
from crl_markdown.report import diagnostic, new_manifest, write_reports


def test_all_findings_and_completeness_evidence_retained(tmp_path):
    source = tmp_path / "inputs"
    source.mkdir()
    pdf = source / "sub" / "mesmo | nome.pdf"
    manifest = new_manifest(source, tmp_path / "out", [(pdf, Path("sub/doc.md"))], {})
    record = manifest["documents"][0]
    record.update(
        {
            "quality_status": "blocked",
            "state": "rever",
            "pages": 3,
            "tables": 2,
            "findings": [
                {
                    "severity": "error",
                    "rule": "TABLE_OVERLAP",
                    "line": i,
                    "message": f"Problema {i} | célula\nsegunda linha",
                }
                for i in range(40)
            ],
            "completeness": {
                "veredicto": "OK",
                "cobertura": 0.999,
                "ordem": 0.998,
                "amounts_missing": {"1250,00": 2},
                "trechos_falta": [[3, "```texto desaparecido", "outro texto"]],
                "fallback_pages": [3],
                "em_falta": {f"palavra{i}": 1 for i in range(35)},
            },
        }
    )
    manifest["status"] = "concluida"
    path = write_reports(manifest, tmp_path / "out", atomic_write)
    text = (path.parent / "detalhes.md").read_text("utf-8")
    assert "Bloqueado" in text and "99.90%" in text and "Veredicto: OK" in text
    assert text.count("**ERRO — TABLE\\_OVERLAP**") == 40
    assert "1250,00" in text and "palavra34" in text and "```texto desaparecido" in text
    assert "Páginas com referência alternativa" in text
    assert "mesmo \\| nome.pdf" in text
    archive = path.parent / "corridas" / manifest["run_id"]
    saved = json.loads((archive / "manifest.json").read_text("utf-8"))
    assert saved["documents"][0]["findings"] == record["findings"]
    assert saved["counts"] == {"blocked": 1}
    assert "sub/doc.md" in text
    assert "../../../sub/doc.md" in (archive / "detalhes.md").read_text("utf-8")
    assert "Problema 39" in (archive / "relatorio.txt").read_text("utf-8")
    from markdown_it import MarkdownIt

    tokens = MarkdownIt().parse(text)
    assert any(t.type == "fence" and "```texto desaparecido" in t.content for t in tokens)


def test_failed_documents_reported_and_previous_runs_preserved(tmp_path):
    source = tmp_path / "pdfs"
    source.mkdir()
    (source / "bad.pdf").touch()
    (source / "nested").mkdir()
    (source / "nested/bad.pdf").touch()

    def fail(_):
        raise RuntimeError("PDF inválido")

    output = tmp_path / "out"
    logs = []
    for _ in range(2):
        results = run(
            source, output, Options(), converter=SimpleNamespace(convert=fail), progress=logs.append
        )
        assert len(results) == 2
    folders = list((output / "_auditoria/corridas").iterdir())
    assert len(folders) == 2
    manifest = json.loads((output / "_auditoria/manifest.json").read_text("utf-8"))
    assert manifest["counts"] == {"falhou": 2}
    assert manifest["status"] == "concluida"
    assert "nested/bad.pdf" in (output / "_auditoria/relatorio.txt").read_text("utf-8")
    assert "PDF inválido" in (output / "_auditoria/diagnostico.md").read_text("utf-8")
    assert not list(output.glob("*.md"))
    assert "Relatório consolidado:" in logs[-1]


@pytest.mark.parametrize("failure", ["models", "interrupt"])
def test_initialization_failure_records_unprocessed_documents(tmp_path, monkeypatch, failure):
    # O Docling corre num processo à parte: um conversor que não arranca
    # (modelos em falta) interrompe a corrida, como antes, em vez de falhar
    # documento a documento.
    from tests import worker_fakes

    pdf = tmp_path / "origem.pdf"
    pdf.touch()
    kwargs = {"converter_factory": worker_fakes.sem_modelos}
    expected, name = RuntimeError, "Modelos indisponíveis"
    if failure == "interrupt":

        def interrupt(*_args, **_kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr("crl_markdown.pipeline.ConversorIsolado", interrupt)
        kwargs, expected, name = {}, KeyboardInterrupt, "KeyboardInterrupt"
    with pytest.raises(expected):
        run(pdf, tmp_path / "out", Options(), progress=lambda _: None, **kwargs)
    manifest = json.loads((tmp_path / "out/_auditoria/manifest.json").read_text("utf-8"))
    assert manifest["status"] == "interrompida"
    assert manifest["counts"] == {"nao_processado": 1}
    assert name in manifest["error"]


def test_interruption_retains_completed_attempts_and_pending_documents(tmp_path):
    for name in ("a.pdf", "b.pdf"):
        (tmp_path / name).touch()

    def convert(path):
        if path.name == "b.pdf":
            raise KeyboardInterrupt()
        raise RuntimeError("PDF danificado")

    with pytest.raises(KeyboardInterrupt):
        run(
            tmp_path,
            tmp_path / "out",
            Options(),
            converter=SimpleNamespace(convert=convert),
            progress=lambda _: None,
        )
    manifest = json.loads((tmp_path / "out/_auditoria/manifest.json").read_text("utf-8"))
    assert manifest["counts"] == {"falhou": 1, "nao_processado": 1}
    assert "PDF danificado" in diagnostic(manifest, tmp_path / "out/_auditoria")


def test_default_report_groups_occurrences_and_keeps_evidence_separate(tmp_path):
    manifest = new_manifest(tmp_path, tmp_path / "out", [(tmp_path / "a.pdf", Path("a.md"))], {})
    manifest["status"] = "concluida"
    manifest["documents"][0].update(
        quality_status="review",
        state="rever",
        findings=[
            {
                "rule": "TABLE_SPAN",
                "severity": "warning",
                "line": i,
                "message": f"Células unidas {i}",
            }
            for i in range(40)
        ],
    )
    path = write_reports(manifest, tmp_path / "out", atomic_write)
    compact = path.read_text("utf-8")
    details = (path.parent / "detalhes.md").read_text("utf-8")
    assert "40 ocorrência(s)" in compact
    assert "Células unidas 39" not in compact
    assert "Células unidas 39" in details
    assert "Proveniência" not in compact and "detalhes.md" in compact



def test_relative_source_uses_forward_slashes_for_windows_paths():
    from pathlib import PureWindowsPath

    class WindowsPath(PureWindowsPath):
        def resolve(self):
            return self

        def is_dir(self):
            return True

    source = WindowsPath("C:/pdfs")
    output = WindowsPath("C:/results")
    pdf = source / "nested/documento.pdf"
    manifest = new_manifest(source, output, [(pdf, WindowsPath("nested/documento.md"))], {})
    assert manifest["documents"][0]["relative_source"] == "nested/documento.pdf"
    assert manifest["documents"][0]["source"] == str(pdf)
