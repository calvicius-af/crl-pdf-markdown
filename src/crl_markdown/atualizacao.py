"""Atualização do código da aplicação sem reinstalar.

O instalador tem cerca de 1 GB porque leva o Python, o Docling e os modelos.
Entre versões candidatas muda quase sempre só o código da aplicação (a pasta
`crl_markdown`, cerca de 1 MB). Um pacote de atualização é um ZIP com essa
pasta, os hashes de cada ficheiro e as versões das bibliotecas com que foi
ensaiado. Aplica-se na pasta do utilizador, sem administrador:

1. Confirma que a pasta é uma instalação CRL e que as bibliotecas instaladas
   são as mesmas do ensaio; se não forem, recusa e pede o instalador completo.
2. Confirma os hashes de todos os ficheiros do pacote.
3. Prepara a pasta nova ao lado, guarda a atual como `crl_markdown.anterior-…`
   e troca as duas. Uma falha a meio repõe a anterior.

O ZIP executa-se com o Python instalado (o ficheiro «Atualizar CRL.cmd» faz
isso) ou pela janela principal, em «Aplicar atualização…».
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

MANIFEST = 'atualizacao.json'
PACKAGE = 'crl_markdown'
# Bibliotecas de que o código depende diretamente; têm de coincidir com o ensaio.
DEPENDENCIES = ('docling', 'docling-core', 'pdfplumber', 'pypdfium2', 'rapidocr', 'lxml', 'openpyxl')

MAIN = '''import sys
from crl_markdown.atualizacao import main_zip
raise SystemExit(main_zip(sys.argv[0], sys.argv[1:]))
'''


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _installed(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def build(destination: Path, source: Path | None = None) -> Path:
    """Cria o pacote a partir do código em `source` (por omissão, este pacote)."""
    from . import __version__
    source = Path(source) if source else Path(__file__).resolve().parent
    files = {}
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f'CRL-atualizacao-{__version__}.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix in {'.pyc', '.pyo'}:
                continue
            name = f'{PACKAGE}/{path.relative_to(source).as_posix()}'
            data = path.read_bytes()
            files[name] = _digest(data)
            archive.writestr(name, data)
        archive.writestr('__main__.py', MAIN)
        archive.writestr(MANIFEST, json.dumps({
            'schema': 1, 'version': __version__,
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'dependencies': {name: _installed(name) for name in DEPENDENCIES},
            'files': files}, ensure_ascii=False, indent=2))
    return target


def read_package(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read(MANIFEST))
        names = {n for n in archive.namelist() if n.startswith(PACKAGE + '/') and not n.endswith('/')}
        if names != set(manifest['files']):
            raise ValueError('O pacote de atualização está incompleto ou foi alterado.')
        for name, digest in manifest['files'].items():
            if _digest(archive.read(name)) != digest:
                raise ValueError(f'O pacote de atualização foi alterado: {name}.')
    return manifest


def installation(site=None) -> tuple[Path, Path]:
    """Pasta da instalação e site-packages do Python que corre este código."""
    site = Path(site) if site else Path(sys.prefix) / 'Lib' / 'site-packages'
    root = site.parents[2]
    if not (root / 'distribuicao.json').is_file() or not (site / PACKAGE).is_dir():
        raise ValueError('Esta pasta não é uma instalação da aplicação CRL. '
                         'Execute a atualização com o Python da aplicação instalada.')
    return root, site


def apply(package: Path, site=None, *, check_dependencies=True) -> dict:
    manifest = read_package(package)
    root, site = installation(site)
    if check_dependencies:
        different = {name: (expected, _installed(name)) for name, expected in manifest['dependencies'].items()
                     if expected and _installed(name) != expected}
        if different:
            listed = ', '.join(f'{n} {have or "ausente"} (esperado {want})' for n, (want, have) in different.items())
            raise ValueError('As bibliotecas instaladas não são as do ensaio desta atualização: '
                             f'{listed}. Use o instalador completo.')
    current = site / PACKAGE
    from_version = _package_version(current)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    staging = site / f'{PACKAGE}.novo-{stamp}'
    previous = site / f'{PACKAGE}.anterior-{from_version}-{stamp}'
    with zipfile.ZipFile(package) as archive:
        for name in manifest['files']:
            target = staging / name.removeprefix(PACKAGE + '/')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    try:
        current.rename(previous)
    except OSError as error:
        shutil.rmtree(staging, ignore_errors=True)
        raise ValueError('Feche a aplicação CRL antes de atualizar e tente de novo.') from error
    try:
        staging.rename(current)
    except BaseException:
        previous.rename(current)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    record = {'version': manifest['version'], 'from_version': from_version, 'applied_utc': stamp,
              'previous_folder': previous.name, 'package_sha256': _digest(Path(package).read_bytes())}
    _record_distribution(root, site, record)
    return record


def revert(site=None) -> dict:
    """Repõe a versão anterior guardada pela última atualização."""
    root, site = installation(site)
    previous = sorted(site.glob(f'{PACKAGE}.anterior-*'), key=lambda p: p.name.rsplit('-', 1)[-1])
    if not previous:
        raise ValueError('Não há versão anterior guardada para repor.')
    current = site / PACKAGE
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    discarded = site / f'{PACKAGE}.revertida-{_package_version(current)}-{stamp}'
    current.rename(discarded)
    previous[-1].rename(current)
    record = {'version': _package_version(current), 'reverted_utc': stamp, 'discarded_folder': discarded.name}
    _record_distribution(root, site, record)
    return record


def _package_version(folder: Path) -> str:
    for line in (folder / '__init__.py').read_text(encoding='utf-8').splitlines():
        if line.startswith('__version__'):
            return line.split('=', 1)[1].strip().strip('"\'')
    return 'desconhecida'


def _record_distribution(root: Path, site: Path, record: dict):
    """O ensaio da instalação passa a aceitar os ficheiros da versão aplicada."""
    path = root / 'distribuicao.json'
    original = root / 'distribuicao.original.json'
    if not original.exists():
        shutil.copy2(path, original)
    data = json.loads(path.read_text(encoding='utf-8'))
    prefix = site.relative_to(root).as_posix() + f'/{PACKAGE}/'
    files = {k: v for k, v in data['files'].items() if not k.startswith(prefix)}
    for file in sorted((site / PACKAGE).rglob('*')):
        if file.is_file() and '__pycache__' not in file.parts:
            files[file.relative_to(root).as_posix()] = _digest(file.read_bytes())
    data['files'] = files
    data.setdefault('atualizacoes', []).append(record)
    data['codigo_versao'] = _package_version(site / PACKAGE)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def main_zip(package, argv):
    """Executado como `python CRL-atualizacao-….zip`, com o Python instalado."""
    try:
        record = apply(Path(package).resolve())
    except ValueError as error:
        print(f'A atualização não foi aplicada: {error}')
        return 1
    print(f"Atualização aplicada: {record['from_version']} -> {record['version']}. "
          'Pode abrir a aplicação CRL.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--criar', type=Path, metavar='PASTA', help='Criar o pacote nesta pasta')
    action.add_argument('--aplicar', type=Path, metavar='ZIP', help='Aplicar um pacote a esta instalação')
    action.add_argument('--reverter', action='store_true', help='Repor a versão anterior')
    args = parser.parse_args(argv)
    try:
        if args.criar:
            print(build(args.criar))
        elif args.aplicar:
            print(json.dumps(apply(args.aplicar), ensure_ascii=False))
        else:
            print(json.dumps(revert(), ensure_ascii=False))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
