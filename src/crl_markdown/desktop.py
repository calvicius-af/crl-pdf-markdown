"""Entrada do atalho Windows: runtime privado, modelos incluídos e falhas visíveis."""

import os
import sys
from pathlib import Path


def prepare_environment():
    from .settings import user_folder

    resources = Path(sys.executable).resolve().parent.parent / "recursos"
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                       "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
                       "HF_HOME": str(user_folder() / "cache-hf"),
                       "TORCH_HOME": str(user_folder() / "cache-torch")})
    # Modelos ONNX e o parser PDF podem exigir um alias ANSI em Windows.
    if sys.platform == "win32":
        import ctypes
        packages = Path(sys.executable).parent / "Lib/site-packages"
        if not str(packages).isascii():
            from ctypes import wintypes
            short_path = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
            short_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
            short_path.restype = wintypes.DWORD
            buffer = ctypes.create_unicode_buffer(32768)
            size = short_path(str(packages), buffer, len(buffer))
            if not 0 < size < len(buffer) or not buffer.value.isascii():
                raise RuntimeError("O Windows não disponibilizou um caminho compatível para as "
                                   "bibliotecas. Peça ao apoio uma pasta local sem acentos.")
            sys.path.insert(0, buffer.value)
    return resources


def main():
    try:
        resources = prepare_environment()
        from .app import main as application
        application(["--models", str(resources / "modelos"), "--offline", "--installed"])
    except Exception as error:
        import tkinter as tk

        from .diagnostics import support_dialog
        root = tk.Tk()
        root.withdraw()
        support_dialog(root, error, "Abrir CRL")
        root.destroy()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
