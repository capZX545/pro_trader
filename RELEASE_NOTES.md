# ProTrader Academy v1.1.1

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
