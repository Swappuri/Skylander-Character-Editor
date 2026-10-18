#!/usr/bin/env bash
set -euo pipefail
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m PyInstaller --noconfirm --clean --windowed --name "Skylander Character Editor" --collect-all cryptography --collect-all tkinterdnd2 --add-data "assets:assets" src/skylander_character_editor.py
echo "Build output is in ./dist"
