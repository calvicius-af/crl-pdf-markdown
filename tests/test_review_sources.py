import json
import shutil
from pathlib import Path

import pytest

from crl_markdown.review_sources import locate_sources, resolve_source
from crl_markdown.revisions import audit_revision, create_revision, pending_revisions
from crl_markdown.validation import _load, _verified, decide, deliver
from tests.test_pipeline import converter  # noqa: F401
from tests.test_revisions import damaged_output  # noqa: F401
from tests.test_validation import reviewed_output  # noqa: F401


def test_copy_to_another_machine_rebinds_pdfs_without_invalidating_approval(reviewed_output, tmp_path):  # noqa: F811
    out = reviewed_output
    decision = decide(out, 'a.pdf', reviewer='Pessoa A', decision='aprovado',
                      scope='integral', notes='Conferido.')
    decision_bytes = decision.read_bytes()
    original = tmp_path / 'a.pdf'
    other = tmp_path / 'machine-b'
    pdfs = other / 'originais'
    pdfs.mkdir(parents=True)
    shutil.copy2(original, pdfs / 'nome-diferente.pdf')
    copied = other / 'lote'
    shutil.copytree(out, copied)
    original.unlink()
    doc = _load(copied)['documents'][0]
    with pytest.raises(ValueError, match='Localizar PDFs'):
        _verified(copied, doc)
    before = (copied / '_auditoria/documentos/a.qualidade.json').read_bytes()
    assert locate_sources(copied, pdfs) == {'found': 1, 'missing': 0}
    _verified(copied, doc)
    assert resolve_source(copied, doc) == pdfs / 'nome-diferente.pdf'
    result = deliver(copied, other / 'entrega')
    assert (result.parent / 'documentos/a.md').is_file()
    assert (copied / decision.relative_to(out)).read_bytes() == decision_bytes
    assert (copied / '_auditoria/documentos/a.qualidade.json').read_bytes() == before
    (pdfs / 'nome-diferente.pdf').write_bytes(b'Documento errado')
    with pytest.raises(ValueError, match='conteúdo mudou'):
        resolve_source(copied, doc)


def test_saved_correction_can_be_resumed_and_audited_in_relocated_folder(damaged_output, tmp_path):  # noqa: F811
    out = damaged_output
    revision = create_revision(out, 'source.pdf', 'Pessoa A')
    draft = revision / 'correcao.md'
    draft.write_text(draft.read_text(encoding='utf-8').replace('125,00', '-125,00'), encoding='utf-8')
    other = tmp_path / 'machine-b'
    copied = other / 'lote'
    shutil.copytree(out, copied)
    pdfs = other / 'pdfs'
    pdfs.mkdir()
    shutil.copy2(tmp_path / 'source.pdf', pdfs / 'original-renomeado.pdf')
    (tmp_path / 'source.pdf').unlink()
    locate_sources(copied, pdfs)
    document = _load(copied)['documents'][0]
    _, _, report = _verified(copied, document)
    from crl_markdown.revisions import _identity
    target, report_path, _ = _verified(copied, document)
    drafts = pending_revisions(copied, 'source.pdf', 'Pessoa A', _identity(target, report_path, report))
    assert len(drafts) == 1
    publication, corrected = audit_revision(drafts[0])
    assert publication.is_relative_to(copied)
    assert '-125,00' in (publication / 'source.md').read_text(encoding='utf-8')
    assert corrected['quality_status'] != 'blocked'
    _verified(copied, document)
    assert not list((out / '_auditoria/versoes').glob('*.json'))
    pointer = next((copied / '_auditoria/versoes').glob('*.json'))
    assert Path(json.loads(pointer.read_text(encoding='utf-8'))['publication']).parts[0] == '_auditoria'


def test_cached_reaudit_preserves_profile_after_source_rename(tmp_path, converter):  # noqa: F811
    from crl_markdown.pipeline import Options, run
    from crl_markdown.reaudit import reaudit
    name = '2026_BTE_28_JUR_348_46278_Test.pdf'
    source = tmp_path / name
    source.write_bytes(b'fixture')
    output = tmp_path / 'out'
    run(source, output, Options(), converter=converter, progress=lambda _: None)
    pdfs = tmp_path / 'pdfs'
    pdfs.mkdir()
    shutil.move(source, pdfs / 'original-renomeado.pdf')
    locate_sources(output, pdfs)
    destination, reports = reaudit(output, tmp_path / 'new', jobs=1, progress=lambda _: None)
    assert reports[0]['document_profile'] == 'acordao'
    assert reports[0]['relative_source'] == name
    assert (destination / Path(name).with_suffix('.md')).is_file()
    assert json.loads((destination / '_auditoria/manifest.json').read_text(encoding='utf-8'))['source'] == str(pdfs)
