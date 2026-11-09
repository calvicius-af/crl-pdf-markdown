"""Progresso real: documentos terminados, estimativa e interrupções."""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from crl_markdown.pipeline import Options, run
from crl_markdown.progress import OperationProgress, ProgressReporter, duration


def test_percentage_only_changes_when_documents_complete_and_eta_uses_elapsed():
    now = [100.0]
    model = OperationProgress(clock=lambda: now[0])
    model.begin("Conversão")
    model.update({"stage": "preparing", "total": 4, "completed": 0})
    now[0] = 160.0
    model.update({"stage": "converting", "total": 4, "completed": 0, "document": "a.pdf"})
    assert model.snapshot()["percent"] == 0
    assert model.snapshot()["remaining"] is None
    model.update({"stage": "completed_document", "total": 4, "completed": 1})
    assert model.snapshot()["percent"] == 25
    assert model.snapshot()["remaining"] == 180
    now[0] = 190.0
    assert model.snapshot()["percent"] == 25  # tempo sozinho não inventa avanço
    assert model.snapshot()["remaining"] == 270
    model.update({"stage": "completed_document", "total": 4, "completed": 4})
    assert model.snapshot()["active"]  # ainda pode estar a escrever relatórios
    model.finish()
    now[0] = 500.0
    assert model.snapshot()["elapsed"] == 90
    assert not model.snapshot()["active"]


def test_interrupted_operation_keeps_measured_progress_and_new_run_resets_it():
    model = OperationProgress()
    model.begin("Conversão")
    model.update({"stage": "converting", "total": 3, "completed": 1})
    model.finish(failed=True)
    assert model.snapshot()["percent"] == pytest.approx(100 / 3)
    assert model.snapshot()["failed"]
    model.begin("Recolha")
    assert model.snapshot()["percent"] is None
    assert model.snapshot()["completed"] == 0
    assert not model.snapshot()["failed"]


def test_elapsed_time_is_readable_for_long_batches():
    assert duration(3 * 3600 + 125.9) == "03:02:05"
    assert duration(-1) == "00:00:00"


def test_pipeline_progress_covers_success_failure_and_finalization(tmp_path):
    source = tmp_path / "pdfs"
    source.mkdir()
    for name in ("a.pdf", "b.pdf"):
        (source / name).write_bytes(b"not a real PDF; converter is a failing fixture")

    def fail(_path):
        raise ValueError("PDF ilegível neste ensaio")

    events = []
    reporter = ProgressReporter(lambda line: None, events.append)
    reports = run(source, tmp_path / "out", Options(), converter=SimpleNamespace(convert=fail),
                  progress=reporter)
    assert all(report["state"] == "falhou" for report in reports)
    assert [(event["stage"], event["completed"]) for event in events] == [
        ("preparing", 0), ("converting", 0), ("completed_document", 1),
        ("converting", 1), ("completed_document", 2), ("finalizing", 2)]
    assert all(event["total"] == 2 for event in events)


def test_retry_messages_do_not_count_an_unfinished_document():
    events, lines = [], []
    reporter = ProgressReporter(lines.append, events.append)
    reporter("Corrida 20261109T120000Z-abc: 2 PDF de L:\\originais")
    reporter("[1/2] exemplo.pdf")
    reporter("  o processo de conversão terminou com uma falha nativa; a repetir num processo novo")
    assert events[-1]["completed"] == 0
    reporter("  rever")
    reporter("[2/2] outro.pdf")
    assert events[-1]["completed"] == 1
    reporter("  sem_alertas_automaticos (já convertido, reaproveitado)")
    assert events[-1]["completed"] == 2
    assert len(lines) == 6


def test_production_offline_guard_blocks_network_but_allows_local_ipc():
    code = '''
import socket, tempfile
from pathlib import Path
from crl_markdown.offline import install_guard, OfflineNetworkError
install_guard()
install_guard()
for attempt in (
    lambda: socket.create_connection(("127.0.0.1", 9)),
    lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("127.0.0.1", 9)),
    lambda: socket.getaddrinfo("example.invalid", 443),
    lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", ("127.0.0.1", 9)),
):
    try:
        attempt()
    except OfflineNetworkError:
        pass
    else:
        raise AssertionError("A rede não foi bloqueada")
if hasattr(socket, "AF_UNIX"):
    with tempfile.TemporaryDirectory() as folder:
        path = str(Path(folder) / "ipc")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(path)
            server.listen(1)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(path)
                connection, _ = server.accept()
                connection.close()
'''
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    subprocess.run([sys.executable, "-c", code], env=env, check=True, timeout=20)
