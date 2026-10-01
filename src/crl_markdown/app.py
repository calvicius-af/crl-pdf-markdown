"""Interface local; extração em thread e atualizações Tk apenas na thread principal."""

import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .pipeline import Options, run


def main():
    root = tk.Tk()
    root.title("CRL — PDF para Markdown")
    root.geometry("780x500")
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    source, output = tk.StringVar(), tk.StringVar()
    ocr, offline, overwrite = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
    models = tk.StringVar()
    events = queue.Queue()
    ttk.Label(frame, text="Preparar documentos Markdown para importação no MAXQDA").pack(anchor="w")
    for label, variable in (
        ("PDF ou pasta de PDFs", source),
        ("Pasta de saída", output),
        ("Pasta de modelos (opcional)", models),
    ):
        ttk.Label(frame, text=label).pack(anchor="w", pady=(8, 0))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)

        def choose_folder(var=variable):
            chosen = filedialog.askdirectory()
            if chosen:
                var.set(chosen)

        ttk.Button(row, text="Pasta…", command=choose_folder).pack(side="left")
        if variable is source:

            def choose_pdf():
                chosen = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
                if chosen:
                    source.set(chosen)

            ttk.Button(row, text="PDF…", command=choose_pdf).pack(side="left")
    flags = ttk.Frame(frame)
    flags.pack(fill="x", pady=8)
    for text, variable in (
        ("OCR (digitalizações)", ocr),
        ("Modelos locais / offline", offline),
        ("Substituir saídas existentes", overwrite),
    ):
        ttk.Checkbutton(flags, text=text, variable=variable).pack(side="left")
    log = tk.Text(frame, height=10, state="disabled", wrap="word")
    log.pack(fill="both", expand=True)

    report_path = None

    def open_report():
        if report_path:
            webbrowser.open(report_path.resolve().as_uri())

    def start():
        if not source.get().strip() or not output.get().strip():
            messagebox.showerror("Campos em falta", "Escolhe a entrada e a pasta de saída.")
            return
        args = (
            Path(source.get()),
            Path(output.get()),
            Options(ocr.get(), Path(models.get()) if models.get() else None, offline.get()),
        )
        replace = overwrite.get()
        previous_manifest = args[1] / "_auditoria" / "manifest.json"
        previous_run = previous_manifest.read_bytes() if previous_manifest.exists() else None
        button.configure(state="disabled")
        report_button.configure(state="disabled")

        def worker():
            try:
                reports = run(
                    *args, overwrite=replace, progress=lambda line: events.put(("log", line))
                )
                failed = sum(r["state"] == "falhou" for r in reports)
                review = sum(r["state"] == "rever" for r in reports)
                blocked = sum(r.get("quality_status") == "blocked" for r in reports)
                events.put(
                    (
                        "log",
                        f"Concluído: {len(reports) - failed} convertidos, "
                        f"{review} para rever ({blocked} bloqueados), {failed} falhas. Ver _auditoria.",
                    )
                )
            except Exception as exc:
                events.put(("log", f"Erro: {exc}"))
            finally:
                path = args[1] / "_auditoria" / "diagnostico.md"
                current_manifest = args[1] / "_auditoria" / "manifest.json"
                if (
                    path.exists()
                    and current_manifest.exists()
                    and current_manifest.read_bytes() != previous_run
                ):
                    events.put(("report", path))
                events.put(("done", ""))

        threading.Thread(target=worker, daemon=True).start()

    button = ttk.Button(frame, text="Construir Markdown", command=start)
    button.pack(pady=(8, 0))
    report_button = ttk.Button(
        frame, text="Abrir relatório do lote", command=open_report, state="disabled"
    )
    report_button.pack(pady=(4, 0))

    def poll():
        nonlocal report_path
        while not events.empty():
            kind, text = events.get_nowait()
            if kind == "report":
                report_path = text
                report_button.configure(state="normal")
            elif kind == "done":
                button.configure(state="normal")
            else:
                log.configure(state="normal")
                log.insert("end", text + "\n")
                log.see("end")
                log.configure(state="disabled")
        root.after(100, poll)

    poll()
    root.mainloop()


if __name__ == "__main__":
    main()
