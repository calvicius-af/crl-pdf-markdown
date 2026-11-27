"""A lista_siglas_global é a fonte única; o siglas.csv é derivado dela."""

import csv
import importlib.util
import io
from pathlib import Path

import pytest

from crl_markdown import nomeacao

RAIZ = Path(__file__).resolve().parents[1]
CABECALHO = ("sigla;nome;fonte;categoria;estado;codigo_origem;sigla_unica;id_entidade;lado;"
             "sigla_mae;rotulos_crl;confianca_crl;revisao;data_atualizacao;ambito;"
             "ambito_subsetor;ambito_fundamento;ambito_confianca")


def _modulo():
    caminho = RAIZ / "scripts/gerar_siglas_da_lista_global.py"
    spec = importlib.util.spec_from_file_location("gerar_siglas_testes", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _lista(*linhas):
    return list(csv.DictReader(io.StringIO("\n".join((CABECALHO,) + linhas)), delimiter=";"))


def _linha(sigla, nome, *, ident, fonte="Organização (DGERT)", codigo="5.1", lado="empregadores",
           rotulos="", revisao="", estado="Activa"):
    return (f"{sigla};{nome};{fonte};X;{estado};{codigo};VERDADEIRO;{ident};{lado};;{rotulos};;"
            f"{revisao};2026-11-25;;;;")


def test_entidade_e_rotulos_dao_linhas_com_a_mesma_sigla():
    linhas, rel = _modulo().converter(_lista(
        _linha("AHP", "ASSOCIAÇÃO DA HOTELARIA DE PORTUGAL", ident="DGERT-5.1",
               rotulos="AHP - Ass. Hotel. Port. | AHP"),
    ))
    assert [(linha["nome"], linha["sigla"], linha["origem_sigla"]) for linha in linhas] == [
        ("ASSOCIAÇÃO DA HOTELARIA DE PORTUGAL", "AHP", "lista_global"),
        ("AHP - Ass. Hotel. Port.", "AHP", "lista_global_rotulo"),
        ("AHP", "AHP", "lista_global_rotulo"),
    ]
    assert linhas[0]["codigo_dgert"] == "5.1" and linhas[0]["estado"] == "documentada"
    assert rel["entidades"] == 1 and rel["rotulos"] == 2


def test_codigo_dgert_so_para_entidades_da_dgert():
    linhas, _ = _modulo().converter(_lista(
        _linha("CM-BEJA", "Município de Beja", ident="INE-1",
               fonte="Administração pública (INE S.13 2025)", codigo="S.1313", lado="administração pública"),
    ))
    assert linhas[0]["codigo_dgert"] == ""


def test_linha_com_revisao_fica_por_confirmar_e_a_nomeacao_nao_a_usa(tmp_path):
    modulo = _modulo()
    linhas, _ = modulo.converter(_lista(
        _linha("AITomate", "ASSOCIAÇÃO DOS INDUSTRIAIS DE TOMATE", ident="DGERT-5.2",
               revisao="sigla fora do padrão"),
    ))
    assert linhas[0]["estado"] == "por_confirmar"
    destino = tmp_path / "siglas.csv"
    modulo.escrever(linhas, destino)
    tabela = nomeacao.carregar_siglas(destino)
    assert nomeacao.chave_entidade("ASSOCIAÇÃO DOS INDUSTRIAIS DE TOMATE") in tabela.nomes_pendentes


def test_siglas_que_so_diferem_no_hifen_ficam_ambiguas():
    linhas, rel = _modulo().converter(_lista(
        _linha("JF-AGUALONGA", "Freguesia de Agualonga", ident="INE-1"),
        _linha("JF-AGUA-LONGA", "Freguesia de Água Longa", ident="INE-2"),
    ))
    assert {linha["estado"] for linha in linhas} == {"ambigua"}
    assert rel["colisoes_de_sigla"] == {"jfagualonga": ["INE-1", "INE-2"]}


INE = "Administração pública (INE S.13 2025)"
CRL = "Empregador (CRL 2025)"


def test_prioridade_dgert_ine_crl_no_mesmo_nome():
    linhas, rel = _modulo().converter(_lista(
        _linha("ML", "Metropolitano de Lisboa, E.P.E.", ident="INE-1", fonte=INE),
        _linha("METRO-LISBOA", "Metropolitano de Lisboa, EPE", ident="CRL-1", fonte=CRL),
        _linha("AE-BAIAO", "Associação Empresarial de Baião", ident="CRL-2", fonte=CRL),
        _linha("AEB", "ASSOCIAÇÃO EMPRESARIAL DE BAIÃO", ident="DGERT-5.357"),
    ))
    assert sorted(linha["sigla"] for linha in linhas) == ["AEB", "ML"]
    assert {(p["sigla"], p["fica_fonte"]) for p in rel["preteridas_por_prioridade"]} == {
        ("METRO-LISBOA", "INE"), ("AE-BAIAO", "DGERT")}
    assert rel["nomes_com_siglas_diferentes"] == {}


def test_freguesias_que_so_diferem_num_acento_coexistem(tmp_path):
    modulo = _modulo()
    linhas, rel = modulo.converter(_lista(
        _linha("JF-LOUSA", "Freguesia de Lousa", ident="INE-1", fonte=INE),
        _linha("JF-LOUSA-2", "Freguesia de Lousã", ident="INE-2", fonte=INE),
        _linha("JF-TABUA", "Freguesia de Tabua", ident="INE-3", fonte=INE),
        _linha("JF-TABUA-2", "Freguesia de Tábua", ident="INE-4", fonte=INE),
    ))
    assert {linha["estado"] for linha in linhas} == {"documentada"}
    assert len(rel["distinguidas_por_grafia"]) == 2
    destino = tmp_path / "siglas.csv"
    modulo.escrever(linhas, destino)
    tabela = nomeacao.carregar_siglas(destino)
    assert nomeacao.sigla("Freguesia de Lousa", tabela) == ("JFLOUSA", None)
    assert nomeacao.sigla("Freguesia de Lousã", tabela) == ("JFLOUSA2", None)
    assert nomeacao.sigla("FREGUESIA DE TÁBUA", tabela) == ("JFTABUA2", None)
    assert nomeacao.sigla("Freguesia de Tabua", tabela) == ("JFTABUA", None)
    # Outra grafia do mesmo nome não se resolve por aproximação.
    valor, aviso = nomeacao.sigla("Freguesia de Lóusa", tabela)
    assert aviso and "pendente" in aviso


def test_organizacoes_com_o_mesmo_nome_na_mesma_fonte_ficam_ambiguas(tmp_path):
    modulo = _modulo()
    linhas, rel = modulo.converter(_lista(
        _linha("FPP", "FEDERAÇAO PORTUGUESA DE PROFESSORES", ident="DGERT-2.59"),
        _linha("PROFESSORES", "FEDERAÇÃO PORTUGUESA DE PROFESSORES", ident="DGERT-2.49"),
    ))
    # Numa organização, a diferença de acento é erro de registo, não outra entidade.
    assert {linha["estado"] for linha in linhas} == {"ambigua"}
    assert rel["nomes_com_siglas_diferentes"] == {
        "federacaoportuguesadeprofessores": ["FPP", "PROFESSORES"]}
    destino = tmp_path / "siglas.csv"
    modulo.escrever(linhas, destino)
    tabela = nomeacao.carregar_siglas(destino)
    assert nomeacao.sigla("FEDERAÇÃO PORTUGUESA DE PROFESSORES", tabela)[1]


def test_entidade_desativada_fica_fora():
    linhas, rel = _modulo().converter(_lista(
        _linha("SGP", "Secretaria-Geral da Presidência", ident="INE-1", fonte=INE, estado="Desativada"),
        _linha("SG-PRESIDENC", "Secretaria Geral da Presidência", ident="INE-2", fonte=INE),
    ))
    assert [linha["sigla"] for linha in linhas] == ["SG-PRESIDENC"]
    assert rel["nomes_com_siglas_diferentes"] == {}
    assert [d["entidade"] for d in rel["desativadas"]] == ["INE-1"]


def test_no_mesmo_nome_a_entidade_ativa_prevalece_sobre_a_extinta():
    linhas, rel = _modulo().converter(_lista(
        _linha("FPP", "FEDERAÇÃO PORTUGUESA DE PROFESSORES", ident="DGERT-2.59"),
        _linha("PROFESSORES", "FEDERAÇÃO PORTUGUESA DE PROFESSORES", ident="DGERT-2.49", estado="Extinta"),
    ))
    assert [(linha["sigla"], linha["estado"]) for linha in linhas] == [("FPP", "documentada")]
    assert rel["desativadas"][0]["motivo"] == "extinta; fica FPP"


def test_freguesia_com_distrito_cabe_na_sigla(tmp_path):
    modulo = _modulo()
    linhas, _ = modulo.converter(_lista(
        _linha("JF-AGUALONGA-VIANA-DO-CASTELO", "Freguesia de Agualonga", ident="INE-1", fonte=INE),
        _linha("JF-AGUA-LONGA-PORTO", "Freguesia de Água Longa", ident="INE-2", fonte=INE),
    ))
    destino = tmp_path / "siglas.csv"
    modulo.escrever(linhas, destino)
    tabela = nomeacao.carregar_siglas(destino)
    assert nomeacao.sigla("Freguesia de Agualonga", tabela) == ("JFAGUALONGAVIANADOCASTELO", None)
    assert nomeacao.sigla("Freguesia de Água Longa", tabela) == ("JFAGUALONGAPORTO", None)


def test_freguesia_homonima_sem_concelho_fica_pendente_sem_bloquear_a_outra_grafia(tmp_path):
    modulo = _modulo()
    linhas, rel = modulo.converter(_lista(
        _linha("JF-MOSTEIRO", "Freguesia de Mosteiro", ident="INE-1", fonte=INE,
               revisao="três freguesias com este nome: indicar o concelho"),
        _linha("JF-MOSTEIRO-BRAGA", "Freguesia de Mosteiro - Vieira do Minho", ident="CAOP-031110",
               fonte="Administração pública (CAOP 2024.1)"),
        _linha("JF-MOSTEIRO-AVEIRO", "Freguesia de Mosteirô", ident="INE-2", fonte=INE),
    ))
    assert rel["nomes_com_siglas_diferentes"] == {}
    destino = tmp_path / "siglas.csv"
    modulo.escrever(linhas, destino)
    tabela = nomeacao.carregar_siglas(destino)
    assert nomeacao.sigla("Freguesia de Mosteirô", tabela) == ("JFMOSTEIROAVEIRO", None)
    assert nomeacao.sigla("Freguesia de Mosteiro - Vieira do Minho", tabela) == ("JFMOSTEIROBRAGA", None)
    assert "pendente" in nomeacao.sigla("Freguesia de Mosteiro", tabela)[1]


def test_coluna_em_falta_interrompe(tmp_path):
    caminho = tmp_path / "lista.csv"
    caminho.write_text("sigla;nome\nAHP;Associação\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Colunas em falta"):
        _modulo().ler_lista(caminho)


def test_nao_substitui_saida_existente(tmp_path):
    destino = tmp_path / "siglas.csv"
    destino.write_text("existente", encoding="utf-8")
    with pytest.raises(FileExistsError):
        _modulo().escrever([], destino)


@pytest.mark.parametrize("derivado", ["siglas.csv", "src/crl_markdown/vocabularios/siglas.csv"])
def test_siglas_csv_e_derivado_da_lista_global(derivado, tmp_path):
    """Quem editar o siglas.csv à mão perde a edição na geração seguinte: falha aqui."""
    modulo = _modulo()
    lista = RAIZ / "vocabularios/lista_siglas_global.csv"
    linhas, _ = modulo.converter(modulo.ler_lista(lista), lista.name)
    esperado = tmp_path / "esperado.csv"
    modulo.escrever(linhas, esperado)
    # Compara linhas: no Windows o checkout pode converter LF em CRLF.
    ler = lambda p: p.read_text(encoding="utf-8").splitlines()  # noqa: E731
    assert ler(RAIZ / derivado) == ler(esperado)
