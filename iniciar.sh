#!/usr/bin/env bash
# =============================================================================
#  J.A.R.V.I.S. Kids — instala (só na primeira vez) e liga o Jarvis.
#  Uso:  ./iniciar.sh            (experiência completa com voz)
#        ./iniciar.sh --texto    (sem microfone)   ./iniciar.sh --diagnostico
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

azul() { printf "\033[1;36m%s\033[0m\n" "$1"; }
aviso() { printf "\033[1;33m%s\033[0m\n" "$1" >&2; }
erro() { printf "\033[1;31m%s\033[0m\n" "$1" >&2; }

azul "🚀 Preparando o J.A.R.V.I.S. Kids..."

# --- 1. Python 3.10, 3.11 ou 3.12 (3.13 também funciona, mas sem a voz neural Kokoro)
PY=""
for candidato in python3.12 python3.11 python3.10 python3 python3.13 python; do
  if command -v "$candidato" >/dev/null 2>&1 &&
     "$candidato" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)' 2>/dev/null; then
    PY="$candidato"
    break
  fi
done
if [ -z "$PY" ]; then
  erro "❌ Não encontrei o Python 3.10, 3.11 ou 3.12."
  erro "   Mac: baixe em https://www.python.org/downloads/   |   Ubuntu/Debian: sudo apt install python3 python3-venv"
  exit 1
fi

# --- 2. Ambiente isolado (.venv) + componentes (só reinstala se requirements.txt mudar)
if [ ! -x .venv/bin/python ]; then
  azul "🛠️  Criando o ambiente do Jarvis (pasta .venv)..."
  if ! "$PY" -m venv .venv; then
    erro "❌ Não consegui criar o ambiente. No Ubuntu/Debian rode: sudo apt install python3-venv"
    exit 1
  fi
fi
if ! cmp -s requirements.txt .venv/requirements.instalado.txt; then
  azul "📦 Instalando os componentes de IA (na primeira vez leva alguns minutos)..."
  .venv/bin/python -m pip install --upgrade pip
  # Linux sem placa NVIDIA: PyTorch "só CPU" é muito menor para baixar.
  if [ "$(uname -s)" = "Linux" ] && ! command -v nvidia-smi >/dev/null 2>&1; then
    .venv/bin/python -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
  fi
  .venv/bin/python -m pip install -r requirements.txt
  cp requirements.txt .venv/requirements.instalado.txt
fi

# --- 3. Linux: biblioteca de áudio (microfone e alto-falante)
if [ "$(uname -s)" = "Linux" ] && ! ldconfig -p 2>/dev/null | grep -q libportaudio; then
  aviso "⚠️  Sem PortAudio o Jarvis não ouve nem fala. Instale com: sudo apt install libportaudio2"
fi

# --- 4. Ollama (o "cérebro" local)
ollama_ligado() {
  .venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://localhost:11434/api/version', timeout=2)" \
    >/dev/null 2>&1
}
if ! command -v ollama >/dev/null 2>&1; then
  aviso "⚠️  Ollama não encontrado. Instale em https://ollama.com/download"
  aviso "    (Linux: curl -fsSL https://ollama.com/install.sh | sh)"
elif ! ollama_ligado; then
  azul "🧠 Ligando o Ollama..."
  (ollama serve >/dev/null 2>&1 &)
  for _ in 1 2 3 4 5 6 7 8 9 10; do ollama_ligado && break; sleep 1; done
fi

# --- 5. Só na primeira vez: baixa todos os modelos de IA de uma vez, com barra de progresso
if [ ! -f .venv/.modelos_preparados ]; then
  azul "🧠 Baixando os modelos de IA (cérebro ~2 GB, ouvido ~0,5 GB, voz ~0,3 GB). Só acontece uma vez!"
  if .venv/bin/python main.py --preparar; then
    touch .venv/.modelos_preparados
  fi
fi

# --- 6. Decolar!
exec .venv/bin/python main.py "$@"
