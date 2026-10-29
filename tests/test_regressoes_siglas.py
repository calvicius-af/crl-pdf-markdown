import pytest

from crl_markdown import nomeacao, recolha
from crl_markdown.cli import main


@pytest.mark.parametrize('name,expected', [
    ('Auto-Estradas de Portugal - BRISA, SA', 'BRISA'),
    ('Associação Nacional - ANESA, Lda', 'ANESA'),
    ('Companhia - LUSA, Lda', 'LUSA'),
    ('Metro - STEM, Lda', 'STEM'),
    ('Companhia - APSA, S.A.', 'APSA'),
    ('Companhia - INCM, SA', 'INCM'),
    ('Companhia - INCM, SA, EPE', 'INCM'),
    ('Companhia - ACRL, CRL', 'ACRL'),
])
def test_legal_form_never_eats_the_literal_acronym(name, expected):
    assert nomeacao.sigla(name, {}) == (expected, None)


def test_legacy_cli_uses_explicit_vocabulary_instead_of_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'siglas.csv').write_text('nome;sigla;estado\nSindicato Exemplo;ANTIGA;confirmada\n', encoding='utf-8')
    chosen = tmp_path / 'selecionado.csv'
    chosen.write_text('nome;sigla;estado\nSindicato Exemplo;NOVA;confirmada\n', encoding='utf-8')
    registry = tmp_path / 'registo.jsonl'
    registry.write_text('', encoding='utf-8')
    # O adaptador público fornece a tabela ao motor partilhado de nomeação.
    captured = {}
    def naming(*args, **kwargs):
        captured.update(kwargs)
        return {'siglas_pendentes': {}, 'nomes': [], 'por_estado': {}, 'avisos': [],
                'problemas': [], 'ordinais_novos': 0}
    monkeypatch.setattr(nomeacao, 'nomear', naming)
    index = tmp_path / 'indice.xlsx'
    index.write_bytes(b'fixture')
    monkeypatch.setattr(recolha, 'recolher', lambda *a, **k: {'problemas': [], 'por_estado': {}})
    monkeypatch.setattr(recolha, 'texto_resumo', lambda *a, **k: '')
    monkeypatch.setattr(nomeacao, 'texto_resumo', lambda *a, **k: '')
    assert main(['collect', '--indices', str(index), '--registo', str(registry),
                 '--siglas', str(chosen)]) == 0
    assert nomeacao.sigla('Sindicato Exemplo', captured['tabela']) == ('NOVA', None)
