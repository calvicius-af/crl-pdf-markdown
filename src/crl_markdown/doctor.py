"""Verificação local sem rede, com relatório que pode ser entregue ao apoio."""

import importlib
import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from . import models as model_api
from .pipeline import atomic_write


def check(models, output):
    results = []
    supported = (3, 11) <= sys.version_info[:2] <= (3, 13)
    results.append({'item': 'Python', 'ok': supported, 'detail': sys.version,
                    'action': 'Use o lançador instalado ou peça Python 3.13 com Tcl/Tk ao apoio.'})
    for module, package in (('docling', 'docling'), ('docling_core', 'docling-core'),
                            ('torch', 'torch'), ('openpyxl', 'openpyxl'),
                            ('markdown_it', 'markdown-it-py'), ('tkinter', None)):
        try:
            importlib.import_module(module)
            results.append({'item': module, 'ok': True,
                            'detail': version(package) if package else 'disponível'})
        except Exception as error:
            results.append({'item': module, 'ok': False, 'detail': str(error),
                            'action': 'Reinstale pelo pacote offline completo. Não instale bibliotecas uma a uma.'})
    problems = ['Pasta de modelos não indicada.']
    ocr = False
    if models:
        models = Path(models)
        try:
            problems = model_api.verify(models)
            ocr = model_api.has_ocr_models(models)
            problems += model_api.required_files_problems(models, ocr=ocr)
            if not problems:
                manifest = json.loads((models / model_api.MANIFEST).read_text('utf-8'))
                if manifest.get('docling') != version('docling'):
                    problems.append('O manifesto dos modelos refere outra versão do Docling.')
        except (OSError, ValueError, TypeError, KeyError, PackageNotFoundError) as error:
            problems = ['Não foi possível verificar o manifesto dos modelos: ' + str(error)]
    results.append({'item': 'Modelos locais', 'ok': not problems,
                    'detail': '; '.join(problems) if problems else f'Integridade verificada: {models}',
                    'action': 'Selecione a pasta modelos completa do pacote instalado, incluindo o manifesto.'})
    data = {'python': sys.executable, 'platform': platform.platform(), 'checks': results,
            'ocr_files_verified': ocr and not problems,
            'note': 'O doctor verifica imports, manifesto e ficheiros exigidos. Não executa uma conversão. '
                    'O OCR só é verificado quando os seus ficheiros estão presentes. '
                    'Teste um PDF representativo com a rede desligada antes de preparar o lote.'}
    output = Path(output)
    atomic_write(output / 'instalacao.json', json.dumps(data, ensure_ascii=False, indent=2))
    lines = ['# Verificação da instalação', '', f'Python usado: {sys.executable}', '']
    for result in results:
        lines += [f"- {result['item']}: {'OK' if result['ok'] else 'Precisa de correção'} — {result['detail']}"]
        if not result['ok']:
            lines += ['  O que fazer: ' + result['action']]
    lines += ['', data['note']]
    atomic_write(output / 'instalacao.md', '\n'.join(lines) + '\n')
    return all(result['ok'] for result in results)
