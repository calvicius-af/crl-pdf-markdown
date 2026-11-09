"""Configuração por utilizador, fora da instalação e sem resolver unidades mapeadas."""

import json
import os
import tempfile
from pathlib import Path

PATH_LABELS = {
    "workspace": "Pasta de trabalho RNC (catálogo e vocabulários)",
    "indices": "Índices Excel",
    "originals": "PDFs originais",
    "named": "PDFs nomeados",
    "markdown": "Markdown e auditoria",
}


def user_folder():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "CRL-PDF-Markdown"


def defaults(root=None):
    root = Path(root) if root else Path.home() / "Documents" / "CRL"
    return {"workspace": str(root), "indices": str(root / "1_fontes/indices_bte"),
            "originals": str(root / "2_processamento/recolha_original"),
            "named": str(root / "1_fontes/irct"),
            "markdown": str(root / "2_processamento/texto")}


def validate(values):
    if not isinstance(values, dict) or set(values) != set(PATH_LABELS):
        raise ValueError("Escolha as cinco pastas da configuração inicial.")
    for key, value in values.items():
        if not isinstance(value, str) or not value.strip() or not Path(value).is_absolute():
            raise ValueError(f"Escolha um caminho completo para {PATH_LABELS[key]}.")
    paths = [Path(value) for value in values.values()]
    if len(set(paths)) != len(paths):
        raise ValueError("Escolha pastas diferentes para cada tipo de ficheiro.")
    # Nunca permitir que a aplicação guarde dados dentro do programa instalado.
    import sys
    protected = (Path(__file__).resolve().parent, Path(sys.base_prefix).resolve())
    for path in paths:
        if any(path.resolve().is_relative_to(parent) for parent in protected):
            raise ValueError("Guarde os dados fora da pasta do programa, por exemplo em Documentos.")
    return dict(values)


def load(path=None):
    path = path or user_folder() / "pastas.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("A configuração guardada não é reconhecida. Volte a escolher as pastas.")
    return validate(data.get("paths"))


def save(values, path=None):
    values = validate(values)
    path = path or user_folder() / "pastas.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Uma unidade L: indisponível não apaga uma configuração válida. Os acessos
    # são verificados ao usar a pasta; a origem pode ser apenas de leitura.
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(json.dumps({"schema": 1, "paths": values}, ensure_ascii=False,
                                    indent=2).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def dialog(parent, initial=None):
    """Cancelar conserva a configuração anterior; guardar só publica no fim."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    window = tk.Toplevel(parent)
    window.title("Configuração inicial — pastas do CRL")
    window.transient(parent)
    window.grab_set()
    frame = ttk.Frame(window, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Escolha onde estão os dados. Pode usar pastas em L:.\n"
              "O programa e os modelos já estão incluídos na instalação.").pack(anchor="w")
    variables = {key: tk.StringVar(value=value) for key, value in (initial or defaults()).items()}
    result = None
    for key, label in PATH_LABELS.items():
        ttk.Label(frame, text=label).pack(anchor="w", pady=(10, 0))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=variables[key], width=70).pack(side="left", fill="x", expand=True)

        def choose(key=key):
            folder = filedialog.askdirectory(parent=window, title=PATH_LABELS[key])
            if folder:
                variables[key].set(folder)

        ttk.Button(row, text="Escolher…", command=choose).pack(side="left")

    def accept():
        nonlocal result
        try:
            values = {key: var.get().strip() for key, var in variables.items()}
            save(values)
        except (ValueError, OSError) as error:
            messagebox.showerror("Não foi possível guardar as pastas", str(error), parent=window)
            return
        result = values
        window.destroy()

    ttk.Button(frame, text="Guardar e continuar", command=accept).pack(side="right", pady=16)
    ttk.Button(frame, text="Cancelar", command=window.destroy).pack(side="right", padx=8, pady=16)
    parent.wait_window(window)
    return result
