import json

import pytest

from crl_markdown.pipeline import Options, run
from crl_markdown.reaudit import reaudit
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
    data = json.loads((output / '_auditoria/manifest.json').read_text())
    assert data['schema_version'] == 2
    assert 'structured_text' not in data['documents'][0]
    assert data['documents'][0]['markdown_sha256'] == reports[0]['markdown_sha256']
    detail = json.loads((output / data['documents'][0]['detail_report']).read_text())
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
