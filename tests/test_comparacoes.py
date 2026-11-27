"""Pastas de comparação e comparação com a versão completa anterior."""

import csv

import openpyxl
import pytest

from crl_markdown import cli, comparacoes, diacronia
from crl_markdown.recolha import Registo, sha256_ficheiro
from crl_markdown.workspace import initialize


def versao(doc_id, clausulas):
    """Versão sintética: `clausulas` é uma lista de (rótulo, corpo)."""
    texto, nos = "", []
    for n, (rotulo, corpo) in enumerate(clausulas):
        inicio = len(texto)
        texto += f"{rotulo}\n{corpo}\n"
        tipo = "anexo" if rotulo.lower().startswith("anexo") else "clausula"
        nos.append({"id": f"{doc_id}-{n}", "tipo": tipo, "rotulo": rotulo, "folha": True,
                    "char_start": inicio, "char_end": len(texto)})
    return {"doc_id": doc_id, "nos": nos, "texto": texto}


# Uma cláusula longa, como as do BTE: muda um valor e quase nada mais
REGRAS = " ".join(f"{n}- O subsídio é devido em cada dia de trabalho efetivo, "
                  "nos termos e condições previstos nesta cláusula." for n in range(2, 12))

ANTERIOR = [
    ("Cláusula 1.ª - Âmbito", "1- O presente contrato obriga as empresas e os trabalhadores."),
    ("Cláusula 2.ª - Vigência", "1- O respectivo contrato vigora por 12 meses; a) Prazo inicial."),
    ("Cláusula 3.ª - Subsídio de refeição", "1- O subsídio de refeição é de 4,29 € por dia. " + REGRAS),
    ("Cláusula 4.ª - Formação", "O empregador proporciona acções de formação contínua aos "
                                 "trabalhadores, com o mínimo de quarenta horas anuais."),
    ("Cláusula 5.ª - Disposição revogada", "Esta cláusula desaparece na revisão global."),
    ("Anexo I - Tabela salarial", "Grau 1 | 900,00\nGrau 2 | 1 000,00"),
]
NOVA = [
    ("Cláusula 1.ª - Âmbito", "1- O presente contrato obriga as empresas e os trabalhadores."),
    ("Cláusula 2.ª - Vigência", "1-O respetivo contrato vigora por 12 meses. a)Prazo inicial."),
    ("Cláusula 3.ª - Subsídio de refeição", "1- O subsídio de refeição é de 4,42 € por dia. " + REGRAS),
    ("Cláusula 4.ª - Igualdade", "Cláusula nova sobre igualdade e não discriminação no emprego."),
    ("Cláusula 5.ª - Formação", "O empregador proporciona ações de formação contínua aos "
                                 "trabalhadores, com o mínimo de quarenta horas anuais."),
    ("Anexo I - Tabela salarial", "Grau 1 | 950,00\nGrau 2 | 1 050,00"),
]


def test_formal_differences_are_separated_from_content_changes():
    resultado = diacronia.comparar(versao("anterior", ANTERIOR), versao("nova", NOVA))
    por_rotulo = {(r["rotulo_novo"] or r["rotulo_anterior"]): r for r in resultado["linhas"]}
    assert por_rotulo["Cláusula 1.ª - Âmbito"]["classificacao"] == "="
    assert por_rotulo["Cláusula 2.ª - Vigência"]["classificacao"] == "alteracao_formal"
    valor = por_rotulo["Cláusula 3.ª - Subsídio de refeição"]
    # 0,996 de semelhança: com o limiar do AppCCT ficava «=»
    assert valor["semelhanca"] >= 0.995
    assert valor["classificacao"] == "alteracao" and valor["numeros_alterados"]
    assert "[-4,29-] {+4,42+}" in valor["diferencas"]
    renumerada = por_rotulo["Cláusula 5.ª - Formação"]
    assert renumerada["renumerada"] and renumerada["rotulo_anterior"] == "Cláusula 4.ª - Formação"
    assert renumerada["classificacao"] == "alteracao_formal"
    assert por_rotulo["Cláusula 4.ª - Igualdade"]["classificacao"] == "nova"
    assert por_rotulo["Cláusula 5.ª - Disposição revogada"]["classificacao"] == "removida"
    assert por_rotulo["Anexo I - Tabela salarial"]["classificacao"] == "alteracao"
    assert resultado["resumo"] == {"=": 1, "alteracao_formal": 2, "alteracao": 2,
                                   "nova": 1, "removida": 1}


@pytest.mark.parametrize("anterior,novo", [
    ("1- O respectivo trabalhador", "1-O respetivo trabalhador"),
    ("a) Efectuar inspecções; b) Acto", "a)Efetuar inspeções. b)Ato"),
    ("trabalho nocturno do sector", "trabalho noturno do setor"),
    ("declaração me- dica", "declaração médica"),
    ("recusar -se a cumprir", "recusar-se a cumprir"),
    ("Almoço ........ 12,00 €", "– Almoço 12,00 €"),
])
def test_formal_key_ignores_spelling_spacing_and_layout(anterior, novo):
    assert diacronia.chave_formal(anterior) == diacronia.chave_formal(novo)


@pytest.mark.parametrize("anterior,novo", [
    ("valor de 4,29 €", "valor de 4,42 €"),
    ("valor de 42,9 €", "valor de 4,29 €"),
    ("no número 6 da cláusula", "no número 7 da cláusula"),
    ("contacto pessoal", "acto pessoal"),
])
def test_formal_key_keeps_values_and_words(anterior, novo):
    assert diacronia.chave_formal(anterior) != diacronia.chave_formal(novo)


def test_index_reference_is_described_and_partial_alteration_is_flagged():
    texto, aviso = comparacoes.descrever_referencias("ACT.20241108.484/2024")
    assert texto == "ACT 484/2024, publicado a 08/11/2024 (ACT.20241108.484/2024)"
    assert aviso == ""
    texto, aviso = comparacoes.descrever_referencias(
        "ACT-ALT.20220509.104/2022; ACT-ALT.20250408.144/2025")
    assert "ACT-ALT 144/2025, publicado a 08/04/2025" in texto
    assert aviso.startswith("Alteração parcial")
    assert comparacoes.descrever_referencias("")[1].startswith("Índice sem referência")


def _entrada(chave, titulo, nome=None, caminho=None, altera="CCT.20231229.511/2023"):
    entrada = {"chave": chave, "ano": 2026, "num_bte": 1, "id_dgert": chave.split("/")[-1] + "/2026",
               "tipo": "CCT", "familia": "convencao", "cod_irct": "27204",
               "titulo": titulo, "altera": altera}
    if nome:
        entrada["nomeacao"] = {"estado": "nomeado", "nome": nome, "caminho": str(caminho),
                               "sha256": sha256_ficheiro(caminho)}
    return entrada


@pytest.fixture
def workspace(tmp_path):
    root = initialize(tmp_path / "RNC_Dados_2026")
    nome = "2026_BTE_01_PRI_041_CCT_27204_ACAP-SINDEL+1"
    pdf = root / "1_fontes/irct/convencoes/PRI" / (nome + ".pdf")
    pdf.write_bytes(b"%PDF actual")
    entradas = [
        _entrada("2026/1/41", "Contrato coletivo entre a ACAP e o SINDEL - Revisão global.", nome, pdf),
        _entrada("2026/1/42", "Contrato coletivo entre a X e o Y - Revisão Global."),
        _entrada("2026/1/43", "Contrato coletivo entre a X e o Y - Alteração salarial e outras."),
    ]
    Registo(root / "0_gestao/catalogo/registo_bte.jsonl", {e["chave"]: e for e in entradas}).guardar()
    equipa = root / "3_analise/comparacoes/053_BTE_05_2026_ACAP_SINDEL"
    equipa.mkdir(parents=True)
    (equipa / "ACAP_SINDEL_2023.pdf").write_bytes(b"da equipa")
    return root, nome


def _pendentes(root):
    with (root / "3_analise/comparacoes/pendentes.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def test_prepare_simulates_then_creates_folder_copy_and_pending_list(workspace):
    root, nome = workspace
    linhas = comparacoes.preparar(root)
    assert [linha["estado"] for linha in linhas] == ["a_criar", "por_nomear"]
    assert not (root / "3_analise/comparacoes" / nome).exists()
    assert not (root / "3_analise/comparacoes/pendentes.csv").exists()

    comparacoes.preparar(root, aplicar=True)
    pasta = root / "3_analise/comparacoes" / nome
    assert (pasta / (nome + ".pdf")).read_bytes() == b"%PDF actual"
    linhas = _pendentes(root)
    assert [(linha["pasta"], linha["estado"]) for linha in linhas] == [(nome, "sem_anterior"), ("", "por_nomear")]
    assert linhas[0]["versao_anterior_indice"].startswith("CCT 511/2023, publicado a 29/12/2023")
    # a pasta criada pela equipa com outro nome fica como estava
    equipa = root / "3_analise/comparacoes/053_BTE_05_2026_ACAP_SINDEL"
    assert [p.name for p in equipa.iterdir()] == ["ACAP_SINDEL_2023.pdf"]


def test_prepare_reports_folder_state_and_keeps_team_notes(workspace):
    root, nome = workspace
    comparacoes.preparar(root, aplicar=True)
    pasta = root / "3_analise/comparacoes" / nome
    linhas = _pendentes(root)
    linhas[0]["observacoes"] = "Pedido à DGERT"
    with (root / "3_analise/comparacoes/pendentes.csv").open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)
    (pasta / "duplicado.pdf").write_bytes(b"%PDF actual")
    assert comparacoes.preparar(root, aplicar=True)[0]["estado"] == "anterior_igual_ao_actual"
    (pasta / "duplicado.pdf").unlink()
    (pasta / "ACAP_SINDEL_29_2023.pdf").write_bytes(b"%PDF anterior")
    linha = comparacoes.preparar(root, aplicar=True)[0]
    assert (linha["estado"], linha["ficheiros_anteriores"]) == ("pronta", "ACAP_SINDEL_29_2023.pdf")
    assert _pendentes(root)[0]["observacoes"] == "Pedido à DGERT"


def test_prepare_never_replaces_a_different_pdf(workspace):
    root, nome = workspace
    pasta = root / "3_analise/comparacoes" / nome
    pasta.mkdir(parents=True)
    (pasta / (nome + ".pdf")).write_bytes(b"outro")
    assert comparacoes.preparar(root, aplicar=True)[0]["estado"] == "sem_pdf_actual"
    assert (pasta / (nome + ".pdf")).read_bytes() == b"outro"


@pytest.fixture
def versoes_sinteticas(monkeypatch):
    def falsa(pdf, relatorios=None):
        clausulas = ANTERIOR if b"anterior" in pdf.read_bytes() else NOVA
        return {**versao(pdf.stem, clausulas), "ficheiro": pdf, "sha256": sha256_ficheiro(pdf),
                "extracao": "docling", "fonte_extracao": "teste"}
    monkeypatch.setattr(comparacoes, "versao", falsa)


def test_compare_folder_writes_excel_with_provenance(workspace, versoes_sinteticas):
    root, nome = workspace
    comparacoes.preparar(root, aplicar=True)
    pasta = root / "3_analise/comparacoes" / nome
    (pasta / "ACAP_SINDEL_2018.pdf").write_bytes(b"%PDF anterior 2018")
    (pasta / "ACAP_SINDEL_29_2023.pdf").write_bytes(b"%PDF anterior 2023")
    resultado = comparacoes.comparar_pasta(pasta)
    assert resultado["anterior"] == "ACAP_SINDEL_29_2023.pdf"
    assert "Mais de um PDF anterior" in resultado["avisos"][0]
    livro = openpyxl.load_workbook(pasta / (nome + "_comparacao.xlsx"))
    assert livro.sheetnames == ["Comparação", "Resumo", "Proveniência"]
    primeira = [c.value for c in livro["Comparação"][2]]
    assert primeira[0] == "nova"
    proveniencia = {r[0]: r[1] for r in livro["Proveniência"].iter_rows(values_only=True)}
    assert proveniencia["Documento anterior"] == "ACAP_SINDEL_29_2023.pdf"
    assert proveniencia["SHA-256 actual"] == sha256_ficheiro(pasta / (nome + ".pdf"))
    again = comparacoes.comparar_pasta(pasta)
    assert "--substituir" in again["avisos"][0]
    assert comparacoes.preparar(root, aplicar=True, copiar=False)[0]["estado"] == "comparada"


def test_compare_refuses_the_current_document_as_previous(workspace, versoes_sinteticas):
    root, nome = workspace
    comparacoes.preparar(root, aplicar=True)
    pasta = root / "3_analise/comparacoes" / nome
    (pasta / "copia.pdf").write_bytes(b"%PDF actual")
    resultado = comparacoes.comparar_pasta(pasta)
    assert resultado["estado"] == "anterior_igual_ao_actual"
    assert not (pasta / (nome + "_comparacao.xlsx")).exists()


def test_cli_prepares_and_compares(workspace, versoes_sinteticas, capsys):
    root, nome = workspace
    assert cli.main(["prepare-comparisons", "--workspace", str(root)]) == 0
    assert "Simulação" in capsys.readouterr().out
    assert cli.main(["prepare-comparisons", "--workspace", str(root), "--aplicar"]) == 0
    pasta = root / "3_analise/comparacoes" / nome
    (pasta / "ACAP_SINDEL_29_2023.pdf").write_bytes(b"%PDF anterior")
    assert cli.main(["compare", "--workspace", str(root)]) == 0
    assert (pasta / (nome + "_comparacao.xlsx")).is_file()
    assert _pendentes(root)[0]["estado"] == "comparada"


def _extraida(doc_id, salario):
    """Estrutura do extractor real: o anexo é só o cabeçalho; a tabela fica num «bloco» filho."""
    from crl_markdown.legacy.extractor import estruturar

    texto = ("Cláusula 1.ª\nÂmbito\n1- O presente contrato obriga as empresas e os trabalhadores.\n"
             "ANEXO I\nTabela salarial\nNível | Categoria | Retribuição\n"
             f"I | Encarregado | {salario}\nII | Operador | 850,00\n")
    estrutura, estruturado = estruturar(texto, doc_id)
    return {"doc_id": doc_id, "nos": estrutura["nos"], "texto": estruturado}


def test_salary_change_inside_annex_table_is_not_equal():
    anterior, nova = _extraida("anterior", "900,00"), _extraida("nova", "950,00")
    anexo = next(n for n in nova["nos"] if n["tipo"] == "anexo")
    assert any(n.get("pai") == anexo["id"] and n["tipo"] == "bloco" for n in nova["nos"])
    linhas = {r["rotulo_novo"]: r for r in diacronia.comparar(anterior, nova)["linhas"]}
    tabela = linhas["ANEXO I - Tabela salarial"]
    assert tabela["classificacao"] == "alteracao" and tabela["numeros_alterados"]
    assert "[-900,00-] {+950,00+}" in tabela["diferencas"]
    assert linhas["Cláusula 1.ª - Âmbito"]["classificacao"] == "="
    igual = diacronia.comparar(anterior, _extraida("nova", "900,00"))
    assert igual["resumo"]["="] == 2
