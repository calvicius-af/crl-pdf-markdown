"""Completude da extração: o texto tem tudo o que o PDF tem.

Estes testes passam pela extração real (pdfplumber) sobre PDF sintéticos com o
mobiliário do BTE, e comparam com a leitura independente do PDFium. É o que
faltava para apanhar, antes da estação, uma correção que apaga texto: a
primeira versão da remoção de mobiliário por posição (#47) apagava as frases
repetidas de páginas curtas, e nenhum teste sobre texto já extraído o via.
"""
from pathlib import Path

import pytest

from crl_markdown.legacy.completude import (diagnostico, medir, medir_pdf,
                            paginas_de_referencia, sem_mobiliario)
from crl_markdown.legacy.extractor import extrair_pdf
from tests.pdf_sintetico import escrever_pdf, pagina_bte

CORPO = ["O período anual de férias é de 22 dias úteis.",
         "O disposto no número anterior não prejudica os direitos adquiridos.",
         "Os trabalhadores têm direito a um subsídio de refeição por dia."]


def _paginas(n_paginas: int, extra: int = 0):
    """Páginas com texto próprio e, a meio, frases iguais em todas elas."""
    return [pagina_bte(n, [f"Cláusula {n}.ª - Férias",
                           *[f"Linha própria {n}.{k} da cláusula." for k in range(extra)],
                           *CORPO,
                           *[f"Outra linha {n}.{k} da cláusula." for k in range(extra)]])
            for n in range(1, n_paginas + 1)]


@pytest.mark.parametrize("extra", [0, 30], ids=["paginas-curtas", "paginas-cheias"])
def test_extracao_completa_de_paginas_com_mobiliario(tmp_path, extra):
    """Frases repetidas em todas as páginas ficam; o mobiliário sai."""
    pdf = escrever_pdf(tmp_path / "x.pdf", _paginas(5, extra))
    _doc, texto = extrair_pdf(pdf)
    m = medir_pdf("x", pdf, texto)
    assert m.veredicto == "OK", diagnostico([m])
    assert m.cobertura == 1.0
    assert "Boletim do Trabalho" not in texto and "BTE 31 |" not in texto


def test_texto_em_falta_e_localizado_na_pagina(tmp_path):
    pdf = escrever_pdf(tmp_path / "x.pdf", _paginas(4, 10))
    _doc, texto = extrair_pdf(pdf)
    texto = texto.replace(CORPO[2], "", 1)          # perde-se na página 1
    m = medir_pdf("x", pdf, texto)
    assert m.veredicto == "ATENÇÃO"
    assert m.em_falta["subsídio"] == 1
    assert [n for n, _ in m.perda_por_pagina] == [4], \
        "as páginas consomem as palavras por ordem: a falta aparece na última"
    assert "subsídio de refeição" in m.contexto_falta["subsídio"]


def test_perda_grande_e_falha():
    m = medir("x", ["Primeira frase inteira.\n" * 20, "Segunda página com texto."],
              "Segunda página com texto.")
    assert m.veredicto == "FALHA"


def test_palavras_invertidas_e_mobiliario_no_texto():
    """Os dois sintomas das tabelas rodadas e das colunas mal cortadas."""
    pdf = ["Folgas Serviço Semana\nTexto normal da escala."]
    texto = ("sagloF oçivreS Semana\nBoletim do Trabalho e Emprego 31\n"
             "Texto normal da escala.")
    m = medir("x", pdf, texto)
    assert ("sagloF", "Folgas") in m.invertidas
    assert m.residuos == [(2, "Boletim do Trabalho e Emprego 31")], \
        "o parágrafo é o número que o MAXQDA mostra"
    assert m.veredicto == "FALHA", "duas de sete palavras perdidas"


def test_tabela_colapsada_numa_linha():
    celulas = " | ".join(f"Categoria {i} | {1000 + i},00" for i in range(60))
    m = medir("x", [celulas.replace(" | ", "\n")], celulas)
    assert m.cobertura == 1.0
    assert m.linhas_longas and m.veredicto == "ATENÇÃO"


def test_linha_inteira_de_tabela_nao_e_tabela_colapsada():
    """#84, corrida de 2025: o conteúdo funcional numa célula (CARRIS, RTP) e o
    cabeçalho de uma grelha larga, com as mesmas células que as linhas de
    baixo, contavam como tabelas colapsadas."""
    funcoes = "É o trabalhador que realiza tarefas de montagem e manutenção. " * 12
    descricao = f"5 | E | 151 | Mestre | {funcoes.strip()}"
    cabecalho = " | ".join(f"Categoria profissional {i}" for i in range(30))
    valores = " | ".join(f"{900 + i},50" for i in range(30))
    colapsada = " | ".join(f"Nível {i} | {1000 + i},00" for i in range(40))
    texto = "\n".join([descricao, "Texto.", cabecalho, valores, "Texto.", colapsada])
    m = medir("x", [texto.replace(" | ", "\n")], texto)
    assert [n for n, _ in m.linhas_longas] == [6], m.linhas_longas


def test_blocos_trocados_baixam_a_ordem():
    a = " ".join(f"alfa{i}" for i in range(200))
    b = " ".join(f"beta{i}" for i in range(200))
    m = medir("x", [f"{a}\n{b}"], f"{b}\n{a}")
    assert m.cobertura == 1.0
    assert m.ordem < 0.6 and m.veredicto == "ATENÇÃO"


def test_numero_a_meio_da_pagina_nao_e_mobiliario():
    """Um valor de tabela numa linha própria conta; o número da página não."""
    pagina = "Boletim do Trabalho e Emprego, n.º 31\nTexto.\n1250\nMais texto.\nBTE 31 | 7\n7"
    limpa, saem = sem_mobiliario(pagina)
    assert "1250" in limpa
    assert saem == ["Boletim do Trabalho e Emprego, n.º 31", "BTE 31 | 7", "7"]


def test_hifenizacao_nao_conta_como_perda():
    m = medir("x", ["O traba-\nlhador tem direito."], "O trabalhador tem direito.")
    assert m.cobertura == 1.0 and not m.a_mais


def test_pdf_ilegivel_da_sem_medida(tmp_path):
    falso = tmp_path / "x.pdf"
    falso.write_bytes(b"%PDF-1.4\n")
    m = medir_pdf("x", falso, "texto")
    assert m.veredicto == "SEM MEDIDA"
    assert "SEM MEDIDA" in diagnostico([m])


def test_referencia_le_todas_as_paginas(tmp_path):
    pdf = escrever_pdf(tmp_path / "x.pdf", _paginas(3))
    paginas = paginas_de_referencia(pdf)
    assert len(paginas) == 3 and "Cláusula 3.ª" in paginas[2]






def test_gerador_de_pdf_e_legivel_pelos_dois_motores(tmp_path):
    pdf = escrever_pdf(tmp_path / "x.pdf", [[(72, 700, "Olá, ação à mão (sim)")]])
    import pdfplumber
    with pdfplumber.open(pdf) as p:
        assert p.pages[0].extract_text() == "Olá, ação à mão (sim)"
    assert paginas_de_referencia(Path(pdf))[0] == "Olá, ação à mão (sim)"


ESCALA = ["Folgas Serviço Semana 1", "Motorista Guarda-freio Folga",
          "Segunda Terça Quarta"]


def test_a_referencia_le_bem_o_texto_rodado(tmp_path):
    """O PDFium lê na ordem certa o texto a 90º numa página sem rotação."""
    pdf = escrever_pdf(tmp_path / "x.pdf",
                       [[(100 + 20 * i, 100, t, "rodado") for i, t in enumerate(ESCALA)]])
    assert paginas_de_referencia(pdf)[0].split("\n") == ESCALA


def test_extrator_le_bem_o_texto_rodado(tmp_path):
    """ISSUE-0020 e #42: era um xfail estrito até o extrator ler o texto
    rodado no sentido certo (char_dir_rotated do pdfplumber 0.11)."""
    pdf = escrever_pdf(tmp_path / "x.pdf",
                       [[(100 + 20 * i, 100, t, "rodado") for i, t in enumerate(ESCALA)]])
    _doc, texto = extrair_pdf(pdf)
    m = medir_pdf("x", pdf, texto)
    assert not m.invertidas and m.cobertura == 1.0, diagnostico([m])


def test_o_diagnostico_apanha_o_texto_rodado_invertido(tmp_path):
    """A leitura antiga (extract_text sem sentido) tem de dar FALHA."""
    import pdfplumber
    pdf = escrever_pdf(tmp_path / "x.pdf",
                       [[(100 + 20 * i, 100, t, "rodado") for i, t in enumerate(ESCALA)]])
    with pdfplumber.open(pdf) as p:
        texto_antigo = p.pages[0].extract_text()
    m = medir_pdf("x", pdf, texto_antigo)
    assert ("sagloF", "Folgas") in m.invertidas
    assert m.veredicto == "FALHA"


# ---------- casos reais do corpus (comparacao.md de 24-09-2026) ----------

def test_hifen_do_pdfium_com_rodape_colado_nao_parte_palavras():
    """O PDFium marca a hifenização com U+FFFE e cola-lhe o rodapé; «pro» e
    «fissional» contavam como em falta e «profissional» como a mais."""
    paginas = ["o trabalho prestado, não podendo o pro￾BTE 31 | 34",
               "fissional receber em relação a esse trabalho uma remuneração.\n"
               "a necessária corre￾ção."]
    texto = ("o trabalho prestado, não podendo o profissional receber em relação "
             "a esse trabalho uma remuneração.\na necessária correção.")
    m = medir("x", paginas, texto)
    assert m.cobertura == 1.0 and not m.a_mais, diagnostico([m])
    assert not m.perda_por_pagina


def test_cabecalho_datado_a_meio_da_linha_sai_da_referencia():
    """Corrida de 2025: o PDFium cola o cabeçalho ao fim da linha anterior
    («… Homologação da avaliação Boletim do Trabalho e Emprego 28 29 agosto
    2025») e às vezes parte o ano («202 5»). Contava como texto em falta."""
    pagina = ("Reunião de avaliação Homologação da avaliação Boletim do Trabalho e "
              "Emprego 28 29 agosto 2025\n"
              "Boletim do Trabalho e Emprego 5 8 fevereiro 202 5 ANEXO III\n"
              "publicado no Boletim do Trabalho e Emprego, n.º 21, de 8 de junho de 2025.")
    limpa, saem = sem_mobiliario(pagina)
    assert limpa.split("\n") == [
        "Reunião de avaliação Homologação da avaliação", "ANEXO III",
        "publicado no Boletim do Trabalho e Emprego, n.º 21, de 8 de junho de 2025."]
    assert saem == ["Boletim do Trabalho e Emprego 28 29 agosto 2025",
                    "Boletim do Trabalho e Emprego 5 8 fevereiro 202 5"]


def test_rodape_sem_numero_do_boletim_sai_da_referencia():
    """BTE 38/2025: o rodapé é «BTE | 100», sem o número do boletim. O
    extrator tirava-o e a medição contava-o como texto em falta."""
    limpa, saem = sem_mobiliario("Texto da página.\nMais texto.\nBTE | 100")
    assert limpa == "Texto da página.\nMais texto." and saem == ["BTE | 100"]


def test_citar_o_boletim_no_corpo_nao_e_mobiliario():
    """As menções ao BTE no articulado saíam da referência e contavam como
    resíduo: 5 «resíduos» falsos só no 377."""
    frase = ("1- A presente convenção entra em vigor a partir do quinto dia "
             "posterior ao da sua publicação no Boletim do Trabalho e Emprego.")
    citacao = "publicado no Boletim do Trabalho e Emprego, n.º 21, 8 de junho de 2026"
    m = medir("x", [f"{frase}\n{citacao}"], f"{frase}\n{citacao}")
    assert m.cobertura == 1.0 and not m.a_mais and not m.residuos


def test_mobiliario_do_bte_de_2026_sai_da_referencia_e_e_apanhado_no_texto():
    pagina = ("Boletim do Trabalho e Emprego 31\n22 agosto 2026\n"
              "Texto da cláusula.\nBTE 31 | 139")
    texto = ("Texto da cláusula.\nBoletim do Trabalho e Emprego 31 ANEX Categorias e gru\n"
             "1 | 139 Boletim do Trabalho e Emprego 31\nBTE 3\n22 agosto 2026")
    m = medir("x", [pagina], texto)
    assert m.em_falta == {}, "o cabeçalho, a data e o rodapé não são texto a exigir"
    assert [n for n, _ in m.residuos] == [2, 3, 4, 5]


def test_invertidas_pela_forma_quando_a_referencia_nao_tem_a_palavra():
    """Nas tabelas rodadas dos CARRISTUR o PDFium não lê nada; o par exato não
    existe, mas «ahlocsE» e «ocincéT» denunciam-se pela maiúscula no fim."""
    m = medir("x", ["Assim, na página 225, onde se lê:"],
              "Assim, na página 225, onde se lê:\nahlocsE ¦ ocincéT ¦ levíN ¦ Escolha")
    assert [a for a, _ in m.invertidas] == ["ahlocsE", "levíN", "ocincéT"]


def test_cabecalho_do_pdfium_numa_so_linha_e_colado_ao_texto():
    """CI de 24-09-2026: o PDFium lê o cabeçalho e a data numa só linha e, nas
    páginas rodadas, cola-lhe o texto seguinte. Eram 9 palavras «em falta» por
    página, que não são texto da convenção."""
    paginas = ["Boletim do Trabalho e Emprego 31 22 agosto 2026\nPRIVADO\nTexto.",
               "Boletim do Trabalho e Emprego 31 22 agosto 2026 Deve ler-se:\nMais."]
    m = medir("x", paginas, "PRIVADO\nTexto.\nDeve ler-se:\nMais.")
    assert m.cobertura == 1.0 and not m.a_mais, diagnostico([m])


def test_trechos_em_falta_mostram_a_frase_e_a_pagina():
    frase = "O trabalhador tem direito a vinte e cinco dias úteis de férias"
    m = medir("x", ["Primeira página sem problemas nenhuns.", f"Início. {frase}. Fim."],
              "Primeira página sem problemas nenhuns.\nInício. Fim.")
    assert m.trechos_falta == [(2, frase, "")]
    assert f"p2: «{frase}»" in diagnostico([m])


def test_paragrafo_longo_de_texto_nao_e_tabela_colapsada():
    prosa = "O trabalhador tem direito a férias e a descanso semanal. " * 15
    tabela = " | ".join(f"Nível {i} | {1000 + i},00" for i in range(40))
    numeros = " ".join(f"{1000 + i},{i:02d}" for i in range(120))
    m = medir("x", [prosa, tabela.replace(" | ", "\n"), numeros],
              "\n".join([prosa.strip(), tabela, numeros]))
    assert [n for n, _ in m.linhas_longas] == [2, 3]
