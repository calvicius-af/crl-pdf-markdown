"""Página do PDF como imagem PNG, para mostrar ao lado do Markdown na revisão.

Usa o PDFium (pypdfium2), já instalado com o Docling e o pdfplumber. O Tk 8.6
lê PNG diretamente, por isso não é preciso o módulo ImageTk do Pillow.
"""

import tempfile
from pathlib import Path


def page_count(pdf) -> int:
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument(str(pdf))
    try:
        return len(document)
    finally:
        document.close()


def render_page(pdf, page_no: int, width: int = 800, folder=None) -> Path:
    """Desenha a página (numerada a partir de 1) com a largura pedida, em píxeis."""
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument(str(pdf))
    try:
        if not 1 <= page_no <= len(document):
            raise ValueError(f'Página {page_no} inexistente; o PDF tem {len(document)} páginas.')
        page = document[page_no - 1]
        try:
            scale = max(.5, min(4.0, width / page.get_width()))
            image = page.render(scale=scale).to_pil()
        finally:
            page.close()
    finally:
        document.close()
    folder = Path(folder) if folder else Path(tempfile.mkdtemp(prefix='crl-pagina-'))
    target = folder / f'pagina-{page_no}.png'
    image.save(target, format='PNG')
    return target
