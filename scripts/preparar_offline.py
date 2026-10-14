"""Preparar num computador com rede, com o mesmo sistema e Python da estação."""

import argparse
import hashlib
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import tomllib
import traceback
import zipfile
from email.parser import BytesParser
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def model_api(root):
    spec = importlib.util.spec_from_file_location('crl_offline_models', root / 'src/crl_markdown/models.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_smoke(path):
    """PDF pequeno e sintético: evita distribuir documentos privados com o pacote."""
    stream = (b'BT /F1 18 Tf 50 750 Td (CRL teste offline) Tj ET\n'
              b'BT /F1 12 Tf 60 682 Td (Categoria) Tj 150 0 Td (Valor) Tj ET\n'
              b'BT /F1 12 Tf 60 657 Td (Categoria A) Tj 150 0 Td (123.45) Tj ET\n'
              b'BT /F1 12 Tf 60 632 Td (Categoria B) Tj 150 0 Td (678.90) Tj ET\n'
              b'50 700 m 350 700 l S 50 675 m 350 675 l S '
              b'50 650 m 350 650 l S 50 625 m 350 625 l S '
              b'50 700 m 50 625 l S 200 700 m 200 625 l S 350 700 m 350 625 l S\n')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
               b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'endstream']
    content, offsets = b'%PDF-1.4\n', [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content += str(index).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
    xref = len(content)
    content += b'xref\n0 6\n0000000000 65535 f \n'
    content += b''.join(f'{offset:010} 00000 n \n'.encode() for offset in offsets[1:])
    content += b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(xref).encode() + b'\n%%EOF\n'
    path.write_bytes(content)


def lock_wheels(wheels, target):
    """Versões e hashes de todas as wheels transitivas efetivamente preparadas."""
    versions, requirements = {}, []
    for wheel in sorted(wheels.glob('*.whl')):
        with zipfile.ZipFile(wheel) as archive:
            # Wheels como setuptools incluem cópias internas de bibliotecas
            # com METADATA próprios. Só o dist-info da raiz identifica a wheel.
            names = [n for n in archive.namelist()
                     if n.count('/') == 1 and n.endswith('.dist-info/METADATA')]
            if len(names) != 1:
                raise ValueError(f'Wheel sem metadados únicos: {wheel.name}')
            metadata = BytesParser().parsebytes(archive.read(names[0]))
        name = metadata['Name'].lower().replace('_', '-')
        version = metadata['Version']
        if name in versions:
            raise ValueError(f'Mais de uma wheel para {name}. Prepare numa pasta nova.')
        versions[name] = version
        digest = sha256(wheel)
        requirements.append(f'{name}=={version} --hash=sha256:{digest}')
    if not {'crl-pdf-markdown', 'docling'}.issubset(versions):
        raise ValueError('Wheelhouse incompleta: falta a aplicação ou Docling.')
    target.write_text('\n'.join(requirements) + '\n', encoding='utf-8')
    return versions


def prepare(output, models):
    root = Path(__file__).resolve().parents[1]
    output, models = output.resolve(), models.resolve()
    if output.exists():
        raise ValueError('Escolha uma pasta de pacote nova; não substituir um pacote já distribuído.')
    if sys.version_info[:2] not in {(3, 11), (3, 12), (3, 13)}:
        raise ValueError('Prepare com Python 3.11, 3.12 ou 3.13, igual ao da estação.')
    api = model_api(root)
    problems = api.verify(models)
    ocr = api.has_ocr_models(models)
    problems += api.required_files_problems(models, ocr=ocr)
    if problems:
        raise ValueError('Modelos incompletos ou alterados: ' + '; '.join(problems[:3]))
    wheels = output / 'wheelhouse'
    wheels.mkdir(parents=True)
    try:
        with (output / 'preparacao.txt').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-m', 'pip', 'wheel', str(root),
                            '-c', str(root / 'requirements/runtime.txt'),
                            '--only-binary=:all:', '--wheel-dir', str(wheels)], check=True,
                           stdout=log, stderr=subprocess.STDOUT)
            subprocess.run([sys.executable, '-m', 'pip', 'download', 'pip', 'setuptools',
                            '--only-binary=:all:', '--dest', str(wheels)], check=True,
                           stdout=log, stderr=subprocess.STDOUT)
        versions = lock_wheels(wheels, output / 'requirements.install.txt')
        project = tomllib.loads((root / 'pyproject.toml').read_text('utf-8'))
        if versions['crl-pdf-markdown'] != project['project']['version']:
            raise ValueError('A wheel da aplicação não corresponde à versão do projeto.')
        model_manifest = json.loads((models / api.MANIFEST).read_text('utf-8'))
        if model_manifest.get('docling') != versions['docling']:
            raise ValueError('Modelos preparados com outra versão de Docling. Instale a versão '
                             'fixada em requirements/runtime.txt e prepare novamente os modelos.')
        shutil.copytree(models, output / 'modelos', ignore=shutil.ignore_patterns('.cache'))
        shutil.copytree(root / 'vocabularios', output / 'vocabularios')
        for name in ('siglas.csv', 'siglas.manifest.json'):
            shutil.copyfile(root / name, output / name)
        shutil.copyfile(root / 'src/crl_markdown/models.py', output / 'offline_models.py')
        shutil.copyfile(root / 'scripts/instalar_offline.py', output / 'instalar_offline.py')
        batch = (root / 'scripts/Instalar_CRL.bat').read_text('utf-8')
        batch = batch.replace('3.13', f'{sys.version_info.major}.{sys.version_info.minor}')
        (output / 'Instalar_CRL.bat').write_text(batch, encoding='utf-8', newline='\r\n')
        shutil.copyfile(root / 'docs/operacao/instalacao-offline.md', output / 'LEIA_PRIMEIRO.md')
        write_smoke(output / 'smoke.pdf')
        files = {p.relative_to(output).as_posix(): sha256(p)
                 for p in sorted(output.rglob('*')) if p.is_file()}
        manifest = {'schema': 2, 'platform': sys.platform, 'machine': platform.machine(),
                    'python': list(sys.version_info[:2]), 'files': files, 'versions': versions,
                    'ocr': ocr, 'validation': 'por_validar_na_estacao'}
        (output / 'pacote.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                          encoding='utf-8')
        print('Pacote preparado. Faça a instalação e uma conversão com a rede desligada antes de distribuir.')
    except BaseException:
        (output / 'PACOTE_INCOMPLETO.txt').write_text(
            'A preparação falhou. Não distribuir esta pasta. Consulte preparacao.txt e falha.txt. '
            'O apoio deve confirmar rede, versões e modelos e preparar novamente numa pasta nova.\n',
            encoding='utf-8')
        (output / 'falha.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--saida', type=Path, required=True)
    parser.add_argument('--modelos', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.saida, args.modelos)
