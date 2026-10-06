@echo off
setlocal
rem pushd cria uma unidade temporaria quando a pasta e uma partilha UNC.
pushd "%~dp0\.."
if errorlevel 1 (
    echo Nao foi possivel abrir a pasta do projeto.
    pause
    exit /b 1
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" /wait ".venv\Scripts\pythonw.exe" "scripts\launch_gui.py"
) else (
    start "" /wait pyw -3 "scripts\launch_gui.py"
)
rem Manter a unidade mapeada enquanto o lancador esta a instalar.
popd
endlocal
