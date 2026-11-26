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
           rotulos="", revisao=""):
    return (f"{sigla};{nome};{fonte};X;Activa;{codigo};VERDADEIRO;{ident};{lado};;{rotulos};;"
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


def test_nome_com_duas_siglas_e_relatado():
    _, rel = _modulo().converter(_lista(
        _linha("ML", "Metropolitano de Lisboa, E.P.E.", ident="INE-1"),
        _linha("METROLISBOA", "Metropolitano de Lisboa, EPE", ident="CRL-1"),
    ))
    assert rel["nomes_com_siglas_diferentes"] == {"metropolitanodelisboaepe": ["METROLISBOA", "ML"]}


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
