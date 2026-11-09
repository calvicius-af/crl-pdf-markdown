"""Interface local; extração em thread e atualizações Tk apenas na thread principal."""

import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .pipeline import Options, run


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--installed", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = tk.Tk()
    from . import __version__, settings
    root.title(f"CRL — PDF para Markdown {__version__}")
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
    configured = None
    startup_error = None
    try:
        configured = settings.load()
    except (ValueError, OSError) as error:
        startup_error = error

    def apply_settings(values):
        nonlocal configured
        configured = values
        workspace_path.set(values["workspace"])
        source.set(values["named"])
        output.set(values["markdown"])

    if configured:
        apply_settings(configured)

    def configure():
        if running.is_set():
            return
        values = settings.dialog(root, configured)
        if values:
            apply_settings(values)

    family_labels = {"Convenções (inclui ACEP/ACCE)": "convencao", "Portarias": "extensao",
                     "Adesões": "adesao", "Acórdãos": "acordao", "Cessações de vigência": "cessacao",
                     "Outros avisos": "aviso", "Todos os documentos IRCT": "todos"}
    selected_family = tk.StringVar(value=next(iter(family_labels)))
    def choose_family(_event=None):
        from .workspace import document_source
        if configured:
            from .workspace import DOCUMENT_FOLDERS
            source.set(str(Path(configured["named"]) / DOCUMENT_FOLDERS[family_labels[selected_family.get()]]))
        elif workspace_path.get():
            source.set(str(document_source(workspace_path.get(), family_labels[selected_family.get()])))
    ttk.Label(frame, text="Preparar documentos Markdown para importação no MAXQDA").pack(anchor="w")
    def use_workspace():
        from .workspace import initialize
        folder = filedialog.askdirectory(title="Escolha ou crie a pasta RNC_Dados_AAAA")
        if folder:
            workspace = initialize(Path(folder))
            values = settings.defaults(workspace)
            settings.save(values)
            apply_settings(values)
            workspace_path.set(str(workspace))
            choose_family()
            output.set(str(workspace / "2_processamento/texto"))
            messagebox.showinfo("Pastas prontas", "A árvore RNC está pronta. Os ficheiros existentes "
                                "foram conservados. Coloque os índices em 1_fontes/indices_bte.")
    ttk.Button(frame, text="Configurar pastas…", command=configure).pack(anchor="w", pady=4)
    if args.installed:
        def use_sample():
            source.set(str(args.models.parent / "smoke.pdf"))
        ttk.Button(frame, text="Usar PDF de teste incluído", command=use_sample).pack(anchor="w", pady=4)
    if not args.installed:
        ttk.Button(frame, text="Criar / usar pasta RNC…", command=use_workspace).pack(anchor="w", pady=4)
    ttk.Label(frame, text="Documentos a converter na pasta RNC").pack(anchor="w")
    family_box = ttk.Combobox(frame, textvariable=selected_family, values=list(family_labels), state="readonly")
    family_box.pack(fill="x")
    family_box.bind("<<ComboboxSelected>>", choose_family)
    for label, variable in (
        ("PDF ou pasta de PDFs", source),
        ("Pasta de saída", output),
        ("Pasta de modelos (opcional)", models),
    ):
        if args.installed and variable is models:
            continue
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
        if args.installed and variable is offline:
            continue
        ttk.Checkbutton(flags, text=text, variable=variable).pack(side="left")
    log = tk.Text(frame, height=10, state="disabled", wrap="word")
    log.pack(fill="both", expand=True)

    report_path = None
    last_error = None
    running = threading.Event()
    reaudit_cancel = threading.Event()

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
        reaudit_cancel.set()
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
        if not args[0].exists():
            raise FileNotFoundError("A origem escolhida não está disponível. Confirme a pasta no Explorador.")
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
                if failed:
                    events.put(("log", "Alguns PDFs não puderam ser convertidos. Confira o relatório "
                                "do lote ou use Guardar relatório para o apoio."))
            except Exception as exc:
                events.put(("failure", exc))
                from .diagnostics import save_failure
                try:
                    failure = save_failure(exc, args[1] / "_assistencia", "Conversão pela interface")
                    events.put(("log", f"A conversão não terminou. Como resolver: {failure}"))
                    events.put(("report", failure))
                except OSError:
                    from tempfile import gettempdir
                    try:
                        failure = save_failure(exc, Path(gettempdir()) / "CRL-assistencia", "Conversão")
                        events.put(("report", failure))
                    except OSError:
                        events.put(("log", "Use Guardar relatório para o apoio e escolha uma pasta com escrita."))
            finally:
                try:
                    path = args[1] / "_auditoria" / "diagnostico.md"
                    current_manifest = args[1] / "_auditoria" / "manifest.json"
                    if (path.exists() and current_manifest.exists()
                            and current_manifest.read_bytes() != previous_run):
                        events.put(("report", path))
                except OSError:
                    events.put(("log", "Não foi possível abrir o relatório do lote. "
                                "Use Guardar relatório para o apoio."))
                finally:
                    events.put(("done", ""))

        threading.Thread(target=worker, daemon=True).start()

    button = ttk.Button(frame, text="Construir Markdown", command=start)
    button.pack(pady=(8, 0))
    report_button = ttk.Button(
        frame, text="Abrir relatório do lote", command=open_report, state="disabled"
    )
    report_button.pack(pady=(4, 0))

    def save_support():
        from .diagnostics import export_support
        target = filedialog.asksaveasfilename(title="Guardar relatório para o apoio",
                                             initialfile="CRL-apoio.zip", defaultextension=".zip",
                                             filetypes=[("Relatório de apoio", "*.zip")])
        if not target:
            return
        attachments = [report_path, report_path.with_suffix(".json")] if report_path else []
        audit = Path(output.get()) / "_auditoria"
        attachments += [audit / name for name in ("manifest.json", "progresso.log", "falha_nativa.log")]
        try:
            export_support(target, error=last_error, log=log.get("1.0", "end"), attachments=attachments)
        except OSError:
            messagebox.showerror("Não foi possível guardar", "Escolha outra pasta onde possa guardar ficheiros.")
        else:
            messagebox.showinfo("Relatório guardado", "Entregue o ZIP ao apoio informático.")

    ttk.Button(frame, text="Guardar relatório para o apoio", command=save_support).pack(pady=4)
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill="x", pady=4)
    progress_active = False

    def callback_error(error_type, error, tb):
        nonlocal last_error
        from .diagnostics import support_dialog
        last_error = error.with_traceback(tb)
        support_dialog(root, last_error, "Interface")
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
        if configured:
            selected.indices = configured["indices"]
            selected.destino = configured["originals"]
            selected.named_root = Path(configured["named"])
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
                events.put(("failure", exc))
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

    def organize_workspace():
        if running.is_set():
            return
        if not workspace_path.get():
            use_workspace()
        if not workspace_path.get():
            return
        from collections import Counter

        from .naming import name_records

        workspace = Path(workspace_path.get())
        from .workspace import initialize
        initialize(workspace)
        running.set()
        def work():
            try:
                results = name_records(workspace / "0_gestao/catalogo/registo_bte.jsonl", workspace,
                                       workspace / "0_gestao/vocabularios/siglas.csv",
                                       workspace / "0_gestao/vocabularios/empregadores_ambito.csv",
                                       apply=True, named_root=Path(configured["named"]) if configured else None)
                counts = Counter(row["estado"] for row in results)
                events.put(("log", "Organização local terminada: " + ", ".join(
                    f"{n} {state}" for state, n in sorted(counts.items()))))
                for row in results:
                    if row["estado"] == "por_confirmar":
                        events.put(("log", f"Pendente {row['chave']}: {row['motivo']}"))
                events.put(("log", f"Catálogo: {workspace / '0_gestao/catalogo/nomeacao.csv'}"))
            except (ValueError, OSError) as error:
                events.put(("failure", error))
                events.put(("log", f"A organização não terminou: {error}"))
            finally:
                events.put(("done", ""))
        threading.Thread(target=work, daemon=True).start()

    def review_document():
        if running.is_set():
            return
        from .review_app import ReviewWindow
        try:
            ReviewWindow(root, Path(output.get()))
        except (ValueError, OSError) as error:
            messagebox.showinfo("Ainda não é possível conferir", str(error))

    def reaudit_batch():
        if running.is_set():
            return
        from .reaudit import reaudit
        if not output.get().strip():
            messagebox.showinfo("Pasta de saída", "Selecione a saída de uma conversão existente.")
            return
        current_output = Path(output.get())
        reaudit_cancel.clear()
        running.set()
        def worker():
            try:
                destination, reports = reaudit(current_output, progress=lambda line: events.put(("log", line)),
                                               cancel_event=reaudit_cancel)
                events.put(("output", str(destination)))
                events.put(("report", destination / "_auditoria/diagnostico.md"))
                events.put(("log", f"Reauditoria terminada: {len(reports)} documentos. Nova saída: {destination}"))
            except (ValueError, OSError, RuntimeError) as error:
                events.put(("failure", error))
                events.put(("log", f"Reauditoria não concluída: {error}"))
            finally:
                events.put(("done", ""))
        threading.Thread(target=worker, daemon=True).start()

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
    ttk.Button(workflow, text="Organizar PDFs (sem rede)", command=organize_workspace).pack(side="left")
    ttk.Button(workflow, text="Conferir / aprovar…", command=review_document).pack(side="left")
    ttk.Button(workflow, text="Entregar aprovados…", command=deliver_approved).pack(side="left")

    ttk.Button(frame, text="Reauditar lote (sem nova extração)", command=reaudit_batch).pack(pady=4)

    def poll():
        nonlocal report_path, last_error, progress_active
        while not events.empty():
            kind, text = events.get_nowait()
            if kind == "output":
                output.set(text)
            elif kind == "report":
                report_path = text
                report_button.configure(state="normal")
            elif kind == "done":
                running.clear()
                button.configure(state="normal")
            elif kind == "failure":
                from .diagnostics import support_dialog
                last_error = text
                support_dialog(root, text, "Operação pela interface")
            else:
                log.configure(state="normal")
                log.insert("end", text + "\n")
                log.see("end")
                log.configure(state="disabled")
        if running.is_set() and not progress_active:
            progress.start(15)
            progress_active = True
        elif not running.is_set() and progress_active:
            progress.stop()
            progress_active = False
        root.after(100, poll)

    poll()
    def first_start():
        if startup_error:
            from .diagnostics import support_dialog
            support_dialog(root, startup_error, "Ler configuração das pastas")
        if not configured:
            configure()
    root.after(0, first_start)
    root.mainloop()


if __name__ == "__main__":
    main()
