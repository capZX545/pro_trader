#!/usr/bin/env bash
# ProTrader web/mobile server — same engine as the desktop app, no Qt required (works on a VPS / Raspberry Pi).
#   ./run_web.sh            → http://<this-machine-ip>:8765  (open on your phone, same Wi-Fi)
#   PORT=9000 ./run_web.sh
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements-web.txt 2>/dev/null || true
exec python3 main.py --web --port "${PORT:-8765}"
