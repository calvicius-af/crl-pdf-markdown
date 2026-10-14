"""Pacote offline: integridade, recursos locais e publicação recuperável sem rede."""

import errno
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from crl_markdown import doctor, models
from crl_markdown.diagnostics import explain, save_failure

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def installer():
    return load_script('instalar_offline')


def make_package(folder):
    """Tiny model-shaped fixture, never represented as validated real model weights."""
    folder.mkdir()
    model_folder = folder / 'modelos'
    layout = model_folder / 'docling-project--docling-layout-heron'
    layout.mkdir(parents=True)
    (layout / 'model.safetensors').write_bytes(b'layout mock weights')
    (layout / 'config.json').write_text('{}')
    (layout / 'preprocessor_config.json').write_text('{}')
    table = model_folder / 'docling-project--docling-models' / 'model_artifacts' / 'tableformer' / 'accurate'
    table.mkdir(parents=True)
    (table / 'tableformer_accurate.safetensors').write_bytes(b'table mock weights')
    (table / 'tm_config.json').write_text('{}')
    model_inventory = models.write_inventory(model_folder)
    model_inventory['docling'] = '2.134.0'
    (model_folder / models.MANIFEST).write_text(json.dumps(model_inventory))
    (folder / 'vocabularios').mkdir()
    (folder / 'vocabularios' / 'siglas.csv').write_text('sigla;nome\nCRL;CRL\n')
    for name in ('siglas.csv', 'siglas.manifest.json', 'LEIA_PRIMEIRO.md'):
        (folder / name).write_text('conteudo de ensaio')
    (folder / 'offline_models.py').write_text((ROOT / 'src/crl_markdown/models.py').read_text(encoding="utf-8"), encoding="utf-8")
    load_script('preparar_offline').write_smoke(folder / 'smoke.pdf')
    wheels = folder / 'wheelhouse'
    wheels.mkdir()
    (wheels / 'mock.whl').write_bytes(b'not installed by this test')
    (folder / 'requirements.install.txt').write_text('crl-pdf-markdown==0.2.2 --hash=sha256:' + '1' * 64)
    manifest = {'schema': 2, 'platform': sys.platform, 'machine': platform.machine(),
                'python': list(sys.version_info[:2]), 'ocr': False,
                'versions': {'crl-pdf-markdown': '0.2.2', 'docling': '2.134.0'}}
    refresh_manifest(folder, manifest)
    return folder


def refresh_manifest(folder, manifest=None):
    if manifest is None:
        manifest = json.loads((folder / 'pacote.json').read_text(encoding="utf-8"))
    manifest['files'] = {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in folder.rglob('*') if p.is_file() and p.name != 'pacote.json'}
    (folder / 'pacote.json').write_text(json.dumps(manifest))


def fake_tk(monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, 'tkinter', types.SimpleNamespace(TkVersion=8.6))


@pytest.mark.parametrize('attack', ['../outside.txt', '/tmp/outside.txt', 'C:/outside.txt',
                                    'modelos\\outside.txt', 'modelos/../outside.txt'])
def test_bundle_rejects_path_traversal(installer, tmp_path, attack):
    package = make_package(tmp_path / 'package')
    manifest = json.loads((package / 'pacote.json').read_text(encoding="utf-8"))
    manifest['files'][attack] = '0' * 64
    (package / 'pacote.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Caminho inválido'):
        installer.verify(package)


def test_verified_package_is_read_only_and_repeatable(installer, tmp_path, monkeypatch):
    package = make_package(tmp_path / 'package')
    fake_tk(monkeypatch)
    before = sorted(str(p.relative_to(package)) for p in package.rglob('*'))
    assert installer.verify(package)['schema'] == 2
    assert installer.verify(package)['schema'] == 2
    assert before == sorted(str(p.relative_to(package)) for p in package.rglob('*'))
    assert not list(package.rglob('__pycache__'))


@pytest.mark.parametrize('change', ['missing', 'corrupt', 'extra', 'link'])
def test_bundle_integrity_precedes_venv(installer, tmp_path, monkeypatch, change):
    package = make_package(tmp_path / 'package')
    called = []
    monkeypatch.setattr(installer.venv, 'create', lambda *a, **kw: called.append(a))
    if change == 'missing':
        (package / 'siglas.csv').unlink()
    elif change == 'corrupt':
        (package / 'siglas.csv').write_text('changed')
    elif change == 'extra':
        (package / 'private.txt').write_text('not for support')
    else:
        (package / 'link.txt').symlink_to(package / 'siglas.csv')
    with pytest.raises(ValueError):
        installer.install(package, tmp_path / 'dest', tmp_path / 'log.txt')
    assert called == []


def test_package_with_bad_model_manifest_is_rejected(installer, tmp_path):
    package = make_package(tmp_path / 'package')
    manifest = package / 'modelos' / models.MANIFEST
    manifest.write_text(json.dumps({'files': [{'path': '../private', 'bytes': 1, 'sha256': '0' * 64}]}))
    refresh_manifest(package)
    with pytest.raises(ValueError, match='Modelos inválidos'):
        installer.verify(package)


def test_package_with_wrong_docling_models_is_rejected(installer, tmp_path):
    package = make_package(tmp_path / 'package')
    manifest = json.loads((package / 'pacote.json').read_text(encoding="utf-8"))
    manifest['versions']['docling'] = 'impossible'
    refresh_manifest(package, manifest)
    with pytest.raises(ValueError, match='outra versão'):
        installer.verify(package)


def fake_heavy_steps(installer, monkeypatch, commands, fail=None):
    fake_tk(monkeypatch)
    monkeypatch.setattr(installer.venv, 'create', lambda folder, **kw: folder.mkdir())

    def run(command, **kwargs):
        commands.append((command, kwargs))
        if fail and fail(command):
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(installer.subprocess, 'run', run)


def test_install_runs_local_conversion_before_publication(installer, tmp_path, monkeypatch):
    package = make_package(tmp_path / 'pacote com espaços')
    commands = []
    fake_heavy_steps(installer, monkeypatch, commands)
    monkeypatch.setenv('PYTHONPATH', '/unexpected/source')
    monkeypatch.setenv('PIP_FIND_LINKS', 'https://unexpected.example/wheels')
    monkeypatch.setenv('PIP_TARGET', '/unexpected/site-packages')
    destination = tmp_path / 'instalação com espaços'
    launcher = installer.install(package, destination, tmp_path / 'log.txt')
    assert launcher.is_file()
    configuration = json.loads((destination / 'instalacao.json').read_text(encoding="utf-8"))
    resources = Path(configuration['resources'])
    pip_command, pip_options = commands[0]
    assert '--require-hashes' in pip_command and '--only-binary=:all:' in pip_command
    assert '--no-index' in pip_command
    smoke, options = commands[-1]
    assert smoke[-4:-1] == [str(resources / 'modelos'), str(resources / 'smoke.pdf'), '0']
    assert json.loads(smoke[-1])['docling'] == '2.134.0'
    assert 'socket.socket.connect = blocked' in smoke[2]
    assert 'Options(models=folder, offline=True, ocr=ocr)' in smoke[2]
    assert options['cwd'] == resources
    assert options['env']['HF_HUB_OFFLINE'] == '1'
    assert 'PYTHONPATH' not in options['env']
    assert 'PIP_FIND_LINKS' not in pip_options['env']
    assert 'PIP_TARGET' not in pip_options['env']
    assert pip_options['env']['PIP_CONFIG_FILE'] == installer.os.devnull
    assert (resources / 'siglas.csv').is_file()
    assert not (destination / '.instalacao-em-curso').exists()
    assert configuration['python'] in launcher.read_text(encoding="utf-8")


@pytest.mark.parametrize('failure', ['pip', 'smoke'])
def test_failed_install_keeps_previous_configuration_and_launcher(
        installer, tmp_path, monkeypatch, failure):
    package = make_package(tmp_path / 'package')
    destination = tmp_path / 'installed'
    destination.mkdir()
    config = destination / 'instalacao.json'
    config.write_text('previous valid configuration')
    old_launcher = destination / ('Abrir_CRL.bat' if installer.os.name == 'nt' else 'Abrir_CRL.command')
    old_launcher.write_text('previous valid launcher')
    commands = []
    fake_heavy_steps(installer, monkeypatch, commands,
                     lambda command: ('pip' in command) if failure == 'pip' else '-c' in command)
    with pytest.raises(RuntimeError, match='anterior continua disponível'):
        installer.install(package, destination, tmp_path / 'log.txt')
    assert config.read_text(encoding="utf-8") == 'previous valid configuration'
    assert old_launcher.read_text(encoding="utf-8") == 'previous valid launcher'
    assert not (destination / '.instalacao-em-curso').exists()


def test_failed_launcher_publication_rolls_back_config(installer, tmp_path, monkeypatch):
    configuration, launcher = tmp_path / 'instalacao.json', tmp_path / 'Abrir_CRL.command'
    configuration.write_bytes(b'old configuration')
    launcher.write_bytes(b'old launcher')
    original = installer.atomic_bytes

    def fail_launcher(path, content, mode=None):
        if path == launcher:
            raise PermissionError('launcher open')
        original(path, content, mode)

    monkeypatch.setattr(installer, 'atomic_bytes', fail_launcher)
    with pytest.raises(PermissionError):
        installer.publish(configuration, {'new': True}, launcher, 'new launcher')
    assert configuration.read_bytes() == b'old configuration'
    assert launcher.read_bytes() == b'old launcher'


def test_all_transitive_wheels_are_exact_and_hash_pinned(tmp_path):
    preparer = load_script('preparar_offline')
    for name, version in [('crl-pdf-markdown', '0.2.2'), ('docling', '2.134.0'), ('transitive', '1.7')]:
        with zipfile.ZipFile(tmp_path / f'{name}-{version}.whl', 'w') as wheel:
            wheel.writestr(name + '.dist-info/METADATA', f'Name: {name}\nVersion: {version}\n')
    lock = tmp_path / 'requirements.install.txt'
    versions = preparer.lock_wheels(tmp_path, lock)
    assert versions['transitive'] == '1.7'
    assert 'transitive==1.7 --hash=sha256:' in lock.read_text(encoding="utf-8")
    assert all('--hash=sha256:' in line for line in lock.read_text(encoding="utf-8").splitlines())


def test_doctor_does_not_accept_arbitrary_weights(tmp_path, monkeypatch):
    folder = tmp_path / 'models'
    folder.mkdir()
    (folder / 'random.safetensors').write_bytes(b'not a Docling model')
    monkeypatch.setattr(doctor.importlib, 'import_module', lambda module: object())
    monkeypatch.setattr(doctor, 'version', lambda package: 'test')
    assert not doctor.check(folder, tmp_path / 'report')
    report = json.loads((tmp_path / 'report' / 'instalacao.json').read_text(encoding="utf-8"))
    result = next(item for item in report['checks'] if item['item'] == 'Modelos locais')
    assert not result['ok'] and models.MANIFEST in result['detail']
    assert not report['ocr_files_verified']


def test_diagnostics_omit_explicit_secrets_and_offer_disk_recovery(tmp_path):
    error = RuntimeError('failed https://user:secret@example.com api_key=private-value')
    target = save_failure(error, tmp_path, 'instalação')
    for path in (target, target.with_suffix('.json')):
        assert 'secret' not in path.read_text(encoding="utf-8")
        assert 'private-value' not in path.read_text(encoding="utf-8")
    assert 'Se continuar' in target.read_text(encoding="utf-8")
    result = explain(OSError(errno.ENOSPC, 'no space'))
    assert result['code'] == 'CRL-ESPACO'
    assert 'espaço' in result['action']


def test_windows_launcher_selects_utf8_before_accented_paths(installer, tmp_path, monkeypatch):
    from types import SimpleNamespace

    package = make_package(tmp_path / 'package')
    commands = []
    fake_heavy_steps(installer, monkeypatch, commands)
    actual_os = installer.os
    monkeypatch.setattr(installer, 'os', SimpleNamespace(
        name='nt', environ=actual_os.environ, devnull=actual_os.devnull, fsync=actual_os.fsync))
    destination = tmp_path / 'Instalação 100% com espaços'
    launcher = installer.install(package, destination, tmp_path / 'log.txt')
    text = launcher.read_text('utf-8')
    assert launcher.name == 'Abrir_CRL.bat'
    assert text.index('chcp 65001 >nul') < text.index('pushd')
    assert 'setlocal DisableDelayedExpansion' in text
    assert 'Instalação 100%% com espaços' in text
    config = json.loads((destination / 'instalacao.json').read_text('utf-8'))
    assert Path(config['python']).parts[-2:] == ('Scripts', 'python.exe')
    assert '100%' in config['resources'] and '100%%' not in config['resources']


def test_preparation_launcher_handles_unc_and_target_version():
    text = (ROOT / 'scripts/Instalar_CRL.bat').read_text('utf-8')
    assert 'pushd "%~dp0"' in text and 'popd' in text
    assert 'chcp 65001 >nul' in text
    for target in ('3.11', '3.12', '3.13'):
        prepared = text.replace('3.13', target)
        assert 'py -' + target + ' instalar_offline.py' in prepared
