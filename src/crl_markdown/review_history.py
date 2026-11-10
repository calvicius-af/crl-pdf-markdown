"""Inventário de conferência independente da última seleção processada."""

import json
from collections import Counter
from pathlib import Path


def load_history(output):
    """Reúne corridas conservadas, sem transformar uma falha numa nova versão.

    O manifesto corrente continua a representar uma execução, não todo o corpus.
    A conferência/entrega precisam também dos documentos das execuções anteriores.
    Não se procura recursivamente: publicações de correções têm manifestos próprios.
    """
    output = Path(output)
    current = output / '_auditoria/manifest.json'
    paths = sorted([*(current.parent / 'corridas').glob('*/manifest.json'),
                    *(current.parent / 'corridas').glob('*/manifest-anterior-*.json')])
    if current.exists():
        paths.append(current)
    if not paths:
        raise FileNotFoundError(current)
    documents = {}
    runs = []
    latest = None
    for path in paths:
        try:
            manifest = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise ValueError(f'Histórico de revisão ilegível: {path}. '
                             'Conserve os ficheiros e peça apoio antes de continuar.') from error
        if not isinstance(manifest, dict) or not isinstance(manifest.get('documents'), list):
            raise ValueError(f'Histórico de revisão inválido: {path}.')
        latest = manifest
        run_id = manifest.get('run_id', path.parent.name)
        if run_id not in runs:
            runs.append(run_id)
        for record in manifest['documents']:
            relative = record.get('relative_source')
            if not isinstance(relative, str) or not relative:
                raise ValueError(f'Documento sem identidade no histórico: {path}.')
            relative_path = Path(relative)
            if relative_path.is_absolute() or '..' in relative_path.parts:
                raise ValueError('Caminho de documento inválido no histórico de revisão.')
            previous = documents.get(relative)
            if previous and not record.get('quality_status') and previous.get('quality_status'):
                # Uma tentativa falhada/incompleta não elimina a versão conferível.
                documents[relative] = {**previous, 'latest_attempt': {
                    'run_id': run_id, 'state': record.get('state'), 'error': record.get('error')}}
            else:
                documents[relative] = {**record, 'review_run_id': run_id}
    counts = Counter(d.get('quality_status', d.get('state', 'review')) for d in documents.values())
    return {**latest, 'documents': list(documents.values()), 'counts': dict(counts), 'review_runs': runs,
            'review_inventory': True}


def protect_reviewed_outputs(output, entries, *, overwrite):
    """Recusa colisões e substituição de bases com trabalho humano antes de escrever."""
    import hashlib

    output = Path(output)
    try:
        manifest = load_history(output)
    except FileNotFoundError:
        return
    records = {Path(d['relative_source']).with_suffix('.md').as_posix().casefold(): d
               for d in manifest['documents']}
    for source, relative in entries:
        previous = records.get(relative.as_posix().casefold())
        if previous is None:
            continue
        if Path(previous['source']).resolve() != Path(source).resolve():
            from .models import _sha256
            if not previous.get('source_sha256') or _sha256(Path(source)) != previous['source_sha256']:
                raise ValueError('Outro PDF já ocupa este nome na pasta de saída. '
                                 'Escolha uma pasta nova para conservar as duas versões.')
        if overwrite:
            target = output / relative
            if target.is_file() and previous.get('markdown_sha256'):
                from .models import _sha256
                if _sha256(target) != previous['markdown_sha256']:
                    raise ValueError('O Markdown foi alterado fora da extração. Escolha uma pasta nova '
                                     'para conservar as alterações existentes antes de repetir o OCR ou a extração.')
            key = hashlib.sha256(previous['relative_source'].encode('utf-8')).hexdigest()
            audit = output / '_auditoria'
            if (any((audit / 'revisoes' / key).glob('*.json'))
                    or (audit / 'correcoes' / key).exists()
                    or (audit / 'versoes' / (key + '.json')).exists()
                    or any((audit / 'notas' / key).glob('*.json'))
                    or any((audit / 'ocorrencias' / key / 'confirmacoes').glob('*.json'))):
                raise ValueError('Este documento tem correções ou decisões humanas guardadas. '
                                 'Escolha uma pasta de saída nova para a extração/OCR; '
                                 'o trabalho anterior será conservado na pasta original.')


def archive_legacy_manifest(output):
    """Conserva também o índice de versões antigas sem arquivo por corrida."""
    import hashlib

    from .pipeline import atomic_write

    current = Path(output) / '_auditoria/manifest.json'
    if not current.exists():
        return
    content = current.read_text(encoding='utf-8')
    data = json.loads(content)
    run_id = data.get('run_id')
    if not isinstance(run_id, str) or not run_id or Path(run_id).name != run_id or run_id in {'.', '..'}:
        raise ValueError('Identificador de corrida inválido; conserve o manifesto e peça apoio.')
    archive = current.parent / 'corridas' / run_id / 'manifest.json'
    if not archive.exists():
        atomic_write(archive, content)
    elif json.loads(archive.read_text(encoding='utf-8')) != data:
        # Nunca substituir evidência diferente. A cópia adicional fica na mesma
        # corrida, fora do glob de índices, e conserva os bytes do índice anterior.
        digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
        atomic_write(archive.with_name('manifest-anterior-' + digest + '.json'), content)
