"""Texto que está no PDF mas não se vê: recortado, ou fora da página.

Um PDF pode trazer texto que nunca aparece impresso. No GESAMB de 2025 (p29),
a tabela do fardamento veio de outro documento colado inteiro na página e
recortado (um *clip path*) à volta da tabela: o texto desse documento (os
artigos 9.º e 10.º numa versão anterior, noutra fonte) continua lá, por baixo
e por cima da página. O pdfplumber não conhece recortes e lia-o, entrelaçado
linha a linha com o texto visível («1- O fardamento…» / «4- O fardamento…»);
o PDFium também o dá no texto, no fim da página.

A regra: uma letra só conta se se vê. Não se vê quando está toda fora da
página, ou quando o objeto de texto a que pertence fica fora da área de
recorte que o PDF lhe aplica. O PDFium diz as duas coisas; o pdfplumber não.
Só se olha para os objetos do nível da página: os de dentro de um objeto
embebido têm as coordenadas no espaço desse objeto.
"""
from __future__ import annotations

import ctypes

# distância (pt) entre a origem de uma letra no PDFium e no pdfplumber. A
# origem (o ponto da linha de base onde a letra começa) é a mesma nos dois; as
# caixas não são (o PDFium dá a do desenho, o pdfplumber a da fonte), e a
# camada escondida cobre a página toda: comparar caixas tirava letras visíveis.
TOLERANCIA = 0.1


def _endereco(obj) -> int | None:
    return ctypes.cast(obj.raw, ctypes.c_void_p).value if obj is not None else None


def _caixas_de_recorte(obj) -> list[tuple[float, float, float, float]]:
    import pypdfium2.raw as R

    recorte = R.FPDFPageObj_GetClipPath(obj.raw)
    if not recorte:
        return []
    caixas = []
    for i in range(R.FPDFClipPath_CountPaths(recorte)):
        xs, ys = [], []
        for j in range(R.FPDFClipPath_CountPathSegments(recorte, i)):
            segmento = R.FPDFClipPath_GetPathSegment(recorte, i, j)
            x, y = ctypes.c_float(), ctypes.c_float()
            R.FPDFPathSegment_GetPoint(segmento, x, y)
            xs.append(x.value)
            ys.append(y.value)
        if xs:
            caixas.append((min(xs), min(ys), max(xs), max(ys)))
    return caixas


def _recortado(obj) -> bool:
    """O objeto fica fora de alguma das áreas de recorte (que se intersetam)."""
    esquerda, fundo, direita, topo = obj.get_bounds()
    return any(direita < x0 or esquerda > x1 or topo < y0 or fundo > y1
               for x0, y0, x1, y1 in _caixas_de_recorte(obj))


def _objetos_recortados(pagina) -> set[int | None]:
    import pypdfium2.raw as R

    return {_endereco(o) for o in pagina.get_objects(
        filter=(R.FPDF_PAGEOBJ_TEXT,), max_depth=0) if _recortado(o)}


def _fora(caixa, largura: float, altura: float) -> bool:
    esquerda, fundo, direita, topo = caixa
    if (esquerda, fundo, direita, topo) == (0, 0, 0, 0):
        return False                    # caracteres gerados (espaços) não têm caixa
    return direita < 0 or esquerda > largura or topo < 0 or fundo > altura


def indices_escondidos(pagina, textpage, fora_da_pagina: bool = True) -> set[int]:
    """Índices, na textpage do PDFium, das letras que não se veem.

    Percorrer as letras uma a uma custa; só se faz quando há objetos
    recortados ou, com `fora_da_pagina`, letras fora da página.
    """
    recortados = _objetos_recortados(pagina)
    largura, altura = pagina.get_size()
    if not recortados and not (fora_da_pagina and _ha_texto_fora(textpage)):
        return set()
    indices = set()
    for i in range(textpage.count_chars()):
        if recortados and _endereco(textpage.get_textobj(i)) in recortados:
            indices.add(i)
        elif fora_da_pagina and _fora(textpage.get_charbox(i), largura, altura):
            indices.add(i)
    return indices


def _ha_texto_fora(textpage) -> bool:
    """O texto dentro da página é menos do que o texto todo?"""
    def letras(t: str) -> int:
        return sum(1 for c in t if not c.isspace())
    return letras(textpage.get_text_bounded()) < letras(textpage.get_text_range())


def letras_escondidas(pagina) -> list[tuple[str, float, float]]:
    """(letra, x, y) da origem das letras escondidas, no referencial do PDF."""
    import pypdfium2.raw as R

    textpage = pagina.get_textpage()
    try:
        # as de fora da página tira-as o extrator, sem o PDFium
        indices = indices_escondidos(pagina, textpage, fora_da_pagina=False)
        letras = []
        for i in sorted(indices):
            x, y = ctypes.c_double(), ctypes.c_double()
            R.FPDFText_GetCharOrigin(textpage.raw, i, x, y)
            letras.append((textpage.get_text_range(i, 1), x.value, y.value))
        return letras
    finally:
        textpage.close()


def texto_visivel(pagina) -> str:
    """O texto da página no PDFium, sem as letras escondidas."""
    textpage = pagina.get_textpage()
    try:
        # a textpage e o texto devolvido contam as letras da mesma maneira: o
        # índice de cada letra no texto é o seu índice na textpage
        texto = textpage.get_text_range()
        indices = indices_escondidos(pagina, textpage)
        if not indices:
            return texto
        return "".join(c for i, c in enumerate(texto) if i not in indices)
    finally:
        textpage.close()


# O PDFium dá o hífen de fim de linha como U+FFFE; o pdfplumber, como «-»
_EQUIVALENTES = {"\ufffe": "-"}


def tirar_escondidas(pag, letras: list[tuple[str, float, float]]) -> int:
    """Tira da página do pdfplumber as letras escondidas; devolve quantas.

    Uma letra do pdfplumber emparelha com as do PDFium que têm a mesma
    origem: a mesma letra, ou as várias em que o PDFium decompõe uma
    ligadura («fi» é «f» e «i», ambas na origem do «fi»). Sem isto, as
    ligaduras e os hífenes da camada escondida ficavam no texto (boletim 28
    de 2021, p44: «1fi45», «150-» numa tabela).
    """
    if not letras:
        return 0
    por_origem: dict[tuple[int, int], list[tuple[float, float, str]]] = {}
    for texto, x, y in letras:
        por_origem.setdefault((round(x), round(y)), []).append(
            (x, y, _EQUIVALENTES.get(texto, texto)))

    def escondida(c) -> bool:
        # a origem da letra são os dois últimos termos da matriz do texto
        ox, oy = c["matrix"][4], c["matrix"][5]
        mesmas = [t for i in (-1, 0, 1) for j in (-1, 0, 1)
                  for x, y, t in por_origem.get((round(ox) + i, round(oy) + j), ())
                  if abs(ox - x) <= TOLERANCIA and abs(oy - y) <= TOLERANCIA]
        return c["text"] in mesmas or (len(mesmas) > 1 and c["text"] == "".join(mesmas))
    todas = pag.objects.get("char", [])
    tiradas = [c for c in todas if not c["text"].isspace() and escondida(c)]
    # o PDFium não dá os espaços como letras: um espaço sai com as letras
    # escondidas da mesma fonte, na mesma linha de base
    linhas = {(c["fontname"], round(c["matrix"][5], 1)) for c in tiradas}
    ids = {id(c) for c in tiradas}
    pag.objects["char"] = [
        c for c in todas
        if id(c) not in ids and not (c["text"].isspace()
                                     and (c["fontname"], round(c["matrix"][5], 1)) in linhas)]
    return len(todas) - len(pag.objects["char"])
