#!/usr/bin/env bash
# Piorsec — setup de dependências de sistema (Linux / macOS)
# Uso: bash setup.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[piorsec]${NC} $1"; }
warn()    { echo -e "${YELLOW}[piorsec]${NC} $1"; }
error()   { echo -e "${RED}[piorsec]${NC} $1"; exit 1; }

# ---------------------------------------------------------------------------
# 1. Dependências de sistema
# ---------------------------------------------------------------------------
OS="$(uname -s)"

if [[ "$OS" == "Linux" ]]; then
    info "Linux detectado — instalando dependências de sistema..."

    if command -v apt &>/dev/null; then
        info "Usando apt (Debian / Ubuntu)"
        sudo apt update -qq
        sudo apt install -y portaudio19-dev python3-dev build-essential

    elif command -v pacman &>/dev/null; then
        info "Usando pacman (Arch)"
        sudo pacman -S --noconfirm portaudio base-devel

    elif command -v dnf &>/dev/null; then
        info "Usando dnf (Fedora)"
        sudo dnf install -y portaudio-devel python3-devel gcc

    elif command -v zypper &>/dev/null; then
        info "Usando zypper (openSUSE)"
        sudo zypper install -y portaudio-devel python3-devel gcc

    else
        warn "Gerenciador de pacotes não reconhecido."
        warn "Instale manualmente: portaudio (headers) e build-essential."
    fi

elif [[ "$OS" == "Darwin" ]]; then
    info "macOS detectado — instalando dependências via Homebrew..."

    if ! command -v brew &>/dev/null; then
        info "Homebrew não encontrado — instalando..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi

    brew install portaudio

else
    error "Sistema operacional não suportado: $OS"
fi

# ---------------------------------------------------------------------------
# 2. uv
# ---------------------------------------------------------------------------
if command -v uv &>/dev/null; then
    info "uv já instalado: $(uv --version)"
else
    info "Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# ---------------------------------------------------------------------------
# 3. Dependências Python
# ---------------------------------------------------------------------------
info "Instalando dependências Python via uv sync..."
uv sync

info "Setup concluído! Para rodar:"
echo ""
echo "  Host:   uv run piorsec host --client-ip <IP_DO_CLIENTE>"
echo "  Client: uv run piorsec client --ip <IP_DO_HOST>"
echo ""
