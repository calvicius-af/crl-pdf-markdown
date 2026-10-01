"""Reaplicar as regras a uma extração Docling auditada, verificando o PDF de origem."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace


class CachedConverter:
    def __init__(self, directory: Path):
        self.documents = {}
        for path in directory.rglob("*.docling.json"):
            name = path.name.removesuffix(".docling.json")
            if name in self.documents:
                raise ValueError(f"Cache ambígua para {name}.")
            self.documents[name] = path
        self.docling_version = "unknown"
        self.extraction_options = {}

    def convert(self, pdf: Path):
        from docling_core.types.doc import DoclingDocument

        if pdf.stem not in self.documents:
            raise ValueError(f"Extração Docling em cache não encontrada: {pdf.name}")
        path = self.documents[pdf.stem]
        metadata = json.loads(path.with_name(pdf.stem + ".qualidade.json").read_text("utf-8"))
        if metadata["source_sha256"] != hashlib.sha256(pdf.read_bytes()).hexdigest():
            raise ValueError(f"O PDF não corresponde ao hash da extração em cache: {pdf.name}")
        expected = metadata.get("docling_document_sha256")
        if expected and expected != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError(f"Extração Docling em cache alterada: {path.name}")
        self.docling_version = metadata["docling_version"]
        self.extraction_options = metadata["options"]
        return SimpleNamespace(status="success", document=DoclingDocument.load_from_json(path))
