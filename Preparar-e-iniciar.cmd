@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\aa-ready-0.6.0.txt" (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Instale Python 3.12 x64 pelo site https://www.python.org/downloads/windows/
    echo Marque a opcao do Python Launcher durante a instalacao.
    pause
    exit /b 1
  )
  py -3.12 -m venv .venv
  if errorlevel 1 goto erro
  .venv\Scripts\python.exe -m pip install --require-hashes -r backend\requirements.lock
  if errorlevel 1 goto erro
  echo ready> .venv\aa-ready-0.6.0.txt
)
if not exist "frontend\dist\index.html" (
  where npm >nul 2>nul
  if errorlevel 1 (
    echo Instale Node.js 24 LTS pelo site https://nodejs.org/
    pause
    exit /b 1
  )
  call npm --prefix frontend ci
  if errorlevel 1 goto erro
  call npm --prefix frontend run build
  if errorlevel 1 goto erro
)
set PLAYWRIGHT_BROWSERS_PATH=%CD%\browsers
.venv\Scripts\python.exe -m playwright install --no-shell chromium
if errorlevel 1 goto erro
.venv\Scripts\python.exe backend\launcher.py
if errorlevel 1 goto erro
exit /b 0
:erro
echo Nao foi possivel iniciar. Confira as mensagens acima e o guia docs\TESTE-LOCAL.md.
pause
exit /b 1
