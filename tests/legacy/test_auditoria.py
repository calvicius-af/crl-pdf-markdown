"""Testes da auditoria cruzada de tabelas (guardiões de 2026-09-17).

O que se protege aqui: uma tabela perdida na extração tem de ser
visível no relatório — como divergência entre extratores ou como anexo
de remuneração sem tabela — em vez de desaparecer em silêncio.
"""
from crl_markdown.legacy.auditoria import (_aviso_tabela_rodada, contar_blocos_tabela,
                          divergencias, tabelas_esperadas)
from crl_markdown.legacy.extractor import estruturar


# ------------------------------------------------------- contagem de blocos

def test_conta_blocos_de_tabela():
    texto = ("Antes.\n"
             "A | B | C\n"
             "1 | 2 | 3\n"
             "4 | 5 | 6\n"
             "Meio.\n"
             "X | Y\n"
             "Z | W\n"
             "Fim.\n")
    assert contar_blocos_tabela(texto) == 2


def test_linha_isolada_com_pipe_nao_e_bloco():
    texto = "Uma frase | outra parte da frase\nFim.\n"
    assert contar_blocos_tabela(texto) == 0


def test_texto_sem_tabelas_devolve_zero():
    assert contar_blocos_tabela("Cláusula 1.ª\nCorpo da cláusula.") == 0


# ---------------------------------------------------------- divergências

def test_pdfplumber_ve_e_o_texto_nao():
    avisos = divergencias(n_pdfplumber=3, n_texto=0)
    assert len(avisos) == 1
    assert "pdfplumber deteta 3" in avisos[0]
    assert "perda" in avisos[0]


def test_docling_ve_e_o_texto_nao():
    avisos = divergencias(n_pdfplumber=0, n_texto=0, n_docling=2)
    assert any("docling deteta 2" in a for a in avisos)


def test_sem_divergencia_quando_coincidem():
    assert divergencias(2, 2) == []
    assert divergencias(0, 0) == []
    assert divergencias(2, 3) == []  # contagens não precisam de ser iguais


def test_docling_nao_ve_o_que_o_pdfplumber_ve():
    avisos = divergencias(n_pdfplumber=1, n_texto=1, n_docling=0)
    assert any("sem grelha" in a for a in avisos)


# ------------------------------------------- anexos sem tabela (canário)

def _doc_com_anexo(rotulo: str, corpo: str,
                   tabela_fora: str = "") -> tuple[dict, str]:
    """Documento mínimo com um anexo, para o canário da sanidade.

    `tabela_fora` acrescenta linhas DEPOIS do anexo — o caso em que a
    tabela existe no documento mas cai fora do corpo do nó.
    """
    texto, nos = [], []

    def _add(tipo: str, rot: str, linhas_do_no: list[str]):
        start = sum(len(l) + 1 for l in texto)
        texto.extend(linhas_do_no)
        nos.append({"id": f"{tipo}{len(nos)}", "tipo": tipo, "rotulo": rot,
                    "char_start": start,
                    "char_end": start + sum(len(l) + 1 for l in linhas_do_no),
                    "pai": None, "origem": "novo", "folha": True})

    _add("clausula", "Cláusula 1.ª - Âmbito",
         ["Cláusula 1.ª - Âmbito", "1- A convenção aplica-se à empresa."])
    _add("anexo", rotulo, [rotulo] + corpo.split("\n"))
    if tabela_fora:
        texto.extend(tabela_fora.split("\n"))
    doc = {"versao_schema": "0.1", "doc_id": "teste", "tipo": "CCT",
           "subtipo": "desconhecido", "nos": nos}
    return doc, "\n".join(texto)


def test_anexo_de_remuneracao_sem_tabela_da_aviso():
    doc, texto = _doc_com_anexo(
        "Anexo I - Mapa de remunerações",
        "Texto corrido sem tabela.")
    avisos = tabelas_esperadas(doc, texto)
    assert len(avisos) == 1
    assert "Mapa de remunerações" in avisos[0]
    assert "sem nenhuma tabela" in avisos[0]


def test_anexo_com_tabela_fora_do_no_diz_fora_do_no():
    """A tabela existe no documento mas cai fora do corpo do anexo.

    É o caso real do estruturar com o docling: o anexo fecha no
    cabeçalho e as linhas de grelha ficam órfãs a seguir. A mensagem
    tem de distingui-lo da perda real.
    """
    doc, texto = _doc_com_anexo(
        "Anexo I - Mapa de remunerações",
        "Sem tabela no corpo do nó.",
        tabela_fora="Nível | Escalão\nI | 1 000,00")
    avisos = tabelas_esperadas(doc, texto)
    assert len(avisos) == 1
    assert "fora do corpo do nó" in avisos[0]
    assert "perdida" not in avisos[0]


def test_anexo_de_remuneracao_com_tabela_nao_da_aviso():
    doc, texto = _doc_com_anexo(
        "Anexo I - Mapa de remunerações",
        "Nível | Escalão 1\nI | 1 234,56")
    assert tabelas_esperadas(doc, texto) == []


def test_anexo_sem_termos_de_tabela_nao_da_aviso():
    doc, texto = _doc_com_anexo(
        "Anexo II - Regulamento interno",
        "Parágrafo primeiro.")
    assert tabelas_esperadas(doc, texto) == []


def _estruturado(corpo_anexo: str, clausula: str = "Aplica-se à empresa."):
    from crl_markdown.legacy.extractor import MARCA_TABELA_FIM, MARCA_TABELA_INI, estruturar
    tabela = f"{MARCA_TABELA_INI}\nNível | Valor\nA | 1 355,48\nB | 1 200,00\n{MARCA_TABELA_FIM}"
    return estruturar(
        f"Cláusula 1.ª - Âmbito\n{clausula.format(tabela=tabela)}\n"
        f"ANEXO III - Tabela de remunerações\n{corpo_anexo.format(tabela=tabela)}\n",
        "teste")


def test_tabela_no_corpo_filho_do_anexo_nao_esta_fora_do_no():
    """Issue #83 (BTE 31/2026): o estruturar fecha o anexo no cabeçalho e
    guarda o corpo num nó filho. A tabela está nesse filho, no sítio certo;
    a auditoria só olhava para o cabeçalho e dizia «fora do nó»."""
    doc, texto = _estruturado("Os valores mensais são:\n{tabela}")
    anexo = next(n for n in doc["nos"] if n["tipo"] == "anexo")
    assert any(n.get("pai") == anexo["id"] for n in doc["nos"]), \
        "o teste pressupõe o corpo num nó filho, como no estruturar real"
    assert tabelas_esperadas(doc, texto) == []


def test_tabela_que_nao_pertence_ao_anexo_continua_a_dar_aviso():
    """O verdadeiro positivo: a grelha existe, mas fora da árvore do anexo
    (aqui, na cláusula do articulado, antes dele)."""
    doc, texto = _estruturado(
        "Texto do anexo sem grelha.",
        clausula="Os valores constam da grelha:\n{tabela}")
    [aviso] = tabelas_esperadas(doc, texto)
    assert "fora do corpo do nó" in aviso


# -------------------------------------------- tabelas rodadas (ISSUE-0020)

def test_deteta_tabela_muito_mais_alta_que_larga():
    # o caso real do CARRISTUR: bbox 315×672 pt
    aviso = _aviso_tabela_rodada(2, (120.7, 99.2, 435.5, 771.0))
    assert aviso is not None
    assert "p2" in aviso and "docling" in aviso


def test_nao_marca_tabela_com_proporcao_normal():
    # uma tabela salarial normal é mais larga do que alta
    aviso = _aviso_tabela_rodada(1, (80.0, 100.0, 500.0, 250.0))
    assert aviso is None


def test_tabela_quadrada_nao_e_marcada():
    # o limiar é 2×, não qualquer altura > largura
    aviso = _aviso_tabela_rodada(1, (80.0, 100.0, 280.0, 280.0))
    assert aviso is None


# --------------------------------------- integração: sanidade chama canário

def test_sanidade_inclui_o_canario_de_tabelas():
    from crl_markdown.legacy.sanidade import verificar
    doc, texto = _doc_com_anexo(
        "Anexo I - Mapa de remunerações",
        "Sem tabela aqui.")
    avisos = verificar(doc, texto)
    assert any("Mapa de remunerações" in a and "tabela" in a for a in avisos)


# ------------------- integração: a auditoria nunca custa o documento (PR #67)



def test_anexo_de_carreiras_em_texto_nao_da_aviso():
    """Corrida de 2025: 40 avisos «fora do nó» eram anexos de texto
    (regulamentos de carreiras, regras de progressão), com tabelas noutro
    sítio do documento."""
    doc, texto = _doc_com_anexo(
        "ANEXO VII - Regulamento de Carreiras Profissionais do AE",
        "Artigo 1.º - Objeto\nO presente regulamento define as carreiras.\n"
        "Artigo 2.º - Progressão\nA progressão depende da avaliação.",
        tabela_fora="Nível | Escalão\nI | 1 000,00")
    assert tabelas_esperadas(doc, texto) == []


def test_anexo_com_os_valores_em_texto_nao_da_aviso():
    """A tabela lida como texto continua a ter os valores: não se perdeu."""
    doc, texto = _doc_com_anexo(
        "ANEXO I - Tabela salarial",
        "Nível I 1 087,90\nNível II 1 154,20\nNível III 1 216,00",
        tabela_fora="Outra | Tabela\nx | 1,00")
    assert tabelas_esperadas(doc, texto) == []


def test_tabela_salarial_sem_valores_continua_a_dar_aviso():
    doc, texto = _doc_com_anexo(
        "ANEXO I - Tabela salarial",
        "Os valores produzem efeitos a 1 de janeiro.\nNota 1.\nNota 2.",
        tabela_fora="Nível | Escalão\nI | 1 000,00")
    [aviso] = tabelas_esperadas(doc, texto)
    assert "fora do corpo do nó" in aviso


def test_tabela_numa_imagem_diz_a_pagina(tmp_path):
    """Corrida de 2025: as tabelas salariais do INCM, do Portway e do
    SUPERBOOK eram imagens. O aviso diz onde está a imagem, em vez de sugerir
    uma perda na extração; o logótipo do BTE, pequeno, não conta."""
    from crl_markdown.legacy.auditoria import paginas_com_imagem
    from tests.pdf_sintetico import escrever_pdf
    pdf = escrever_pdf(tmp_path / "x.pdf", [
        [(72, 780, "Texto."), ("imagem", 280, 790, 30, 30)],
        [(72, 780, "ANEXO III"), ("imagem", 80, 300, 430, 240)]])
    assert paginas_com_imagem(pdf) == [2]
    doc, texto = estruturar("ANEXO III - Tabela salarial\n1- Tabela salarial\n", "x")
    [aviso] = tabelas_esperadas(doc, texto, paginas_imagem=[2])
    assert "em imagem (p2)" in aviso and "perdida" not in aviso


def test_enquadramento_sem_grelha_lido_como_texto_nao_da_aviso():
    """CNIS e ACIP de 2025: as categorias de cada nível, numa tabela sem
    grelha, saem como texto («Nível I Director de serviços; …»). A tabela está
    lá; não está fora do nó nem perdida."""
    doc, texto = _doc_com_anexo(
        "ANEXO IV - Enquadramento das profissões em níveis de remuneração",
        "Nível I Director de serviços;\nSecretário-geral.\n"
        "Nível II Chefe de divisão;\nPsicólogo principal.\nNível III Técnico.")
    assert tabelas_esperadas(doc, texto + "\nx | y") == []


def test_tabela_salarial_so_com_rotulos_de_nivel_continua_a_dar_aviso():
    """Revisão do PR #92: três rótulos «Nível I/II/III» num anexo salarial sem
    nenhum valor não provam a tabela; nem num enquadramento sem categorias."""
    for rotulo, corpo in (
            ("ANEXO III - Tabela salarial", "Nível I\nNível II\nNível III"),
            ("ANEXO IV - Enquadramento em níveis de remuneração", "Nível I\nNível II\nNível III"),
            ("ANEXO IV - Enquadramento em níveis de remuneração",
             "Nível I Director.\nNível II\nNível III\nNível IV\nNível V Técnico.")):
        doc, texto = _doc_com_anexo(rotulo, corpo)
        assert len(tabelas_esperadas(doc, texto + "\nx | y")) == 1, rotulo


def test_enquadramento_de_alteracao_com_niveis_omitidos_nao_da_aviso():
    """AEBRAGA e AHRESP de 2025: os níveis que não mudam vêm com «(...)», e o
    rótulo pode dizer «Categorias profissionais e níveis» em vez de
    «Enquadramento». Chega que a maioria dos níveis traga categorias."""
    corpo = ("Nível V (...)\nNível VI (...)\nNível VII (...)\nNível VIII (...)\n"
             "Nível IX Caixeiro ajudante;\nNível X Operador;\nNível XI Cozinheiro.")
    for rotulo in ("ANEXO II - Enquadramento das profissões por níveis salariais",
                   "ANEXO II - Categorias profissionais e níveis de remuneração"):
        doc, texto = _doc_com_anexo(rotulo, corpo)
        assert tabelas_esperadas(doc, texto + "\nx | y") == [], rotulo
