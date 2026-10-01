"""Controlos de sanidade da extração (revisão MaxQDA de 2026-08-25).

Os dois padrões foram medidos no corpus antes de virarem controlo: a nota
de depósito do art. 494.º CT existe nas 4 convenções verificadas e fecha
o documento; cláusulas sem corpo só aparecem quando algo correu mal na
ordem de leitura.
"""
from crl_markdown.legacy.extractor import estruturar
from crl_markdown.legacy.sanidade import clausulas_sem_corpo, deposito_no_fim, verificar

DEPOSITO = ("Depositado em 23 de janeiro de 2025, a fl. 87 do livro n.º 13, "
            "com o n.º 23/2025, nos termos do artigo 494.º do Código do "
            "Trabalho, aprovado pela Lei n.º 7/2009, de 12 de fevereiro.")

BOM = ("Cláusula 8.ª - Deveres\n"
       "1- O trabalhador deve cumprir as disposições deste AE.\n"
       "Cláusula 9.ª - Garantias\n"
       "É proibido à empresa opor-se ao exercício dos direitos.\n"
       + DEPOSITO + "\n")


# ---------- nota de depósito ----------

def test_deposito_no_fim_aceita_as_duas_formas():
    assert deposito_no_fim("Texto.\n" + DEPOSITO + "\n") is None
    assert deposito_no_fim("Texto.\nDepositado a 17 de julho de 2025, a fl. 111.\n") is None


def test_deteta_texto_depois_do_deposito():
    # AguasNorte e AguasSerraEstrela: matéria de anexos aparecia no fim
    aviso = deposito_no_fim(DEPOSITO + "\n2- Reenquadramento nas categorias.\n")
    assert aviso and "depois da nota de depósito" in aviso
    # o aviso diz qual é a linha (corrida de 2025: 74 avisos sem ela)
    assert "«2- Reenquadramento nas categorias.»" in aviso


def test_nota_de_deposito_partida_em_duas_linhas():
    partida = DEPOSITO.replace(", de 12 de fevereiro.", "")
    assert deposito_no_fim(f"Texto.\n{partida}\nde 12 de fevereiro.\n") is None
    aviso = deposito_no_fim(f"Texto.\n{DEPOSITO}\nde 12 de fevereiro.\n")
    assert aviso and aviso.startswith("1 linha(s)"), "uma nota já fechada não continua"


def test_deteta_ausencia_do_deposito():
    aviso = deposito_no_fim("Cláusula 1.ª - Âmbito\n1- Aplica-se a todos.\n")
    assert aviso and "sem nota de depósito" in aviso


# ---------- depósito colado à assinatura (ACRAL, BTE 31/2026) ----------

def test_deposito_colado_a_assinatura_na_mesma_linha():
    # o extrator une a assinatura e a nota seguidas numa só linha
    texto = ("Texto da convenção.\n"
             "Vânia Elisabete Serfaty Rosa Depositado a 7 de agosto de 2026, "
             "a fl. 150 do livro n.º 13.\n")
    assert deposito_no_fim(texto) is None


# ---------- retificações (CARRISTUR, BTE 31/2026) ----------

def test_retificacao_nao_exige_nota_de_deposito():
    """AE-ALT-RECT: retifica outra convenção, o depósito é o dela."""
    texto = ("Retifica o acordo de empresa publicado no BTE 30/2026.\n"
             "1- O número anterior passa a ler-se como segue.\n")
    assert deposito_no_fim(texto, e_retificacao=True) is None
    # sem a bandeira, o aviso existe — é o comportamento clássico
    assert deposito_no_fim(texto) is not None


def test_verificar_respeita_subtipo_rect():
    doc = {"subtipo": "retificacao", "nos": []}
    texto = ("1- O número anterior passa a ler-se como segue.\n")
    assert deposito_no_fim(texto, e_retificacao=True) is None
    avisos = verificar(doc, texto)
    # a retificação não gera aviso de depósito (pode gerar outros)
    assert not any("depósito" in a for a in avisos)


# ---------- cláusulas sem corpo ----------

def test_clausula_vazia_e_detetada():
    # LAGOSemFORMA: o conteúdo da cláusula 9.ª tinha ido parar antes do
    # cabeçalho, deixando a cláusula vazia
    texto = ("Cláusula 9.ª - Garantias do trabalhador\n"
             "CAPÍTULO IV - Categorias profissionais\n"
             "Cláusula 10.ª - Categorias\n"
             "1- As categorias constam do anexo II.\n")
    doc, final = estruturar(texto, "t")
    falhas = clausulas_sem_corpo(doc, final)
    assert any("Cláusula 9.ª" in f and "sem conteúdo" in f for f in falhas)


def test_corpo_sem_ponto_final_e_detetado():
    texto = ("Cláusula 1.ª - Âmbito\n"
             "1- Aplica-se a todos os trabalhadores\n")
    doc, final = estruturar(texto, "t")
    assert any("sem frase terminada" in f for f in clausulas_sem_corpo(doc, final))


def test_documento_saudavel_nao_gera_avisos():
    doc, final = estruturar(BOM, "t")
    assert verificar(doc, final) == []


def test_tabela_no_corpo_conta_como_conteudo():
    # uma cláusula que remete para tabela tem texto antes dela; o controlo
    # não pode disparar por a tabela em si não ter ponto final
    texto = ("Cláusula 21.ª - Retribuição\n"
             "1- A retribuição consta da tabela seguinte.\n"
             "Níveis | Escalão 1\n"
             "1 | 1 234,56\n")
    doc, final = estruturar(texto, "t")
    assert clausulas_sem_corpo(doc, final) == []


# ---------- zero cláusulas (ISSUE-0014, issue #64) ----------

def test_retificacao_sem_clausulas_e_o_esperado():
    """As quatro CARRISTUR do BTE 31/2026 eram retificações (AE-ALT-RECT):
    zero cláusulas era o resultado certo, e o relatório dizia «truncado?»."""
    from crl_markdown.legacy.sanidade import AVISO_RETIFICACAO_SEM_ARTICULADO

    doc, final = estruturar("Retifica o acordo publicado no BTE n.º 27.\n"
                            "Na cláusula 5.ª, onde se lê 20 deve ler-se 25.\n", "t")
    doc["tipo_registo"] = "AE-ALT-RECT"
    avisos = verificar(doc, final)
    assert avisos == [AVISO_RETIFICACAO_SEM_ARTICULADO]
    assert not any("truncado" in a for a in avisos)


def test_zero_clausulas_fora_de_retificacao_diz_o_que_pode_ser():
    from crl_markdown.legacy.sanidade import AVISO_SEM_ESTRUTURA

    doc, final = estruturar("Texto corrido sem cabeçalhos.\n" + DEPOSITO + "\n", "t")
    assert verificar(doc, final) == [AVISO_SEM_ESTRUTURA]




# ---------- retificação pelo título (revisão do PR #88) ----------

TITULO_CARRISTUR = (
    "PRIVADO\nREGULAMENTAÇÃO DO TRABALHO\nCONVENÇÕES COLETIVAS\n"
    "Acordo de empresa entre a CARRISTUR - Inovação em Transportes Urbanos e "
    "Regionais, Sociedade Unipessoal L.da e a Associação Sindical dos "
    "Trabalhadores da Carris e Participadas (ASPTC) - Retificação\n"
    "Por ter sido publicado com inexatidão no Boletim do Trabalho e Emprego, "
    "n.º 27, de 22 de julho de 2026, procede-se à sua retificação.\n")




def test_titulo_de_retificacao_so_olha_para_o_titulo():
    from crl_markdown.legacy.sanidade import titulo_de_retificacao

    assert titulo_de_retificacao(TITULO_CARRISTUR)
    assert titulo_de_retificacao(TITULO_CARRISTUR.replace("Retificação", "Rectificação"))
    # «retificação» no corpo, depois do primeiro cabeçalho, não conta
    corpo = ("Contrato coletivo entre a A e o B - Revisão global\n"
             "Cláusula 1.ª - Âmbito\n"
             "O anexo II - Retificação de categorias aplica-se a todos.\n")
    assert not titulo_de_retificacao(corpo)
    # nem a palavra solta no título, sem o travessão do subtipo
    assert not titulo_de_retificacao("Acordo de retificação de horários\n")


def test_os_exemplos_publicados_nao_sao_retificacoes():
    from pathlib import Path

    from crl_markdown.legacy.sanidade import titulo_de_retificacao

    raiz = Path(__file__).resolve().parents[2] / "examples"
    textos = list(raiz.glob("*.md"))
    assert textos
    for p in textos:
        assert not titulo_de_retificacao(p.read_text(encoding="utf-8")), p.name


ALTERACAO = ("Acordo de empresa entre a X e o Y - Alteração salarial e outras\n"
             "Artigo 1.º - Alteração\n"
             "As cláusulas 5.ª e 7.ª do acordo de empresa publicado no BTE n.º 3, "
             "de 2020, passam a ter a redação seguinte:\n"
             "Cláusula 5.ª - Férias\nO período de férias é de 25 dias.\n"
             "{setima}")


def test_artigo_que_anuncia_as_clausulas_seguintes_nao_esta_truncado():
    """Issue #83 (384 e 385 do BTE 31/2026): o artigo 1.º termina em dois
    pontos porque as cláusulas que anuncia vêm a seguir."""
    doc, final = estruturar(ALTERACAO.format(
        setima="Cláusula 7.ª - Subsídios\nO subsídio é de 5 euros.\n"), "x")
    assert clausulas_sem_corpo(doc, final) == []


def test_enumeracao_sem_alineas_continua_a_ser_truncada():
    """O caso negativo: uma cláusula que abre uma enumeração e é seguida por
    outra cláusula perdeu as alíneas. Não anuncia redação nenhuma."""
    doc, final = estruturar(ALTERACAO.format(
        setima="Cláusula 7.ª - Subsídios\nOs trabalhadores têm direito a:\n"
               "Cláusula 8.ª - Outra\nTexto final.\n"), "x")
    assert clausulas_sem_corpo(doc, final) == [
        "Cláusula 7.ª - Subsídios: corpo sem frase terminada em ponto"]


def test_artigo_que_anuncia_mas_acaba_o_documento_continua_a_dar_aviso():
    """Anunciar a redação seguinte e não ter nada a seguir é truncagem."""
    doc, final = estruturar(
        "Artigo 1.º - Alteração\nAs cláusulas 5.ª e 7.ª passam a ter a redação seguinte:\n",
        "x")
    assert clausulas_sem_corpo(doc, final) == [
        "Artigo 1.º - Alteração: corpo sem frase terminada em ponto"]


def test_corpo_de_tabela_formula_ou_omitido_nao_e_truncado():
    """Corrida de 2025: «Cálculo da remuneração» (uma fórmula), uma tabela
    de valores e «Cláusula transitória (...)» não se escrevem em frases."""
    texto = ("Cláusula 34.ª - Cálculo da remuneração\n"
             "RH = (Rm × 12) / (52 × n)\n"
             "Cláusula 37.ª - Cláusula transitória\n(...)\n"
             "Cláusula 38.ª - Valores\n"
             "\x02TABELA\nDiária completa | 88,20 €\n\x03TABELA\n"
             "Cláusula 39.ª - Parentalidade\nAplica-se o regime legal\n")
    doc, final = estruturar(texto, "t")
    assert clausulas_sem_corpo(doc, final) == [
        "Cláusula 39.ª - Parentalidade: corpo sem frase terminada em ponto"]


def test_ordinal_abreviado_fecha_a_frase():
    """Corrida de 2025: 80 dos 134 corpos «sem frase terminada em ponto»
    acabavam numa remissão; a redação não põe outro ponto depois de «36.ª»."""
    doc, final = estruturar(
        "Cláusula 38.ª - Mapas de horário\nA instituição disponibiliza ao "
        "sindicato os mapas de horário a que se referem as cláusulas 34.ª a 36.ª\n"
        "Cláusula 66.ª - Poder disciplinar\nÉ o previsto nos artigos 328.º a 332.º\n"
        "Cláusula 67.ª - Outra\nAplica-se o regime legal\n", "x")
    assert clausulas_sem_corpo(doc, final) == [
        "Cláusula 67.ª - Outra: corpo sem frase terminada em ponto"]


def test_dois_pontos_antes_de_cabecalho_como_no_pdf_e_redacao():
    """SETAAB de 2025: a «Parentalidade» acaba em «nomeadamente:» e, no PDF
    também, a cláusula seguinte vem logo a seguir. É redação. A prova é local:
    se o PDF tem alguma coisa entre os dois, o aviso fica, por pequena que
    seja a perda no documento (revisão do PR #92)."""
    from crl_markdown.legacy.completude import palavras
    doc, final = estruturar(ALTERACAO.format(
        setima="Cláusula 7.ª - Parentalidade\nSão assegurados os direitos "
               "da lei, nomeadamente:\nCláusula 8.ª - Outra\nTexto final.\n"), "x")
    aviso = ["Cláusula 7.ª - Parentalidade: corpo sem frase terminada em ponto"]
    pdf_igual = palavras(final)
    pdf_com_alineas = palavras(final.replace(
        "nomeadamente:\n", "nomeadamente:\na) Licença parental inicial;\n"))
    assert clausulas_sem_corpo(doc, final) == aviso
    assert clausulas_sem_corpo(doc, final, pdf_igual) == []
    assert clausulas_sem_corpo(doc, final, pdf_com_alineas) == aviso
    # quatro palavras em mil: a cobertura do documento seria 99,6%
    assert len(pdf_com_alineas) - len(pdf_igual) == 4

def test_alteracao_salarial_so_com_numeros_e_tabelas_nao_tem_articulado():
    """DHL de 2025: «- Alteração salarial e outras», números e uma tabela.
    Zero cláusulas é o esperado; uma linha com forma de cláusula que o
    extrator não reconheceu continua a dar o aviso de estrutura."""
    from crl_markdown.legacy.sanidade import (AVISO_ALTERACAO_SALARIAL_SEM_ARTICULADO,
                              AVISO_SEM_ESTRUTURA)
    titulo = ("Acordo de empresa entre a DHL Aviation NV e o Sindicato - SITAVA - "
              "Alteração salarial e outras\n")
    corpo = ("Para efeitos do disposto no artigo 492.º, declara-se que são abrangidos 40 "
             "trabalhadores.\n\x02TABELA\nCláusula | Designação | Valor\n"
             "Grupo | Chefe de secção | 2 585,00 €\n\x03TABELA\n" + DEPOSITO + "\n")
    doc, final = estruturar(titulo + corpo, "x")
    assert AVISO_ALTERACAO_SALARIAL_SEM_ARTICULADO in verificar(doc, final)
    doc, final = estruturar(titulo + "Cláusula nova - Ajudas de custo\n" + corpo, "x")
    assert AVISO_SEM_ESTRUTURA in verificar(doc, final)
