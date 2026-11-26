"""Decisões humanas e entrega rastreável; nunca certifica o que não foi conferido."""

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .locking import exclusive
from .models import _sha256
from .pipeline import atomic_write, previous_report
from .report import escaped

_UNSPECIFIED = object()


def _load(output: Path):
    from .review_exchange import ensure_complete_imports
    from .review_history import load_history

    ensure_complete_imports(output)
    try:
        manifest = load_history(output)
    except FileNotFoundError as error:
        raise ValueError('Ainda não há um lote convertido nesta pasta de saída. '
                         'Execute Construir Markdown ou selecione a saída de uma conversão existente. '
                         'A organização e nomeação dos PDFs faz-se em Organizar PDFs (sem rede).') from error
    except json.JSONDecodeError as error:
        raise ValueError('Relatório de execução ilegível. Repita a conversão numa pasta nova.') from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get('documents'), list):
        raise ValueError('Relatório de execução inválido. Repita a conversão numa pasta nova.')
    return manifest


def _key(relative: str):
    return hashlib.sha256(relative.encode('utf-8')).hexdigest()


def _verified(output: Path, document: dict):
    from .revisions import active_version
    active = active_version(output, document)
    if active is not None:
        return active
    relative = Path(document['relative_source']).with_suffix('.md')
    target = output / relative
    if not target.resolve().is_relative_to(output.resolve()):
        raise ValueError('Caminho de documento fora da pasta de saída.')
    audit = output / '_auditoria/documentos' / relative.parent
    report_path = audit / (target.stem + '.qualidade.json')
    from .review_sources import resolve_source
    report = previous_report(resolve_source(output, document), target, audit)
    if report is None:
        raise ValueError(f'{relative}: o PDF ou a extração mudou ou está incompleto. Volte a converter e rever.')
    if report.get('markdown_sha256') != document.get('markdown_sha256'):
        raise ValueError(f'{relative}: o relatório do lote está desatualizado. Volte a executar a conversão.')
    return target, report_path, report


def decision_branches(output, relative_source):
    files = sorted((Path(output) / '_auditoria/revisoes' / _key(relative_source)).glob('*.json'))
    records = {_sha256(path): json.loads(path.read_text(encoding='utf-8')) for path in files}
    legacy = [key for key, record in records.items() if 'previous_decision' not in record]
    candidates = {key for key, record in records.items() if 'previous_decision' in record}
    if legacy:
        candidates.add(legacy[-1])
    parents = {r['previous_decision'] for r in records.values() if r.get('previous_decision')}
    parents.update(parent for r in records.values() for parent in r.get('previous_decisions', []))
    if not parents.issubset(records):
        raise ValueError('O histórico de decisões está incompleto. Conserve as revisões e peça reconciliação.')
    leaves = candidates - parents
    if records and not leaves:
        raise ValueError('O histórico de decisões é inválido. Conserve as revisões e peça apoio.')
    seen, pending = set(legacy), list(leaves)
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        seen.add(key)
        record = records[key]
        pending.extend(record.get('previous_decisions', []))
        if record.get('previous_decision'):
            pending.append(record['previous_decision'])
    if seen != set(records):
        raise ValueError('O histórico de decisões contém ramos inválidos. Conserve as revisões e peça apoio.')
    return {key: records[key] for key in sorted(leaves)}


def _latest_decision(output, relative_source):
    branches = decision_branches(output, relative_source)
    if len(branches) > 1:
        raise ValueError('Há decisões humanas concorrentes sobre este documento. '
                         'Conserve as duas versões e reconcilie antes de aprovar ou entregar.')
    head = next(iter(branches), None)
    return head, branches.get(head)


def review_head(output, relative_source):
    return _latest_decision(output, relative_source)[0]


def decide(output: Path, relative_source: str, *, reviewer: str, decision: str,
           scope: str, notes: str = '', expected: dict | None = None,
           expected_decision=_UNSPECIFIED, reconcile_heads=None) -> Path:
    if not reviewer.strip() or decision not in {'aprovado', 'rejeitado'}:
        raise ValueError('Indique o nome de quem reviu e a decisão aprovado/rejeitado.')
    if scope not in {'integral', 'amostra'}:
        raise ValueError('Indique se conferiu o documento integral ou apenas uma amostra.')
    if expected_decision is _UNSPECIFIED and reconcile_heads is None:
        expected_decision = review_head(output, relative_source)
    with exclusive(output / '_auditoria/.operacao.lock'):
        manifest = _load(output)
        matches = [d for d in manifest['documents'] if d['relative_source'] == relative_source]
        if len(matches) != 1:
            raise ValueError('Documento não encontrado de forma única no relatório deste lote.')
        if reconcile_heads is not None:
            branches = decision_branches(output, relative_source)
            if len(branches) < 2 or set(branches) != set(reconcile_heads) or not notes.strip():
                raise ValueError('A reconciliação exige os ramos atuais e notas da nova conferência. '
                                 'Reabra as decisões concorrentes.')
            previous_decision = None
        else:
            previous_decision = review_head(output, relative_source)
        if expected_decision is not _UNSPECIFIED and previous_decision != expected_decision:
            raise ValueError('Outra pessoa já registou uma decisão desde que abriu a conferência. '
                             'Reabra o documento e confira a decisão atual antes de continuar.')
        _, report_path, report = _verified(output, matches[0])
        current = {key: report[key] for key in ('source_sha256', 'markdown_sha256')}
        current['report_sha256'] = _sha256(report_path)
        if expected is not None and current != expected:
            raise ValueError('O documento mudou desde que abriu a revisão. Feche e reabra a conferência; reveja a versão atual.')
        if decision == 'aprovado' and report['quality_status'] == 'blocked':
            raise ValueError('Documento bloqueado: consulte as ocorrências na conferência. '
                             'Use Criar / editar correção e Reauditar correção; '
                             'para regras antigas, use Reauditar lote. A aprovação exige '
                             'uma versão atual sem erros por resolver.')
        if decision == 'aprovado' and report['quality_status'] == 'review' and not notes.strip():
            raise ValueError('Há avisos. Registe o que conferiu e como resolveu cada aviso nas notas.')
        record = {
            'schema_version': 1, 'decision_id': uuid4().hex,
            'reviewer': reviewer.strip(), 'decision': decision, 'scope': scope,
            'notes': notes.strip(), 'date_utc': datetime.now(timezone.utc).isoformat(),
            'relative_source': relative_source, 'run_id': matches[0].get('review_run_id', manifest['run_id']),
            'source_sha256': report['source_sha256'],
            'markdown_sha256': report['markdown_sha256'],
            'report_sha256': _sha256(report_path),
            'previous_decision': previous_decision,
        }
        if reconcile_heads is not None:
            record['previous_decisions'] = sorted(reconcile_heads)
            record['reconciliation'] = True
        folder = output / '_auditoria/revisoes' / _key(relative_source)
        target = folder / (record['date_utc'].replace(':', '-') + '-' + record['decision_id'] + '.json')
        atomic_write(target, json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        return target


def _decision(output: Path, document: dict, report_path: Path):
    _, record = _latest_decision(output, document['relative_source'])
    if not record:
        return None
    current = json.loads(report_path.read_text(encoding='utf-8'))
    if (record.get('markdown_sha256') != current.get('markdown_sha256')
            or record.get('source_sha256') != current.get('source_sha256')
            or record.get('report_sha256') != _sha256(report_path)):
        return None
    return record


def deliver(output: Path, destination: Path) -> Path:
    """Cria entrega nova, completa e imutável; só documentos com revisão integral."""
    with exclusive(output / '_auditoria/.operacao.lock'):
        if destination.exists():
            raise FileExistsError('A pasta de entrega já existe. Escolha um nome novo para conservar a anterior.')
        manifest = _load(output)
        selected, excluded = [], []
        for document in manifest['documents']:
            try:
                target, report_path, report = _verified(output, document)
                decision = _decision(output, document, report_path)
                if (report['quality_status'] == 'blocked' or not decision
                        or decision['decision'] != 'aprovado' or decision['scope'] != 'integral'):
                    raise ValueError('Sem aprovação integral atual ou documento bloqueado.')
                selected.append((document, target, report, decision))
            except (ValueError, KeyError, OSError) as exc:
                excluded.append({'document': document.get('relative_source', '?'), 'reason': str(exc)})
        if not selected:
            raise ValueError('Não há documentos com revisão integral aprovada e hashes atuais para entregar.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix='.crl-entrega-', dir=destination.parent))
        try:
            records = []
            for doc, path, report, decision in selected:
                relative = Path(doc['relative_source']).with_suffix('.md')
                copied = staging / 'documentos' / relative
                copied.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, copied)
                if _sha256(copied) != report['markdown_sha256']:
                    raise ValueError('A extração mudou durante a entrega. Repita a operação.')
                records.append({'document': relative.as_posix(), 'source_sha256': report['source_sha256'],
                                'markdown_sha256': report['markdown_sha256'], 'quality': report,
                                'human_review': decision,
                                'source_run_id': doc.get('review_run_id', manifest['run_id'])})
            data = {'schema_version': 1, 'run_id': manifest['run_id'],
                    'source_runs': manifest.get('review_runs', [manifest['run_id']]),
                    'generated_utc': datetime.now(timezone.utc).isoformat(),
                    'documents': records, 'excluded': excluded,
                    'maxqda_import': 'Não verificada por esta operação; registar ensaio na versão da equipa.'}
            atomic_write(staging / 'conformidade.json', json.dumps(data, ensure_ascii=False, indent=2) + '\n')
            lines = ['# Relatório metodológico de entrega', '',
                     f"Execução de origem: {manifest['run_id']}", '',
                     f'Documentos entregues: {len(records)}. Excluídos: {len(excluded)}.', '',
                     'O PDF é o original. A extração usa Docling e conserva auditoria de completude, '
                     'montantes, símbolos e tabelas. O JSON acompanha hashes, opções, versões, '
                     'ocorrências e decisões humanas efetivamente registadas.', '',
                     'A aprovação integral é uma declaração do revisor identificado; '
                     'a aplicação verifica integridade, não substitui a conferência visual. '
                     'Este relatório não certifica a importação no MAXQDA.', '',
                     '| Documento | Revisor | Data |', '| --- | --- | --- |']
            for r in records:
                review = r['human_review']
                lines.append(f"| {escaped(r['document'])} | {escaped(review['reviewer'])} | {review['date_utc']} |")
            lines += ['', '## Documentos excluídos', '']
            lines += [f"- {escaped(r['document'])}: {escaped(r['reason'])}" for r in excluded] or ['Nenhum.']
            atomic_write(staging / 'conformidade.md', '\n'.join(lines) + '\n')
            # Uma pasta nova impede substituir um corpus já importado/codificado.
            if destination.exists():
                raise FileExistsError('A pasta de entrega foi criada por outra operação; escolha outro nome.')
            staging.rename(destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return destination / 'conformidade.md'
