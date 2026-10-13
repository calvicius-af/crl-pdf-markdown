"""Interface local; extração em thread e atualizações Tk apenas na thread principal."""

import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .pipeline import Options, run


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    root = tk.Tk()
    root.title("CRL — PDF para Markdown")
    root.geometry("900x760")
    root.minsize(750, 560)
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    source, output, workspace_path = tk.StringVar(), tk.StringVar(), tk.StringVar()
    ocr, offline, overwrite = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
    models = tk.StringVar()
    if args.models:
        models.set(str(args.models))
    offline.set(args.offline)
    events = queue.Queue()
    ttk.Label(frame, text="Preparar documentos Markdown para importação no MAXQDA").pack(anchor="w")
    def use_workspace():
        from .workspace import initialize
        folder = filedialog.askdirectory(title="Escolha ou crie a pasta RNC_Dados_AAAA")
        if folder:
            workspace = initialize(Path(folder))
            workspace_path.set(str(workspace))
            source.set(str(workspace / "1_fontes/irct/convencoes"))
            output.set(str(workspace / "2_processamento/texto"))
            messagebox.showinfo("Pastas prontas", "A árvore RNC está pronta. Os ficheiros existentes "
                                "foram conservados. Coloque os índices em 1_fontes/indices_bte.")
    ttk.Button(frame, text="Criar / usar pasta RNC…", command=use_workspace).pack(anchor="w", pady=4)
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
    running = threading.Event()

    def close():
        # A conversão corre numa thread que morre com a janela. Os documentos
        # já convertidos ficam, e a próxima corrida sobre a mesma pasta de
        # saída retoma a partir deles; ainda assim, fechar tem de ser pedido.
        if running.is_set() and not messagebox.askyesno(
            "Conversão em curso",
            "A conversão ainda está a decorrer. Fechar agora interrompe-a.\n\n"
            "Os documentos já convertidos ficam guardados, e uma nova corrida "
            "com a mesma pasta de saída continua a partir deles. Fechar?",
        ):
            return
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)

    def open_report():
        if report_path:
            webbrowser.open(report_path.resolve().as_uri())

    def start():
        if running.is_set():
            return
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
        running.set()

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
                from .diagnostics import save_failure
                try:
                    failure = save_failure(exc, args[1] / "_assistencia", "Conversão pela interface")
                    events.put(("log", f"A conversão não terminou. Como resolver: {failure}"))
                    events.put(("report", failure))
                except OSError:
                    from tempfile import gettempdir
                    failure = save_failure(exc, Path(gettempdir()) / "CRL-assistencia", "Conversão")
                    events.put(("log", f"Como resolver: {failure}"))
                    events.put(("report", failure))
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

    def callback_error(error_type, error, tb):
        from tempfile import gettempdir

        from .diagnostics import save_failure
        try:
            path = save_failure(error.with_traceback(tb), Path(gettempdir()) / "CRL-assistencia", "Interface")
            messagebox.showerror("A operação não terminou", f"{error}\n\nComo resolver: {path}")
        except Exception:
            messagebox.showerror("A operação não terminou", str(error))
    root.report_callback_exception = callback_error

    def collect_workspace():
        if running.is_set():
            return
        if not workspace_path.get():
            use_workspace()
        if not workspace_path.get():
            return
        import argparse
        import contextlib
        import io

        from .recolha import add_arguments, collect
        parser = argparse.ArgumentParser()
        add_arguments(parser)
        selected = parser.parse_args(["--workspace", workspace_path.get(), "--confirmar-rede"])
        running.set()
        def work():
            transcript = io.StringIO()
            try:
                with contextlib.redirect_stdout(transcript):
                    result = collect(selected)
                events.put(("log", transcript.getvalue()))
                events.put(("log", "Recolha terminada. Confira as pendências no relatório." if result
                            else "Recolha e nomeação terminadas. Pode construir o Markdown."))
            except Exception as exc:
                from tempfile import gettempdir

                from .diagnostics import save_failure
                try:
                    path = save_failure(exc, Path(gettempdir()) / "CRL-assistencia", "Recolha")
                    events.put(("report", path))
                finally:
                    events.put(("log", f"A recolha não terminou: {exc}\n{transcript.getvalue()}"))
            finally:
                events.put(("done", ""))
        threading.Thread(target=work, daemon=True).start()

    def review_document():
        if running.is_set():
            return
        import json

        from .models import _sha256
        from .validation import decide
        folder = Path(output.get())
        manifest = json.loads((folder / "_auditoria/manifest.json").read_text(encoding="utf-8"))
        documents = manifest["documents"]
        expected = {}
        for document in documents:
            relative = Path(document["relative_source"])
            report = folder / "_auditoria/documentos" / relative.parent / (relative.stem + ".qualidade.json")
            if report.is_file():
                expected[document["relative_source"]] = {
                    "source_sha256": document.get("source_sha256"),
                    "markdown_sha256": document.get("markdown_sha256"),
                    "report_sha256": _sha256(report),
                }
        dialog = tk.Toplevel(root)
        dialog.title("Conferir texto com o PDF original")
        dialog.transient(root)
        dialog.grab_set()
        dialog.geometry("760x530")
        body = ttk.Frame(dialog, padding=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Abra o PDF, o Markdown e o relatório. Confira o texto e todas as tabelas.",
                  wraplength=700).pack(anchor="w")
        selected = tk.StringVar()
        choices = [d["relative_source"] for d in documents]
        ttk.Combobox(body, textvariable=selected, values=choices, state="readonly", width=95).pack(fill="x", pady=8)
        if choices:
            selected.set(choices[0])
        def document():
            return next(d for d in documents if d["relative_source"] == selected.get())
        links = ttk.Frame(body)
        links.pack(fill="x")
        for title, field in (("Abrir PDF original", "source"), ("Abrir Markdown", "output")):
            ttk.Button(links, text=title, command=lambda key=field:
                       webbrowser.open(Path(document()[key]).resolve().as_uri())).pack(side="left")
        ttk.Button(links, text="Abrir evidências", command=lambda:
                   webbrowser.open((folder / "_auditoria/detalhes.md").resolve().as_uri())).pack(side="left")
        reviewer = tk.StringVar()
        ttk.Label(body, text="Nome de quem fez a conferência").pack(anchor="w", pady=(10, 0))
        ttk.Entry(body, textvariable=reviewer).pack(fill="x")
        integral = tk.BooleanVar()
        ttk.Checkbutton(body, text="Conferi integralmente este documento, incluindo tabelas e anexos",
                        variable=integral).pack(anchor="w", pady=8)
        ttk.Label(body, text="O que conferiu / resolução de cada aviso (obrigatório se há avisos)").pack(anchor="w")
        notes = tk.Text(body, height=8, wrap="word")
        notes.pack(fill="both", expand=True)
        def record(decision):
            path = decide(folder, selected.get(), reviewer=reviewer.get(), decision=decision,
                          scope="integral" if integral.get() else "amostra", notes=notes.get("1.0", "end").strip(),
                          expected=expected.get(selected.get(), {}))
            messagebox.showinfo("Conferência registada", f"Decisão guardada: {path}", parent=dialog)
        actions = ttk.Frame(body)
        actions.pack(pady=8)
        ttk.Button(actions, text="Registar aprovação", command=lambda: record("aprovado")).pack(side="left")
        ttk.Button(actions, text="Registar rejeição", command=lambda: record("rejeitado")).pack(side="left")

    def deliver_approved():
        if running.is_set():
            return
        from datetime import datetime

        from .validation import deliver
        parent = filedialog.askdirectory(title="Onde guardar a nova entrega aprovada?")
        if parent:
            destination = Path(parent) / ("entrega_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
            path = deliver(Path(output.get()), destination)
            webbrowser.open(path.resolve().as_uri())
            messagebox.showinfo("Entrega pronta", f"Importe os Markdown da pasta documentos.\n{destination}\n\n"
                                "O relatório de conformidade acompanha a entrega.")

    workflow = ttk.Frame(frame)
    workflow.pack(pady=8)
    ttk.Button(workflow, text="Recolher PDFs (usa internet)", command=collect_workspace).pack(side="left")
    ttk.Button(workflow, text="Conferir / aprovar…", command=review_document).pack(side="left")
    ttk.Button(workflow, text="Entregar aprovados…", command=deliver_approved).pack(side="left")

    def poll():
        nonlocal report_path
        while not events.empty():
            kind, text = events.get_nowait()
            if kind == "report":
                report_path = text
                report_button.configure(state="normal")
            elif kind == "done":
                running.clear()
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
