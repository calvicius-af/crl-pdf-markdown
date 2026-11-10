import json

import pytest

from crl_markdown.occurrences import confirm_absence, history, version_key
from crl_markdown.revisions import audit_revision, create_revision
from tests.test_revisions import damaged_output  # noqa: F401
from tests.test_validation import reviewed_output  # noqa: F401


def test_missing_error_remains_until_explicit_current_version_confirmation(damaged_output):  # noqa: F811
    out = damaged_output
    before = history(out, 'source.pdf')
    errors = [r for r in before['occurrences'] if r['finding']['rule'] == 'AMOUNTS']
    assert errors and all(r['status'] == 'pending' for r in errors)
    old = errors[0]
    with pytest.raises(ValueError, match='atuais exigem'):
        confirm_absence(out, 'source.pdf', old['occurrence_id'], reviewer='Pessoa A',
                        notes='Não pode dispensar montantes atuais.', expected_version=before['current_version_id'])
    revision = create_revision(out, 'source.pdf', 'Pessoa A')
    draft = revision / 'correcao.md'
    draft.write_text(draft.read_text(encoding='utf-8').replace('125,00', '-125,00'), encoding='utf-8')
    audit_revision(revision)
    after = history(out, 'source.pdf')
    recovered = next(r for r in after['occurrences'] if r['occurrence_id'] == old['occurrence_id'])
    assert recovered['status'] == 'absent_unconfirmed'
    assert recovered['observations']
    with pytest.raises(ValueError, match='mudou'):
        confirm_absence(out, 'source.pdf', old['occurrence_id'], reviewer='Pessoa A',
                        notes='Sinal conferido.', expected_version=before['current_version_id'])
    confirmation = confirm_absence(out, 'source.pdf', old['occurrence_id'], reviewer='Pessoa A',
                                  notes='Sinal negativo conferido no PDF.', expected_version=after['current_version_id'])
    saved = history(out, 'source.pdf')
    row = next(r for r in saved['occurrences'] if r['occurrence_id'] == old['occurrence_id'])
    assert row['status'] == 'human_resolved'
    assert row['resolution']['reviewer'] == 'Pessoa A'
    assert json.loads(confirmation.read_text(encoding='utf-8'))['previous_status'] == 'absent_unconfirmed'
    # Uma nova versão não herda a confirmação como uma dispensa do erro real.
    second = create_revision(out, 'source.pdf', 'Pessoa B')
    text = second / 'correcao.md'
    text.write_text(text.read_text(encoding='utf-8').replace('-125,00', '125,00'), encoding='utf-8')
    audit_revision(second)
    latest = history(out, 'source.pdf')
    assert any(r['finding']['rule'] == 'AMOUNTS' and r['status'] == 'pending'
               for r in latest['occurrences'])
    assert confirmation.is_file()


def test_missing_pdf_keeps_historical_occurrences_visible(reviewed_output):  # noqa: F811
    out = reviewed_output
    before = history(out, 'a.pdf')
    from pathlib import Path

    from crl_markdown.validation import _load
    Path(_load(out)['documents'][0]['source']).unlink()
    after = history(out, 'a.pdf')
    assert len(after['occurrences']) == len(before['occurrences'])
    assert all(r['status'] == 'unverified' for r in after['occurrences'])
    assert after['verification_error']


def test_source_change_invalidates_historical_confirmation(reviewed_output, monkeypatch):  # noqa: F811
    out = reviewed_output
    before = history(out, 'a.pdf')
    from crl_markdown.validation import _load
    current = {**_load(out)['documents'][0], 'source_sha256': 'changed-source', 'findings': []}
    monkeypatch.setattr('crl_markdown.validation._verified', lambda *a: (None, None, current))
    after = history(out, 'a.pdf')
    row = after['occurrences'][0]
    assert row['status'] == 'source_changed'
    assert after['current_version_id'] != before['current_version_id']
    assert after['current_version_id'] == version_key(current)


def test_tampered_snapshot_is_not_silently_accepted(reviewed_output):  # noqa: F811
    history(reviewed_output, 'a.pdf')
    snapshot = next((reviewed_output / '_auditoria/ocorrencias').rglob('versoes/*.json'))
    data = json.loads(snapshot.read_text(encoding='utf-8'))
    data['findings'] = []
    snapshot.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='perdeu integridade'):
        history(reviewed_output, 'a.pdf')


@pytest.mark.parametrize('context', ['docling_version', 'docling_document_sha256', 'model_manifest_sha256', 'options'])
def test_new_extraction_or_model_context_gets_distinct_review_version(context):
    base = {'source_sha256': 'source', 'markdown_sha256': 'text', 'findings': []}
    changed = {**base, context: {'ocr': True} if context == 'options' else 'changed'}
    assert version_key(base) != version_key(changed)
