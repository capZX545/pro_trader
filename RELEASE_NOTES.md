# ProTrader Academy v1.2.0

## v1.2.0 — smooth & stable (nothing removed)
Measured with a 150 s UI stress test (page switching, double-runs, live 1m stream, self-training active on 2 cores): worst UI freeze **30 s → 2.8 s**, p99 **1.2 s → 0.13 s**, zero crashes, clean exit.
- **Crash fixes**: `Worker` threads keep a strong reference until finished (PyQt aborts the process when a running QThread is garbage-collected — the classic random crash), stale jobs are cancelled instead of racing, global `sys.excepthook`/`threading.excepthook` so an exception inside a slot no longer terminates the app, `faulthandler` → `crash.log` in the data folder.
- **Chart engine**: candle history is drawn in lazily-built 1000-bar chunks and only visible chunks are replayed (50 000 bars: build 2.5 s → 0.2 s); trade lines are 4 batched items instead of 3 per trade (up to 1 200 items → 4); a new bar appends in ~5 ms instead of regenerating the history; one repaint per load instead of one per item.
- **Self-training no longer fights the UI**: starts 90 s after launch, runs at below-normal process/thread priority, throttles itself (~35 % idle), yields per strategy/symbol, and pauses whenever you launch a backtest, scan or chart run (`maintenance.ui_busy`).
- Numeric libraries capped to 1 thread each (`OMP/OPENBLAS/MKL_NUM_THREADS`) — stops 20+ background jobs from oversubscribing every core.
- Websocket close moved off the UI thread (TLS shutdown could block for seconds when switching symbols).


## v1.1.2 — chart appears immediately, everywhere
- **Dashboard "Market pulse" was blank for a long time**: it waited until all 94 strategies were back-tested before drawing anything (minutes on a slow PC, and looked like "the chart never shows"). Now it draws the chart ~1 s after data arrives, starts the **live stream** on it, and fills the strategy table later in the background.
- `ProTrader.exe --diag` : opens the chart page, waits 20 s, saves `diag_chart.png` + `diag_report.json` to the data folder (`%APPDATA%\ProTrader`) — send these if anything still looks wrong.
- Verified on the actual frozen (PyInstaller) build, not just source.


## v1.1.1 — chart guaranteed visible
- Some Windows machines showed an **empty chart area** even though data was live (pyqtgraph's QGraphicsView canvas never painted — GPU/driver specific). New `ui/chart_compat.py`: a pure-QPainter software renderer (candles, volume, overlays, signals, zones, levels, trades, sub-panels, crosshair, wheel-zoom, drag-pan, live price tag) that draws through the same raster path as every other widget.
- **Auto-detection**: 1.2 s after the first draw the pyqtgraph canvas is sampled; if it is blank the app switches to the compatibility renderer for the whole session automatically.
- Manual control: 🖼 button in the Chart toolbar and *Settings → Chart renderer* (Auto / pyqtgraph / Compatibility); the choice is saved. Live streaming works identically in both renderers.


## v1.1.0 — the chart works everywhere + real-time streaming
- **Fixed: empty chart.** `api.binance.com` returns HTTP 451 (geo-block) in many countries and Yahoo throttles with 429, so the Chart page silently fell back to synthetic data. New `core/sources.py` fetches crypto history with automatic failover **binance-vision → OKX → KuCoin → Gate → MEXC** (sticky healthy venue, health scoring); Yahoo gets retries with backoff.
- **Real-time streaming on the Chart page.** WebSocket candle stream (binance-vision, OKX fallback, REST polling as last resort) updates the forming candle, volume bar and price tag every second; new bars append and the view follows the market; strategy overlays/signals recompute on bar close. Per-tick redraw is < 1 ms even with 50 000 bars (live bar is drawn separately from the static history).
- Live status pill in the toolbar: `● live · venue · next bar in mm:ss`; non-crypto symbols poll every 60 s.
- Live engine universe falls back to OKX tickers when Binance is unreachable.
- Clean shutdown of sockets/timers on window close.

---
## v1.0.0

Desktop (PyQt6) trading analysis platform — Persian/English. **Analysis, signals, backtesting, education. It does not place orders.**

- 100 strategies (books + bot ports), 80 indicators with full usage sheets, 86 symbols across crypto/forex/commodities/indices/stocks/ETFs, 14 timeframes (1m → 1mo)
- Honest evaluation: multi-year data, dynamic cost model (spread/impact/session/funding), automatic look-ahead + random-walk audit, breadth-gated out-of-sample Playbook, proven-only pickers, low-correlation equal-risk Portfolio
- Live Binance stream, Advisor across all timeframes, forward test with Telegram / desktop alerts
- Chart Vision: reads candle charts from screenshots (MetaTrader / TradingView / Binance app tested), pattern detector, offline analyst
- Self-maintaining: audit → playbook → alert scan run automatically in the background

Known limits (see Health page): most classic strategies are *not* profitable after realistic costs; the Playbook keeps only what survives out-of-sample, and the forward test decides the rest. Photos of monitors decode ~30 % worse than clean screenshots.
