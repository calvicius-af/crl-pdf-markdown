"""Lançador por duplo clique, com instalação guiada sem comandos no terminal."""

import hashlib
import ntpath
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path, PureWindowsPath
from tkinter import messagebox, ttk

ROOT = Path(__file__).absolute().parent.parent


def windows_environment_directory(project_identity, local_appdata):
    """Isola as dependências de cada projeto num diretório local do utilizador."""
    identity = ntpath.normcase(str(project_identity))
    project_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return PureWindowsPath(local_appdata) / "CRL-PDF-Markdown" / "envs" / project_id


if os.name == "nt":
    local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    ENVIRONMENT = Path(str(windows_environment_directory(ROOT.resolve(), local_appdata)))
else:
    ENVIRONMENT = ROOT / ".venv"
PYTHON = ENVIRONMENT / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def app_environment(root):
    """Não depende da letra temporária guardada pelo pip na instalação editable."""
    environment = os.environ.copy()
    source = str(root / "src")
    previous = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = source + (os.pathsep + previous if previous else "")
    return environment


def project_reference(root):
    """Preserva o servidor UNC na conversão de URI feita pelo pip no Windows."""
    text = str(root)
    if not text.startswith("\\\\"):
        return text
    server, _, rest = text[2:].partition("\\")
    if server.lower() == "localhost":
        server = "127.0.0.1"
    return PureWindowsPath(f"\\\\{server}\\{rest}").as_uri()


def project_install_command(python, root):
    return [str(python), "-m", "pip", "install", "-e", project_reference(root)]


def main():
    root = tk.Tk()
    root.title("Preparar CRL — PDF para Markdown")
    root.geometry("700x420")
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Recolha → revisão dos nomes → Markdown").pack(anchor="w")
    ttk.Label(frame, text=f"Bibliotecas Python: {ENVIRONMENT}", wraplength=650).pack(anchor="w")
    status = tk.StringVar(value="A verificar a instalação…")
    ttk.Label(frame, textvariable=status, wraplength=650).pack(anchor="w", pady=12)
    log = tk.Text(frame, height=12, wrap="word", state="disabled")
    log.pack(fill="both", expand=True)
    events = queue.Queue()
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}

    def open_app():
        executable = PYTHON.with_name("pythonw.exe") if os.name == "nt" else PYTHON
        process = subprocess.Popen([str(executable), "-m", "crl_markdown.app"], cwd=ROOT, env=app_environment(ROOT), **flags)
        root.destroy()
        # O .bat só pode desfazer o pushd depois de a aplicação terminar.
        process.wait()

    def install():
        if not messagebox.askyesno("Instalar dependências", f"Descarregar e instalar as bibliotecas em {ENVIRONMENT}? "
                                  "É necessária ligação à Internet. Os modelos são preparados separadamente."):
            return
        button.configure(state="disabled")
        status.set("A instalar; pode demorar alguns minutos.")

        def worker():
            try:
                if not (ROOT / "pyproject.toml").is_file():
                    raise RuntimeError("Não foi encontrado pyproject.toml. Extrai o ZIP completo "
                                       "e abre scripts/Iniciar.bat dentro dessa pasta.")
                if not PYTHON.exists():
                    execute([sys.executable, "-m", "venv", str(ENVIRONMENT)])
                if sys.platform.startswith("linux"):
                    execute([str(PYTHON), "-m", "pip", "install", "torch", "torchvision",
                             "--index-url", "https://download.pytorch.org/whl/cpu"])
                execute(project_install_command(PYTHON, ROOT))
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
                                    cwd=ROOT, env=app_environment(ROOT), capture_output=True, **flags) if PYTHON.exists() else None
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
