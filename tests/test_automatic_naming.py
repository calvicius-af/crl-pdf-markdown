"""Regras de organização: índice real, evidência e casos contraditórios."""

import csv
from collections import Counter
from pathlib import Path

import pytest

from crl_markdown import nomeacao
from crl_markdown.naming import execute_records
from crl_markdown.recolha import Registo, ler_indice, sha256_ficheiro
from crl_markdown.validation import _load
from crl_markdown.workspace import initialize

ROOT = Path(__file__).resolve().parents[1]


def test_supplied_index_organizes_all_documents_without_confirmation(tmp_path):
    entries = ler_indice(ROOT / "docs/BTE_2026_01_10_CRL_b.xlsx")
    assert len(entries) == 411
    source = tmp_path / "original.pdf"
    source.write_bytes(b"%PDF-1.4\nsynthetic copy fixture, no extraction\n")
    for entry in entries:
        entry["descarga"] = {"estado": "descarregado", "caminho": str(source),
                             "sha256": sha256_ficheiro(source)}
    registry = Registo(tmp_path / "registo.jsonl", {e["chave"]: e for e in entries})
    workspace = initialize(tmp_path / "RNC")
    table = nomeacao.tabela_de_siglas(equipa=workspace / "0_gestao/vocabularios/siglas.csv")
    results = execute_records(registry, workspace, table, apply=True)
    assert Counter(r["estado"] for r in results) == {"nomeado": 411}
    files = list((workspace / "1_fontes/irct").rglob("*.pdf"))
    assert len(files) == 411
    assert all(sha256_ficheiro(p) == sha256_ficheiro(source) for p in files)
    assert all(len(p.stem) <= 63 for p in files)
    assert len(list((workspace / "1_fontes/irct/convencoes/APU").glob("*.pdf"))) == 55
    assert len(list((workspace / "1_fontes/irct/cessacoes_vigencia").glob("*.pdf"))) == 2
    assert len(list((workspace / "1_fontes/irct/portarias_extensao").glob("*.pdf"))) == 110
    assert len(list((workspace / "1_fontes/irct/acordos_adesao").glob("*.pdf"))) == 9
    assert len(list((workspace / "1_fontes/irct/acordaos").glob("*.pdf"))) == 1
    for entry in registry.entradas.values():
        if "RECT" in entry["tipo"]:
            assert entry["outorgantes_origem"].startswith("convencao_retificada:")
            assert entry["outorgantes"]
    with (workspace / "0_gestao/catalogo/catalogo_irct_2026.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    portaria = next(r for r in rows if r["chave"] == "2026/1/00050006")
    assert portaria["portaria_dr"] == "Portaria n.º 457/2025/1"
    assert portaria["data_publicacao_dr"] == "2025-12-22"
    assert "_0457-2025-1_" in portaria["nome_canonico"]
    names_before = {e["chave"]: e.get("nomeacao", {}).get("nome") for e in entries}
    repeated = execute_records(registry, workspace, table, apply=True)
    assert Counter(r["estado"] for r in repeated) == {"nomeado": 411}
    assert len(list((workspace / "1_fontes/irct").rglob("*.pdf"))) == 411
    assert names_before == {e["chave"]: e.get("nomeacao", {}).get("nome") for e in entries}


def test_acep_title_overrides_generic_act_and_uses_native_reference():
    entry = {"ano": 2026, "num_bte": 11, "id_dgert": "10/2026", "tipo": "ACT",
             "titulo": "Acordo coletivo de trabalho n.º 12/2026 - Acordo coletivo de empregador público "
                       "entre a Freguesia Alfa e o Sindicato Beta", "outorgantes": "Freguesia Alfa; Sindicato Beta"}
    name, warnings = nomeacao.nome_documento(entry, tabela={nomeacao.chave_entidade("Freguesia Alfa"): "FA",
                                                          nomeacao.chave_entidade("Sindicato Beta"): "SB"})
    assert "_APU_010_ACT_ACEP12-2026_" in name
    assert not nomeacao.avisos_bloqueantes(warnings)
    assert not entry.get("cod_irct")  # nunca inventar um código DGERT


def test_conflicting_codes_cannot_be_automated():
    base = {"chave": "base", "ano": 2026, "id_dgert": "12/2026", "tipo": "CCT", "cod_irct": "111"}
    extension = {"chave": "pe", "ano": 2026, "num_bte": 2, "id_dgert": "13/2026", "tipo": "PE",
                 "cod_irct": "222", "altera": "CCT.20260101.12/2026"}
    nomeacao.resolver_convencoes_base([base, extension])
    with pytest.raises(nomeacao.NomeRNCInvalido, match="difere"):
        nomeacao.nome_documento(extension)


def test_manual_refusal_remains_blocking_even_with_automatic_label_support(tmp_path):
    vocabulary = tmp_path / "siglas.csv"
    vocabulary.write_text("nome;sigla;estado;origem_sigla;responsavel\n"
                          "Empresa Alfa - XYZ;XYZ;por_confirmar;equipa;Ana\n"
                          "Empresa Beta;Beta;por_confirmar;indice;\n")
    table = nomeacao.carregar_siglas(vocabulary)
    assert nomeacao.avisos_bloqueantes([nomeacao.sigla("Empresa Alfa - XYZ", table)[1]])
    label, warning = nomeacao.sigla("Empresa Beta", table)
    assert label == "EmpresaBeta"
    assert not nomeacao.avisos_bloqueantes([warning])
    assert "não é uma sigla oficial" in warning


def test_generated_proposal_cannot_override_human_refusal_in_same_file(tmp_path):
    vocabulary = tmp_path / "siglas.csv"
    vocabulary.write_text("nome;sigla;estado;origem_sigla;responsavel\n"
                          "Empresa Alfa - XYZ;XYZ;por_confirmar;equipa;Ana\n"
                          "Empresa Alfa - XYZ;Alfa;por_confirmar;indice;\n")
    table = nomeacao.carregar_siglas(vocabulary)
    assert nomeacao.avisos_bloqueantes([nomeacao.sigla("Empresa Alfa - XYZ", table)[1]])


def test_federation_of_employers_is_not_treated_as_a_trade_union():
    assert not nomeacao.e_sindical("FENAME - Federação Nacional do Metal")
    assert nomeacao.e_sindical("FNE - Federação Nacional da Educação")


def test_contradictory_acronyms_for_same_full_name_remain_pending(tmp_path):
    vocabulary = tmp_path / "siglas.csv"
    vocabulary.write_text("nome;sigla;estado;origem_sigla\n"
                          "Sindicato Alfa;ALF;documentada;registo\n"
                          "Sindicato Alfa;OUTRA;documentada;registo\n")
    table = nomeacao.carregar_siglas(vocabulary)
    assert nomeacao.avisos_bloqueantes([nomeacao.sigla("Sindicato Alfa", table)[1]])


def test_missing_conversion_explains_which_gui_step_to_use(tmp_path):
    with pytest.raises(ValueError, match="Construir Markdown"):
        _load(tmp_path)
