@echo off
setlocal

:: Switch to script directory
cd /d "%~dp0"

:: 1. Prefer uv if available
where uv >nul 2>nul
if %ERRORLEVEL% equ 0 (
    uv run python main.py %*
    goto :end
)

:: 2. Use local virtual environment if present
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %*
    goto :end
)

:: 3. Fallback to system Python
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

echo [ERROR] Python environment not found. Please install Python or uv.
pause
exit /b 1

:end
endlocal
