"""Limites dos PDF que entram na extração, verificados antes de a começar (#25).

Um PDF é um input complexo, e o que custa caro tem de falhar cedo e com uma
mensagem que diga o que fazer: um ficheiro corrompido, protegido por
palavra-passe, grande de mais ou com páginas a mais. Verifica-se com o PDFium,
que abre o ficheiro sem o interpretar todo, antes de qualquer extrator (o
pdfplumber ou o docling, que carrega modelos e pode demorar minutos).

A memória vigia-se durante a conversão do docling (`limite_de_memoria`).

Os limites mudam-se pelo ambiente, sem mexer no código:
`CCT_MAX_PAGINAS` (por omissão 500) e `CCT_MAX_MB` (por omissão 100). Uma
convenção do BTE tem poucas dezenas de páginas; o maior PDF do corpus de 2025
tem 67 páginas e 1,6 MB.
"""
from __future__ import annotations

import _thread
import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

MAX_PAGINAS = 500
MAX_MB = 100.0


class PDFRecusado(ValueError):
    """O PDF não entra na extração; a mensagem diz porquê e o que fazer."""


def _limite(nome: str, omissao: float) -> float:
    valor = os.environ.get(nome)
    try:
        return float(valor) if valor else omissao
    except ValueError:
        raise PDFRecusado(f"{nome}={valor!r} não é um número") from None


def verificar_pdf(caminho: Path) -> int:
    """Abre o PDF com o PDFium e devolve o número de páginas, ou recusa-o."""
    import pypdfium2 as pdfium

    caminho = Path(caminho)
    max_mb = _limite("CCT_MAX_MB", MAX_MB)
    max_paginas = int(_limite("CCT_MAX_PAGINAS", MAX_PAGINAS))
    tamanho = caminho.stat().st_size / (1024 * 1024)
    if tamanho > max_mb:
        raise PDFRecusado(
            f"{caminho.name}: {tamanho:.1f} MB, acima do limite de {max_mb:g} MB. "
            "Uma convenção do BTE não chega a isto: confirmar que é o PDF certo, "
            "ou subir CCT_MAX_MB")
    try:
        documento = pdfium.PdfDocument(str(caminho))
    except pdfium.PdfiumError as e:
        if "password" in str(e).lower():
            raise PDFRecusado(
                f"{caminho.name}: o PDF está protegido por palavra-passe. Obter a "
                "versão pública do BTE, que não é protegida") from None
        raise PDFRecusado(
            f"{caminho.name}: o PDF está corrompido ou não é um PDF ({e}). "
            "Descarregar de novo do BTE") from None
    try:
        paginas = len(documento)
    finally:
        documento.close()
    if paginas > max_paginas:
        raise PDFRecusado(
            f"{caminho.name}: {paginas} páginas, acima do limite de {max_paginas}. "
            "Uma convenção do BTE não chega a isto: confirmar que é uma convenção e "
            "não o boletim inteiro, ou subir CCT_MAX_PAGINAS")
    return paginas


class MemoriaExcedida(RuntimeError):
    """A extração passou o limite de memória e foi interrompida."""


# Intervalo entre duas medidas da memória, em segundos.
INTERVALO_MEMORIA = 0.5


@contextmanager
def limite_de_memoria(max_mb: float | None, intervalo: float = INTERVALO_MEMORIA,
                      medir: Callable[[], float] | None = None) -> Iterator[None]:
    """Interrompe o bloco se a memória do processo passar `max_mb` (#25).

    Um vigilante mede a memória residente (cct/memoria.py) a cada `intervalo`
    segundos e, acima do limite, interrompe a thread principal; a interrupção
    sai daqui como `MemoriaExcedida`, com o que fazer. Funciona em Windows,
    Linux e macOS, só com a biblioteca padrão; o `RLIMIT_AS` do sistema só
    existia no Linux. O código nativo (um modelo a meio de uma página) não é
    interrompido a meio: a interrupção chega quando o controlo volta ao Python,
    o que no docling acontece entre as etapas de cada página.

    Sem limite (`None` ou 0), ou fora da thread principal (onde não se pode
    interromper), o bloco corre sem vigilância.
    """
    if not max_mb or threading.current_thread() is not threading.main_thread():
        yield
        return
    if medir is None:
        from .memoria import atual_mb
        medir = atual_mb
    excedido: list[float] = []
    parar = threading.Event()
    trinco = threading.Lock()

    def vigiar() -> None:
        while not parar.wait(intervalo):
            try:
                agora = medir()
            except Exception:
                return                     # sem medida, sem vigilância
            with trinco:
                if agora > max_mb and not parar.is_set():
                    excedido.append(agora)
                    _thread.interrupt_main()
                    return

    vigia = threading.Thread(target=vigiar, name="limite-de-memoria", daemon=True)
    vigia.start()

    def erro() -> MemoriaExcedida:
        return MemoriaExcedida(
            f"a extração chegou a {excedido[0]:.0f} MB, acima do limite de "
            f"{max_mb:g} MB, e foi interrompida. Usar o pdfplumber para este "
            "documento, ou subir CCT_DOCLING_MEMORIA_MAX_MB se a máquina tiver memória")
    try:
        yield
    except KeyboardInterrupt:
        if excedido:
            raise erro() from None
        raise
    finally:
        with trinco:
            parar.set()
    if excedido:
        # a interrupção foi pedida mesmo no fim do bloco: espera-se por ela aqui,
        # para não rebentar mais à frente, noutro sítio
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            pass
        raise erro()
