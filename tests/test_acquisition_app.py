"""Teste funcional Tk; executar com DISPLAY num servidor X real ou virtual."""

import os
import time
import tkinter as tk
from tkinter import ttk

import pytest

from crl_markdown.acquisition_app import AcquisitionPanel
from crl_markdown.recolha import Registo, sha256_ficheiro

from .pdf_sintetico import escrever_pdf


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk requer um servidor gráfico")
def test_gui_preview_approve_and_transfer(tmp_path, monkeypatch):
    original = escrever_pdf(tmp_path / "original.pdf", [[(50, 780, "TESTE")]])
    entry = {"chave": "documento", "ano": 2026, "num_bte": 31,
             "id_dgert": "377/2026", "tipo": "CCT", "familia": "convencao",
             "cod_irct": "27251", "outorgantes": "Associação A - ACRAL; CESP - Sindicato B",
             "descarga": {"estado": "descarregado", "caminho": str(original),
                          "sha256": sha256_ficheiro(original)}}
    reg = Registo(tmp_path / "registo.jsonl", {"documento": entry})
    reg.guardar()
    root = tk.Tk()
    try:
        notebook = ttk.Notebook(root)
        notebook.pack()
        source = tk.StringVar(master=root)
        panel = AcquisitionPanel(notebook, source)
        panel.register.set(str(reg.caminho))
        panel.destination.set(str(tmp_path / "named"))
        monkeypatch.setattr("crl_markdown.acquisition_app.messagebox.askyesno", lambda *a: True)
        monkeypatch.setattr("crl_markdown.acquisition_app.messagebox.showerror",
                            lambda *a: pytest.fail(str(a)))

        def wait():
            deadline = time.monotonic() + 5
            while panel.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(0.01)
            assert not panel.busy

        panel.preview()
        wait()
        assert panel.table.get_children() == ("documento",)
        assert panel.table.item("documento", "values")[1].startswith("2026_BTE_31_")
        panel.table.selection_set("documento")
        panel.apply()
        wait()
        assert panel.table.item("documento", "values")[2] == "nomeado"
        panel.use_destination()
        assert source.get() == str(tmp_path / "named")
        assert original.exists()
    finally:
        root.destroy()
