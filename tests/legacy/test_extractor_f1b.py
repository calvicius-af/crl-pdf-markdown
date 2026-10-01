"""Testes do 2.º ciclo da Fase 1 — memos MaxQDA de 05/07 (2.ª ronda) + tabelas.

- Anotação 1: rodapés "BTE n | página" não podem sobreviver no texto;
- Anotações 2 e 3: sem linhas em branco no texto final (leitura compacta;
  a remoção de um rodapé a meio de cláusula não deixa quebra extra);
- Pedido novo: tabelas mantêm estrutura (linhas com células separadas por " | ").
"""
from pathlib import Path

import pytest

from crl_markdown.legacy.extractor import (extrair_pdf, estruturar, juntar_linhas,
                           _remover_cabecalhos_rodapes, MARCA_TABELA_INI,
                           MARCA_TABELA_FIM)

PDF_BTE = Path(__file__).parents[2] / "data" / "raw" / "bte" / "bte2_2025.pdf"


def test_rodape_bte_removido():
    paginas = ["Texto útil da cláusula\nBTE 2 | 49\nMais texto útil",
               "Outra página\nBTE 2 | 50"]
    limpas = _remover_cabecalhos_rodapes(paginas)
    junto = "\n".join(limpas)
    assert "BTE 2 | 49" not in junto and "BTE 2 | 50" not in junto
    assert "Texto útil da cláusula" in junto


def test_sem_linhas_em_branco_no_texto_final():
    texto = ("Preâmbulo da convenção.\n\n\nCláusula 1.ª\nÂmbito\n\n"
             "1- Primeiro número.\n\n2- Segundo número.\n")
    _doc, saida = estruturar(texto, doc_id="t")
    assert "\n\n" not in saida


def test_juntar_nao_toca_em_linhas_de_tabela():
    texto = (f"Os valores passam a ser\n{MARCA_TABELA_INI}\n"
             "Nível | Grupo A | Grupo B\nXV | 2728 | 2496\n"
             f"{MARCA_TABELA_FIM}\ntexto seguinte")
    saida = juntar_linhas(texto)
    assert "Nível | Grupo A | Grupo B\nXV | 2728 | 2496" in saida


@pytest.fixture(scope="module")
def extraido():
    return extrair_pdf(PDF_BTE, paginas=(15, 49),
                       doc_id="25_CCT_BTE_02_ACIP_FESAHT")


@pytest.mark.skipif(not PDF_BTE.exists(), reason="bte2_2025.pdf não disponível")
class TestPdfReal:
    def test_sem_rodapes_bte(self, extraido):
        _doc, texto = extraido
        import re
        assert not re.search(r"BTE\s+\d+\s*\|\s*\d+", texto)

    def test_sem_linhas_em_branco(self, extraido):
        _doc, texto = extraido
        assert "\n\n" not in texto

    def test_tabelas_com_estrutura(self, extraido):
        _doc, texto = extraido
        linhas_tabela = [l for l in texto.split("\n") if l.count(" | ") >= 2]
        assert len(linhas_tabela) >= 10  # tabelas de remuneração do anexo

    def test_zero_perda_mantida(self, extraido):
        doc, texto = extraido
        folhas = [n for n in doc["nos"] if n.get("folha")]
        assert "".join(texto[n["char_start"]:n["char_end"]] for n in folhas) == texto
