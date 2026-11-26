import hashlib
import json

import pytest

from crl_markdown.locking import exclusive
from crl_markdown.validation import decide, deliver


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def reviewed_output(tmp_path):
    output = tmp_path / 'out'
    audit = output / '_auditoria/documentos'
    audit.mkdir(parents=True)
    pdf = tmp_path / 'a.pdf'
    pdf.write_bytes(b'%PDF fixture')
    md = output / 'a.md'
    md.write_text('# Documento\n\nTexto', encoding='utf-8')
    (audit / 'a.docling.json').write_text('{}', encoding='utf-8')
    (audit / 'a.docling.md').write_text('Texto', encoding='utf-8')
    report = {'source': str(pdf), 'source_sha256': _hash(pdf), 'markdown_sha256': _hash(md),
              'docling_document_sha256': _hash(audit / 'a.docling.json'),
              'raw_markdown_sha256': _hash(audit / 'a.docling.md'),
              'quality_status': 'review', 'findings': [{'severity': 'warning', 'rule': 'STRUCTURE'}]}
    (audit / 'a.qualidade.json').write_text(json.dumps(report), encoding='utf-8')
    (output / '_auditoria/manifest.json').write_text(json.dumps({
        'run_id': 'test', 'documents': [{**report, 'relative_source': 'a.pdf'}]}), encoding='utf-8')
    return output


def _approve(output, **kwargs):
    return decide(output, 'a.pdf', reviewer='Revisor de teste', decision='aprovado',
                  scope=kwargs.pop('scope', 'integral'), notes='Conferência dos avisos.', **kwargs)


def test_delivery_requires_current_full_human_approval(reviewed_output, tmp_path):
    out = reviewed_output
    with pytest.raises(ValueError, match='Não há documentos'):
        deliver(out, tmp_path / 'not-approved')
    _approve(out, scope='amostra')
    with pytest.raises(ValueError, match='Não há documentos'):
        deliver(out, tmp_path / 'sample')
    _approve(out)
    result = deliver(out, tmp_path / 'entrega')
    assert result.is_file()
    data = json.loads(result.with_suffix('.json').read_text())
    assert data['documents'][0]['human_review']['scope'] == 'integral'
    assert (result.parent / 'documentos/a.md').read_bytes() == (out / 'a.md').read_bytes()
    with pytest.raises(FileExistsError):
        deliver(out, result.parent)


@pytest.mark.parametrize('artifact', ['a.md', '_auditoria/documentos/a.docling.json',
                                     '_auditoria/documentos/a.qualidade.json'])
def test_edits_invalidate_approval(reviewed_output, tmp_path, artifact):
    _approve(reviewed_output)
    path = reviewed_output / artifact
    if path.name.endswith('.qualidade.json'):
        data = json.loads(path.read_text())
        data['pages'] = 99
        path.write_text(json.dumps(data))
    else:
        path.write_text('changed')
    with pytest.raises(ValueError, match='Não há documentos'):
        deliver(reviewed_output, tmp_path / 'invalid')


def test_rejection_revokes_previous_approval(reviewed_output, tmp_path):
    _approve(reviewed_output)
    decide(reviewed_output, 'a.pdf', reviewer='Outra pessoa', decision='rejeitado', scope='integral')
    with pytest.raises(ValueError, match='Não há documentos'):
        deliver(reviewed_output, tmp_path / 'rejected')


def test_blocked_documents_cannot_be_approved(reviewed_output):
    path = reviewed_output / '_auditoria/documentos/a.qualidade.json'
    data = json.loads(path.read_text())
    data['quality_status'] = 'blocked'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='bloqueado'):
        _approve(reviewed_output)


def test_concurrent_operations_fail_with_actionable_message(tmp_path):
    lock = tmp_path / '.operacao.lock'
    with exclusive(lock):
        with pytest.raises(RuntimeError, match='Aguarde'):
            with exclusive(lock):
                pass
    with exclusive(lock):
        pass


def test_review_cannot_approve_an_unseen_new_version(reviewed_output):
    out = reviewed_output
    report_path = out / '_auditoria/documentos/a.qualidade.json'
    report = json.loads(report_path.read_text())
    expected = {k: report[k] for k in ('source_sha256', 'markdown_sha256')}
    expected['report_sha256'] = _hash(report_path)
    # Uma segunda conversão legítima substitui a versão enquanto o revisor lê a primeira.
    (out / 'a.md').write_text('Nova versão ainda não conferida', encoding='utf-8')
    report['markdown_sha256'] = _hash(out / 'a.md')
    report_path.write_text(json.dumps(report))
    manifest_path = out / '_auditoria/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['documents'][0]['markdown_sha256'] = report['markdown_sha256']
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='mudou desde'):
        _approve(out, expected=expected)
