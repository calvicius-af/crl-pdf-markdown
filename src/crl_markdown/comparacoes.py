"""Pastas de comparação e comparação com a versão completa anterior.

Sem índices BTE dos anos anteriores, a versão anterior é descarregada à mão.
O índice do ano diz quais convenções têm de ser comparadas (revisões globais)
e qual o documento que cada uma altera (`DocAlteradosPorEste`). A preparação:

1. cria `3_analise/comparacoes/<nome do ficheiro original>/` para cada revisão
   global nomeada e copia para lá o PDF actual, verificado pelo SHA-256;
2. escreve `3_analise/comparacoes/pendentes.csv`, com a referência da versão
   anterior a descarregar e o estado de cada pasta.

A comparação lê cada pasta: o PDF com o nome da pasta é a versão actual; outro
PDF posto pela equipa é a versão anterior. O resultado é um Excel na pasta.
"""

import csv
import json
import re
import unicodedata
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from . import diacronia
from .pipeline import atomic_write
from .recolha import Registo, sha256_ficheiro

PASTA = "3_analise/comparacoes"
PENDENTES = "pendentes.csv"
SUFIXO_EXCEL = "_comparacao.xlsx"
NOMEADOS = {"nomeado", "ja_existente", "conflito"}
CAMPOS_PENDENTES = (
    "pasta", "estado", "versao_anterior_indice", "aviso_indice", "ficheiros_anteriores",
    "comparacao", "num_bte", "ano", "id_dgert", "tipo", "cod_irct", "titulo", "observacoes",
)
_RE_REFERENCIA = re.compile(r"([A-Z]+(?:-[A-Z]+)*)\s*\.\s*(\d{4})(\d{2})(\d{2})\s*\.\s*(\d+/\d{4})")
ESTADOS = {
    "por_nomear": "Revisão global ainda sem nome atribuído; corra primeiro a nomeação",
    "sem_pdf_actual": "PDF actual não encontrado ou com hash diferente do registo",
    "sem_anterior": "Falta descarregar a versão anterior para a pasta",
    "anterior_igual_ao_actual": "O ficheiro posto como anterior é o próprio documento actual",
    "varias_anteriores": "Mais de um PDF anterior na pasta; a comparação escolhe o mais recente",
    "pronta": "Versão anterior presente; pronta para comparar",
    "comparada": "Comparação feita",
}


def _sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto or "")
                   if unicodedata.category(c) != "Mn").lower()


def e_revisao_global(entrada: dict) -> bool:
    return "revisao global" in re.sub(r"\s+", " ", _sem_acentos(entrada.get("titulo", "")))


def referencias(altera: str) -> list[dict]:
    """`ACT-ALT.20250408.145/2025` → tipo, data e número do documento alterado."""
    refs = []
    for m in _RE_REFERENCIA.finditer(altera or ""):
        tipo, ano, mes, dia, numero = m.groups()
        refs.append({"referencia": m.group(0).replace(" ", ""), "tipo": tipo,
                     "data": f"{dia}/{mes}/{ano}", "documento": numero,
                     "parcial": tipo.endswith("-ALT") or "-ALT-" in tipo})
    return refs


def descrever_referencias(altera: str) -> tuple[str, str]:
    refs = referencias(altera)
    if not refs:
        return (altera or "", "Índice sem referência ao documento alterado; procurar à mão" if not altera
                else "Referência do índice não reconhecida; conferir à mão")
    texto = "; ".join(f"{r['tipo']} {r['documento']}, publicado a {r['data']} ({r['referencia']})"
                      for r in refs)
    aviso = ("Alteração parcial: procurar o último texto completo anterior "
             "(revisão global, texto consolidado ou convenção inicial)"
             if all(r["parcial"] for r in refs) else "")
    return texto, aviso


def _pdfs(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.glob("*.pdf") if p.is_file() and not p.name.startswith("."))


def anteriores(pasta: Path, nome: str) -> list[Path]:
    return [p for p in _pdfs(pasta) if p.stem != nome]


def _ano_no_nome(caminho: Path) -> int:
    anos = [int(a) for a in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", caminho.stem)]
    return max(anos) if anos else -1


def escolher_anterior(candidatos: list[Path]) -> tuple[Path, list[str]]:
    """O mais recente pelo ano no nome (empate: o maior ficheiro), com aviso se houver vários."""
    escolhido = max(candidatos, key=lambda p: (_ano_no_nome(p), p.stat().st_size, p.name))
    avisos = []
    if len(candidatos) > 1:
        avisos.append("Mais de um PDF anterior na pasta (" + ", ".join(p.name for p in candidatos)
                      + f"); escolhido {escolhido.name}. Para outro, use --anterior.")
    return escolhido, avisos


def estado_pasta(pasta: Path, nome: str, sha: str) -> tuple[str, list[Path]]:
    actual = pasta / (nome + ".pdf")
    if not actual.is_file() or (sha and sha256_ficheiro(actual) != sha):
        return "sem_pdf_actual", []
    outros = anteriores(pasta, nome)
    if not outros:
        return "sem_anterior", []
    digest = sha256_ficheiro(actual)
    if any(sha256_ficheiro(p) == digest for p in outros):
        return "anterior_igual_ao_actual", outros
    if (pasta / (nome + SUFIXO_EXCEL)).is_file():
        return "comparada", outros
    return ("varias_anteriores" if len(outros) > 1 else "pronta"), outros


def _csv(linhas: list[dict]) -> str:
    texto = StringIO(newline="")
    escritor = csv.DictWriter(texto, fieldnames=CAMPOS_PENDENTES, delimiter=";",
                              lineterminator="\n", extrasaction="ignore")
    escritor.writeheader()
    escritor.writerows(linhas)
    return texto.getvalue()


def preparar(root: Path, registo: Path | None = None, *, aplicar=False, copiar=True) -> list[dict]:
    """Planeia (ou, com `aplicar`, cria) as pastas e o `pendentes.csv`.

    Nunca apaga nem substitui: um PDF diferente com o nome do actual fica por
    confirmar, e as pastas criadas pela equipa com outros nomes não são tocadas.
    Com `copiar=False` só actualiza os estados do `pendentes.csv`.
    """
    from .naming import _copy_verified

    root = Path(root)
    registo = Path(registo or root / "0_gestao/catalogo/registo_bte.jsonl")
    entradas = Registo.carregar(registo).entradas
    if not entradas:
        raise ValueError("Registo vazio ou inexistente. Faça primeiro a recolha a partir dos índices.")
    base = root / PASTA
    observacoes = {}
    if (base / PENDENTES).is_file():
        with (base / PENDENTES).open(encoding="utf-8-sig", newline="") as f:
            observacoes = {r.get("pasta", ""): r.get("observacoes", "")
                           for r in csv.DictReader(f, delimiter=";")}
    linhas = []
    for entrada in sorted(entradas.values(), key=lambda e: (e.get("ano", 0), e.get("num_bte") or 0,
                                                             e.get("id_dgert", ""))):
        if (entrada.get("familia") or "convencao") != "convencao" or not e_revisao_global(entrada):
            continue
        nomeacao = entrada.get("nomeacao") or {}
        nome = nomeacao.get("nome") or nomeacao.get("doc_id") or ""
        referencia, aviso = descrever_referencias(entrada.get("altera", ""))
        linha = {"pasta": nome, "versao_anterior_indice": referencia, "aviso_indice": aviso,
                 **{c: entrada.get(c, "") for c in ("num_bte", "ano", "id_dgert", "tipo",
                                                     "cod_irct", "titulo")}}
        linhas.append(linha)
        if nomeacao.get("estado") not in NOMEADOS or not nome or not nomeacao.get("caminho"):
            linha["estado"] = "por_nomear"
            linha["pasta"] = ""
            continue
        linha["observacoes"] = observacoes.get(nome, "")
        origem, sha = Path(nomeacao["caminho"]), nomeacao.get("sha256", "")
        pasta = base / nome
        destino = pasta / (nome + ".pdf")
        if not destino.exists():
            if not origem.is_file() or (sha and sha256_ficheiro(origem) != sha):
                linha["estado"] = "sem_pdf_actual"
                continue
            if not (aplicar and copiar):
                linha["estado"] = "a_criar"
                continue
            _copy_verified(origem, destino, sha or sha256_ficheiro(origem))
        estado, outros = estado_pasta(pasta, nome, sha)
        linha["estado"] = estado
        linha["ficheiros_anteriores"] = ", ".join(p.name for p in outros)
        excel = pasta / (nome + SUFIXO_EXCEL)
        linha["comparacao"] = excel.name if excel.is_file() else ""
    if aplicar:
        base.mkdir(parents=True, exist_ok=True)
        atomic_write(base / PENDENTES, _csv(linhas))
    return linhas


def texto_resumo(linhas: list[dict], *, aplicar: bool) -> str:
    contagem: dict[str, int] = {}
    for linha in linhas:
        contagem[linha["estado"]] = contagem.get(linha["estado"], 0) + 1
    partes = [f"{len(linhas)} revisões globais no registo."]
    for estado, n in sorted(contagem.items()):
        descricao = ESTADOS.get(estado, "Pasta a criar com o PDF actual" if estado == "a_criar" else estado)
        partes.append(f"  {n:>3}  {descricao}")
    if not aplicar:
        partes.append("Simulação: nada foi escrito. Repita com --aplicar para criar as pastas.")
    return "\n".join(partes)


# Extracção --------------------------------------------------------------------

def _relatorios_docling(raiz: Path):
    for caminho in sorted(raiz.rglob("*.qualidade.json")):
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if dados.get("source_sha256") and dados.get("structure_nodes") and dados.get("structured_text"):
            yield caminho, dados


def versao(pdf: Path, relatorios: dict[str, tuple[Path, dict]] | None = None) -> dict:
    """Estrutura e texto de um PDF: a extracção Docling auditada, se existir para o
    mesmo ficheiro (mesmo SHA-256); senão a leitura pdfplumber do AppCCT."""
    digest = sha256_ficheiro(pdf)
    if relatorios and digest in relatorios:
        caminho, dados = relatorios[digest]
        return {"doc_id": pdf.stem, "nos": dados["structure_nodes"], "texto": dados["structured_text"],
                "ficheiro": pdf, "sha256": digest, "extracao": "docling",
                "fonte_extracao": str(caminho)}
    from .legacy.extractor import extrair_pdf
    estrutura, texto = extrair_pdf(pdf, doc_id=pdf.stem, subtipo="revisao_parcial_com_consolidado")
    return {"doc_id": pdf.stem, "nos": estrutura["nos"], "texto": texto, "ficheiro": pdf,
            "sha256": digest, "extracao": "pdfplumber",
            "fonte_extracao": "leitura pdfplumber do AppCCT (sem conferência humana)"}


def indice_relatorios(root: Path | None) -> dict[str, tuple[Path, dict]]:
    if root is None or not (Path(root) / "2_processamento/texto").is_dir():
        return {}
    return {d["source_sha256"]: (c, d) for c, d in _relatorios_docling(Path(root) / "2_processamento/texto")}


# Excel ------------------------------------------------------------------------

LIMITE_CELULA = 32000
ORDEM = {"nova": 0, "alteracao": 1, "removida": 2, "alteracao_formal": 3, "=": 4}
DESCRICAO_CLASSES = {
    "=": "igual",
    "alteracao_formal": "só muda o espaçamento, a pontuação ou a grafia (Acordo Ortográfico)",
    "alteracao": "alteração de conteúdo",
    "nova": "sem correspondente na versão anterior",
    "removida": "sem correspondente na versão actual",
}


def _celula(texto) -> object:
    if isinstance(texto, str) and len(texto) > LIMITE_CELULA:
        return texto[:LIMITE_CELULA] + " … [cortado]"
    return texto


def exportar_excel(resultado: dict, anterior: dict, novo: dict, destino: Path,
                   avisos: list[str]) -> None:
    import openpyxl
    from openpyxl.styles import Alignment, Font

    from . import __version__

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Comparação"
    ws.append(["Classificação", "Tipo", "Rótulo (actual)", "Rótulo (anterior)", "Semelhança",
               "Renumerada", "Números alterados", "Diferenças", "Texto anterior", "Texto actual"])
    for r in sorted(resultado["linhas"], key=lambda x: (ORDEM[x["classificacao"]],
                                                        x["rotulo_novo"] or x["rotulo_anterior"])):
        ws.append([r["classificacao"], r["tipo"], r["rotulo_novo"], r["rotulo_anterior"],
                   r["semelhanca"], "sim" if r["renumerada"] else "",
                   "sim" if r["numeros_alterados"] else "", _celula(r["diferencas"]),
                   _celula(r["texto_anterior"]), _celula(r["texto_novo"])])
    for celula in ws[1]:
        celula.font = Font(bold=True)
    for coluna, largura in zip("ABCDEFGHIJ", (16, 10, 40, 40, 11, 11, 11, 70, 60, 60)):
        ws.column_dimensions[coluna].width = largura
    for linha in ws.iter_rows(min_row=2, min_col=8, max_col=10):
        for celula in linha:
            celula.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    res = wb.create_sheet("Resumo")
    res.append(["Classificação", "N.º", "Significado"])
    for classe in diacronia.CLASSES:
        res.append([classe, resultado["resumo"][classe], DESCRICAO_CLASSES[classe]])
    res.append([])
    res.append(["Unidades comparadas (actual)", resultado["unidades"]["novo"]])
    res.append(["Unidades comparadas (anterior)", resultado["unidades"]["anterior"]])
    res.append(["Renumeradas", sum(1 for r in resultado["linhas"] if r["renumerada"])])
    res.append(["Com números alterados", sum(1 for r in resultado["linhas"] if r["numeros_alterados"])])
    res.column_dimensions["A"].width = 32
    res.column_dimensions["C"].width = 70

    prov = wb.create_sheet("Proveniência")
    for rotulo, versao_ in (("actual", novo), ("anterior", anterior)):
        prov.append([f"Documento {rotulo}", versao_["ficheiro"].name])
        prov.append([f"SHA-256 {rotulo}", versao_["sha256"]])
        prov.append([f"Extracção {rotulo}", versao_["extracao"]])
        prov.append([f"Fonte da extracção {rotulo}", versao_["fonte_extracao"]])
    prov.append(["Versão da aplicação", __version__])
    prov.append(["Data", datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")])
    prov.append(["Limiares", json.dumps(diacronia.LIMITES, ensure_ascii=False)])
    prov.append(["Regra de igualdade", "texto igual sem acentos, maiúsculas nem espaços repetidos"])
    for aviso in avisos:
        prov.append(["Aviso", aviso])
    prov.column_dimensions["A"].width = 30
    prov.column_dimensions["B"].width = 100

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name("." + destino.name + ".part")
    wb.save(temporario)
    temporario.replace(destino)


# Comparação -------------------------------------------------------------------

def comparar_pasta(pasta: Path, *, anterior: Path | None = None, substituir=False,
                   relatorios: dict | None = None) -> dict:
    """Compara a versão actual (o PDF com o nome da pasta) com a anterior."""
    pasta = Path(pasta)
    nome = pasta.name
    actual = pasta / (nome + ".pdf")
    destino = pasta / (nome + SUFIXO_EXCEL)
    resultado = {"pasta": nome, "estado": "", "avisos": [], "excel": ""}
    if not actual.is_file():
        resultado.update(estado="sem_pdf_actual",
                         avisos=[f"Falta {actual.name}: o PDF actual tem o nome da pasta."])
        return resultado
    if anterior is None:
        outros = anteriores(pasta, nome)
        if not outros:
            resultado["estado"] = "sem_anterior"
            return resultado
        anterior, avisos = escolher_anterior(outros)
        resultado["avisos"].extend(avisos)
    anterior = Path(anterior)
    if sha256_ficheiro(anterior) == sha256_ficheiro(actual):
        resultado.update(estado="anterior_igual_ao_actual",
                         avisos=[f"{anterior.name} é o mesmo ficheiro que o actual; falta a versão anterior."])
        return resultado
    if destino.exists() and not substituir:
        resultado.update(estado="comparada", excel=str(destino),
                         avisos=["Comparação já existente; use --substituir para a refazer."])
        return resultado
    v_novo, v_anterior = versao(actual, relatorios), versao(anterior, relatorios)
    if len(v_anterior["texto"]) < len(v_novo["texto"]) * 0.25:
        resultado["avisos"].append(
            f"A versão anterior tem só {len(v_anterior['texto'])} caracteres, contra "
            f"{len(v_novo['texto'])} na actual: parece uma alteração parcial, não um texto completo.")
    if "pdfplumber" in (v_novo["extracao"], v_anterior["extracao"]):
        resultado["avisos"].append(
            "Pelo menos uma versão foi lida com pdfplumber, sem a extracção Docling conferida; "
            "confirmar no PDF as diferenças que forem usadas.")
    comparacao = diacronia.comparar(v_anterior, v_novo)
    exportar_excel(comparacao, v_anterior, v_novo, destino, resultado["avisos"])
    resultado.update(estado="comparada", excel=str(destino), anterior=anterior.name,
                     resumo=comparacao["resumo"],
                     extracao={"actual": v_novo["extracao"], "anterior": v_anterior["extracao"]})
    return resultado


def pastas_de_comparacao(root: Path) -> list[Path]:
    base = Path(root) / PASTA
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / (p.name + ".pdf")).is_file())


def comparar_tudo(root: Path, *, pasta: str | None = None, anterior: Path | None = None,
                  substituir=False, progresso=print) -> list[dict]:
    root = Path(root)
    if pasta:
        alvo = Path(pasta)
        alvo = alvo if alvo.is_absolute() or alvo.exists() else root / PASTA / pasta
        pastas = [alvo]
    else:
        if anterior is not None:
            raise ValueError("--anterior só se usa com --pasta.")
        pastas = pastas_de_comparacao(root)
        if not pastas:
            raise ValueError("Não há pastas de comparação. Corra primeiro prepare-comparisons --aplicar.")
    relatorios = indice_relatorios(root)
    resultados = []
    for p in pastas:
        progresso(f"A comparar {p.name}…")
        resultados.append(comparar_pasta(p, anterior=anterior, substituir=substituir,
                                         relatorios=relatorios))
    return resultados
