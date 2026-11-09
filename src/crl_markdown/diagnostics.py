"""Explicações autónomas com detalhe técnico conservado para assistência."""

import errno
import json
import os
import platform
import re
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path


def atomic_write(path, text):
    # Independente do conversor: também funciona se uma biblioteca não importar.
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(text.encode("utf-8"))
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def safe_detail(text: str) -> str:
    """Retira credenciais de URLs e segredos explícitos; não recolhe outros dados."""
    text = re.sub(r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[credenciais omitidas]@", text)
    return re.sub(r"(?i)(token|password|api_key|authorization)(\s*[:=]\s*)([^\s,;]+)",
                  r"\1\2[omitido]", text)


def explain(error: BaseException) -> dict:
    detail = safe_detail(str(error))
    lowered = detail.lower()
    if 'documento bloqueado' in lowered:
        code, action = 'CRL-QUALIDADE', (
            'Abra Conferir / aprovar e selecione a ocorrência do documento. '
            'Use Criar / editar correção e Reauditar correção para erros de conteúdo, '
            'ou Reauditar lote para aplicar regras atualizadas. Repetir a mesma '
            'extração não resolve uma regra inadequada. O PDF original é conservado.')
    elif isinstance(error, OSError) and error.errno == errno.ENOSPC:
        code, action = "CRL-ESPACO", (
            "Não há espaço livre suficiente. Peça ao apoio informático para libertar espaço "
            "na pasta de saída ou escolha uma unidade local com espaço e tente novamente."
        )
    elif isinstance(error, PermissionError) or (
            isinstance(error, OSError) and error.errno == errno.EROFS):
        code, action = "CRL-PERMISSOES", (
            "Escolha uma pasta local onde possa guardar ficheiros, por exemplo Documentos. "
            "Feche o ficheiro aberto no Excel ou noutro programa e tente novamente. "
            "Se continuar, entregue este relatório ao apoio informático."
        )
    elif isinstance(error, FileExistsError):
        code, action = "CRL-SAIDA-EXISTENTE", (
            "Escolha uma pasta de saída nova. Se pretende refazer a extração, guarde primeiro "
            "as correções manuais e só depois selecione Substituir saídas existentes."
        )
    elif isinstance(error, (ImportError, ModuleNotFoundError)):
        code, action = "CRL-INSTALACAO", (
            "Abra a aplicação pelo lançador CRL, para usar o ambiente instalado. "
            "Se não abrir, execute novamente o instalador oficial do CRL. "
            "Conserve este relatório se o problema continuar."
        )
    elif any(word in lowered for word in ("model", "hugging", "artifacts", "offline")):
        code, action = "CRL-MODELOS", (
            "Os modelos incluídos na instalação estão em falta ou não puderam ser lidos. "
            "Execute novamente o instalador oficial ou contacte o apoio informático."
        )
    elif isinstance(error, TimeoutError) or any(
            word in lowered for word in ("timeout", "tempo máximo", "timed out")):
        code, action = "CRL-TEMPO", (
            "Experimente converter apenas o PDF indicado. Feche programas pesados. "
            "O apoio informático pode aumentar o tempo máximo sem mudar de extrator."
        )
    elif isinstance(error, FileNotFoundError):
        code, action = "CRL-FICHEIRO", (
            "Use o botão Pasta ou PDF para selecionar uma localização que exista. "
            "Se estiver numa unidade partilhada, confirme que consegue abri-la no Explorador."
        )
    else:
        code, action = "CRL-OPERACAO", (
            "Confira a entrada e a pasta de saída indicadas neste relatório. "
            "Tente novamente com um só documento numa pasta nova. Se continuar, "
            "entregue este relatório ao apoio informático; não precisa de alterar código."
        )
    return {"code": code, "problem": detail, "action": action,
            "error_type": type(error).__name__}


def save_failure(error: BaseException, folder: Path, context: str) -> Path:
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    data = {**explain(error), "context": safe_detail(context), "date_utc": identifier,
            "python": sys.version, "platform": platform.platform(),
            "traceback": safe_detail("".join(traceback.format_exception(error)))}
    target = folder / f"falha-{identifier}.md"
    atomic_write(target.with_suffix(".json"), json.dumps(data, ensure_ascii=False, indent=2))
    atomic_write(target, f"# A operação não terminou\n\nCódigo: {data['code']}\n\n"
                 f"Operação: {context}\n\n## O que aconteceu\n\n{data['problem']}\n\n"
                 f"## O que fazer agora\n\n{data['action']}\n\n"
                 "## Se continuar\n\nEntregue este relatório e o JSON com o mesmo nome ao apoio informático.\n\n"
                 "## Para o apoio informático\n\n"
                 f"O ficheiro JSON com o mesmo nome conserva o erro técnico e o ambiente.\n"
                 f"Python: {sys.executable}\n")
    return target


def export_support(target, *, error=None, context="Interface", log="", attachments=()):
    """Um ZIP explícito, sem PDFs nem recolha recursiva dos dados da colega."""
    import zipfile

    from . import __version__
    data = {"version": __version__, "platform": platform.platform(), "python": sys.version,
            "context": safe_detail(context)}
    if error is not None:
        data.update(explain(error))
        data["traceback"] = safe_detail("".join(traceback.format_exception(error)))
    target = Path(target)
    # Produzir primeiro num temporário conserva o relatório anterior se falhar.
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("apoio.json", json.dumps(data, ensure_ascii=False, indent=2))
            archive.writestr("operacao.txt", safe_detail(log))
            for index, attachment in enumerate(attachments):
                path = Path(attachment)
                if path.is_file() and path.suffix in {".json", ".md", ".txt", ".jsonl", ".log"}:
                    archive.writestr(f"relatorios/{index}-{path.name}",
                                     safe_detail(path.read_text(encoding="utf-8", errors="replace")))
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def support_dialog(parent, error, context):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    info = explain(error)
    window = tk.Toplevel(parent)
    window.title("A operação não terminou")
    window.transient(parent)
    window.grab_set()
    frame = ttk.Frame(window, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=f"A operação não terminou ({info['code']}).\n\n{info['action']}",
              wraplength=540).pack(anchor="w")

    def save():
        target = filedialog.asksaveasfilename(parent=window, title="Guardar relatório para o apoio",
                                             defaultextension=".zip", initialfile="CRL-apoio.zip",
                                             filetypes=[("Relatório de apoio", "*.zip")])
        if target:
            try:
                export_support(target, error=error, context=context)
            except OSError:
                messagebox.showerror("Não foi possível guardar", "Escolha outra pasta onde tenha "
                                     "permissão para guardar ficheiros.", parent=window)
            else:
                messagebox.showinfo("Relatório guardado", "Entregue o ZIP ao apoio informático.", parent=window)

    ttk.Button(frame, text="Guardar relatório para o apoio", command=save).pack(pady=16)
    ttk.Button(frame, text="Fechar", command=window.destroy).pack()
    parent.wait_window(window)
