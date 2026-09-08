# ProTrader — Web & Mobile

The desktop engine (179 strategies, success-rate registry, advisor, fast signals, academy) served to any phone/browser.
No extra dependencies (Python `http.server`), no Qt.

* Desktop app → **Settings ▸ Web & mobile ▸ Start** → scan the QR with your phone (same Wi-Fi).
* Headless: `ProTrader --web` (release binary) or `./run_web.sh` / `run_web.bat` from source.
* Internet: `cloudflared tunnel --url http://localhost:8765` or `ngrok http 8765` → open the printed https URL on the phone
  and use *Add to Home Screen* (PWA manifest included) for an app-like icon.
* Docker/VPS: `docker run -p 8765:8765 -v protrader-data:/data -e PROTRADER_DATA=/data <image> python main.py --web`.

API (JSON): `/api/meta /api/symbols /api/strategies /api/ohlcv /api/run /api/signals /api/advise /api/fast /api/library /api/clock /api/success`.
