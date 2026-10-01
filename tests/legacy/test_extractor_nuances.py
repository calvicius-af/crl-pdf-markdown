"""Nuances de reconhecimento apanhadas na revisão MaxQDA de 2026-08-25.

Três padrões que escapavam, com os respetivos guardas contra falsos
positivos (o objetivo é flexibilidade sem ruído novo):

- ordinal separado do número pelo PDF ("Artigo 1. º");
- pontuação forte seguida de fecho de parêntesis ("(Valores em euros.)");
- fim do bloco de título da convenção ("… - Revisão global").
"""
from crl_markdown.legacy.extractor import estruturar, juntar_linhas


# ---------- ordinal separado ----------

def test_rotulo_de_artigo_com_ordinal_separado():
    # AguasSerraEstrela: o docling devolve "Artigo 1. º" e o rótulo saía
    # partido ao meio ("Artigo 1. - º")
    texto = "Artigo 1. º\nValoração das habilitações\n1- Por «habilitação» entende-se.\n"
    doc, _ = estruturar(texto, "t")
    art = [n for n in doc["nos"] if n["tipo"] == "artigo"]
    assert art and art[0]["rotulo"] == "Artigo 1.º - Valoração das habilitações"


def test_ordinal_separado_tambem_no_corpo():
    texto = "Artigo 1.º\nHabilitações\n1- Inferior ao 12. º ano de escolaridade.\n"
    _doc, final = estruturar(texto, "t")
    assert "12.º ano" in final


def test_nao_mexe_em_numeros_com_ponto_final():
    # "…do número 2. Os restantes…" não é um ordinal partido
    texto = "Cláusula 1.ª\nÂmbito\n1- Aplica-se o número 2. Os restantes seguem.\n"
    _doc, final = estruturar(texto, "t")
    assert "número 2. Os restantes" in final


# ---------- pontuação forte com fecho de parêntesis ----------

def test_parentesis_depois_do_ponto_fecha_a_frase():
    # TRATOLIXO: "(Valores em euros.)" colava-se ao título seguinte
    texto = "(Valores em euros.)\nRegulamento de Admissões e Carreiras"
    assert juntar_linhas(texto) == texto


def test_aspas_depois_do_ponto_fecham_a_frase():
    texto = 'Diz a norma «o trabalhador tem direito.»\nSegue-se outro parágrafo.'
    assert juntar_linhas(texto) == texto


def test_parentesis_sem_pontuacao_continua_a_juntar():
    # sem pontuação forte lá dentro, o parêntesis não fecha nada
    texto = "O acordo (adiante designado AE)\naplica-se a todos."
    assert juntar_linhas(texto) == "O acordo (adiante designado AE) aplica-se a todos."


# ---------- fim do bloco de título ----------

def test_titulo_da_convencao_separa_se_do_preambulo():
    texto = ("Acordo de empresa entre a Empresa X e o Sindicato Y - Revisão global\n"
             "Aos vinte dias do mês de janeiro de 2025, as partes acordam.")
    assert juntar_linhas(texto) == texto


def test_titulo_com_texto_consolidado():
    texto = ("Acordo coletivo entre a Empresa X e outras - Alteração salarial "
             "e outras e texto consolidado\n"
             "Aos dez dias do mês de março de 2025, as partes acordam.")
    assert juntar_linhas(texto) == texto


def test_a_regra_do_titulo_nao_se_aplica_ao_corpo():
    # a mesma expressão a meio do documento continua a juntar-se: a regra
    # vale só no cabeçalho, onde o bloco de título vive
    corpo = "\n".join(f"{i}- Número de enchimento do documento." for i in range(1, 25))
    texto = (corpo + "\nAs partes acordam proceder a uma revisão global\n"
             "do clausulado no prazo de um ano.")
    assert "revisão global do clausulado" in juntar_linhas(texto)


# ---------- número de parágrafo sem separador ----------

def test_numero_sem_separador_recuperado():
    # AguasSerraEstrela: o PDF tem "3- São considerados", o docling dá "3São"
    texto = "Artigo 5.º\nCargos\n3São considerados cargos de interesse público.\n"
    _doc, final = estruturar(texto, "t")
    assert "3- São considerados" in final


def test_numero_composto_sem_separador():
    texto = "Artigo 5.º\nFatores\n2.1No fator antiguidade entra o número de anos.\n"
    _doc, final = estruturar(texto, "t")
    assert "2.1- No fator" in final


def test_nao_mexe_em_ano_nem_em_ordinal():
    texto = ("Cláusula 1.ª\nÂmbito\n"
             "1- O acordo de 2025 aplica-se.\n"
             "2- Vigora desde o 12.º ano de escolaridade.\n")
    _doc, final = estruturar(texto, "t")
    assert "de 2025 aplica-se" in final and "12.º ano" in final


# ---------- numeração: ordinais a sério ----------

def test_titulo_de_capitulo_nao_vira_clausula_vazia():
    # AguasNorte: o CAPÍTULO XV chama-se "Cláusula geral e transitória" e
    # a palavra "geral" era lida como número de cláusula
    texto = ("CAPÍTULO XV\nCláusula geral e transitória\n"
             "Cláusula 73.ª\nCláusula geral e transitória\n"
             "1- Todas as disposições que violem a lei não são aplicáveis.\n")
    doc, _ = estruturar(texto, "t")
    rotulos = [n["rotulo"] for n in doc["nos"] if n["tipo"] == "clausula"]
    assert rotulos == ["Cláusula 73.ª - Cláusula geral e transitória"]
    cap = [n["rotulo"] for n in doc["nos"] if n["tipo"] == "capitulo"]
    assert cap == ["CAPÍTULO XV - Cláusula geral e transitória"]


def test_numeracao_por_extenso_continua_reconhecida():
    texto = ("Cláusula décima segunda\nFérias\n1- O trabalhador tem direito.\n")
    doc, _ = estruturar(texto, "t")
    cl = [n["rotulo"] for n in doc["nos"] if n["tipo"] == "clausula"]
    assert cl == ["Cláusula décima segunda - Férias"]


def test_marcador_de_travessao_colado_faz_paragrafo():
    # TRATOLIXO: "-25 % pela primeira hora" é uma alínea, não texto corrido
    texto = ("Cláusula 76.ª - Acréscimos\n1- Os acréscimos são:\n"
             "-25 % pela primeira hora;\n-37,5 % pelas seguintes;\n")
    doc, _ = estruturar(texto, "t")
    assert sum(1 for n in doc["nos"] if n["tipo"] == "paragrafo") == 3


def test_artigo_unico_e_clausula_unica_sao_reconhecidos():
    # regressão apanhada na revisão de 2026-08-27: ao restringir a
    # numeração por extenso a ordinais, "Artigo único" (redação corrente
    # quando o instrumento tem um só artigo — EMARP 2025, anexo I) deixou
    # de ser cabeçalho: o nó desaparecia e o rótulo colava-se ao corpo
    # frase do EMARP real (>90 chars, logo não é candidata a título — a
    # ambiguidade entre título e primeira frase está registada à parte)
    texto = ("ANEXO I - Mapa de pessoal\n"
             "Artigo único\n"
             "Excecionalmente, poderá ser atribuído o nível remuneratório "
             "subsequente ao indicado no mapa de pessoal no caso de ausência "
             "de candidatura.\n")
    doc, final = estruturar(texto, "t")
    arts = [n for n in doc["nos"] if n["tipo"] == "artigo"]
    assert [n["rotulo"] for n in arts] == ["Artigo único"]
    assert "Artigo único\nExcecionalmente" in final  # não se colam

    texto = "Cláusula única\nÂmbito\n1- Aplica-se a todos.\n"
    doc, _ = estruturar(texto, "t")
    cl = [n["rotulo"] for n in doc["nos"] if n["tipo"] == "clausula"]
    assert cl == ["Cláusula única - Âmbito"]


def test_titulo_nomeado_continua_excluido():
    # o contraponto: "geral e transitória" é título, não designador
    from crl_markdown.legacy.extractor import RE_CLAUSULA
    assert not RE_CLAUSULA.match("Cláusula geral e transitória")
    assert not RE_CLAUSULA.match("Cláusula final")


def test_remissao_em_minusculas_nao_cria_no_falso():
    # revisão de 2026-08-27: com IGNORECASE, uma remissão partida pelo PDF
    # ("… nos termos do\nartigo 253.º do Código do Trabalho…") virava um nó
    # de artigo que roubava o corpo à cláusula real — 4 casos nos 6
    # documentos de 2025, um deles com 3746 caracteres mal atribuídos
    texto = ("Cláusula 54.ª - Atualização\n"
             "1- A atualização faz-se de acordo com a fórmula prevista na\n"
             "cláusula 33.ª supra.\n")
    doc, _ = estruturar(texto, "t")
    rotulos = [n["rotulo"] for n in doc["nos"] if n["tipo"] in ("clausula", "artigo")]
    assert rotulos == ["Cláusula 54.ª - Atualização"]


def test_cabecalho_em_maiusculas_continua_a_contar():
    for texto, tipo in [("CLÁUSULA 1.ª\nÂmbito\n1- Aplica-se.\n", "clausula"),
                        ("ARTIGO 5.º\nObjeto\n1- Define o objeto.\n", "artigo")]:
        doc, _ = estruturar(texto, "t")
        assert [n["tipo"] for n in doc["nos"] if n["tipo"] == tipo] == [tipo]


# ---------- designadores de posição (ISSUE #40) ----------

def test_clausula_previa_e_um_cabecalho():
    # AEVP/FESAHT, BTE 31/2026 (revisão parcial): a convenção abre com
    # "Cláusula prévia", que fixa o âmbito da revisão. Sem a reconhecer, o
    # título e os três números eram absorvidos pelo preâmbulo
    texto = ("Cláusula prévia Âmbito de revisão\n"
             "1- O presente contrato coletivo revê parcialmente o anterior.\n"
             "2- O presente CCT aplica-se aos trabalhadores da associação.\n"
             "3- Nas matérias não alteradas mantém-se a redação anterior.\n")
    doc, _ = estruturar(texto, "t")
    cl = [n for n in doc["nos"] if n["tipo"] == "clausula"]
    assert [n["rotulo"] for n in cl] == ["Cláusula prévia - Âmbito de revisão"]


def test_clausula_previa_subsegmenta_os_numeros():
    # a subsegmentação só atua sobre nós já classificados como cláusula/artigo,
    # portanto é consequência direta do reconhecimento — e é o que a
    # codificação temática precisa para marcar cada número
    texto = ("Cláusula prévia Âmbito de revisão\n"
             "1- O presente contrato coletivo revê parcialmente o anterior.\n"
             "2- O presente CCT aplica-se aos trabalhadores da associação.\n"
             "3- Nas matérias não alteradas mantém-se a redação anterior.\n")
    doc, _ = estruturar(texto, "t")
    par = [n for n in doc["nos"] if n["tipo"] == "paragrafo"]
    assert len(par) == 3


def test_designadores_aceites_e_recusados():
    from crl_markdown.legacy.extractor import RE_ARTIGO, RE_CLAUSULA
    assert RE_CLAUSULA.match("Cláusula prévia")
    assert RE_CLAUSULA.match("CLÁUSULA PRÉVIA")
    assert RE_CLAUSULA.match("Cláusula preliminar Objeto")
    assert RE_ARTIGO.match("Artigo preliminar")
    # sem acento continua a passar: nos cabeçalhos em maiúsculas o BTE nem
    # sempre o escreve, e é a mesma tolerância já dada a "CLAUSULA"
    assert RE_CLAUSULA.match("CLAUSULA PREVIA")
    # o contraponto: a lista é fechada, e o guarda trava prosa
    assert not RE_CLAUSULA.match("Cláusula geral e transitória")
    assert not RE_CLAUSULA.match("Cláusula final")
    assert not RE_CLAUSULA.match("Cláusula previa o pagamento de um subsídio.")


def test_prosa_com_previa_nao_rouba_o_corpo_da_clausula():
    # o caso que o guarda evita: a linha de prosa ficaria como cabeçalho e
    # levaria consigo o resto do texto da cláusula real
    texto = ("Cláusula 3.ª\nSubsídio de refeição\n"
             "1- O valor é atualizado anualmente.\n"
             "Cláusula previa o pagamento em duodécimos, o que se mantém.\n")
    doc, _ = estruturar(texto, "t")
    cl = [n for n in doc["nos"] if n["tipo"] == "clausula"]
    assert [n["rotulo"] for n in cl] == ["Cláusula 3.ª - Subsídio de refeição"]


# ---------- título com mais de 60 caracteres (ISSUE-0017) ----------

def test_titulo_entre_60_e_90_caracteres_nao_se_funde_ao_corpo():
    # ACIBARCELOS_IndependenteSector: o docling dá o título e o corpo já
    # separados, mas o limite de 60 caracteres do "é título?" na junção de
    # linhas era mais apertado do que o de _titulo_candidato (90), e um
    # título de 65 caracteres fundia-se com a frase seguinte
    titulo = "Organização de serviços de segurança, higiene e saúde no trabalho"
    assert len(titulo) == 65
    texto = (f"Cláusula 68.ª\n{titulo}\n"
             "Independentemente do número de trabalhadores, a entidade "
             "empregadora é obrigada a organizar serviços de segurança.\n")
    doc, final = estruturar(texto, "t")
    cl = [n for n in doc["nos"] if n["tipo"] == "clausula"]
    assert cl[0]["rotulo"] == f"Cláusula 68.ª - {titulo}"
    assert "Independentemente do número" in final


def test_paragrafo_de_corpo_com_virgula_continua_a_juntar_se():
    # memo 23: alargar o limite não pode voltar a fundir um parágrafo do
    # corpo com a linha seguinte só por ser curto — a vírgula final é o
    # sinal de que a frase continua, não um título
    texto = ("Preâmbulo\n"
             "Cumpre em primeiro lugar referir que a existência de qualquer organização,\n"
             "pressupõe respostas colectivas.")
    saida = juntar_linhas(texto)
    assert "organização, pressupõe" in saida


# ---------- data de outorga nunca é título (ISSUE-0018) ----------

def test_data_de_outorga_nao_vira_titulo_do_anexo():
    # EmpresaMetropolitana_SINTAP: quando a tabela do anexo não produz
    # conteúdo, o cabeçalho "ANEXO III" fica seguido, sem nada entre os
    # dois, pela data que assina o documento — que não é o título do anexo
    texto = ("ANEXO III\nMaia, 14 de julho de 2026.\n"
             "Pela Empresa Exemplo, EM:\nJoão Silva , na qualidade de mandatário.\n")
    doc, final = estruturar(texto, "t")
    anexo = [n for n in doc["nos"] if n["tipo"] == "anexo"]
    assert anexo[0]["rotulo"] == "ANEXO III"
    assert "Maia, 14 de julho de 2026." in final


def test_linha_de_tabela_nao_vira_titulo_do_anexo():
    # 382 de 2026: o ANEXO III não tem título próprio, só as grelhas de
    # carreiras; a primeira linha da tabela colava-se ao rótulo, «ANEXO III -
    # | Carreira de Direção Geral», e saía da tabela (ISSUE-0018)
    from crl_markdown.legacy.extractor import MARCA_TABELA_FIM, MARCA_TABELA_INI
    texto = (f"ANEXO III\n{MARCA_TABELA_INI}\n | Carreira de Direção Geral\n"
             f"Sub-Nível | I | II\n{MARCA_TABELA_FIM}\n")
    doc, final = estruturar(texto, "t")
    anexo = [n for n in doc["nos"] if n["tipo"] == "anexo"]
    assert anexo[0]["rotulo"] == "ANEXO III"
    assert "| Carreira de Direção Geral" in final.split("ANEXO III", 1)[1]
    # uma linha curta fora da tabela continua a ser o título
    doc, _ = estruturar("ANEXO III\nTabela salarial\nTexto.\n", "t")
    assert [n["rotulo"] for n in doc["nos"] if n["tipo"] == "anexo"] == [
        "ANEXO III - Tabela salarial"]


# ---------- "Declaração" como início de bloco (ISSUE-0015, ponto 3) ----------

def test_declaracao_nao_se_cola_ao_nome_anterior():
    # AEVP-FESAHT: quando um sindicato assina em representação de outros, o
    # PDF traz uma "Declaração" própria — sem a quebra, cola-se ao nome do
    # signatário anterior, escondendo a representação de terceiros
    texto = "José Eduardo Pereira Andrade\nDeclaração A FESAHT representa também:\n"
    assert juntar_linhas(texto) == \
        "José Eduardo Pereira Andrade\nDeclaração A FESAHT representa também:\n"


def test_declaracao_continua_a_juntar_o_que_vem_a_seguir():
    # a quebra é só antes de "Declaração" — o resto da frase junta-se como
    # qualquer outro parágrafo, sem se tornar um cabeçalho a sério
    texto = "Declaração A FESAHT representa também os seguintes\nsindicatos:\n"
    assert juntar_linhas(texto) == \
        "Declaração A FESAHT representa também os seguintes sindicatos:\n"


# ---------- corrida de 2025: corpo, título e assinaturas ----------

def test_prosa_com_pelo_e_dois_pontos_nao_e_assinatura():
    """LPFP de 2025: «Pelo presente instrumento, […] passará a ter a seguinte
    redação:» abria o bloco das assinaturas e a cláusula ficava vazia."""
    texto = ("Cláusula primeira\nPelo presente instrumento, no que diz respeito ao "
             "regime contributivo transitório, as partes acordam alterar o teor do "
             "artigo 32.º-A, que passará a ter a seguinte redação:\n"
             "Artigo 32.º-A - Disposição transitória\n1- O jogador tem direito.\n"
             "Lisboa, 3 de julho de 2025.\nPela Liga Portuguesa de Futebol Profissional:\n"
             "Fulano de Tal, presidente.\nPelos outorgantes:\nBeltrano.\n")
    doc, final = estruturar(texto, "t")
    rotulos = [n["rotulo"] for n in doc["nos"]]
    assert rotulos.count("ASSINATURAS") == 1, rotulos
    primeira = next(n for n in doc["nos"] if n["rotulo"] == "Cláusula primeira")
    assert "Pelo presente instrumento" in final[primeira["char_start"]:primeira["char_end"]]
    assimaturas = next(n for n in doc["nos"] if n["rotulo"] == "ASSINATURAS")
    assert "Pelos outorgantes:" in final[assimaturas["char_start"]:assimaturas["char_end"]]


def test_seccao_em_minusculas_nao_e_cabecalho():
    """FNOP de 2025: «… subsecção XI da» e, na linha seguinte, «secção II do
    capítulo II do Código do Trabalho.» abria uma secção falsa."""
    doc, final = estruturar(
        "Cláusula 51.ª - Faltas\nEm matéria de faltas aplica-se o previsto na "
        "legislação, designadamente, o previsto na subsecção XI da\nsecção II "
        "do capítulo II do Código do Trabalho.\n", "t")
    assert not [n for n in doc["nos"] if n["tipo"] == "seccao"]
    assert "subsecção XI da secção II do capítulo II" in final


def test_revogado_e_texto_omitido_sao_corpo_e_nao_titulo():
    """LPFP e APDL de 2025: «[Revogado.]» na linha a seguir ao número e
    «(...)» no fim da linha do cabeçalho viravam título, e o artigo ficava
    sem conteúdo."""
    doc, final = estruturar(
        "Artigo 2.º\n[Revogado.]\n"
        "Cláusula 37.ª - Cláusula transitória (Anterior cláusula 35.ª) (...)\n"
        "Cláusula 38.ª - Outra\nTexto.\n", "t")
    nos = {n["rotulo"]: final[n["char_start"]:n["char_end"]] for n in doc["nos"]}
    assert nos["Artigo 2.º"] == "Artigo 2.º\n[Revogado.]\n"
    assert nos["Cláusula 37.ª - Cláusula transitória (Anterior cláusula 35.ª)"].endswith("\n(...)\n")


# ---------- anexos: numeração com letra, partes e regulamentos ----------

def test_anexo_com_letra_nao_perde_a_palavra_anexo():
    """NAV e Autoridade de Seguros de 2025: em «ANEXO A» o rótulo partia-se no
    primeiro «A» e a palavra ANEXO saía do texto (« - A»)."""
    doc, final = estruturar("ANEXO A\nDescrição global de funções\nTexto.\n"
                            "ANEXO II-A\nClassificação profissional\nTexto.\n", "t")
    rotulos = [n["rotulo"] for n in doc["nos"] if n["tipo"] == "anexo"]
    assert rotulos == ["ANEXO A - Descrição global de funções",
                       "ANEXO II-A - Classificação profissional"]
    assert final.startswith("ANEXO A - Descrição")


def test_partes_de_um_anexo_ficam_dentro_dele():
    """INATEL de 2025: a tabela salarial vinha no «ANEXO I - (A)», irmão do
    «ANEXO I - Tabela salarial», e a auditoria dava-a fora do nó."""
    doc, _ = estruturar("ANEXO I - Tabela salarial\nPressupostos.\n"
                        "ANEXO I - (A)\nTabela.\nANEXO II-A\nOutro.\nANEXO II-B\nMais.\n", "t")
    anexos = {n["rotulo"]: n for n in doc["nos"] if n["tipo"] == "anexo"}
    assert anexos["ANEXO I - (A)"]["pai"] == anexos["ANEXO I - Tabela salarial"]["id"]
    # sem um «ANEXO II» aberto, II-A e II-B são irmãos
    assert anexos["ANEXO II-A - Outro."]["pai"] is None
    assert anexos["ANEXO II-B - Mais."]["pai"] is None


def test_regulamento_em_anexo_guarda_os_seus_capitulos():
    """NAV, CARRIS, INOVA de 2025: o anexo que abre com um capítulo é um
    texto articulado, e os capítulos, secções e artigos são dele."""
    doc, _ = estruturar(
        "Cláusula 1.ª - Âmbito\nTexto.\n"
        "ANEXO VII - Regulamento de Carreiras Profissionais\n"
        "CAPÍTULO I - Objeto\nArtigo 1.º - Objeto\nTexto do artigo.\n"
        "CAPÍTULO II - Carreiras\nArtigo 2.º - Níveis\nTexto do artigo.\n"
        "ANEXO VIII - Tabela\nTexto.\n", "t")
    nos = {n["rotulo"]: n for n in doc["nos"]}
    anexo = nos["ANEXO VII - Regulamento de Carreiras Profissionais"]["id"]
    assert nos["CAPÍTULO I - Objeto"]["pai"] == anexo
    assert nos["CAPÍTULO II - Carreiras"]["pai"] == anexo
    assert nos["Artigo 2.º - Níveis"]["pai"] == nos["CAPÍTULO II - Carreiras"]["id"]
    assert nos["ANEXO VIII - Tabela"]["pai"] is None


def test_capitulo_depois_do_corpo_de_um_anexo_fecha_o_anexo():
    """O capítulo que vem depois de um anexo com corpo (a republicação que
    começa depois dos anexos da alteração) não é do anexo."""
    doc, _ = estruturar("ANEXO I - Tabela\nNível | Valor\n"
                        "CAPÍTULO I - Disposições gerais\nCláusula 1.ª - Âmbito\nTexto.\n", "t")
    nos = {n["rotulo"]: n for n in doc["nos"]}
    assert nos["CAPÍTULO I - Disposições gerais"]["pai"] is None


def test_texto_omitido_colado_ao_titulo_e_corpo():
    """APDL de 2025, no PDF: «Cláusula 37.ª» / «Cláusula transitória» /
    «(Anterior cláusula 35.ª)» / «(...)». A junção de linhas cola o «(...)»
    ao título, e a cláusula ficava sem conteúdo."""
    doc, final = estruturar("Cláusula 37.ª\nCláusula transitória (Anterior cláusula 35.ª) (...)\n"
                            "Cláusula 38.ª - Outra\nTexto.\n", "t")
    nos = {n["rotulo"]: final[n["char_start"]:n["char_end"]] for n in doc["nos"]}
    assert nos["Cláusula 37.ª - Cláusula transitória (Anterior cláusula 35.ª)"].endswith("\n(...)\n")


# ---------- #29: títulos e preâmbulos partidos no cabeçalho ----------

CABECALHO = "PRIVADO\nREGULAMENTAÇÃO DO TRABALHO\nCONVENÇÕES COLETIVAS\n"


def test_titulo_partido_antes_do_travessao_da_sigla_junta_se():
    """AARibatejo, AGERE, APICER, CTT Expresso de 2025: o título parte-se
    antes do travessão que liga a sigla ao nome («… e Afins» / «- SETAAB -
    Revisão global»), e o travessão no início da linha mantinha a quebra."""
    texto = juntar_linhas(CABECALHO + "Contrato coletivo entre a AARibatejo e o Sindicato "
                          "Nacional dos Trabalhadores da Agricultura, Bebidas e Afins\n"
                          "- SETAAB - Revisão global\nCláusula 1.ª - Âmbito\n")
    assert ("Bebidas e Afins - SETAAB - Revisão global\nCláusula 1.ª" in texto), texto


def test_subtipo_alteracao_salarial_e_outra_fecha_o_titulo():
    """AHP, UMP e CTT Expresso de 2025: «- Alteração salarial e outra», no
    singular, não fechava o título, que se colava ao preâmbulo."""
    texto = juntar_linhas(CABECALHO + "Contrato coletivo entre a AHP e o SITESE - "
                          "Alteração salarial e outra\nA Associação da Hotelaria e o "
                          "Sindicato acordam a revisão parcial.\n")
    assert "Alteração salarial e outra\nA Associação" in texto, texto


def test_lista_com_travessoes_nao_se_junta():
    """A regra do travessão vale só no cabeçalho, depois de uma linha sem
    pontuação que não é ela própria um item: as listas ficam como estão."""
    texto = juntar_linhas("Cláusula 5.ª - Direitos\nOs trabalhadores têm direito a:\n"
                          "- Férias\n- Subsídio de Natal\n")
    assert "a:\n- Férias\n- Subsídio de Natal" in texto


def test_subtipo_alteracao_sozinho_e_capitulo_so_com_o_numero():
    """CARRIS, APDL, EMAS Beja e VIMAGUA de 2025 fecham o título em «-
    Alteração», sem mais; e o ULSAS numera o capítulo só com «I», sem a
    palavra CAPÍTULO. Os dois colavam o título ao que vinha a seguir."""
    texto = juntar_linhas(CABECALHO + "Acordo coletivo entre a APDL e a FECTRANS - Alteração\n"
                          "A presente revisão altera a convenção publicada.\n")
    assert "FECTRANS - Alteração\nA presente revisão" in texto, texto
    texto = juntar_linhas(CABECALHO + "Acordo de empresa entre a ULS e o Sindicato - STMO\n"
                          "I\nÁrea, âmbito, vigência, denúncia e revisão\n")
    assert "- STMO\nI" in texto, texto
