"""Testes do extrator docling — limpeza APP_CCT dos itens do documento.

Cobrem os problemas do QA MaxQDA de 2026-08-24/25 (4 convenções
verificadas) e os artefactos do ensaio docling: mobiliário do BTE,
translineação residual, células repetidas pelos spans da grelha e blocos
emitidos fora da ordem de leitura (ISSUE-0003, ISSUE-0004).

Nenhum teste deste ficheiro importa docling ou docling_core: a
dependência é opcional e a suite normal tem de correr sem ela. Os
objetos de teste imitam a estrutura que o docling entrega (a grelha
repete a mesma célula em cada posição do span; a bbox traz o nome da
origem das coordenadas). A prova com os tipos reais está em
tests/test_docling_integracao.py, que se ignora sozinha quando o
docling_core não está instalado.
"""
from types import SimpleNamespace

from crl_markdown.legacy.extractor import estruturar
from crl_markdown.legacy.extractor_docling import (distancia_ao_topo,
                                   limpar_texto_item, ordenar_por_leitura,
                                   _linhas_de_tabela, RE_MARCADOR_PROPRIO)


# ---------- limpeza de itens de texto ----------

def test_descarta_mobiliario_bte():
    assert limpar_texto_item("Boletim do Trabalho e Emprego   40") is None
    assert limpar_texto_item("29 outubro 2025") is None
    assert limpar_texto_item("42") is None
    assert limpar_texto_item("   ") is None


def test_descarta_fragmento_be_ou_bte_isolado():
    """ISSUE-0019: o cabeçalho corrido chega às vezes partido pelo docling,
    e sobra "BE" ou "BTE" isolado entre dois parágrafos do corpo."""
    assert limpar_texto_item("BE") is None
    assert limpar_texto_item("BTE") is None


def test_nao_descarta_sigla_real_parecida_com_be():
    """A regra é estreita de propósito: só a linha inteira "BE"/"BTE", sem
    pontuação nem texto à volta — nunca uma sigla legítima."""
    assert limpar_texto_item("BE - Banco Espírito Santo") is not None
    assert limpar_texto_item("A BE assinou em representação") is not None
    assert limpar_texto_item("ABE") is not None


def test_mantem_texto_util():
    assert limpar_texto_item("1- O trabalhador tem direito.") == \
        "1- O trabalhador tem direito."


def test_repara_translineacao_residual():
    assert "recrutamento" in limpar_texto_item(
        "As admissões respeitam o enquadramento do recruta -mento.")


def test_nao_junta_travessao_legitimo():
    assert " - adiante" in limpar_texto_item("O AE - adiante designado acordo.")


def test_normaliza_quebras_internas():
    assert limpar_texto_item("primeira\nsegunda") == "primeira segunda"


# ---------- tabelas: uma célula por span ----------

def _celula(texto, linha=0, coluna=0, linhas=1, colunas=1):
    """Célula como o docling a descreve (posição inicial + extensão)."""
    return SimpleNamespace(text=texto,
                           start_row_offset_idx=linha,
                           end_row_offset_idx=linha + linhas,
                           start_col_offset_idx=coluna,
                           end_col_offset_idx=coluna + colunas)


def _tabela(celulas, n_linhas, n_colunas):
    """Grelha à maneira do docling: cada célula repetida em todo o seu span."""
    grelha = [[None] * n_colunas for _ in range(n_linhas)]
    for celula in celulas:
        for linha in range(celula.start_row_offset_idx, celula.end_row_offset_idx):
            for coluna in range(celula.start_col_offset_idx,
                                celula.end_col_offset_idx):
                grelha[linha][coluna] = celula
    return SimpleNamespace(data=SimpleNamespace(grid=grelha))


def test_colspan_emitido_uma_vez():
    # perfil de função do TRATOLIXO: "Competência" abrange 3 colunas
    tabela = _tabela([_celula("Competência", 0, 0, colunas=3),
                      _celula("Encarregado geral (DI)", 0, 3)], 1, 4)
    assert _linhas_de_tabela(tabela) == ["Competência | Encarregado geral (DI)"]


def test_rowspan_emitido_uma_vez():
    # caso da revisão do PR #23: "Categoria" abrange 2 linhas
    tabela = _tabela([_celula("Categoria", 0, 0, linhas=2),
                      _celula("A", 0, 1), _celula("B", 1, 1)], 2, 2)
    assert _linhas_de_tabela(tabela) == ["Categoria | A", " | B"]


def test_span_misto_emitido_uma_vez():
    # célula que abrange 2 linhas E 2 colunas: sai uma vez na linha 0 e
    # deixa uma célula vazia na linha 1 — uma só, porque a continuação
    # horizontal é omitida em ambas, o que mantém as colunas alinhadas
    tabela = _tabela([_celula("Carreira técnica", 0, 0, linhas=2, colunas=2),
                      _celula("Nível 3", 0, 2), _celula("Nível 4", 1, 2)], 2, 3)
    linhas = _linhas_de_tabela(tabela)
    assert linhas == ["Carreira técnica | Nível 3", " | Nível 4"]
    # NESTE caso as colunas ficam alinhadas; não é garantia geral — ver
    # test_nenhuma_celula_se_perde_nem_se_repete
    assert len({l.count("|") for l in linhas}) == 1


def test_valores_repetidos_em_colunas_distintas_sobrevivem():
    # tabela de remunerações do AguasNorte: o nível M é "n.a." em todas as
    # colunas — são células distintas, não um span
    tabela = _tabela([_celula("M", 0, 0)]
                     + [_celula("n.a.", 0, c) for c in range(1, 5)], 1, 5)
    assert _linhas_de_tabela(tabela) == ["M | n.a. | n.a. | n.a. | n.a."]


def test_valores_repetidos_em_linhas_distintas_sobrevivem():
    tabela = _tabela([_celula("n.a.", 0, 0), _celula("1 385,99 €", 0, 1),
                      _celula("n.a.", 1, 0), _celula("1 438,62 €", 1, 1)], 2, 2)
    assert _linhas_de_tabela(tabela) == ["n.a. | 1 385,99 €",
                                         "n.a. | 1 438,62 €"]


def test_celula_vazia_mantem_a_ordem_das_colunas():
    tabela = _tabela([_celula("Montante", 0, 0),
                      _celula("1 385,99 €", 0, 2)], 1, 3)
    assert _linhas_de_tabela(tabela) == ["Montante |  | 1 385,99 €"]


def test_linha_toda_vazia_e_descartada():
    tabela = _tabela([_celula("Montante", 0, 0)], 2, 2)
    assert _linhas_de_tabela(tabela) == ["Montante | "]


def test_tabela_sem_grelha_nao_rebenta():
    assert _linhas_de_tabela(SimpleNamespace(data=object())) == []


# ---------- ordem de leitura pela geometria ----------

def _bbox(l, r, t, origem="BOTTOMLEFT"):
    """Caixa como a do docling, sem importar docling_core (dependência
    opcional): lá o CoordOrigin é um enum de strings e o que nos importa
    é o nome."""
    return SimpleNamespace(l=l, r=r, t=t, coord_origin=origem)


def test_distancia_ao_topo_nas_duas_origens():
    # origem em baixo (o que o docling usa nos PDF): t cresce para cima
    assert distancia_ao_topo(_bbox(0, 100, 742.0), 841.0) == 99.0
    # origem em cima: t já é a distância ao topo
    assert distancia_ao_topo(_bbox(0, 100, 99.0, "TOPLEFT"), 841.0) == 99.0


def test_repoe_bloco_emitido_fora_de_sitio():
    # LAGOSemFORMA p.5: o docling emitia o corpo da cláusula 9.ª (mais
    # abaixo na página) antes das alíneas da 8.ª e do próprio cabeçalho
    A, L = 841.0, 595.0
    itens = [("corpo da 9.ª", 5, _bbox(79, 518, 400.0), A, L),
             ("alíneas da 8.ª", 5, _bbox(79, 518, 742.0), A, L),
             ("Cláusula 9.ª", 5, _bbox(273, 324, 436.0), A, L)]
    assert [i[0] for i in ordenar_por_leitura(itens)] == \
        ["alíneas da 8.ª", "Cláusula 9.ª", "corpo da 9.ª"]


def test_respeita_a_ordem_das_paginas():
    A, L = 841.0, 595.0
    itens = [("p2 topo", 2, _bbox(79, 518, 700.0), A, L),
             ("p1 fundo", 1, _bbox(79, 518, 100.0), A, L)]
    assert [i[0] for i in ordenar_por_leitura(itens)] == ["p1 fundo", "p2 topo"]


def test_duas_colunas_lidas_uma_de_cada_vez():
    # BTE antigos: a coluna esquerda inteira antes da direita
    A, L = 841.0, 595.0
    itens = ([(f"dir {i}", 1, _bbox(310, 560, 700.0 - i * 20), A, L) for i in range(6)]
             + [(f"esq {i}", 1, _bbox(40, 280, 700.0 - i * 20), A, L) for i in range(6)])
    nomes = [i[0] for i in ordenar_por_leitura(itens)]
    assert nomes[:6] == [f"esq {i}" for i in range(6)]
    assert nomes[6:] == [f"dir {i}" for i in range(6)]


def test_coluna_unica_nao_e_tratada_como_duas():
    # a página da LAGOSemFORMA é de coluna única: todos os itens atravessam
    # o meio e a ordem tem de ser só a vertical
    A, L = 841.0, 595.0
    itens = [(f"linha {i}", 1, _bbox(79, 518, 700.0 - i * 20), A, L)
             for i in range(10)]
    baralhados = itens[5:] + itens[:5]
    assert [i[0] for i in ordenar_por_leitura(baralhados)] == \
        [f"linha {i}" for i in range(10)]


def test_item_sem_geometria_fica_onde_estava():
    A, L = 841.0, 595.0
    itens = [("primeiro", 1, _bbox(79, 518, 700.0), A, L),
             ("sem prov", 0, None, 0.0, 0.0),
             ("terceiro", 1, _bbox(79, 518, 500.0), A, L)]
    assert [i[0] for i in ordenar_por_leitura(itens)] == \
        ["primeiro", "sem prov", "terceiro"]


# ---------- bala de lista duplicada ----------

def test_bala_nao_duplica_marcador_proprio():
    # "- -25 % pela primeira hora" no TRATOLIXO (1321 ocorrências)
    assert RE_MARCADOR_PROPRIO.match("-25 % pela primeira hora ou fração desta;")
    assert RE_MARCADOR_PROPRIO.match("–Técnica superior;")
    assert not RE_MARCADOR_PROPRIO.match("Texto normal sem marcador")


# ---------- integração com o estruturar ----------

def test_clausula_com_titulo_em_itens_separados():
    texto = "Cláusula 22.ª\nDescanso diário\n1- O trabalhador tem direito.\n"
    doc, _ = estruturar(texto, "t")
    cl = [n for n in doc["nos"] if n["tipo"] == "clausula"]
    assert cl and cl[0]["rotulo"] == "Cláusula 22.ª - Descanso diário"


def test_clausula_com_sufixo_de_letra():
    # LAGOSemFORMA 2025 tem "Cláusula 16.ª-A" … "16.ª-D" (aditadas em revisão)
    texto = "Cláusula 16.ª-D\nIsenção de horário\n1- O regime aplica-se.\n"
    doc, _ = estruturar(texto, "t")
    cl = [n for n in doc["nos"] if n["tipo"] == "clausula"]
    assert cl and cl[0]["rotulo"] == "Cláusula 16.ª-D - Isenção de horário"


def test_nenhuma_celula_se_perde_nem_se_repete():
    """Propriedade sobre tabelas geradas: são estas as garantias reais.

    Cada célula sai exatamente uma vez, seja qual for a combinação de
    spans. O alinhamento das colunas não é garantido — linhas com
    colspans diferentes emitem contagens diferentes, o que é inerente a
    "uma célula por span" e está documentado em celulas_da_linha.
    """
    import random
    aleatorio = random.Random(11)
    for _ in range(120):
        n_linhas = aleatorio.randint(1, 5)
        n_colunas = aleatorio.randint(1, 5)
        ocupado = [[False] * n_colunas for _ in range(n_linhas)]
        celulas = []
        for linha in range(n_linhas):
            for coluna in range(n_colunas):
                if ocupado[linha][coluna]:
                    continue
                alt = aleatorio.randint(1, min(2, n_linhas - linha))
                larg = aleatorio.randint(1, min(2, n_colunas - coluna))
                if any(ocupado[linha + a][coluna + b]
                       for a in range(alt) for b in range(larg)):
                    alt = larg = 1
                for a in range(alt):
                    for b in range(larg):
                        ocupado[linha + a][coluna + b] = True
                celulas.append(_celula(f"c{linha}_{coluna}", linha, coluna,
                                       linhas=alt, colunas=larg))
        saida = "\n".join(_linhas_de_tabela(
            _tabela(celulas, n_linhas, n_colunas)))
        for celula in celulas:
            assert saida.count(celula.text) == 1, (
                f"{celula.text} saiu {saida.count(celula.text)}x em {saida!r}")
