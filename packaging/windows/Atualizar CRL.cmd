@echo off
rem Aplica o pacote CRL-atualizacao-*.zip desta pasta a instalacao mais recente
rem da aplicacao CRL, na pasta do utilizador. Nao precisa de administrador.
setlocal
set "BASE=%LOCALAPPDATA%\Programs\CRL-PDF-Markdown"
set "APP="
for /f "delims=" %%V in ('dir /b /ad /o:n "%BASE%" 2^>nul') do (
  if exist "%BASE%\%%V\python\python.exe" if exist "%BASE%\%%V\distribuicao.json" set "APP=%BASE%\%%V"
)
if not defined APP (
  echo Nao foi encontrada a aplicacao CRL em %BASE%.
  pause
  exit /b 1
)
set "PACOTE="
for %%Z in ("%~dp0CRL-atualizacao-*.zip") do set "PACOTE=%%~fZ"
if not defined PACOTE (
  echo Coloque o ficheiro CRL-atualizacao-*.zip na mesma pasta deste ficheiro.
  pause
  exit /b 1
)
echo Instalacao: %APP%
echo Pacote: %PACOTE%
"%APP%\python\python.exe" -E -s -X utf8 -B "%PACOTE%"
set "RESULTADO=%ERRORLEVEL%"
pause
exit /b %RESULTADO%
