#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg pipx

# Ensure pipx on PATH for current session
python3 -m pipx ensurepath || true

pipx install yt-dlp || pipx upgrade yt-dlp

# Optional: Node (only if you want it)
# sudo apt-get install -y nodejs
