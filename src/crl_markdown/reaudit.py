"""Nova corrida a partir de extrações verificadas, sem carregar modelos Docling."""

import hashlib
import json
import multiprocessing
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from datetime import datetime, timezone
from pathlib import Path

from .cache import CachedConverter
from .pipeline import Options, convert_pdf, run


def plan_reaudit(output, *, relative_source=None, families=(), rules=(), statuses=(), include_history=False):
    """Selecionar pelo retrato da corrida anterior, sem abrir PDFs nem modelos."""
    from .review_exchange import ensure_complete_imports
    ensure_complete_imports(output)
    manifest_path = Path(output).resolve() / '_auditoria/manifest.json'
    content = manifest_path.read_bytes()
    manifest = json.loads(content)
    if include_history:
        from .validation import _load
        manifest = _load(Path(output))
    documents = manifest['documents']
    families, rules, statuses = (sorted(set(values)) for values in (families, rules, statuses))

    def family(document):
        parts = Path(document['relative_source']).parts
        return parts[0] if len(parts) > 1 else '.'

    available = {
        'família': ({family(d) for d in documents}, families),
        'regra': ({f['rule'] for d in documents for f in d.get('findings', [])}, rules),
        'estado': ({'passed', 'review', 'blocked'}, statuses),
    }
    for label, (known, requested) in available.items():
        unknown = set(requested) - known
        if unknown:
            raise ValueError(f'Filtro de {label} desconhecido: {", ".join(sorted(unknown))}. '
                             f'Valores disponíveis: {", ".join(sorted(known)) or "nenhum"}.')
    selected = [d for d in documents
                if (relative_source is None or d['relative_source'] == relative_source)
                and (not families or family(d) in families)
                and (not rules or any(f['rule'] in rules for f in d.get('findings', [])))
                and (not statuses or d.get('quality_status') in statuses)]
    if not selected:
        raise ValueError('Nenhum documento corresponde aos filtros de reauditoria.')
    if any('quality_status' not in d for d in selected):
        raise ValueError('Selecione documentos com uma extração completa para reauditar.')
    for document in selected:
        relative = Path(document['relative_source'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Caminho relativo inválido no manifesto.')
    provenance = {
        'operation': 'reaudit',
        'manifest': str(manifest_path),
        'manifest_sha256': hashlib.sha256(content).hexdigest(),
        'run_id': manifest['run_id'],
        'filters': {'document': relative_source, 'families': families,
                    'rules': rules, 'statuses': statuses},
        'selection_basis': 'review_inventory' if include_history else 'previous_run',
        'review_runs': manifest.get('review_runs', [manifest['run_id']]),
        'review_inventory_sha256': hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        'total_documents': len(documents),
        'selected_documents': [d['relative_source'] for d in selected],
    }
    return manifest, selected, provenance


def _cached_entry(record, cache_directory, destination, options):
    relative = Path(record['relative_source']).with_suffix('.md')
    converter = CachedConverter(cache_directory, records=[record])
    return convert_pdf(Path(record['source']), destination / relative, converter, options,
                       audit_dir=destination / '_auditoria/documentos' / relative.parent, logical_name=relative.stem)


class _ParallelReports:
    def __init__(self, records, cache, destination, options, workers, cancel_event=None):
        self.records = [{k: r.get(k) for k in ('source', 'relative_source', 'source_sha256',
                                             'docling_document_sha256')} for r in records]
        self.cache, self.destination, self.options, self.workers = cache, destination, options, workers
        self.executor = None
        self.futures = {}
        self.cancel_event = cancel_event

    def __call__(self, pdf, _target, _audit):
        if self.executor is None:
            self.executor = ProcessPoolExecutor(max_workers=self.workers,
                                                mp_context=multiprocessing.get_context('spawn'))
            for record in self.records:
                self.futures[str(Path(record['source']).resolve())] = self.executor.submit(
                    _cached_entry, record, self.cache, self.destination, self.options)
        future = self.futures.pop(str(pdf.resolve()))
        while True:
            if self.cancel_event is not None and self.cancel_event.is_set():
                raise _ReauditCancelled()
            try:
                return future.result(timeout=.2)
            except TimeoutError:
                continue

    def close(self, cancelled=False):
        if self.executor:
            if cancelled:
                if hasattr(self.executor, 'terminate_workers'):
                    self.executor.terminate_workers()
                else:
                    # Compatibilidade Python 3.11–3.13: só processos que
                    # pertencem a este executor; nunca procurar/terminar por nome.
                    for process in list((self.executor._processes or {}).values()):
                        process.terminate()
            self.executor.shutdown(wait=True, cancel_futures=True)


class _ReauditCancelled(KeyboardInterrupt):
    pass


def reaudit(output, destination=None, *, relative_source=None, families=(), rules=(), statuses=(),
            progress=print, jobs=2, cancel_event=None, include_history=False):
    if jobs not in {1, 2}:
        raise ValueError('A reauditoria suporta 1 ou 2 processos locais.')
    output = Path(output).resolve()
    manifest, selected, provenance = plan_reaudit(
        output, relative_source=relative_source, families=families, rules=rules, statuses=statuses,
        include_history=include_history)
    if destination is None:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        destination = output.with_name(output.name + '_reauditoria_' + stamp)
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('A reauditoria exige uma pasta nova; a corrida original é conservada.')
    options = manifest.get('options', {})
    options = Options(ocr=bool(options.get('ocr')), offline=bool(options.get('offline')),
                      models=Path(options['models']) if options.get('models') else None,
                      timeout=options.get('timeout', 900))
    entries = []
    from .review_sources import resolve_source
    def local_source(document):
        try:
            return resolve_source(output, document)
        except ValueError:
            # O conversor verifica os hashes contra o manifesto e regista a
            # falha deste documento; os outros documentos continuam a corrida.
            return Path(document['source'])
    selected = [{**doc, 'source': str(local_source(doc))} for doc in selected]
    # A nova auditoria mantém o histórico de ocorrências, mas não promove
    # decisões antigas nem ativa correções que não foram reauditadas.
    from .locking import exclusive
    from .occurrences import _capture_legacy
    from .validation import _key
    with exclusive(output / '_auditoria/.operacao.lock'):
        for document in selected:
            relative = document['relative_source']
            key = _key(relative)
            folder = output / '_auditoria/ocorrencias' / key
            if folder.exists():
                shutil.copytree(folder, destination / '_auditoria/ocorrencias' / key)
            _capture_legacy(output, relative, destination=destination)
            for area in ('revisoes', 'notas', 'correcoes'):
                folder = output / '_auditoria' / area / key
                if folder.exists():
                    shutil.copytree(folder, destination / '_auditoria/historico-anterior' / key / area)
    for doc in selected:
        relative = Path(doc['relative_source'])
        entries.append((Path(doc['source']), relative.with_suffix('.md')))
    source = Path(manifest.get('source') or selected[0]['source'])
    if not source.exists():
        try:
            source = Path(os.path.commonpath([str(Path(d['source']).parent) for d in selected]))
        except ValueError:
            source = Path(selected[0]['source'])
    shown = progress
    def progress(line):
        if line.startswith('[') and cancel_event is not None and cancel_event.is_set():
            raise _ReauditCancelled()
        shown(line)
    cache = CachedConverter(output / '_auditoria/documentos', records=selected)
    if jobs == 1 or len(entries) == 1:
        try:
            reports = run(source, destination, options, converter=cache, progress=progress,
                          entries_override=entries, relative_sources=[d['relative_source'] for d in selected],
                          provenance=provenance)
        except _ReauditCancelled as error:
            raise RuntimeError('Reauditoria cancelada; a corrida parcial e os originais foram conservados.') from error
    else:
        provider = _ParallelReports(selected, output / '_auditoria/documentos', destination, options, jobs, cancel_event)
        interrupted = False
        try:
            reports = run(source, destination, options, report_provider=provider,
                          progress=progress, entries_override=entries,
                          relative_sources=[d['relative_source'] for d in selected], provenance=provenance)
        except _ReauditCancelled as error:
            interrupted = True
            raise RuntimeError('Reauditoria cancelada; a corrida parcial e os originais foram conservados.') from error
        except BaseException:
            interrupted = True
            raise
        finally:
            provider.close(cancelled=interrupted)
    return destination, reports
