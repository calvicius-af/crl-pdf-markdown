import json
import shutil
from pathlib import Path

import pytest

from crl_markdown.drafts import DraftSession, confirm_discard_or_save
from crl_markdown.pipeline import Options, atomic_write, run
from crl_markdown.report import new_manifest, write_reports
from crl_markdown.review_history import load_history
from crl_markdown.validation import _load, _verified, decide, deliver
from tests.test_validation import reviewed_output  # noqa: F401


def full_manifest(output):
    old = json.loads((output / '_auditoria/manifest.json').read_text(encoding='utf-8'))
    pdf = Path(old['documents'][0]['source'])
    manifest = new_manifest(pdf, output, [(pdf, Path('a.md'))], {})
    manifest['run_id'] = '20000101-original'
    record = {**manifest['documents'][0], **old['documents'][0], 'state': 'rever'}
    record['findings'] = [{**f, 'message': 'Conferir estrutura'} for f in record['findings']]
    manifest.update(documents=[record], status='concluida')
    return manifest


def test_324_documents_survive_single_document_ocr_attempt(reviewed_output, tmp_path):  # noqa: F811
    output = reviewed_output
    original = full_manifest(output)
    for i in range(323):
        stem = f'doc-{i}'
        source = tmp_path / (stem + '.pdf')
        shutil.copy2(tmp_path / 'a.pdf', source)
        shutil.copy2(output / 'a.md', output / (stem + '.md'))
        audit = output / '_auditoria/documentos'
        for suffix in ('.docling.json', '.docling.md', '.qualidade.json'):
            shutil.copy2(audit / ('a' + suffix), audit / (stem + suffix))
        original['documents'].append({**original['documents'][0], 'relative_source': stem + '.pdf',
                                      'source': str(source), 'output': str(output / (stem + '.md'))})
    write_reports(original, output, atomic_write)
    decision = decide(output, 'a.pdf', reviewer='Pessoa A', decision='aprovado',
                      scope='integral', notes='Conferido antes do OCR.')
    evidence = {p: p.read_bytes() for p in output.rglob('*') if p.is_file()}
    pdf = tmp_path / 'acordao.pdf'
    pdf.write_bytes(b'OCR fixture')

    # Testa a seleção/publicação do lote com OCR, sem fingir um ensaio do motor OCR.
    def provider(source, target, audit):
        return {'source': str(source), 'state': 'rever', 'quality_status': 'review',
                'findings': [], 'options': {'ocr': True}}

    run(pdf, output, Options(ocr=True), report_provider=provider, progress=lambda _: None)
    latest = json.loads((output / '_auditoria/manifest.json').read_text(encoding='utf-8'))
    assert len(latest['documents']) == 1
    restored = _load(output)
    assert len(restored['documents']) == 325
    assert sum(restored['counts'].values()) == 325
    assert len(load_history(output)['documents']) == 325  # reabrir a aplicação
    for p, content in evidence.items():
        if p == decision or '/documentos/' in p.as_posix() or '/corridas/' in p.as_posix():
            assert p.read_bytes() == content
    doc = next(d for d in restored['documents'] if d['relative_source'] == 'a.pdf')
    _verified(output, doc)
    result = deliver(output, tmp_path / 'entrega-recuperada')
    assert (result.parent / 'documentos/a.md').is_file()
    data = json.loads(result.with_suffix('.json').read_text(encoding='utf-8'))
    assert data['documents'][0]['human_review']['run_id'] == original['run_id']


def test_history_recovers_even_if_current_manifest_is_missing(reviewed_output):  # noqa: F811
    out = reviewed_output
    manifest = full_manifest(out)
    write_reports(manifest, out, atomic_write)
    (out / '_auditoria/manifest.json').unlink()
    assert _load(out)['documents'][0]['relative_source'] == 'a.pdf'


def test_incomplete_attempt_keeps_reviewable_version_and_error(reviewed_output):  # noqa: F811
    out = reviewed_output
    manifest = full_manifest(out)
    write_reports(manifest, out, atomic_write)
    failed = {**manifest, 'run_id': 'zzz-new', 'documents': [
        {'relative_source': 'a.pdf', 'source': manifest['documents'][0]['source'],
         'state': 'falhou', 'error': 'OCR interrompido'}]}
    write_reports(failed, out, atomic_write)
    doc = _load(out)['documents'][0]
    assert doc['quality_status'] == 'review'
    assert doc['latest_attempt']['error'] == 'OCR interrompido'
    _verified(out, doc)


def test_overwrite_with_human_review_refused_before_changing_manifest(reviewed_output):  # noqa: F811
    out = reviewed_output
    decide(out, 'a.pdf', reviewer='Pessoa A', decision='aprovado',
           scope='integral', notes='Conferido.')
    before = {p: p.read_bytes() for p in out.rglob('*') if p.is_file()}
    pdf = Path(_load(out)['documents'][0]['source'])
    with pytest.raises(ValueError, match='correções ou decisões'):
        run(pdf, out, Options(), overwrite=True, progress=lambda _: None)
    for p, content in before.items():
        assert p.read_bytes() == content


def test_same_output_name_from_different_source_is_refused(reviewed_output, tmp_path):  # noqa: F811
    folder = tmp_path / 'other'
    folder.mkdir()
    pdf = folder / 'a.pdf'
    pdf.write_bytes(b'Outro PDF')
    with pytest.raises(ValueError, match='Outro PDF'):
        run(pdf, reviewed_output, Options(), overwrite=True, progress=lambda _: None)


def test_manual_markdown_edit_is_not_destroyed_by_overwrite(reviewed_output):  # noqa: F811
    out = reviewed_output
    path = out / 'a.md'
    path.write_text('Correção humana feita fora da aplicação', encoding='utf-8')
    pdf = Path(_load(out)['documents'][0]['source'])
    before = path.read_bytes()
    with pytest.raises(ValueError, match='Markdown foi alterado'):
        run(pdf, out, Options(), overwrite=True, progress=lambda _: None)
    assert path.read_bytes() == before


def test_legacy_unarchived_manifest_is_kept_before_next_run(reviewed_output, tmp_path):  # noqa: F811
    pdf = tmp_path / 'new.pdf'
    pdf.touch()
    run(pdf, reviewed_output, Options(), report_provider=lambda *args: {
        'state': 'falhou', 'error': 'Erro de ensaio'}, progress=lambda _: None)
    assert {d['relative_source'] for d in _load(reviewed_output)['documents']} == {'a.pdf', 'new.pdf'}


def test_invalid_history_is_reported_instead_of_silently_dropping_documents(tmp_path):
    out = tmp_path / 'out'
    path = out / '_auditoria/corridas/old/manifest.json'
    path.parent.mkdir(parents=True)
    path.write_text('{broken', encoding='utf-8')
    with pytest.raises(ValueError, match='ilegível'):
        load_history(out)


def test_draft_concurrent_saves_keep_first_changes_and_reject_stale_session(tmp_path):
    path = tmp_path / 'correcao.md'
    path.write_text('Base', encoding='utf-8')
    first, second = DraftSession(path), DraftSession(path)
    first.save('Correção da pessoa A')
    with pytest.raises(ValueError, match='outra janela ou máquina'):
        second.save('Correção da pessoa B')
    assert path.read_text(encoding='utf-8') == 'Correção da pessoa A'
    assert second.text == 'Base'
    reopened = DraftSession(path)
    assert reopened.text == 'Correção da pessoa A'


@pytest.mark.parametrize('answer,save_result,expected', [
    (None, True, False), (False, True, True), (True, True, True), (True, False, False)])
def test_close_guard_cancel_discard_save_and_failed_save(monkeypatch, answer, save_result, expected):
    calls = []
    monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: answer)

    def save():
        calls.append(1)
        return save_result

    assert confirm_discard_or_save(None, True, save) is expected
    assert bool(calls) is (answer is True)


def test_clean_editor_closes_without_prompt(monkeypatch):
    monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: pytest.fail('prompt'))
    assert confirm_discard_or_save(None, False, lambda: pytest.fail('save'))
