"""Conversores de ensaio para o processo de conversão isolado (`isolamento.py`).

Vivem num módulo, e não dentro dos testes, porque o processo de trabalho é
criado com «spawn» e só recebe funções que consiga importar pelo nome. O
comportamento escolhe-se pelo ambiente, que o processo de trabalho herda:

    CRL_TESTE_FALHA   nome do PDF em que o processo cai com uma falha nativa
    CRL_TESTE_MARCA   pasta: com ela, cai só na primeira vez em cada PDF
    CRL_TESTE_PIDS    pasta onde cada conversão deixa o PID do processo
"""

import faulthandler
import os
from pathlib import Path
from types import SimpleNamespace


def _documento():
    from docling_core.types.doc import DocItemLabel, DoclingDocument

    doc = DoclingDocument(name="Convenção")
    doc.add_text(label=DocItemLabel.TITLE, text="Convenção")
    doc.add_text(label=DocItemLabel.TEXT, text="Cláusula 1.ª — Retribuição de 1 250,00 €.")
    return doc


def conversor(_options):
    def convert(path):
        if os.environ.get("CRL_TESTE_PIDS"):
            (Path(os.environ["CRL_TESTE_PIDS"]) / path.name).write_text(str(os.getpid()))
        if path.name == os.environ.get("CRL_TESTE_FALHA"):
            marca_dir = os.environ.get("CRL_TESTE_MARCA")
            marca = Path(marca_dir) / path.name if marca_dir else None
            if marca is None or not marca.exists():
                if marca is not None:
                    marca.write_text("caiu", encoding="utf-8")
                faulthandler._sigsegv()
        if path.name == "erro.pdf":
            raise ValueError("PDF ilegível neste ensaio")
        return SimpleNamespace(status=SimpleNamespace(value="success"), document=_documento())

    return SimpleNamespace(convert=convert, docling_version="ensaio")


def sem_modelos(_options):
    raise RuntimeError("Modelos indisponíveis")


def cai_ao_arrancar(_options):
    faulthandler._sigsegv()
