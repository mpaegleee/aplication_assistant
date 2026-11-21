$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Instale Python 3.12 x64 para compilar.' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Instale Node.js 24 LTS para compilar.' }
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependencias.' }
npm --prefix frontend ci
if ($LASTEXITCODE -ne 0) { throw 'Falha npm ci.' }
npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw 'Falha no build da interface.' }
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) 'browsers'
& .\.venv\Scripts\python.exe -m playwright install --no-shell chromium
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar Chromium.' }
$env:RUN_BROWSER_TESTS = '1'
$env:PYTHONPATH = 'backend'
& .\.venv\Scripts\python.exe -m pytest backend\tests -q
if ($LASTEXITCODE -ne 0) { throw 'Testes falharam.' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --name ApplicationAssistant --onedir --paths backend --add-data "frontend\dist;frontend" --collect-all reportlab --collect-all tzdata --collect-all playwright --collect-submodules uvicorn backend\launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Falha no empacotamento Windows.' }
Copy-Item -Recurse browsers dist\ApplicationAssistant\browsers
Copy-Item docs\GUIA-DO-USUARIO.md dist\ApplicationAssistant\LEIA-ME.md
Copy-Item LICENSE.txt dist\ApplicationAssistant\LICENSE.txt
& .\.venv\Scripts\python.exe packaging\third_party.py dist\ApplicationAssistant\THIRD-PARTY-NOTICES.txt
Write-Host 'Executavel em dist\ApplicationAssistant\ApplicationAssistant.exe'
