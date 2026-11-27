"""Siglas resolvidas por regra, entidades novas e decisões da equipa (2026-11-27)."""

import csv
import importlib.util
from pathlib import Path

import pytest

from crl_markdown import nomeacao
from crl_markdown.recolha import ler_indice

RAIZ = Path(__file__).resolve().parents[1]


def _tabela(tmp_path, texto):
    caminho = tmp_path / "siglas.csv"
    caminho.write_text("nome;sigla;codigo_dgert;lado;estado;origem_sigla;fonte;responsavel;data\n" + texto,
                       encoding="utf-8")
    return nomeacao.carregar_siglas(caminho)


def _script():
    spec = importlib.util.spec_from_file_location("acrescentar_siglas", RAIZ / "scripts/acrescentar_siglas.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("nome, esperada", [
    ("Freguesia da Barrosa", "JFBARROSA"),
    ("Freguesia de Pontinha e Famões", "UFPONTINHA"),
    ("Águas do Norte, SA", "AGUASDONORTE"),
    ("Cooperativa da Beira Central, CRL (sede em Viseu)", "COOPBC"),
])
def test_equivalencia_de_nome_resolve_grafias_da_mesma_entidade(tmp_path, nome, esperada):
    tabela = _tabela(tmp_path, (
        "Freguesia de Barrosa;JF-BARROSA;;;documentada;lista_global;;;\n"
        "União das freguesias de Pontinha e Famões;UF-PONTINHA;;;documentada;lista_global;;;\n"
        "Águas do Norte;AGUAS-DO-NORTE;;;documentada;lista_global;;;\n"
        "Cooperativa da Beira Central;COOP-BC;;;documentada;lista_global;;;\n"))
    assert nomeacao.origem_sigla(nome, tabela) == (esperada, "equivalencia")


def test_equivalencia_nao_escolhe_entre_duas_entidades(tmp_path):
    tabela = _tabela(tmp_path, (
        "Freguesia de Lousa;JF-LOUSA-BRAGANCA;;;documentada;lista_global;;;\n"
        "Freguesia de Lousã;JF-LOUSA-COIMBRA;;;documentada;lista_global;;;\n"))
    # «da Lousa» não é nenhuma das duas grafias: fica com rótulo por regra.
    assert nomeacao.origem_sigla("Freguesia da Lousa", tabela)[1] == "regra"


def test_origens_da_sigla(tmp_path):
    tabela = _tabela(tmp_path, (
        "Sindicato Exemplo;SEX;;;documentada;lista_global;;;\n"
        "Associação Pendente;AP;;;por_confirmar;lista_global;;;\n"))
    assert nomeacao.origem_sigla("Sindicato Exemplo", tabela) == ("SEX", "lista")
    assert nomeacao.origem_sigla("ABC - Empresa de Exemplo, SA", tabela) == ("ABC", "literal")
    assert nomeacao.origem_sigla("Empresa Inexistente de Exemplo, SA", tabela)[1] == "regra"
    assert nomeacao.origem_sigla("Associação Pendente", tabela)[1] == "por_confirmar"


def test_indice_do_repositorio_resolve_pelo_menos_90_por_cento_por_regra():
    tabela = nomeacao.tabela_de_siglas(equipa=Path("nao-existe.csv"))
    origens = {}
    for entrada in ler_indice(RAIZ / "docs/BTE_2026_01_10_CRL_b.xlsx"):
        for nome, _valor, origem in nomeacao.origens_do_documento(entrada, tabela):
            origens[nome] = origem
    automaticas = sum(origem in nomeacao.ORIGENS_AUTOMATICAS for origem in origens.values())
    assert automaticas / len(origens) >= 0.9


def test_entidades_novas_e_decisoes_entram_na_lista_e_no_siglas_csv(tmp_path):
    novas = nomeacao.escrever_siglas_novas(
        {"Refinaria Exemplar, SA": {"sigla": "RefinariaExemplar", "origem": "regra", "documentos": ["D1"]},
         "Sindicato Exemplo": {"sigla": "SindicatoExemplo", "origem": "regra", "documentos": ["D2"]}},
        tmp_path / "siglas_novas.csv", data="2026-11-27")
    decisoes = nomeacao.escrever_siglas_pendentes(
        {"Associação Pendente": {"sigla": "AssociacaoPendente", "documentos": ["D3"]},
         "Associação Ignorada": {"sigla": "AI", "documentos": ["D4"]}},
        tmp_path / "siglas_pendentes.csv")
    texto = decisoes.read_text("utf-8-sig").replace("Associação Pendente;AssociacaoPendente;;",
                                                    "Associação Pendente;AP-NOVA;aprovar;")
    decisoes.write_text(texto, encoding="utf-8-sig")

    lista = tmp_path / "lista.csv"
    cabecalho = ";".join(nomeacao.COLUNAS_LISTA_GLOBAL)
    vazio = ";" * 4 + "2026-11-25;;;;"
    lista.write_text("\n".join((
        cabecalho,
        f"SEX;Sindicato Exemplo;Organização (DGERT);X;Activa;1.1;VERDADEIRO;DGERT-1.1;trabalhadores;;;;{vazio}",
        "AP;Associação Pendente;Organização (DGERT);X;Activa;5.1;VERDADEIRO;DGERT-5.1;empregadores;;;;"
        "sigla fora do padrão;2026-11-25;;;;",
        "APX;ASSOCIAÇÃO PENDENTE;Organização (DGERT);X;Activa;5.2;VERDADEIRO;DGERT-5.2;empregadores;;;;"
        ";2026-11-25;;;;",
    )) + "\n", encoding="utf-8")
    destino = tmp_path / "siglas.csv"
    script = _script()
    assert script.main(["--lista", str(lista), "--novas", str(novas), "--decisoes", str(decisoes),
                        "--siglas", str(destino)]) == 0

    linhas = {linha["id_entidade"]: linha for linha in csv.DictReader(lista.open(encoding="utf-8"), delimiter=";")}
    assert linhas["NOM-0001"]["nome"] == "Refinaria Exemplar, SA"
    assert linhas["NOM-0001"]["fonte"] == nomeacao.FONTE_REGRA
    assert "NOM-0002" not in linhas  # o Sindicato Exemplo já estava na lista
    assert (linhas["DGERT-5.1"]["sigla"], linhas["DGERT-5.1"]["revisao"]) == ("AP-NOVA", "")
    assert linhas["DGERT-5.2"]["estado"] == "Desativada"

    tabela = nomeacao.carregar_siglas(destino)
    assert nomeacao.sigla("Refinaria Exemplar, SA", tabela) == ("RefinariaExemplar", None)
    assert nomeacao.sigla("Associação Pendente", tabela) == ("APNOVA", None)
    assert destino.with_name("siglas.manifest.json").exists()
