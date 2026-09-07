# ◆ ProTrader Academy  |  آکادمی پروتریدر

A professional desktop trading-education & analysis platform (Python / PyQt6).
پلتفرم دسکتاپ حرفه‌ای آموزش و تحلیل ترید — دوزبانه (فارسی / English).

## نصب و اجرا  |  Install & Run
```bash
pip install -r requirements.txt
python main.py        # English
python main.py fa     # فارسی
```
Windows: double-click `run_windows.bat`  ·  Linux/macOS: `./run_linux_mac.sh`

Requires Python 3.10+ and internet (Binance public API for crypto, Yahoo Finance for forex/gold/stocks/indices). If offline, a synthetic demo dataset is used and clearly labelled.

## بخش‌ها  |  Modules
| Page | What it does |
|---|---|
| 🏠 Dashboard | Market pulse (trend / regime / volatility / RSI), top-performing strategies on the chosen symbol, lesson of the day |
| 📈 Chart & Signals | Interactive candlestick chart, strategy overlays, zones (FVG / OB / S&D), entry/stop/target of every signal, live parameter tuning |
| 📡 Market Scanner | Runs all 32 strategies across crypto, forex, commodities, indices, stocks and ranks fresh signals by a composite score (PF, win rate, R:R, confluence, freshness) |
| 🧪 Backtester | Event-driven backtest with realistic costs, fixed-fractional risk sizing, walk-forward (in-sample / out-of-sample) split, equity curve, trade list, CSV export, compare-all table |
| 🌐 Web Analyzer | Paste any trading-site URL (TradingView, articles, courses, signal sites). Fetches the page (with anti-bot fallback), extracts instruments, indicators/concepts (mapped to built-in strategies), explicit trading rules, price levels, sentiment, site capabilities, scam red-flags + trust score — then runs all strategies on the detected instruments for live signals |
| 🎓 Strategy Academy | Full bilingual documentation of every strategy: origin, rules, strengths, weaknesses, parameters |
| 🛡 Risk Manager | Position sizing, R-multiple targets, expectancy, Kelly, risk of ruin, breakeven win-rate table |
| 📓 Trade Journal | Log real trades with emotion tagging, auto R calculation and stats |

## ۴۲ استراتژی  |  55 built-in strategies
**Trend:** EMA Cross, Triple EMA pullback, Golden Cross, Supertrend+ADX, Ichimoku, Parabolic SAR, Turtle/Donchian, ADX/DMI, Hull MA
**Momentum:** MACD zero-line, Stoch RSI, RSI Divergence
**Mean-Reversion:** RSI+trend, Connors RSI(2), Bollinger Bounce, VWAP reversion
**Volatility / Volume:** TTM Squeeze, OBV breakout, MFI
**Price Action:** Pin Bar, Engulfing, Inside Bar, Morning/Evening Star, S/R Break & Retest, Fibonacci Golden Zone, Opening Range Breakout
**Smart Money / ICT:** Supply & Demand (RBR/DBD), Fair Value Gap, Order Block + BOS, Liquidity Sweep, Market Structure Shift (CHoCH), Wyckoff Spring, **ICT Silver Bullet**, **Power of Three (AMD)**
**Masters & quantified research:** Raschke Holy Grail, Raschke Anti, Larry Williams Volatility Breakout, Triple RSI, IBS+RSI, Turnaround Tuesday, Crabel NR7, False-Breakout Fade

## افزودن استراتژی خودت  |  Add your own strategy
Create a class in `strategies/`, subclass `Strategy`, implement `run(df) -> StrategyResult`, and add it to `ALL_STRATEGIES` in `strategies/__init__.py`. It instantly appears in every module.

## ⚠️ Disclaimer
Education & research only. Backtests are hypothetical. Past performance never guarantees future results. Most retail traders lose money.


## Phase 3 — Bot-ported strategies, Validation Lab & Robust Ensemble

**13 new strategies** (`strategies/bots.py`, `strategies/ensemble.py`), re-implemented from the most-used open-source bots and
TradingView scripts: freqtrade BinHV45, ClucMay72018, BbandRsi, ADXMomentum, MACD+CCI; paulcpk EMA-800 cross, Double-EMA+EMA200,
RSI-directional; NFI-lite protected dip (NostalgiaForInfinity idea); WaveTrend (LazyBear); Elder Impulse; Chandelier + Choppiness lock;
and the **★ Robust Ensemble**.

**Validation Lab** (`core/validation.py`, page 🧬): every strategy × 14 markets → full backtest, 3 walk-forward out-of-sample folds,
300-run Monte-Carlo trade shuffle → **Robustness Score 0–100** (weights OOS profit factor, fold consistency, cross-market consistency,
MC drawdown, trade count). Results are cached to `data/validation.json` and feed the Scanner (new "Robust" column, 25 % of score),
the Academy detail box, and the Ensemble.

**Robust Ensemble**: for the specific symbol/timeframe, uses only strategies whose OOS profit factor ≥ 1.1 on that very market; requires
≥ 2 agreeing within 3 bars, Choppiness < 60, no ATR spike; tightest member stop, 2R target. If nothing validated on a market
(e.g. EUR/USD 1h, GBP/USD 4h) it **abstains** — no trades rather than random ones.

Latest lab run (Sep 2026): robust (≥55) — BinHV45 66, NFI-lite 65, ICT Silver Bullet 62, Ensemble 60, ClucMay 55.
Failed (<25): Larry Williams vol-breakout, false-breakout, liquidity-sweep, pin-bar, ORB, NR7, Hull, BB-bounce, WaveTrend (too few trades), …

## Phase 4 — Indicators, ML Lab, whole-market live stream

- **71-indicator encyclopedia** (`core/indicators2.py`, Academy → "Indicator Encyclopedia"): KAMA, ALMA, T3, McGinley, Ehlers SuperSmoother,
  LinReg channel, Aroon, Vortex, TRIX, KST, Coppock, DPO, Schaff, Hurst, Efficiency Ratio, Choppiness, CMO, Ultimate, AO/AC, Fisher, RVI,
  Connors RSI, QQE, Squeeze Momentum, Elder Ray, Mass Index, Z-score, A/D, Chaikin, Force Index, EOM, VPT, NVI/PVI, Klinger, RVOL,
  Volume Profile (POC/VA), Heikin Ashi, ZigZag, Fib/Camarilla/Woodie pivots, HalfTrend, relative strength — each with bilingual
  "how computed / how to read / used by which strategies".
- **ML Lab** (`core/ml.py`, page 🧠): ≈90 scale-free features → HistGradientBoosting, triple-barrier labels (+2 ATR vs −1 ATR in H bars),
  purged walk-forward CV; shows OOS AUC / lift / calibration, feature-group importances, live P(long)/P(short), and meta-labels every
  strategy's recent signals (take / skip). Models saved in `data/models/`. Honest note: hourly BTC gave AUC 0.50 (no edge); NVDA 1d 0.55,
  Gold 1h 0.57 — small but real.
- **Live Market** (`core/live.py`, page ⚡): WebSocket to `data-stream.binance.vision` — every USDT pair's price each second
  (`!miniTicker@arr`) + kline streams for the top-N by volume; on each bar close the validated strategies + Ensemble run and fresh signals
  are pushed with a status-bar notification. Market breadth (% above EMA50/200, advancers/decliners) shown. No API key required.
  Any `XXX/USDT` symbol can now be opened on the Chart page.

## Phase 5 — High win-rate family + domain lock

`strategies/highwr.py` (8 strategies, category **High Win-Rate**): Connors RSI(2) classic, Cumulative RSI(2), Double 7, 3-Day High/Low,
IBS<0.2, RSI(2) dual-trend + persistence, BB-lower + RSI(2), and the High-WR composite. Implemented exactly as published: daily bars,
long-only above SMA200, **rule-based exits** (close > SMA5 / RSI(2) > 65) instead of fixed targets, wide disaster stop only, 10-bar time stop.
The backtester now supports `exit_long/exit_short` rule series and strategy-bundled `bt_kwargs`.

**Domain lock** (`core/validation.allowed`): Scanner and Live Market hide a strategy's signals on any market where it failed
out-of-sample in the Validation Lab (OOS PF < 1.0 / 1.1). This is what actually lifts the win rate — not "training".

Honest measured results (held-out last 25 % of validated markets, with domain lock, 1 036 trades):
family WR **67.9 %**, PF 1.67 — S&P/NVDA/AMD/META/GOOGL 70–87 %, MSFT 47–62 %, crypto 4h ~60 %.
On 13 blind markets **without** the lock: WR 62 %, PF 0.98 (break-even). Forex and hourly gold: ≈45 %, PF < 0.5 → locked out.

## Phase 6 — Timeframe Playbook (5m → 1d) + Advisor

`core/playbook.py`: every strategy × 6 timeframes × 4 asset groups (crypto / stocks-indices / commodities / forex), 3 walk-forward
OOS folds → `data/playbook.json` (WR, PF, trades, avg hold). Binance history extended (5m: 20 000 bars ≈ 70 d, 1h: 9 000 ≈ 1 y).
Result of the first build (proven = OOS PF ≥ 1.15, n ≥ 20): **5m 0/230 · 15m 1/164 · 30m 2/154 · 1h 7/235 · 4h 24/210 · 1d 55/187**.
Edge grows with timeframe; below 30 m nothing survives costs. Forex only proves out on 1d.

`core/advisor.py` + page 🎯: one symbol, all TFs in ~2 s (cached data): regime per TF (ADX + Choppiness), HTF bias, only playbook-proven &
non-locked strategies, freshness cutoff (≤ 2 bars), expected hold, minutes to next bar close, confidence, cross-TF verdict (or WAIT).
Scanner and Live Market now run only the playbook-proven strategies for the chosen timeframe (crypto 5m/15m → intentionally no signals).

## Phase 7 — Masters' Indicators: the inventors' ORIGINAL rules (`strategies/masters2.py`)
15 strategies that reproduce how the *creator* of each indicator actually used it — not the simplified "internet version":

| Master | Indicator | Original rule coded | Common misuse avoided |
|---|---|---|---|
| J. W. Wilder | DMI/ADX | Buy-stop at the HIGH of the +DI/−DI cross bar (extreme point), ADXR filter, exit at reverse extreme | Buying at the cross itself |
| George Lane | Stochastic | Trade only DIVERGENCE + %K/%D cross, ignore raw OB/OS | Selling at 80 / buying at 20 |
| Gerald Appel | MACD | Signal-line cross on the correct SIDE of zero, slow (19/39) trend filter | Every cross taken |
| John Bollinger | Bollinger Bands | W-bottom / M-top with %b confirmation + volume | Fading every band touch |
| Alexander Elder | Triple Screen | Weekly-tide (MACD-H) → daily wave (Force/Stoch) → intrabar trailing buy-stop | Single-timeframe oscillator |
| Bill Williams | Alligator + Fractals | Lips>Teeth>Jaw awake, break of fractal outside teeth, exit on line cross | Trading while Alligator sleeps |
| Stan Weinstein | Stage Analysis | Stage-2 breakout above rising 30-week MA with volume | Buying below declining MA |
| Mark Minervini | Trend Template | All 8 criteria + contraction breakout, 8% hard stop (long only) | Template used as a buy signal |
| William O'Neil | Cup & Handle | Pivot breakout + 40% volume surge, 7% stop (long only) | No volume, no stop |
| Marc Chaikin | CMF + Chaikin Osc | CMF persistence (>0 for N bars) + CO zero cross | Single-bar CMF sign |
| Tushar Chande | Aroon + CMO | Aroon-Up>70 & Down<30 with CMO momentum agreement | Aroon cross alone |
| Perry Kaufman | KAMA | Trade only when Efficiency Ratio is high, KAMA direction filter | Treating KAMA as a plain MA |
| Donald Lambert | CCI | ±100 BREAKOUT (trend entry) as Lambert defined; exit on return | CCI as OB/OS reversal |
| Larry Williams | %R | Exit after 5 bars or reverse; extreme-zone exit rule | Holding until opposite extreme |
| Martin Pring | KST | KST/signal cross + long-term KST slope filter | — |

Each carries FA/EN description + rules for the Academy, is validated (`data/validation.json`) and scored per timeframe in the Playbook.

## Phase 8 — Honesty layer, Forward Test, Self-Health (fixes for every known weakness)
| Weakness | Fix |
|---|---|
| Small samples looked great (PF 2.8 on 20 trades) | `core/stats.py`: Wilson CI for win-rate, bootstrap CI for PF/expectancy, t-stat, **Grade A/B/C/D** shown everywhere; the Advisor/Scanner rank by the **lower** confidence bound |
| Selection bias (~1900 tests → false "proven" edges) | Playbook gate is now n≥30 · PF lower-CI>1 · t≥2 · last-12-month PF≥0.9 (proven combos: 73 → **17**, 5 grade-A) |
| Idealised costs | `core/costs.py`: per-asset-class commission + half-spread + ATR-scaled slippage on stop fills (gap fills too) |
| Too few symbols per group | Playbook groups widened (6 crypto / 7 stocks / 4 commodities / 5 forex) |
| No forward test | `core/forward.py` + **Forward Test page**: every Advisor/Scanner/Live signal auto-recorded, resolved like the backtester, reality-vs-backtest gap, CI verdict |
| No portfolio logic | `core/portfolio.py`: correlation clustering, quarter-Kelly cap, total-risk cap; allocation table in Advisor |
| Chasing stale signals | Advisor "chase guard": >0.5R past signal close → flagged & discounted |
| Future problems | `core/health.py` + **Health page** (self-diagnosis, one-click fixes) and `core/maintenance.py` daemon (forward update 15 min, safe auto-fixes 6 h, playbook rebuild when stale) |
| Regressions | `tests/test_core.py` (all strategies, stats, costs, forward round-trip, portfolio, health) |

## Phase 9 — Curriculum: 15 bots + 30 books embedded (`strategies/bots2.py`, `core/quant.py`, `core/patterns.py`, `core/psychology.py`, `core/library.py`)
**Bots re-implemented as strategies:** Jesse (trend template), OctoBot (evaluator vote), Superalgos (LRC + BB squeeze), Hummingbot (Avellaneda–Stoikov fair-value reversion), Gekko (MACD persistence, DEMA), Zenbot (trend_ema), Grid bots (Pionex/Bitsgap/3Commas/chrisleekr), DCA safety-order bots (3Commas/MagiBot), Blackbird/ArbitrageBot (→ cointegration spread scanner), TensorTrade/FreqAI (→ transparent regime-adaptive ensemble + ML Lab). Freqtrade family was already ported.
**Books → code:**
- Murphy → `murphy_confirm`; Nison → `core/patterns.candlesticks` (26 patterns) + `nison_candles`; Bulkowski → `chart_patterns` with his failure-rate/avg-move stats + `bulkowski_patterns`; Elder → `elder_force2` (+ existing Triple Screen/Impulse); O'Neil → `oneil_canslim`; McAllen → S/R strategies.
- Chan → `core/quant.py` (ADF, Hurst, half-life, Engle–Granger, z-score pairs, multi-asset Kelly) + `chan_statarb`; López de Prado → CUSUM, fractional differentiation, bet sizing, **Deflated Sharpe**, **PBO (CSCV)**; Davey → WFE + incubation checklist; Johnson → cost model; Hilpisch/Weiming/Conlan/Järemo → architecture, MC, Kelly.
- Douglas / Steenbarger / Kahneman / Taleb / Bernstein / Day → `core/psychology.py`: pre-trade checklist, hard risk gates, **journal bias audit** (disposition, stop violation, revenge, martingale, luck-vs-skill t-test, tail events), Monte-Carlo risk of ruin.
**UI:** new **Quant Lab** page (Series · Pairs · Overfitting · Patterns · Psychology desk) and Academy ▸ **Library** tab mapping every book/bot to where it lives. Total strategies: **94**.

## Phase 10 — deepening the bot & book ports (100 strategies)

New modules
- `core/protections.py` — Freqtrade **Protections** re-implemented for the backtester: `CooldownPeriod`, `StoplossGuard`,
  `MaxDrawdown`, `LowProfitPairs` (candle-based lookback/lock like the docs). `run_backtest(..., protections=True)` or a
  strategy's `bt_kwargs["protections"]`; lock counts are returned in `stats["protection_locks"]`.
- `core/pairlist.py` — Freqtrade **Pairlist handlers/filters** on OHLCV: AgeFilter, VolatilityFilter, RangeStabilityFilter,
  SpreadFilter (H-L proxy), PriceFilter (tick ratio), VolumePairList top-N per asset class.
- `core/marketmaking.py` — Hummingbot **Avellaneda–Stoikov**: reservation price `r = s − qγσ²(T−t)`, optimal spread
  `γσ²(T−t) + (2/γ)ln(1+γ/κ)`, κ from trading intensity, fee-edge check; Pure-MM levels; **Blackbird** cross-venue
  spread_entry/spread_exit.
- `core/quant2.py` — Chan Kalman-filter hedge ratio & bands; de Prado triple-barrier, uniqueness/sample weights,
  sequential bootstrap; Davey **Monkey test** (random-entry benchmark) and trade-resampling Monte Carlo; Elder SafeZone,
  Impulse, 2%/6% rules; O'Neil sell rules; Steenbarger performance metrics; Jesse anchor-TF; OctoBot evaluator matrix.

New strategies (`strategies/bots3.py`): `chan_kalman`, `elder_impulse_safezone`, `jesse_anchor`, `oneil_sell_rules`,
`freqtrade_sample` (SampleStrategy + ROI/stop), `davey_robust` (protections ON).

UI
- Quant Lab ▸ Overfitting: Monkey test, MC return/drawdown distribution, "with Freqtrade protections" comparison;
  two new incubation checks.
- Quant Lab ▸ **Bot desk** (new tab): pairlist report for the whole universe, A-S quotes with γ/inventory/fee inputs,
  OctoBot weighted matrix, Blackbird spread readout.
- Journal: **Steenbarger performance review** (by setup / emotion / weekday, top-10% concentration, worst streak).

Phase-10 honest results (strict CI grades, all markets): `oneil_sell_rules` C on 1d stocks (WR 50, PF 1.86, n 62) and
4h/30m crypto; `jesse_anchor` C on 4h crypto (PF 1.21, n 421); `davey_robust` not proven (score 52); `chan_kalman`,
`elder_impulse_safezone`, `freqtrade_sample` low scores (31–37) — kept in the library as faithful references, the
playbook & advisor will not recommend them.

## Phase 11 — AI layer: Chart Vision + AI Desk (`core/vision.py`, `core/forecast.py`, `core/sentiment.py`, `core/rl.py`, `core/engines.py`)
What was studied and what was ported (pure numpy/sklearn core; heavy libraries auto-enabled when installed):

| Area | Libraries studied | What the bot learned | Optional heavy path |
|---|---|---|---|
| **Chart Vision** (page 👁) | YOLO, OpenCV+PyTorch, Detectron2 | OpenCV candle segmentation → OHLC reconstruction → numeric pattern library + FA/EN explanation; self-test model card; price calibration | `data/models/chart_yolo.pt` (ultralytics) |
| **Forecast** (AI Desk tab) | Prophet, NeuralProphet, Darts, Kats, sktime, GluonTS, PyTorch-Forecasting (N-BEATS) | naive / drift / SES / Holt / Theta / Prophet-like (piecewise trend + changepoints + damping) / N-BEATS-like MLP & ridge / quantile GBR; **rolling-origin backtest with MASE vs naive** and direction p-value; CUSUM changepoints | — |
| **Sentiment** (AI Desk tab) | VADER, TextBlob, FinBERT, Flair, Stanza, FinGPT | VADER-style rule engine + Loughran-McDonald finance lexicon, subjectivity, ticker extraction, RSS headline fetch, crowd-extremity contrarian flag | `transformers` + ProsusAI/finbert |
| **RL agent** (AI Desk tab) | TensorTrade, Stable-Baselines3, RLlib, Intel Coach | Gym-style `TradingEnv` (window features, costs, log-return or differential-Sharpe reward), linear Q-learning & REINFORCE agents, time split + early stopping on validation, comparison with buy&hold and **95th percentile of random agents** | `stable_baselines3` + `gymnasium` (`rl.sb3_backend`) |
| **Engines** (AI Desk tab) | LEAN/QuantConnect, Zipline, Backtrader, FreqAI | Backtrader-style event engine (next-bar fills, brackets, risk sizer, SQN analyzer), **parity check** vs the vectorised backtester (equal trade count, return gap < 1% on tested strategies), Zipline pipeline ranks, Zipline slippage models, LEAN Alpha→Portfolio→Risk→Execution framework, FreqAI retrain schedule | — |

Verdict shown in the UI is always relative to a baseline: on liquid crypto 1h data the forecasting models mostly do **not** beat naive and the RL agents do **not** beat buy&hold/random-p95 — the app says so instead of pretending.
