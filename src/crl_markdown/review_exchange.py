"""Cópias de revisão e fusão por comparação com a base, sem substituir o corpus."""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .locking import exclusive
from .models import _sha256
from .pipeline import atomic_write

META = '_auditoria/intercambio.json'
CORPUS = '_auditoria/corpus.json'
REVIEW_AREAS = {'correcoes', 'revisoes', 'versoes', 'notas', 'ocorrencias'}


def ensure_complete_imports(output):
    for path in (Path(output) / '_auditoria/intercambios').glob('*/importacao.json'):
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('status') == 'prepared':
            raise ValueError('Uma importação foi interrompida. Conserve a pasta e use '
                             'Recuperar importação interrompida antes de continuar.')


def _ignored(relative):
    parts = relative.parts
    return (relative.suffix == '.lock' or relative.name == '.DS_Store'
            or relative.as_posix() == META or '_assistencia' in parts
            or parts[:2] in {('_auditoria', 'fontes-locais'), ('_auditoria', 'fontes-transferidas')})


def inventory(root):
    result = {}
    for path in sorted(Path(root).rglob('*')):
        if path.is_symlink():
            raise ValueError('A pasta de revisão contém ligações simbólicas. Use uma cópia de ficheiros reais.')
        relative = path.relative_to(root)
        if path.is_file() and not _ignored(relative):
            if '\\' in relative.as_posix() or ':' in relative.as_posix():
                raise ValueError('Há nomes de ficheiros incompatíveis com a transferência Windows.')
            result[relative.as_posix()] = _sha256(path)
    if len({name.casefold() for name in result}) != len(result):
        raise ValueError('Há nomes de ficheiros que colidem em Windows.')
    return result


def _metadata(branch):
    data = json.loads((Path(branch) / META).read_text(encoding='utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('base_files'), dict):
        raise ValueError('A pasta não é uma cópia de revisão reconhecida.')
    # Estes caminhos são dados de outra máquina, nunca destinos arbitrários.
    for name, digest in data['base_files'].items():
        path = Path(name)
        if (path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name
                or not isinstance(digest, str) or len(digest) != 64):
            raise ValueError('Inventário de base inválido na cópia de revisão.')
    return data


def export_review(output, destination, *, reviewer):
    from .review_sources import resolve_source
    from .validation import _load, _verified

    output, destination = Path(output).resolve(), Path(destination).resolve()
    if not reviewer.strip():
        raise ValueError('Indique quem recebe a cópia de revisão.')
    if destination.exists() or destination.is_relative_to(output) or output.is_relative_to(destination):
        raise ValueError('Escolha uma pasta de revisão nova e fora da pasta original.')
    with exclusive(output / '_auditoria/.operacao.lock'):
        manifest = _load(output)
        identities = {}
        for document in manifest['documents']:
            if document.get('quality_status'):
                _, report_path, report = _verified(output, document)
                from .validation import _key
                identities[_key(document['relative_source'])] = {
                    'source_sha256': report['source_sha256'], 'markdown_sha256': report['markdown_sha256'],
                    'report_sha256': _sha256(report_path)}
        corpus = output / CORPUS
        if not corpus.exists():
            atomic_write(corpus, json.dumps({'schema': 1, 'corpus_id': uuid4().hex}) + '\n')
        corpus_id = json.loads(corpus.read_text(encoding='utf-8'))['corpus_id']
        baseline = inventory(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix='.crl-revisao-', dir=destination.parent))
        try:
            for name, digest in baseline.items():
                target = staging / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(output / name, target)
                if _sha256(target) != digest:
                    raise ValueError('A pasta mudou durante a exportação. Repita com os editores fechados.')
            sources = {}
            for document in manifest['documents']:
                if not document.get('source_sha256'):
                    continue
                pdf = resolve_source(output, document)
                digest = document['source_sha256']
                relative = Path('_auditoria/fontes-transferidas') / digest / Path(document['relative_source']).name
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdf, target)
                if _sha256(target) != digest:
                    raise ValueError('Um PDF mudou durante a exportação. Conserve os originais e repita.')
                sources[digest] = relative.as_posix()
            atomic_write(staging / '_auditoria/fontes-transferidas/fontes.json',
                         json.dumps({'schema': 1, 'sources': sources}, ensure_ascii=False, indent=2) + '\n')
            data = {'schema': 1, 'export_id': uuid4().hex, 'corpus_id': corpus_id,
                    'reviewer': reviewer.strip(), 'created_at_utc': datetime.now(timezone.utc).isoformat(),
                    'base_files': baseline, 'base_identities': identities}
            atomic_write(staging / META, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
            if inventory(output) != baseline:
                raise ValueError('A pasta mudou durante a exportação. Repita com os editores fechados.')
            if destination.exists():
                raise FileExistsError('A pasta de destino foi criada por outra operação.')
            staging.rename(destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return destination


def _document_for_file(name):
    parts = Path(name).parts
    if len(parts) < 3 or parts[0] != '_auditoria' or parts[1] not in REVIEW_AREAS:
        return None
    if parts[1] == 'versoes':
        return Path(parts[2]).stem
    return parts[2]


def _human_file(name):
    parts = Path(name).parts
    # Observações históricas são aditivas; notas também. A publicação/decisão
    # concorrente sobre o mesmo documento exige reconciliação explícita.
    return len(parts) > 2 and parts[1] in {'correcoes', 'versoes', 'revisoes'}


def _mutable_review_file(name):
    parts = Path(name).parts
    return (len(parts) == 3 and parts[:2] == ('_auditoria', 'versoes')
            or len(parts) == 5 and parts[:2] == ('_auditoria', 'correcoes') and parts[-1] == 'correcao.md')


def _plan(output, branch):
    output, branch = Path(output), Path(branch)
    data = _metadata(branch)
    ensure_complete_imports(output)
    ensure_complete_imports(branch)
    local_corpus = json.loads((output / CORPUS).read_text(encoding='utf-8'))
    if data.get('corpus_id') != local_corpus.get('corpus_id'):
        raise ValueError('Esta cópia pertence a outro corpus. Nenhum ficheiro foi importado.')
    base, local, remote = data['base_files'], inventory(output), inventory(branch)
    deleted = set(base) - remote.keys()
    if deleted:
        raise ValueError('A cópia de revisão perdeu ficheiros da base. Não se importam eliminações.')
    changed = {name: digest for name, digest in remote.items() if base.get(name) != digest}
    for name in changed:
        if _document_for_file(name) is None:
            raise ValueError('A cópia foi usada para alterar o corpus ou executar uma nova conversão. '
                             'A importação aceita apenas trabalho de revisão, conservando a base.')
        if name in base and not _mutable_review_file(name):
            raise ValueError('A cópia alterou uma evidência imutável da base. '
                             'Conserve ambas as pastas e use uma nova correção, sem editar publicações ou decisões antigas.')
    effective = {name: digest for name, digest in changed.items() if local.get(name) != digest}
    for name in list(effective):
        parts = Path(name).parts
        if (len(parts) == 5 and parts[:2] == ('_auditoria', 'ocorrencias')
                and parts[3] == 'versoes' and (output / name).exists()):
            from .occurrences import version_key
            left = json.loads((output / name).read_text(encoding='utf-8'))
            right = json.loads((branch / name).read_text(encoding='utf-8'))
            if version_key(left) == version_key(right) == Path(name).stem:
                del effective[name]
    local_changes = {name for name in local if local[name] != base.get(name)}
    conflicts = {name for name in effective
                 if local.get(name) not in {None, base.get(name)}}
    # Alterações diferentes em ficheiros distintos do mesmo documento também conflituam.
    local_docs = {_document_for_file(n) for n in local_changes if _human_file(n)} - {None}
    remote_docs = {_document_for_file(n) for n in effective if _human_file(n)} - {None}
    conflicted_docs = local_docs & remote_docs
    from .validation import _key, _load, _verified
    affected = {_document_for_file(name) for name in effective} - {None}
    local_documents = {_key(d['relative_source']): d for d in _load(output)['documents']}
    remote_documents = {_key(d['relative_source']): d for d in _load(branch)['documents']}
    for key in affected:
        if key not in local_documents or key not in remote_documents:
            raise ValueError('Revisão de documento desconhecido na cópia recebida.')
        _, report_path, report = _verified(output, local_documents[key])
        identity = {'source_sha256': report['source_sha256'], 'markdown_sha256': report['markdown_sha256'],
                    'report_sha256': _sha256(report_path)}
        if identity != data.get('base_identities', {}).get(key) and key in remote_docs:
            conflicted_docs.add(key)
        _verified(branch, remote_documents[key])
    for name in effective:
        if Path(name).suffix == '.json':
            json.loads((branch / name).read_text(encoding='utf-8'))
    return {'metadata': data, 'local': local, 'remote': remote, 'changes': effective,
            'conflicts': sorted(conflicts),
            'conflicted_documents': sorted(local_documents[k]['relative_source'] for k in conflicted_docs)}


def plan_merge(output, branch):
    with exclusive(Path(output) / '_auditoria/.operacao.lock'):
        plan = _plan(output, branch)
        return {k: plan[k] for k in ('changes', 'conflicts', 'conflicted_documents')}


def merge_review(output, branch, *, reviewer):
    """Aplica um plano validado; um journal conserva a evidência para recuperação."""
    if not reviewer.strip():
        raise ValueError('Indique o responsável pela importação.')
    output, branch = Path(output).resolve(), Path(branch).resolve()
    if output == branch or branch.is_relative_to(output) or output.is_relative_to(branch):
        raise ValueError('Escolha uma cópia de revisão separada da pasta principal.')
    with exclusive(output / '_auditoria/.operacao.lock'):
        plan = _plan(output, branch)
        if plan['conflicts'] or plan['conflicted_documents']:
            raise ValueError('Há revisões concorrentes incompatíveis. Nenhum ficheiro foi importado. '
                             'Conserve as duas pastas e consulte o plano de conflitos: '
                             + ', '.join(plan['conflicted_documents'] + plan['conflicts']))
        if not plan['changes']:
            return {'imported': 0, 'receipt': None}
        journal = output / '_auditoria/intercambios' / uuid4().hex
        journal.mkdir(parents=True)
        updates = journal / 'ficheiros'
        originals = journal / 'anteriores'
        for name, digest in plan['changes'].items():
            source = branch / name
            target = updates / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if _sha256(target) != digest:
                raise ValueError('A cópia recebida mudou durante a importação. A base não foi alterada.')
            if (output / name).exists():
                backup = originals / name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(output / name, backup)
        receipt = journal / 'importacao.json'
        record = {'schema': 1, 'export_id': plan['metadata']['export_id'],
                  'reviewer': reviewer.strip(), 'at_utc': datetime.now(timezone.utc).isoformat(),
                  'files': plan['changes'], 'previous': {n: plan['local'].get(n) for n in plan['changes']},
                  'status': 'prepared'}
        atomic_write(receipt, json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        # Nenhuma publicação fica ativa antes de existirem os seus artefactos.
        ordered = sorted(plan['changes'], key=lambda n: Path(n).parts[:2] == ('_auditoria', 'versoes'))
        applied = []
        try:
            if inventory(branch) != plan['remote']:
                raise ValueError('A cópia recebida mudou. Feche os editores e repita a importação.')
            for name in ordered:
                target = output / name
                if not target.resolve().is_relative_to(output):
                    raise ValueError('O destino da importação está fora da pasta permitida.')
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name('.importacao-' + uuid4().hex)
                try:
                    shutil.copy2(updates / name, temporary)
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
                applied.append(name)
            record['status'] = 'complete'
            atomic_write(receipt, json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        except BaseException:
            for name in reversed(applied):
                target = output / name
                if record['previous'][name] is None:
                    target.unlink(missing_ok=True)
                else:
                    shutil.copy2(originals / name, target)
            record['status'] = 'rolled_back'
            atomic_write(receipt, json.dumps(record, ensure_ascii=False, indent=2) + '\n')
            raise
        return {'imported': len(applied), 'receipt': str(receipt)}


def recover_imports(output):
    """Repõe a base de importações interrompidas, recusando alterações posteriores."""
    output = Path(output).resolve()
    recovered = []
    with exclusive(output / '_auditoria/.operacao.lock'):
        for receipt in (output / '_auditoria/intercambios').glob('*/importacao.json'):
            data = json.loads(receipt.read_text(encoding='utf-8'))
            if data.get('status') != 'prepared':
                continue
            for name, incoming in data['files'].items():
                relative = Path(name)
                if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
                    raise ValueError('Journal de importação inválido. Conserve os ficheiros e peça apoio.')
                target = output / name
                if not target.resolve().is_relative_to(output):
                    raise ValueError('O destino da recuperação está fora da pasta permitida.')
                actual = _sha256(target) if target.exists() else None
                previous = data['previous'][name]
                if actual not in {previous, incoming}:
                    raise ValueError('Há alterações posteriores à importação interrompida. '
                                     'Conserve a pasta e peça reconciliação ao apoio.')
                backup = receipt.parent / 'anteriores' / name
                if not backup.resolve().is_relative_to(receipt.parent):
                    raise ValueError('A cópia de recuperação está fora da pasta permitida.')
                if previous and (not backup.is_file() or _sha256(backup) != previous):
                    raise ValueError('A cópia de recuperação perdeu integridade. Conserve a pasta e peça apoio.')
            ordered = sorted(data['files'], key=lambda n: Path(n).parts[:2] != ('_auditoria', 'versoes'))
            for name in ordered:
                target = output / name
                if data['previous'][name] is None:
                    target.unlink(missing_ok=True)
                else:
                    shutil.copy2(receipt.parent / 'anteriores' / name, target)
            data['status'] = 'recovered'
            data['recovered_at_utc'] = datetime.now(timezone.utc).isoformat()
            atomic_write(receipt, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
            recovered.append(str(receipt))
    return recovered
