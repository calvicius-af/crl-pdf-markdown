"""Testes da nomeação no esquema do RNC (ADR-0022), portada do crl-app-cct.

Correm offline, sobre um índice de ensaio com o cabeçalho real do BTE: duas
convenções, uma portaria de extensão, dois acordos de adesão (um com o tipo por
extenso, «ADESÃO», como no índice de 2026 dos BTE 1 a 10) e um acórdão.
"""

from pathlib import Path

import pytest

from crl_markdown import nomeacao
from crl_markdown.nomeacao import (
    MAX_NOME,
    NomeRNCInvalido,
    carregar_siglas,
    nome_documento,
    nomear,
    resolver_convencoes_base,
    sigla,
    tabela_de_siglas,
)
from crl_markdown.recolha import Registo, ler_indice, recolher
from tests.test_recolha import CABECALHO, URL, AbridorFalso

ACRAL = "Associação do Comércio e Serviços da Região do Algarve - ACRAL"
CESP = "CESP - Sindicato dos Trabalhadores do Comércio, Escritórios e Serviços de Portugal"

# (id, título, tipo, código, outorgantes, cadeia de alterações, ficheiro)
LINHAS = [
    ("377/2026", f"Contrato coletivo entre a {ACRAL} e o CESP", "CCT", "27251",
     f"{ACRAL}; {CESP}; STRUP - Sindicato dos Trabalhadores de Transportes", "",
     "00260057.pdf"),
    ("382/2026", "Acordo de empresa entre a Empresa Metropolitana de Estacionamento da "
     "Maia, EM e o SINTAP", "AE", "47252",
     "Empresa Metropolitana de Estacionamento da Maia, EM; Sindicato dos Trabalhadores "
     "da Administração Pública e de Entidades com Fins Públicos - SINTAP", "",
     "00880122.pdf"),
    ("401/2026", "Portaria n.º 452/2025 - Portaria que estende o contrato coletivo entre "
     "a ACRAL e o CESP.", "PE", "27251", "", "CCT.20260822.377/2026", "00010004.pdf"),
    ("402/2026", "Acordo de adesão entre a Algarve Retalho, L.da e o CESP ao contrato "
     "coletivo entre a ACRAL e o CESP.", "AA", "27251",
     f"Algarve Retalho, L.da - ALGRET; {CESP}", "CCT.20260822.377/2026", "00050006.pdf"),
    ("405/2026", "Acordo de adesão entre a Sul Retalho, L.da e o CESP ao contrato "
     "coletivo entre a ACRAL e o CESP.", "ADESÃO", "27251",
     f"Sul Retalho, L.da - SULRET; {CESP}", "CCT.20260822.377/2026", "00090010.pdf"),
    ("404/2026", "Acórdão do Supremo Tribunal de Justiça sobre a cláusula 12.ª do contrato "
     "coletivo entre a ACRAL e o CESP.", "ACORDÃO", "27251",
     f"{ACRAL}; {CESP}", "CCT.20260822.377/2026", "00110012.pdf"),
]  # fmt: skip


def escrever_indice(pasta: Path, linhas=LINHAS) -> Path:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "31"
    ws.append(CABECALHO)
    for id_dgert, titulo, tipo, cod, outorgantes, altera, ficheiro in linhas:
        linha = [None] * len(CABECALHO)
        linha[0], linha[1], linha[2], linha[3] = 2026, id_dgert, titulo, tipo
        linha[5], linha[6] = 93, 31
        linha[11], linha[14], linha[18] = cod, altera, outorgantes
        linha[20], linha[21] = ficheiro, f"{URL}/{ficheiro}"
        ws.append(linha)
    caminho = pasta / "BTE31_2026.xlsx"
    wb.save(caminho)
    return caminho


@pytest.fixture()
def itens(tmp_path):
    itens = ler_indice(escrever_indice(tmp_path))
    resolver_convencoes_base(itens)
    return {i["id_dgert"]: i for i in itens}


TABELA = {
    nomeacao.chave_entidade(ACRAL): "ACRAL",
    nomeacao.chave_entidade(CESP): "CESP",
}


def test_nomes_das_familias(itens):
    nomes = {k: nome_documento(i, 1, TABELA)[0] for k, i in itens.items()}
    assert nomes["377/2026"] == "2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+1"
    assert nomes["382/2026"].startswith("2026_BTE_31_SPE_382_AE_47252_")
    assert nomes["401/2026"] == "2026_BTE_31_PE_401_0452-2025_27251_ACRAL-CESP"
    assert nomes["402/2026"] == "2026_BTE_31_AA_402_27251_ALGRET-CESP"
    assert all(len(n) <= MAX_NOME for n in nomes.values())


def test_adesao_por_extenso_tem_o_mesmo_quarto_campo(itens):
    # O índice de 2026 escreve «ADESÃO»; o nome usa o código AA, como os outros.
    assert itens["405/2026"]["familia"] == "adesao"
    nome, _ = nome_documento(itens["405/2026"], 1, TABELA)
    assert nome == "2026_BTE_31_AA_405_27251_SULRET-CESP"


def test_acordao_tem_familia_e_quarto_campo_proprios(itens):
    # JUR e não AC: AC confundia-se com ACT e com acordo (decisão da equipa).
    assert itens["404/2026"]["familia"] == "acordao"
    nome, _ = nome_documento(itens["404/2026"], 1, TABELA)
    assert nome == "2026_BTE_31_JUR_404_27251_ACRAL-CESP"


@pytest.mark.parametrize("id_dgert", ["402/2026", "404/2026"])
def test_sem_convencao_de_base_nao_ha_nome(itens, id_dgert):
    item = dict(itens[id_dgert], altera="", cod_irct_base="", cod_irct_base_origem="")
    resolver_convencoes_base([item])
    with pytest.raises(NomeRNCInvalido, match="convenção de base"):
        nome_documento(item, 1, TABELA)


def test_portaria_sem_numero_nao_tem_nome(itens):
    item = dict(itens["401/2026"], titulo="Portaria que estende o contrato coletivo")
    with pytest.raises(NomeRNCInvalido, match="portaria"):
        nome_documento(item, 1, TABELA)


def test_sigla_derivada_pede_confirmacao():
    valor, aviso = sigla("Águas do Norte Interior, S.A.")
    assert valor == "AguasNorteInterior" and "confirmar" in aviso
    assert sigla("Associação das Empresas de Vinho do Porto (AEVP)") == ("AEVP", None)


def test_siglas_da_dgert_sao_carregadas_e_as_da_equipa_ganham(tmp_path):
    dgert = carregar_siglas(nomeacao.SIGLAS_DGERT)
    # as siglas inventadas por recurso (origem_sigla=recurso) não entram
    assert len(dgert) > 1000
    equipa = tmp_path / "siglas.csv"
    chave, sigla_dgert = next(iter(dgert.items()))
    equipa.write_text(f"{chave};OUTRA\n", encoding="utf-8")
    tabela = tabela_de_siglas(equipa=equipa)
    assert tabela[chave] == "OUTRA" != sigla_dgert


def _recolhido(tmp_path, linhas=LINHAS):
    indice = escrever_indice(tmp_path, linhas)
    registo = Registo(tmp_path / "registo.jsonl")
    recolher([indice], tmp_path / "interim", registo, rede=True, abridor=AbridorFalso(), pausa=0)
    return registo


def test_nomear_arruma_por_familia_e_ambito(tmp_path):
    registo = _recolhido(tmp_path)
    destino = tmp_path / "bte"
    resumo = nomear(registo, destino, aplicar=True, tabela=TABELA, aceitar_heuristicas=True)
    assert resumo["problemas"] == []
    escritos = sorted(p.relative_to(destino).as_posix() for p in destino.rglob("*.pdf"))
    assert escritos == [
        "bte_2026/acordaos/2026_BTE_31_JUR_404_27251_ACRAL-CESP.pdf",
        "bte_2026/acordos_adesao/2026_BTE_31_AA_402_27251_ALGRET-CESP.pdf",
        "bte_2026/acordos_adesao/2026_BTE_31_AA_405_27251_SULRET-CESP.pdf",
        "bte_2026/convencoes/PRI/2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+1.pdf",
        "bte_2026/convencoes/SPE/" + next(destino.rglob("*_382_*")).name,
        "bte_2026/portarias_extensao/2026_BTE_31_PE_401_0452-2025_27251_ACRAL-CESP.pdf",
    ]
    # repetir não escreve nada de novo nem muda nomes
    resumo = nomear(registo, destino, aplicar=True, tabela=TABELA, aceitar_heuristicas=True)
    assert resumo["por_estado"] == {"ja_existente": 6}


def test_sem_confirmacao_so_escreve_os_nomes_seguros(tmp_path):
    registo = _recolhido(tmp_path)
    destino = tmp_path / "bte"
    resumo = nomear(registo, destino, aplicar=True, tabela=TABELA)
    # A convenção tem siglas confirmadas e âmbito por omissão: é escrita. As
    # outras dependem da cadeia de alterações ou de regras e esperam confirmação.
    assert [p.name for p in destino.rglob("*.pdf")] == [
        "2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+1.pdf"
    ]
    assert resumo["por_estado"] == {"nomeado": 1, "por_confirmar": 5}


def test_nome_atribuido_nao_muda(tmp_path):
    registo = _recolhido(tmp_path, LINHAS[:1])
    destino = tmp_path / "bte"
    nomear(registo, destino, aplicar=True, tabela=TABELA)
    outra = {nomeacao.chave_entidade(ACRAL): "OUTRA", nomeacao.chave_entidade(CESP): "CESP"}
    resumo = nomear(registo, destino, aplicar=True, tabela=outra)
    assert resumo["por_estado"] == {"conflito": 1}
    assert len(list(destino.rglob("*.pdf"))) == 1


def test_collect_nomeia_automaticamente(tmp_path, monkeypatch, capsys):
    from crl_markdown import recolha
    from crl_markdown.cli import main

    monkeypatch.setattr(recolha, "abridor_urllib", AbridorFalso())
    monkeypatch.chdir(tmp_path)
    indice = escrever_indice(tmp_path, LINHAS[:1])
    argumentos = ["collect", "--indices", str(indice), "--pausa", "0"]
    # Sem rede não há PDF, logo não há nada para nomear.
    assert main(argumentos) == 0
    assert "nenhum PDF recolhido para nomear" in capsys.readouterr().out
    assert main(argumentos + ["--confirmar-rede"]) == 0
    saida = capsys.readouterr().out
    assert "nomeado: 1" in saida
    nomeados = list((tmp_path / "data" / "raw" / "bte").rglob("*.pdf"))
    assert [p.name for p in nomeados] == ["2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+1.pdf"]
    # Registo persistido com o nome, e válido para a próxima leitura.
    registo = Registo.carregar(tmp_path / "data" / "registo" / "registo_bte.jsonl")
    entrada = next(iter(registo.entradas.values()))
    assert entrada["nomeacao"]["estado"] == "nomeado"
    assert main(argumentos + ["--sem-nomear"]) == 0
    assert "Nomeação" not in capsys.readouterr().out
