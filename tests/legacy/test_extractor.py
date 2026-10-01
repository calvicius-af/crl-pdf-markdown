"""Testes do extrator PDF→doc.json — Fase 1.

Cobrem diretamente o feedback do gate da Fase 0 (memos MaxQDA de 2026-07-05):
- Anotações 1, 5, 6: quebras de linha a meio de frase são inaceitáveis;
- Anotação 2: rótulo da cláusula deve incluir o título ("Cláusula 1.ª - Âmbito");
- Anotação 3: cabeçalho de capítulo numa só linha ("CAPÍTULO I - Âmbito, ...");
- Anotação 7: fronteiras de segmento corretas.
"""
from pathlib import Path

import pytest

from crl_markdown.legacy.extractor import (MARCA_COLUNA, MARCA_TABELA_FIM, MARCA_TABELA_INI,
                           _remover_cabecalhos_rodapes, juntar_linhas,
                           estruturar, extrair_pdf)
from crl_markdown.legacy.schemas import validar_doc
from tests.pdf_sintetico import escrever_pdf

PDF_BTE = Path(__file__).parents[2] / "data" / "raw" / "bte" / "bte2_2025.pdf"


# ---------- junção de linhas ----------

def test_junta_frase_partida_apos_virgula():
    # caso real da anotação 1: quebra após vírgula, linha seguinte com maiúscula
    texto = ("Contrato coletivo entre a Associação do Comércio e da Indústria de Panificação,\n"
             "Pastelaria e Similares - ACIP e a FESAHT - Federação dos Sindicatos")
    assert "Panificação, Pastelaria" in juntar_linhas(texto)


def test_junta_frase_sem_pontuacao_final():
    # caso real da anotação 5: quebra a meio de frase sem pontuação
    texto = ("2- O dever de obediência, a que se refere a alínea d) do número anterior, respeita tanto às ordens e\n"
             "instruções dadas directamente pelo empregador como às emanadas dos superiores hierárquicos")
    assert "ordens e instruções" in juntar_linhas(texto)


def test_mantem_quebra_apos_ponto_final():
    texto = "A cláusula termina aqui.\nOutra frase começa."
    assert juntar_linhas(texto) == texto


def test_mantem_quebra_antes_de_alinea_e_numero():
    texto = "os seguintes deveres:\na) Cumprir o horário;\nb) Zelar pelos bens;\n1- Primeiro número"
    assert juntar_linhas(texto) == texto


def test_mantem_quebra_antes_de_clausula_e_capitulo():
    texto = "texto anterior sem pontuacao final\nCláusula 2.ª\nCAPÍTULO II"
    saida = juntar_linhas(texto)
    assert "\nCláusula 2.ª" in saida
    assert "\nCAPÍTULO II" in saida


def test_marcas_de_tabela_repetidas_nao_sao_cabecalho_bte():
    """BTE 31: tabelas em 2 de 3 páginas não podem perder delimitadores."""
    paginas = [
        "Boletim do Trabalho e Emprego\nTexto inicial.",
        ("Boletim do Trabalho e Emprego\nANEXO III - Tabela salarial\n"
         f"{MARCA_TABELA_INI}\nGrupo | Valor\nA | 100\nB | 200\n"
         f"{MARCA_TABELA_FIM}"),
        ("Boletim do Trabalho e Emprego\n"
         f"{MARCA_TABELA_INI}\nGrupo | Valor\nC | 300\nD | 400\n"
         f"{MARCA_TABELA_FIM}\nAssinaturas."),
    ]
    limpas = _remover_cabecalhos_rodapes(paginas)
    assert all("Boletim do Trabalho e Emprego" not in p for p in limpas)
    assert sum(p.count(MARCA_TABELA_INI) for p in limpas) == 2
    assert sum(p.count(MARCA_TABELA_FIM) for p in limpas) == 2
    assert sum(p.count("Grupo | Valor") for p in limpas) == 2, (
        "cabeçalhos de tabela repetidos são conteúdo, não mobiliário do BTE")
    _, texto = estruturar("\n".join(limpas), "teste")
    assert "Grupo | Valor\nA | 100\nB | 200" in texto
    assert "C | 300\nD | 400" in texto


def _pagina(n: int, corpo: str) -> str:
    return (f"Boletim do Trabalho e Emprego, n.º 31, 22/8/2026\n{corpo}\n"
            f"BTE 31 | {n}\n{n}")


def test_frase_repetida_no_corpo_nao_e_mobiliario():
    """Issue #47: uma frase legítima repetida em várias páginas desaparecia
    só por atingir o limiar de repetição. Agora só se remove o que se
    repete no topo ou no fundo das páginas."""
    corpo = ("Cláusula {n}.ª - Revogada\nTexto anterior da cláusula.\n"
             "O disposto no número anterior não prejudica os direitos adquiridos.\n"
             "Texto posterior da cláusula.")
    paginas = [_pagina(n, corpo.format(n=n)) for n in range(1, 6)]
    junto = "\n".join(_remover_cabecalhos_rodapes(paginas))
    assert junto.count("O disposto no número anterior não prejudica") == 5
    assert "Boletim do Trabalho e Emprego" not in junto
    assert "BTE 31 |" not in junto
    assert not any(l.strip().isdigit() for l in junto.split("\n")), \
        "o número da página, sozinho no fundo, é mobiliário"


def test_bloco_repetido_em_poucas_paginas_nao_e_mobiliario():
    """CIMPOR de 2025 (8 páginas): as tabelas de cada ano têm o mesmo título
    no topo da página e as mesmas notas no fundo. Com o limiar de duas
    páginas, a segunda e a terceira tabelas perdiam o título e as notas."""
    titulo = "ANEXO II-A\nTabela do enquadramento profissional e retribuições mínimas"
    nota = "Os trabalhadores integrados na tabela II serão integrados na tabela I."
    paginas = []
    for n in range(1, 9):
        corpo = [f"Texto próprio da página {n}.", f"Mais texto da página {n}.",
                 f"Outra linha da página {n}.", f"Última linha da página {n}."]
        if n in (2, 3, 5):
            corpo = [titulo, *corpo, nota]
        paginas.append(_pagina(n, "\n".join(corpo)))
    junto = "\n".join(_remover_cabecalhos_rodapes(paginas))
    assert junto.count("ANEXO II-A") == 3
    assert junto.count("Tabela do enquadramento profissional") == 3
    assert junto.count(nota) == 3
    assert "BTE 31 |" not in junto


def test_linha_repetida_em_quase_todas_as_paginas_e_mobiliario():
    """O que o BTE não diz pelo conteúdo, diz pela repetição: um título
    corrido no topo de todas as páginas continua a sair."""
    paginas = [f"AE CIMPOR - Alteração salarial\nTexto {n}.\nMais {n}.\nOutra {n}.\nFim {n}."
               for n in range(1, 7)]
    junto = "\n".join(_remover_cabecalhos_rodapes(paginas))
    assert "AE CIMPOR" not in junto and junto.count("Fim ") == 6


def test_numero_sozinho_a_meio_da_pagina_fica():
    """Um número numa linha própria a meio da página é conteúdo (por
    exemplo, uma célula de uma grelha que o pdfplumber não detetou)."""
    corpo = "Primeira linha.\nSegunda linha.\nTerceira linha.\n1250\nQuarta linha.\nQuinta."
    limpas = _remover_cabecalhos_rodapes([_pagina(n, corpo) for n in range(1, 4)])
    assert all("\n1250\n" in p for p in limpas)


def test_mobiliario_de_paginas_em_duas_colunas():
    """Numa página em duas colunas o cabeçalho parte-se entre as duas; cada
    coluna tem as suas margens, e a marca de coluna não chega ao texto."""
    paginas = [
        (f"Boletim do Trabalho\nTexto da esquerda {n}.\nMais texto {n}.\n"
         f"Continua a esquerda {n}.\n{n}\n{MARCA_COLUNA}\n"
         f"e Emprego, n.º 3\nTexto da direita {n}.\nAinda a direita {n}.\n"
         f"Fim da direita {n}.")
        for n in range(10, 14)
    ]
    junto = "\n".join(_remover_cabecalhos_rodapes(paginas))
    assert MARCA_COLUNA not in junto
    assert "Boletim do Trabalho" not in junto and "e Emprego, n.º 3" not in junto
    assert junto.count("Texto da direita") == 4 and junto.count("Fim da direita") == 4


# ---------- estruturação ----------

EXEMPLO = """Contrato coletivo entre a ACIP e a FESAHT - Alteração salarial e outras/texto consolidado
CAPÍTULO I
Âmbito, área, vigência e denúncia do contrato
Cláusula 1.ª
Âmbito
1- O presente CCT obriga as empresas associadas da ACIP.
2- Este CCT abrange 3500 empresas e 13 500 trabalhadores.
Cláusula 2.ª
Área
O presente CCT aplica-se em todo o território nacional.
SECÇÃO I
Disposições gerais
Cláusula 3.ª - Vigência
Este CCT entra em vigor após a sua publicação.
ANEXO I
Tabela salarial
Artigo 1.º
Os valores são os constantes do quadro seguinte.
"""


def _estruturado():
    return estruturar(EXEMPLO, doc_id="teste")


def test_rotulo_da_clausula_inclui_titulo():
    doc, texto = _estruturado()
    rotulos = [n["rotulo"] for n in doc["nos"] if n["tipo"] == "clausula"]
    assert "Cláusula 1.ª - Âmbito" in rotulos
    assert "Cláusula 2.ª - Área" in rotulos
    assert "Cláusula 3.ª - Vigência" in rotulos  # título já na mesma linha


def test_titulo_da_clausula_fundido_no_texto():
    doc, texto = _estruturado()
    assert "Cláusula 1.ª - Âmbito\n" in texto
    # a linha do título não fica duplicada
    assert "Cláusula 1.ª\nÂmbito" not in texto


def test_capitulo_numa_so_linha():
    doc, texto = _estruturado()
    caps = [n for n in doc["nos"] if n["tipo"] == "capitulo"]
    assert caps and caps[0]["rotulo"] == "CAPÍTULO I - Âmbito, área, vigência e denúncia do contrato"
    assert "CAPÍTULO I - Âmbito" in texto


def test_hierarquia_pai():
    doc, _ = _estruturado()
    por_id = {n["id"]: n for n in doc["nos"]}
    cl1 = next(n for n in doc["nos"] if n["rotulo"].startswith("Cláusula 1.ª"))
    assert por_id[cl1["pai"]]["tipo"] == "capitulo"
    cl3 = next(n for n in doc["nos"] if n["rotulo"].startswith("Cláusula 3.ª"))
    assert por_id[cl3["pai"]]["tipo"] == "seccao"
    art = next(n for n in doc["nos"] if n["tipo"] == "artigo")
    assert por_id[art["pai"]]["tipo"] == "anexo"


def test_preambulo_e_zero_perda():
    doc, texto = _estruturado()
    assert doc["nos"][0]["tipo"] == "preambulo"
    folhas = [n for n in doc["nos"] if n.get("folha")]
    assert "".join(texto[n["char_start"]:n["char_end"]] for n in folhas) == texto
    validar_doc(doc)


# ---------- integração com o PDF real ----------

@pytest.mark.skipif(not PDF_BTE.exists(), reason="bte2_2025.pdf não disponível")
def test_pdf_real_acip_fesaht():
    doc, texto = extrair_pdf(PDF_BTE, paginas=(15, 49), doc_id="25_CCT_BTE_02_ACIP_FESAHT")
    validar_doc(doc)
    clausulas = [n for n in doc["nos"] if n["tipo"] == "clausula"]
    assert len(clausulas) >= 80
    assert any(n["rotulo"] == "Cláusula 1.ª - Âmbito" for n in clausulas)
    # anotação 5: parágrafo do dever de obediência sem quebra interna
    assert "ordens e instruções dadas" in texto.replace("directamente", "directamente")
    assert "às ordens e\ninstruções" not in texto
    # sem cabeçalhos do BTE no corpo
    assert "Boletim do Trabalho e Emprego 2 15 janeiro 2025" not in texto
    # zero perda
    folhas = [n for n in doc["nos"] if n.get("folha")]
    assert "".join(texto[n["char_start"]:n["char_end"]] for n in folhas) == texto


# ---------- PDF sintéticos: rotação e colunas (corpus de 24-09-2026) ----------

def _tabela_rodada(sentido, y0=300, logica=None, quase=False):
    """Tabela «Nível | Valor» desenhada a 90º, com grelha, como as dos CARRISTUR.

    Na página, cada linha lógica da tabela é uma coluna; «btt» lê-se de baixo
    para cima (cabeçalho à esquerda), «ttb» de cima para baixo (à direita).
    Com `quase`, a rotação e os traços desviam-se uns centésimos (TINITA).
    """
    from tests.pdf_sintetico import grelha
    logica = logica or [["Nível", "Valor"], ["A", "1 355,48"], ["B", "1 200,00"]]
    x0, w, h = 100, 20, 70
    itens = grelha(x0, y0, [w] * 3, [h] * 2, desvio=0.07 if quase else 0.0)
    for i, linha in enumerate(logica):
        for j, texto in enumerate(linha):
            if sentido == "btt":        # linha i: coluna i; coluna j: de baixo
                itens.append((x0 + w * i + 15, y0 + h * j + 5, texto,
                              "quase_rodado" if quase else "rodado"))
            else:                       # linha i: coluna da direita; coluna j: de cima
                itens.append((x0 + w * (2 - i) + 5, y0 + h * (2 - j) - 5, texto,
                              "rodado_horario"))
    return [[(72, 780, "Assim, na página 225, onde se lê:"), *itens]]


@pytest.mark.parametrize("sentido", ["btt", "ttb"])
def test_tabela_rodada_sai_de_pe_e_legivel(tmp_path, sentido):
    """ISSUE-0020 e #42: as tabelas rodadas saíam com as palavras invertidas
    («levíN», «rolaV») e com as linhas trocadas pelas colunas."""
    from tests.pdf_sintetico import escrever_pdf
    pdf = escrever_pdf(tmp_path / "x.pdf", _tabela_rodada(sentido))
    _doc, texto = extrair_pdf(pdf)
    assert "Nível | Valor\nA | 1 355,48\nB | 1 200,00" in texto, texto


def test_tabela_quase_rodada_le_se_como_a_rodada(tmp_path):
    """#42, TINITA de 2025: em metade das páginas das escalas, a rotação de
    90º vinha com a matriz desviada uns centésimos e os traços da grelha
    tortos. O pdfplumber dava as letras como direitas e não via a grelha:
    «F ol g a s», nomes partidos em duas linhas, nenhuma célula."""
    from tests.pdf_sintetico import escrever_pdf
    pdf = escrever_pdf(tmp_path / "x.pdf", _tabela_rodada("btt", quase=True))
    _doc, texto = extrair_pdf(pdf)
    assert "Nível | Valor\nA | 1 355,48\nB | 1 200,00" in texto, texto


def test_linha_rente_a_tabela_rodada_sai_uma_vez(tmp_path):
    """INOVA de 2025, grelhas deitadas: uma linha de valores rente à tabela
    seguinte entrava na zona antes da tabela e na zona por baixo dela, e saía
    duas vezes, a segunda entrelaçada com a linha vizinha («1.080400,,0000
    €€»). Uma letra pertence à zona do seu centro."""
    from tests.pdf_sintetico import escrever_pdf
    [pagina] = _tabela_rodada("btt")
    # a primeira linha acaba rente ao traço esquerdo da tabela (x=100); a
    # segunda está por baixo da tabela, na largura dela
    pagina += [(103, 120, "Primeira nota", "rodado"), (115, 120, "Segunda nota", "rodado")]
    pdf = escrever_pdf(tmp_path / "x.pdf", [pagina])
    _doc, texto = extrair_pdf(pdf)
    assert texto.count("Primeira nota") == 1 and "Segunda nota" in texto, texto


def test_tabela_com_coluna_do_meio_vazia_nao_e_cortada_em_colunas(tmp_path):
    """377, «Enquadramento das profissões»: a coluna do meio quase vazia fazia
    a página passar por duas colunas; o corte separava a primeira coluna da
    terceira e punha o cabeçalho do BTE a meio do texto."""
    from tests.pdf_sintetico import escrever_pdf, grelha
    linhas = 10
    itens = grelha(40, 200, [200, 60, 200], [30] * linhas)
    for k in range(linhas):
        y = 200 + 30 * (linhas - 1 - k) + 10
        itens.append((45, y, f"Categoria profissional número {k}"))
        itens.append((305, y, f"Técnico administrativo de segunda {k}"))
    pdf = escrever_pdf(tmp_path / "x.pdf", [[(200, 760, "Enquadramento das profissões"), *itens]])
    _doc, texto = extrair_pdf(pdf)
    assert "Categoria profissional número 3 |  | Técnico administrativo de segunda 3" in texto, texto


def test_duas_colunas_de_texto_sem_grelha_continuam_a_ser_cortadas(tmp_path):
    """O BTE antigo em duas colunas continua a ler-se coluna a coluna."""
    from tests.pdf_sintetico import escrever_pdf
    itens = []
    for k in range(25):
        itens.append((40, 760 - 14 * k, f"Esquerda linha {k} do texto."))
        itens.append((320, 760 - 14 * k, f"Direita linha {k} do texto."))
    pdf = escrever_pdf(tmp_path / "x.pdf", [itens])
    _doc, texto = extrair_pdf(pdf)
    assert texto.index("Esquerda linha 24") < texto.index("Direita linha 0"), texto


def test_seccao_por_baixo_das_colunas_le_se_depois_das_duas(tmp_path):
    """ISSUE-0006, boletim 28 de 2021, p44: por baixo de um bloco em duas
    colunas, «DECISÕES ARBITRAIS», curto e encostado à esquerda, não atravessa
    a goteira; lia-se entre a coluna esquerda e a direita. Um espaço em branco
    largo, nas duas colunas à mesma altura, é uma mudança de secção. O espaço
    entre parágrafos, ainda que coincida nas duas colunas, não é."""
    from tests.pdf_sintetico import escrever_pdf
    itens = []
    y = 760
    for k in range(20):
        if k == 10:
            y -= 14                       # um parágrafo novo nas duas colunas
        itens.append((40, y, f"Esquerda linha {k} do texto."))
        itens.append((320, y, f"Direita linha {k} do texto."))
        y -= 14
    itens.append((40, y - 60, "DECISÕES ARBITRAIS"))
    itens.append((40, y - 80, "..."))
    itens.append((40, y - 140, "AVISOS DE CESSAÇÃO DA VIGÊNCIA DE CONVENÇÕES COLETIVAS "
                               "E DE OUTROS INSTRUMENTOS DE REGULAMENTAÇÃO"))
    pdf = escrever_pdf(tmp_path / "x.pdf", [itens])
    _doc, texto = extrair_pdf(pdf)
    ordem = [texto.index(t) for t in ("Esquerda linha 9", "Esquerda linha 19", "Direita linha 0",
                                      "Direita linha 19", "DECISÕES ARBITRAIS", "AVISOS DE CESSAÇÃO")]
    assert ordem == sorted(ordem), texto


def test_texto_ao_lado_de_uma_tabela_nao_se_perde(tmp_path):
    """As bandas só liam acima e abaixo das tabelas: o que estava ao lado,
    na mesma altura, desaparecia (CARRISTUR: «Deve ler-se:» e o título)."""
    from tests.pdf_sintetico import escrever_pdf, grelha
    itens = [(72, 780, "Texto antes da tabela."), *grelha(300, 500, [100, 100], [30, 30])]
    itens += [(305, 540, "Nível"), (405, 540, "Valor"), (305, 510, "A"), (405, 510, "100")]
    itens += [(72, 530, "Deve ler-se:"), (72, 400, "Texto depois da tabela.")]
    pdf = escrever_pdf(tmp_path / "x.pdf", [itens])
    _doc, texto = extrair_pdf(pdf)
    assert "Deve ler-se:" in texto
    assert texto.index("Deve ler-se:") < texto.index("Nível | Valor"), texto


def test_pagina_rodada_com_titulo_ao_lado_da_tabela(tmp_path):
    """A página inteira rodada dos CARRISTUR: o título está «acima» da tabela
    na leitura, mas à esquerda dela na página."""
    from tests.pdf_sintetico import escrever_pdf
    pagina = _tabela_rodada("btt")
    pagina[0].append((80, 300, "ANEXO II Quadro remuneratório", "rodado"))
    pdf = escrever_pdf(tmp_path / "x.pdf", pagina)
    _doc, texto = extrair_pdf(pdf)
    # o estruturar reconhece o anexo e escreve o rótulo «ANEXO II - …»
    assert "ANEXO II - Quadro remuneratório\nNível | Valor" in texto, texto
    assert "\no\n" not in texto and not texto.rstrip().endswith("\nA"), \
        "nenhuma letra solta de uma linha rodada partida"


def test_cabecalho_vertical_numa_tabela_direita(tmp_path):
    """382: células de cabeçalho escritas na vertical, numa grelha direita,
    saíam invertidas («levíN») ou faltavam."""
    from tests.pdf_sintetico import escrever_pdf, grelha
    # de baixo para cima: duas linhas de dados e o cabeçalho, mais alto
    itens = grelha(100, 400, [60, 60, 60], [20, 20, 80])
    itens += [(135, 445, "Nível", "rodado"), (195, 445, "Escalão", "rodado"),
              (255, 445, "Valor", "rodado")]
    for y, (a, b, c) in ((425, ("I", "1", "900")), (405, ("II", "2", "950"))):
        itens += [(105, y, a), (165, y, b), (225, y, c)]
    itens += [(72, 780, "Categoria profissional e remuneração mensal."),
              (72, 766, "Texto da página em linhas direitas, como no corpo da convenção.")]
    pdf = escrever_pdf(tmp_path / "x.pdf", [itens])
    _doc, texto = extrair_pdf(pdf)
    assert "Nível | Escalão | Valor\nI | 1 | 900\nII | 2 | 950" in texto, texto
    assert "levíN" not in texto


def test_uma_so_palavra_vertical_numa_tabela_direita(tmp_path):
    """AGEAS de 2025: a única palavra rodada da página, a célula vertical
    «Gestão» de uma grelha de carreiras, ficava abaixo do mínimo de letras
    rodadas e saía invertida («oãtseG»)."""
    from tests.pdf_sintetico import escrever_pdf
    # a primeira coluna é uma célula fundida, da altura das três linhas
    itens = [("traco", 100, y, 260, y) for y in (400, 460)]
    itens += [("traco", 140, y, 260, y) for y in (420, 440)]
    itens += [("traco", x, 400, x, 460) for x in (100, 140, 260)]
    itens += [(125, 410, "Gestão", "rodado"),
              (145, 445, "Diretor geral"), (145, 425, "Diretor grau II"),
              (145, 405, "Diretor grau I"),
              (72, 780, "Enquadramento das carreiras e categorias profissionais.")]
    pdf = escrever_pdf(tmp_path / "x.pdf", [itens])
    _doc, texto = extrair_pdf(pdf)
    assert "Gestão" in texto and "oãtseG" not in texto, texto


def test_tabelas_rodadas_lado_a_lado_nao_se_repetem(tmp_path):
    """382, p34: várias grelhas rodadas na mesma página deitada. As faixas
    entre tabelas cobriam a página inteira e voltavam a ler as outras
    tabelas: 2527 palavras a mais no corpus."""
    from tests.pdf_sintetico import escrever_pdf
    [a] = _tabela_rodada("btt", y0=150)
    [b] = _tabela_rodada("btt", y0=450, logica=[["Carreira", "Nível"],
                                               ["Técnico", "XII"], ["Diretor", "XVI"]])
    pdf = escrever_pdf(tmp_path / "x.pdf", [a + b[1:]])
    _doc, texto = extrair_pdf(pdf)
    assert texto.count("1 355,48") == 1 and texto.count("Diretor") == 1, texto
    assert "Nível | Valor\nA | 1 355,48" in texto
    assert "Carreira | Nível\nTécnico | XII\nDiretor | XVI" in texto


def test_negrito_simulado_nao_duplica_letras(tmp_path):
    """O mesmo carácter desenhado duas vezes, meio ponto ao lado: «CCaarrrreeiirraa»."""
    from tests.pdf_sintetico import escrever_pdf
    pdf = escrever_pdf(tmp_path / "x.pdf", [[(72, 700, "Carreira Técnica"),
                                             (72.3, 700, "Carreira Técnica")]])
    _doc, texto = extrair_pdf(pdf)
    assert texto.strip() == "Carreira Técnica", texto


def test_grelha_com_fronteira_a_meio_da_pagina_nao_e_cortada(tmp_path):
    """384 e 385, p4: a fronteira entre as colunas cai no meio da página e os
    traços são desenhados célula a célula; nenhum atravessa a goteira, e o
    título centrado saía partido («ANEX» | «O II»)."""
    from tests.pdf_sintetico import escrever_pdf
    meio, n = 297.5, 12
    itens = [(200, 760, "ANEXO II Grupos profissionais")]
    for k in range(n + 1):                       # traços célula a célula
        y = 300 + 30 * k
        itens += [("traco", 40, y, meio, y), ("traco", meio, y, 555, y)]
    for x in (40, meio, 555):
        itens.append(("traco", x, 300, x, 300 + 30 * n))
    for k in range(n):
        y = 300 + 30 * (n - 1 - k) + 10
        itens += [(45, y, f"Diretor coordenador de área {k}"),
                  (meio + 5, y, f"Gestor de projetos globais {k}")]
    pdf = escrever_pdf(tmp_path / "x.pdf", [itens])
    _doc, texto = extrair_pdf(pdf)
    assert "ANEXO II" in texto and "Grupos profissionais" in texto, texto
    assert "Diretor coordenador de área 3 | Gestor de projetos globais 3" in texto, texto


def test_cabecalho_e_data_na_mesma_linha_saem():
    """CARRISTUR, primeira página: o pdfplumber lê o cabeçalho e a data numa
    só linha, com o título do documento colado."""
    paginas = ["Boletim do Trabalho e Emprego 31 22 agosto 2026 PRIVADO\nTexto."]
    assert _remover_cabecalhos_rodapes(paginas) == ["PRIVADO\nTexto."]


def test_cabecalho_direito_numa_pagina_deitada_nao_se_parte(tmp_path):
    """CARRISTUR, pp. 2-3: o cabeçalho está direito numa página deitada; as
    faixas verticais partiam-no em «Boletim do Trabalh» e «ho e Emprego 31»."""
    from tests.pdf_sintetico import escrever_pdf
    [pagina] = _tabela_rodada("btt")
    pagina = [i for i in pagina if not (len(i) == 3 and i[2].startswith("Assim"))]
    pagina += [(40, 810, "Boletim do Trabalho e Emprego 31"),
               (80, 200, "Deve ler-se: ANEXO II Quadro remuneratório e tempos", "rodado"),
               (60, 200, "de permanência para progressão nas carreiras", "rodado")]
    pdf = escrever_pdf(tmp_path / "x.pdf", [pagina])
    _doc, texto = extrair_pdf(pdf)
    assert "Boletim" not in texto and "Trabalh" not in texto, texto
    assert "Nível | Valor" in texto


def test_hifenizacao_dentro_das_celulas_junta_a_palavra():
    """384 e 385, anexo de conteúdos funcionais: «estratégi- co», «procedi-
    mentos» nas células, que o corpo do texto já juntava."""
    from crl_markdown.legacy.extractor import _formatar_tabela
    assert _formatar_tabela([["Diretor", "atividades de âmbito estratégi-\nco, define"]]) == \
        "Diretor | atividades de âmbito estratégico, define"
    assert _formatar_tabela([["Sub-\nCategoria", "A -\n B"]]) == "Sub- Categoria | A - B", \
        "hífen antes de maiúscula ou de espaço fica"


@pytest.mark.parametrize("distancia", [2.5, 1.5])
def test_linhas_entrelacadas_separam_se(tmp_path, distancia):
    """ANACOM de 2025: «ECma vriggoors d deesd De i1r edçeã…» eram duas
    linhas a menos de 3 pt, na mesma largura, fundidas letra a letra."""
    pdf = escrever_pdf(tmp_path / "x.pdf", [[
        (72, 700, "Em vigor desde 1 de janeiro de 2025"),
        (80, 700 - distancia, "Cargos de Direção e Chefia"),
        (72, 680, "Texto normal da linha seguinte.")]])
    _doc, texto = extrair_pdf(pdf)
    assert "Em vigor desde 1 de janeiro de 2025" in texto
    assert "Cargos de Direção e Chefia" in texto


def test_indice_colado_a_letra_nao_e_entrelacado(tmp_path):
    """Um expoente ou uma nota (n.º, 1)) está mais alto, mas não em cima de
    outras letras: a linha lê-se como sempre."""
    pdf = escrever_pdf(tmp_path / "x.pdf", [[
        (72, 700, "Cláusula 3.ª - Retribuição"), (212, 703, "1"),
        (218, 700, "e outras prestações do trabalho.")]])
    _doc, texto = extrair_pdf(pdf)
    assert "Retribuição" in texto and "outras prestações" in texto


def test_texto_virado_180_graus_le_se_no_sentido_certo(tmp_path):
    """CARRIS de 2025: «oã etniuges lacse oa ossecA» era «Acesso ao escalão
    seguinte», escrito de pernas para o ar num esquema de carreiras."""
    from crl_markdown.legacy.completude import medir_pdf
    pdf = escrever_pdf(tmp_path / "x.pdf", [[
        (72, 700, "Texto direito normal da página."),
        (400, 500, "Acesso ao escalão seguinte", "virado"),
        (400, 486, "Legenda Progressão", "virado")]])
    _doc, texto = extrair_pdf(pdf)
    assert "Acesso ao escalão seguinte" in texto and "Legenda Progressão" in texto
    assert "Texto direito normal da página." in texto
    assert medir_pdf("x", pdf, texto).cobertura == 1.0


def _rotulos(texto: str) -> list[str]:
    doc, _ = estruturar(texto, "teste")
    return [n["rotulo"] for n in doc["nos"] if n["tipo"] in ("clausula", "artigo")]


def test_linhas_de_tabela_e_de_lista_nao_sao_clausulas():
    """Corrida de 2025: «Cláusula 44.ª, número 2 - Valor… | 88,20 €» (uma
    linha da tabela de valores) e «Cláusula 28.ª - Deslocações em serviço -
    16,55 €;» (uma lista) viravam cláusulas vazias."""
    texto = "\n".join([
        "Cláusula 1.ª", "Âmbito", "O presente acordo aplica-se a todo o território.",
        "Artigo 2.º", "Valores", "Os valores passam a ser os seguintes:",
        "Cláusula 28.ª - Deslocações em serviço - 16,55 €;",
        "Cláusula 29.ª - Viagens em serviço - 71,65 €.",
        MARCA_TABELA_INI,
        "Cláusula 44.ª, número 2 - Valor das despesas | 88,20 €",
        "Cláusula 44.ª, número 5 - Valor por km | 0,40 €",
        MARCA_TABELA_FIM,
        "Cláusula 45.ª, número 1, passa a ter a redação seguinte."])
    # o último item da lista acaba em ponto e continua a ser do artigo
    # (revisão do PR #90: o teste esperava aqui uma cláusula falsa)
    assert _rotulos(texto) == ["Cláusula 1.ª - Âmbito", "Artigo 2.º - Valores"]
    doc, final = estruturar(texto, "teste")
    artigo = next(n for n in doc["nos"] if n["rotulo"] == "Artigo 2.º - Valores")
    corpo = final[artigo["char_start"]:artigo["char_end"]]
    assert "16,55 €" in corpo and "71,65 €." in corpo
    assert "Cláusula 45.ª, número 1" in corpo


def test_ultimo_item_de_lista_sem_valores_nao_e_clausula():
    """Uma lista de cláusulas revogadas, sem valores: o último item acaba em
    ponto e vem logo a seguir a outro item. A cláusula real que se segue, com
    o título na linha seguinte, continua a ser reconhecida."""
    texto = "\n".join([
        "Artigo 3.º", "Revogação", "São revogadas as cláusulas seguintes:",
        "Cláusula 5.ª - Férias;", "Cláusula 6.ª - Feriados.",
        "Cláusula 7.ª", "Faltas", "As faltas regem-se pela lei."])
    assert _rotulos(texto) == ["Artigo 3.º - Revogação", "Cláusula 7.ª - Faltas"]
    doc, final = estruturar(texto, "teste")
    artigo = next(n for n in doc["nos"] if n["rotulo"] == "Artigo 3.º - Revogação")
    assert "Cláusula 6.ª - Feriados." in final[artigo["char_start"]:artigo["char_end"]]


def test_titulo_que_acaba_em_ponto_continua_a_ser_cabecalho():
    """Sem valor em euros e sem item antes, a linha é um cabeçalho, mesmo
    que o título acabe em ponto."""
    texto = "\n".join(["Cláusula 9.ª - Deslocações.", "O trabalhador tem direito ao reembolso."])
    assert _rotulos(texto) == ["Cláusula 9.ª - Deslocações."]


def test_corpo_na_linha_do_cabecalho():
    """«Artigo 7.º Serão ainda sujeitos ao teste…»: o corpo ficava no rótulo
    e o artigo sem conteúdo."""
    texto = "\n".join([
        "Artigo 7.º Serão ainda sujeitos ao teste todos os trabalhadores que o "
        "solicitem, nos termos do regulamento em vigor.",
        "Cláusula 5.ª (Revogada.)",
        "Artigo 2.º [Revogado.]",
        "Artigo 17.º As decisões dos árbitros são tomadas por maioria.",
        "Artigo 18.º - Disposições finais e transitórias",
        "Aplica-se o regime legal em vigor.",
        "Cláusula 6.ª - Férias", "O período de férias é de 22 dias úteis."])
    doc, final = estruturar(texto, "teste")
    assert _rotulos(texto) == ["Artigo 7.º", "Cláusula 5.ª", "Artigo 2.º", "Artigo 17.º",
                               "Artigo 18.º - Disposições finais e transitórias",
                               "Cláusula 6.ª - Férias"]
    from crl_markdown.legacy.sanidade import clausulas_sem_corpo
    assert clausulas_sem_corpo(doc, final) == []
    assert "Serão ainda sujeitos ao teste" in final


def test_letras_em_escada_nao_se_separam_uma_a_uma(tmp_path):
    """TINITA de 2025: letras escritas em escada também se sobrepõem com
    alturas diferentes. Separá-las como linhas entrelaçadas dava uma letra por
    linha («F F S / o é e l r r …») e 929 palavras a mais."""
    linhas = [(72, 760, "Texto normal da página antes da escala.")]
    for j, palavra in enumerate(["Folgas", "Férias", "Serviço"]):
        for i, letra in enumerate(palavra):
            linhas.append((100 + j * 40 + i * 1.5, 700 - i * 2.0, letra))
    _doc, texto = extrair_pdf(escrever_pdf(tmp_path / "x.pdf", [linhas]))
    assert "Folgas Férias Serviço" in texto


def test_pagina_final_com_assinaturas_em_colunas(tmp_path):
    """Corrida de 2025: nas páginas finais, as assinaturas vêm em duas
    colunas e o fim do texto e a nota de depósito ocupam a largura toda.
    Cortar a página ao meio partia a nota: «livro n.º 13, com o n.º 45/2025,
    nos…» ficava depois dela."""
    linhas = [(72, 800, "Boletim do Trabalho e Emprego, n.º 6, 15/2/2025")]
    y = 760
    for t in ["O presente acordo produz efeitos a partir de 1 de janeiro de 2025, com exceção das",
              "cláusulas de expressão pecuniária, que produzem efeitos a partir de 1 de março."]:
        linhas.append((72, y, t))
        y -= 14
    y -= 10
    esquerda = ["Pela Empresa X, SA:", "Maria Alves Pereira, na qualidade",
                "de presidente do conselho de", "administração.",
                "João Carlos Silva, vogal do", "conselho de administração."]
    direita = ["Pelo Sindicato dos Trabalhadores", "da Administração Pública e de",
               "Entidades com Fins Públicos - SINTAP:", "Carlos Miguel Dias Moreira, na",
               "qualidade de mandatário.", "Ana Rita Costa, mandatária."]
    for a, b in zip(esquerda, direita):
        linhas += [(72, y, a), (320, y, b)]
        y -= 14
    y -= 10
    for t in ["Depositado em 20 de fevereiro de 2025, a fl. 90 do livro n.º 13, com o n.º 45/2025, nos",
              "termos do artigo 494.º do Código do Trabalho, aprovado pela Lei n.º 7/2009, de 12 de fevereiro."]:
        linhas.append((72, y, t))
        y -= 14
    linhas.append((470, 40, "BTE 6 | 110"))
    _doc, texto = extrair_pdf(escrever_pdf(tmp_path / "x.pdf", [linhas]))
    from crl_markdown.legacy.sanidade import deposito_no_fim
    assert deposito_no_fim(texto) is None, texto
    assert "com exceção das cláusulas de expressão pecuniária" in texto
    assert texto.index("Pela Empresa X") < texto.index("Pelo Sindicato") < texto.index("Depositado")
    assert "110" not in texto


def test_rodape_partido_nas_margens_sai():
    paginas = [f"Texto {n}.\nMais texto {n}.\nOutra linha {n}.\nFim {n}.\n{n} | 1{n}"
               for n in range(1, 4)] + ["Texto.\nMais.\nOutra.\nFim.\nBTE | 23"]
    junto = "\n".join(_remover_cabecalhos_rodapes(paginas))
    assert "|" not in junto and junto.count("Fim") == 4


def test_titulos_lado_a_lado_nao_atravessam_a_goteira(tmp_path):
    """Lusitânia-STAS de 2025: duas tabelas lado a lado, cada uma com o seu
    título perto da goteira. Lidos como uma linha só, os títulos misturavam-se
    («ANEXO VI ANEXO VI Tabela de correspondência … Tabela de …»)."""
    linhas = []
    y = 760
    for n in range(12):
        linhas += [(72, y, f"Categoria da esquerda número {n}."),
                   (320, y, f"Categoria da direita número {n}.")]
        y -= 14
    linhas += [(200, 790, "ANEXO VI - Esquerda"), (303, 790, "ANEXO VI - Direita")]
    _doc, texto = extrair_pdf(escrever_pdf(tmp_path / "x.pdf", [linhas]))
    assert "ANEXO VI - Esquerda\n" in texto
    assert texto.index("esquerda número 11") < texto.index("ANEXO VI - Direita")


def test_frase_na_linha_seguinte_nao_e_titulo():
    """ADIPA, Caravela e RTP de 2025: «Artigo 7.º» numa linha e a frase na
    seguinte. A frase virava o título e o artigo ficava «sem conteúdo»."""
    texto = "\n".join([
        "Artigo 7.º", "Serão ainda sujeitos ao teste todos os trabalhadores que o solicitem.",
        "Artigo 8.º", "Âmbito",
        "O presente regulamento aplica-se a todos os trabalhadores."])
    doc, final = estruturar(texto, "teste")
    assert _rotulos(texto) == ["Artigo 7.º", "Artigo 8.º - Âmbito"]
    from crl_markdown.legacy.sanidade import clausulas_sem_corpo
    assert clausulas_sem_corpo(doc, final) == []


def test_tabela_dentro_de_outra_le_se_uma_vez(tmp_path):
    """EPAL de 2025: a tabela salarial em escada tem a grelha de fora e,
    dentro dela, grelhas pequenas que não tocam nos traços de fora. O
    pdfplumber via as duas, e o texto das de dentro saía duas vezes."""
    from tests.pdf_sintetico import escrever_pdf, grelha
    itens = grelha(80, 300, [200, 220], [250, 30])          # a de fora
    itens += grelha(120, 360, [40, 60], [20, 20])           # uma de dentro
    itens += [(90, 565, "TÉCNICO AUXILIAR"), (290, 565, "QUADRO"),
              (125, 385, "B15"), (165, 385, "1,177.4"),
              (125, 365, "B14"), (165, 365, "1,154.2"),
              (72, 780, "Tabela salarial de 2025 da empresa, com a grelha em escada.")]
    pdf = escrever_pdf(tmp_path / "x.pdf", [itens])
    _doc, texto = extrair_pdf(pdf)
    assert texto.count("1,177.4") == 1 and texto.count("B14") == 1, texto
