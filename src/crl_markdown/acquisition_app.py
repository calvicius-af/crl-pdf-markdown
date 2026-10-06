"""Recolha e revisão de nomes: operações em thread, Tk na thread principal."""

import queue
import threading
from pathlib import Path
from tkinter import BooleanVar, StringVar, filedialog, messagebox, ttk

from .ambito import carregar_vocabulario
from .nomeacao import nomear, tabela_de_siglas, texto_resumo
from .recolha import Registo, recolher
from .recolha import texto_resumo as resumo_recolha


class AcquisitionPanel:
    def __init__(self, notebook, source):
        self.source = source
        self.events = queue.Queue()
        self.busy = False
        self.reviewed = False
        self.indices = StringVar(value="data/raw/indices")
        self.downloads = StringVar(value="data/interim/recolha")
        self.register = StringVar(value="data/registo/registo_bte.jsonl")
        self.destination = StringVar(value="data/raw/bte")
        self.siglas = StringVar()
        self.ambitos = StringVar()
        self.network = BooleanVar(value=False)
        self.status = StringVar(value="Escolhe os índices Excel fornecidos pela equipa.")
        collect = ttk.Frame(notebook, padding=16)
        naming = ttk.Frame(notebook, padding=16)
        notebook.add(collect, text="1. Recolher PDFs")
        notebook.add(naming, text="2. Rever nomes")
        for label, var, kind in (
            ("Índices Excel (ficheiro ou pasta)", self.indices, "xlsx"),
            ("Pasta dos PDFs originais", self.downloads, "folder"),
            ("Registo de recolha e nomeação", self.register, "jsonl"),
        ):
            self.field(collect, label, var, kind)
        ttk.Checkbutton(collect, text="Autorizar descargas do site do BTE nesta corrida",
                        variable=self.network).pack(anchor="w", pady=12)
        ttk.Label(collect, text="Sem autorização, a recolha simula e atualiza o catálogo.",
                  wraplength=700).pack(anchor="w")
        self.collect_button = ttk.Button(collect, text="Recolher / simular", command=self.collect)
        self.collect_button.pack(anchor="w", pady=12)
        for label, var, kind in (
            ("Pasta das cópias com nomes RNC", self.destination, "folder"),
            ("CSV de siglas confirmadas (opcional)", self.siglas, "csv"),
            ("CSV de âmbitos dos empregadores (opcional)", self.ambitos, "csv"),
        ):
            self.field(naming, label, var, kind)
        ttk.Label(naming, text="Os originais são preservados. Revê os nomes e avisos; "
                  "seleciona apenas os documentos que aprovas.", wraplength=700).pack(anchor="w", pady=8)
        self.table = ttk.Treeview(naming, columns=("original", "name", "state", "warnings"),
                                 show="headings", selectmode="extended", height=7)
        for key, label, width in (("original", "PDF original", 140), ("name", "Nome proposto", 360), ("state", "Estado", 100),
                                  ("warnings", "Avisos / motivo", 350)):
            self.table.heading(key, text=label)
            self.table.column(key, width=width)
        self.table.pack(fill="both", expand=True)
        horizontal = ttk.Scrollbar(naming, orient="horizontal", command=self.table.xview)
        horizontal.pack(fill="x")
        self.table.configure(xscrollcommand=horizontal.set)
        self.table.bind("<Double-1>", self.details)
        actions = ttk.Frame(naming)
        actions.pack(fill="x", pady=8)
        self.preview_button = ttk.Button(actions, text="Preparar / atualizar nomes", command=self.preview)
        self.preview_button.pack(side="left")
        self.apply_button = ttk.Button(actions, text="Aprovar e copiar selecionados",
                                       command=self.apply, state="disabled")
        self.apply_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Usar esta pasta na conversão", command=self.use_destination).pack(side="left")
        for frame in (collect, naming):
            ttk.Label(frame, textvariable=self.status, wraplength=720).pack(anchor="w", pady=8)
        self.snapshot = None
        self.approved_snapshot = None
        self.poll(notebook)

    @staticmethod
    def field(frame, label, var, kind):
        ttk.Label(frame, text=label).pack(anchor="w", pady=(8, 0))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)

        def choose(folder=False):
            if folder or kind == "folder":
                chosen = filedialog.askdirectory()
            elif kind == "jsonl":
                chosen = filedialog.asksaveasfilename(defaultextension=".jsonl")
            else:
                chosen = filedialog.askopenfilename(filetypes=[(kind.upper(), f"*.{kind}")])
            if chosen:
                var.set(chosen)

        ttk.Button(row, text="Escolher…", command=choose).pack(side="left")
        if kind == "xlsx":
            ttk.Button(row, text="Pasta…", command=lambda: choose(True)).pack(side="left")

    def values(self):
        return tuple(v.get().strip() for v in
                     (self.register, self.destination, self.siglas, self.ambitos))

    def submit(self, job, done):
        if self.busy:
            return
        self.busy = True
        for button in (self.collect_button, self.preview_button, self.apply_button):
            button.configure(state="disabled")
        self.status.set("A executar…")

        def worker():
            try:
                self.events.put((done, job(), None))
            except Exception as exc:
                self.events.put((None, None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def collect(self):
        if not all(v.get().strip() for v in (self.indices, self.downloads, self.register)):
            messagebox.showerror("Campos em falta", "Indica índices, destino e registo.")
            return
        indices, downloads, register = map(Path, (self.indices.get(), self.downloads.get(), self.register.get()))
        network = self.network.get()  # explícito; não herda CRL_RECOLHA_REDE
        if network and not messagebox.askyesno("Recolha do BTE", "Autorizar a descarga dos PDFs indicados nos índices?"):
            return
        self.reviewed = False

        def job():
            files = sorted(indices.glob("*.xlsx")) if indices.is_dir() else [indices]
            files = [p for p in files if p.is_file() and not p.name.startswith("~$")]
            if not files:
                raise ValueError("Não foram encontrados índices Excel.")
            result = recolher(files, downloads, Registo.carregar(register), rede=network)
            return resumo_recolha(result, rede=network)

        self.submit(job, lambda text: self.status.set(text))

    @staticmethod
    def naming_job(values, selected=None):
        register, destination, siglas, ambitos = values
        if not register or not destination:
            raise ValueError("Indica o registo e a pasta das cópias nomeadas.")
        for value in (siglas, ambitos):
            if value and not Path(value).is_file():
                raise ValueError(f"CSV não encontrado: {value}")
        reg = Registo.carregar(Path(register))
        if not reg.entradas:
            raise ValueError("Registo vazio; recolhe os documentos primeiro.")
        result = nomear(reg, Path(destination), aplicar=selected is not None,
                        tabela=tabela_de_siglas([Path(siglas)] if siglas else []),
                        vocabulario_ambito=carregar_vocabulario(Path(ambitos)) if ambitos else {},
                        confirmados=selected)
        return result, reg

    @staticmethod
    def review_fingerprint(values):
        register, _destination, siglas, ambitos = values
        return tuple(Path(path).read_bytes() if path else None
                     for path in (register, siglas, ambitos))

    def preview(self):
        values = self.values()
        self.snapshot = values
        self.reviewed = False
        self.submit(lambda: self.naming_job(values), self.show_names)

    def show_names(self, data):
        result, reg = data
        self.table.delete(*self.table.get_children())
        for key, entry in sorted(reg.entradas.items()):
            name = entry.get("nomeacao", {})
            self.table.insert("", "end", iid=key, values=(entry.get("ficheiro") or Path(entry.get("descarga", {}).get("caminho", "")).name,
                              name.get("doc_id", ""),
                              name.get("estado", "sem_origem"), "\n".join(name.get("avisos", []))))
        self.status.set(texto_resumo(result, aplicar=False))
        self.reviewed = True
        self.approved_snapshot = self.review_fingerprint(self.snapshot)

    def apply(self):
        selected = set(self.table.selection())
        if not self.reviewed or self.values() != self.snapshot:
            messagebox.showerror("Atualizar nomes", "Atualiza a proposta depois de alterar os campos.")
            return
        if not selected:
            messagebox.showerror("Selecionar documentos", "Seleciona os nomes que aprovas na lista.")
            return
        if not messagebox.askyesno("Confirmar nomes", f"Aprovas os nomes e avisos dos {len(selected)} documentos selecionados?"):
            return
        values, previous = self.snapshot, self.approved_snapshot

        def job():
            if self.review_fingerprint(values) != previous:
                raise ValueError("O registo ou os CSV mudaram; atualiza os nomes antes de aprovar.")
            return self.naming_job(values, selected)

        self.reviewed = False
        self.submit(job, self.applied)

    def applied(self, data):
        self.show_names(data)
        self.status.set(texto_resumo(data[0], aplicar=True))

    def details(self, _event=None):
        selection = self.table.selection()
        if selection:
            original, name, state, warnings = self.table.item(selection[0], "values")
            messagebox.showinfo("Revisão do documento", f"Original: {original}\n\nNome proposto: {name}\n\nEstado: {state}\n\n{warnings}")

    def use_destination(self):
        path = Path(self.destination.get())
        if not path.is_dir() or not any(path.rglob("*.pdf")):
            messagebox.showerror("Sem PDFs nomeados", "Aprova e copia os documentos antes da conversão.")
            return
        self.source.set(str(path))
        self.status.set("Pasta transferida para o passo 3. Escolhe a saída e constrói o Markdown.")

    def poll(self, notebook):
        try:
            done, data, error = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            if error:
                self.status.set(f"Erro: {error}")
                messagebox.showerror("Operação interrompida", error)
            elif done:
                done(data)
            self.collect_button.configure(state="normal")
            self.preview_button.configure(state="normal")
            self.apply_button.configure(state="normal" if self.reviewed else "disabled")
        notebook.after(100, lambda: self.poll(notebook))
