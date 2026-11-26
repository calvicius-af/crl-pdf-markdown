import csv
import importlib.util
import json
from pathlib import Path

import pytest

from crl_markdown.diagnostics import explain, save_failure
from crl_markdown.naming import key, make_name, name_records
from crl_markdown.recolha import Registo, sha256_ficheiro
from crl_markdown.workspace import initialize


def entry():
    return {"chave": "2026/31/original", "ano": 2026, "num_bte": 31,
            "id_dgert": "377/2026", "tipo": "CCT", "familia": "convencao",
            "cod_irct": "27251", "outorgantes": "ACRAL;CESP - Sindicato dos Trabalhadores;STRUP;SIESI;SINTTAV"}


def test_name_matches_supplied_readme_and_never_uses_internal_ordinal():
    table = {key(s): s for s in ["ACRAL", "CESP", "STRUP", "SIESI", "SINTTAV"]}
    assert make_name(entry(), table, {}, scheme="v4")[0] == "2026_PRI_377_CCT_27251_BTE_31_ACRAL-CESP-STRUP+2"
    with pytest.raises(ValueError, match="IDDocumento"):
        make_name({**entry(), "id_dgert": "377/2025"}, table, {})
    with pytest.raises(ValueError, match="Sigla"):
        make_name(entry(), {}, {}, scheme="v4")
    with pytest.raises(ValueError, match="Âmbito"):
        make_name(entry(), table, {key("ACRAL"): "../fora"})


def test_adhesion_written_in_full_is_not_silently_ignored():
    from crl_markdown.recolha import familia
    assert familia("ADESÃO") == "adesao"
    assert familia("ACORDÃO") == "acordao"


def test_copy_keeps_original_and_refuses_hash_mismatch_or_existing_different_pdf(tmp_path):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"original bytes")
    registry_path = tmp_path / "registo.jsonl"
    item = {**entry(), "descarga": {"caminho": str(source), "sha256": sha256_ficheiro(source)}}
    Registo(registry_path, {item["chave"]: item}).guardar()
    siglas = tmp_path / "siglas.csv"
    siglas.write_text("nome;sigla;estado\nACRAL;ACRAL;documentada\nCESP;CESP;documentada\nSTRUP;STRUP;documentada\n")
    scopes = tmp_path / "ambitos.csv"
    scopes.write_text("nome;ambito\nACRAL;PRI\n")
    root = initialize(tmp_path / "RNC_Dados_2026")
    proposed = name_records(registry_path, root, siglas, scopes)
    assert proposed[0]["estado"] == "proposto"
    assert not list((root / "1_fontes").rglob("*.pdf"))
    applied = name_records(registry_path, root, siglas, scopes, apply=True)
    target = next((root / "1_fontes").rglob("*.pdf"))
    assert applied[0]["estado"] == "nomeado"
    assert target.read_bytes() == source.read_bytes()
    assert name_records(registry_path, root, siglas, scopes, apply=True)[0]["estado"] == "nomeado"
    catalog = root / "0_gestao/catalogo/catalogo_irct_2026.csv"
    rows = list(csv.DictReader(catalog.open(encoding="utf-8"), delimiter=";"))
    rows[0]["observacoes_equipa"] = "Conferido pela analista"
    with catalog.open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    target.write_bytes(b"different")
    failed = name_records(registry_path, root, siglas, scopes, apply=True)
    assert failed[0]["estado"] == "por_confirmar"
    assert target.read_bytes() == b"different"
    assert "Conferido pela analista" in catalog.read_text(encoding="utf-8")


def test_diagnostic_has_recovery_and_technical_trace(tmp_path):
    error = PermissionError("pasta sem acesso")
    path = save_failure(error, tmp_path, "Conversão")
    assert "O que fazer agora" in path.read_text(encoding="utf-8")
    data = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["code"] == "CRL-PERMISSOES" and "PermissionError" in data["traceback"]
    assert explain(FileExistsError("saída"))["code"] == "CRL-SAIDA-EXISTENTE"


def test_offline_verifier_refuses_corruption_before_installation(tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "scripts/instalar_offline.py"
    spec = importlib.util.spec_from_file_location("installer", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import platform
    import sys
    (tmp_path / "pacote.json").write_text(json.dumps({
        "platform": sys.platform, "machine": platform.machine(),
        "python": list(sys.version_info[:2]), "files": {"missing.whl": "0" * 64}}))
    with pytest.raises(ValueError, match="em falta"):
        module.verify(tmp_path)


def test_consolidated_siglas_safe_rows_have_no_acronym_collision_between_lineages():
    path = Path(__file__).resolve().parents[1] / "siglas.csv"
    claims = {}
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    assert len(rows) > 3000
    for row in rows:
        assert row["fonte"] and row["sigla"] and row["estado"]
        if row["estado"] != "documentada":
            continue
        lineage = ".".join(row["codigo_dgert"].split(".")[:2]) or key(row["nome"])
        previous = claims.setdefault(row["sigla"].casefold(), lineage)
        assert previous == lineage


def _registry_for_naming(tmp_path, items=None):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\nsource")
    item = {**entry(), "descarga": {"estado": "descarregado", "caminho": str(source),
                                   "sha256": sha256_ficheiro(source)}}
    records = Registo(tmp_path / "registry.jsonl", {item["chave"]: item})
    if items:
        records.entradas.update(items)
    records.guardar()
    return records


def test_preview_preserves_assigned_identity_registry_and_catalog_notes(tmp_path):
    from crl_markdown.naming import execute_records
    records = _registry_for_naming(tmp_path)
    root = initialize(tmp_path / "RNC")
    table = {key(s): s for s in ["ACRAL", "CESP", "STRUP"]}
    execute_records(records, root, table, {}, apply=True)
    before = records.caminho.read_bytes()
    result = execute_records(records, root, table, {}, apply=False)
    assert result[0]["estado"] == "nomeado"
    assert records.caminho.read_bytes() == before
    result = execute_records(records, root, {**table, key("ACRAL"): "NOVO"}, {}, apply=False)
    assert result[0]["estado"] == "nomeado"
    assert result[0]["nome_proposto"].endswith("NOVO-CESP+3")
    assert records.caminho.read_bytes() == before
    catalog = root / "0_gestao/catalogo/catalogo_irct_2026.csv"
    row = next(csv.DictReader(catalog.open(encoding="utf-8"), delimiter=";"))
    assert row["nome_canonico"].endswith("ACRAL-CESP+3")
    assert row["estado_nomeacao"] == "nomeado"
    assert row["estado_proposta"] == "nomeado"


def test_invalid_catalog_rejected_before_copy_or_registry_write(tmp_path):
    from crl_markdown.naming import execute_records
    records = _registry_for_naming(tmp_path)
    root = initialize(tmp_path / "RNC")
    catalog = root / "0_gestao/catalogo/catalogo_irct_2026.csv"
    catalog.write_text("nome;observacoes_equipa\nlegado;conservar\n")
    before = records.caminho.read_bytes()
    with pytest.raises(ValueError, match="chave estável"):
        execute_records(records, root, {key(s): s for s in ["ACRAL", "CESP", "STRUP"]}, {}, apply=True)
    assert records.caminho.read_bytes() == before
    assert catalog.read_text(encoding="utf-8").endswith("legado;conservar\n")
    assert not list((root / "1_fontes").rglob("*.pdf"))


def test_conflicting_destinations_in_batch_do_not_write_first_pdf(tmp_path):
    from crl_markdown.naming import execute_records
    records = _registry_for_naming(tmp_path)
    second = tmp_path / "second.pdf"
    second.write_bytes(b"%PDF-1.7\nanother document")
    item = {**entry(), "chave": "second", "descarga": {"caminho": str(second), "sha256": sha256_ficheiro(second)}}
    records.entradas[item["chave"]] = item
    root = initialize(tmp_path / "RNC")
    results = execute_records(records, root, {key(s): s for s in ["ACRAL", "CESP", "STRUP"]}, {}, apply=True)
    assert all(result["estado"] == "por_confirmar" for result in results)
    assert not list((root / "1_fontes").rglob("*.pdf"))
    assert not list(root.rglob("*.part"))


def test_initialize_uses_packaged_vocabulary_and_preserves_team_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = initialize(tmp_path / "RNC")
    siglas = root / "0_gestao/vocabularios/siglas.csv"
    assert len(list(csv.DictReader(siglas.open(encoding="utf-8"), delimiter=";"))) > 3000
    siglas.write_text("nome;sigla;estado\nEquipa;EQ;confirmada\n")
    initialize(root)
    assert "Equipa;EQ;confirmada" in siglas.read_text(encoding="utf-8")
    assert (root / "1_fontes/irct/acordaos").is_dir()


def test_consolidated_state_is_required_and_ambiguous_name_is_rejected(tmp_path):
    from crl_markdown.naming import load_siglas
    siglas = tmp_path / "siglas.csv"
    siglas.write_text("nome;sigla;estado\nEmpresa;ABC;por_confirmar\nAmbigua;XYZ;ambigua\n"
                      "Confirmada;CF;confirmada\nDuplicada;A;documentada\nDuplicada;B;documentada\n")
    assert load_siglas(siglas) == {key("Confirmada"): "CF"}


def test_naming_scheme_selection_and_structural_metadata_are_explicit():
    from crl_markdown.nomeacao import nome_documento
    table = {key(s): s for s in ["ACRAL", "CESP", "STRUP"]}
    assert make_name(entry(), table, {}, scheme="adr0022")[0] == "2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+3"
    with pytest.raises(ValueError, match="Código IRCT"):
        nome_documento({**entry(), "cod_irct": "27251x"}, tabela=table)
    with pytest.raises(ValueError, match="Tipo"):
        nome_documento({**entry(), "tipo": "CCT!"}, tabela=table)
    with pytest.raises(ValueError, match="IDDocumento"):
        nome_documento({**entry(), "id_dgert": ""}, ordinal=1, tabela=table)


def _consolidator():
    path = Path(__file__).resolve().parents[1] / "scripts/consolidar_siglas.py"
    spec = importlib.util.spec_from_file_location("siglas_consolidation_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_siglas_consolidation_does_not_confirm_an_acronym_fragment_identity(tmp_path):
    import openpyxl
    module = _consolidator()
    docs = tmp_path / "docs"
    docs.mkdir()
    complement = tmp_path / "organizations.csv"
    complement.write_text("codigo_dgert;denominacao;sigla;origem_sigla;lado\n"
                          "1.2.0;XYZ - Sindicato Alfa;XYZ;registo;trabalhadores\n")
    workbook = openpyxl.Workbook()
    workbook.active.append(["Outorgantes"])
    workbook.active.append(["Sindicato Completamente Diferente - XYZ"])
    workbook.save(docs / "indice.xlsx")
    output = tmp_path / "proposta.csv"
    module.consolidate(docs, complement, output)
    rows = list(csv.DictReader(output.open(encoding="utf-8"), delimiter=";"))
    other = next(row for row in rows if "Diferente" in row["nome"])
    assert other["codigo_dgert"] == ""
    assert other["estado"] == "ambigua"
    assert all(row["estado"] == "ambigua" for row in rows)
    with pytest.raises(FileExistsError):
        module.consolidate(docs, complement, output)


def test_siglas_consolidation_preserves_reviewed_decision_with_evidence(tmp_path):
    module = _consolidator()
    docs = tmp_path / "docs"
    docs.mkdir()
    complement = tmp_path / "organizations.csv"
    complement.write_text("codigo_dgert;denominacao;sigla;origem_sigla;lado\n"
                          "1.2.0;Sindicato Alfa;XYZ;registo;trabalhadores\n")
    decisions = tmp_path / "ativo.csv"
    decisions.write_text("nome;sigla;codigo_dgert;lado;estado;origem_sigla;fonte;responsavel;data\n"
                         "Sindicato Alfa;ALFA;1.2.0;trabalhadores;confirmada;equipa;Ata 12;Analista;2026-10-13\n")
    output = tmp_path / "proposta.csv"
    module.consolidate(docs, complement, output, decisions=decisions)
    row = next(csv.DictReader(output.open(encoding="utf-8"), delimiter=";"))
    assert row["estado"] == "confirmada" and row["sigla"] == "ALFA"
    assert row["responsavel"] == "Analista" and row["fonte"] == "Ata 12"
    assert "ALFA" in decisions.read_text(encoding="utf-8")
    decisions.write_text(decisions.read_text(encoding="utf-8").replace(";Analista;", ";;"))
    with pytest.raises(ValueError, match="responsável"):
        module.consolidate(docs, complement, tmp_path / "second.csv", decisions=decisions)
    assert not (tmp_path / "second.csv").exists()


def test_naming_copy_on_share_without_hardlinks_is_exclusive_and_verified(tmp_path, monkeypatch):
    import errno

    from crl_markdown import naming
    records = _registry_for_naming(tmp_path)
    root = initialize(tmp_path / "RNC")

    def unsupported(*args):
        raise OSError(errno.EOPNOTSUPP, "not supported on this share")

    monkeypatch.setattr(naming.os, "link", unsupported)
    result = naming.execute_records(records, root, {key(s): s for s in ["ACRAL", "CESP", "STRUP"]}, {}, apply=True)
    assert result[0]["estado"] == "nomeado"
    pdf = next((root / "1_fontes").rglob("*.pdf"))
    assert sha256_ficheiro(pdf) == result[0]["sha256"]
    assert not list(root.rglob("*.part"))


@pytest.mark.parametrize("acronyms", [("ALFA", "BETA"), ("BETA", "ALFA")])
@pytest.mark.parametrize("codes", [("1.2.0", "1.2.0"), ("1.2.0", "1.2.1")])
def test_siglas_conflicting_human_decisions_fail_before_output(tmp_path, acronyms, codes):
    module = _consolidator()
    docs = tmp_path / "docs"
    docs.mkdir()
    complement = tmp_path / "organizations.csv"
    complement.write_text("codigo_dgert;denominacao;sigla;origem_sigla;lado\n"
                          "1.2.0;Sindicato Alfa;XYZ;registo;trabalhadores\n")
    decisions = tmp_path / "ativo.csv"
    decisions.write_text(
        "nome;sigla;codigo_dgert;lado;estado;origem_sigla;fonte;responsavel;data\n"
        + "".join(f"Sindicato Alfa;{acronym};{code};trabalhadores;confirmada;equipa;Ata {i};Analista;2026-10-13\n"
                  for i, (acronym, code) in enumerate(zip(acronyms, codes)))
    )
    before = decisions.read_bytes()
    output = tmp_path / "proposta.csv"
    with pytest.raises(ValueError, match="confirmadas contraditórias"):
        module.consolidate(docs, complement, output, decisions=decisions)
    assert not output.exists()
    assert not output.with_suffix(".manifest.json").exists()
    assert decisions.read_bytes() == before


def test_siglas_identical_human_decisions_deduplicate_and_keep_evidence(tmp_path):
    module = _consolidator()
    docs = tmp_path / "docs"
    docs.mkdir()
    complement = tmp_path / "organizations.csv"
    complement.write_text("codigo_dgert;denominacao;sigla;origem_sigla;lado\n"
                          "1.2.0;Sindicato Alfa;XYZ;registo;trabalhadores\n")
    decisions = tmp_path / "ativo.csv"
    decisions.write_text(
        "nome;sigla;codigo_dgert;lado;estado;origem_sigla;fonte;responsavel;data\n"
        "Sindicato Alfa;ALFA;1.2.0;trabalhadores;confirmada;equipa;Ata 12;Ana;2026-10-12\n"
        "Sindicato Alfa;ALFA;1.2.0;trabalhadores;confirmada;equipa;Ata 13;Bruno;2026-10-13\n"
    )
    output = tmp_path / "proposta.csv"
    module.consolidate(docs, complement, output, decisions=decisions)
    rows = list(csv.DictReader(output.open(encoding="utf-8"), delimiter=";"))
    assert len(rows) == 1
    assert rows[0]["sigla"] == "ALFA" and rows[0]["estado"] == "confirmada"
    assert rows[0]["fonte"] == "Ata 12 | Ata 13"
    assert rows[0]["responsavel"] == "Ana | Bruno"
    assert rows[0]["data"] == "2026-10-12 | 2026-10-13"


@pytest.mark.parametrize("state", ["ambigua", "por_confirmar"])
def test_denied_siglas_cannot_be_confirmed_by_literal_fallback(tmp_path, state):
    from crl_markdown.naming import execute_records
    from crl_markdown.nomeacao import carregar_siglas, nome_documento, sigla, tabela_de_siglas
    vocabulary = tmp_path / "siglas.csv"
    vocabulary.write_text(
        "nome;sigla;estado;codigo_dgert\n"
        f"Empresa Alfa - XYZ;XYZ;{state};5.1.0\n"
        f"Empresa Beta - XYZ;XYZ;{state};5.2.0\n"
        "Sindicato Gamma - SG;SG;confirmada;1.3.0\n"
    )
    loaded = carregar_siglas(vocabulary)
    merged = tabela_de_siglas(equipa=vocabulary, dgert=False)
    item = {**entry(), "outorgantes": "Empresa Alfa - XYZ;Sindicato Gamma - SG"}
    for table in (loaded, merged):
        _, warnings = nome_documento(item, tabela=table, vocabulario_ambito={})
        assert any("pendente ou ambígua" in warning for warning in warnings)
        # Uma variante ainda não listada também não pode publicar a sigla recusada.
        assert "pendente ou ambígua" in sigla("XYZ - Empresa Variante", table)[1]
        records = _registry_for_naming(tmp_path)
        records.entradas[item["chave"]]["outorgantes"] = item["outorgantes"]
        root = initialize(tmp_path / "RNC")
        results = execute_records(records, root, table, {}, apply=True)
        assert results[0]["estado"] == "por_confirmar"
        assert "pendente ou ambígua" in results[0]["motivo"]
        assert not list((root / "1_fontes").rglob("*.pdf"))


def test_team_pending_identity_blocks_safe_lower_priority_vocabulary(tmp_path):
    from crl_markdown.nomeacao import sigla, tabela_de_siglas
    team = tmp_path / "team.csv"
    team.write_text("nome;sigla;estado\nEmpresa Alfa - XYZ;XYZ;por_confirmar\n")
    complement = tmp_path / "complement.csv"
    complement.write_text("nome;sigla;estado\nEmpresa Alfa - XYZ;XYZ;documentada\n")
    table = tabela_de_siglas([complement], equipa=team, dgert=False)
    assert "pendente ou ambígua" in sigla("Empresa Alfa - XYZ", table)[1]


@pytest.mark.parametrize('variant', [
    'XYZ - Sindicato Alfa', 'Sindicato Alfa - XYZ', 'Sindicato Alfa (XYZ)',
])
def test_exact_full_name_and_acronym_link_the_same_lineage(tmp_path, variant):
    import openpyxl
    module = _consolidator()
    docs = tmp_path / 'docs'
    docs.mkdir()
    complement = tmp_path / 'organizations.csv'
    complement.write_text('codigo_dgert;denominacao;sigla;origem_sigla;lado\n'
                          '1.2.0;Sindicato Alfa;XYZ;registo;trabalhadores\n')
    workbook = openpyxl.Workbook()
    workbook.active.append(['Outorgantes'])
    workbook.active.append([variant])
    workbook.save(docs / 'indice.xlsx')
    output = tmp_path / 'proposta.csv'
    module.consolidate(docs, complement, output)
    with output.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter=';'))
    assert len(rows) == 2
    assert all(row['codigo_dgert'] == '1.2.0' for row in rows)
    assert all(row['estado'] == 'documentada' for row in rows)
    linked = next(row for row in rows if row['nome'] == variant)
    assert linked['origem_sigla'] == 'nome_completo_exato'
