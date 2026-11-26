"""Natureza documental e relações explícitas, sem alterar os tipos publicados."""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

RECURSO = Path(__file__).with_name("vocabularios") / "tipologias_documentais.json"
CAMPOS = ("familia", "familia_origem", "tipo_documental", "ambito_documental", "regra_tipologia",
          "tipologia_versao", "tipo_acordo_base", "referencia_acordo_base", "texto_consolidado",
          "operacao_documental", "processo_irct", "relacoes_documentais")
RE_ACORDO = re.compile(
    r"acordo\s+colec?tivo\s+(?:de\s+trabalho\s+)?n\.?\s*[º°o]?\s*(\d+)/(\d{4})", re.I)
RE_BTE = re.compile(
    r"^\s*([A-Z][A-Z-]*)\.\s*(\d{8}|\d{2}/\d{2}/\d{4})\.(\d+)/(\d{4})\s*$")
RE_AVISO = re.compile(r"^aviso\s+n\.?\s*[º°o]?\s*(\d+)/(\d{4})", re.I)


def normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn")


def perfil_documental(doc_id):
    """Só marcadores de tipo no nome canónico alteram o perfil de auditoria."""
    if "_CES-VIG_" in doc_id.upper():
        return "cessacao_vigencia"
    if re.search(r"_(?:ACEP|ACCE)-DELI_", doc_id.upper()):
        return "deliberacao_comissao_paritaria"
    if "-RECT_" in doc_id.upper():
        return "retificacao"
    return "desconhecido"


def carregar(caminho=RECURSO):
    path = Path(caminho)
    return _carregar(str(path.resolve()), path.stat().st_mtime_ns)


@lru_cache(maxsize=16)
def _carregar(caminho, modificacao):
    data = json.loads(Path(caminho).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not data.get("versao") or not isinstance(data.get("regras"), list):
        raise ValueError("Vocabulário de tipologias inválido.")
    try:
        for regra in data["regras"]:
            for field in ("tipo_regex", "titulo_regex", "contexto_regex", "titulo_alternativo_regex"):
                if field in regra:
                    re.compile(regra[field])
    except (TypeError, re.error) as error:
        raise ValueError("Padrão inválido no vocabulário de tipologias.") from error
    return data


def classificar(entrada, regras=None):
    regras = regras or carregar()
    tipo = normalizar(entrada.get("tipo", "")).upper()
    titulo = normalizar(entrada.get("titulo", "")).lower()
    contexto = " ".join(normalizar(entrada.get(k, "")).lower()
                        for k in ("titulo", "outorgantes", "em_vigor", "altera"))
    result = {"familia_origem": entrada.get("familia_origem", entrada.get("familia")),
              "familia": entrada.get("familia_origem", entrada.get("familia")),
              "tipo_documental": tipo, "ambito_documental": "", "regra_tipologia": "tipo_publicado",
              "tipologia_versao": regras["versao"], "tipo_acordo_base": "",
              "referencia_acordo_base": "", "operacao_documental": "",
              "texto_consolidado": "texto consolidado" in titulo}
    if tipo.startswith(("ACEP", "ACCE")):
        result.update(familia="convencao", ambito_documental="APU", tipo_acordo_base=tipo.split("-")[0])
        if "-ALT" in tipo:
            result["operacao_documental"] = "alteracao"
        elif "-DELI" in tipo:
            result["operacao_documental"] = "deliberacao_comissao_paritaria"
    elif tipo.startswith("ACT") and re.search(r"acordo coletivo de [ec]mpregador publico", titulo):
        result.update(ambito_documental="APU", tipo_acordo_base="ACEP",
                      regra_tipologia="titulo_empregador_publico")
    elif tipo.startswith("ACT") and re.search(r"carreira(?:s)? especia(?:l|is)", titulo):
        result.update(ambito_documental="APU", tipo_acordo_base="ACCE",
                      regra_tipologia="titulo_carreira_especial")
    for regra in regras["regras"]:
        if regra.get("titulo_alternativo_regex") and re.search(regra["titulo_alternativo_regex"], titulo):
            matched = True
        else:
            matched = bool(re.fullmatch(regra["tipo_regex"], tipo))
            matched &= not regra.get("titulo_regex") or bool(re.search(regra["titulo_regex"], titulo))
            matched &= not regra.get("contexto_regex") or bool(re.search(regra["contexto_regex"], contexto))
        if matched:
            if regra["id"].startswith("aviso_") and not re.search(r"acordo\s+colec?tivo", titulo):
                continue
            result.update({k: v for k, v in regra.items() if k in CAMPOS})
            result["regra_tipologia"] = regra["id"]
            break
    if result["tipo_acordo_base"]:
        for campo in ("titulo", "altera", "em_vigor"):
            match = RE_ACORDO.search(normalizar(entrada.get(campo, "")))
            if match:
                result["referencia_acordo_base"] = f"{int(match[1])}/{match[2]}"
                break
    if result["referencia_acordo_base"]:
        result["processo_irct"] = f"APU:{result['tipo_acordo_base']}:{result['referencia_acordo_base']}"
    elif entrada.get("cod_irct"):
        result["processo_irct"] = "DGERT:" + str(entrada["cod_irct"])
    else:
        result["processo_irct"] = ""
    return result


def enriquecer(entradas, regras=None):
    """Mantém referências externas quando a publicação de base não está no lote."""
    entradas = list(entradas)
    for entrada in entradas:
        entrada.update(classificar(entrada, regras))
        entrada["relacoes_documentais"] = []
    for entrada in entradas:
        if entrada["familia"] != "cessacao" and not (entrada.get("referencia_acordo_base")
                                                     and entrada.get("operacao_documental")):
            continue
        relacoes = []
        for ref in re.split(r"[;\n]", entrada.get("altera") or ""):
            if not ref.strip():
                continue
            match = RE_BTE.fullmatch(normalizar(ref).upper())
            targets = []
            if match:
                identificador = f"{int(match[3])}/{match[4]}"
                targets = [e for e in entradas if e is not entrada and e.get("id_dgert") == identificador
                           and normalizar(e.get("tipo", "")).upper() == match[1]]
            else:
                identificador = ""
                aviso = RE_AVISO.match(normalizar(ref.strip()))
                acordo = RE_ACORDO.search(normalizar(ref))
                if aviso:
                    for e in entradas:
                        publicado = RE_AVISO.match(normalizar(e.get("titulo", "")))
                        if e is not entrada and publicado and publicado.groups() == aviso.groups():
                            targets.append(e)
                elif acordo:
                    referencia = f"{int(acordo[1])}/{acordo[2]}"
                    targets = [e for e in entradas if e is not entrada
                               and e.get("referencia_acordo_base") == referencia
                               and e.get("tipo_acordo_base") == entrada.get("tipo_acordo_base")
                               and not e.get("operacao_documental")]
            relation = {"relacao": "cessa_vigencia_de" if entrada["familia"] == "cessacao" else
                        "delibera_sobre" if "DELI" in entrada["tipo_documental"] else "altera",
                        "referencia": ref.strip(), "origem": "DocAlteradosPorEste",
                        "id_publicacao": identificador,
                        "estado": "ligado" if len(targets) == 1 else "ambiguo" if targets else "fora_do_lote"}
            if len(targets) == 1:
                relation["alvo_chave"] = targets[0]["chave"]
            relacoes.append(relation)
        if entrada.get("referencia_acordo_base"):
            targets = [e for e in entradas if e is not entrada and e.get("processo_irct") == entrada["processo_irct"]
                       and e.get("operacao_documental") not in {"alteracao", "deliberacao_comissao_paritaria"}]
            relation = {"relacao": "acordo_base", "referencia": entrada["referencia_acordo_base"],
                        "processo_irct": entrada["processo_irct"], "origem": "metadados_indice",
                        "estado": "ligado" if len(targets) == 1 else "ambiguo" if targets else "fora_do_lote"}
            if len(targets) == 1:
                relation["alvo_chave"] = targets[0]["chave"]
            relacoes.append(relation)
        entrada["relacoes_documentais"] = relacoes
