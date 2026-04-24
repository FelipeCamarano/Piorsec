# Piorsec — setup de dependências de sistema (Windows)
# Uso: .\setup.ps1

$ErrorActionPreference = "Stop"

function Info  { param($msg) Write-Host "[piorsec] $msg" -ForegroundColor Green }
function Warn  { param($msg) Write-Host "[piorsec] $msg" -ForegroundColor Yellow }

# ---------------------------------------------------------------------------
# 1. uv
# ---------------------------------------------------------------------------
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Info "uv já instalado: $(uv --version)"
} else {
    Info "Instalando uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

    # Recarrega PATH da sessão atual
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
}

# ---------------------------------------------------------------------------
# 2. Dependências Python
# ---------------------------------------------------------------------------
Info "Instalando dependências Python via uv sync..."
uv sync

# ---------------------------------------------------------------------------
# 3. ViGEmBus (necessário para injeção de gamepad no modo host)
# ---------------------------------------------------------------------------
$vigem = Get-ItemProperty `
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*" `
    -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName -like "*ViGEm*" }

if ($vigem) {
    Info "ViGEmBus já instalado."
} else {
    Warn "ViGEmBus não encontrado."
    Warn "Necessário para modo host (injeção de gamepad)."
    Warn "Baixe em: https://github.com/nefarius/ViGEmBus/releases"
}

# ---------------------------------------------------------------------------
Info "Setup concluído! Para rodar:"
Write-Host ""
Write-Host "  Host:   uv run piorsec host --client-ip <IP_DO_CLIENTE>"
Write-Host "  Client: uv run piorsec client --ip <IP_DO_HOST>"
Write-Host ""
