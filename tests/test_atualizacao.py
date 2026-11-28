import json
import zipfile

import pytest

from crl_markdown import __version__
from crl_markdown.atualizacao import apply, build, read_package, revert


@pytest.fixture
def installed(tmp_path):
    root = tmp_path / 'CRL-PDF-Markdown' / '0.4.0rc3'
    site = root / 'python' / 'Lib' / 'site-packages'
    package = site / 'crl_markdown'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('__version__ = "0.4.0rc3"\n', encoding='utf-8')
    (package / 'antigo.py').write_text('x = 1\n', encoding='utf-8')
    (root / 'distribuicao.json').write_text(json.dumps({'version': '0.4.0rc3', 'files': {
        'python/Lib/site-packages/crl_markdown/__init__.py': 'a', 'recursos/smoke.pdf': 'b'}}), encoding='utf-8')
    return root, site


def test_update_replaces_code_keeps_previous_and_can_revert(installed, tmp_path):
    root, site = installed
    package = build(tmp_path / 'pacote')
    record = apply(package, site)
    assert record['from_version'] == '0.4.0rc3' and record['version'] == __version__
    assert (site / 'crl_markdown/ensaio_completo.py').is_file()
    assert not (site / 'crl_markdown/antigo.py').exists()
    data = json.loads((root / 'distribuicao.json').read_text(encoding='utf-8'))
    assert data['files']['recursos/smoke.pdf'] == 'b'
    assert 'python/Lib/site-packages/crl_markdown/atualizacao.py' in data['files']
    assert data['codigo_versao'] == __version__
    assert (root / 'distribuicao.original.json').is_file()
    assert revert(site)['version'] == '0.4.0rc3'
    assert (site / 'crl_markdown/antigo.py').is_file()


def test_tampered_package_or_other_folder_is_refused(installed, tmp_path):
    _root, site = installed
    package = build(tmp_path / 'pacote')
    tampered = tmp_path / 'alterado.zip'
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(tampered, 'w') as target:
        for item in source.infolist():
            data = source.read(item)
            if item.filename == 'crl_markdown/pipeline.py':
                data += b'\n# alterado\n'
            target.writestr(item, data)
    with pytest.raises(ValueError, match='alterado'):
        read_package(tampered)
    with pytest.raises(ValueError, match='instalação da aplicação CRL'):
        apply(package, tmp_path / 'outra' / 'python' / 'Lib' / 'site-packages')
    assert (site / 'crl_markdown/antigo.py').is_file()
