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
    from .progress import OperationProgress, ProgressReporter, duration
    root.title(f"CRL — PDF para Markdown {__version__}")
    root.geometry(f"900x{max(600, min(760, root.winfo_screenheight() - 120))}")
    root.minsize(750, 600)
    frame = ttk.Frame(root, padding=12)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1, minsize=100)
    toolbar = ttk.Frame(frame)
    toolbar.grid(row=1, column=0, sticky="ew", pady=(4, 8))
    notebook = ttk.Notebook(frame)
    notebook.grid(row=2, column=0, sticky="ew", pady=(0, 8))
    conversion_panel = ttk.Frame(notebook, padding=8)
    tools_panel = ttk.Frame(notebook, padding=8)
    notebook.add(conversion_panel, text="Converter PDFs")
    notebook.add(tools_panel, text="Preparar e conferir")
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
        try:
            previous_review = settings.last_review(configured['workspace'])
            if previous_review:
                output.set(previous_review)
        except (ValueError, OSError) as error:
            startup_error = error

    def configure():
        if running.is_set():
            return
        values = settings.dialog(root, configured)
        if values:
            apply_settings(values)

    family_labels = {"Convenções (inclui ACEP/ACCE)": "convencao", "Portarias": "extensao",
                     "Adesões": "adesao", "Acórdãos": "acordao", "Cessações de vigência": "cessacao",
                     "Outros avisos": "aviso", "Todos os documentos IRCT": "todos"}
    selected_family = tk.StringVar(value="Todos os documentos IRCT")
    def choose_family(_event=None):
        from .workspace import document_source
        if configured:
            from .workspace import DOCUMENT_FOLDERS
            source.set(str(Path(configured["named"]) / DOCUMENT_FOLDERS[family_labels[selected_family.get()]]))
        elif workspace_path.get():
            source.set(str(document_source(workspace_path.get(), family_labels[selected_family.get()])))
    ttk.Label(frame, text="Preparar documentos Markdown para importação no MAXQDA").grid(
        row=0, column=0, sticky="w")
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
    ttk.Button(toolbar, text="Configurar pastas…", command=configure).pack(side="left", padx=(0, 8))
    if args.installed:
        def use_sample():
            source.set(str(args.models.parent / "smoke.pdf"))
        ttk.Button(toolbar, text="Usar PDF de teste incluído", command=use_sample).pack(side="left")
    if not args.installed:
        ttk.Button(toolbar, text="Criar / usar pasta RNC…", command=use_workspace).pack(side="left")
    ttk.Label(conversion_panel, text="Documentos a converter na pasta RNC").pack(anchor="w")
    family_box = ttk.Combobox(conversion_panel, textvariable=selected_family, values=list(family_labels), state="readonly")
    family_box.pack(fill="x")
    family_box.bind("<<ComboboxSelected>>", choose_family)
    for label, variable in (
        ("PDF ou pasta de PDFs", source),
        ("Pasta de saída", output),
        ("Pasta de modelos (opcional)", models),
    ):
        if args.installed and variable is models:
            continue
        ttk.Label(conversion_panel, text=label).pack(anchor="w", pady=(8, 0))
        row = ttk.Frame(conversion_panel)
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
    flags = ttk.Frame(conversion_panel)
    flags.pack(fill="x", pady=(10, 0))
    for text, variable in (
        ("OCR (digitalizações)", ocr),
        ("Modelos locais / offline", offline),
        ("Substituir saídas existentes", overwrite),
    ):
        if args.installed and variable is offline:
            continue
        ttk.Checkbutton(flags, text=text, variable=variable).pack(side="left")
    activity = ttk.LabelFrame(frame, text="Atividade", padding=6)
    activity.grid(row=3, column=0, sticky="nsew")
    activity.rowconfigure(0, weight=1)
    activity.columnconfigure(0, weight=1)
    log = tk.Text(activity, height=10, state="disabled", wrap="word", font="TkTextFont")
    log.grid(row=0, column=0, sticky="nsew")
    scrollbar = ttk.Scrollbar(activity, orient="vertical", command=log.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    log.configure(yscrollcommand=scrollbar.set)
    status_panel = ttk.Frame(frame)
    status_panel.grid(row=4, column=0, sticky="ew", pady=6)
    status_panel.columnconfigure(1, weight=1)
    phase_text = tk.StringVar(value="Pronto para começar")
    totals_text = tk.StringVar()
    time_text = tk.StringVar(value="Tempo decorrido: 00:00:00")
    phase_label = ttk.Label(status_panel, textvariable=phase_text, wraplength=800)
    phase_label.grid(row=0, column=0, columnspan=2, sticky="w")
    status_panel.bind("<Configure>", lambda event: phase_label.configure(wraplength=max(280, event.width)))
    activity_pulse = ttk.Progressbar(status_panel, mode="indeterminate", length=70)
    activity_pulse.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=4)
    progress = ttk.Progressbar(status_panel, mode="determinate", maximum=100)
    progress.grid(row=1, column=1, sticky="ew", pady=4)
    ttk.Label(status_panel, textvariable=totals_text).grid(row=2, column=0, columnspan=2, sticky="w")
    ttk.Label(status_panel, textvariable=time_text).grid(row=3, column=0, columnspan=2, sticky="w")
    actions = ttk.Frame(frame)
    actions.grid(row=5, column=0, sticky="ew")
    actions.columnconfigure((0, 1), weight=1)

    report_path = None
    last_error = None
    running = threading.Event()
    reaudit_cancel = threading.Event()
    operation = OperationProgress()
    operation_context = "Interface"
    operation_failed = False
    pulse_active = False

    def begin_operation(label):
        nonlocal last_error, operation_context, operation_failed, report_path
        last_error = None
        report_path = None
        report_button.configure(state="disabled")
        operation_failed = False
        operation_context = label
        operation.begin(label)
        running.set()
        button.configure(state="disabled")

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
        if not all(guard() for guard in getattr(root, 'review_close_guards', [])):
            return
        remember_review_folder(output.get())
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
        begin_operation("A preparar a conversão")

        def worker():
            try:
                reporter = ProgressReporter(lambda line: events.put(("log", line)),
                                            lambda event: events.put(("progress", event)))
                reports = run(
                    *args, overwrite=replace, progress=reporter,
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
                        events.put(("review_folder", args[1]))
                except OSError:
                    events.put(("log", "Não foi possível abrir o relatório do lote. "
                                "Use Guardar relatório para o apoio."))
                finally:
                    events.put(("done", ""))

        threading.Thread(target=worker, daemon=True).start()

    button = ttk.Button(flags, text="Construir Markdown", command=start)
    button.pack(side="right", padx=(12, 0))
    report_button = ttk.Button(
        actions, text="Abrir relatório do lote", command=open_report, state="disabled"
    )
    report_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

    def save_support():
        from .diagnostics import export_support
        target = filedialog.asksaveasfilename(title="Guardar relatório para o apoio",
                                             initialfile="CRL-apoio.zip", defaultextension=".zip",
                                             filetypes=[("Relatório de apoio", "*.zip")])
        if not target:
            return
        attachments = [report_path, report_path.with_suffix(".json")] if report_path else []
        audit = (report_path.parent if report_path and report_path.name == "diagnostico.md"
                 else Path(output.get()) / "_auditoria")
        attachments += [audit / name for name in ("manifest.json", "progresso.log", "falha_nativa.log")]
        try:
            export_support(target, error=last_error, context=operation_context,
                           log=log.get("1.0", "end"), attachments=attachments)
        except OSError:
            messagebox.showerror("Não foi possível guardar", "Escolha outra pasta onde possa guardar ficheiros.")
        else:
            messagebox.showinfo("Relatório guardado", "Entregue o ZIP ao apoio informático.")

    ttk.Button(actions, text="Guardar relatório para o apoio", command=save_support).grid(
        row=0, column=1, sticky="ew", padx=(6, 0))

    def callback_error(error_type, error, tb):
        nonlocal last_error, operation_context, operation_failed
        from .diagnostics import support_dialog
        last_error = error.with_traceback(tb)
        if not running.is_set():
            operation_context = "Validar operação pela interface"
            operation_failed = True
            operation.begin(operation_context)
            operation.finish(failed=True)
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
        begin_operation("A recolher PDFs do BTE (usa Internet)")
        def work():
            transcript = io.StringIO()
            try:
                with contextlib.redirect_stdout(transcript):
                    result = collect(selected, progress_event=lambda event: events.put(("progress", event)))
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
        begin_operation("A organizar os PDFs")
        def work():
            try:
                results = name_records(workspace / "0_gestao/catalogo/registo_bte.jsonl", workspace,
                                       workspace / "0_gestao/vocabularios/siglas.csv",
                                       workspace / "0_gestao/vocabularios/empregadores_ambito.csv",
                                       apply=True, named_root=Path(configured["named"]) if configured else None,
                                       progress_event=lambda event: events.put(("progress", event)))
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
            remember_review_folder(output.get())
        except (ValueError, OSError) as error:
            messagebox.showinfo("Ainda não é possível conferir", str(error))

    def remember_review_folder(folder):
        try:
            settings.remember_review(Path(folder), workspace_path.get())
        except (ValueError, OSError, RuntimeError) as error:
            events.put(('log', f'Não foi possível atualizar os lotes recentes: {error}. '
                        'A pasta de trabalho e as revisões foram conservadas.'))

    def recent_review_folders():
        if running.is_set():
            return
        try:
            records = settings.recent_reviews(workspace_path.get())
        except (ValueError, OSError) as error:
            messagebox.showerror('Lotes recentes', str(error))
            return
        folders = list(dict.fromkeys([r['folder'] for r in reversed(records)]
                                    + ([configured['markdown']] if configured else [])))
        window = tk.Toplevel(root)
        window.title('Retomar um lote recente')
        window.geometry('750x320')
        ttk.Label(window, text='Escolha a pasta de revisão. A pasta principal configurada também está incluída.').pack(padx=12, pady=8)
        choices = tk.Listbox(window, height=10)
        choices.pack(fill='both', expand=True, padx=12)
        for folder in folders:
            choices.insert('end', folder + ('' if Path(folder).is_dir() else ' — indisponível'))

        def open_selected(_event=None):
            if choices.curselection():
                output.set(folders[choices.curselection()[0]])
                window.destroy()
                review_document()
        choices.bind('<Double-Button-1>', open_selected)
        ttk.Button(window, text='Abrir conferência', command=open_selected).pack(pady=8)

    ttk.Button(toolbar, text='Lotes recentes…', command=recent_review_folders).pack(side='left', padx=8)

    def resume_review():
        if running.is_set():
            return
        folder = filedialog.askdirectory(title="Pasta Markdown com o histórico a conferir")
        if folder:
            output.set(folder)
            review_document()

    def locate_review_sources():
        if running.is_set() or not output.get().strip():
            return
        folder = filedialog.askdirectory(title="Pasta com os PDFs originais deste lote")
        if not folder:
            return
        from .review_sources import locate_sources
        begin_operation("A localizar os PDFs originais pelos hashes")
        destination = Path(output.get())
        def worker():
            try:
                result = locate_sources(destination, Path(folder))
                events.put(("log", f"Fontes localizadas: {result['found']}; em falta: {result['missing']}. "
                            "Reabra Conferir / aprovar para retomar a revisão."))
            except Exception as error:
                events.put(("failure", error))
            finally:
                events.put(("done", ""))
        threading.Thread(target=worker, daemon=True).start()

    def recover_review_import():
        if running.is_set() or not output.get().strip():
            return
        from .review_exchange import recover_imports
        destination = Path(output.get())
        begin_operation("A recuperar importações interrompidas")
        def worker():
            try:
                receipts = recover_imports(destination)
                events.put(("log", f"Importações recuperadas: {len(receipts)}. "
                            "Reabra a conferência para continuar."))
            except Exception as error:
                events.put(("failure", error))
            finally:
                events.put(("done", ""))
        threading.Thread(target=worker, daemon=True).start()

    def reaudit_batch():
        if running.is_set():
            return
        from .reaudit import reaudit
        if not output.get().strip():
            messagebox.showinfo("Pasta de saída", "Selecione a saída de uma conversão existente.")
            return
        current_output = Path(output.get())
        reaudit_cancel.clear()
        begin_operation("A reauditar o Markdown")
        def worker():
            try:
                reporter = ProgressReporter(lambda line: events.put(("log", line)),
                                            lambda event: events.put(("progress", event)))
                destination, reports = reaudit(current_output, progress=reporter,
                                               cancel_event=reaudit_cancel, include_history=True)
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

    tools_panel.columnconfigure((0, 1), weight=1, uniform="tools")
    tools = (
        ("Recolher PDFs (usa internet)", collect_workspace, "Segue as ligações dos índices Excel no site do BTE."),
        ("Organizar PDFs (sem rede)", organize_workspace, "Atribui os nomes RNC e conserva os originais."),
        ("Conferir / aprovar…", review_document, "Revê alertas e regista a decisão sobre cada documento."),
        ("Retomar revisão noutra pasta…", resume_review, "Abre documentos e revisões de um lote anterior."),
        ("Localizar PDFs do lote…", locate_review_sources, "Associa os originais nesta máquina, sem alterar as revisões."),
        ("Recuperar importação interrompida…", recover_review_import, "Repõe o estado anterior a uma importação incompleta."),
        ("Entregar aprovados…", deliver_approved, "Cria uma entrega dos documentos já aprovados."),
        ("Reauditar lote (sem nova extração)", reaudit_batch, "Aplica os controlos atuais ao Markdown existente."),
    )
    tool_descriptions = []
    for index, (label, command, description) in enumerate(tools):
        row, column = divmod(index, 2)
        cell = ttk.Frame(tools_panel, padding=(4, 3))
        cell.grid(row=row, column=column, sticky="nsew")
        ttk.Button(cell, text=label, command=command).pack(fill="x")
        note = ttk.Label(cell, text=description, wraplength=340)
        note.pack(fill="x", pady=(3, 0))
        tool_descriptions.append(note)
    tools_panel.bind("<Configure>", lambda event: [
        note.configure(wraplength=max(200, event.width // 2 - 24)) for note in tool_descriptions])

    def poll():
        nonlocal report_path, last_error, operation_failed, pulse_active
        while not events.empty():
            kind, text = events.get_nowait()
            if kind == "progress":
                operation.update(text)
            elif kind == "output":
                output.set(text)
                remember_review_folder(text)
            elif kind == "review_folder":
                remember_review_folder(text)
            elif kind == "report":
                report_path = text
                report_button.configure(state="normal")
            elif kind == "done":
                running.clear()
                operation.finish(failed=operation_failed)
                button.configure(state="normal")
            elif kind == "failure":
                from .diagnostics import support_dialog
                last_error = text
                operation_failed = True
                support_dialog(root, text, "Operação pela interface")
            else:
                follow = log.yview()[1] >= 0.99
                log.configure(state="normal")
                log.insert("end", text + "\n")
                if follow:
                    log.see("end")
                log.configure(state="disabled")
        snapshot = operation.snapshot()
        phase_text.set(snapshot["phase"] + (" — " + snapshot["document"] if snapshot["document"] else ""))
        percent = snapshot["percent"]
        if percent is None:
            totals_text.set("Contagem indisponível nesta operação" if snapshot["active"] else "")
            progress.configure(value=0)
        else:
            totals_text.set(f"{snapshot['completed']}/{snapshot['total']} {snapshot['unit']} processados "
                            f"({percent:.1f}%)".replace(".", ","))
            progress.configure(value=percent)
        timing = "Tempo decorrido: " + duration(snapshot["elapsed"])
        if snapshot["active"]:
            if snapshot["total"] and snapshot["completed"] == snapshot["total"]:
                timing += "  ·  A finalizar o lote"
            else:
                timing += ("  ·  Restante estimado: cerca de " + duration(snapshot["remaining"])
                           if snapshot["remaining"] is not None else "  ·  Restante estimado: a calcular")
        time_text.set(timing)
        if running.is_set() and not pulse_active:
            activity_pulse.start(15)
            pulse_active = True
        elif not running.is_set() and pulse_active:
            activity_pulse.stop()
            pulse_active = False
        root.after(100, poll)

    # Font sizes and Windows display scaling vary between stations. Reserve
    # room for readable activity text as well as the controls at the bottom.
    root.update_idletasks()
    minimum_height = max(600, frame.winfo_reqheight() - activity.winfo_reqheight() + 100)
    root.minsize(750, minimum_height)
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
