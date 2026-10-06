"""Lançador por duplo clique, com instalação guiada sem comandos no terminal."""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main():
    root = tk.Tk()
    root.title("Preparar CRL — PDF para Markdown")
    root.geometry("700x420")
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Recolha → revisão dos nomes → Markdown").pack(anchor="w")
    status = tk.StringVar(value="A verificar a instalação…")
    ttk.Label(frame, textvariable=status, wraplength=650).pack(anchor="w", pady=12)
    log = tk.Text(frame, height=12, wrap="word", state="disabled")
    log.pack(fill="both", expand=True)
    events = queue.Queue()
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}

    def open_app():
        executable = PYTHON.with_name("pythonw.exe") if os.name == "nt" else PYTHON
        subprocess.Popen([str(executable), "-m", "crl_markdown.app"], cwd=ROOT, **flags)
        root.destroy()

    def install():
        if not messagebox.askyesno("Instalar dependências", "Descarregar e instalar as bibliotecas nesta pasta? "
                                  "É necessária ligação à Internet. Os modelos são preparados separadamente."):
            return
        button.configure(state="disabled")
        status.set("A instalar; pode demorar alguns minutos.")

        def worker():
            try:
                if not PYTHON.exists():
                    execute([sys.executable, "-m", "venv", str(ROOT / ".venv")])
                if sys.platform.startswith("linux"):
                    execute([str(PYTHON), "-m", "pip", "install", "torch", "torchvision",
                             "--index-url", "https://download.pytorch.org/whl/cpu"])
                execute([str(PYTHON), "-m", "pip", "install", "-e", str(ROOT)])
                events.put(("ready", ""))
            except Exception as exc:
                events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def execute(command):
        with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, **flags) as process:
            for line in process.stdout:
                events.put(("log", line))
            if process.wait():
                raise RuntimeError("A instalação falhou. Consulta o detalhe acima.")

    button = ttk.Button(frame, text="Instalar e abrir", command=install, state="disabled")
    button.pack(pady=8)

    def check():
        try:
            result = subprocess.run([str(PYTHON), "-c",
                                     "import crl_markdown, docling, openpyxl, tkinter"],
                                    cwd=ROOT, capture_output=True, **flags) if PYTHON.exists() else None
            events.put(("ready" if result and result.returncode == 0 else "missing", ""))
        except OSError as exc:
            events.put(("error", str(exc)))

    def poll():
        while not events.empty():
            kind, text = events.get_nowait()
            if kind == "ready":
                open_app()
                return
            if kind in {"missing", "error"}:
                status.set(text or "É necessário preparar as bibliotecas Python nesta pasta.")
                button.configure(state="normal")
            else:
                log.configure(state="normal")
                log.insert("end", text)
                log.see("end")
                log.configure(state="disabled")
        root.after(100, poll)

    threading.Thread(target=check, daemon=True).start()
    poll()
    root.mainloop()


if __name__ == "__main__":
    main()
