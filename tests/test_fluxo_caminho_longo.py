"""Fluxo completo numa pasta de saída com nome longo, acentos e espaços.

Reproduz a estação CRL: a pasta sincronizada do SharePoint já tem cerca de
120 caracteres e as subpastas de auditoria (ocorrências, correções) passam os
260 caracteres que o Windows aceita por omissão. No Windows, este teste corre
com o prefixo estendido; noutros sistemas confirma o mesmo fluxo.
"""

import json
import os
from types import SimpleNamespace

import pytest
from docling_core.types.doc import DocItemLabel, DoclingDocument, Size

from crl_markdown.caminhos import PREFIX
from crl_markdown.diagnostics import explain
from crl_markdown.pipeline import Options, run
from crl_markdown.reaudit import reaudit
from crl_markdown.review_exchange import export_review
from crl_markdown.revisions import audit_revision, create_revision
from crl_markdown.validation import decide, deliver
from tests.pdf_sintetico import escrever_pdf, pagina_bte

ESTACAO = ('eSocial/Centro de Relações Laborais - Negociação Coletiva/'
           'RNC_Dados_2026 - Cópia/2_processamento/texto')


def _converter(lines):
    document = DoclingDocument(name='Ensaio')
    document.add_page(page_no=1, size=Size(width=595, height=842))
    for value in lines:
        document.add_text(label=DocItemLabel.TEXT, text=value.replace('-125,00', '125,00'))
    return SimpleNamespace(docling_version='fixture',
                           convert=lambda _pdf: SimpleNamespace(status='success', document=document))


def _text_files(folder):
    return [p for p in folder.rglob('*') if p.is_file() and p.suffix in {'.json', '.md', '.txt', '.log'}]


def test_full_flow_in_deep_output_folder(tmp_path):
    lines = ['Convenção de ensaio', 'Cláusula 1.ª', 'Retribuição',
             '1- O saldo é -125,00 euros.', 'Depositado em 1 de janeiro de 2026.']
    source = tmp_path / 'fontes' / 'APU'
    source.mkdir(parents=True)
    name = '2026_BTE_03_APU_034_ACT_ACEP1-2026_FreguesiaVilaNova-STAL.pdf'
    escrever_pdf(source / name, [pagina_bte(1, lines)])
    output = tmp_path / ESTACAO
    reports = run(source.parent, output, Options(), converter=_converter(lines), progress=lambda _: None)
    assert [r['state'] for r in reports] != ['falhou']
    relative = 'APU/' + name
    occurrences = list((output / '_auditoria/ocorrencias').rglob('*.json'))
    assert occurrences, 'O histórico de ocorrências tem de ser gravado.'

    _new, again = reaudit(output, tmp_path / 'reauditoria', jobs=1, progress=lambda _: None)
    assert again[0]['quality_status'] == reports[0]['quality_status']

    revision = create_revision(output, relative, 'Revisor de ensaio')
    draft = revision / 'correcao.md'
    draft.write_text(draft.read_text(encoding='utf-8').replace('125,00', '-125,00'), encoding='utf-8')
    publication, corrected = audit_revision(revision)
    assert corrected['quality_status'] != 'blocked'
    decide(output, relative, reviewer='Revisor de ensaio', decision='aprovado', scope='integral',
           notes='Sinal negativo conferido no PDF.')
    delivered = deliver(output, tmp_path / 'entrega')
    assert (delivered.parent / 'documentos' / 'APU' / (name[:-4] + '.md')).is_file()
    branch = export_review(output, tmp_path / 'copia-revisao', reviewer='Pessoa B')

    # O prefixo do Windows é interno: nunca fica nos relatórios nem nos caminhos devolvidos.
    for path in (revision, publication, delivered, branch):
        assert not str(path).startswith(PREFIX)
    for folder in (output, tmp_path / 'reauditoria', delivered.parent, branch):
        for path in _text_files(folder):
            assert PREFIX not in path.read_text(encoding='utf-8', errors='replace'), path
    manifest = json.loads((output / '_auditoria/manifest.json').read_text(encoding='utf-8'))
    assert not manifest['output'].startswith(PREFIX)


def test_long_path_error_gets_its_own_guidance():
    error = FileNotFoundError(3, 'O sistema não conseguiu localizar o caminho especificado',
                              'C:\\' + 'a' * 300, None, 3)
    error.winerror = 3
    assert explain(error)['code'] == 'CRL-CAMINHO-LONGO'
    assert explain(FileNotFoundError(2, 'x', 'C:\\curto'))['code'] == 'CRL-FICHEIRO'


@pytest.mark.skipif(os.environ.get('CRL_TEST_TK') != '1', reason='Ensaio Tk explícito numa sessão gráfica')
def test_end_to_end_check_drives_review_window(tmp_path, monkeypatch):
    from tkinter import messagebox

    from crl_markdown.ensaio_completo import check
    from tests.conftest import tk_root
    tk_root().destroy()  # Ignorar o ensaio se o Tk do runner não arrancar.
    for name in ('askyesno', 'askyesnocancel', 'showinfo', 'showerror'):
        monkeypatch.setattr(messagebox, name, getattr(messagebox, name))
    lines = ['Convenção de ensaio', 'Cláusula 1.ª', 'Retribuição',
             '1- O saldo é -125,00 euros.', 'Depositado em 1 de janeiro de 2026.']
    pdfs = tmp_path / 'pdfs'
    pdfs.mkdir()
    escrever_pdf(pdfs / 'bloqueado.pdf', [pagina_bte(1, lines)])
    escrever_pdf(pdfs / 'limpo.pdf', [pagina_bte(1, ['Convenção limpa', 'Cláusula 1.ª', 'Texto corrente.'])])
    steps = check(pdfs, tmp_path / 'ensaio', converter=_converter(lines), ocr=False)
    names = [s['passo'] for s in steps]
    assert names[0] == 'conversao' and names[-1] == 'relatorios_sem_prefixo'
