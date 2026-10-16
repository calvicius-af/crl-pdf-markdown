"""Reaplicar as regras a uma extração Docling auditada, verificando o PDF de origem."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace


class CachedConverter:
    def __init__(self, directory: Path, expected_options=None, records=None):
        self.expected_options = expected_options
        self.documents = {}
        self.sources = {}
        if records is not None:
            for record in records:
                relative = Path(record['relative_source']).with_suffix('.docling.json')
                path = directory / relative
                if relative.is_absolute() or '..' in relative.parts or not path.is_file():
                    raise ValueError(f'Extração verificada não encontrada para {record["relative_source"]}.')
                identity = str(Path(record['source']).resolve())
                if identity in self.sources and self.sources[identity] != path:
                    raise ValueError(f'Cache ambígua para a mesma fonte: {identity}.')
                self.sources[identity] = path
        for path in directory.rglob("*.docling.json") if records is None else []:
            name = path.name.removesuffix(".docling.json")
            if name in self.documents:
                raise ValueError(f"Cache ambígua para {name}.")
            self.documents[name] = path
        self.docling_version = "unknown"
        self.extraction_options = {}

    def convert(self, pdf: Path):
        from docling_core.types.doc import DoclingDocument

        path = self.sources.get(str(pdf.resolve())) or self.documents.get(pdf.stem)
        if path is None:
            raise ValueError(f"Extração Docling em cache não encontrada: {pdf.name}")
        metadata = json.loads(path.with_name(pdf.stem + ".qualidade.json").read_text("utf-8"))
        if self.expected_options is not None:
            stored = metadata.get('options', {})
            if (bool(stored.get('ocr')) != self.expected_options.ocr
                    or stored.get('models') != (str(self.expected_options.models) if self.expected_options.models else None)):
                raise ValueError('A cache usa opções OCR/modelos diferentes. Faça uma nova extração.')
        if metadata["source_sha256"] != hashlib.sha256(pdf.read_bytes()).hexdigest():
            raise ValueError(f"O PDF não corresponde ao hash da extração em cache: {pdf.name}")
        expected = metadata.get("docling_document_sha256")
        if not isinstance(expected, str) or expected != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError(f"Extração Docling em cache alterada: {path.name}")
        self.docling_version = metadata["docling_version"]
        self.extraction_options = metadata["options"]
        return SimpleNamespace(status="success", document=DoclingDocument.load_from_json(path))
