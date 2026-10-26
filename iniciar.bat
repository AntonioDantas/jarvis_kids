@echo off
rem =============================================================================
rem  J.A.R.V.I.S. Kids - instala (so na primeira vez) e liga o Jarvis no Windows.
rem  Uso: de dois cliques neste arquivo.  Opcoes: iniciar.bat --texto
rem =============================================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
title J.A.R.V.I.S. Kids

echo.
echo  Preparando o J.A.R.V.I.S. Kids...
echo.

rem --- 1. Python 3.12, 3.11 ou 3.10 (pelo lancador "py" ou pelo "python")
set "PY="
for %%V in (3.12 3.11 3.10) do call :testar_py %%V
if not defined PY (
  python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [ERRO] Nao encontrei o Python 3.10, 3.11 ou 3.12.
  echo        Instale em https://www.python.org/downloads/ e marque "Add python.exe to PATH".
  echo        Ou, no Terminal:  winget install Python.Python.3.12
  pause
  exit /b 1
)

rem --- 2. Ambiente isolado .venv + componentes - so reinstala se requirements.txt mudar
if not exist ".venv\Scripts\python.exe" (
  echo Criando o ambiente do Jarvis na pasta .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [ERRO] Nao consegui criar o ambiente do Python.
    pause
    exit /b 1
  )
)
fc /b requirements.txt ".venv\requirements.instalado.txt" >nul 2>&1
if errorlevel 1 (
  echo Instalando os componentes de IA. Na primeira vez leva alguns minutos...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERRO] A instalacao falhou. Confira a internet e tente de novo.
    pause
    exit /b 1
  )
  copy /y requirements.txt ".venv\requirements.instalado.txt" >nul
)

rem --- 3. Ollama - o cerebro local
where ollama >nul 2>&1
if errorlevel 1 (
  echo [AVISO] Ollama nao encontrado. Baixe em https://ollama.com/download
  echo         ou rode no Terminal:  winget install Ollama.Ollama
) else (
  ".venv\Scripts\python.exe" -c "import urllib.request; urllib.request.urlopen('http://localhost:11434/api/version', timeout=2)" >nul 2>&1
  if errorlevel 1 (
    echo Ligando o Ollama...
    start "" /min ollama serve
    timeout /t 4 /nobreak >nul
  )
)

rem --- 4. Decolar!
".venv\Scripts\python.exe" main.py %*
echo.
pause
exit /b 0

:testar_py
if defined PY exit /b 0
py -%1 -c "import sys" >nul 2>&1 && set "PY=py -%1"
exit /b 0
