"""Ensaio de ponta a ponta no runtime instalado, numa pasta como a da estação CRL.

Corre o fluxo que a pessoa usa, sem rede e com os modelos locais: converter,
reauditar, OCR dirigido a uma página, marcar falso alarme na janela de
revisão, corrigir com o PDF ao lado, aprovar um a um e em lote, entregar e
exportar uma cópia de revisão. A pasta de saída imita a da estação (nome
longo, acentos e espaços), para que as subpastas de auditoria passem os 260
caracteres do Windows.

Uso: python -I -X utf8 -B -m crl_markdown.ensaio_completo --pdfs PASTA --out PASTA
"""

import argparse
import json
import shutil
import time
import traceback
from pathlib import Path

ESTACAO = ('eSocial/Centro de Relações Laborais - Negociação Coletiva/'
           'RNC_Dados_2026 - Cópia/2_processamento/texto')


def _wait(root, view, seconds=900):
    deadline = time.monotonic() + seconds
    while view.busy and time.monotonic() < deadline:
        root.update()
        time.sleep(.05)
    root.update()
    if view.busy:
        raise RuntimeError('A janela de revisão não terminou a tarefa a tempo.')


def _new_root(tk):
    # O Tcl do Windows falha por vezes a ler o init.tcl à primeira tentativa.
    for attempt in range(3):
        try:
            return tk.Tk()
        except tk.TclError:
            if attempt == 2:
                raise
            time.sleep(.5 * (attempt + 1))


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def _leaks(folder):
    from .caminhos import PREFIX
    found = []
    for path in Path(folder).rglob('*'):
        if path.is_file() and path.suffix in {'.json', '.md', '.txt', '.log'}:
            if PREFIX in path.read_text(encoding='utf-8', errors='replace'):
                found.append(str(path))
    return found


def check(pdfs: Path, out: Path, *, models=None, steps=None, converter=None, ocr=True):
    """Devolve a evidência; levanta exceção no primeiro passo que falhar."""
    steps = [] if steps is None else steps

    def step(name, **details):
        steps.append({'passo': name, **details})

    from .release_check import converter as factory
    if converter is None:
        from .desktop import prepare_environment
        resources = prepare_environment()
        from .release_check import block_network
        block_network()
        models = Path(models) if models else resources / 'modelos'
    from .caminhos import longpath
    from .pipeline import Options, run
    output = out / ESTACAO
    deepest = 0

    reports = run(pdfs, output, Options(models=models, offline=True), converter_factory=factory,
                  converter=converter, progress=lambda _line: None)
    failed = [r['relative_source'] for r in reports if r.get('state') == 'falhou']
    if failed or not reports:
        raise RuntimeError(f'Conversão falhou: {failed or "sem documentos"}')
    occurrences = list(longpath(output / '_auditoria/ocorrencias').rglob('*.json'))
    if len(occurrences) < len(reports):
        raise RuntimeError('O histórico de ocorrências não foi gravado para todos os documentos.')
    deepest = max(len(str(p)) for p in occurrences)
    step('conversao', documentos=len(reports), estados=sorted({r['quality_status'] for r in reports}),
         caminho_mais_longo=deepest)

    from .reaudit import reaudit
    _destination, again = reaudit(output, out / 'reauditoria', jobs=1, progress=lambda _line: None)
    if any(r.get('state') == 'falhou' for r in again):
        raise RuntimeError('A reauditoria falhou.')
    step('reauditoria', documentos=len(again))

    relatives = [r['relative_source'] for r in reports]
    if ocr:
        from .page_ocr import reextract_pages
        publication, _report = reextract_pages(output, relatives[0], 'Ensaio automático', models, [1],
                                               progress=lambda _line: None)
        step('ocr_dirigido', documento=relatives[0], publicacao=len(str(publication)))

    import tkinter as tk
    from tkinter import messagebox
    errors = []
    messagebox.askyesno = lambda *a, **k: True
    messagebox.askyesnocancel = lambda *a, **k: False
    messagebox.showinfo = lambda *a, **k: None
    messagebox.showerror = lambda title, message, **k: errors.append(f'{title}: {message}')
    from .review_app import ReviewWindow
    root = _new_root(tk)
    root.withdraw()
    try:
        view = ReviewWindow(root, output)
        view.reviewer.set('Ensaio automático')
        view.selected.set(relatives[-1])
        view.refresh()
        root.update()
        view.edit_revision()
        root.update()
        editor, _guard = view.editors[view.revision]
        if not any(isinstance(w, tk.Canvas) and w.find_all() for w in _descendants(editor)):
            raise RuntimeError('A janela de correção não mostrou a página do PDF.')
        step('correcao_lado_a_lado', documento=relatives[-1])
        editor.destroy()
        view.editors.clear()
        pending = [d['relative_source'] for d in view.documents if d.get('quality_status') != 'passed']
        for relative in pending:
            view.selected.set(relative)
            view.refresh()
            root.update()
            if view.current[2]['quality_status'] != 'passed':
                view.resolve()
                _wait(root, view)
            if errors:
                raise RuntimeError('Falso alarme: ' + '; '.join(errors))
            if view.current[2]['quality_status'] == 'blocked':
                raise RuntimeError(f'O falso alarme não desbloqueou {relative}.')
            view.record('aprovado')
            if errors:
                raise RuntimeError('Aprovação: ' + '; '.join(errors))
        step('falso_alarme_e_aprovacao', documentos=len(pending))
        view.approve_clean()
        _wait(root, view)
        if errors:
            raise RuntimeError('Aprovação: ' + '; '.join(errors))
        step('aprovacao_em_lote')
    finally:
        root.destroy()

    from .validation import decide, deliver, review_head
    for relative in relatives:
        if review_head(output, relative) is None:
            decide(output, relative, reviewer='Ensaio automático', decision='aprovado', scope='integral',
                   notes='Conferido no ensaio automático.')
    report = deliver(output, out / 'entrega')
    delivered = list((report.parent / 'documentos').rglob('*.md'))
    if len(delivered) != len(relatives):
        raise RuntimeError(f'Entrega incompleta: {len(delivered)} de {len(relatives)}.')
    step('entrega', documentos=len(delivered))

    from .review_exchange import export_review
    branch = export_review(output, out / 'copia-revisao', reviewer='Pessoa B')
    step('copia_de_revisao', pasta=str(branch))

    leaks = [*_leaks(output), *_leaks(report.parent)]
    if leaks:
        raise RuntimeError('Caminhos internos do Windows ficaram nos relatórios: ' + ', '.join(leaks[:5]))
    step('relatorios_sem_prefixo')
    return steps


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdfs', type=Path, required=True, help='Pasta com os PDF de ensaio')
    parser.add_argument('--out', type=Path, required=True, help='Pasta nova para o ensaio')
    parser.add_argument('--modelos', type=Path, help='Por omissão, os modelos instalados')
    args = parser.parse_args(argv)
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    steps = []
    evidence = args.out / 'ensaio_completo.json'
    try:
        check(args.pdfs, args.out, models=args.modelos, steps=steps)
    except BaseException:
        evidence.write_text(json.dumps({'status': 'falhou', 'passos': steps, 'erro': traceback.format_exc()},
                                       ensure_ascii=False, indent=2), encoding='utf-8')
        raise
    from . import __version__
    evidence.write_text(json.dumps({'status': 'passou', 'versao': __version__, 'passos': steps},
                                   ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
