"""Progresso medido por documentos concluídos e estimativa baseada na corrida atual."""

import re
import time


class ProgressReporter:
    """Observa o protocolo de progresso existente, sem mudar as regras de extração.

    Cada callback corresponde a uma mensagem completa do pipeline. Só uma
    mensagem de estado terminal conta um documento como processado.
    """

    def __init__(self, log, event):
        self.log, self.event = log, event
        self.total = 0
        self.current = 0
        self.completed = 0

    def __call__(self, line):
        self.log(line)
        batch = re.match(r"^Corrida [\w-]+: (\d+) PDF de ", line)
        document = re.match(r"^\[(\d+)/(\d+)\] (.+)$", line)
        terminal = re.match(r"^  (?:sem_alertas_automaticos|rever|falhou)(?:\s|:|$)", line)
        stage, name = None, ""
        if batch:
            self.total = int(batch[1])
            self.current = self.completed = 0
            stage = "preparing"
        elif document:
            self.current, self.total = int(document[1]), int(document[2])
            name = document[3]
            stage = "converting"
        elif terminal and self.current:
            self.completed = self.current
            stage = "completed_document"
        elif line.startswith("Relatório consolidado:"):
            stage = "finalizing"
        if stage and self.total:
            self.event({"stage": stage, "completed": self.completed,
                        "total": self.total, "document": name})


def duration(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class OperationProgress:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = None
        self.finished = None
        self.total = None
        self.completed = 0
        self.phase = "Pronto para começar"
        self.document = ""
        self.active = False
        self.failed = False

    def begin(self, label):
        self.started = self.clock()
        self.finished = None
        self.total = None
        self.completed = 0
        self.phase = label
        self.document = ""
        self.active = True
        self.failed = False

    def update(self, event):
        stage = event["stage"]
        self.total = event.get("total", self.total)
        self.completed = event.get("completed", self.completed)
        self.document = event.get("document", "")
        self.phase = {
            "preparing": "A preparar a conversão",
            "converting": "A processar e conferir o documento",
            "completed_document": "Documento processado",
            "finalizing": "A guardar os relatórios do lote",
        }.get(stage, self.phase)

    def finish(self, failed=False):
        self.finished = self.clock()
        self.active = False
        self.failed = failed or self.failed
        self.phase = "A operação não terminou" if self.failed else "Operação concluída"
        self.document = ""

    def snapshot(self):
        end = self.clock() if self.finished is None else self.finished
        elapsed = 0 if self.started is None else max(0, end - self.started)
        percent = None if not self.total else min(100, 100 * self.completed / self.total)
        remaining = None
        if self.active and self.total and 0 < self.completed < self.total:
            remaining = elapsed * (self.total - self.completed) / self.completed
        return {"phase": self.phase, "document": self.document, "total": self.total,
                "completed": self.completed, "percent": percent,
                "elapsed": elapsed, "remaining": remaining, "active": self.active,
                "failed": self.failed}
