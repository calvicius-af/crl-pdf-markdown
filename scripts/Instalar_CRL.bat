@echo off
chcp 65001 >nul
setlocal DisableDelayedExpansion
set PYTHONUTF8=1
pushd "%~dp0"
if errorlevel 1 (
  echo Nao foi possivel abrir a pasta do pacote. Copie a pasta completa para Documentos e repita.
  pause
  exit /b 1
)
py -3.13 instalar_offline.py
set CRL_EXIT=%errorlevel%
if not "%CRL_EXIT%"=="0" (
  echo Se Python nao foi encontrado, o apoio informatico deve instalar Python 3.13 com Tcl/Tk.
  echo Conserve o texto apresentado nesta janela e consulte LEIA_PRIMEIRO.md.
)
popd
pause
exit /b %CRL_EXIT%
