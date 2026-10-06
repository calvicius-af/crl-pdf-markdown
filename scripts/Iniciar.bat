@echo off
cd /d "%~dp0\.."
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "scripts\launch_gui.py"
) else (
    start "" pyw -3 "scripts\launch_gui.py"
)
