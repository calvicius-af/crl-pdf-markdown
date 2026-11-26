"""Conferência por ocorrência e editor de correções, com Tk na thread principal."""

import json
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .models import _sha256
from .pipeline import atomic_write
from .validation import _load, _verified, decide


def load_document(output, document):
    target, report_path, report = _verified(Path(output), document)
    expected = {k: report[k] for k in ('source_sha256', 'markdown_sha256')}
    expected['report_sha256'] = _sha256(report_path)
    return target, report_path, report, expected


class ReviewWindow:
    def __init__(self, root, output):
        self.output = Path(output)
        self.manifest = _load(self.output)
        self.documents = self.manifest['documents']
        from .revisions import current_pointer
        for document in self.documents:
            pointer = current_pointer(self.output, document['relative_source'])
            if pointer.exists():
                data = json.loads(pointer.read_text(encoding='utf-8'))
                document['quality_status'] = data.get('quality_status', document.get('quality_status'))
        self.current = None
        self.revision = None
        self.busy = False
        self.events = queue.Queue()
        self.window = tk.Toplevel(root)
        self.window.title('Conferir, corrigir e reauditar')
        self.window.geometry('1100x800')
        self.window.minsize(950, 700)
        self.window.transient(root)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill='both', expand=True)
        filters = ttk.Frame(frame)
        filters.pack(fill='x')
        self.state = tk.StringVar(value='Todos')
        self.family = tk.StringVar(value='Todas')
        self.rule = tk.StringVar(value='Todas')
        families = sorted({Path(d['relative_source']).parts[0] for d in self.documents})
        rules = sorted({f['rule'] for d in self.documents for f in d.get('findings', [])})
        for label, variable, choices in [
            ('Estado', self.state, ['Todos', 'blocked', 'review', 'passed', 'falhou']),
            ('Família', self.family, ['Todas', *families]),
            ('Regra', self.rule, ['Todas', *rules]),
        ]:
            ttk.Label(filters, text=label).pack(side='left', padx=(0, 4))
            box = ttk.Combobox(filters, textvariable=variable, values=choices, state='readonly', width=18)
            box.pack(side='left', padx=(0, 12))
            box.bind('<<ComboboxSelected>>', self.filter_documents)
        self.selected = tk.StringVar()
        self.choices = ttk.Combobox(frame, textvariable=self.selected, state='readonly')
        self.choices.pack(fill='x', pady=8)
        self.choices.bind('<<ComboboxSelected>>', self.refresh)
        self.status = tk.StringVar()
        ttk.Label(frame, textvariable=self.status, wraplength=1020).pack(anchor='w')
        actions = ttk.Frame(frame)
        actions.pack(fill='x', pady=6)
        for label, action in [('Abrir PDF', self.open_pdf), ('Abrir Markdown', self.open_markdown),
                              ('Relatório deste documento', self.open_evidence),
                              ('Reler páginas com OCR', self.ocr_pages),
                              ('Criar / editar correção', self.edit_revision)]:
            ttk.Button(actions, text=label, command=action).pack(side='left', padx=(0, 6))
        self.findings = ttk.Treeview(frame, columns=('severity', 'rule', 'page', 'message'),
                                     show='headings', height=9, selectmode='browse')
        for key, label, width in [('severity', 'Estado', 85), ('rule', 'Regra', 155),
                                  ('page', 'Página', 55), ('message', 'Ocorrência / ação', 680)]:
            self.findings.heading(key, text=label)
            self.findings.column(key, width=width, stretch=key == 'message')
        self.findings.pack(fill='both', expand=True)
        self.findings.bind('<<TreeviewSelect>>', self.show_finding)
        self.evidence = tk.Text(frame, height=6, wrap='word', state='disabled')
        self.evidence.pack(fill='x', pady=6)
        identity = ttk.Frame(frame)
        identity.pack(fill='x')
        ttk.Label(identity, text='Responsável pela conferência/correção').pack(side='left')
        self.reviewer = tk.StringVar()
        ttk.Entry(identity, textvariable=self.reviewer).pack(side='left', fill='x', expand=True, padx=8)
        self.integral = tk.BooleanVar()
        ttk.Checkbutton(frame, variable=self.integral,
                        text='Conferi integralmente esta versão, incluindo tabelas e anexos').pack(anchor='w', pady=4)
        ttk.Label(frame, text='Notas da conferência / evidência da ocorrência selecionada').pack(anchor='w')
        self.notes = tk.Text(frame, height=4, wrap='word')
        self.notes.pack(fill='x')
        resolution = ttk.Frame(frame)
        resolution.pack(fill='x', pady=6)
        self.resolution_action = tk.StringVar(value='conferido')
        ttk.Combobox(resolution, textvariable=self.resolution_action,
                     values=['conferido', 'corrigido', 'decorativo', 'transcrito'],
                     state='readonly', width=14).pack(side='left')
        ttk.Label(resolution, text='Página conferida').pack(side='left', padx=6)
        self.page = tk.StringVar()
        ttk.Entry(resolution, textvariable=self.page, width=6).pack(side='left')
        ttk.Button(resolution, text='Resolver ocorrência e reauditar', command=self.resolve).pack(side='left', padx=8)
        decisions = ttk.Frame(frame)
        decisions.pack(fill='x', pady=6)
        self.approve = ttk.Button(decisions, text='Registar aprovação', command=lambda: self.record('aprovado'))
        self.approve.pack(side='left')
        ttk.Button(decisions, text='Registar rejeição', command=lambda: self.record('rejeitado')).pack(side='left', padx=6)
        self.filter_documents()
        self.window.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('Auditoria em curso', 'Aguarde a conclusão antes de fechar.', parent=self.window)
        else:
            self.window.destroy()

    def filter_documents(self, _event=None):
        choices = []
        for d in self.documents:
            if self.family.get() != 'Todas' and Path(d['relative_source']).parts[0] != self.family.get():
                continue
            if self.state.get() != 'Todos' and d.get('quality_status', d.get('state', 'review')) != self.state.get():
                continue
            if self.rule.get() != 'Todas' and not any(f['rule'] == self.rule.get() for f in d.get('findings', [])):
                continue
            choices.append(d['relative_source'])
        self.choices['values'] = choices
        self.selected.set(choices[0] if choices else '')
        self.refresh()

    def refresh(self, _event=None):
        if self.busy:
            return
        self.current = None
        self.revision = None
        self.integral.set(False)
        self.page.set('')
        self.notes.delete('1.0', 'end')
        self.findings.delete(*self.findings.get_children())
        self.approve.configure(state='disabled')
        if not self.selected.get():
            self.status.set('Sem documentos para os filtros escolhidos.')
            return
        document = next(d for d in self.documents if d['relative_source'] == self.selected.get())
        try:
            self.current = load_document(self.output, document)
        except (ValueError, OSError) as error:
            self.status.set(str(error))
            return
        target, report_path, report, _ = self.current
        document.update({k: report[k] for k in ('quality_status', 'findings')})
        if report.get('revision'):
            self.revision = target.parents[len(Path(document['relative_source']).parts) - 1].parent.parent
        state = report['quality_status']
        self.status.set(f'{state} · Perfil: {report.get("document_profile", "não indicado")} · '
                        + ('Resolva as ocorrências de erro antes de aprovar.' if state == 'blocked'
                           else 'Confira esta versão e registe a decisão.'))
        self.approve.configure(state='disabled' if state == 'blocked' else 'normal')
        for i, finding in enumerate(report.get('findings', [])):
            self.findings.insert('', 'end', iid=str(i), values=(finding['severity'], finding['rule'],
                                 finding.get('page', '—'), finding.get('message', '')))

    def open_pdf(self):
        if self.current:
            page = self.page.get().strip()
            suffix = '#page=' + page if page.isdigit() else ''
            webbrowser.open(Path(self.current[2]['source']).resolve().as_uri() + suffix)

    def open_markdown(self):
        if self.current:
            webbrowser.open(self.current[0].resolve().as_uri())

    def open_evidence(self):
        if not self.current:
            return
        from .report import diagnostic
        from .validation import _key
        manifest = {**self.manifest, 'documents': [{**self.current[2], 'relative_source': self.selected.get()}]}
        path = self.output / '_auditoria/consulta' / (_key(self.selected.get()) + '.md')
        atomic_write(path, diagnostic(manifest, path.parent))
        webbrowser.open(path.resolve().as_uri())

    def show_finding(self, _event=None):
        selected = self.findings.selection()
        if not selected or not self.current:
            return
        finding = self.current[2]['findings'][int(selected[0])]
        if finding.get('page'):
            self.page.set(str(finding['page']))
        details = [finding.get('message', ''), f"ID: {finding.get('id', 'requer reauditoria')} · Linha: {finding.get('line', 0)}"]
        if finding.get('bbox'):
            details.append('Região PDF: ' + str(finding['bbox']))
        if finding.get('evidence'):
            details.append('Célula na fonte: ' + finding['evidence'].get('source_cell', ''))
            details.append('Célula na saída: ' + finding['evidence'].get('rendered_cell', ''))
        if finding['rule'] in {'AMOUNTS', 'CRITICAL_SYMBOLS'}:
            for e in self.current[2].get('completeness', {}).get('numeric_evidence', []):
                details.append(f"Página {e['page']}: {e['source_text']}")
        lines = self.current[0].read_text(encoding='utf-8').splitlines()
        line = finding.get('line', 0)
        if line:
            details.extend(lines[max(0, line-2):line+2])
        self.evidence.configure(state='normal')
        self.evidence.delete('1.0', 'end')
        self.evidence.insert('1.0', '\n'.join(details))
        self.evidence.configure(state='disabled')

    def task(self, work, done):
        if self.busy:
            return
        self.busy = True
        self.approve.configure(state='disabled')
        self.status.set('A auditar a correção; o original é conservado…')
        def worker():
            try:
                result = work()
                self.events.put((done, result, None))
            except Exception as error:
                self.events.put((None, None, error))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        while not self.events.empty():
            callback, result, error = self.events.get_nowait()
            self.busy = False
            if error:
                self.refresh()
                messagebox.showerror('Ação não concluída', str(error), parent=self.window)
            elif callback:
                callback(result)
        if self.window.winfo_exists():
            self.window.after(100, self.poll)

    def edit_revision(self):
        if not self.current or self.busy:
            return
        from .revisions import audit_revision, create_revision
        try:
            if self.revision is None:
                self.revision = create_revision(self.output, self.selected.get(), self.reviewer.get())
        except (ValueError, OSError) as error:
            messagebox.showerror('Correção', str(error), parent=self.window)
            return
        revision = self.revision
        editor = tk.Toplevel(self.window)
        editor.title('Correção separada do original — guardar e reauditar')
        editor.geometry('1000x720')
        edit_body = ttk.Frame(editor)
        edit_body.pack(fill='both', expand=True)
        edit_body.rowconfigure(0, weight=1)
        edit_body.columnconfigure(0, weight=1)
        text = tk.Text(edit_body, wrap='none', undo=True)
        text.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(edit_body, orient='vertical', command=text.yview)
        horizontal = ttk.Scrollbar(edit_body, orient='horizontal', command=text.xview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        text.insert('1.0', (revision / 'correcao.md').read_text(encoding='utf-8'))
        def save():
            atomic_write(revision / 'correcao.md', text.get('1.0', 'end-1c'))
        def audit():
            save()
            self.task(lambda: audit_revision(revision), lambda _result: self.refresh())
        controls = ttk.Frame(editor)
        controls.pack(fill='x', pady=8)
        ttk.Button(controls, text='Guardar rascunho', command=save).pack(side='left', padx=8)
        ttk.Button(controls, text='Reauditar correção guardada', command=audit).pack(side='left')
        ttk.Label(controls, text='Uma correção auditada precisa de nova conferência e decisão.').pack(side='left', padx=8)

    def resolve(self):
        if not self.current or self.busy or not self.findings.selection():
            return
        from .revisions import audit_revision, create_revision
        finding = self.current[2]['findings'][int(self.findings.selection()[0])]
        try:
            if not finding.get('id'):
                raise ValueError('Esta auditoria é antiga. Use Reauditar lote antes de resolver ocorrências.')
            page = int(self.page.get())
            notes = self.notes.get('1.0', 'end').strip()
            if not notes:
                raise ValueError('Descreva a evidência e a resolução desta ocorrência nas notas.')
            if self.revision is None:
                self.revision = create_revision(self.output, self.selected.get(), self.reviewer.get())
        except (ValueError, OSError) as error:
            messagebox.showerror('Resolução', str(error), parent=self.window)
            return
        resolution = {'finding_id': finding['id'], 'page': page, 'notes': notes,
                      'action': self.resolution_action.get()}
        revision = self.revision
        self.task(lambda: audit_revision(revision, resolutions=[resolution]), lambda _result: self.refresh())

    def ocr_pages(self):
        if not self.current or self.busy:
            return
        from .page_ocr import parse_pages, reextract_pages
        if not self.reviewer.get().strip():
            messagebox.showinfo('Responsável', 'Indique o responsável pela nova extração.', parent=self.window)
            return
        if self.current[2].get('revision'):
            messagebox.showinfo('Correção ativa', 'Existe uma edição humana ativa. Para a conservar, '
                'o OCR deve ser ensaiado numa reauditoria separada do original.', parent=self.window)
            return
        dialog = tk.Toplevel(self.window)
        dialog.title('OCR local nas páginas selecionadas')
        frame = ttk.Frame(dialog, padding=14)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Páginas a reler (exemplo: 2,5-7)').pack(anchor='w')
        pages = tk.StringVar(value=self.page.get())
        ttk.Entry(frame, textvariable=pages, width=60).pack(fill='x', pady=6)
        models = tk.StringVar(value=self.current[2].get('options', {}).get('models') or '')
        ttk.Label(frame, text='Pasta de modelos locais com OCR').pack(anchor='w')
        ttk.Entry(frame, textvariable=models, width=60).pack(fill='x', pady=6)
        def choose():
            path = filedialog.askdirectory(parent=dialog, title='Modelos locais com OCR')
            if path:
                models.set(path)
        ttk.Button(frame, text='Escolher modelos…', command=choose).pack(anchor='w')
        def start():
            try:
                selected = parse_pages(pages.get(), self.current[2]['pages'])
                if not models.get().strip():
                    raise ValueError('Selecione a pasta de modelos OCR.')
            except ValueError as error:
                messagebox.showerror('OCR dirigido', str(error), parent=dialog)
                return
            folder, relative, reviewer, model_folder = self.output, self.selected.get(), self.reviewer.get(), Path(models.get())
            dialog.destroy()
            self.task(lambda: reextract_pages(folder, relative, reviewer, model_folder, selected),
                      lambda _result: self.refresh())
        ttk.Button(frame, text='Executar OCR sem rede', command=start).pack(pady=10)

    def record(self, decision):
        if not self.current or self.busy:
            return
        try:
            path = decide(self.output, self.selected.get(), reviewer=self.reviewer.get(), decision=decision,
                          scope='integral' if self.integral.get() else 'amostra',
                          notes=self.notes.get('1.0', 'end').strip(), expected=self.current[3])
            messagebox.showinfo('Conferência registada', f'Decisão guardada: {path}', parent=self.window)
        except (ValueError, OSError) as error:
            messagebox.showerror('Conferência', str(error), parent=self.window)
