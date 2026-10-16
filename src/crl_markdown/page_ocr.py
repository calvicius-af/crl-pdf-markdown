"""OCR dirigido com Docling isolado; as páginas restantes vêm da cache verificada."""

import json
import shutil
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from .cache import CachedConverter
from .locking import exclusive
from .models import _sha256
from .pipeline import Options, atomic_write, make_converter, run


def parse_pages(text, maximum):
    result = set()
    try:
        for part in text.split(','):
            values = [int(v.strip()) for v in part.split('-')]
            if len(values) not in {1, 2}:
                raise ValueError
            first, last = values[0], values[-1]
            if not 1 <= first <= last <= maximum:
                raise ValueError
            result.update(range(first, last + 1))
    except ValueError as error:
        raise ValueError(f'Indique páginas entre 1 e {maximum}, por exemplo 2,5-7.') from error
    return sorted(result)


@dataclass(frozen=True)
class PageOCROptions(Options):
    selected_pages: tuple[int, ...] = ()
    cache_directory: str = ''


class PageOCRConverter:
    def __init__(self, options, native):
        self.options = options
        self.native = native
        self.docling_version = version('docling')
        self.extraction_options = {}

    def convert(self, pdf):
        from docling_core.types.doc import DoclingDocument

        base = CachedConverter(Path(self.options.cache_directory))
        original = base.convert(pdf).document
        pages = sorted(original.pages)
        selected = set(self.options.selected_pages)
        if not selected or not selected.issubset(pages):
            raise ValueError('Selecione páginas existentes no documento.')
        for item, _ in original.iterate_items():
            locations = {p.page_no for p in getattr(item, 'prov', [])}
            if locations & selected and locations - selected:
                raise ValueError('Um elemento atravessa páginas selecionadas e não selecionadas. '
                                 'Inclua todas as páginas desse elemento para conservar a unidade.')
        groups = []
        for page in pages:
            if groups and (page in selected) == (groups[-1][-1] in selected) and page == groups[-1][-1] + 1:
                groups[-1].append(page)
            else:
                groups.append([page])
        documents = []
        for group in groups:
            if group[0] in selected:
                result = self.native.convert(pdf, page_range=(group[0], group[-1]))
                if getattr(result.status, 'value', str(result.status)) != 'success':
                    raise RuntimeError('OCR incompleto nas páginas selecionadas.')
                document = result.document
                if set(document.pages) != set(group):
                    raise ValueError('A numeração de páginas do OCR não corresponde à fonte.')
                documents.append(document)
            else:
                documents.append(original.filter(page_nrs=set(group)))
        combined = DoclingDocument.concatenate(documents)
        if set(combined.pages) != set(pages):
            raise ValueError('O OCR dirigido alterou o inventário de páginas.')
        # A concatenação pode reatribuir refs; conferir conteúdo e geometria
        # das páginas reutilizadas sem depender desses identificadores internos.
        def untouched(doc):
            records = []
            for item, _ in doc.iterate_items():
                prov = getattr(item, 'prov', [])
                if prov and all(p.page_no not in selected for p in prov):
                    records.append((item.label.value, getattr(item, 'text', ''),
                                    getattr(item, 'data', None), [p.model_dump() for p in prov]))
            return records
        if untouched(original) != untouched(combined):
            raise ValueError('As páginas não selecionadas mudaram durante a composição do OCR.')
        self.extraction_options = {**asdict(self.options), 'models': str(self.options.models),
            'operation': 'ocr_paginas', 'selected_pages': sorted(selected),
            'reused_pages': sorted(set(pages) - selected), 'parent_options': base.extraction_options}
        return SimpleNamespace(status='success', document=combined)


def make_page_ocr_converter(options):
    native = make_converter(Options(ocr=True, models=options.models, offline=options.offline,
                                    timeout=options.timeout))
    return PageOCRConverter(options, native)


def reextract_pages(output, relative_source, reviewer, models, pages, *, progress=print):
    from .report import write_reports
    from .revisions import _identity, _record, create_revision, current_pointer
    from .validation import _verified

    if not pages or any(isinstance(p, bool) or not isinstance(p, int) or p < 1 for p in pages):
        raise ValueError('Indique números de página positivos.')
    revision = create_revision(output, relative_source, reviewer)
    output = Path(output).resolve()
    meta = json.loads((revision / 'revision.json').read_text(encoding='utf-8'))
    with exclusive(output / '_auditoria/.operacao.lock'):
        document = _record(output, relative_source)
        target, report_path, report = _verified(output, document)
        if _identity(target, report_path, report) != meta['parent']:
            raise ValueError('A versão mudou. Repita o OCR a partir da versão atual.')
        if report.get('revision'):
            raise ValueError('Há uma correção humana ativa. Reaplicar OCR exige preservar e reconciliar '
                             'essa edição; use uma nova reauditoria do original para este ensaio.')
        publication = revision / 'publicacoes' / uuid4().hex
        options = PageOCROptions(ocr=True, models=Path(models), offline=True,
                                 selected_pages=tuple(sorted(set(pages))), cache_directory=str(revision / 'cache'))
        relative_md = Path(relative_source).with_suffix('.md')
        reports = run(Path(document['source']), publication, options,
                      converter_factory=make_page_ocr_converter, progress=progress,
                      entries_override=[(Path(document['source']), relative_md)])
        updated = reports[0]
        if updated.get('state') == 'falhou':
            raise RuntimeError(updated['error'])
        cache = revision / 'cache_ocr'
        cache.mkdir()
        audit = publication / '_auditoria/documentos' / relative_md.parent
        meta['extraction_cache'] = 'cache_ocr'
        meta['ocr_pages'] = list(options.selected_pages)
        meta['generated_headings'] = updated['generated_headings']
        atomic_write(revision / 'revision.json', json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
        shutil.copy2(publication / relative_md, revision / 'correcao.md')
        updated['revision'] = meta
        updated['draft_sha256'] = _sha256(revision / 'correcao.md')
        saved_report = audit / (relative_md.stem + '.qualidade.json')
        atomic_write(saved_report, json.dumps(updated, ensure_ascii=False, indent=2) + '\n')
        for suffix in ('.docling.json', '.docling.md', '.qualidade.json'):
            shutil.copy2(audit / (relative_md.stem + suffix), cache / (relative_md.stem + suffix))
        manifest = json.loads((publication / '_auditoria/manifest.json').read_text(encoding='utf-8'))
        manifest['documents'] = [updated]
        write_reports(manifest, publication, atomic_write)
        pointer = {'revision_id': revision.name, 'publication': str(publication.relative_to(output)),
                   'quality_status': updated['quality_status'],
                   'identity': _identity(publication / relative_md, saved_report, updated)}
        atomic_write(current_pointer(output, relative_source), json.dumps(pointer, ensure_ascii=False, indent=2) + '\n')
        return publication, updated
