import os
import time
import tkinter as tk

import pytest

from crl_markdown.review_app import ReviewWindow, load_document
from crl_markdown.validation import _load
from tests.test_revisions import damaged_output  # noqa: F401


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
        assert 'blocked' in view.status.get()
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
