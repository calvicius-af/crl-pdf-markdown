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


def _load(output: Path):
    try:
        manifest = json.loads((output / '_auditoria/manifest.json').read_text(encoding='utf-8'))
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
    report = previous_report(Path(document['source']), target, audit)
    if report is None:
        raise ValueError(f'{relative}: o PDF ou a extração mudou ou está incompleto. Volte a converter e rever.')
    if report.get('markdown_sha256') != document.get('markdown_sha256'):
        raise ValueError(f'{relative}: o relatório do lote está desatualizado. Volte a executar a conversão.')
    return target, report_path, report


def decide(output: Path, relative_source: str, *, reviewer: str, decision: str,
           scope: str, notes: str = '', expected: dict | None = None) -> Path:
    if not reviewer.strip() or decision not in {'aprovado', 'rejeitado'}:
        raise ValueError('Indique o nome de quem reviu e a decisão aprovado/rejeitado.')
    if scope not in {'integral', 'amostra'}:
        raise ValueError('Indique se conferiu o documento integral ou apenas uma amostra.')
    with exclusive(output / '_auditoria/.operacao.lock'):
        manifest = _load(output)
        matches = [d for d in manifest['documents'] if d['relative_source'] == relative_source]
        if len(matches) != 1:
            raise ValueError('Documento não encontrado de forma única no relatório deste lote.')
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
            'relative_source': relative_source, 'run_id': manifest['run_id'],
            'source_sha256': report['source_sha256'],
            'markdown_sha256': report['markdown_sha256'],
            'report_sha256': _sha256(report_path),
        }
        folder = output / '_auditoria/revisoes' / _key(relative_source)
        target = folder / (record['date_utc'].replace(':', '-') + '-' + record['decision_id'] + '.json')
        atomic_write(target, json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        return target


def _decision(output: Path, document: dict, report_path: Path):
    folder = output / '_auditoria/revisoes' / _key(document['relative_source'])
    files = sorted(folder.glob('*.json'))
    if not files:
        return None
    record = json.loads(files[-1].read_text(encoding='utf-8'))
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
                                'human_review': decision})
            data = {'schema_version': 1, 'run_id': manifest['run_id'],
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
