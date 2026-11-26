"""Rascunhos com deteção de alterações concorrentes e proteção de fecho."""

from .locking import exclusive
from .pipeline import atomic_write


class DraftSession:
    def __init__(self, path):
        self.path = path
        self.saved = path.read_bytes()
        self.text = self.saved.decode('utf-8')

    def save(self, text):
        # O bloqueio do corpus coordena também exportações e importações.
        parent = self.path.parent
        lock = (parent.parents[3] / '_auditoria/.operacao.lock'
                if len(parent.parents) > 3 and parent.parents[1].name == 'correcoes'
                and parent.parents[2].name == '_auditoria' else parent / '.rascunho.lock')
        with exclusive(lock):
            if self.path.read_bytes() != self.saved:
                raise ValueError('O rascunho foi alterado noutra janela ou máquina. '
                                 'Conserve o seu texto numa cópia e reabra a versão atual; '
                                 'a gravação foi recusada para não perder alterações.')
            atomic_write(self.path, text)
            self.saved = self.path.read_bytes()
            self.text = text


def confirm_discard_or_save(parent, changed, save):
    """True permite fechar; Cancelar ou falha a guardar conserva a janela."""
    from tkinter import messagebox

    if not changed:
        return True
    answer = messagebox.askyesnocancel(
        'Alterações por guardar',
        'Há alterações por guardar. Quer guardá-las antes de continuar?\n\n'
        'Sim: guardar. Não: descartar as alterações. Cancelar: continuar a editar.',
        parent=parent)
    if answer is None:
        return False
    if answer:
        return save()
    return True
