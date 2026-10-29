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
    manifest = json.loads((out / "_auditoria/manifest.json").read_text("utf-8"))
    events = manifest['execution_events']
    assert [(event['kind'], event['attempt']) for event in events] == [
        ('worker_exit', 1), ('recovered', 2),
    ]
    assert events[0]['exitcode'] not in (None, 0)
    assert events[0]['retry'] is True
    assert events[0]['source'].endswith('b.pdf')
    assert events[0]['at_utc'].endswith('+00:00')
    diagnostic = (out / '_auditoria/diagnostico.md').read_text('utf-8')
    assert 'Incidentes de execução' in diagnostic
    assert 'Documentos recuperados numa nova tentativa: **1**' in diagnostic
    native = (out / '_auditoria/falha_nativa.log').read_text('utf-8')
    assert 'b.pdf\nUTC:' in native


def test_repeated_native_crash_fails_only_that_document(tmp_path, monkeypatch):
    out, reports, _lines = _run(tmp_path, monkeypatch, CRL_TESTE_FALHA="b.pdf")
    assert [r["state"] == "falhou" for r in reports] == [False, True, False]
    assert reports[1]["error_type"] == "FalhaNativa"
    assert "duas vezes" in reports[1]["error"]
    manifest = json.loads((out / "_auditoria/manifest.json").read_text("utf-8"))
    assert manifest["status"] == "concluida"
    assert [event['kind'] for event in manifest['execution_events']] == [
        'worker_exit', 'worker_exit',
    ]
    assert manifest['execution_events'][-1]['retry'] is False


def test_timeout_is_not_a_native_crash_and_next_document_continues(tmp_path, monkeypatch):
    original = isolamento.ConversorIsolado._esperar

    def timeout_once(self, prazo):
        if not self.events:
            self.processo.kill()
            return ('prazo',)
        return original(self, prazo)

    monkeypatch.setattr(isolamento.ConversorIsolado, '_esperar', timeout_once)
    out, reports, _lines = _run(tmp_path, monkeypatch)
    assert reports[0]['error_type'] == 'TimeoutError'
    assert reports[0]['recovery']['code'] == 'CRL-TEMPO'
    assert all(report['state'] != 'falhou' for report in reports[1:])
    manifest = json.loads((out / '_auditoria/manifest.json').read_text('utf-8'))
    assert [event['kind'] for event in manifest['execution_events']] == ['timeout']
    assert manifest['execution_events'][0]['attempt'] == 1
    assert manifest['status'] == 'concluida'


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
    assert "worker_fakes.py" in failed[0]["traceback"]
    assert "ValueError: PDF ilegível" in failed[0]["traceback"]


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


def test_crash_at_startup_never_overwrites_existing_manual_output(tmp_path):
    inputs = _bte_inputs(tmp_path)
    out = tmp_path / 'out'
    target = out / '2026/29/a.md'
    target.parent.mkdir(parents=True)
    target.write_text('Texto conferido manualmente', encoding='utf-8')
    reports = run(inputs, out, Options(), progress=lambda _: None,
                  converter_factory=worker_fakes.cai_ao_arrancar)
    assert reports[0]['error_type'] == 'FileExistsError'
    assert target.read_text(encoding='utf-8') == 'Texto conferido manualmente'
