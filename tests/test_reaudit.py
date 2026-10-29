import hashlib
import json
import threading

import pytest

from crl_markdown.cli import main
from crl_markdown.pipeline import Options, run
from crl_markdown.reaudit import plan_reaudit, reaudit
from tests.test_pipeline import converter  # noqa: F401


def test_reaudit_preserves_subfolders_and_never_initializes_models(tmp_path, converter, monkeypatch):  # noqa: F811
    source = tmp_path / 'pdfs'
    (source / 'PRI').mkdir(parents=True)
    (source / 'PRI/a.pdf').write_bytes(b'fixture')
    output = tmp_path / 'output'
    run(source, output, Options(), converter=converter, progress=lambda _: None)
    original = (output / '_auditoria/manifest.json').read_bytes()
    def unexpected(*args, **kwargs):
        raise AssertionError('Não carregar modelos numa reauditoria')
    monkeypatch.setattr('crl_markdown.pipeline.make_converter', unexpected)
    destination, reports = reaudit(output, tmp_path / 'new', progress=lambda _: None)
    assert len(reports) == 1 and reports[0]['cached_extraction']
    assert (destination / 'PRI/a.md').exists()
    assert (output / '_auditoria/manifest.json').read_bytes() == original
    with pytest.raises(FileExistsError):
        reaudit(output, destination)


def test_compact_manifest_keeps_detail_hashes_but_not_corpus_copies(tmp_path, converter):  # noqa: F811
    pdf = tmp_path / 'a.pdf'
    pdf.write_bytes(b'fixture')
    output = tmp_path / 'out'
    reports = run(pdf, output, Options(), converter=converter, progress=lambda _: None)
    data = json.loads((output / '_auditoria/manifest.json').read_text(encoding='utf-8'))
    assert data['schema_version'] == 2
    assert 'structured_text' not in data['documents'][0]
    assert data['documents'][0]['markdown_sha256'] == reports[0]['markdown_sha256']
    detail = json.loads((output / data['documents'][0]['detail_report']).read_text(encoding='utf-8'))
    assert detail['structured_text'] == reports[0]['structured_text']


def test_parallel_reaudit_uses_manifest_paths_and_does_not_adopt_inflight_reports(tmp_path, converter):  # noqa: F811
    source = tmp_path / 'source'
    for family in ['a', 'b', 'c', 'd']:
        (source / family).mkdir(parents=True)
        (source / family / 'same.pdf').write_bytes(family.encode())
    output = tmp_path / 'out'
    run(source, output, Options(), converter=converter, progress=lambda _: None)
    _destination, reports = reaudit(output, tmp_path / 'new', jobs=2, progress=lambda _: None)
    assert len(reports) == 4
    assert all(r.get('cached_extraction') and r['state'] != 'falhou' for r in reports)
    assert len({r['source_sha256'] for r in reports}) == 4


@pytest.mark.parametrize('jobs', [1, 2])
def test_cancelled_reaudit_records_interruption_without_changing_original(tmp_path, converter, jobs):  # noqa: F811
    source = tmp_path / 'source'
    source.mkdir()
    for name in ['a.pdf', 'b.pdf']:
        (source / name).write_bytes(b'fixture')
    output = tmp_path / 'out'
    run(source, output, Options(), converter=converter, progress=lambda _: None)
    original = (output / '_auditoria/manifest.json').read_bytes()
    cancel = threading.Event()
    cancel.set()
    destination = tmp_path / 'cancelled'
    with pytest.raises(RuntimeError, match='cancelada'):
        reaudit(output, destination, families=['.'], jobs=jobs,
                cancel_event=cancel, progress=lambda _: None)
    partial = json.loads((destination / '_auditoria/manifest.json').read_text(encoding='utf-8'))
    assert partial['status'] == 'interrompida'
    assert partial['provenance']['filters']['families'] == ['.']
    assert partial['provenance']['selected_documents'] == ['a.pdf', 'b.pdf']
    assert (output / '_auditoria/manifest.json').read_bytes() == original


@pytest.fixture
def selection_output(tmp_path):
    output = tmp_path / 'previous'
    audit = output / '_auditoria'
    audit.mkdir(parents=True)
    documents = []
    for relative, state, rules in [
        ('convencoes/PRI/a.pdf', 'blocked', ['AMOUNTS', 'TABLE_OVERLAP']),
        ('convencoes/APU/a.pdf', 'review', ['STRUCTURE']),
        ('portarias_extensao/a.pdf', 'review', ['STRUCTURE']),
        ('acordaos/a.pdf', 'passed', []),
        ('root.pdf', 'passed', []),
    ]:
        documents.append({'relative_source': relative, 'quality_status': state,
                          'findings': [{'rule': rule} for rule in rules]})
    documents.append({'relative_source': 'failed.pdf', 'state': 'falhou'})
    (audit / 'manifest.json').write_text(json.dumps({
        'run_id': 'previous-run', 'documents': documents}), encoding='utf-8')
    return output


def test_selection_combines_categories_and_unions_repeated_values(selection_output):
    _, selected, provenance = plan_reaudit(
        selection_output, families=['convencoes'], rules=['STRUCTURE', 'AMOUNTS'],
        statuses=['review', 'blocked'])
    assert [d['relative_source'] for d in selected] == [
        'convencoes/PRI/a.pdf', 'convencoes/APU/a.pdf']
    assert provenance['total_documents'] == 6
    assert provenance['selection_basis'] == 'previous_run'
    content = (selection_output / '_auditoria/manifest.json').read_bytes()
    assert provenance['manifest_sha256'] == hashlib.sha256(content).hexdigest()
    _, selected, _ = plan_reaudit(selection_output, families=['.', 'acordaos'], statuses=['passed'])
    assert [d['relative_source'] for d in selected] == ['acordaos/a.pdf', 'root.pdf']


@pytest.mark.parametrize('filters, message', [
    ({'families': ['typo']}, 'família desconhecido'),
    ({'rules': ['TYPO']}, 'regra desconhecido'),
    ({'statuses': ['approved']}, 'estado desconhecido'),
    ({'families': ['acordaos'], 'rules': ['AMOUNTS']}, 'Nenhum documento'),
    ({'relative_source': 'missing.pdf'}, 'Nenhum documento'),
    ({}, 'extração completa'),
    ({'relative_source': 'failed.pdf'}, 'extração completa'),
])
def test_invalid_or_empty_selection_never_creates_destination(selection_output, tmp_path, filters, message):
    destination = tmp_path / 'new'
    with pytest.raises(ValueError, match=message):
        reaudit(selection_output, destination, **filters)
    assert not destination.exists()


def test_dry_run_does_not_open_cache_or_write_even_on_invalid_filters(selection_output, tmp_path, capsys, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError('A simulação não abre cache nem modelos')
    monkeypatch.setattr('crl_markdown.reaudit.CachedConverter', unexpected)
    original = {p: p.read_bytes() for p in selection_output.rglob('*') if p.is_file()}
    destination = tmp_path / 'new'
    args = ['reaudit', '--out', str(selection_output), '--destination', str(destination), '--dry-run']
    assert main([*args, '--family', 'convencoes', '--status', 'blocked', '--rule', 'AMOUNTS']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['selected_documents'] == ['convencoes/PRI/a.pdf']
    assert main([*args, '--rule', 'TYPO']) == 1
    assert 'regra desconhecido' in capsys.readouterr().err
    assert {p: p.read_bytes() for p in selection_output.rglob('*') if p.is_file()} == original
    assert not destination.exists()


@pytest.mark.parametrize('jobs', [1, 2])
def test_filtered_reaudit_keeps_all_checks_and_archives_selection(tmp_path, converter, jobs):  # noqa: F811
    source = tmp_path / 'source'
    for relative in ['convencoes/PRI/a.pdf', 'convencoes/APU/a.pdf', 'portarias_extensao/a.pdf']:
        pdf = source / relative
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b'fixture')
    output = tmp_path / 'old'
    run(source, output, Options(), converter=converter, progress=lambda _: None)
    manifest_path = output / '_auditoria/manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8'))
    # Uma regra da política anterior pode desaparecer; a seleção continua reproduzível.
    for doc in previous['documents']:
        doc['findings'].append({'rule': 'OLD_RULE', 'severity': 'warning', 'message': 'anterior'})
    manifest_path.write_text(json.dumps(previous), encoding='utf-8')
    original = {p: p.read_bytes() for p in output.rglob('*') if p.is_file()}
    destination, reports = reaudit(output, tmp_path / 'new', families=['convencoes'],
                                   rules=['OLD_RULE'], jobs=jobs, progress=lambda _: None)
    assert len(reports) == 2
    assert all(r['cached_extraction'] and r['quality_status'] == 'blocked' for r in reports)
    assert all(r['findings'] and all(f['rule'] != 'OLD_RULE' for f in r['findings']) for r in reports)
    assert (destination / 'convencoes/PRI/a.md').is_file()
    assert (destination / 'convencoes/APU/a.md').is_file()
    assert not (destination / 'portarias_extensao').exists()
    current = json.loads((destination / '_auditoria/manifest.json').read_text(encoding='utf-8'))
    assert current['provenance']['manifest_sha256'] == hashlib.sha256(original[manifest_path]).hexdigest()
    assert current['provenance']['filters']['rules'] == ['OLD_RULE']
    archive = destination / '_auditoria/corridas' / current['run_id']
    archived = json.loads((archive / 'manifest.json').read_text(encoding='utf-8'))
    assert archived['provenance'] == current['provenance']
    for folder in [destination / '_auditoria', archive]:
        text = (folder / 'diagnostico.md').read_text(encoding='utf-8')
        assert '2 de 3' in text and 'OLD' in text and 'todos os controlos atuais' in text
    assert {p: p.read_bytes() for p in output.rglob('*') if p.is_file()} == original


@pytest.mark.parametrize('jobs', [1, 2])
@pytest.mark.parametrize('replacement', ['pdf', 'extraction', 'missing_manifest_hash'])
def test_reaudit_rejects_a_consistent_cache_replaced_after_manifest(tmp_path, converter, jobs, replacement):  # noqa: F811
    source = tmp_path / 'source'
    source.mkdir()
    for name in ['a.pdf', 'b.pdf']:
        (source / name).write_bytes(b'fixture')
    output = tmp_path / 'old'
    run(source, output, Options(), converter=converter, progress=lambda _: None)
    manifest_bytes = (output / '_auditoria/manifest.json').read_bytes()
    audit = output / '_auditoria/documentos'
    metadata_path = audit / 'a.qualidade.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    if replacement == 'pdf':
        (source / 'a.pdf').write_bytes(b'new PDF')
        metadata['source_sha256'] = hashlib.sha256(b'new PDF').hexdigest()
    elif replacement == 'extraction':
        extraction_path = audit / 'a.docling.json'
        extraction = json.loads(extraction_path.read_text(encoding='utf-8'))
        extraction['name'] = 'new extraction'
        extraction_path.write_text(json.dumps(extraction), encoding='utf-8')
        metadata['docling_document_sha256'] = hashlib.sha256(extraction_path.read_bytes()).hexdigest()
    else:
        manifest_path = output / '_auditoria/manifest.json'
        manifest = json.loads(manifest_bytes)
        del manifest['documents'][0]['docling_document_sha256']
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        manifest_bytes = manifest_path.read_bytes()
    metadata_path.write_text(json.dumps(metadata), encoding='utf-8')
    _, reports = reaudit(output, tmp_path / 'new', jobs=jobs, progress=lambda _: None)
    assert reports[0]['state'] == 'falhou'
    assert 'manifesto' in reports[0]['error']
    assert reports[1]['cached_extraction'] and reports[1]['state'] != 'falhou'
    assert (output / '_auditoria/manifest.json').read_bytes() == manifest_bytes
