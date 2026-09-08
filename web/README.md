# ProTrader — Web & Mobile

The desktop engine (179 strategies, success-rate registry, advisor, fast signals, academy) served to any phone/browser.
No extra dependencies (Python `http.server`), no Qt.

* Desktop app → **Settings ▸ Web & mobile ▸ Start** → scan the QR with your phone (same Wi-Fi).
* Headless: `ProTrader --web` (release binary) or `./run_web.sh` / `run_web.bat` from source.
* Internet: `cloudflared tunnel --url http://localhost:8765` or `ngrok http 8765` → open the printed https URL on the phone
  and use *Add to Home Screen* (PWA manifest included) for an app-like icon.
* Docker/VPS: `docker run -p 8765:8765 -v protrader-data:/data -e PROTRADER_DATA=/data <image> python main.py --web`.

API (JSON): `/api/meta /api/symbols /api/strategies /api/ohlcv /api/run /api/signals /api/advise /api/fast /api/library /api/clock /api/success`.

## Phase 21 — parity routes
| Route | Purpose |
|---|---|
| `GET /api/indicators?lang=` | catalog of every chart indicator (place, params, uses, signals, pitfalls) |
| `GET /api/indicator?sym&tf&key&n&params=` | compute one indicator → overlays / panels / levels |
| `GET/POST /api/drawings?sym&tf` | drawings shared with the desktop (`data/drawings.json`) |
| `GET /api/forward?update=1` | forward-test report / open / closed |
| `GET /api/portfolio?tf&n&equity` | proven-strategy portfolio |
| `GET /api/risk?equity&risk_pct&entry&stop&wr&rr` | position size, Kelly, RoR, expectancy |
| `GET/POST /api/journal` | journal rows + Steenbarger audit (`{op:add|delete|replace}`) |
| `GET /api/health?quick&lang` | self-diagnosis findings |
| `GET /api/patterns?sym&tf&recent` | candlestick + chart patterns |
| `GET /api/analyst?sym&tf&lang&q=` | offline analyst report (+ answer to `q`) |
| `POST /api/vision?lang` (body = image bytes, `Content-Type: image/*`) | chart-image understanding |
| `GET /api/ml?sym&tf&train=1` | ML model status / train / P(up) |
| `GET /api/quant?sym&sym2&tf` | ADF, Hurst, half-life, cointegration |
| `GET/POST /api/alerts` | alert settings + history |
| `GET /api/status` | training stage, playbook, success coverage, maintenance log |
| `GET /api/success_precompute` | start/poll bulk success-rate computation |
| `GET /api/search?q=` | symbol search |

## Android app
`android/` is a Gradle project (Chaquopy) that packages the whole engine as an APK — see `scripts/prepare_android.py`,
`requirements-android.txt` and the `android` job in `.github/workflows/release.yml`. The APK is attached to every GitHub release
as `ProTrader-<ver>-android.apk`.
