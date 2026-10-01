"""Completude da extração: o texto que chega ao MaxQDA tem tudo o que o PDF tem?

Compara o texto extraído com uma leitura independente do mesmo PDF, feita pelo
PDFium (`pypdfium2`, que já vem instalado com o pdfplumber). Os dois motores
leem o PDF de formas diferentes, mas as palavras são as mesmas: o que o PDF tem
e o texto não tem é perda; o que o texto tem e o PDF não tem é lixo (palavras
invertidas, letras separadas, pedaços de palavras).

A comparação é por contagem de palavras, e não linha a linha, porque a ordem e
as quebras de linha diferem legitimamente entre motores. A ordem mede-se à
parte, e o mobiliário do BTE (cabeçalho, rodapé, número de página) sai da
referência antes de comparar, porque removê-lo é o comportamento esperado.

Nesta variante mede o Markdown final; não lê projetos QDPX.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .mobiliario import (RE_NUMERO_PAGINA, RE_RODAPE_PARTIDO, e_mobiliario, sem_cabecalho_com_data,
                         sem_prefixo_de_cabecalho, tem_mobiliario)

# ---------- limiares do veredicto (explicados no próprio diagnóstico) ----------

COBERTURA_OK = 0.995        # palavras do PDF presentes no texto
COBERTURA_FALHA = 0.97
EXCESSO_OK = 0.005          # palavras no texto que o PDF não tem
ORDEM_OK = 0.97             # palavras do PDF na mesma ordem no texto
LINHA_LONGA = 600           # caracteres: sinal de tabela colapsada numa linha
TRECHO_MINIMO = 4           # palavras seguidas para um trecho contar
TRECHOS = 12                # trechos mostrados por documento
TRECHO_MAXIMO = 300         # caracteres de cada trecho no relatório

RE_PALAVRA = re.compile(r"\w+")
MARGEM = 2
# O PDFium marca a hifenização de fim de linha com U+FFFE e cola-lhe a linha
# seguinte («pro\ufffeposta»), às vezes o próprio rodapé («pro\ufffeBTE 31 | 34»).
HIFEN_PDFIUM = "\ufffe"
RE_HIFEN_FIM = re.compile(r"[-\x02\xad\ufffe]\n(?=[a-zà-ÿ])")
# Uma palavra invertida tem a maiúscula no fim: «sagloF», «ocincéT», «levíN».
RE_INVERTIDA = re.compile(r"^[a-zà-ÿ]{2,}[A-ZÀ-Ý]$")
# Uma página em que o PDFium lê menos de metade dos caracteres que o pdfplumber
# vê não serve de referência (sucede nas tabelas rodadas dos CARRISTUR).
PDFIUM_CEGO = 0.5


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto.replace("\r\n", "\n").replace("\r", "\n"))
    # o hífen do PDFium passa a fim de linha, para o mobiliário que vem colado
    # a ele ficar numa linha própria e a junção se fazer como no extrator
    return texto.replace(HIFEN_PDFIUM, HIFEN_PDFIUM + "\n").replace(
        HIFEN_PDFIUM + "\n\n", HIFEN_PDFIUM + "\n")


def _juntar_hifenizacao(texto: str) -> str:
    return RE_HIFEN_FIM.sub("", texto).replace(HIFEN_PDFIUM, "-")


def _sobretudo_numeros(texto: str) -> bool:
    tokens = texto.split()
    numeros = sum(1 for t in tokens if any(c.isdigit() for c in t))
    return bool(tokens) and numeros / len(tokens) > 0.4


def _parece_tabela(linha: str) -> bool:
    """Uma linha longa só é sinal de tabela colapsada se tiver células ou for
    sobretudo números: um parágrafo de 800 caracteres é normal numa cláusula."""
    return " | " in linha or _sobretudo_numeros(linha)


# uma célula de texto corrido: a descrição de funções de uma categoria, a lista
# de concelhos de uma zona. Tem palavras, e não números.
MIN_PALAVRAS_PROSA = 10


def _linha_de_tabela_inteira(linha: str, vizinhas: list[str]) -> bool:
    """Uma linha longa com células que é uma linha da tabela, e não a tabela toda.

    Na corrida de 2025, 177 das «linhas longas» (CARRIS, RTP, INOVA, LAGOS em
    Forma) eram linhas certas: o conteúdo funcional de uma categoria numa
    célula, ou o cabeçalho de uma grelha de 36 colunas. Uma tabela colapsada
    tem as células de várias linhas numa só; uma linha inteira tem as mesmas
    células que a linha ao lado, ou é longa só por uma célula de texto.
    """
    celulas = linha.split(" | ")
    if any(v.count(" | ") + 1 == len(celulas) for v in vizinhas if " | " in v):
        return True
    curtas = [c for c in celulas
              if len(c.split()) < MIN_PALAVRAS_PROSA or _sobretudo_numeros(c)]
    return len(" | ".join(curtas)) <= LINHA_LONGA


def invertidas_pela_forma(texto: str) -> list[str]:
    """Palavras com a maiúscula no fim («sagloF»): texto rodado lido ao contrário."""
    return [p for p in RE_PALAVRA.findall(texto) if len(p) >= 4 and RE_INVERTIDA.match(p)]


def palavras(texto: str) -> list[str]:
    """As palavras, com as formas de compatibilidade unificadas (ligaduras
    como «ﬁ», que um motor dá e o outro não)."""
    return [unicodedata.normalize("NFKC", p) for p in RE_PALAVRA.findall(texto)]


def paginas_de_referencia(pdf: Path) -> list[str]:
    """Texto de cada página, lido pelo PDFium."""
    return ler_referencia(pdf)[0]


def ler_referencia(pdf: Path) -> tuple[list[str], list[int]]:
    """Texto de cada página e as páginas em que o PDFium não serve.

    Nessas páginas (o PDFium lê menos de metade dos caracteres que o pdfplumber
    vê), a referência passa a ser o pdfplumber, com o texto rodado lido no
    sentido certo. A comparação aí deixa de ser independente, e o diagnóstico
    di-lo; mas as palavras invertidas continuam a ser apanhadas pela forma.
    """
    import pdfplumber
    import pypdfium2 as pdfium

    from .extractor import normalizar_pagina
    from .recorte import letras_escondidas, texto_visivel, tirar_escondidas

    documento = pdfium.PdfDocument(str(pdf))
    paginas, cegas = [], []
    try:
        with pdfplumber.open(pdf) as plumber:
            for i in range(len(documento)):
                pp = plumber.pages[i]
                pagina = documento[i]
                try:
                    # só o que se vê: nem o texto recortado nem o que fica
                    # fora da página, que o extrator também não lê. Dos dois
                    # lados: comparar o PDFium visível com todas as letras do
                    # pdfplumber dava a página como cega (MaiaAmbiente, p28)
                    texto = _normalizar(texto_visivel(pagina))
                    tirar_escondidas(pp, letras_escondidas(pagina))
                finally:
                    pagina.close()
                normalizar_pagina(pp)
                vistos = sum(1 for c in pp.chars if c["text"].strip())
                lidos = sum(1 for c in texto if not c.isspace())
                if vistos and lidos < PDFIUM_CEGO * vistos:
                    cegas.append(i + 1)
                    texto = _normalizar(pp.extract_text(
                        line_dir_rotated="ltr", char_dir_rotated="btt") or "")
                paginas.append(texto)
    finally:
        documento.close()
    return paginas, cegas


def sem_mobiliario(pagina: str) -> tuple[str, list[str]]:
    """A página sem as linhas de mobiliário, e as linhas retiradas."""
    linhas = pagina.split("\n")
    cheias = [i for i, l in enumerate(linhas) if l.strip()]
    margens = set(cheias[:MARGEM] + cheias[-MARGEM:])
    ficam: list[str] = []
    saem: list[str] = []
    for i, linha in enumerate(linhas):
        limpa = linha.strip()
        mobiliario = (e_mobiliario(limpa)
                      or (i in margens and (RE_NUMERO_PAGINA.match(limpa)
                                            or RE_RODAPE_PARTIDO.match(limpa))))
        if mobiliario:
            saem.append(linha)
            continue
        resto = sem_prefixo_de_cabecalho(limpa)
        if resto != limpa:
            saem.append(limpa[:len(limpa) - len(resto)])
            linha = resto
        resto, colados = sem_cabecalho_com_data(linha)
        if colados:
            saem.extend(colados)
            linha = resto
        if linha.strip() or not limpa:
            ficam.append(linha)
    return "\n".join(ficam), [l.strip() for l in saem if l.strip()]


def _juntar_paginas(limpas: list[str]) -> list[str]:
    """Junta a palavra partida entre duas páginas na página onde começa."""
    limpas = [l.rstrip() for l in limpas]
    for i in range(len(limpas) - 1):
        if limpas[i].endswith(("-", HIFEN_PDFIUM)):
            seguinte = limpas[i + 1].lstrip()
            m = re.match(r"[a-zà-ÿ]\w*", seguinte)
            if m:
                limpas[i] = limpas[i][:-1] + m.group(0)
                limpas[i + 1] = seguinte[m.end():]
    return [_juntar_hifenizacao(l) for l in limpas]


@dataclass
class Medida:
    documento: str
    paginas: int = 0
    palavras_pdf: int = 0
    palavras_texto: int = 0
    em_falta: Counter = field(default_factory=Counter)
    a_mais: Counter = field(default_factory=Counter)
    ordem: float = 1.0
    perda_por_pagina: list[tuple[int, float]] = field(default_factory=list)
    invertidas: list[tuple[str, str]] = field(default_factory=list)
    # trechos contínuos: (página, no PDF, no texto em vez dele); e os do texto
    # que o PDF não tem. Mostram o que se perdeu, e não só palavras soltas.
    trechos_falta: list[tuple[int, str, str]] = field(default_factory=list)
    trechos_mais: list[str] = field(default_factory=list)
    # páginas em que a referência veio do pdfplumber (o PDFium não as lê)
    paginas_cegas: list[int] = field(default_factory=list)
    # (parágrafo, conteúdo): o parágrafo conta só as linhas não vazias, como
    # a numeração que o MAXQDA mostra ao lado do texto
    residuos: list[tuple[int, str]] = field(default_factory=list)
    linhas_longas: list[tuple[int, int]] = field(default_factory=list)
    caracteres: dict[str, tuple[int, int]] = field(default_factory=dict)
    contexto_falta: dict[str, str] = field(default_factory=dict)
    contexto_mais: dict[str, str] = field(default_factory=dict)
    erro: str | None = None
    # a extração correu, mas o documento ficou fora do QDPX (erro depois da
    # medida). Sem isto, os 39 documentos perdidos na corrida de 2025
    # apareciam como OK no diagnóstico.
    excluido: str | None = None
    # as palavras do PDF, sem o mobiliário, pela ordem da referência: a
    # sanidade vê nelas o que o PDF tem entre o fim de um corpo e o cabeçalho
    # seguinte (cct/sanidade.py, `clausulas_sem_corpo`)
    palavras_referencia: list[str] = field(default_factory=list)

    @property
    def cobertura(self) -> float:
        if not self.palavras_pdf:
            return 1.0
        return 1 - sum(self.em_falta.values()) / self.palavras_pdf

    @property
    def excesso(self) -> float:
        if not self.palavras_texto:
            return 0.0
        return sum(self.a_mais.values()) / self.palavras_texto

    @property
    def veredicto(self) -> str:
        if self.excluido:
            return "EXCLUÍDO"
        if self.erro:
            return "SEM MEDIDA"
        if self.cobertura < COBERTURA_FALHA or len(self.invertidas) >= 5:
            return "FALHA"
        if (self.cobertura < COBERTURA_OK or self.excesso > EXCESSO_OK
                or self.ordem < ORDEM_OK or self.invertidas or self.residuos
                or self.linhas_longas):
            return "ATENÇÃO"
        return "OK"


def _contexto(texto: str, palavra: str, largura: int = 70) -> str:
    m = re.search(rf"(?<!\w){re.escape(palavra)}(?!\w)", texto)
    if not m:
        return ""
    ini, fim = max(0, m.start() - largura), min(len(texto), m.end() + largura)
    trecho = texto[ini:fim].replace("\n", " ⏎ ")
    return ("…" if ini else "") + trecho + ("…" if fim < len(texto) else "")


def medir(documento: str, paginas_pdf: list[str], texto: str) -> Medida:
    """Compara as páginas lidas do PDF com o texto extraído."""
    m = Medida(documento, paginas=len(paginas_pdf))
    limpas = _juntar_paginas(
        [sem_mobiliario(_normalizar(pagina))[0] for pagina in paginas_pdf])
    referencia = "\n".join(limpas)
    texto = _juntar_hifenizacao(_normalizar(texto))

    ref_palavras = palavras(referencia)
    m.palavras_referencia = ref_palavras
    txt_palavras = palavras(texto)
    m.palavras_pdf, m.palavras_texto = len(ref_palavras), len(txt_palavras)
    ref, txt = Counter(ref_palavras), Counter(txt_palavras)
    m.em_falta, m.a_mais = ref - txt, txt - ref

    # onde está a perda: cada página consome as palavras que encontra no texto
    disponiveis = Counter(txt)
    for n, limpa in enumerate(limpas, 1):
        da_pagina = palavras(limpa)
        if not da_pagina:
            continue
        achadas = 0
        for p in da_pagina:
            if disponiveis[p] > 0:
                disponiveis[p] -= 1
                achadas += 1
        perda = 1 - achadas / len(da_pagina)
        if perda > 0:
            m.perda_por_pagina.append((n, perda))

    if ref_palavras and txt_palavras:
        comparador = difflib.SequenceMatcher(
            None, ref_palavras, txt_palavras, autojunk=False)
        m.ordem = sum(b.size for b in comparador.get_matching_blocks()) / len(ref_palavras)
        pagina_de = [n for n, limpa in enumerate(limpas, 1) for _ in palavras(limpa)]
        falta, mais = [], []
        for tag, i1, i2, j1, j2 in comparador.get_opcodes():
            if tag in ("delete", "replace") and i2 - i1 >= TRECHO_MINIMO:
                falta.append((i2 - i1, pagina_de[i1], " ".join(ref_palavras[i1:i2]),
                              " ".join(txt_palavras[j1:j2])))
            if tag in ("insert", "replace") and j2 - j1 >= TRECHO_MINIMO:
                mais.append((j2 - j1, " ".join(txt_palavras[j1:j2])))
        m.trechos_falta = [(pg, a, b) for _, pg, a, b in
                           sorted(falta, key=lambda x: -x[0])[:TRECHOS]]
        m.trechos_mais = [t for _, t in sorted(mais, key=lambda x: -x[0])[:TRECHOS]]

    # invertidas: o par exato quando a referência tem a palavra certa, e a
    # forma (maiúscula no fim) quando não tem, como nas páginas cegas
    m.invertidas = sorted(
        (p, p[::-1]) for p in m.a_mais
        if len(p) >= 4 and (p[::-1] in m.em_falta or RE_INVERTIDA.match(p)))
    paragrafos = [l.strip() for l in texto.split("\n") if l.strip()]
    for n, linha in enumerate(paragrafos, 1):
        if tem_mobiliario(linha):
            m.residuos.append((n, linha))
        if len(linha) > LINHA_LONGA and _parece_tabela(linha):
            vizinhas = paragrafos[max(0, n - 2):n - 1] + paragrafos[n:n + 1]
            if " | " in linha and _linha_de_tabela_inteira(linha, vizinhas):
                continue
            m.linhas_longas.append((n, len(linha)))

    def classes(t: str) -> dict[str, int]:
        return {"letras": sum(c.isalpha() for c in t),
                "dígitos": sum(c.isdigit() for c in t),
                "vírgulas": t.count(","), "pontos": t.count("."),
                "a": t.lower().count("a")}
    c_ref, c_txt = classes(referencia), classes(texto)
    m.caracteres = {k: (c_ref[k], c_txt[k]) for k in c_ref}

    for p, _ in m.em_falta.most_common(25):
        m.contexto_falta[p] = _contexto(referencia, p)
    for p, _ in m.a_mais.most_common(25):
        m.contexto_mais[p] = _contexto(texto, p)
    return m


def medir_pdf(documento: str, pdf: Path, texto: str) -> Medida:
    """Como `medir`, mas nunca rebenta: um PDF ilegível dá SEM MEDIDA."""
    try:
        paginas, cegas = ler_referencia(pdf)
        m = medir(documento, paginas, texto)
        m.paginas_cegas = cegas
        return m
    except Exception as e:                       # o diagnóstico nunca custa a corrida
        return Medida(documento, erro=f"{type(e).__name__}: {e}")


# ---------- o relatório único ----------

def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def diagnostico(medidas: list[Medida], manifesto: dict | None = None,
                relatorio: str = "", extras: dict[str, str] | None = None) -> str:
    """Markdown com tudo o que é preciso para diagnosticar a corrida."""
    manifesto = manifesto or {}
    ambiente = manifesto.get("environment", {})
    parametros = manifesto.get("parameters", {})
    resumo = manifesto.get("summary", {})
    contagem = Counter(m.veredicto for m in medidas)

    linhas = ["# Diagnóstico da corrida", ""]
    linhas += [
        f"Início: {manifesto.get('started_at_utc', '?')} (UTC). "
        f"Aplicação {ambiente.get('app_version', '?')}, "
        f"Python {ambiente.get('python', '?')}, {ambiente.get('platform', '?')}.",
        f"Commit: {(ambiente.get('git') or {}).get('commit') or 'desconhecido'}. "
        f"Extrator: {parametros.get('extrator', '?')}.",
        f"Comando: `{' '.join(manifesto.get('command', []))}`",
        "",
        f"Documentos: {len(medidas)}. OK: {contagem['OK']}. "
        f"Atenção: {contagem['ATENÇÃO']}. Falha: {contagem['FALHA']}. "
        f"Sem medida: {contagem['SEM MEDIDA']}. "
        + (f"**Fora do QDPX: {contagem['EXCLUÍDO']}.** " if contagem["EXCLUÍDO"] else "")
        + f"Cláusulas: {resumo.get('clausulas', '?')}. "
        f"Anotações: {resumo.get('anotacoes', '?')}.",
        "",
        "## Resumo por documento",
        "",
        "| Documento | Veredicto | Cobertura | Em falta | A mais | Ordem "
        "| Invertidas | Mobiliário | Linhas longas |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in medidas:
        if m.erro or m.excluido:
            linhas.append(f"| {m.documento} | {m.veredicto} | | | | | | | |")
            continue
        linhas.append(
            f"| {m.documento} | {m.veredicto} | {_pct(m.cobertura)} "
            f"| {sum(m.em_falta.values())} | {sum(m.a_mais.values())} "
            f"| {_pct(m.ordem)} | {len(m.invertidas)} | {len(m.residuos)} "
            f"| {len(m.linhas_longas)} |")

    linhas += ["", "## Como ler", "",
               "1. **Cobertura:** palavras do PDF (sem cabeçalho, rodapé e número "
               "de página) que estão no texto. OK a partir de "
               f"{_pct(COBERTURA_OK)}; falha abaixo de {_pct(COBERTURA_FALHA)}.",
               "2. **A mais:** palavras do texto que o PDF não tem: letras "
               "separadas, palavras invertidas ou partidas.",
               "3. **Ordem:** palavras do PDF que aparecem pela mesma ordem no "
               f"texto. Abaixo de {_pct(ORDEM_OK)} há blocos trocados (colunas, "
               "tabelas).",
               "4. **Mobiliário:** linhas de cabeçalho ou rodapé do BTE que "
               "ficaram no texto.",
               f"5. **Linhas longas:** linhas com mais de {LINHA_LONGA} "
               "caracteres com células « | » ou sobretudo números: uma tabela "
               "colapsada. Parágrafos longos de texto não contam, nem uma linha "
               "com as mesmas células que a do lado ou longa só por uma célula "
               "de texto.",
               "6. A referência é a leitura do PDFium, outro motor. Uma "
               "diferença pode vir dele; o contexto de cada palavra permite "
               "decidir.", ""]

    if relatorio.strip():
        linhas += ["## Relatório da corrida", "", "```", relatorio.strip(), "```", ""]

    linhas += ["## Detalhe por documento", ""]
    for m in medidas:
        linhas.append(f"### {m.documento}: {m.veredicto}")
        linhas.append("")
        if m.excluido:
            linhas += [f"Extraído, mas fora do QDPX: {m.excluido}", ""]
            continue
        if m.erro:
            linhas += [f"Não foi possível ler o PDF: {m.erro}", ""]
            continue
        linhas.append(
            f"{m.paginas} páginas; {m.palavras_pdf} palavras no PDF e "
            f"{m.palavras_texto} no texto.")
        cls = "; ".join(f"{k}: {a} no PDF, {b} no texto" for k, (a, b) in m.caracteres.items())
        linhas += ["", f"Caracteres: {cls}.", ""]
        if m.paginas_cegas:
            linhas += ["O PDFium não lê o texto das páginas " + ", ".join(
                f"p{n}" for n in m.paginas_cegas) + "; aí a referência é o "
                "pdfplumber e a comparação não é independente.", ""]
        if m.veredicto == "OK":
            continue
        piores = sorted(m.perda_por_pagina, key=lambda x: -x[1])[:8]
        if piores:
            linhas.append("Páginas com perda: " + ", ".join(
                f"p{n} ({_pct(p)})" for n, p in piores) + ".")
            linhas.append("")
        if m.invertidas:
            linhas.append("Palavras invertidas: " + ", ".join(
                f"`{a}` (é `{b}`)" for a, b in m.invertidas[:15]) + ".")
            linhas.append("")
        if m.residuos:
            linhas.append("Mobiliário no texto (parágrafo no MAXQDA):")
            linhas += [f"{i}. parágrafo {n}: `{r}`"
                       for i, (n, r) in enumerate(m.residuos[:10], 1)]
            linhas.append("")
        if m.linhas_longas:
            linhas += ["Linhas longas (parágrafo no MAXQDA): " + ", ".join(
                f"{n} ({c} caracteres)" for n, c in m.linhas_longas[:10]) + ".", ""]
        if m.trechos_falta:
            linhas += ["Trechos do PDF que faltam no texto (ou que aparecem "
                       "noutra ordem), por tamanho:", ""]
            for i, (pg, trecho, em_vez) in enumerate(m.trechos_falta, 1):
                linhas.append(f"{i}. p{pg}: «{trecho[:TRECHO_MAXIMO]}»"
                              + (f" → no texto: «{em_vez[:TRECHO_MAXIMO]}»" if em_vez else ""))
            linhas.append("")
        if m.trechos_mais:
            linhas += ["Trechos do texto que o PDF não tem nesse sítio:", ""]
            linhas += [f"{i}. «{t[:TRECHO_MAXIMO]}»" for i, t in enumerate(m.trechos_mais, 1)]
            linhas.append("")
        for titulo, contagem_p, contextos in (
                ("Em falta no texto (contexto no PDF)", m.em_falta, m.contexto_falta),
                ("A mais no texto (contexto no texto)", m.a_mais, m.contexto_mais)):
            if not contagem_p:
                continue
            linhas += [f"{titulo}:", "", "| Palavra | Vezes | Contexto |", "|---|---|---|"]
            for p, n in contagem_p.most_common(25):
                ctx = contextos.get(p, "").replace("|", "¦")
                linhas.append(f"| `{p}` | {n} | {ctx} |")
            linhas.append("")

    for titulo, conteudo in (extras or {}).items():
        if conteudo.strip():
            linhas += [f"## {titulo}", "", "```", conteudo.strip(), "```", ""]
    return "\n".join(linhas) + "\n"


# ---------- sobre uma corrida já feita ----------

