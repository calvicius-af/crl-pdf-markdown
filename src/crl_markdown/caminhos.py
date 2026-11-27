"""Caminhos longos no Windows e abertura de ficheiros na aplicação predefinida.

O Windows recusa, por omissão, caminhos com mais de 260 caracteres e responde
«O sistema não conseguiu localizar o caminho especificado». As correções e o
OCR dirigido criam subpastas profundas dentro da pasta de saída, que nas
estações CRL já está numa pasta sincronizada com nome longo. O prefixo de
caminho estendido («\\\\?\\») retira esse limite sem exigir alterações ao
registo do Windows.
"""

import ntpath
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PREFIX = '\\\\?\\'
UNC_PREFIX = PREFIX + 'UNC\\'
# Margem abaixo de 260 para nomes temporários criados pelo atomic_write.
WINDOWS_LIMIT = 240


def extended(text: str) -> str:
    """Forma estendida de um caminho Windows absoluto; idempotente."""
    if text.startswith(PREFIX):
        return text
    text = ntpath.normpath(text)
    if text.startswith('\\\\'):
        return UNC_PREFIX + text[2:]
    return PREFIX + text


def plain(text: str) -> str:
    """Caminho Windows sem o prefixo estendido, para mostrar ou abrir."""
    if text.startswith(UNC_PREFIX):
        return '\\\\' + text[len(UNC_PREFIX):]
    if text.startswith(PREFIX):
        return text[len(PREFIX):]
    return text


def longpath(path) -> Path:
    """Pasta de trabalho segura para caminhos profundos; sem efeito fora do Windows."""
    if os.name != 'nt':
        return Path(path)
    return Path(extended(os.path.abspath(str(path))))


def like(result, original) -> Path:
    """Devolver no mesmo formato da entrada: só quem pediu o prefixo o recebe."""
    if os.name == 'nt' and not str(original).startswith(PREFIX):
        return Path(plain(str(result)))
    return Path(result)


def display(path) -> str:
    return plain(str(path)) if os.name == 'nt' else str(path)


def open_with_system(path) -> Path:
    """Abrir na aplicação predefinida (leitor de PDF, editor de texto), não no browser.

    Um caminho que continue acima do limite do Windows é copiado para a pasta
    temporária e aberto como cópia de consulta; o original não é alterado.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'Ficheiro não encontrado: {display(path)}')
    if os.name == 'nt':
        target = plain(str(path))
        if len(target) >= WINDOWS_LIMIT:
            folder = Path(tempfile.mkdtemp(prefix='crl-'))
            copy = folder / path.name
            if len(str(copy)) >= WINDOWS_LIMIT:
                copy = folder / ('documento' + path.suffix)
            shutil.copy2(path, copy)
            target = str(copy)
        os.startfile(target)  # noqa: S606 (abre na aplicação associada)
        return Path(target)
    command = ['open', str(path)] if sys.platform == 'darwin' else ['xdg-open', str(path)]
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603
    return path
