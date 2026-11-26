"""Avisos públicos são documentos; relações ausentes não são inventadas."""

import json
from collections import Counter
from pathlib import Path

import pytest

from crl_markdown import nomeacao, tipologias
from crl_markdown.recolha import Registo, ler_indice
from crl_markdown.workspace import document_source, initialize


def public_notice(title, **fields):
    return {"tipo": "AVISO", "familia": "aviso", "titulo": title, **fields}


def test_nine_notices_are_classified_by_content_and_original_type_preserved():
    entries = ler_indice(Path(__file__).resolve().parents[1] / "docs/BTE_2026_01_10_CRL_b.xlsx")
    notices = [e for e in entries if e["tipo"] == "AVISO"]
    assert len(notices) == 9
    assert Counter(e["tipo_documental"] for e in notices) == {
        "ACEP-ALT": 7, "ACCE-ALT": 1, "ACEP-DELI": 1}
    assert all(e["familia"] == "convencao" and e["ambito_documental"] == "APU" for e in notices)
    assert all(e["familia_origem"] == "aviso" and e["referencia_acordo_base"] for e in notices)
    assert sum(e["texto_consolidado"] for e in notices) == 3


@pytest.mark.parametrize("title", [
    "Aviso de projeto de portaria de extensão do contrato coletivo entre a Associação Alfa e o Sindicato Beta.",
    "Aviso de alteração do contrato coletivo entre a Empresa Alfa e o Sindicato Beta.",
    "Aviso de abertura de concurso do Município de Alfa.",
    "Aviso de alteração do horário de atendimento do Município Alfa.",
])
def test_ambiguous_or_private_notices_do_not_become_public_agreements(title):
    result = tipologias.classificar(public_notice(title))
    assert result["familia"] == "aviso"
    assert result["ambito_documental"] == ""


def test_cessation_links_exact_publication_and_preserves_external_references():
    base = {"chave": "2005/1/base", "tipo": "CCT", "familia": "convencao",
            "id_dgert": "9/2005", "cod_irct": "25859"}
    cessation = {"chave": "2026/27/aviso", "tipo": "AV-CES-VIG", "familia": "aviso",
                 "cod_irct": "25859", "altera": "CCT.20050111.9/2005; CCT-ALT. 15/02/2008.39/2008"}
    tipologias.enriquecer([base, cessation])
    assert cessation["familia"] == "cessacao"
    assert cessation["processo_irct"] == "DGERT:25859"
    local, external = cessation["relacoes_documentais"]
    assert local["alvo_chave"] == base["chave"] and local["estado"] == "ligado"
    assert external["id_publicacao"] == "39/2008" and external["estado"] == "fora_do_lote"
    assert "alvo_chave" not in external
    assert external["referencia"] == "CCT-ALT. 15/02/2008.39/2008"


def test_caducity_title_is_a_cessation_even_when_source_type_is_generic_notice():
    result = tipologias.classificar(public_notice("Aviso de caducidade do contrato coletivo entre Alfa e Beta"))
    assert result["familia"] == "cessacao" and result["tipo_documental"] == "CES-VIG"


def test_public_alteration_links_original_by_its_published_reference():
    base = {"chave": "base", "tipo": "ACEP", "familia": "convencao",
            "titulo": "Acordo Colectivo de Trabalho n.º 53/2016 entre o Município Alfa e o Sindicato Beta"}
    notice = public_notice("Aviso n.º 1/2026 - Alteração ao Acordo Coletivo de Trabalho n.º 53/2016 "
                           "entre o Município Alfa e o Sindicato Beta", chave="aviso")
    tipologias.enriquecer([base, notice])
    assert base["relacoes_documentais"] == []  # uma publicação original não aponta para si própria
    relation = next(r for r in notice["relacoes_documentais"] if r["relacao"] == "acordo_base")
    assert relation["estado"] == "ligado" and relation["alvo_chave"] == "base"
    assert notice["processo_irct"] == "APU:ACEP:53/2016"


def test_duplicate_reference_does_not_select_an_arbitrary_document():
    base = {"chave": "a", "tipo": "CCT", "familia": "convencao", "id_dgert": "9/2005"}
    notice = {"chave": "c", "tipo": "AV-CES-VIG", "altera": "CCT.20050111.9/2005"}
    tipologias.enriquecer([base, {**base, "chave": "b"}, notice])
    relation = notice["relacoes_documentais"][0]
    assert relation["estado"] == "ambiguo" and "alvo_chave" not in relation


def test_public_notice_links_a_previous_notice_by_published_number():
    previous = public_notice("Aviso n.º 5356/2018 - Alteração ao Acordo Coletivo de Trabalho n.º 322/2015 "
                             "entre o Município Alfa e o Sindicato Beta", chave="anterior")
    current = public_notice("Aviso n.º 2/2026 - Alteração ao Acordo Coletivo de Trabalho n.º 322/2015 "
                            "entre o Município Alfa e o Sindicato Beta", chave="atual",
                            altera="Aviso n.º 5356/2018 - Diário da República n.º 77/2018")
    tipologias.enriquecer([previous, current])
    assert current["relacoes_documentais"][0]["alvo_chave"] == "anterior"


def test_generic_notice_keeps_an_independent_file_name():
    item = public_notice("Aviso de projeto de portaria", ano=2026, num_bte=2, id_dgert="10/2026")
    name, warnings = nomeacao.nome_documento(item)
    assert "_AVISO_010_DOC10-2026_" in name
    assert not nomeacao.avisos_bloqueantes(warnings)


def test_workspace_installs_rules_and_allows_selecting_cessations(tmp_path):
    root = initialize(tmp_path / "RNC")
    path = root / "0_gestao/vocabularios/tipologias_documentais.json"
    data = json.loads(path.read_text())
    assert data["versao"] == "2026-10-16.1"
    assert document_source(root, "cessacao").is_dir()
    assert document_source(root, "todos") == root / "1_fontes/irct"
    data["versao"] = "equipa"
    path.write_text(json.dumps(data))
    initialize(root)
    assert tipologias.carregar(path)["versao"] == "equipa"
    data["versao"] = "equipa-revista"
    path.write_text(json.dumps(data))
    assert tipologias.carregar(path)["versao"] == "equipa-revista"


def test_registry_preserves_published_and_normalized_types(tmp_path):
    item = public_notice("Aviso de alteração ao Acordo Coletivo de Trabalho n.º 1/2025 "
                         "entre o Município Alfa e o Sindicato Beta", chave="aviso")
    item.update(tipologias.classificar(item))
    registry = Registo(tmp_path / "registo.jsonl", {})
    registry.actualizar(item)
    registry.guardar()
    stored = Registo.carregar(registry.caminho).entradas["aviso"]
    assert stored["tipo"] == "AVISO" and stored["tipo_documental"] == "ACEP-ALT"


def test_declared_document_profiles_allow_zero_clauses_without_hiding_other_checks():
    from crl_markdown.legacy import sanidade
    for name in ("2026_BTE_27_CES-VIG_331_25859_APAT-FETESE",
                 "2026_BTE_24_APU_270_ACEP-DELI_ACEP50-2022_Municipio-SINTAP"):
        subtype = tipologias.perfil_documental(name)
        assert sanidade.sem_articulado({"subtipo": subtype, "nos": []}) == sanidade.AVISO_DECLARATIVO_SEM_ARTICULADO
        warnings = sanidade.verificar({"subtipo": subtype, "nos": []}, "Texto sem nota de depósito.")
        assert not any("sem nota de depósito" in warning for warning in warnings)
    assert sanidade.sem_articulado({"subtipo": "desconhecido", "nos": []}) == sanidade.AVISO_SEM_ESTRUTURA
    assert tipologias.perfil_documental("documento_sobre_cessacao") == "desconhecido"
