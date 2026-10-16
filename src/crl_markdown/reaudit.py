"""Nova corrida a partir de extrações verificadas, sem carregar modelos Docling."""

import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .cache import CachedConverter
from .pipeline import Options, convert_pdf, run


def _cached_entry(record, cache_directory, destination, options):
    relative = Path(record['relative_source']).with_suffix('.md')
    converter = CachedConverter(cache_directory, records=[record])
    return convert_pdf(Path(record['source']), destination / relative, converter, options,
                       audit_dir=destination / '_auditoria/documentos' / relative.parent)


class _ParallelReports:
    def __init__(self, records, cache, destination, options, workers):
        self.records = [{k: r[k] for k in ('source', 'relative_source')} for r in records]
        self.cache, self.destination, self.options, self.workers = cache, destination, options, workers
        self.executor = None
        self.futures = {}

    def __call__(self, pdf, _target, _audit):
        if self.executor is None:
            self.executor = ProcessPoolExecutor(max_workers=self.workers,
                                                mp_context=multiprocessing.get_context('spawn'))
            for record in self.records:
                self.futures[str(Path(record['source']).resolve())] = self.executor.submit(
                    _cached_entry, record, self.cache, self.destination, self.options)
        future = self.futures.pop(str(pdf.resolve()))
        return future.result()

    def close(self):
        if self.executor:
            self.executor.shutdown(wait=True, cancel_futures=True)


def reaudit(output, destination=None, *, relative_source=None, progress=print, jobs=2):
    if jobs not in {1, 2}:
        raise ValueError('A reauditoria suporta 1 ou 2 processos locais.')
    output = Path(output).resolve()
    manifest = json.loads((output / '_auditoria/manifest.json').read_text(encoding='utf-8'))
    selected = [d for d in manifest['documents']
                if relative_source is None or d['relative_source'] == relative_source]
    if not selected or any('quality_status' not in d for d in selected):
        raise ValueError('Selecione documentos com uma extração completa para reauditar.')
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
    for doc in selected:
        relative = Path(doc['relative_source'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Caminho relativo inválido no manifesto.')
        entries.append((Path(doc['source']), relative.with_suffix('.md')))
    source = Path(manifest.get('source') or selected[0]['source'])
    cache = CachedConverter(output / '_auditoria/documentos', records=selected)
    if jobs == 1 or len(entries) == 1:
        reports = run(source, destination, options, converter=cache, progress=progress,
                      entries_override=entries)
    else:
        provider = _ParallelReports(selected, output / '_auditoria/documentos', destination, options, jobs)
        try:
            reports = run(source, destination, options, report_provider=provider,
                          progress=progress, entries_override=entries)
        finally:
            provider.close()
    return destination, reports
