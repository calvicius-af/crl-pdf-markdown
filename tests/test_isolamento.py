"""O Docling corre num processo à parte: uma falha nativa não leva a corrida.

No ensaio de 9 de outubro em Windows, a interface fechou-se duas vezes a meio
do lote com uma violação de acesso dentro do Docling. Estes testes provocam
falhas nativas reais (SIGSEGV) no processo de conversão.
"""

import json

import pytest

from crl_markdown import isolamento
from crl_markdown.pipeline import Options, run
from tests import worker_fakes
from tests.test_pipeline import _bte_inputs

pytest.importorskip("docling_core")


def _run(tmp_path, monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    out, lines = tmp_path / "out", []
    reports = run(
        _bte_inputs(tmp_path),
        out,
        Options(),
        progress=lines.append,
        converter_factory=worker_fakes.conversor,
    )
    return out, reports, lines


def test_native_crash_is_retried_in_a_new_process(tmp_path, monkeypatch):
    marks = tmp_path / "marcas"
    marks.mkdir()
    out, reports, lines = _run(
        tmp_path, monkeypatch, CRL_TESTE_FALHA="b.pdf", CRL_TESTE_MARCA=marks
    )
    assert [r["state"] != "falhou" for r in reports] == [True, True, True]
    assert any("falha nativa" in line and "a repetir b.pdf" in line for line in lines)
    assert "Fatal Python error" in (out / "_auditoria/falha_nativa.log").read_text("utf-8")
    assert (out / "2026/30/b.md").is_file()


def test_repeated_native_crash_fails_only_that_document(tmp_path, monkeypatch):
    out, reports, _lines = _run(tmp_path, monkeypatch, CRL_TESTE_FALHA="b.pdf")
    assert [r["state"] == "falhou" for r in reports] == [False, True, False]
    assert reports[1]["error_type"] == "FalhaNativa"
    assert "duas vezes" in reports[1]["error"]
    manifest = json.loads((out / "_auditoria/manifest.json").read_text("utf-8"))
    assert manifest["status"] == "concluida"


def test_python_errors_in_the_worker_keep_their_type(tmp_path, monkeypatch):
    inputs = _bte_inputs(tmp_path)
    (inputs / "2026/31/erro.pdf").write_bytes(b"%PDF erro")
    reports = run(
        inputs,
        tmp_path / "out",
        Options(),
        progress=lambda _: None,
        converter_factory=worker_fakes.conversor,
    )
    failed = [r for r in reports if r["state"] == "falhou"]
    assert [(r["error_type"], r["error"]) for r in failed] == [
        ("ValueError", "PDF ilegível neste ensaio")
    ]
    assert len(reports) == 4


def test_worker_is_renewed_every_few_documents(tmp_path, monkeypatch):
    pids = tmp_path / "pids"
    pids.mkdir()
    monkeypatch.setattr(isolamento, "RENOVAR_A_CADA", 2)
    _run(tmp_path, monkeypatch, CRL_TESTE_PIDS=pids)
    seen = {p.name: p.read_text() for p in pids.iterdir()}
    assert seen["a.pdf"] == seen["b.pdf"] != seen["c.pdf"]


def test_worker_dying_at_startup_does_not_break_the_run(tmp_path):
    reports = run(
        _bte_inputs(tmp_path),
        tmp_path / "out",
        Options(),
        progress=lambda _: None,
        converter_factory=worker_fakes.cai_ao_arrancar,
    )
    assert {(r["state"], r["error_type"]) for r in reports} == {("falhou", "FalhaNativa")}
