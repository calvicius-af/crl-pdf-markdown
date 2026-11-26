import json
import os

import pytest

from crl_markdown import settings
from tests.test_desktop_distribution import (
    collect_destroyed_tk_windows_on_main_thread,  # noqa: F401
)


def make_output(tmp_path, name):
    path = tmp_path / name
    (path / '_auditoria').mkdir(parents=True)
    (path / '_auditoria/manifest.json').write_text('{}', encoding='utf-8')
    return path


def test_last_review_and_all_previous_folders_survive_restart_without_changing_primary_paths(tmp_path):
    primary = make_output(tmp_path, 'principal')
    derived = make_output(tmp_path, 'reauditoria')
    recent = tmp_path / 'recentes.json'
    config = tmp_path / 'pastas.json'
    values = settings.defaults(tmp_path / 'dados')
    settings.save(values, config)
    before = config.read_bytes()
    for folder in (primary, derived, primary, derived):
        settings.remember_review(folder, 'projeto-a', recent)
    assert settings.last_review('projeto-a', recent) == str(derived)
    assert [r['folder'] for r in settings.recent_reviews('projeto-a', recent)] == [str(primary), str(derived)]
    assert settings.recent_reviews('projeto-b', recent) == []
    assert config.read_bytes() == before
    assert settings.load(config) == values


def test_unavailable_folder_does_not_erase_the_recent_record(tmp_path):
    folder = make_output(tmp_path, 'antigo')
    path = tmp_path / 'recentes.json'
    settings.remember_review(folder, 'projeto', path)
    folder.rename(tmp_path / 'movido')
    assert settings.last_review('projeto', path) is None
    assert settings.recent_reviews('projeto', path)[0]['folder'] == str(folder)


def test_corrupt_recent_index_is_preserved_and_reported(tmp_path):
    path = tmp_path / 'recentes.json'
    content = json.dumps({'schema': 1, 'folders': ['invalid']})
    path.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError, match='entradas inválidas'):
        settings.recent_reviews('projeto', path)
    assert path.read_text(encoding='utf-8') == content


@pytest.mark.skipif(os.environ.get('CRL_TEST_TK') != '1', reason='Ensaio Tk explícito numa sessão gráfica')
def test_app_reopens_last_review_and_lists_primary_and_derived_folders(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import ttk

    from crl_markdown import app

    primary = make_output(tmp_path, 'principal')
    derived = make_output(tmp_path, 'reauditoria')
    profile = tmp_path / 'perfil'
    monkeypatch.setattr(settings, 'user_folder', lambda: profile)
    values = settings.defaults(tmp_path / 'dados')
    values['markdown'] = str(primary)
    settings.save(values)
    settings.remember_review(derived, values['workspace'])
    root = tk.Tk()
    monkeypatch.setattr(app.tk, 'Tk', lambda: root)

    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)

    def inspect():
        try:
            entries = [w.get() for w in descendants(root) if isinstance(w, ttk.Entry)]
            assert str(derived) in entries
            button = next(w for w in descendants(root)
                          if isinstance(w, ttk.Button) and w.cget('text') == 'Lotes recentes…')
            button.invoke()
            listing = next(w for w in descendants(root) if isinstance(w, tk.Listbox))
            assert set(listing.get(0, 'end')) == {str(primary), str(derived)}
        finally:
            root.destroy()
    monkeypatch.setattr(root, 'mainloop', inspect)
    app.main(['--installed', '--offline', '--models', str(tmp_path / 'models')])
