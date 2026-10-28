"""Instalador só com biblioteca padrão; nenhum pedido de rede nem privilégio admin."""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import types
import venv
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath


def wheelhouse_reference(folder):
    """Preserva a partilha quando o pip converte --find-links em URLs."""
    text = str(folder)
    if not text.startswith("\\\\"):
        return text
    server, _, rest = text[2:].partition("\\")
    if server.lower() == 'localhost':
        server = '127.0.0.1'
    return PureWindowsPath(f"\\\\{server}\\{rest}").as_uri()


def install_command(python, package):
    return [str(python), '-m', 'pip', 'install', '--no-index', '--only-binary=:all:',
            '--require-hashes', '--find-links', wheelhouse_reference(package / 'wheelhouse'),
            '-r', str(package / 'requirements.install.txt')]


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def windows_ascii_path(path):
    """Alias do mesmo diretório para bibliotecas nativas que abrem nomes ANSI."""
    text = str(path)
    if text.isascii():
        return path
    import ctypes
    from ctypes import wintypes

    get_short_path = ctypes.WinDLL('kernel32', use_last_error=True).GetShortPathNameW
    get_short_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    get_short_path.restype = wintypes.DWORD
    size = get_short_path(text, None, 0)
    if size:
        buffer = ctypes.create_unicode_buffer(size)
        written = get_short_path(text, buffer, size)
        if 0 < written < size and buffer.value.isascii():
            alias = Path(buffer.value)
            if alias.samefile(path):
                return alias
    raise ValueError('O parser PDF requer um caminho de bibliotecas sem acentos nesta estação. '
                     'O Windows não disponibilizou um alias curto. Repita com --destination '
                     'numa pasta local sem acentos, com permissão de escrita; não altere os modelos.')


def configure_native_paths(environment):
    """Conservar o ambiente; importar a mesma site-packages pelo alias ASCII."""
    if sys.platform != 'win32':
        return {}
    packages = environment / 'Lib/site-packages'
    alias = windows_ascii_path(packages)
    if alias == packages:
        return {}
    # A linha .pth é executada pelo próprio ambiente antes de importar Docling.
    # Não altera wheels, recursos nativos ou o ambiente de outros projetos.
    bootstrap = packages / 'crl_native_paths.pth'
    bootstrap.write_text('import sys; sys.path.insert(0, ' + repr(str(alias)) + ')\n',
                         encoding='ascii')
    return {'native_site_packages': str(alias), 'native_path_bootstrap_sha256': sha256(bootstrap)}


def verify(package):
    package = package.resolve()
    if (package / 'PACOTE_INCOMPLETO.txt').exists():
        raise ValueError('Pacote incompleto. Peça ao apoio informático uma cópia completa.')
    manifest = json.loads((package / 'pacote.json').read_text(encoding='utf-8'))
    if (manifest['platform'], manifest['machine'], manifest['python']) != (
            sys.platform, platform.machine(), list(sys.version_info[:2])):
        raise ValueError('Pacote preparado para outro sistema ou Python. Peça o pacote da sua estação.')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('Manifesto vazio ou inválido. Peça uma cópia completa do pacote.')
    for name, digest in files.items():
        if (not isinstance(name, str) or '\\' in name
                or PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive
                or '..' in PurePosixPath(name).parts or name != PurePosixPath(name).as_posix()
                or name == 'pacote.json'):
            raise ValueError('Caminho inválido no pacote; peça uma cópia completa.')
        path = package / name
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError('Ligação simbólica no pacote; peça uma cópia completa.')
        if not path.resolve().is_relative_to(package):
            raise ValueError('Caminho inválido no pacote; peça uma cópia completa.')
        if (not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)
                or not path.is_file() or sha256(path) != digest):
            raise ValueError(f'Ficheiro em falta ou alterado: {name}. Copie novamente o pacote completo.')
    if manifest.get('schema') != 2:
        raise ValueError('Formato de pacote antigo ou inválido. Peça ao apoio um pacote preparado novamente.')
    required = {'requirements.install.txt', 'offline_models.py', 'smoke.pdf',
                'siglas.csv', 'siglas.manifest.json', 'LEIA_PRIMEIRO.md',
                'modelos/manifesto_modelos.json'}
    if not required.issubset(files) or not any(n.startswith('wheelhouse/') for n in files):
        raise ValueError('Pacote incompleto: faltam recursos obrigatórios. Copie novamente a pasta completa.')
    actual = set()
    for path in package.rglob('*'):
        if path.is_symlink():
            raise ValueError('Ligação simbólica no pacote; peça uma cópia completa.')
        if path.is_file() and path != package / 'pacote.json':
            actual.add(path.relative_to(package).as_posix())
    if actual != set(files):
        raise ValueError('Ficheiros não inventariados no pacote. Peça uma cópia completa, sem misturar pastas.')
    versions = manifest.get('versions')
    if (not isinstance(versions, dict) or not versions.get('docling')
            or not versions.get('crl-pdf-markdown') or not isinstance(manifest.get('ocr'), bool)):
        raise ValueError('Versões ou perfil OCR ausentes no manifesto. Peça um pacote preparado novamente.')
    model_module = types.ModuleType('crl_offline_models')
    source = package / 'offline_models.py'
    exec(compile(source.read_text('utf-8'), str(source), 'exec'), model_module.__dict__)
    problems = model_module.verify(package / 'modelos')
    problems += model_module.required_files_problems(package / 'modelos', ocr=bool(manifest.get('ocr')))
    if problems:
        raise ValueError('Modelos inválidos: ' + '; '.join(problems[:3]))
    model_manifest = json.loads((package / 'modelos' / model_module.MANIFEST).read_text('utf-8'))
    if model_manifest.get('docling') != manifest.get('versions', {}).get('docling'):
        raise ValueError('Modelos de outra versão do Docling. Peça modelos preparados com a versão do pacote.')
    if manifest.get('ocr') and not model_module.has_ocr_models(package / 'modelos'):
        raise ValueError('Faltam os modelos OCR. Copie novamente o pacote completo.')
    import tkinter
    if not tkinter.TkVersion:
        raise ValueError('Python sem interface gráfica. O apoio informático deve instalar Tcl/Tk.')
    return manifest


# Executado pelo Python instalado; o teste bloqueia sockets mesmo se uma dependência
# ignorar as opções offline. Só usa um PDF sintético distribuído, nunca o corpus.
SMOKE = '''import json, socket, sys
from importlib.metadata import version
from pathlib import Path

def blocked(*args, **kwargs):
    raise RuntimeError("O ensaio offline tentou usar a rede")
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked
import tkinter
window = tkinter.Tk()
window.withdraw()
window.update_idletasks()
window.destroy()
from crl_markdown import models
from crl_markdown.pipeline import Options, make_converter
folder = Path(sys.argv[1])
problems = models.verify(folder)
if problems:
    raise RuntimeError("Modelos inválidos: " + "; ".join(problems[:3]))
expected_versions = json.loads(sys.argv[4])
for package, expected in expected_versions.items():
    if version(package) != expected:
        raise RuntimeError("Versão instalada diferente do pacote: " + package)
ocr = sys.argv[3] == "1"
converter = make_converter(Options(models=folder, offline=True, ocr=ocr))
if ocr:
    from docling.datamodel.base_models import InputFormat
    converter.format_to_options[InputFormat.PDF].pipeline_options.ocr_options.force_full_page_ocr = True
result = converter.convert(Path(sys.argv[2]))
from docling.datamodel.base_models import ConversionStatus
if result.status != ConversionStatus.SUCCESS:
    raise RuntimeError("A conversão do PDF de ensaio ficou incompleta")
text = result.document.export_to_markdown()
if any(token not in text for token in ("CRL", "Categoria", "123.45", "678.90")):
    raise RuntimeError("O PDF de ensaio não preservou o título e os valores da tabela")
print("Conversão local concluída; OCR:", ocr)
'''


def atomic_bytes(path, content, mode=None):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        if mode is not None:
            temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def publish(configuration, config, launcher, launch_text):
    """O lançador é a última publicação; uma falha conserva a instalação anterior."""
    previous = configuration.read_bytes() if configuration.exists() else None
    atomic_bytes(configuration, json.dumps(config, ensure_ascii=False, indent=2).encode('utf-8'))
    try:
        atomic_bytes(launcher, launch_text.encode('utf-8'), 0o755)
    except BaseException:
        if previous is None:
            configuration.unlink(missing_ok=True)
        else:
            atomic_bytes(configuration, previous)
        raise


def install(package, destination, log):
    # Preservar L: para o pip; verify() faz a validação canónica separadamente.
    package, destination = package.absolute(), destination.resolve()
    manifest = verify(package)
    destination.mkdir(parents=True, exist_ok=True)
    lock = destination / '.instalacao-em-curso'
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ValueError('Já existe uma instalação em curso. Espere pela outra janela. '
                         'Se foi interrompida, peça ao apoio para remover .instalacao-em-curso.') from error
    try:
        identifier = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        environment = destination / ('ambiente-' + identifier)
        resources = destination / ('recursos-' + identifier)
        resources.mkdir()
        for folder in ('modelos', 'vocabularios'):
            shutil.copytree(package / folder, resources / folder)
        for filename in ('siglas.csv', 'siglas.manifest.json', 'LEIA_PRIMEIRO.md', 'smoke.pdf'):
            shutil.copyfile(package / filename, resources / filename)
        for name, digest in manifest['files'].items():
            if name.startswith(('modelos/', 'vocabularios/')) or name in (
                    'siglas.csv', 'siglas.manifest.json', 'LEIA_PRIMEIRO.md', 'smoke.pdf'):
                if sha256(resources / name) != digest:
                    raise ValueError(f'Ficheiro alterado durante a cópia: {name}. Copie novamente o pacote.')
        venv.create(environment, with_pip=True)
        native_paths = configure_native_paths(environment)
        python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        child_env = {**os.environ, 'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
                     'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'PYTHONUTF8': '1',
                     'HF_HOME': str(resources / 'cache-hf')}
        child_env.pop('PYTHONPATH', None)
        child_env.pop('PYTHONHOME', None)
        for key in list(child_env):
            if key.startswith('PIP_'):
                child_env.pop(key)
        child_env.update({'PIP_NO_INDEX': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
                          'PIP_CONFIG_FILE': os.devnull})
        command = install_command(python, package)
        with log.open('a', encoding='utf-8') as handle:
            for label, command, timeout in (
                ('Instalar bibliotecas locais', command, 1800),
                ('Conferir dependências', [str(python), '-m', 'pip', 'check'], 300),
                ('Converter PDF de ensaio sem rede', [str(python), '-c', SMOKE,
                 str(resources / 'modelos'), str(resources / 'smoke.pdf'),
                 '1' if manifest.get('ocr') else '0', json.dumps(manifest['versions'])], 900),
            ):
                print(label + '…', flush=True)
                handle.write('\nEtapa: ' + label + '\n')
                handle.flush()
                try:
                    subprocess.run(command, check=True, stdout=handle, stderr=subprocess.STDOUT,
                                   env=child_env, cwd=resources, timeout=timeout)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                    raise RuntimeError(label + ' falhou. Conserve o relatório TXT para o apoio; '
                                       'a instalação anterior continua disponível.') from error
        config = {**native_paths, 'python': str(python), 'models': str(resources / 'modelos'),
                  'resources': str(resources), 'ocr_tested': bool(manifest.get('ocr')),
                  'package_sha256': sha256(package / 'pacote.json'), 'versions': manifest['versions']}
        if os.name == 'nt':
            launcher = destination / 'Abrir_CRL.bat'
            cmd_resources = str(resources).replace('%', '%%')
            cmd_python = str(python).replace('%', '%%')
            cmd_models = str(resources / 'modelos').replace('%', '%%')
            launch_text = ('@echo off\r\nchcp 65001 >nul\r\nsetlocal DisableDelayedExpansion\r\n'
                           'set PYTHONUTF8=1\r\nset PYTHONPATH=\r\nset PYTHONHOME=\r\n'
                           'set HF_HUB_OFFLINE=1\r\n'
                           'set TRANSFORMERS_OFFLINE=1\r\n'
                           f'pushd "{cmd_resources}"\r\nif errorlevel 1 exit /b 1\r\n'
                           f'"{cmd_python}" -m crl_markdown.app --models "{cmd_models}" --offline\r\n'
                           'set CRL_EXIT=%errorlevel%\r\npopd\r\nif not "%CRL_EXIT%"=="0" pause\r\n'
                           'exit /b %CRL_EXIT%\r\n')
        else:
            import shlex
            launcher = destination / 'Abrir_CRL.command'
            launch_text = ('#!/bin/sh\nunset PYTHONPATH PYTHONHOME\n'
                           'export PYTHONUTF8=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1\n'
                           'cd ' + shlex.quote(str(resources)) + ' || exit 1\nexec '
                           + shlex.quote(str(python)) + ' -m crl_markdown.app --models '
                           + shlex.quote(str(resources / 'modelos')) + ' --offline\n')
        publish(destination / 'instalacao.json', config, launcher, launch_text)
        return launcher
    finally:
        lock.rmdir()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Instalar o pacote CRL sem acesso à rede.')
    parser.add_argument('--destination', type=Path, help='Pasta local de instalação (apoio informático).')
    parser.add_argument('--package', type=Path,
                        help='Pacote existente, para instalar com uma versão atualizada deste script.')
    args = parser.parse_args(argv)
    package = (args.package or Path(__file__).absolute().parent).absolute()
    destination = args.destination or (
        Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'CRL-PDF-Markdown')
    log_folder = destination / 'assistencia'
    try:
        log_folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_folder = Path(tempfile.mkdtemp(prefix='CRL-assistencia-'))
    log = log_folder / datetime.now().strftime('instalacao-%Y%m%d-%H%M%S-%f.txt')
    try:
        launcher = install(package, destination, log)
        print(f'Instalação concluída. Para abrir, faça duplo clique em:\n{launcher}')
        print('O PDF de ensaio foi convertido com modelos locais. Antes do lote, teste um PDF seu e confira o relatório.')
        return 0
    except Exception as error:
        report = log.with_suffix('.md')
        message = ('# Não foi possível instalar\n\n'
                   f'O que aconteceu: {error}\n\n'
                   'O que fazer agora:\n\n'
                   '1. Confirme que copiou a pasta completa do pacote.\n'
                   '2. Repita Instalar_CRL.bat. O lançador anterior continua disponível.\n'
                   '3. Se continuar, entregue este relatório e o TXT com o mesmo nome ao apoio informático.\n'
                   '4. O apoio deve confirmar Python/sistema, integridade, espaço livre e modelos.\n')
        try:
            with log.open('a', encoding='utf-8') as handle:
                handle.write(traceback.format_exc())
            report.write_text(message, encoding='utf-8')
            print(f'A instalação não terminou: {error}\nInstruções e detalhe técnico: {report}')
        except OSError:
            print(message + '\nNão foi possível guardar o relatório. Conserve o texto desta janela para o apoio.')
        return 1


if __name__ == '__main__':
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    raise SystemExit(main())
