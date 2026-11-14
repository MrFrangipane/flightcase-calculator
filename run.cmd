@echo off
setlocal

:: Ir a la carpeta del script
cd /d "%~dp0"

:: 1. Usar uv si esta disponible
where uv >nul 2>nul
if %ERRORLEVEL% equ 0 (
    uv run python main.py %*
    goto :end
)

:: 2. Usar el entorno virtual local si existe
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %*
    goto :end
)

:: 3. Si no, usar el Python del sistema
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python main.py %*
    goto :end
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py -m main %*
    goto :end
)

echo [ERROR] No se encontro Python. Instala Python o uv.
pause
exit /b 1

:end
endlocal
