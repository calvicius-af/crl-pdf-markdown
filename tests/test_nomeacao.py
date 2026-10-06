"""Contratos de segurança e repetição da fase recolha → nomeação → conversão."""

from pathlib import Path

import pytest

from crl_markdown.acquisition_app import AcquisitionPanel
from crl_markdown.cli import main
from crl_markdown.nomeacao import nome_documento, nomear
from crl_markdown.recolha import Registo, sha256_ficheiro

from .pdf_sintetico import escrever_pdf


@pytest.fixture
def collected(tmp_path):
    source = escrever_pdf(tmp_path / "original.pdf", [[(50, 780, "CONVENCAO DE TESTE")]])
    entry = {"chave": "2026:31:377", "ano": 2026, "num_bte": 31,
             "id_dgert": "377/2026", "tipo": "CCT", "familia": "convencao",
             "cod_irct": "27251", "titulo": "Contrato coletivo de teste",
             "outorgantes": "Associação A - ACRAL; CESP - Sindicato B",
             "descarga": {"estado": "descarregado", "caminho": str(source),
                          "sha256": sha256_ficheiro(source)}}
    reg = Registo(tmp_path / "registo.jsonl", {entry["chave"]: entry})
    reg.guardar()
    return reg, entry, tmp_path / "named"


def test_rnc_identity():
    name, _ = nome_documento({"ano": 2026, "num_bte": 31, "id_dgert": "377/2026",
                             "tipo": "CCT", "cod_irct": "27251",
                             "outorgantes": "Associação A - ACRAL; CESP - Sindicato B"}, 1)
    assert name == "2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP"


def test_preview_preserves_original_and_writes_no_copy(collected):
    reg, entry, dest = collected
    result = nomear(reg, dest)
    assert result["nomes"]
    assert not dest.exists()
    assert Path(entry["descarga"]["caminho"]).is_file()
    assert Registo.carregar(reg.caminho).entradas[entry["chave"]]["nomeacao"]["ordinal"] == 1


def test_apply_is_repeatable_and_preserves_hash(collected):
    reg, entry, dest = collected
    result = nomear(reg, dest, aplicar=True, confirmados={entry["chave"]})
    assert result["por_estado"] == {"nomeado": 1}
    target = Path(entry["nomeacao"]["caminho"])
    assert sha256_ficheiro(target) == entry["descarga"]["sha256"]
    assert Path(entry["descarga"]["caminho"]).exists()
    assert nomear(reg, dest, aplicar=True)["por_estado"] == {"ja_existente": 1}
    assert list(dest.rglob("*.pdf")) == [target]


def test_changed_source_is_blocked(collected):
    reg, entry, dest = collected
    Path(entry["descarga"]["caminho"]).write_bytes(b"changed")
    assert nomear(reg, dest, aplicar=True)["por_estado"] == {"sem_origem": 1}
    assert not dest.exists()


def test_collision_does_not_overwrite(collected):
    reg, entry, dest = collected
    nomear(reg, dest)
    target = Path(entry["nomeacao"]["caminho"])
    target.parent.mkdir(parents=True)
    target.write_bytes(b"unrelated document")
    assert nomear(reg, dest, aplicar=True)["por_estado"] == {"conflito": 1}
    assert target.read_bytes() == b"unrelated document"


def test_heuristics_wait_for_individual_approval(collected):
    reg, entry, dest = collected
    entry["outorgantes"] = "Empresa de Teste; Sindicato de Teste"
    assert nomear(reg, dest, aplicar=True)["por_estado"] == {"por_confirmar": 1}
    assert not dest.exists()
    assert nomear(reg, dest, aplicar=True, confirmados={entry["chave"]})["por_estado"] == {"nomeado": 1}


def test_gui_job_and_cli_share_register(collected):
    reg, entry, dest = collected
    values = (str(reg.caminho), str(dest), "", "")
    result, preview = AcquisitionPanel.naming_job(values)
    assert result["nomes"]
    result, applied = AcquisitionPanel.naming_job(values, {entry["chave"]})
    assert result["por_estado"] == {"nomeado": 1}
    assert main(["rename", "--registo", str(reg.caminho), "--destino", str(dest), "--aplicar"]) == 0
    assert applied.entradas[entry["chave"]]["nomeacao"]["doc_id"] == preview.entradas[entry["chave"]]["nomeacao"]["doc_id"]


def test_empty_register_reports_error(tmp_path):
    assert main(["rename", "--registo", str(tmp_path / "missing.jsonl")]) == 1


def test_invalid_structural_name_cannot_be_confirmed(collected):
    reg, entry, dest = collected
    entry["tipo"] = "CCT-" + "A" * 100
    result = nomear(reg, dest, aplicar=True, confirmados={entry["chave"]})
    assert result["por_estado"] == {"por_confirmar": 1}
    assert result["problemas"]
    assert not dest.exists()


def test_review_detects_changed_vocabulary(collected, tmp_path):
    reg, _, dest = collected
    csv = tmp_path / "siglas.csv"
    csv.write_text("nome;sigla\nEmpresa;ABC\n")
    values = (str(reg.caminho), str(dest), str(csv), "")
    before = AcquisitionPanel.review_fingerprint(values)
    csv.write_text("nome;sigla\nEmpresa;XYZ\n")
    assert AcquisitionPanel.review_fingerprint(values) != before
