"""Texto que está no PDF mas não se vê (cct/recorte.py).

GESAMB de 2025: um documento colado na página e recortado à volta de uma
tabela trazia, escondido, o texto de outra versão dos artigos, que o
pdfplumber lia entrelaçado com o visível. MaiaAmbiente de 2025: texto fora da
página, e camadas escondidas nas tabelas que davam a página como cega à
completude.
"""
from crl_markdown.legacy.completude import ler_referencia, medir_pdf
from crl_markdown.legacy.extractor import extrair_pdf
from tests.pdf_sintetico import escrever_pdf

VISIVEL = ["Artigo 10.º - Aquisição e requisição de fardamento",
           "4- O fardamento é entregue ao trabalhador no momento da admissão."]


def _pagina(*extra):
    return [(72, 760, VISIVEL[0]), (72, 740, VISIVEL[1]), *extra]


def test_texto_recortado_nao_entra_no_texto_nem_na_referencia(tmp_path):
    escondido = ("recortado", 72, 700, "1- O fardamento antigo, noutra versão.",
                 (72, 300, 500, 400))
    pdf = escrever_pdf(tmp_path / "x.pdf", [_pagina(escondido)])
    _doc, texto = extrair_pdf(pdf)
    assert "antigo" not in texto and "4- O fardamento é entregue" in texto, texto
    [referencia], _cegas = ler_referencia(pdf)
    assert "antigo" not in referencia
    assert medir_pdf("x", pdf, texto).cobertura == 1.0


def test_texto_fora_da_pagina_nao_entra(tmp_path):
    pdf = escrever_pdf(tmp_path / "x.pdf", [_pagina((72, -120, "Artigo 9.º de outra página"))])
    _doc, texto = extrair_pdf(pdf)
    assert "outra página" not in texto
    m = medir_pdf("x", pdf, texto)
    assert m.cobertura == 1.0 and not m.a_mais


def test_espaco_por_cima_de_uma_letra_nao_parte_a_palavra(tmp_path):
    """GESAMB de 2025: um espaço da camada escondida, por cima do «o» de
    «obrigam», dava «o brigam». Um espaço da própria fonte, no texto
    justificado, pode cair sobre a letra seguinte e continua a separar."""
    pdf = escrever_pdf(tmp_path / "x.pdf", [_pagina((72, 700, "obrigam à sua utilização."),
                                                    (73.5, 700, " ", "times"))])
    _doc, texto = extrair_pdf(pdf)
    assert "obrigam à sua utilização." in texto, texto
    pdf = escrever_pdf(tmp_path / "y.pdf", [_pagina((72, 700, "A"), (78.5, 700, "suspensão"),
                                                    (76, 700, " "))])
    _doc, texto = extrair_pdf(pdf)
    assert "A suspensão" in texto, texto


def test_ligaduras_e_hifenes_escondidos_tambem_saem():
    """O PDFium decompõe a ligadura «fi» em «f» e «i», na mesma origem, e dá
    o hífen de fim de linha como U+FFFE; o pdfplumber tem «fi» e «-». Sem as
    emparelhar, ficavam da camada escondida «1fi45» e «150-» numa tabela
    (boletim 28 de 2021, p44)."""
    from types import SimpleNamespace

    from crl_markdown.legacy.recorte import tirar_escondidas

    def letra(texto, x, y=700.0):
        return {"text": texto, "matrix": (1, 0, 0, 1, x, y), "fontname": "F"}
    visiveis = [letra("1", 10), letra("4", 15), letra("5", 20)]
    escondidas = [letra("fi", 12.0), letra("-", 30.0), letra("f", 50.0, 600.0)]
    pag = SimpleNamespace(objects={"char": visiveis + escondidas})
    tiradas = tirar_escondidas(pag, [("f", 12.0, 700.0), ("i", 12.0, 700.0),
                                     ("￾", 30.0, 700.0), ("f", 50.05, 600.0)])
    assert tiradas == 3
    assert [c["text"] for c in pag.objects["char"]] == ["1", "4", "5"]
    # uma letra só com metade da ligadura na origem não sai
    pag = SimpleNamespace(objects={"char": [letra("fi", 12.0)]})
    assert tirar_escondidas(pag, [("f", 12.0, 700.0)]) == 0
