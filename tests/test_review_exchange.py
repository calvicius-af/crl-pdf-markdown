import json
import shutil

import pytest

from crl_markdown.review_exchange import (
    export_review,
    inventory,
    merge_review,
    plan_merge,
    recover_imports,
)
from crl_markdown.validation import _load, _verified, decide, deliver
from tests.test_revisions import damaged_output  # noqa: F401
from tests.test_validation import reviewed_output  # noqa: F401


def approve(out, document, reviewer):
    return decide(out, document, reviewer=reviewer, decision='aprovado', scope='integral', notes='Conferido.')


def add_second(out):
    path = out / '_auditoria/manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    first = manifest['documents'][0]
    source = out.parent / 'b.pdf'
    shutil.copy2(out.parent / 'a.pdf', source)
    shutil.copy2(out / 'a.md', out / 'b.md')
    audit = out / '_auditoria/documentos'
    for suffix in ('.docling.json', '.docling.md', '.qualidade.json'):
        shutil.copy2(audit / ('a' + suffix), audit / ('b' + suffix))
    manifest['documents'].append({**first, 'source': str(source), 'relative_source': 'b.pdf'})
    path.write_text(json.dumps(manifest), encoding='utf-8')


def test_independent_reviews_merge_with_authorship_and_reimport_is_idempotent(reviewed_output, tmp_path):  # noqa: F811
    out = reviewed_output
    add_second(out)
    branch = export_review(out, tmp_path / 'pessoa-b', reviewer='Pessoa B')
    first = approve(out, 'a.pdf', 'Pessoa A')
    second = approve(branch, 'b.pdf', 'Pessoa B')
    plan = plan_merge(out, branch)
    assert not plan['conflicts'] and not plan['conflicted_documents']
    result = merge_review(out, branch, reviewer='Coordenador')
    assert result['imported'] == 1
    assert first.is_file()
    assert (out / second.relative_to(branch)).read_bytes() == second.read_bytes()
    assert merge_review(out, branch, reviewer='Coordenador')['imported'] == 0
    delivery = deliver(out, tmp_path / 'entrega')
    records = json.loads(delivery.with_suffix('.json').read_text(encoding='utf-8'))['documents']
    assert {r['human_review']['reviewer'] for r in records} == {'Pessoa A', 'Pessoa B'}
    receipt = json.loads((out / result['receipt']).read_text(encoding='utf-8'))
    assert receipt['status'] == 'complete' and receipt['reviewer'] == 'Coordenador'


def test_same_document_concurrent_decisions_refused_without_losing_either_copy(reviewed_output, tmp_path):  # noqa: F811
    out = reviewed_output
    branch = export_review(out, tmp_path / 'pessoa-b', reviewer='Pessoa B')
    approve(out, 'a.pdf', 'Pessoa A')
    approve(branch, 'a.pdf', 'Pessoa B')
    before_local, before_remote = inventory(out), inventory(branch)
    plan = plan_merge(out, branch)
    assert plan['conflicted_documents']
    with pytest.raises(ValueError, match='concorrentes'):
        merge_review(out, branch, reviewer='Coordenador')
    assert inventory(out) == before_local
    assert inventory(branch) == before_remote


def test_export_contains_hash_verified_pdfs_for_another_machine(reviewed_output, tmp_path):  # noqa: F811
    branch = export_review(reviewed_output, tmp_path / 'pessoa-b', reviewer='Pessoa B')
    (tmp_path / 'a.pdf').unlink()
    doc = _load(branch)['documents'][0]
    _verified(branch, doc)
    approve(branch, 'a.pdf', 'Pessoa B')
    assert (branch / '_auditoria/fontes-transferidas/fontes.json').is_file()


def test_damaged_base_or_altered_corpus_refuses_import(reviewed_output, tmp_path):  # noqa: F811
    out = reviewed_output
    branch = export_review(out, tmp_path / 'pessoa-b', reviewer='Pessoa B')
    (branch / 'a.md').write_text('Alteração fora do editor', encoding='utf-8')
    with pytest.raises(ValueError, match='alterar o corpus'):
        plan_merge(out, branch)
    (branch / 'a.md').unlink()
    with pytest.raises(ValueError, match='perdeu ficheiros'):
        plan_merge(out, branch)


def test_old_human_decision_cannot_be_rewritten_through_import(reviewed_output, tmp_path):  # noqa: F811
    out = reviewed_output
    old = approve(out, 'a.pdf', 'Pessoa A')
    branch = export_review(out, tmp_path / 'pessoa-b', reviewer='Pessoa B')
    path = branch / old.relative_to(out)
    data = json.loads(path.read_text(encoding='utf-8'))
    data['notes'] = 'Tentativa de alterar uma decisão antiga'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='imutável'):
        plan_merge(out, branch)


def test_import_failure_rolls_back_applied_files(reviewed_output, tmp_path, monkeypatch):  # noqa: F811
    out = reviewed_output
    add_second(out)
    branch = export_review(out, tmp_path / 'pessoa-b', reviewer='Pessoa B')
    approve(branch, 'a.pdf', 'Pessoa B')
    approve(branch, 'b.pdf', 'Pessoa B')
    before = inventory(out)
    from pathlib import Path
    replace = Path.replace
    count = 0

    def fail_second(path, target):
        nonlocal count
        if path.name.startswith('.importacao-'):
            count += 1
            if count == 2:
                raise OSError('Interrupção simulada')
        return replace(path, target)

    monkeypatch.setattr(Path, 'replace', fail_second)
    with pytest.raises(OSError, match='Interrupção'):
        merge_review(out, branch, reviewer='Coordenador')
    after = inventory(out)
    assert all(after[name] == digest for name, digest in before.items())
    assert not list((out / '_auditoria/revisoes').rglob('*.json'))
    receipt = next((out / '_auditoria/intercambios').glob('*/importacao.json'))
    assert json.loads(receipt.read_text(encoding='utf-8'))['status'] == 'rolled_back'


def test_interrupted_import_blocks_review_until_safe_recovery(reviewed_output):  # noqa: F811
    out = reviewed_output
    journal = out / '_auditoria/intercambios/test'
    journal.mkdir(parents=True)
    new = '_auditoria/notas/doc/new.json'
    path = out / new
    path.parent.mkdir(parents=True)
    path.write_text('{}', encoding='utf-8')
    from crl_markdown.models import _sha256
    receipt = journal / 'importacao.json'
    receipt.write_text(json.dumps({'schema': 1, 'status': 'prepared', 'files': {new: _sha256(path)},
                                  'previous': {new: None}}), encoding='utf-8')
    with pytest.raises(ValueError, match='importação foi interrompida'):
        _load(out)
    assert recover_imports(out) == [str(receipt)]
    assert not path.exists()
    assert _load(out)['documents']


def test_receipt_with_path_traversal_is_refused(reviewed_output, tmp_path):  # noqa: F811
    out = reviewed_output
    branch = export_review(out, tmp_path / 'pessoa-b', reviewer='Pessoa B')
    meta = branch / '_auditoria/intercambio.json'
    data = json.loads(meta.read_text(encoding='utf-8'))
    data['base_files']['../../escape'] = 'a' * 64
    meta.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='Inventário de base inválido'):
        plan_merge(out, branch)


def test_audited_correction_and_approval_return_to_main_corpus(damaged_output, tmp_path):  # noqa: F811
    from crl_markdown.revisions import audit_revision, create_revision
    out = damaged_output
    branch = export_review(out, tmp_path / 'pessoa-b', reviewer='Pessoa B')
    revision = create_revision(branch, 'source.pdf', 'Pessoa B')
    draft = revision / 'correcao.md'
    draft.write_text(draft.read_text(encoding='utf-8').replace('125,00', '-125,00'), encoding='utf-8')
    audit_revision(revision)
    approve(branch, 'source.pdf', 'Pessoa B')
    result = merge_review(out, branch, reviewer='Coordenador')
    assert result['imported'] > 1
    document = _load(out)['documents'][0]
    target, _, report = _verified(out, document)
    assert target.is_relative_to(out)
    assert '-125,00' in target.read_text(encoding='utf-8')
    assert report['revision']['reviewer'] == 'Pessoa B'
    delivered = deliver(out, tmp_path / 'entrega-corrigida')
    assert '-125,00' in (delivered.parent / 'documentos/source.md').read_text(encoding='utf-8')
    assert merge_review(out, branch, reviewer='Coordenador')['imported'] == 0


def _parallel_decision(output, document, reviewer, start, results):
    import time
    from pathlib import Path

    from crl_markdown import validation
    original_load = validation._load

    def slow_load(path):
        time.sleep(.03)
        return original_load(path)

    validation._load = slow_load
    start.wait(5)
    for _ in range(50):
        try:
            validation.decide(Path(output), document, reviewer=reviewer, decision='aprovado',
                              scope='integral', notes='Conferido em paralelo.', expected_decision=None)
            results.put('saved')
            return
        except RuntimeError:
            time.sleep(.01)
        except ValueError as error:
            results.put(str(error))
            return
    results.put('timeout')


@pytest.mark.parametrize('same_document', [False, True])
def test_two_processes_keep_decisions_and_detect_stale_review(reviewed_output, same_document):  # noqa: F811
    import multiprocessing
    out = reviewed_output
    add_second(out)
    context = multiprocessing.get_context('spawn')
    start, results = context.Event(), context.Queue()
    workers = [context.Process(target=_parallel_decision,
                              args=(str(out), doc, who, start, results))
               for doc, who in [('a.pdf', 'Pessoa A'), ('a.pdf' if same_document else 'b.pdf', 'Pessoa B')]]
    try:
        for worker in workers:
            worker.start()
        start.set()
        messages = [results.get(timeout=15) for _ in workers]
        for worker in workers:
            worker.join(5)
            assert worker.exitcode == 0
        assert messages.count('saved') == (1 if same_document else 2)
        if same_document:
            assert any('Outra pessoa' in message for message in messages)
        assert len(list((out / '_auditoria/revisoes').rglob('*.json'))) == (1 if same_document else 2)
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.kill()
            worker.join()


def test_manual_sync_of_competing_decisions_blocks_delivery(reviewed_output, tmp_path):  # noqa: F811
    from crl_markdown.validation import decision_branches, review_head
    out = reviewed_output
    first = export_review(out, tmp_path / 'a', reviewer='Pessoa A')
    second = export_review(out, tmp_path / 'b', reviewer='Pessoa B')
    for branch, who in [(first, 'Pessoa A'), (second, 'Pessoa B')]:
        decision = approve(branch, 'a.pdf', who)
        target = out / decision.relative_to(branch)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(decision, target)
    with pytest.raises(ValueError, match='concorrentes'):
        review_head(out, 'a.pdf')
    with pytest.raises(ValueError, match='Não há documentos'):
        deliver(out, tmp_path / 'nao-entregar')
    branches = decision_branches(out, 'a.pdf')
    assert len(branches) == 2
    decide(out, 'a.pdf', reviewer='Coordenador', decision='aprovado', scope='integral',
           notes='Conferência integral e reconciliação dos dois pareceres.', reconcile_heads=list(branches))
    assert len(decision_branches(out, 'a.pdf')) == 1
    assert len(list((out / '_auditoria/revisoes').rglob('*.json'))) == 3
    assert deliver(out, tmp_path / 'entrega-reconciliada').is_file()
