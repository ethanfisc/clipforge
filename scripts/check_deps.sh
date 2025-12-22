#!/usr/bin/env bash
set -euo pipefail

need() {
  local name="$1"
  local cmd="$2"
  local hint="$3"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "MISSING: $name  (binary: $cmd)"
    echo "  install: $hint"
    exit 1
  fi
  echo "OK: $name ($(command -v "$cmd"))"
}

need "Python" python3 "sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip"
need "ffmpeg" ffmpeg "sudo apt-get update && sudo apt-get install -y ffmpeg"
need "yt-dlp" yt-dlp "pipx install yt-dlp  (or: python3 -m pip install --user yt-dlp)"
need "ffprobe" ffprobe "sudo apt-get update && sudo apt-get install -y ffmpeg"
# optional but recommended
if command -v node >/dev/null 2>&1; then
  echo "OK: Node ($(node --version))"
else
  echo "WARN: Node missing (optional). Install if you see nsig/signature/throttling issues."
  echo "  install: sudo apt-get update && sudo apt-get install -y nodejs"
fi
