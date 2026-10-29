"""Comparação reproduzível de auditorias, com casos de referência explícitos."""

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from .audit import amounts
from .pipeline import atomic_write
from .quality import cells, normalize


def _counts(documents):
    quality = Counter(d.get('quality_status', d.get('state', 'unknown')) for d in documents)
    occurrences, affected = Counter(), Counter()
    for doc in documents:
        occurrences.update(f['rule'] for f in doc.get('findings', []))
        affected.update({f['rule'] for f in doc.get('findings', [])})
    return {'quality': dict(quality), 'occurrences': dict(occurrences), 'affected_documents': dict(affected)}


def _compact(text):
    return ' '.join(text.casefold().split())


def reference_checks(manifest, reference):
    references = json.loads(Path(reference).read_text(encoding='utf-8'))
    documents = {Path(d['relative_source']).stem: d for d in manifest['documents']}
    # A localização da saída é guardada no manifesto, incluindo relatórios em corridas/.
    output = Path(manifest['output'])
    results = []
    for case in references['documents']:
        doc = documents.get(case['stem'])
        if doc is None:
            results.append({'document': case['stem'], 'status': 'absent'})
            continue
        md = output / Path(doc['relative_source']).with_suffix('.md')
        text = md.read_text(encoding='utf-8')
        lines = text.splitlines()
        checks = []
        positions = []
        for heading in case.get('headings', []):
            present = heading in lines
            checks.append({'check': heading, 'passed': present})
            if present:
                positions.append(lines.index(heading))
        checks.append({'check': 'ordem dos cabeçalhos', 'passed': positions == sorted(positions)})
        for forbidden in case.get('forbidden_headings', []):
            checks.append({'check': 'não inventar ' + forbidden,
                           'passed': not any(line == forbidden or line.startswith(forbidden + ' -') for line in lines)})
        rows = [cells(line) for line in lines if line.startswith('|')]
        for expected in case.get('salary_rows', []):
            matched = 0
            for row in rows:
                category = next((i for i, value in enumerate(row) if _compact(value) == _compact(expected['category'])), None)
                if category is None:
                    continue
                values = [next(iter(amounts(value)), '') for value in row[category+1:category+1+len(expected['values'])]]
                if values == expected['values']:
                    matched += 1
            checks.append({'check': expected['category'], 'matched_rows': matched,
                           'passed': matched >= expected.get('minimum_occurrences', 1)})
        errors = {f['rule'] for f in doc.get('findings', []) if f['severity'] == 'error'}
        for rule in case.get('required_errors', []):
            checks.append({'check': 'manter bloqueio ' + rule, 'passed': rule in errors})
        results.append({'document': case['stem'], 'status': 'passed' if all(c['passed'] for c in checks) else 'failed',
                        'checks': checks})
    return {'reference_sha256': hashlib.sha256(Path(reference).read_bytes()).hexdigest(),
            'source': references.get('source'), 'documents': results}


def evaluate(baseline, candidate, destination, *, reference=None):
    baseline, candidate, destination = Path(baseline), Path(candidate), Path(destination)
    before = json.loads(baseline.read_text(encoding='utf-8'))
    after = json.loads(candidate.read_text(encoding='utf-8'))
    left = {d['relative_source']: d for d in before['documents']}
    right = {d['relative_source']: d for d in after['documents']}
    shared = sorted(left.keys() & right.keys())
    transitions = Counter(f'{left[k].get("quality_status", left[k].get("state"))} → '
                          f'{right[k].get("quality_status", right[k].get("state"))}' for k in shared)
    rules = sorted({f['rule'] for d in [*left.values(), *right.values()] for f in d.get('findings', [])})
    b, a = _counts(list(left.values())), _counts(list(right.values()))
    by_family = {}
    for family in sorted({str(Path(k).parent) for k in shared}):
        keys = [k for k in shared if str(Path(k).parent) == family]
        by_family[family] = {'before': _counts([left[k] for k in keys])['quality'],
                             'after': _counts([right[k] for k in keys])['quality']}
    data = {
        'schema_version': 1,
        'baseline_run_id': before['run_id'], 'candidate_run_id': after['run_id'],
        'baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
        'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
        'baseline_status': before['status'], 'candidate_status': after['status'],
        'compared': len(shared), 'only_baseline': sorted(left.keys()-right.keys()),
        'only_candidate': sorted(right.keys()-left.keys()), 'before': b, 'after': a,
        'transitions': dict(transitions), 'by_family': by_family,
        'manifest_bytes': {'before': baseline.stat().st_size, 'after': candidate.stat().st_size},
        'candidate_duration_seconds': (datetime.fromisoformat(after['finished_at_utc']) -
                                       datetime.fromisoformat(after['started_at_utc'])).total_seconds(),
        'limitations': 'Estados automáticos não são aprovação humana. Sem referência anotada, não se estimam falsos positivos/negativos. Duração da extração original e reauditoria são operações diferentes.',
    }
    data['comparable_complete_corpus'] = (before['status'] == after['status'] == 'concluida'
        and left.keys() == right.keys() and all('quality_status' in d for d in right.values()))
    if reference:
        data['reference_checks'] = reference_checks(after, reference)
    destination.mkdir(parents=True, exist_ok=True)
    atomic_write(destination / 'comparacao.json', json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    lines = ['# Comparação de auditorias', '', f'Corridas: {before["run_id"]} → {after["run_id"]}.', '',
             f'Documentos comparados: {len(shared)}. Estado candidato: {after["status"]}.', '',
             '| Estado | Antes | Depois |', '| --- | ---: | ---: |']
    for state in sorted(set(b['quality']) | set(a['quality'])):
        lines.append(f'| {state} | {b["quality"].get(state, 0)} | {a["quality"].get(state, 0)} |')
    lines += ['', '## Regras', '', '| Regra | Documentos antes | Documentos depois | Ocorrências antes | Ocorrências depois |',
              '| --- | ---: | ---: | ---: | ---: |']
    for rule in rules:
        lines.append(f'| {rule} | {b["affected_documents"].get(rule, 0)} | {a["affected_documents"].get(rule, 0)} | '
                     f'{b["occurrences"].get(rule, 0)} | {a["occurrences"].get(rule, 0)} |')
    lines += ['', '## Limites', '', data['limitations'], '',
              f'Manifesto: {baseline.stat().st_size:,} → {candidate.stat().st_size:,} bytes.', '']
    if reference:
        lines += ['## Casos de referência', '']
        for case in data['reference_checks']['documents']:
            lines.append(f'- {case["document"]}: **{case["status"]}**.')
            for check in case.get('checks', []):
                if not check['passed']:
                    lines.append('  - Falhou: ' + re.sub(r'\s+', ' ', check['check']))
    atomic_write(destination / 'comparacao.md', normalize('\n'.join(lines) + '\n'))
    return data
