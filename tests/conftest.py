import pytest


@pytest.fixture(autouse=True)
def isolated_user_profile(tmp_path_factory, monkeypatch):
    """Preferências locais (responsável, lotes recentes) nunca tocam no perfil real."""
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path_factory.mktemp('perfil')))


def tk_root():
    """Janela Tk para os ensaios; o runner Windows às vezes não lê o init.tcl à primeira.

    A falha («Can't find a usable init.tcl … No error») é do ambiente do CI e
    não do código: tenta-se de novo e, se persistir, o ensaio é ignorado.
    """
    import time
    import tkinter as tk
    for attempt in range(3):
        try:
            return tk.Tk()
        except tk.TclError as error:
            if 'init.tcl' not in str(error) and 'display' not in str(error).lower():
                raise
            time.sleep(.5 * (attempt + 1))
    pytest.skip('Tk indisponível neste ambiente de ensaio')
