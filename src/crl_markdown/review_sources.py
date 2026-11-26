"""Relocalização explícita de PDFs sem reescrever relatórios ou aprovações."""

import hashlib
import json
import platform
from pathlib import Path

from .models import _sha256


def _local_map(output):
    machine = hashlib.sha256(platform.node().encode('utf-8')).hexdigest()[:24]
    return Path(output) / '_auditoria/fontes-locais' / (machine + '.json')


def resolve_source(output, document):
    """Só aceita caminhos cujo conteúdo coincide com a fonte auditada."""
    output = Path(output)
    expected = document.get('source_sha256')
    source = Path(document['source'])
    try:
        if source.is_file() and (not expected or _sha256(source) == expected):
            return source
    except OSError:
        pass
    for mapping in (_local_map(output), output / '_auditoria/fontes-transferidas/fontes.json'):
        if not mapping.exists() or not expected:
            continue
        paths = json.loads(mapping.read_text(encoding='utf-8')).get('sources', {})
        candidate = paths.get(expected)
        if candidate:
            path = Path(candidate)
            path = path if path.is_absolute() else output / path
            if path.is_file() and _sha256(path) == expected:
                return path.resolve()
    raise ValueError('O PDF original não está disponível nesta máquina ou o conteúdo mudou. '
                     'Use Localizar PDFs do lote para associar os originais pelos seus hashes.')


def locate_sources(output, folder):
    """Pesquisa só a pasta autorizada; grava referências locais, não altera evidências."""
    import os

    from .locking import exclusive
    from .pipeline import atomic_write
    from .review_history import load_history

    output, folder = Path(output).resolve(), Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError('Escolha a pasta que contém os PDFs originais.')
    documents = load_history(output)['documents']
    wanted = {d['source_sha256'] for d in documents if d.get('source_sha256')}
    found = {}
    for path in sorted(folder.rglob('*')):
        if path.is_file() and path.suffix.lower() == '.pdf':
            digest = _sha256(path)
            if digest in wanted and digest not in found:
                try:
                    found[digest] = os.path.relpath(path, output)
                except ValueError:  # Unidades diferentes em Windows.
                    found[digest] = str(path)
    target = _local_map(output)
    with exclusive(output / '_auditoria/.operacao.lock'):
        previous = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
        sources = {**previous.get('sources', {}), **found}
        atomic_write(target, json.dumps({'schema': 1, 'sources': sources}, ensure_ascii=False, indent=2) + '\n')
    return {'found': len(found), 'missing': len(wanted - found.keys())}
