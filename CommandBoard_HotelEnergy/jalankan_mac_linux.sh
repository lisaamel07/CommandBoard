#!/usr/bin/env bash
# Hotel Energy Command Board - versi web (macOS / Linux)
set -e
cd "$(dirname "$0")"

PY=python3
command -v $PY >/dev/null 2>&1 || { echo "[!] python3 tidak ditemukan. Pasang Python 3.10+ dari https://www.python.org/downloads/"; exit 1; }
$PY -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || { echo "[!] Butuh Python 3.10 atau lebih baru."; exit 1; }

if [ ! -x .venv/bin/python ]; then
  echo "[1/3] Membuat virtual environment .venv ..."
  $PY -m venv .venv
fi
echo "[2/3] Memeriksa / memasang library (pertama kali bisa 2-5 menit) ..."
.venv/bin/python -m pip install --disable-pip-version-check -q -r command_board/requirements-web.txt

echo "[3/3] Menjalankan server di http://localhost:8600  (hentikan dengan Ctrl+C)"
( sleep 5; (command -v open >/dev/null && open http://localhost:8600) || (command -v xdg-open >/dev/null && xdg-open http://localhost:8600) || true ) &
exec .venv/bin/python -m uvicorn server:app --app-dir command_board --host 127.0.0.1 --port 8600
