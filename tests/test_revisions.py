import json
from types import SimpleNamespace

import pytest
from docling_core.types.doc import DocItemLabel, DoclingDocument, Size

from crl_markdown.pipeline import Options, run
from crl_markdown.revisions import _apply_resolutions, audit_revision, create_revision
from crl_markdown.validation import _verified, decide, deliver
from tests.pdf_sintetico import escrever_pdf, pagina_bte


@pytest.fixture
def damaged_output(tmp_path):
    original = ['Convenção de ensaio', 'Cláusula 1.ª', 'Retribuição',
                '1- O saldo é -125,00 euros.', 'Depositado em 1 de janeiro de 2026.']
    pdf = escrever_pdf(tmp_path / 'source.pdf', [pagina_bte(1, original)])
    document = DoclingDocument(name='Ensaio')
    document.add_page(page_no=1, size=Size(width=595, height=842))
    for value in original:
        document.add_text(label=DocItemLabel.TEXT, text=value.replace('-125,00', '125,00'))
    converter = SimpleNamespace(docling_version='fixture',
                                convert=lambda _pdf: SimpleNamespace(status='success', document=document))
    output = tmp_path / 'output'
    reports = run(pdf, output, Options(), converter=converter, progress=lambda _: None)
    assert reports[0]['quality_status'] == 'blocked'
    return output


def test_correction_reaudits_without_overwriting_original_and_requires_new_approval(damaged_output, tmp_path):
    output = damaged_output
    original = (output / 'source.md').read_bytes()
    revision = create_revision(output, 'source.pdf', 'Revisor de ensaio')
    draft = revision / 'correcao.md'
    draft.write_text(draft.read_text().replace('125,00', '-125,00'))
    publication, report = audit_revision(revision)
    assert report['quality_status'] != 'blocked'
    assert (output / 'source.md').read_bytes() == original
    with pytest.raises(ValueError, match='Não há documentos'):
        deliver(output, tmp_path / 'unapproved')
    decide(output, 'source.pdf', reviewer='Revisor de ensaio', decision='aprovado',
           scope='integral', notes='Sinal negativo e documento integral conferidos no PDF.')
    result = deliver(output, tmp_path / 'approved')
    assert '-125,00' in (result.parent / 'documentos/source.md').read_text()
    (publication / 'source.md').write_text('alterado após aprovação')
    with pytest.raises(ValueError, match='Não há documentos'):
        deliver(output, tmp_path / 'tampered')


def test_competing_revision_cannot_overwrite_new_base(damaged_output):
    first = create_revision(damaged_output, 'source.pdf', 'Revisor A')
    second = create_revision(damaged_output, 'source.pdf', 'Revisor B')
    audit_revision(first)
    with pytest.raises(ValueError, match='Outra revisão'):
        audit_revision(second)


def test_reaudit_invalidates_previous_decision_even_for_same_text(damaged_output):
    revision = create_revision(damaged_output, 'source.pdf', 'Revisor A')
    draft = revision / 'correcao.md'
    draft.write_text(draft.read_text().replace('125,00', '-125,00'))
    audit_revision(revision)
    decision = decide(damaged_output, 'source.pdf', reviewer='Revisor A', decision='aprovado',
                      scope='integral', notes='Conferido.')
    before = json.loads(decision.read_text())
    audit_revision(revision)
    doc = json.loads((damaged_output / '_auditoria/manifest.json').read_text())['documents'][0]
    _, report_path, _ = _verified(damaged_output, doc)
    from crl_markdown.models import _sha256
    assert before['report_sha256'] != _sha256(report_path)


@pytest.mark.parametrize('rule,action,changed,allowed', [
    ('IMAGE', 'decorativo', False, True),
    ('IMAGE', 'transcrito', False, False),
    ('IMAGE', 'transcrito', True, True),
    ('TABLE_OVERLAP', 'corrigido', False, False),
    ('TABLE_OVERLAP', 'corrigido', True, True),
    ('AMOUNTS', 'corrigido', True, False),
    ('COMPLETENESS', 'conferido', True, False),
    ('REFERENCE_EMPTY', 'decorativo', True, False),
])
def test_resolution_is_specific_and_cannot_dismiss_independent_content_errors(rule, action, changed, allowed):
    report = {'pages': 2, 'table_content_changed': changed,
              'findings': [{'id': 'one', 'rule': rule, 'severity': 'error'}]}
    resolution = {'finding_id': 'one', 'page': 1, 'notes': 'Evidência conferida na região original.', 'action': action}
    if allowed:
        _apply_resolutions(report, [resolution], 'Revisor', changed)
        assert report['quality_status'] == 'passed'
        assert report['findings'][0]['original_severity'] == 'error'
    else:
        with pytest.raises(ValueError):
            _apply_resolutions(report, [resolution], 'Revisor', changed)
