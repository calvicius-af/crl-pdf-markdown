import os
import time
import tkinter as tk

import pytest

from crl_markdown.review_app import ReviewWindow, load_document
from crl_markdown.validation import _load
from tests.test_desktop_distribution import (
    collect_destroyed_tk_windows_on_main_thread,  # noqa: F401
)
from tests.test_revisions import damaged_output  # noqa: F401
from tests.test_validation import reviewed_output  # noqa: F401


def test_review_view_verifies_current_content_and_finding_ids(damaged_output):  # noqa: F811
    document = _load(damaged_output)['documents'][0]
    target, report_path, report, expected = load_document(damaged_output, document)
    assert target.is_file() and report_path.is_file()
    assert expected['markdown_sha256'] == report['markdown_sha256']
    assert all(f.get('id') for f in report['findings'])


@pytest.mark.skipif(os.environ.get('CRL_TEST_TK') != '1', reason='Ensaio Tk explícito numa sessão gráfica')
def test_native_review_window_opens_editor_and_blocks_unresolved_errors(damaged_output):  # noqa: F811
    root = tk.Tk()
    root.title('CRL — ensaio temporário')
    try:
        view = ReviewWindow(root, damaged_output)
        root.update()
        assert view.window.winfo_ismapped()
        assert view.approve.winfo_ismapped()
        assert view.approve.winfo_rooty() + view.approve.winfo_height() <= (
            view.window.winfo_rooty() + view.window.winfo_height())
        assert str(view.approve['state']) == 'disabled'
        assert 'Bloqueado' in view.status.get()
        assert len(view.findings.get_children()) > 0
        view.reviewer.set('Revisor de ensaio')
        view.edit_revision()
        root.update()
        assert view.revision is not None
        assert (view.revision / 'correcao.md').is_file()
        deadline = time.monotonic() + 3
        seen = []
        view.task(lambda: 'done', lambda value: seen.append(value))
        while not seen and time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert seen == ['done']
        assert not view.busy
    finally:
        root.destroy()


@pytest.mark.skipif(os.environ.get('CRL_TEST_TK') != '1', reason='Ensaio Tk explícito numa sessão gráfica')
def test_editor_and_parent_close_preserve_unsaved_edits(damaged_output, monkeypatch):  # noqa: F811
    root = tk.Tk()
    try:
        view = ReviewWindow(root, damaged_output)
        view.reviewer.set('Pessoa de ensaio')
        view.edit_revision()
        editor, _guard = view.editors[view.revision]

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        text = next(w for w in descendants(editor) if isinstance(w, tk.Text))
        text.insert('end', '\nCorreção por guardar')
        monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: None)
        view.close()
        root.update()
        assert editor.winfo_exists() and view.window.winfo_exists()
        assert not root.review_close_guards[0]()
        monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: True)
        assert root.review_close_guards[0]()
        assert 'Correção por guardar' in (view.revision / 'correcao.md').read_text(encoding='utf-8')
    finally:
        root.destroy()


@pytest.mark.skipif(os.environ.get('CRL_TEST_TK') != '1', reason='Ensaio Tk explícito numa sessão gráfica')
def test_review_notes_can_be_saved_and_reopened_without_approval(damaged_output, monkeypatch):  # noqa: F811
    root = tk.Tk()
    try:
        view = ReviewWindow(root, damaged_output)
        view.reviewer.set('Pessoa A')
        view.notes.insert('1.0', 'Conferência por concluir na página 1.')
        monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: None)
        assert not view.can_close()
        monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: True)
        view.close()
        reopened = ReviewWindow(root, damaged_output)
        assert reopened.notes.get('1.0', 'end-1c') == 'Conferência por concluir na página 1.'
        assert reopened.reviewer.get() == ''  # Não atribuir a outra pessoa a autoria de quem abre agora.
        assert not reopened.integral.get()
        assert not list((damaged_output / '_auditoria/revisoes').rglob('*.json'))
    finally:
        root.destroy()


@pytest.mark.skipif(os.environ.get('CRL_TEST_TK') != '1', reason='Ensaio Tk explícito numa sessão gráfica')
def test_switch_document_can_cancel_or_save_notes_and_stale_decision_is_refused(reviewed_output, monkeypatch):  # noqa: F811
    from tests.test_review_exchange import add_second
    add_second(reviewed_output)
    root = tk.Tk()
    messages = []
    monkeypatch.setattr('tkinter.messagebox.showinfo', lambda *a, **k: None)
    monkeypatch.setattr('tkinter.messagebox.showerror', lambda title, message, **k: messages.append(message))
    try:
        first = ReviewWindow(root, reviewed_output)
        second = ReviewWindow(root, reviewed_output)
        first.reviewer.set('Pessoa A')
        first.notes.insert('1.0', 'Notas da primeira pessoa.')
        monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: None)
        first.selected.set('b.pdf')
        first.refresh()
        assert first.selected.get() == 'a.pdf'
        monkeypatch.setattr('tkinter.messagebox.askyesnocancel', lambda *a, **k: True)
        first.selected.set('b.pdf')
        first.refresh()
        assert first.selected.get() == 'b.pdf'
        first.selected.set('a.pdf')
        first.refresh()
        assert first.notes.get('1.0', 'end-1c') == 'Notas da primeira pessoa.'
        first.integral.set(True)
        first.record('aprovado')
        second.reviewer.set('Pessoa B')
        second.notes.insert('1.0', 'Parecer concorrente.')
        second.integral.set(True)
        second.record('rejeitado')
        assert any('Outra pessoa' in m for m in messages)
        assert len(list((reviewed_output / '_auditoria/revisoes').rglob('*.json'))) == 1
    finally:
        root.destroy()


@pytest.mark.skipif(os.environ.get('CRL_TEST_TK') != '1', reason='Ensaio Tk explícito numa sessão gráfica')
def test_second_reviewer_gets_new_draft_with_own_authorship(damaged_output):  # noqa: F811
    import json

    from crl_markdown.revisions import audit_revision, create_revision
    first = create_revision(damaged_output, 'source.pdf', 'Pessoa A')
    path = first / 'correcao.md'
    path.write_text(path.read_text(encoding='utf-8').replace('125,00', '-125,00'), encoding='utf-8')
    audit_revision(first)
    before = path.read_bytes()
    root = tk.Tk()
    try:
        view = ReviewWindow(root, damaged_output)
        assert view.revision == first
        assert 'AMOUNTS' not in view.rule_values.values()
        view.reviewer.set('Pessoa B')
        view.edit_revision()
        assert view.revision != first
        assert json.loads((view.revision / 'revision.json').read_text(encoding='utf-8'))['reviewer'] == 'Pessoa B'
        assert path.read_bytes() == before
    finally:
        root.destroy()
