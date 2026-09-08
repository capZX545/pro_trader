## v1.4.0 — Phase 17: TradingView-style chart, full Ichimoku, view persistence, local/world clock, signal inspector
- **Chart tools** (pyqtgraph renderer): trend line, ray, horizontal/vertical line, rectangle zone, Fibonacci retracement, text note, measure ruler, eraser, undo/clear. Drawings are movable and persisted per symbol|timeframe by (UTC timestamp, price) → they survive refresh, new bars and restarts (`data/drawings.json`).
- **All 73 catalog indicators on the chart** via "ƒx Add indicator" (searchable, editable parameters, multiple instances) + templates (Ichimoku, Classic, Scalping, Volume, Trend). Layout remembered per symbol|timeframe. Ichimoku Kumo is filled green/red; Bollinger/Keltner/Donchian/LinReg bands are shaded.
- **Ichimoku learned completely** (`strategies/ichimoku.py`, 11 signal strategies): Perfect Order (sanyaku), graded TK cross, Kumo breakout, Kijun bounce, Kumo twist + confirmation, Chikou breakout, edge-to-edge, flat Span-B magnet, crypto 20/60/120, multi-timeframe, N-wave price theory (N/V/E/NT targets) with kihon-suchi timing. 3 of them join the Fast-Signals vote; library entry added. 132 strategies total.
- **Refresh keeps your place**: view anchored to timestamps, so re-runs/recomputes/live bars no longer reset zoom or scroll; "⟳ Refresh" re-applies new settings in place.
- **Signal inspector**: click a table row or a marker on the chart → chart pans to it, marks it (time, side, entry/SL/TP) and the card shows outcome (win/loss, R, bars). Table now has an Outcome column and a success-rate footer (in-sample WR/PF + out-of-sample playbook WR with CI); strategy list shows [WR% · PF] when a playbook exists.
- **Time**: chart axis, tables and cards use the computer's exact system timezone; header clock shows local + UTC; UTC/local toggle.
- **Smoother**: live ticks coalesced to ≤10 repaints/s and y-rescale only when needed (200 ticks: 31 s → 0.5 s); overlays/panels clip-to-view + peak downsampling; fixed pyqtgraph legend/clip exception spam. Nothing removed.

## v1.3.1 — Phase 16 round 2: order-flow methods, NFI/freqtrade autopsy, walk-forward tuning
- **9 new low-timeframe strategies** (`strategies/orderflow.py`, 121 total): value_area_bounce, triple_a_flow (Valentini absorption→accumulation→aggression), stacked_imbalance_retest, lvn_breakout, anchored_scalp (Jesse anchor-TF + VWAP + CVD), ft_scalp (freqtrade community Scalp, re-risked), flat_bb_stoch, nfi_dip_multi (NFI EWO + BB-dip + informative gate), unfinished_auction. All are OHLCV proxies of footprint concepts (no tick data) and are calibrated on crypto distributions (absorption = top-3 % volume/range percentile, EWO measured 6 bars before the dip, one attempt per poor high/low).
- **Fast Signals** now votes with 20 scalp/order-flow methods + classic intraday set; new **🧪 Walk-forward tune** button (`core/scalp_wfo.py`): anchored WFO of the confluence knobs (votes/window/ATR stop/RR) per symbol, reports OOS PF, WFE and an edge/weak/none verdict; the scan adopts tuned knobs per symbol.
- **Library**: +6 research entries (footprint field guides, Valentini playbook, NFI X structure, freqtrade Scalp autopsy, flat-BB quiet-hours scalp, Pardo/Davey walk-forward) and +2 bot entries (NFI X, footprint bots); Freqtrade/Jesse entries deepened.
- Honesty (50k-bar tests, futures-taker fees): single new methods PF 0.2–1.03; best alone = triple_a_flow SOL 15m 1.03, lvn_breakout ETH 15m 0.79 (1.09 at maker). Walk-forward: SOL 15m confluence OOS PF 1.05 (weak), ETH 15m 0.68 (none). Low-TF edge remains thin — forward-test first.

# ProTrader Academy v1.3.0

## v1.3.0 — Fast Signals (low-timeframe research pass) + stability round 3
- **New page ⚡ Fast Signals**: scans the top-N pairs on 1m/3m/5m/15m with 12 new scalping methods + the classic intraday set, shows a setup only when ≥ N independent methods agree, the EMA50/200 trend gate passes and the expected move covers round-trip fees (spot-taker / futures-taker / futures-maker tiers). Each row carries the honest in-sample WR/PF of that confluence rule on that symbol, session (London/NY overlap bonus), perp-funding positioning and a bilingual explanation; double-click opens the chart; score ≥ 60 setups are pushed to alerts.
- **12 new strategies (strategies/scalp.py)**: vwap_pullback_scalp, vwap_band_fade, cvd_divergence (BVC delta proxy), stop_run_scalp (intraday Turtle Soup), brooks_h2l2, micro_squeeze_pop, session_orb (Asia/London/NY), triple_confirm_scalp, fast_rsi_div_scalp, volume_climax_scalp, funding_crowd_reversal, ib_extension (Market Profile). All with ATR/floor stops + hard time stops. Registry: 100 → 112.
- **core/derivs.py**: perpetual funding-rate history/now, open interest, long/short ratio from OKX (Binance fallback), cached; attached to charts on ≤15m and used by funding_crowd_reversal + Fast Signals.
- **Library**: 9 new studied sources (Brooks, Volman, Raschke/Connors Street Smarts, Dalton, Crabel, Coulling, BVC/VPIN paper, perp-positioning research, 2026 1-minute backtest studies) with FA/EN lessons and where-in-app links.
- **Honest measurement** (50 000 bars BTC/ETH/SOL 5m–15m, realistic costs): every single scalp method alone loses (PF 0.2–0.9); ≥3-vote confluence + trend gate reaches PF ≈ 1.0–1.8 on few trades. The UI says so.
- **Stability**: chunked lazy VolumeItem + two-brush histograms (no 40k brush objects per Run), clean shutdown (engine/training stopped, workers awaited, gc.freeze after start-up, hard exit) → no more crash-on-exit.

## v1.2.1 — responsiveness round 2 (nothing removed)
Same 150 s stress test as v1.2.0 but now WITH the Live-Market engine streaming ~300 symbols, self-training on and repeated chart runs: worst UI freeze **8.7 s → 0.77 s**, p99 **432 ms → 49 ms**, p95 **44 → 6 ms**, zero crashes, empty `crash.log`, clean exit.
- **GIL switch interval 5 ms → 1 ms** (`main.py`): background numpy/pandas work (self-training, live analysis) no longer starves the GUI thread — the single biggest win.
- **Chart**: on every Run the old mouse/range handlers are disconnected before the plot is rebuilt (they were piling up → progressively slower mouse-move and "wrapped C/C++ object deleted" crashes); mouse crosshair throttled to 30 fps; guards against deleted plot items.
- **Live Market**: breadth (EMA50/200 over all symbols) cached 20 s and computed with a light numpy loop instead of pandas per symbol; market table updated **in place** (only changed cells, stable ordering re-ranked every 30 s, `Stretch` columns instead of `ResizeToContents`, fixed row height) and skipped while the page is hidden; timer 1.5 s → 3 s; live analysis loop yields CPU between symbols.
- **Thread safety**: bar-dict mutations in the live engine and the analysis copy are under the engine lock (avoids "dictionary changed size during iteration"/torn DataFrames crashes).
- **Self-training status** read by the UI every 5 s is now cached 60 s (was re-parsing a 1 MB `playbook.json`).
- New dev tool `tests/stress/ui_stress.py` (UI-lag percentiles + main-thread stall sampler) used to verify all of the above.

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
