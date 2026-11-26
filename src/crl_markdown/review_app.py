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
from .report import STATUS
from .ui_labels import FAMILIES, PROFILES, family, rule_label
from .validation import _load, _verified, decide, review_head


def load_document(output, document):
    target, report_path, report = _verified(Path(output), document)
    expected = {k: report[k] for k in ('source_sha256', 'markdown_sha256')}
    expected['report_sha256'] = _sha256(report_path)
    return target, report_path, report, expected


def current_inventory(output):
    """Atualiza filtros pelas publicações ativas sem alterar o manifesto de execução."""
    from .revisions import current_pointer
    output = Path(output)
    manifest = _load(output)
    for document in manifest['documents']:
        pointer = current_pointer(output, document['relative_source'])
        if not pointer.exists():
            continue
        data = json.loads(pointer.read_text(encoding='utf-8'))
        publication = (output / data['publication']).resolve()
        if not publication.is_relative_to((output / '_auditoria/correcoes').resolve()):
            raise ValueError('Publicação ativa fora da pasta de correções.')
        relative = Path(document['relative_source'])
        path = publication / '_auditoria/documentos' / relative.parent / (relative.stem + '.qualidade.json')
        if _sha256(path) != data['identity']['report_sha256']:
            raise ValueError('O relatório da versão ativa perdeu integridade.')
        report = json.loads(path.read_text(encoding='utf-8'))
        document.update(quality_status=report['quality_status'], findings=report.get('findings', []))
    return manifest


class ReviewWindow:
    def __init__(self, root, output):
        self.output = Path(output)
        self.manifest = current_inventory(self.output)
        self.documents = self.manifest['documents']
        self.current = None
        self.revision = None
        self.busy = False
        self.events = queue.Queue()
        self.editors = {}
        self.shown_document = ''
        self.saved_notes = ''
        self.decision_head = None
        self.window = tk.Toplevel(root)
        self.window.title('Conferir, corrigir e reauditar')
        self.window.geometry('1100x800')
        self.window.minsize(950, 700)
        self.window.transient(root)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        guards = getattr(root, 'review_close_guards', [])
        guards.append(self.can_close)
        root.review_close_guards = guards
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill='both', expand=True)
        filters = ttk.Frame(frame)
        filters.pack(fill='x')
        self.state = tk.StringVar(value='Todos')
        self.family = tk.StringVar(value='Todas')
        self.rule = tk.StringVar(value='Todas')
        families = sorted({family(d) for d in self.documents})
        rules = sorted({f['rule'] for d in self.documents for f in d.get('findings', [])})
        self.family_values = {FAMILIES.get(code, code.replace('_', ' ').capitalize()): code for code in families}
        self.rule_values = {rule_label(code): code for code in rules}
        self.filter_boxes = {}
        for label, variable, choices in [
            ('Estado', self.state, ['Todos', *(STATUS[k] for k in ('blocked', 'review', 'passed', 'falhou'))]),
            ('Família', self.family, ['Todas', *self.family_values]),
            ('Regra', self.rule, ['Todas', *self.rule_values]),
        ]:
            ttk.Label(filters, text=label).pack(side='left', padx=(0, 4))
            box = ttk.Combobox(filters, textvariable=variable, values=choices, state='readonly', width=18)
            box.pack(side='left', padx=(0, 12))
            self.filter_boxes[label] = box
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
        ttk.Button(decisions, text='Histórico de ocorrências…', command=self.open_history).pack(side='left', padx=6)
        exchange = ttk.Frame(frame)
        exchange.pack(fill='x', pady=4)
        ttk.Button(exchange, text='Preparar cópia para outra pessoa…', command=self.export_copy).pack(side='left')
        ttk.Button(exchange, text='Importar revisão recebida…', command=self.import_copy).pack(side='left', padx=8)
        ttk.Button(exchange, text='Reconciliar decisões…', command=self.reconcile).pack(side='left')
        self.filter_documents()
        self.window.after(100, self.poll)

    def close(self):
        if self.can_close():
            self.window.destroy()

    def can_close(self):
        if not self.window.winfo_exists():
            return True
        if self.busy:
            messagebox.showinfo('Auditoria em curso', 'Aguarde a conclusão antes de fechar.', parent=self.window)
            return False
        return all(guard() for window, guard in list(self.editors.values())
                   if window.winfo_exists()) and self.check_notes()

    def save_notes(self):
        import json
        from datetime import datetime, timezone
        from uuid import uuid4

        from .validation import _key
        if not self.shown_document or not self.current:
            return True
        if not self.reviewer.get().strip():
            messagebox.showerror('Responsável pelas notas',
                                 'Indique quem está a rever antes de guardar as notas.', parent=self.window)
            return False
        text = self.notes.get('1.0', 'end-1c')
        data = {'document': self.shown_document, 'identity': self.current[3],
                'reviewer': self.reviewer.get(), 'notes': text,
                'integral': self.integral.get(), 'at_utc': datetime.now(timezone.utc).isoformat(),
                'kind': 'rascunho_notas_nao_e_aprovacao'}
        target = self.output / '_auditoria/notas' / _key(self.shown_document) / (uuid4().hex + '.json')
        try:
            from .locking import exclusive
            with exclusive(self.output / '_auditoria/.operacao.lock'):
                atomic_write(target, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        except (OSError, RuntimeError) as error:
            messagebox.showerror('Não foi possível guardar as notas', str(error), parent=self.window)
            return False
        self.saved_notes = text
        return True

    def check_notes(self):
        from .drafts import confirm_discard_or_save
        return confirm_discard_or_save(self.window,
                                       self.notes.get('1.0', 'end-1c') != self.saved_notes,
                                       self.save_notes)

    def filter_documents(self, _event=None):
        if self.busy or not self.check_notes():
            return
        try:
            self.manifest = current_inventory(self.output)
        except (ValueError, OSError) as error:
            messagebox.showerror('Não foi possível atualizar a conferência', str(error), parent=self.window)
            return
        self.documents = self.manifest['documents']
        self.family_values = {FAMILIES.get(code, code.replace('_', ' ').capitalize()): code
                              for code in sorted({family(d) for d in self.documents})}
        self.rule_values = {rule_label(code): code for code in sorted({f['rule'] for d in self.documents
                                                                      for f in d.get('findings', [])})}
        for label, variable, values in [('Família', self.family, self.family_values),
                                         ('Regra', self.rule, self.rule_values)]:
            self.filter_boxes[label]['values'] = ['Todas', *values]
            if variable.get() != 'Todas' and variable.get() not in values:
                variable.set('Todas')
        choices = []
        for d in self.documents:
            if self.family.get() != 'Todas' and family(d) != self.family_values.get(self.family.get()):
                continue
            if (self.state.get() != 'Todos'
                    and STATUS.get(d.get('quality_status', d.get('state', 'review'))) != self.state.get()):
                continue
            if (self.rule.get() != 'Todas' and not any(f['rule'] == self.rule_values.get(self.rule.get())
                                                      for f in d.get('findings', []))):
                continue
            choices.append(d['relative_source'])
        self.choices['values'] = choices
        self.selected.set(self.selected.get() if self.selected.get() in choices else choices[0] if choices else '')
        self.saved_notes = self.notes.get('1.0', 'end-1c')
        self.refresh()

    def refresh(self, _event=None):
        if self.busy:
            return
        if not self.check_notes():
            self.selected.set(self.shown_document)
            return
        self.current = None
        self.revision = None
        self.integral.set(False)
        self.page.set('')
        self.notes.delete('1.0', 'end')
        self.saved_notes = ''
        self.shown_document = self.selected.get()
        self.findings.delete(*self.findings.get_children())
        self.approve.configure(state='disabled')
        if not self.selected.get():
            self.status.set('Sem documentos para os filtros escolhidos.')
            return
        document = next(d for d in self.documents if d['relative_source'] == self.selected.get())
        try:
            self.current = load_document(self.output, document)
            self.decision_head = review_head(self.output, document['relative_source'])
        except (ValueError, OSError) as error:
            self.status.set(str(error))
            return
        target, report_path, report, _ = self.current
        document.update({k: report[k] for k in ('quality_status', 'findings')})
        if report.get('revision'):
            self.revision = target.parents[len(Path(document['relative_source']).parts) - 1].parent.parent
        state = report['quality_status']
        profile = PROFILES.get(report.get('document_profile'), 'Não identificado')
        self.status.set(f'{STATUS.get(state, state)} · Perfil: {profile} · '
                        + ('Resolva as ocorrências de erro antes de aprovar.' if state == 'blocked'
                           else 'Confira esta versão e registe a decisão.'))
        if document.get('latest_attempt'):
            self.status.set(self.status.get() + ' · A última tentativa não terminou; '
                            'está a conferir a versão anterior verificada.')
        self.approve.configure(state='disabled' if state == 'blocked' else 'normal')
        for i, finding in enumerate(report.get('findings', [])):
            severity = {'error': 'Erro', 'warning': 'Aviso', 'info': 'Informação'}
            self.findings.insert('', 'end', iid=str(i), values=(severity.get(finding['severity'], finding['severity']), rule_label(finding['rule']),
                                 finding.get('page', '—'), finding.get('message', '')))
        from .validation import _key
        drafts = []
        for path in (self.output / '_auditoria/notas' / _key(self.shown_document)).glob('*.json'):
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('identity') == self.current[3]:
                drafts.append(data)
        if drafts:
            draft = max(drafts, key=lambda d: d['at_utc'])
            self.notes.insert('1.0', draft['notes'])
            self.saved_notes = draft['notes']
            # Uma nota recuperada nunca equivale a uma nova conferência integral.
            self.status.set(self.status.get() + f" · Notas de {draft['reviewer']} recuperadas (não é aprovação). "
                            'Indique quem está a rever.')

    def open_pdf(self):
        if self.current:
            from .review_sources import resolve_source
            document = next(d for d in self.documents if d['relative_source'] == self.selected.get())
            page = self.page.get().strip()
            suffix = '#page=' + page if page.isdigit() else ''
            webbrowser.open(resolve_source(self.output, document).resolve().as_uri() + suffix)

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

    def open_history(self):
        if not self.selected.get() or self.busy:
            return
        from tkinter import simpledialog

        from .occurrences import confirm_absence, history
        relative = self.selected.get()
        window = tk.Toplevel(self.window)
        window.title('Histórico de ocorrências — ' + relative)
        window.geometry('1050x650')
        frame = ttk.Frame(window, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Uma ocorrência ausente após reauditoria mantém-se por confirmar. '
                  'A confirmação histórica não dispensa erros atuais.', wraplength=950).pack(anchor='w')
        tree = ttk.Treeview(frame, columns=('status', 'rule', 'message'), show='headings', height=12)
        for key, label, width in [('status', 'Situação', 330), ('rule', 'Regra', 160),
                                  ('message', 'Ocorrência', 450)]:
            tree.heading(key, text=label)
            tree.column(key, width=width)
        tree.pack(fill='both', expand=True, pady=8)
        detail = tk.Text(frame, height=12, wrap='word', state='disabled')
        detail.pack(fill='both', expand=True)
        data = {}

        def refresh():
            nonlocal data
            try:
                data = history(self.output, relative)
            except (ValueError, OSError, RuntimeError) as error:
                messagebox.showerror('Histórico indisponível', str(error), parent=window)
                return
            tree.delete(*tree.get_children())
            for row in data['occurrences']:
                finding = row['finding']
                tree.insert('', 'end', iid=row['occurrence_id'], values=(row['status_label'],
                            rule_label(finding['rule']), finding.get('message', '')))

        def selected(_event=None):
            if not tree.selection():
                return
            row = next(r for r in data['occurrences'] if r['occurrence_id'] == tree.selection()[0])
            detail.configure(state='normal')
            detail.delete('1.0', 'end')
            finding = row['finding']
            lines = [row['status_label'], '', finding.get('message', ''),
                     f"Página: {finding.get('page') or 'não indicada'}", '', 'Observações conservadas:']
            for observation in row['observations']:
                f = observation['finding']
                lines.append(f"• {observation['recorded_at_utc']} — {f.get('message', '')}")
                if f.get('resolution'):
                    resolution = f['resolution']
                    lines.append(f"  Conferência por {resolution.get('reviewer', 'não indicado')}: "
                                 + resolution.get('notes', ''))
            for confirmation in row['confirmations']:
                lines.append(f"• Confirmação por {confirmation['reviewer']} em {confirmation['at_utc']}: "
                             + confirmation['notes'])
            detail.insert('1.0', '\n'.join(lines))
            detail.configure(state='disabled')

        def confirm():
            if not tree.selection():
                return
            notes = simpledialog.askstring('Confirmar ocorrência histórica',
                'Descreva o que conferiu na versão atual e a evidência da resolução:', parent=window)
            if notes is None:
                return
            try:
                confirm_absence(self.output, relative, tree.selection()[0], reviewer=self.reviewer.get(),
                                notes=notes, expected_version=data['current_version_id'])
            except (ValueError, OSError, RuntimeError) as error:
                messagebox.showerror('Confirmação não registada', str(error), parent=window)
                return
            refresh()

        tree.bind('<<TreeviewSelect>>', selected)
        ttk.Button(frame, text='Confirmar resolução histórica…', command=confirm).pack(anchor='w', pady=8)
        refresh()

    def export_copy(self):
        if not self.can_close():
            return
        parent = filedialog.askdirectory(parent=self.window, title='Onde guardar a nova cópia de revisão?')
        if not parent:
            return
        from uuid import uuid4

        from .review_exchange import export_review
        destination = Path(parent) / ('revisao_' + uuid4().hex[:12])
        reviewer = self.reviewer.get()
        self.task(lambda: export_review(self.output, destination, reviewer=reviewer),
                  lambda path: messagebox.showinfo('Cópia preparada',
                    f'Entregue esta pasta completa à pessoa que vai rever:\n{path}\n\n'
                    'Inclui PDFs, auditorias e revisões. Peça a devolução da cópia completa.', parent=self.window))

    def import_copy(self):
        if not self.can_close():
            return
        branch = filedialog.askdirectory(parent=self.window, title='Pasta completa de revisão recebida')
        if not branch:
            return
        from .review_exchange import merge_review
        reviewer = self.reviewer.get()

        def done(result):
            self.filter_documents()
            messagebox.showinfo('Revisão importada', f"Ficheiros incorporados: {result['imported']}. "
                                'O histórico e a origem da importação foram conservados.', parent=self.window)
        self.task(lambda: merge_review(self.output, Path(branch), reviewer=reviewer), done)

    def reconcile(self):
        if not self.current or self.busy:
            return
        from tkinter import simpledialog

        from .validation import decision_branches
        try:
            branches = decision_branches(self.output, self.selected.get())
            if len(branches) < 2:
                raise ValueError('Não há decisões concorrentes para reconciliar neste documento.')
            summary = '\n'.join(f"{r['reviewer']}: {r['decision']} ({r['date_utc']}) — {r.get('notes', '')}"
                                for r in branches.values())
            choice = simpledialog.askstring('Reconciliar decisões concorrentes', summary + '\n\n'
                'Depois de conferir esta versão, escreva aprovado ou rejeitado. '
                'O responsável e as notas da nova conferência são os indicados na janela principal.',
                parent=self.window)
            if choice is None:
                return
            decide(self.output, self.selected.get(), reviewer=self.reviewer.get(),
                   decision=choice.strip().lower(), scope='integral' if self.integral.get() else 'amostra',
                   notes=self.notes.get('1.0', 'end').strip(), expected=self.current[3],
                   reconcile_heads=list(branches))
            self.saved_notes = self.notes.get('1.0', 'end-1c')
            self.refresh()
        except (ValueError, OSError, RuntimeError) as error:
            messagebox.showerror('Reconciliação não registada', str(error), parent=self.window)

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
            self.check_revision_author()
            if self.revision is None:
                from .revisions import pending_revisions
                drafts = pending_revisions(self.output, self.selected.get(), self.reviewer.get(), self.current[3])
                if drafts:
                    answer = messagebox.askyesnocancel(
                        'Correção guardada por concluir',
                        'Existe um rascunho seu para esta versão. Quer retomá-lo?\n\n'
                        'Sim: retomar o mais recente. Não: criar uma correção separada.',
                        parent=self.window)
                    if answer is None:
                        return
                    if answer:
                        self.revision = drafts[-1]
                if self.revision is None:
                    self.revision = create_revision(self.output, self.selected.get(), self.reviewer.get())
        except (ValueError, OSError) as error:
            messagebox.showerror('Correção', str(error), parent=self.window)
            return
        revision = self.revision
        if revision in self.editors and self.editors[revision][0].winfo_exists():
            self.editors[revision][0].lift()
            return
        from .drafts import DraftSession, confirm_discard_or_save
        session = DraftSession(revision / 'correcao.md')
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
        text.insert('1.0', session.text)
        def save():
            try:
                session.save(text.get('1.0', 'end-1c'))
            except (ValueError, OSError, RuntimeError) as error:
                messagebox.showerror('Não foi possível guardar a correção', str(error), parent=editor)
                return False
            return True
        def can_close():
            return confirm_discard_or_save(editor,
                                          text.get('1.0', 'end-1c') != session.text, save)
        def close():
            if can_close():
                editor.destroy()
        self.editors[revision] = (editor, can_close)
        editor.protocol('WM_DELETE_WINDOW', close)
        def audit():
            if not self.busy and save():
                self.task(lambda: audit_revision(revision), lambda _result: self.refresh())
        controls = ttk.Frame(editor)
        controls.pack(fill='x', pady=8)
        ttk.Button(controls, text='Guardar rascunho', command=save).pack(side='left', padx=8)
        ttk.Button(controls, text='Reauditar correção guardada', command=audit).pack(side='left')
        ttk.Label(controls, text='Uma correção auditada precisa de nova conferência e decisão.').pack(side='left', padx=8)

    def check_revision_author(self):
        reviewer = self.reviewer.get().strip()
        if not reviewer:
            raise ValueError('Indique quem está a conferir ou corrigir este documento.')
        if self.revision is not None:
            meta = json.loads((self.revision / 'revision.json').read_text(encoding='utf-8'))
            if meta.get('reviewer') != reviewer:
                # Uma versão ativa de A é a base de B, não o rascunho de B.
                self.revision = None

    def resolve(self):
        if not self.current or self.busy or not self.findings.selection():
            return
        from .revisions import audit_revision, create_revision
        finding = self.current[2]['findings'][int(self.findings.selection()[0])]
        try:
            self.check_revision_author()
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
                          notes=self.notes.get('1.0', 'end').strip(), expected=self.current[3],
                          expected_decision=self.decision_head)
            self.decision_head = review_head(self.output, self.selected.get())
            self.saved_notes = self.notes.get('1.0', 'end-1c')
            messagebox.showinfo('Conferência registada', f'Decisão guardada: {path}', parent=self.window)
        except (ValueError, OSError) as error:
            messagebox.showerror('Conferência', str(error), parent=self.window)
