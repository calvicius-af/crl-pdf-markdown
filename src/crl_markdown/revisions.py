"""Correções versionadas: o rascunho nunca substitui uma extração ou aprovação."""

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .locking import exclusive
from .models import _sha256
from .pipeline import Options, atomic_write, convert_pdf, previous_report
from .quality import cells, parser


def correction_structure(markdown, generated, doc_id, subtype):
    from .document import plain_markdown
    from .legacy import extractor as rules

    lines = markdown.splitlines()
    for title in generated:
        if title in lines:
            lines.remove(title)
    text = '\n'.join(lines)
    tokens = parser().parse(text)
    table_ranges = {t.map[0]: t.map[1] for t in tokens if t.type == 'table_open'}
    source, index = [], 0
    while index < len(lines):
        if index in table_ranges:
            end = table_ranges[index]
            source.append(rules.MARCA_TABELA_INI)
            for i in range(index, end):
                if i != index + 1:
                    source.append(' | '.join(plain_markdown(c).strip() for c in cells(lines[i])))
            source.append(rules.MARCA_TABELA_FIM)
            index = end
        else:
            source.append(plain_markdown(re.sub(r'^#{1,6}\s+', '', lines[index])).strip())
            index += 1
    return rules.estruturar('\n'.join(source), doc_id, subtipo=subtype)


def _record(output, relative):
    from .validation import _load
    matches = [d for d in _load(output)['documents'] if d['relative_source'] == relative]
    if len(matches) != 1:
        raise ValueError('Documento não encontrado de forma única no lote.')
    return matches[0]


def _identity(target, report_path, report):
    return {**{k: report[k] for k in ('source_sha256', 'markdown_sha256')},
            'report_sha256': _sha256(report_path)}


def table_signature(markdown):
    from .document import plain_markdown
    lines = markdown.splitlines()
    tables = []
    for token in parser().parse(markdown):
        if token.type == 'table_open':
            start, end = token.map
            tables.append([[plain_markdown(cell).strip() for cell in cells(lines[i])]
                           for i in range(start, end) if i != start + 1])
    return hashlib.sha256(json.dumps(tables, ensure_ascii=False).encode()).hexdigest()


def current_pointer(output, relative):
    from .validation import _key
    return Path(output) / '_auditoria/versoes' / (_key(relative) + '.json')


def active_version(output, document):
    output = Path(output).resolve()
    pointer = current_pointer(output, document['relative_source'])
    if not pointer.exists():
        return None
    data = json.loads(pointer.read_text(encoding='utf-8'))
    base = (output / data['publication']).resolve()
    allowed = (output / '_auditoria/correcoes').resolve()
    if not base.is_relative_to(allowed):
        raise ValueError('Versão de correção fora da pasta permitida.')
    relative = Path(document['relative_source']).with_suffix('.md')
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Caminho relativo de correção inválido.')
    target = base / relative
    audit = base / '_auditoria/documentos' / relative.parent
    report_path = audit / (relative.stem + '.qualidade.json')
    report = previous_report(Path(document['source']), target, audit)
    if (report is None or report['source_sha256'] != document['source_sha256']
            or _identity(target, report_path, report) != data['identity']):
        raise ValueError('A versão corrigida mudou ou perdeu integridade. Reaudite e confira de novo.')
    return target, report_path, report


def create_revision(output, relative_source, reviewer):
    from .validation import _key, _verified

    output = Path(output).resolve()
    if not reviewer.strip():
        raise ValueError('Indique o responsável pela correção.')
    with exclusive(output / '_auditoria/.operacao.lock'):
        document = _record(output, relative_source)
        target, report_path, report = _verified(output, document)
        revision = output / '_auditoria/correcoes' / _key(relative_source) / uuid4().hex
        revision.mkdir(parents=True)
        cache = revision / 'cache'
        cache.mkdir()
        for suffix in ('.docling.json', '.docling.md'):
            shutil.copy2(report_path.with_name(Path(relative_source).stem + suffix),
                         cache / (Path(relative_source).stem + suffix))
        shutil.copy2(report_path, cache / report_path.name)
        shutil.copy2(target, revision / 'correcao.md')
        meta = {'schema_version': 1, 'origin_output': str(output),
                'relative_source': relative_source, 'reviewer': reviewer.strip(),
                'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'parent': _identity(target, report_path, report),
                'generated_headings': report.get('generated_headings', []),
                'table_signature': table_signature(target.read_text(encoding='utf-8')),
                'revision_id': revision.name}
        atomic_write(revision / 'revision.json', json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
        return revision


def _apply_resolutions(report, resolutions, reviewer, changed):
    findings = {f['id']: f for f in report['findings']}
    for resolution in resolutions:
        finding = findings.get(resolution.get('finding_id'))
        if finding is None:
            raise ValueError('Ocorrência não pertence à auditoria atual da correção.')
        if (not resolution.get('notes', '').strip() or not isinstance(resolution.get('page'), int)
                or isinstance(resolution['page'], bool) or resolution['page'] < 1
                or resolution['page'] > report['pages']):
            raise ValueError('A resolução exige página válida e evidência nas notas.')
        action = resolution.get('action')
        rule = finding['rule']
        table = rule in {'TABLE_OVERLAP', 'TABLE_EMPTY', 'TABLE_GRID_GAP', 'TABLE_CELL_POSITION'}
        if finding['severity'] == 'error':
            permitted = ((rule == 'IMAGE' and action == 'decorativo')
                         or (rule == 'IMAGE' and action == 'transcrito' and changed)
                         or (table and action == 'corrigido' and changed and report.get('table_content_changed')))
            if not permitted:
                raise ValueError('Este erro exige correção verificável por nova auditoria; não pode ser dispensado por nota.')
        elif action != 'conferido':
            raise ValueError('Use conferido para registar a resolução de um aviso.')
        finding['original_severity'] = finding['severity']
        finding['severity'] = 'info'
        finding['resolution'] = {**resolution, 'reviewer': reviewer,
                                 'at_utc': datetime.now(timezone.utc).isoformat()}
    report['quality_status'] = ('blocked' if any(f['severity'] == 'error' for f in findings.values())
                                else 'review' if any(f['severity'] == 'warning' for f in findings.values()) else 'passed')
    report['state'] = 'rever' if report['quality_status'] != 'passed' else 'sem_alertas_automaticos'


def audit_revision(revision, *, resolutions=()):
    from .cache import CachedConverter
    from .report import new_manifest, write_reports
    from .validation import _verified

    revision = Path(revision).resolve()
    meta = json.loads((revision / 'revision.json').read_text(encoding='utf-8'))
    output = Path(meta['origin_output']).resolve()
    if not revision.is_relative_to((output / '_auditoria/correcoes').resolve()):
        raise ValueError('Rascunho fora da pasta de correções.')
    relative = meta['relative_source']
    with exclusive(output / '_auditoria/.operacao.lock'):
        document = _record(output, relative)
        target, report_path, report = _verified(output, document)
        # Reauditar o próprio rascunho é permitido, mas uma revisão diferente
        # entretanto publicada exige nova base para não perder trabalho.
        pointer = current_pointer(output, relative)
        same_revision = pointer.exists() and json.loads(pointer.read_text()).get('revision_id') == meta['revision_id']
        if not same_revision and _identity(target, report_path, report) != meta['parent']:
            raise ValueError('Outra revisão mudou a base. Crie uma correção a partir da versão atual.')
        draft = (revision / 'correcao.md').read_text(encoding='utf-8')
        draft_digest = hashlib.sha256(draft.encode('utf-8')).hexdigest()
        if not draft.strip():
            raise ValueError('A correção está vazia.')
        publication = revision / 'publicacoes' / uuid4().hex
        relative_md = Path(relative).with_suffix('.md')
        audit = publication / '_auditoria/documentos' / relative_md.parent
        cache_path = (revision / meta.get('extraction_cache', 'cache')).resolve()
        if not cache_path.is_relative_to(revision):
            raise ValueError('Cache de correção fora da pasta da revisão.')
        cache = CachedConverter(cache_path)
        options_data = report.get('options', {})
        options = Options(ocr=bool(options_data.get('ocr')), offline=bool(options_data.get('offline')),
                          models=Path(options_data['models']) if options_data.get('models') else None)
        updated = convert_pdf(Path(document['source']), publication / relative_md, cache, options,
                              audit_dir=audit, markdown_override=draft,
                              generated_headings_override=meta['generated_headings'])
        updated['revision'] = meta
        if _sha256(revision / 'correcao.md') != draft_digest:
            raise ValueError('O rascunho mudou durante a auditoria. Guarde e reaudite de novo.')
        updated['draft_sha256'] = draft_digest
        updated['table_content_changed'] = table_signature(draft) != meta['table_signature']
        if same_revision and report.get('draft_sha256') == draft_digest:
            replacing = {r['finding_id'] for r in resolutions}
            inherited = [f['resolution'] for f in report.get('findings', []) if f.get('resolution')
                         and f['id'] not in replacing]
            resolutions = inherited + list(resolutions)
        _apply_resolutions(updated, resolutions, meta['reviewer'],
                           updated['markdown_sha256'] != meta['parent']['markdown_sha256'])
        saved_report = audit / (relative_md.stem + '.qualidade.json')
        atomic_write(saved_report, json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
        manifest = new_manifest(Path(document['source']), publication,
                                [(Path(document['source']), relative_md)], options_data)
        manifest['documents'] = [{**updated, 'relative_source': relative}]
        manifest['status'] = 'concluida'
        write_reports(manifest, publication, atomic_write)
        data = {'revision_id': meta['revision_id'], 'publication': str(publication.relative_to(output)),
                'quality_status': updated['quality_status'],
                'identity': _identity(publication / relative_md, saved_report, updated)}
        atomic_write(pointer, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        return publication, updated
