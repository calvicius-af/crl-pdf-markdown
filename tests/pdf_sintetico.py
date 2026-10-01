"""PDF mínimos, escritos à mão, para testar os extratores de ponta a ponta.

Os PDF do BTE não estão no repositório. Sem eles, os testes do extrator
trabalhavam sobre texto já extraído, e um defeito na passagem PDF → texto (a
ordem de leitura, o mobiliário, a remoção de linhas) só aparecia na estação.
Estes PDF são pequenos, mas passam pelo pdfplumber e pelo PDFium como um PDF
real: cada linha tem uma posição na página.

Usa a fonte Helvetica (e a Times, numa linha com o modo `"times"`) com a
codificação WinAnsi, que cobre os acentos do
português. Uma linha com um quarto elemento `"rodado"` (ou `"rodado_horario"`)
é escrita a 90º, como as escalas laterais do TINITA e as tabelas dos
CARRISTUR, numa página que não declara rotação; `"quase_rodado"` também, mas
com a matriz desviada uns centésimos, como metade das páginas do TINITA de
2025; `"virado"` escreve-a a 180º,
como os esquemas das carreiras do CARRIS de 2025; `grelha()` desenha os traços
de uma tabela.
"""
from pathlib import Path

LARGURA, ALTURA = 595, 842          # A4, em pontos


def _escapar(texto: str) -> bytes:
    bruto = texto.encode("cp1252")
    return (bruto.replace(b"\\", b"\\\\").replace(b"(", b"\\(")
            .replace(b")", b"\\)"))


def _conteudo(linhas: list[tuple]) -> bytes:
    """Texto e traços. Um item ("traco", x0, y0, x1, y1) desenha uma linha;
    ("imagem", x, y, largura, altura), uma imagem cinzenta (uma tabela
    publicada como imagem, como as do INCM de 2025); ("recortado", x, y,
    texto, (x0, y0, x1, y1)), texto com uma área de recorte que não o
    contém, e que por isso não se vê (GESAMB de 2025)."""
    tracos = [b"0.5 w"]
    partes = [b"BT /F1 10 Tf"]
    blocos = []
    for item in linhas:
        if item[0] == "recortado":
            _, x, y, texto, (x0, y0, x1, y1) = item
            blocos.append(b"q %.1f %.1f %.1f %.1f re W n BT /F1 10 Tf 1 0 0 1 %.1f %.1f Tm ("
                          % (x0, y0, x1 - x0, y1 - y0, x, y) + _escapar(texto) + b") Tj ET Q")
            continue
        if item[0] == "imagem":
            _, x, y, w, h = item
            tracos.append(b"q %.1f 0 0 %.1f %.1f %.1f cm BI /W 1 /H 1 /CS /G /BPC 8 ID \x80 EI Q"
                          % (w, h, x, y))
            continue
        if item[0] == "traco":
            _, x0, y0, x1, y1 = item
            tracos.append(b"%.2f %.2f m %.2f %.2f l S" % (x0, y0, x1, y1))
            continue
        x, y, texto, *modo = item
        if modo and modo[0] == "times":
            partes.append(b"/F2 10 Tf 1 0 0 1 %.1f %.1f Tm (" % (x, y) + _escapar(texto)
                          + b") Tj /F1 10 Tf")
            continue
        matriz = {"rodado": b"0 1 -1 0", "rodado_horario": b"0 -1 1 0",
                  "quase_rodado": b"0.001 1 -1 0.001", "virado": b"-1 0 0 -1"}.get(
            modo[0] if modo else "", b"1 0 0 1")
        partes.append(matriz + b" %.1f %.1f Tm (" % (x, y) + _escapar(texto) + b") Tj")
    partes.append(b"ET")
    return b"\n".join(tracos + partes + blocos)


def grelha(x0: float, y0: float, larguras: list[float], alturas: list[float],
           desvio: float = 0.0) -> list[tuple]:
    """Traços de uma grelha com o canto inferior esquerdo em (x0, y0).

    Com `desvio`, cada traço fica torto por essa distância de uma ponta à
    outra, como os da grelha de uma página quase rodada (TINITA de 2025).
    """
    x1, y1 = x0 + sum(larguras), y0 + sum(alturas)
    tracos = []
    y = y0
    for h in [0.0, *alturas]:
        y += h
        tracos.append(("traco", x0, y, x1, y + desvio))
    x = x0
    for w in [0.0, *larguras]:
        x += w
        tracos.append(("traco", x, y0, x + desvio, y1))
    return tracos


def escrever_pdf(destino: Path, paginas: list[list[tuple]]) -> Path:
    """Escreve um PDF; cada página é uma lista de (x, y, texto), y a contar de baixo."""
    objetos: list[bytes] = []

    def novo(corpo: bytes) -> int:
        objetos.append(corpo)
        return len(objetos)

    catalogo = novo(b"")                     # preenchidos no fim
    arvore = novo(b"")
    times = novo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman "
                 b"/Encoding /WinAnsiEncoding >>")
    fonte = novo(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                 b"/Encoding /WinAnsiEncoding >>")
    folhas = []
    for linhas in paginas:
        conteudo = _conteudo(linhas)
        fluxo = novo(b"<< /Length %d >>\nstream\n" % len(conteudo) + conteudo
                     + b"\nendstream")
        folhas.append(novo(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] "
            b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> /Contents %d 0 R >>"
            % (arvore, LARGURA, ALTURA, fonte, times, fluxo)))
    objetos[catalogo - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % arvore
    objetos[arvore - 1] = (b"<< /Type /Pages /Kids [%s] /Count %d >>"
                           % (b" ".join(b"%d 0 R" % f for f in folhas), len(folhas)))

    saida = bytearray(b"%PDF-1.4\n")
    posicoes = []
    for n, corpo in enumerate(objetos, 1):
        posicoes.append(len(saida))
        saida += b"%d 0 obj\n" % n + corpo + b"\nendobj\n"
    xref = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    saida += b"".join(b"%010d 00000 n \n" % p for p in posicoes)
    saida += (b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objetos) + 1, catalogo, xref))
    Path(destino).write_bytes(bytes(saida))
    return Path(destino)


def pagina_bte(numero: int, corpo: list[str], bte: int = 31) -> list[tuple[float, float, str]]:
    """Página com o mobiliário do BTE: cabeçalho no topo, rodapé no fundo."""
    linhas = [(72, 800, f"Boletim do Trabalho e Emprego, n.º {bte}, 22/8/2026")]
    y = 760.0
    for texto in corpo:
        linhas.append((72, y, texto))
        y -= 14
    linhas.append((72, 40, f"BTE {bte} | {numero}"))
    return linhas
