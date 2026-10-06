"""Preparação de documentos Markdown para análise qualitativa."""

__version__ = "0.2.0"


def utf8_output():
    """Escreve a saída da linha de comandos em UTF-8.

    Em Windows, quando a saída não vai para a consola (pipe, ficheiro, CI), o
    Python usa a página de código local, cp1252, que não tem carateres como
    «→» e interrompe o comando com UnicodeEncodeError (no crl-app-cct, #37).
    """
    import sys

    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding != "utf8" and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
