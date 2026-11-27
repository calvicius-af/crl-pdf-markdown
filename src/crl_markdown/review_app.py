"""Conferência por ocorrência e editor de correções, com Tk na thread principal."""

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .caminhos import longpath, open_with_system
from .models import _sha256
from .pipeline import atomic_write
from .report import STATUS
from .ui_labels import CATEGORIES, FAMILIES, PROFILES, category, family, rule_label
from .validation import _load, _verified, decide, review_head

FALSE_ALARM = 'está correto (falso alarme)'
BATCH_NOTE = 'Aprovação em lote: documento sem alertas automáticos.'
APPROVAL_NOTE = 'Avisos conferidos no PDF; o Markdown está correto.'
FALSE_ALARM_NOTE = 'Conferido no PDF: o Markdown está correto; o alerta automático não corresponde a um erro.'


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
        # Prefixo de caminho estendido no Windows: as correções ficam em
        # subpastas profundas que ultrapassam os 260 caracteres.
        self.output = longpath(output)
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
        self.window.title('Rever documentos')
        self.window.geometry('1150x780')
        self.window.minsize(950, 640)
        self.window.transient(root)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        guards = getattr(root, 'review_close_guards', [])
        guards.append(self.can_close)
        root.review_close_guards = guards
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill='both', expand=True)
        identity = ttk.Frame(frame)
        identity.pack(fill='x', pady=(0, 6))
        ttk.Label(identity, text='Quem está a rever').pack(side='left')
        from . import settings
        self.reviewer = tk.StringVar(value=settings.reviewer())
        ttk.Entry(identity, textvariable=self.reviewer, width=36).pack(side='left', padx=8)
        filters = ttk.Frame(frame)
        filters.pack(fill='x')
        self.state = tk.StringVar(value='Todos')
        self.family = tk.StringVar(value='Todas')
        self.rule = tk.StringVar(value='Todas')
        families = sorted({family(d) for d in self.documents})
        self.family_values = {FAMILIES.get(code, code.replace('_', ' ').capitalize()): code for code in families}
        self.rule_values = {label: code for code, label in CATEGORIES.items()}
        self.filter_boxes = {}
        for label, variable, choices in [
            ('Estado', self.state, ['Todos', *(STATUS[k] for k in ('blocked', 'review', 'passed', 'falhou'))]),
            ('Família', self.family, ['Todas', *self.family_values]),
            ('Problema', self.rule, ['Todas', *self.rule_values]),
        ]:
            ttk.Label(filters, text=label).pack(side='left', padx=(0, 4))
            box = ttk.Combobox(filters, textvariable=variable, values=choices, state='readonly', width=22)
            box.pack(side='left', padx=(0, 12))
            self.filter_boxes[label] = box
            box.bind('<<ComboboxSelected>>', self.filter_documents)
        navigation = ttk.Frame(frame)
        navigation.pack(fill='x', pady=8)
        ttk.Button(navigation, text='Anterior', command=lambda: self.step(-1)).pack(side='left')
        self.selected = tk.StringVar()
        self.choices = ttk.Combobox(navigation, textvariable=self.selected, state='readonly')
        self.choices.pack(side='left', fill='x', expand=True, padx=6)
        self.choices.bind('<<ComboboxSelected>>', self.refresh)
        ttk.Button(navigation, text='Seguinte', command=lambda: self.step(1)).pack(side='left')
        self.position = tk.StringVar()
        ttk.Label(navigation, textvariable=self.position, width=12, anchor='e').pack(side='left')
        self.status = tk.StringVar()
        ttk.Label(frame, textvariable=self.status, wraplength=1080).pack(anchor='w')
        self.findings = ttk.Treeview(frame, columns=('severity', 'rule', 'page', 'message'),
                                     show='headings', height=10, selectmode='browse')
        for key, label, width in [('severity', 'Gravidade', 85), ('rule', 'Problema', 190),
                                  ('page', 'Página', 55), ('message', 'O que foi detetado', 700)]:
            self.findings.heading(key, text=label)
            self.findings.column(key, width=width, stretch=key == 'message')
        self.findings.pack(fill='both', expand=True, pady=(6, 0))
        self.findings.bind('<<TreeviewSelect>>', self.show_finding)
        self.findings.bind('<Double-1>', lambda _event: self.edit_revision())
        self.evidence = tk.Text(frame, height=5, wrap='word', state='disabled')
        self.evidence.pack(fill='x', pady=6)
        ttk.Label(frame, text='Nota (opcional)').pack(anchor='w')
        self.notes = tk.Text(frame, height=2, wrap='word')
        self.notes.pack(fill='x')
        # Campos internos conservados para o OCR e para decisões antigas; não
        # aparecem na janela principal.
        self.integral = tk.BooleanVar()
        self.page = tk.StringVar()
        self.resolution_action = tk.StringVar(value=FALSE_ALARM)
        actions = ttk.Frame(frame)
        actions.pack(fill='x', pady=(8, 0))
        ttk.Button(actions, text='Corrigir (PDF e Markdown lado a lado)',
                   command=self.edit_revision).pack(side='left')
        ttk.Button(actions, text='Está correto (falso alarme)', command=self.resolve).pack(side='left', padx=6)
        self.approve = ttk.Button(actions, text='Aprovar', command=lambda: self.record('aprovado'))
        self.approve.pack(side='left', padx=(18, 6))
        ttk.Button(actions, text='Rejeitar', command=lambda: self.record('rejeitado')).pack(side='left')
        more = ttk.Menubutton(actions, text='Mais opções')
        menu = tk.Menu(more, tearoff=False)
        for label, action in [('Abrir PDF no leitor do sistema', self.open_pdf),
                              ('Abrir Markdown no editor do sistema', self.open_markdown),
                              ('Relatório deste documento', self.open_evidence),
                              ('Aprovar todos os documentos sem alertas desta lista…', self.approve_clean),
                              ('Reler páginas com OCR…', self.ocr_pages),
                              ('Histórico de ocorrências…', self.open_history),
                              (None, None),
                              ('Preparar cópia para outra pessoa…', self.export_copy),
                              ('Importar revisão recebida…', self.import_copy),
                              ('Reconciliar decisões…', self.reconcile)]:
            if label is None:
                menu.add_separator()
            else:
                menu.add_command(label=label, command=action)
        more['menu'] = menu
        more.pack(side='right')
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
        for label, variable, values in [('Família', self.family, self.family_values),
                                         ('Problema', self.rule, self.rule_values)]:
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
            if (self.rule.get() != 'Todas' and not any(
                    category(f['rule']) == self.rule_values.get(self.rule.get()) and f.get('severity') != 'info'
                    for f in d.get('findings', []))):
                continue
            choices.append(d['relative_source'])
        self.choices['values'] = choices
        self.selected.set(self.selected.get() if self.selected.get() in choices else choices[0] if choices else '')
        self.saved_notes = self.notes.get('1.0', 'end-1c')
        self.refresh()

    def step(self, delta):
        values = list(self.choices['values'])
        if self.busy or not values:
            return
        index = values.index(self.selected.get()) if self.selected.get() in values else -1
        index = min(max(index + delta, 0), len(values) - 1)
        if values[index] != self.selected.get():
            self.selected.set(values[index])
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
        values = list(self.choices['values'])
        self.position.set(f'{values.index(self.selected.get()) + 1} de {len(values)}'
                          if self.selected.get() in values else '')
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
        self.status.set(f'{STATUS.get(state, state)} · {profile} · '
                        + ('Corrija o Markdown ou marque os alertas como falso alarme antes de aprovar.'
                           if state == 'blocked' else 'Confira e aprove ou rejeite.'))
        if document.get('latest_attempt'):
            self.status.set(self.status.get() + ' · A última tentativa não terminou; '
                            'está a conferir a versão anterior verificada.')
        self.approve.configure(state='disabled' if state == 'blocked' else 'normal')
        for i, finding in enumerate(report.get('findings', [])):
            if finding['severity'] == 'info':
                continue  # Informação e alertas já resolvidos não pedem ação.
            severity = {'error': 'Erro', 'warning': 'Aviso'}
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

    def open_file(self, path):
        try:
            open_with_system(path)
        except (ValueError, OSError) as error:
            messagebox.showerror('Não foi possível abrir o ficheiro', str(error), parent=self.window)

    def open_pdf(self):
        if self.current:
            from .review_sources import resolve_source
            document = next(d for d in self.documents if d['relative_source'] == self.selected.get())
            try:
                source = resolve_source(self.output, document)
            except (ValueError, OSError) as error:
                messagebox.showerror('PDF indisponível', str(error), parent=self.window)
                return
            self.open_file(source)

    def open_markdown(self):
        if self.current:
            self.open_file(self.current[0])

    def open_evidence(self):
        if not self.current:
            return
        from .report import diagnostic
        from .validation import _key
        manifest = {**self.manifest, 'documents': [{**self.current[2], 'relative_source': self.selected.get()}]}
        path = self.output / '_auditoria/consulta' / (_key(self.selected.get()) + '.md')
        atomic_write(path, diagnostic(manifest, path.parent))
        self.open_file(path)

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
        editor.title('Corrigir: ' + self.selected.get())
        editor.geometry('1400x860')
        panes = ttk.PanedWindow(editor, orient='horizontal')
        panes.pack(fill='both', expand=True)
        pdf_side = ttk.Frame(panes)
        edit_body = ttk.Frame(panes)
        panes.add(pdf_side, weight=1)
        panes.add(edit_body, weight=1)
        finding = None
        if self.findings.selection():
            finding = self.current[2]['findings'][int(self.findings.selection()[0])]
        self.pdf_panel(pdf_side, int((finding or {}).get('page') or 1))
        ttk.Label(edit_body, text='Markdown (cópia de trabalho; o original é conservado)').grid(
            row=0, column=0, sticky='w', padx=4, pady=4)
        edit_body.rowconfigure(1, weight=1)
        edit_body.columnconfigure(0, weight=1)
        text = tk.Text(edit_body, wrap='none', undo=True)
        text.grid(row=1, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(edit_body, orient='vertical', command=text.yview)
        horizontal = ttk.Scrollbar(edit_body, orient='horizontal', command=text.xview)
        vertical.grid(row=1, column=1, sticky='ns')
        horizontal.grid(row=2, column=0, sticky='ew')
        text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        text.insert('1.0', session.text)
        line = int((finding or {}).get('line') or 0)
        if line:
            text.tag_configure('ocorrencia', background='#fff2a8')
            text.tag_add('ocorrencia', f'{line}.0', f'{line}.end')
            text.see(f'{line}.0')
            text.mark_set('insert', f'{line}.0')
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
                def done(_result):
                    if editor.winfo_exists():
                        editor.destroy()
                    self.refresh()
                self.task(lambda: audit_revision(revision), done)
        controls = ttk.Frame(edit_body)
        controls.grid(row=3, column=0, columnspan=2, sticky='ew', pady=8)
        ttk.Button(controls, text='Guardar e verificar', command=audit).pack(side='left', padx=4)
        ttk.Button(controls, text='Guardar sem verificar', command=save).pack(side='left', padx=4)
        ttk.Label(controls, text='Depois de verificar, aprove ou rejeite na janela principal.').pack(
            side='left', padx=8)

    def pdf_panel(self, parent, first_page):
        """Página do PDF desenhada na própria janela, para comparar sem trocar de aplicação."""
        from .review_sources import resolve_source
        document = next(d for d in self.documents if d['relative_source'] == self.selected.get())
        state = {'page': max(1, first_page), 'width': 760, 'image': None, 'total': None}
        bar = ttk.Frame(parent)
        bar.pack(fill='x', padx=4, pady=4)
        label = tk.StringVar()
        canvas = tk.Canvas(parent, background='#808080', highlightthickness=0)
        vertical = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vertical.set)
        vertical.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        try:
            from .pdf_view import page_count
            source = resolve_source(self.output, document)
            state['total'] = page_count(source)
        except Exception as error:  # Sem PDF ou sem PDFium: a correção continua possível.
            ttk.Label(parent, text=f'Não foi possível mostrar o PDF: {error}', wraplength=600).pack()
            return
        import tempfile
        folder = Path(tempfile.mkdtemp(prefix='crl-paginas-'))

        def show():
            from .pdf_view import render_page
            state['page'] = min(max(state['page'], 1), state['total'])
            try:
                png = render_page(source, state['page'], state['width'], folder)
                state['image'] = tk.PhotoImage(file=str(png))
            except Exception as error:
                label.set(f'Página {state["page"]} não desenhada ({type(error).__name__}): {error}')
                return
            canvas.delete('all')
            canvas.create_image(0, 0, anchor='nw', image=state['image'])
            canvas.configure(scrollregion=(0, 0, state['image'].width(), state['image'].height()))
            canvas.yview_moveto(0)
            label.set(f'Página {state["page"]} de {state["total"]}')

        def move(delta):
            state['page'] += delta
            show()

        def zoom(factor):
            state['width'] = int(min(max(state['width'] * factor, 400), 2000))
            show()

        ttk.Button(bar, text='Página anterior', command=lambda: move(-1)).pack(side='left')
        ttk.Label(bar, textvariable=label, width=18, anchor='center').pack(side='left', padx=6)
        ttk.Button(bar, text='Página seguinte', command=lambda: move(1)).pack(side='left')
        ttk.Button(bar, text='Ampliar', command=lambda: zoom(1.25)).pack(side='left', padx=(12, 0))
        ttk.Button(bar, text='Reduzir', command=lambda: zoom(.8)).pack(side='left', padx=4)
        canvas.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        show()

    def check_revision_author(self):
        reviewer = self.reviewer.get().strip()
        if not reviewer:
            raise ValueError('Indique quem está a rever, no campo do topo da janela.')
        from . import settings
        settings.remember_reviewer(reviewer)
        if self.revision is not None:
            meta = json.loads((self.revision / 'revision.json').read_text(encoding='utf-8'))
            if meta.get('reviewer') != reviewer:
                # Uma versão ativa de A é a base de B, não o rascunho de B.
                self.revision = None

    def resolve(self):
        """Marcar como falso alarme a ocorrência selecionada ou, sem seleção, todas as pendentes."""
        if not self.current or self.busy:
            return
        from .revisions import audit_revision, create_revision
        findings = self.current[2]['findings']
        if self.findings.selection():
            chosen = [findings[int(self.findings.selection()[0])]]
        else:
            chosen = [f for f in findings if f.get('severity') != 'info']
            if not chosen:
                return
            if not messagebox.askyesno('Está correto',
                                       f'Confirma que conferiu no PDF os {len(chosen)} alertas deste documento '
                                       'e que o Markdown está correto?', parent=self.window):
                return
        try:
            self.check_revision_author()
            if not all(f.get('id') for f in chosen):
                raise ValueError('Esta auditoria é antiga. Use Reauditar lote antes de resolver ocorrências.')
            notes = self.notes.get('1.0', 'end').strip() or FALSE_ALARM_NOTE
            pages = self.current[2].get('pages') or 1
            if self.revision is None:
                self.revision = create_revision(self.output, self.selected.get(), self.reviewer.get())
        except (ValueError, OSError) as error:
            messagebox.showerror('Está correto', str(error), parent=self.window)
            return
        resolutions = [{'finding_id': f['id'], 'page': min(max(int(f.get('page') or 1), 1), pages),
                        'notes': notes, 'action': 'falso_alarme'} for f in chosen]
        revision = self.revision
        self.task(lambda: audit_revision(revision, resolutions=resolutions), lambda _result: self.refresh())

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

    def approve_clean(self):
        """Aprovação em lote, com o nome de quem revê, só para documentos sem alertas."""
        if self.busy or not self.check_notes():
            return
        try:
            self.check_revision_author()
        except ValueError as error:
            messagebox.showerror('Aprovar em lote', str(error), parent=self.window)
            return
        listed = set(self.choices['values'])
        clean = [d['relative_source'] for d in self.documents
                 if d['relative_source'] in listed and d.get('quality_status') == 'passed']
        if not clean:
            messagebox.showinfo('Aprovar em lote', 'Não há documentos sem alertas nesta lista.', parent=self.window)
            return
        if not messagebox.askyesno('Aprovar em lote',
                                   f'Aprovar em seu nome os {len(clean)} documentos sem alertas automáticos '
                                   'desta lista? Os que já têm decisão atual ficam como estão.', parent=self.window):
            return
        output, reviewer = self.output, self.reviewer.get()

        def work():
            done = 0
            for relative in clean:
                if review_head(output, relative) is not None:
                    continue
                decide(output, relative, reviewer=reviewer, decision='aprovado', scope='integral',
                       notes=BATCH_NOTE)
                done += 1
            return done

        def finished(count):
            self.refresh()
            messagebox.showinfo('Aprovar em lote', f'Documentos aprovados: {count}.', parent=self.window)
        self.task(work, finished)

    def record(self, decision):
        if not self.current or self.busy:
            return
        notes = self.notes.get('1.0', 'end').strip()
        if decision == 'aprovado' and not notes and self.current[2].get('quality_status') == 'review':
            notes = APPROVAL_NOTE
        try:
            self.check_revision_author()
            # Aprovar declara a conferência do documento; é a decisão que a entrega aceita.
            scope = 'integral' if decision == 'aprovado' or self.integral.get() else 'amostra'
            decide(self.output, self.selected.get(), reviewer=self.reviewer.get(), decision=decision,
                   scope=scope, notes=notes, expected=self.current[3],
                   expected_decision=self.decision_head)
            self.decision_head = review_head(self.output, self.selected.get())
            self.saved_notes = self.notes.get('1.0', 'end-1c')
        except (ValueError, OSError) as error:
            messagebox.showerror('Decisão não registada', str(error), parent=self.window)
            return
        label = 'Aprovado' if decision == 'aprovado' else 'Rejeitado'
        self.notes.delete('1.0', 'end')
        self.saved_notes = ''
        before = self.selected.get()
        self.step(1)
        if self.selected.get() == before:
            self.status.set(f'{label}: {before}. Era o último documento desta lista.')
        else:
            self.status.set(f'{label}: {before}. ' + self.status.get())
