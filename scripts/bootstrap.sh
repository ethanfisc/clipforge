#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"

log()  { echo "[bootstrap] $*"; }
warn() { echo "[bootstrap] WARN: $*" >&2; }
die()  { echo "[bootstrap] ERROR: $*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

apt_install() {
  local pkgs=("$@")
  log "Installing via apt: ${pkgs[*]}"
  sudo apt-get update
  sudo apt-get install -y "${pkgs[@]}"
}

ensure_python() {
  if have python3 && have pip3; then
    log "OK: python3 ($(python3 --version))"
    return
  fi
  apt_install python3 python3-venv python3-pip
  log "OK: python3 ($(python3 --version))"
}

ensure_ffmpeg() {
  if have ffmpeg && have ffprobe; then
    log "OK: ffmpeg ($(ffmpeg -version | head -n1))"
    return
  fi
  apt_install ffmpeg
  log "OK: ffmpeg ($(ffmpeg -version | head -n1))"
}

ensure_pipx() {
  if have pipx; then
    log "OK: pipx ($(pipx --version))"
    return
  fi
  apt_install pipx
  # Ensure pipx path for current shell session
  python3 -m pipx ensurepath >/dev/null 2>&1 || true
  # Typical Ubuntu path:
  export PATH="$PATH:$HOME/.local/bin"
  have pipx || die "pipx installed but not on PATH. Try: source ~/.profile"
  log "OK: pipx ($(pipx --version))"
}

ensure_ytdlp() {
  if have yt-dlp; then
    log "OK: yt-dlp ($(yt-dlp --version))"
    return
  fi
  log "Installing yt-dlp via pipx..."
  pipx install yt-dlp >/dev/null 2>&1 || pipx upgrade yt-dlp
  have yt-dlp || die "yt-dlp install failed"
  log "OK: yt-dlp ($(yt-dlp --version))"
}

check_node_optional() {
  if have node; then
    log "OK: node ($(node --version))"
  else
    warn "node missing (optional but recommended for YouTube JS challenge solving)."
    warn "Install: sudo apt-get update && sudo apt-get install -y nodejs"
  fi
}

ensure_venv_and_install() {
  log "Setting up venv at ${VENV_DIR}"
  if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
  fi

  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"

  python -m pip install -U pip setuptools wheel
  log "Installing project (editable) from pyproject..."
  python -m pip install -e "${REPO_ROOT}"
  log "OK: venv ready. Activate with: source .venv/bin/activate"
}

main() {
  cd "${REPO_ROOT}"
  ensure_python
  ensure_ffmpeg
  ensure_pipx
  ensure_ytdlp
  check_node_optional
  ensure_venv_and_install

  log "Done."
  log "Quick checks:"
  log "  yt-dlp: $(command -v yt-dlp)"
  log "  ffmpeg: $(command -v ffmpeg)"
  log "  python: $(command -v python3)"
}

main "$@"
