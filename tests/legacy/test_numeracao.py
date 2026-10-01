"""Número canónico das cláusulas (ISSUE-0001, issue #28).

O extrator já reconhecia «Cláusula décima segunda»; faltava dar-lhe o número
12, para que a comparação diacrónica a emparelhe com a «Cláusula 12.ª» de
outra versão. E a letra de inserção («16.ª-A») passa a distinguir a cláusula
inserida da original.
"""
import pytest

from crl_markdown.legacy.extractor import estruturar
from crl_markdown.legacy.numeracao import chave_numero, ordinal_por_extenso


@pytest.mark.parametrize("texto,valor", [
    ("primeira", 1), ("segundo", 2), ("terceira", 3), ("quarta", 4),
    ("quinta", 5), ("sexta", 6), ("sétima", 7), ("setima", 7), ("oitava", 8),
    ("nona", 9), ("décima", 10), ("décima segunda", 12), ("DÉCIMA SEGUNDA", 12),
    ("vigésima primeira", 21), ("trigésima", 30), ("quadragésima quinta", 45),
    ("nonagésima nona", 99), ("septuagésima", 70), ("setuagésima", 70),
    ("centésima", 100), ("centésima vigésima primeira", 121),
])
def test_ordinais_por_extenso(texto, valor):
    assert ordinal_por_extenso(texto) == valor


@pytest.mark.parametrize("texto", [
    "geral", "geral e transitória", "primeira décima", "décima décima",
    "", "12", "prévia",
])
def test_nao_sao_ordinais(texto):
    assert ordinal_por_extenso(texto) is None


@pytest.mark.parametrize("rotulo,chave", [
    ("Cláusula 12.ª - Horário", "cl12"),
    ("Cláusula décima segunda - Horário", "cl12"),
    ("CLÁUSULA DÉCIMA SEGUNDA - Horário", "cl12"),
    ("Cláusula décima segunda", "cl12"),
    ("Cláusula 16.ª-A - Férias", "cl16A"),
    ("Cláusula 16.ª - Férias", "cl16"),
    ("Artigo 3.º - Vigência", "ar3"),
    ("Artigo terceiro - Vigência", "ar3"),
    ("Artigo único - Âmbito", "arunico"),
    ("Cláusula única", "clunico"),
    ("Cláusula prévia - Âmbito da revisão", "clprevia"),
    ("Cláusula de revisão", "clrevisao"),
    ("Cláusula geral e transitória", None),
    ("Cláusula VII-8 - Ajudas de custo", "clVII-8"),
    ("CLÁUSULA XIII-11 - Refeitórios", "clXIII-11"),
    ("Artigo IV - Âmbito", "arIV"),
    ("Cláusula civil", None),
    ("PREÂMBULO", None),
    ("CAPÍTULO I - Disposições gerais", None),
])
def test_chave_numero(rotulo, chave):
    assert chave_numero(rotulo) == chave


def test_a_chave_coincide_com_os_rotulos_que_o_extrator_produz():
    doc, _ = estruturar("Cláusula décima segunda - Horário\nTexto.\n"
                        "Cláusula 16.ª-A - Férias\nTexto.\n"
                        "Artigo único - Âmbito\nTexto.\n", "x")
    chaves = [chave_numero(n["rotulo"]) for n in doc["nos"]
              if n["tipo"] in ("clausula", "artigo")]
    assert chaves == ["cl12", "cl16A", "arunico"]








def test_numeracao_em_romanos_por_capitulo():
    """EPAL de 2025: as cláusulas vêm numeradas por capítulo («Cláusula VII-8
    Ajudas de custo») e nenhuma era reconhecida; o documento ficava sem
    articulado. Os romanos têm de ser maiúsculos e acabar a palavra."""
    doc, _ = estruturar("Cláusula VII-8 Ajudas de custo\n1- Texto da cláusula.\n"
                        "Cláusula XIII-11 Refeitórios\n1- Outro texto.\n"
                        "Cláusula civil de responsabilidade\n", "x")
    rotulos = [n["rotulo"] for n in doc["nos"] if n["tipo"] == "clausula"]
    assert rotulos == ["Cláusula VII-8 - Ajudas de custo", "Cláusula XIII-11 - Refeitórios"]


def test_clausula_de_revisao_e_um_cabecalho():
    """EMPORDEF de 2025: a única cláusula da revisão, «Cláusula de revisão»,
    não era reconhecida e o documento ficava sem articulado."""
    doc, _ = estruturar("Cláusula de revisão\n1- A presente revisão altera o acordo.\n"
                        "Cláusula de revisão prevista no acordo anterior, que se mantém.\n", "x")
    assert [n["rotulo"] for n in doc["nos"] if n["tipo"] == "clausula"] == ["Cláusula de revisão"]


def test_designador_logo_a_seguir_ao_numero_e_o_titulo():
    """AEVP e APHP de 2025: «Artigo 1.º» e, na linha seguinte, «Artigo de
    revisão», o título. Não é outro artigo, e o 1.º não fica vazio."""
    doc, _ = estruturar("Artigo 1.º\nArtigo de revisão\nO presente contrato revê "
                        "parcialmente o anteriormente acordado pelas partes.\n", "x")
    assert [n["rotulo"] for n in doc["nos"] if n["tipo"] == "artigo"] == [
        "Artigo 1.º - Artigo de revisão"]


