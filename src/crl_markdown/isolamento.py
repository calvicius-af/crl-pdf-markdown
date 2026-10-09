"""Conversão Docling num processo separado, que pode cair sem levar a corrida.

No ensaio de 9 de outubro em Windows (BTE 1 a 36 de 2026), a interface fechou-se
sozinha duas vezes a meio do lote. O faulthandler registou uma violação de
acesso dentro do Docling, em várias threads ao mesmo tempo, ao preparar as
imagens das páginas para o modelo de layout (numpy e torchvision). Não é um PDF
concreto, e não se corrige a partir deste código.

O que se pode fazer é não deixar que essa falha leve a corrida consigo. O
Docling corre num processo à parte, com os modelos carregados uma vez. Se o
processo cair, a falha fica registada, o documento é repetido uma vez num
processo novo e, se voltar a cair, fica `falhou` e a corrida segue. O processo é
também renovado a cada `RENOVAR_A_CADA` documentos: as duas quedas vieram depois
de dezenas de documentos, e um processo novo não herda o estado do anterior.
"""

import faulthandler
import multiprocessing
import time
from pathlib import Path

# Hipótese de mitigação, não um valor medido: renovar custa recarregar os
# modelos (cerca de 10 s), o que em 400 documentos são poucos minutos.
RENOVAR_A_CADA = 25
ARRANQUE_S = 300  # carregar os modelos antes do primeiro documento


class FalhaNativa(RuntimeError):
    """O processo de conversão terminou sem exceção Python (falha numa biblioteca em C)."""

    error_type = "FalhaNativa"


class FalhaArranque(RuntimeError):
    """O conversor não pôde ser criado (modelos em falta, opções inválidas).

    Falharia igual em todos os documentos: interrompe a corrida, como quando o
    Docling corria no mesmo processo.
    """


class ErroNoProcesso(RuntimeError):
    """Uma exceção Python dentro do processo de conversão, com o tipo original."""

    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


def _trabalhador(ligacao, options, factory, registo_falhas):
    from .pipeline import convert_pdf

    if registo_falhas:
        destino = open(registo_falhas, "a", encoding="utf-8")  # noqa: SIM115
        faulthandler.enable(file=destino)
    converter = None
    while True:
        try:
            tarefa = ligacao.recv()
        except EOFError:  # o processo principal terminou
            break
        if tarefa is None:
            break
        pdf, target, overwrite, audit_dir = tarefa
        if converter is None:
            try:
                converter = factory(options)
            except Exception as exc:
                ligacao.send(("arranque", type(exc).__name__, str(exc)))
                break
        try:
            report = convert_pdf(pdf, target, converter, options, overwrite, audit_dir=audit_dir)
            ligacao.send(("ok", report))
        except Exception as exc:
            ligacao.send(("erro", type(exc).__name__, str(exc)))


class ConversorIsolado:
    """Converte cada PDF num processo de trabalho, reiniciado quando cai."""

    def __init__(
        self,
        options,
        factory,
        *,
        registo_falhas: Path | None = None,
        aviso=print,
        renovar_a_cada: int | None = None,
    ):
        self.options, self.factory = options, factory
        self.registo_falhas = str(registo_falhas) if registo_falhas else None
        self.aviso = aviso
        self.renovar_a_cada = renovar_a_cada or RENOVAR_A_CADA
        self.contexto = multiprocessing.get_context("spawn")
        self.processo = self.ligacao = None
        self.feitos = 0

    def _iniciar(self):
        if self.processo is not None:
            return
        ligacao, filho = self.contexto.Pipe()
        processo = self.contexto.Process(
            target=_trabalhador,
            args=(filho, self.options, self.factory, self.registo_falhas),
            daemon=True,
        )
        try:
            processo.start()
        finally:
            filho.close()
        self.processo, self.ligacao, self.feitos = processo, ligacao, 0

    def _descartar(self):
        if self.processo is None:
            return
        if self.processo.is_alive():
            self.processo.kill()
        self.processo.join(10)
        self.ligacao.close()
        self.processo = self.ligacao = None

    def fechar(self):
        if self.processo is not None and self.processo.is_alive():
            try:
                self.ligacao.send(None)
                self.processo.join(30)
            except OSError:
                pass
        self._descartar()

    def _esperar(self, prazo: float):
        """O resultado do processo, ou `None` se ele caiu ou excedeu o prazo."""
        limite = time.monotonic() + prazo
        try:
            while True:
                if self.ligacao.poll(0.5):
                    return self.ligacao.recv()
                if not self.processo.is_alive():
                    # Pode ter respondido mesmo antes de terminar.
                    return self.ligacao.recv() if self.ligacao.poll(0) else None
                if time.monotonic() > limite:
                    self.processo.kill()
                    return ("prazo",)
        except (EOFError, OSError):  # a ligação fechou com o processo
            return None

    def convert_pdf(self, pdf: Path, target: Path, overwrite: bool, audit_dir: Path) -> dict:
        prazo = 2 * self.options.timeout + ARRANQUE_S
        for tentativa in (1, 2):
            self._iniciar()
            # Na repetição, os ficheiros que existam foram escritos pela
            # tentativa que caiu: a primeira já tinha confirmado que não havia.
            try:
                self.ligacao.send((pdf, target, overwrite or tentativa == 2, audit_dir))
            except OSError:  # o processo morreu antes de receber o documento
                resultado = None
            else:
                resultado = self._esperar(prazo)
            if resultado is None or resultado[0] == "prazo":
                codigo = self.processo.exitcode
                self._descartar()
                if resultado is not None:
                    raise FalhaNativa(
                        f"a conversão excedeu {prazo:.0f} s e o processo foi terminado"
                    )
                if tentativa == 1:
                    self.aviso(
                        f"  o processo de conversão terminou com uma falha nativa (código "
                        f"{codigo}); a repetir {pdf.name} num processo novo"
                    )
                    continue
                raise FalhaNativa(
                    f"o processo de conversão terminou com uma falha nativa duas vezes "
                    f"(código {codigo}); ver _auditoria/falha_nativa.log"
                )
            if resultado[0] == "arranque":
                self._descartar()
                raise FalhaArranque(f"{resultado[1]}: {resultado[2]}")
            self.feitos += 1
            if self.feitos >= self.renovar_a_cada:
                self.fechar()
            if resultado[0] == "ok":
                return resultado[1]
            raise ErroNoProcesso(resultado[1], resultado[2])
        raise AssertionError("inalcançável")
