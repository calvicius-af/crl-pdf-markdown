"""Heurísticas de duas colunas: nomes, justificação e fronteiras (#27).

Os limites estão nomeados em cct/extractor.py (palavras do pdfplumber) e em
cct/extractor_docling.py (blocos do docling). Estes testes fixam o
comportamento exatamente nos limites, com páginas falsas: um lado do limite
é uma página em colunas, o outro não.
"""
from types import SimpleNamespace

from crl_markdown.legacy import extractor as E
from crl_markdown.legacy import extractor_docling as D

LARGURA = 600.0


class _Pagina:
    """Página falsa com o que `_duas_colunas` lê: palavras, bbox, traços, tabelas."""

    def __init__(self, palavras):
        self._palavras = palavras
        self.bbox = (0.0, 0.0, LARGURA, 842.0)
        self.horizontal_edges: list = []

    def extract_words(self):
        return self._palavras

    def find_tables(self):
        return []


def _palavras(esquerda: int, direita: int, atravessam: int = 0) -> list[dict]:
    meio = LARGURA / 2
    return ([{"x0": 50.0, "x1": 90.0}] * esquerda + [{"x0": meio + 50, "x1": meio + 90}] * direita
            + [{"x0": meio - 30, "x1": meio + 30}] * atravessam)


def test_colunas_pdfplumber_minimo_de_palavras():
    n = E.MIN_PALAVRAS_COLUNAS
    assert E._duas_colunas(_Pagina(_palavras(n // 2, n - n // 2))) == LARGURA / 2
    assert E._duas_colunas(_Pagina(_palavras(n // 2, n - n // 2 - 1))) is None


def test_colunas_pdfplumber_palavras_a_atravessar_a_goteira():
    # 100 palavras: abaixo de 2% a atravessar é uma página em colunas
    assert E._duas_colunas(_Pagina(_palavras(50, 49, atravessam=1))) == LARGURA / 2
    assert E._duas_colunas(_Pagina(_palavras(49, 49, atravessam=2))) is None


def test_colunas_pdfplumber_cada_metade_com_um_quarto():
    assert E._duas_colunas(_Pagina(_palavras(74, 26))) == LARGURA / 2
    assert E._duas_colunas(_Pagina(_palavras(75, 25))) is None


def _caixas(esquerda: int, direita: int, atravessam: int = 0) -> list:
    meio = LARGURA / 2
    return ([SimpleNamespace(l=50.0, r=250.0)] * esquerda
            + [SimpleNamespace(l=meio + 30, r=meio + 250)] * direita
            + [SimpleNamespace(l=100.0, r=500.0)] * atravessam)


def test_colunas_docling_minimo_de_blocos():
    n = D.MIN_CAIXAS_COLUNAS
    assert D._duas_colunas(_caixas(n // 2, n - n // 2), LARGURA)
    assert not D._duas_colunas(_caixas(n // 2, n - n // 2 - 1), LARGURA)


def test_colunas_docling_blocos_a_atravessar_e_um_quarto_por_metade():
    assert D._duas_colunas(_caixas(50, 46, atravessam=4), LARGURA)       # 4% < 5%
    assert not D._duas_colunas(_caixas(50, 45, atravessam=5), LARGURA)   # 5%
    assert D._duas_colunas(_caixas(74, 26), LARGURA)
    assert not D._duas_colunas(_caixas(75, 25), LARGURA)
