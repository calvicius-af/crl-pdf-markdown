"""O mobiliário do BTE: o que se repete nas páginas e não é texto da convenção.

Definido num só sítio para o extrator (que o remove) e para a medição da
completude (que o tira da referência e o procura no texto). Os padrões vêm do
que as páginas do BTE de 2026 trazem, visto no corpus de regressão (corrida de
24-09-2026):

    Boletim do Trabalho e Emprego 31      ← cabeçalho, linha própria
    22 agosto 2026                        ← data do número, sem «de»
    BTE 31 | 34                           ← rodapé com a página
    BTE 31                                ← rodapé partido

e o formato antigo, numa só linha: «Boletim do Trabalho e Emprego, n.º 31,
22/8/2026». São linhas inteiras: uma frase do corpo que cite o boletim
(«publicado no Boletim do Trabalho e Emprego, n.º 21, …») não é mobiliário.
"""
import re

MESES = ("janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro"
         "|outubro|novembro|dezembro")

RE_CABECALHO = re.compile(
    r"^Boletim do Trabalho e Emprego,?\s*(?:n\.?\s*º\s*)?\d+"
    r"(?:,\s*\d{1,2}/\d{1,2}/\d{4})?$", re.IGNORECASE)
RE_DATA = re.compile(rf"^\d{{1,2}}\s+(?:{MESES})\s+\d{{4}}$", re.IGNORECASE)
# «BTE 31 | 34», «BTE 31» e, no BTE 38/2025, «BTE | 100» (sem o número do boletim)
RE_RODAPE = re.compile(r"^BTE(?:\s+\d+(?:\s*\|\s*\d+)?|\s*\|\s*\d+)$")
RE_NUMERO_PAGINA = re.compile(r"^\d{1,4}$")
# o rodapé partido pela leitura em colunas: «6 | 110», «BTE | 23» (corrida de
# 2025). Só nas margens da página: a meio, «6 | 110» pode ser conteúdo.
RE_RODAPE_PARTIDO = re.compile(r"^(?:BTE\s*)?\d{0,3}\s*\|\s*\d{1,4}$")

# O PDFium lê o cabeçalho e a data numa só linha e, nas páginas rodadas, cola-
# lhe o texto seguinte: «Boletim do Trabalho e Emprego 31 22 agosto 2026 Deve
# ler-se: …». No início de uma linha, esse prefixo é sempre mobiliário.
RE_PREFIXO_CABECALHO = re.compile(
    rf"^Boletim do Trabalho e Emprego\s+\d+(?:\s+\d{{1,2}}\s+(?:{MESES})\s+\d(?:\s?\d){{3}})?"
    r"(?=\s|$)\s*", re.IGNORECASE)

# O cabeçalho completo, com a data, a meio de uma linha: o PDFium cola-o ao fim
# da linha anterior nas páginas com formulários e tabelas largas («Reunião de
# avaliação Homologação da avaliação Boletim do Trabalho e Emprego 28 29 agosto
# 2025», corrida de 2025), e às vezes parte o ano («202 5»). Com a data, não se
# confunde com uma citação no corpo, que diz «n.º 21, de 8 de junho de 2025».
RE_CABECALHO_COM_DATA = re.compile(
    rf"\s*Boletim do Trabalho e Emprego\s+\d+\s+\d{{1,2}}\s+(?:{MESES})\s+\d(?:\s?\d){{3}}(?!\d)",
    re.IGNORECASE)

# o mesmo mobiliário colado a outro texto, depois de juntar linhas:
# «Boletim do Trabalho e Emprego 31 ANEX Categorias e gru», «1 | 139 Boletim …»
RE_COLADO = re.compile(
    r"Boletim do Trabalho e Emprego \d+(?![\d,])|\bBTE \d+ \| \d+\b")


def e_mobiliario(linha: str) -> bool:
    """Linha inteira de mobiliário, em qualquer sítio da página."""
    limpa = linha.strip()
    return bool(RE_CABECALHO.match(limpa) or RE_DATA.match(limpa)
                or RE_RODAPE.match(limpa))


def sem_prefixo_de_cabecalho(linha: str) -> str:
    """A linha sem o cabeçalho do BTE que a abra (pode ficar vazia)."""
    return RE_PREFIXO_CABECALHO.sub("", linha.strip(), count=1)


def sem_cabecalho_com_data(linha: str) -> tuple[str, list[str]]:
    """A linha sem o cabeçalho datado do BTE, onde quer que esteja, e o que saiu."""
    saem = [m.group(0).strip() for m in RE_CABECALHO_COM_DATA.finditer(linha)]
    if not saem:
        return linha, []
    return RE_CABECALHO_COM_DATA.sub(" ", linha).strip(), saem


def tem_mobiliario(linha: str) -> bool:
    """Linha com mobiliário, sozinho ou colado a texto (resíduo a assinalar)."""
    return e_mobiliario(linha) or bool(RE_COLADO.search(linha))
