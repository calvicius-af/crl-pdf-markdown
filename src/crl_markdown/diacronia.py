"""Comparação diacrónica: versão actual de uma convenção face à versão completa anterior.

Porta o comparador do AppCCT (`cct/diacronia.py`) com três mudanças, medidas nos
pares BRISA (41/2024 para 16/2026) e ANIPC (29/2023 para 191/2026):

1. `=` exige texto igual depois da normalização simples. O limiar de 0,995 do
   AppCCT deixava passar como igual a troca de um valor numa cláusula longa
   (três caracteres em mil), que é o que mais interessa numa revisão salarial.
2. Classe `alteracao_formal`: o texto só difere no espaçamento dos marcadores
   («1-» e «1 -», «a)» e «a) »), nas aspas e travessões, ou na grafia anterior
   ao Acordo Ortográfico («respectivo» e «respetivo»). No ANIPC eram 20 das 28
   «alterações».
3. Diferenças por palavra, com contexto curto, em vez de linhas inteiras.

Os limiares de emparelhamento (0,5, 0,75 e 0,8) mantêm-se, para que os pares
encontrados sejam os mesmos do AppCCT.
"""

import difflib
import re
import unicodedata

from .legacy.numeracao import chave_numero

LIMIAR_RENUMERACAO = 0.75
# um par pelo número só é aceite se o conteúdo for minimamente parecido;
# senão trata-se de renumeração (outra cláusula ocupa aquele número)
LIMIAR_MESMO_NUMERO = 0.5
LIMIAR_TITULO = 0.8
LIMITES = {"renumeracao": LIMIAR_RENUMERACAO, "mesmo_numero": LIMIAR_MESMO_NUMERO,
           "titulo": LIMIAR_TITULO}
TIPOS = ("clausula", "artigo", "anexo")
CLASSES = ("=", "alteracao_formal", "alteracao", "nova", "removida")

# Grafias anteriores ao Acordo Ortográfico, já sem acentos e em minúsculas.
# Aplicam-se aos dois textos: juntar por engano duas palavras distintas só
# acontece se ambas existirem com o mesmo radical, o que não ocorre nesta lista.
GRAFIAS = (
    ("accao", "acao"), ("accoes", "acoes"), ("ccao", "cao"), ("ccoes", "coes"),
    ("pcao", "cao"), ("pcoes", "coes"),
    ("activ", "ativ"), ("actual", "atual"), ("actu", "atu"), ("efectiv", "efetiv"),
    ("colectiv", "coletiv"), ("objectiv", "objetiv"), ("respectiv", "respetiv"),
    ("selectiv", "seletiv"), ("direct", "diret"), ("nocturn", "noturn"),
    ("electr", "eletr"), ("project", "projet"), ("afect", "afet"), ("exact", "exat"),
    ("correct", "corret"), ("inspect", "inspet"), ("protect", "protet"),
    ("infract", "infrat"), ("sector", "setor"), ("adopt", "adot"), ("optim", "otim"),
    ("excepc", "excec"), ("except", "excet"), ("recepc", "recec"), ("concepc", "concec"),
    ("percepc", "percec"), ("baptism", "batism"), ("efectu", "efetu"), ("lectiv", "letiv"),
)
# Radicais que só se trocam no início da palavra («acto», mas não «contacto»).
GRAFIAS_INICIO = (("acto", "ato"), ("rect", "ret"))
_RE_GRAFIAS = re.compile("|".join(sorted((re.escape(a) for a, _ in GRAFIAS),
                                         key=len, reverse=True)))
_GRAFIAS = dict(GRAFIAS)
_RE_GRAFIAS_INICIO = re.compile(r"\b(" + "|".join(a for a, _ in GRAFIAS_INICIO) + ")")
_GRAFIAS_INICIO = dict(GRAFIAS_INICIO)


def _sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def normalizar(texto: str) -> str:
    """Sem acentos, em minúsculas e com espaços simples (a semelhança do AppCCT)."""
    return re.sub(r"\s+", " ", _sem_acentos(texto).lower()).strip()


def normalizar_formal(texto: str) -> str:
    """Como `normalizar`, sem as diferenças que não mudam o conteúdo."""
    t = normalizar(texto)
    t = re.sub(r"[«»“”„\"']", '"', t)
    t = re.sub(r"[‐‑‒–—―]", "-", t)
    t = t.replace("×", "x")
    t = re.sub(r"\.{3,}", " ", t)                        # pontos de preenchimento
    t = _RE_GRAFIAS.sub(lambda m: _GRAFIAS[m.group(0)], t)
    t = _RE_GRAFIAS_INICIO.sub(lambda m: _GRAFIAS_INICIO[m.group(1)], t)
    t = re.sub(r"\s*([,;:.!?)\]])", r"\1", t)          # sem espaço antes da pontuação
    t = re.sub(r"([(\[])\s*", r"\1", t)
    t = re.sub(r"(\d+(?:\.\d+)*)\s*-\s*", r"\1- ", t)    # «1 -», «1-» e «1- »
    t = re.sub(r"(?<![\w])([a-z]{1,2})\)\s*", r"\1) ", t)  # «a)» e «a) »
    t = re.sub(r"(\d)\s+(?=\d{3}\b)", r"\1", t)          # «1 200» e «1200»
    return re.sub(r"\s+", " ", t).strip()


def chave_formal(texto: str) -> str:
    """Para decidir se a diferença é só formal: sem pontuação (excepto entre algarismos),
    sem espaços e sem translineações («me- dica», «pre- -determinados», «recusar -se»)."""
    t = normalizar_formal(texto)
    t = re.sub(r"(?:^|(?<=\s))-(?=\s|$)", "", t)          # travessões de enumeração
    t = re.sub(r"(?<!\d)[,;:.!?](?!\d)|[,;:.!?](?=\s|$)", "", t)
    t = re.sub(r"([a-z])\s*-\s*-?\s*(?=[a-z])", r"\1", t)
    return re.sub(r"\s+", "", t)


def semelhanca(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalizar(a), normalizar(b), autojunk=False).ratio()


def _numeros(texto: str) -> list[str]:
    return re.findall(r"\d+(?:[.,]\d+)*", re.sub(r"(\d)\s+(?=\d{3}\b)", r"\1", texto))


def diferencas(anterior: str, novo: str, contexto: int = 6) -> str:
    """Diferenças palavra a palavra: `[-retirado-]` e `{+acrescentado+}`, com contexto."""
    a, b = anterior.split(), novo.split()
    partes = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        antes = " ".join(a[max(0, i1 - contexto):i1])
        depois = " ".join(a[i2:i2 + contexto])
        mudanca = []
        if i2 > i1:
            mudanca.append("[-" + " ".join(a[i1:i2]) + "-]")
        if j2 > j1:
            mudanca.append("{+" + " ".join(b[j1:j2]) + "+}")
        partes.append(" ".join(p for p in ("…" + antes if antes else "", *mudanca,
                                              depois + "…" if depois else "") if p))
    return "\n".join(partes)


def chave(no: dict) -> str | None:
    """`cl12` para «Cláusula 12.ª» e para «Cláusula décima segunda»; `anexoii` para «Anexo II»."""
    if no["tipo"] == "anexo":
        m = re.match(r"\s*anexo\s+([ivxlcdm]+|\d+|[a-z])\b", normalizar(no["rotulo"]))
        return f"anexo{m.group(1)}" if m else None
    return chave_numero(no["rotulo"])


def _titulo(no: dict) -> str:
    partes = re.split(r"\s+[-–—]\s+", no["rotulo"], maxsplit=1)
    return normalizar(partes[1]) if len(partes) > 1 else ""


def corpo(no: dict, texto: str) -> str:
    """Texto do nó sem a linha do rótulo (títulos mudam sem ser alteração)."""
    trecho = texto[no["char_start"]:no["char_end"]]
    linhas = trecho.split("\n", 1)
    return (linhas[1] if len(linhas) > 1 else linhas[0]).strip()


def unidades(nos: list[dict]) -> list[dict]:
    """Cláusulas, artigos e anexos terminais; numa publicação com texto
    consolidado, só a republicação (o texto integral final)."""
    todas = [n for n in nos if n["tipo"] in TIPOS and n.get("folha", True)]
    consolidadas = [n for n in todas if n.get("origem") == "consolidado"]
    return consolidadas if len(consolidadas) >= len(todas) * 0.5 and consolidadas else todas


def comparar(anterior: dict, novo: dict) -> dict:
    """Compara duas versões. Cada uma é `{"doc_id", "nos", "texto"}`."""
    antigas, novas = unidades(anterior["nos"]), unidades(novo["nos"])
    txt_a, txt_n = anterior["texto"], novo["texto"]
    por_chave: dict[str, list[dict]] = {}
    for n in antigas:
        ch = chave(n)
        if ch:
            por_chave.setdefault(ch, []).append(n)
    usadas: set[str] = set()
    linhas: list[dict] = []

    def linha(no_n, no_a, classe, sem, renumerada=False):
        ca = corpo(no_a, txt_a) if no_a else ""
        cn = corpo(no_n, txt_n) if no_n else ""
        numeros = classe in ("alteracao", "alteracao_formal") and _numeros(ca) != _numeros(cn)
        linhas.append({
            "tipo": (no_n or no_a)["tipo"],
            "rotulo_novo": no_n["rotulo"] if no_n else "",
            "rotulo_anterior": no_a["rotulo"] if no_a else "",
            "classificacao": classe, "semelhanca": round(sem, 3),
            "renumerada": renumerada, "numeros_alterados": numeros,
            "diferencas": diferencas(ca, cn) if classe in ("alteracao", "alteracao_formal") else "",
            "texto_anterior": ca, "texto_novo": cn,
        })
        if no_a:
            usadas.add(no_a["id"])

    def classificar(no_n, no_a, sem, renumerada=False):
        ca, cn = corpo(no_a, txt_a), corpo(no_n, txt_n)
        if normalizar(ca) == normalizar(cn):
            classe = "="
        elif chave_formal(ca) == chave_formal(cn):
            classe = "alteracao_formal"
        else:
            classe = "alteracao"
        linha(no_n, no_a, classe, sem, renumerada)

    # 1.ª passagem: pelo número, mas só se o conteúdo ou o título o corroborar
    # (cláusulas muito reescritas mantêm número e título)
    pendentes = []
    for no in novas:
        ch = chave(no)
        candidatos = [a for a in por_chave.get(ch, []) if a["id"] not in usadas] if ch else []
        if candidatos:
            cand = candidatos[0]
            sem = semelhanca(corpo(cand, txt_a), corpo(no, txt_n))
            titulos = bool(_titulo(no)) and difflib.SequenceMatcher(
                None, _titulo(no), _titulo(cand)).ratio() >= LIMIAR_TITULO
            if sem >= LIMIAR_MESMO_NUMERO or titulos:
                classificar(no, cand, sem)
                continue
        pendentes.append(no)

    # 2.ª passagem: renumerações, por semelhança de conteúdo (mesmo tipo)
    for no in pendentes:
        cn = corpo(no, txt_n)
        melhor, melhor_sem = None, 0.0
        for a in antigas:
            if a["id"] in usadas or a["tipo"] != no["tipo"]:
                continue
            sem = semelhanca(corpo(a, txt_a), cn)
            if sem > melhor_sem:
                melhor, melhor_sem = a, sem
        if melhor is not None and melhor_sem >= LIMIAR_RENUMERACAO:
            classificar(no, melhor, melhor_sem, renumerada=True)
        else:
            linha(no, None, "nova", 0.0)

    for a in antigas:
        if a["id"] not in usadas:
            linha(None, a, "removida", 0.0)

    resumo = {c: 0 for c in CLASSES}
    for r in linhas:
        resumo[r["classificacao"]] += 1
    return {"linhas": linhas, "resumo": resumo,
            "doc_anterior": anterior["doc_id"], "doc_novo": novo["doc_id"],
            "unidades": {"anterior": len(antigas), "novo": len(novas)}}
