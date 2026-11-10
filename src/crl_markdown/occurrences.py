"""Ocorrências conservadas por versão, independentes da última auditoria."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .locking import exclusive
from .pipeline import atomic_write

LABELS = {
    'pending': 'Pendente',
    'human_resolved': 'Resolvida por conferência humana',
    'absent_unconfirmed': 'Ausente na versão atual — por confirmar',
    'source_changed': 'Fonte alterada — exige nova conferência',
    'unverified': 'Versão atual por verificar',
}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def version_key(report):
    names = ('source_sha256', 'markdown_sha256', 'findings', 'pipeline_fingerprint', 'audit_policy_version')
    # Ler as observações da primeira implementação sem reescrever evidências.
    legacy = report.get('version_key_schema') == 1 or ('version_id' in report and 'version_key_schema' not in report)
    if not legacy:
        names += ('docling_document_sha256', 'docling_version', 'model_manifest_sha256', 'options', 'document_profile')
    return _digest({**{k: report.get(k) for k in names},
        'revision_id': (report.get('revision') or {}).get('revision_id', report.get('revision_id'))})


def _folder(output, relative):
    from .validation import _key
    return Path(output) / '_auditoria/ocorrencias' / _key(relative)


def record_version(output, relative, report, *, origin='conversion'):
    """Chamado sob o bloqueio da pasta; nunca substitui uma observação existente."""
    if not report.get('quality_status') or not report.get('source_sha256'):
        return
    key = version_key(report)
    path = _folder(output, relative) / 'versoes' / (key + '.json')
    if path.exists():
        return
    data = {'schema': 1, 'version_key_schema': 2, 'version_id': key, 'relative_source': relative,
            'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'origin': origin,
            'source_sha256': report['source_sha256'],
            'markdown_sha256': report.get('markdown_sha256'), 'findings': report.get('findings', []),
            'reviewer': (report.get('revision') or {}).get('reviewer'),
            'revision_id': (report.get('revision') or {}).get('revision_id'),
            'pipeline_fingerprint': report.get('pipeline_fingerprint'),
            'audit_policy_version': report.get('audit_policy_version')}
    data.update({k: report.get(k) for k in ('docling_document_sha256', 'docling_version',
                                          'model_manifest_sha256', 'options', 'document_profile')})
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def _finding_key(source, finding):
    # As resoluções acrescentam campos ao finding, mas mantêm o ID original.
    identity = finding.get('id') or _digest({
        **{k: v for k, v in finding.items() if k not in {'resolution', 'original_severity'}},
        'severity': finding.get('original_severity', finding.get('severity'))})
    return _digest([source, identity])


def _capture_legacy(output, relative, *, destination=None):
    destination = Path(output) if destination is None else destination
    audit = Path(output) / '_auditoria'
    paths = [*sorted((audit / 'corridas').glob('*/manifest*.json')), audit / 'manifest.json']
    for path in paths:
        if not path.exists():
            continue
        manifest = json.loads(path.read_text(encoding='utf-8'))
        for report in manifest.get('documents', []):
            if report.get('relative_source') == relative:
                record_version(destination, relative, report, origin='archived_run')
    # Publicações imutáveis conservam resoluções humanas que não figuram no índice base.
    from .validation import _key
    for path in sorted((audit / 'correcoes' / _key(relative)).glob(
            '*/publicacoes/*/_auditoria/documentos/**/*.qualidade.json')):
        report = json.loads(path.read_text(encoding='utf-8'))
        record_version(destination, relative, report, origin='correction_publication')


def _history(output, relative):
    from .review_exchange import ensure_complete_imports
    from .revisions import _record
    from .validation import _verified

    ensure_complete_imports(output)
    _capture_legacy(output, relative)
    current = None
    verification_error = None
    try:
        _, _, current = _verified(Path(output), _record(output, relative))
        record_version(output, relative, current, origin='verified_current')
    except (ValueError, OSError) as error:
        verification_error = str(error)
    current_key = version_key(current) if current else None
    current_findings = {_finding_key(current['source_sha256'], f): f
                        for f in current.get('findings', [])} if current else {}
    rows = {}
    folder = _folder(output, relative)
    for path in sorted((folder / 'versoes').glob('*.json')):
        version = json.loads(path.read_text(encoding='utf-8'))
        if path.stem != version_key(version) or version.get('version_id') != path.stem:
            raise ValueError('Uma observação histórica perdeu integridade. Conserve a pasta e peça apoio.')
        for finding in version['findings']:
            if finding.get('severity') == 'info' and not finding.get('resolution'):
                continue
            key = _finding_key(version['source_sha256'], finding)
            row = rows.setdefault(key, {'occurrence_id': key, 'finding': finding,
                                       'source_sha256': version['source_sha256'], 'observations': []})
            row['observations'].append({'version_id': version['version_id'],
                                        'recorded_at_utc': version['recorded_at_utc'],
                                        'origin': version['origin'], 'finding': finding})
    confirmations = [json.loads(p.read_text(encoding='utf-8'))
                     for p in (folder / 'confirmacoes').glob('*.json')]
    for key, row in rows.items():
        row['observations'].sort(key=lambda observation: observation['recorded_at_utc'])
        present = current_findings.get(key)
        row['status'] = ('unverified' if current is None else
                         'source_changed' if row['source_sha256'] != current['source_sha256'] else
                         'human_resolved' if present and present.get('resolution') else
                         'pending' if present else 'absent_unconfirmed')
        row['current_version_id'] = current_key
        row['confirmations'] = sorted([c for c in confirmations if c['occurrence_id'] == key],
                                      key=lambda c: c['at_utc'])
        confirmed = next((c for c in reversed(row['confirmations'])
                          if c['version_id'] == current_key), None)
        if confirmed and row['status'] in {'absent_unconfirmed', 'source_changed'}:
            row['status'] = 'human_resolved'
        if present and present.get('resolution'):
            row['resolution'] = present['resolution']
        elif confirmed:
            row['resolution'] = confirmed
        row['status_label'] = LABELS[row['status']]
    return {'relative_source': relative, 'current_version_id': current_key,
            'verification_error': verification_error, 'occurrences': list(rows.values())}


def history(output, relative):
    with exclusive(Path(output) / '_auditoria/.operacao.lock'):
        return _history(output, relative)


def confirm_absence(output, relative, occurrence_id, *, reviewer, notes, expected_version):
    if not reviewer.strip() or not notes.strip():
        raise ValueError('Indique o responsável e a evidência da conferência histórica.')
    with exclusive(Path(output) / '_auditoria/.operacao.lock'):
        data = _history(output, relative)
        if not expected_version or data['current_version_id'] != expected_version:
            raise ValueError('A versão atual mudou ou não está verificada. Reabra o histórico.')
        row = next((r for r in data['occurrences'] if r['occurrence_id'] == occurrence_id), None)
        if row is None or row['status'] not in {'absent_unconfirmed', 'source_changed'}:
            raise ValueError('Só pode confirmar uma ocorrência histórica ausente. '
                             'As ocorrências atuais exigem o percurso de correção e reauditoria.')
        record = {'schema': 1, 'occurrence_id': occurrence_id, 'version_id': expected_version,
                  'previous_status': row['status'], 'reviewer': reviewer.strip(), 'notes': notes.strip(),
                  'at_utc': datetime.now(timezone.utc).isoformat(), 'relative_source': relative}
        path = _folder(output, relative) / 'confirmacoes' / (uuid4().hex + '.json')
        atomic_write(path, json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        return path
