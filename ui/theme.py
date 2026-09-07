"""Dark professional theme (TradingView-like) + i18n strings."""

C = {
    "bg": "#0b0e14",
    "panel": "#131722",
    "panel2": "#1a1f2e",
    "border": "#2a2e39",
    "text": "#d1d4dc",
    "muted": "#787b86",
    "accent": "#2962ff",
    "accent2": "#00bcd4",
    "green": "#26a69a",
    "red": "#ef5350",
    "yellow": "#ffb74d",
    "purple": "#ab47bc",
}

QSS = f"""
* {{ font-family: 'Segoe UI', 'Vazirmatn', 'Inter', 'Helvetica Neue', Arial, sans-serif; font-size: 13px; }}
QMainWindow, QWidget {{ background: {C['bg']}; color: {C['text']}; }}
QLabel {{ background: transparent; }}
QCheckBox {{ background: transparent; }}
QFrame#sidebar {{ background: {C['panel']}; border-right: 1px solid {C['border']}; }}
QFrame#card {{ background: {C['panel']}; border: 1px solid {C['border']}; border-radius: 10px; }}
QFrame#card2 {{ background: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 8px; }}
QLabel#title {{ font-size: 22px; font-weight: 700; color: white; }}
QLabel#subtitle {{ font-size: 13px; color: {C['muted']}; }}
QLabel#h2 {{ font-size: 16px; font-weight: 600; color: white; }}
QLabel#stat {{ font-size: 20px; font-weight: 700; }}
QLabel#statlbl {{ font-size: 11px; color: {C['muted']}; text-transform: uppercase; letter-spacing: 1px; }}
QLabel#brand {{ font-size: 18px; font-weight: 800; color: white; padding: 6px; }}
QPushButton {{ background: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 7px 14px; color: {C['text']}; }}
QPushButton:hover {{ background: #232a3b; border-color: {C['accent']}; }}
QPushButton:pressed {{ background: {C['accent']}; }}
QPushButton#primary {{ background: {C['accent']}; border: none; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: #3d74ff; }}
QPushButton#primary:disabled {{ background: #2a3350; color: #7a85a8; }}
QPushButton#nav {{ text-align: left; padding: 11px 16px; border: none; border-radius: 8px; background: transparent; font-size: 14px; color: {C['muted']}; }}
QPushButton#nav:hover {{ background: {C['panel2']}; color: white; }}
QPushButton#nav:checked {{ background: {C['accent']}; color: white; font-weight: 600; }}
QPushButton#chip {{ padding: 4px 10px; border-radius: 12px; font-size: 12px; }}
QPushButton#chip:checked {{ background: {C['accent']}; color: white; border-color: {C['accent']}; }}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {{
    background: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 6px; padding: 6px 8px; color: {C['text']};
    selection-background-color: {C['accent']}; }}
QComboBox:hover, QLineEdit:hover {{ border-color: {C['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {C['panel2']}; border: 1px solid {C['border']}; selection-background-color: {C['accent']}; outline: none; }}
QTableWidget, QTableView {{ background: {C['panel']}; alternate-background-color: {C['panel2']}; gridline-color: {C['border']};
    border: 1px solid {C['border']}; border-radius: 8px; selection-background-color: #1e3a8a; }}
QHeaderView::section {{ background: {C['panel2']}; color: {C['muted']}; padding: 6px; border: none; border-bottom: 1px solid {C['border']}; font-weight: 600; }}
QTableWidget::item {{ padding: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {C['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {C['border']}; border-radius: 5px; min-width: 30px; }}
QProgressBar {{ background: {C['panel2']}; border: none; border-radius: 4px; height: 6px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {C['accent']}; border-radius: 4px; }}
QTabWidget::pane {{ border: 1px solid {C['border']}; border-radius: 8px; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {C['muted']}; padding: 8px 16px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: white; border-bottom: 2px solid {C['accent']}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {C['border']}; background: {C['panel2']}; }}
QCheckBox::indicator:checked {{ background: {C['accent']}; border-color: {C['accent']}; }}
QSplitter::handle {{ background: {C['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QToolTip {{ background: {C['panel2']}; color: white; border: 1px solid {C['border']}; padding: 6px; }}
QStatusBar {{ background: {C['panel']}; color: {C['muted']}; border-top: 1px solid {C['border']}; }}
QGroupBox {{ border: 1px solid {C['border']}; border-radius: 8px; margin-top: 10px; padding-top: 8px; color: {C['muted']}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
QSlider::groove:horizontal {{ height: 4px; background: {C['border']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; margin: -5px 0; background: {C['accent']}; border-radius: 7px; }}
"""

# ---------------- i18n ----------------
STR = {
    "en": {
        "app": "ProTrader Academy",
        "nav_dash": "Dashboard",
        "nav_chart": "Chart & Signals",
        "nav_scan": "Market Scanner",
        "nav_bt": "Backtester",
        "nav_web": "Web Analyzer",
        "nav_advisor": "Advisor (all TFs)",
        "nav_forward": "Forward Test", "nav_health": "Health",
        "nav_quant": "Quant Lab", "acad_tab_lib": "Library: 30 books · 15 bots", "lib_sub": "Every book and bot from the curriculum, the lesson extracted from it, and exactly where that lesson is implemented in this app. Double-check any claim by opening the referenced strategy or page.", "lib_title_c": "Title", "lib_author": "Author", "lib_group": "Group", "lib_lesson": "Lesson embedded", "lib_where": "Where in the app", "search": "search…",
        "ql_title": "Quant Lab — Chan · López de Prado · Davey · Bulkowski · Nison · Douglas",
        "ql_sub": "Tools from the reading list, applied to any symbol: is the series mean-reverting or trending (ADF, Hurst, half-life)? Which pairs cointegrate? Is a strategy's backtest overfit (Deflated Sharpe, PBO, Walk-Forward Efficiency, Davey's incubation)? Which chart/candle patterns are live and what did they historically do? And the psychology desk: pre-trade checklist, hard risk gates, journal bias audit.",
        "j_steen_title": "Steenbarger performance review", "j_steen_group": "Group", "j_weekday": "Weekday",
        "j_steen_empty": "Log trades to see which setups, emotional states and weekdays actually make (or lose) your money.",
        "j_steen_read": "Top-10% trades produce {top:.0f}% of gross profit (>60% = P&L depends on rare outliers — Taleb). Worst losing streak: {streak}. Steenbarger: trade the states and setups with positive expectancy; shrink size in the others.",
        "nav_vision": "Chart Vision", "vis_title": "Chart Vision — understand a chart IMAGE", 
        "vis_sub": "Drop a screenshot or photo of any candlestick chart (TradingView, MetaTrader, Binance, light or dark). The engine segments the candles with OpenCV, rebuilds the OHLC series, then runs the same Nison/Bulkowski pattern logic, trend and S/R analysis used on live data — and explains it. Optional: enter the top & bottom price of the visible axis to get real price levels. Self-test shows measured accuracy on synthetic charts.",
        "vis_open": "Open image", "vis_paste": "Paste from clipboard", "vis_demo": "Random demo chart", "vis_selftest": "Self-test (model card)", "vis_cal": "Axis calibration:", "vis_cal_top": "top", "vis_cal_bot": "bottom", "vis_apply": "Apply",
        "vis_candles": "Candles found", "vis_theme": "Theme", "vis_last": "Last candle", "vis_conf": "Colour confidence", "vis_drop": "⬇ drop a chart image here, or use the buttons above", "vis_recon": "Reconstructed OHLC (what the engine 'sees')",
        "vis_explain": "Explanation", "vis_patterns": "Patterns detected", "vis_pattern": "Pattern", "vis_kind": "Kind", "vis_where": "Where", "vis_stat": "Direction / stat", "vis_modelcard": "Model card — extraction accuracy on synthetic charts", "vis_found": "found / true", "vis_diracc": "direction acc.", "vis_corr": "close corr.",
        "vis_up": "UP", "vis_down": "DOWN", "vis_range": "RANGE", "vis_candle_pat": "candle (Nison)", "vis_chart_pat": "chart (Bulkowski)", "vis_noclip": "No image in clipboard.", "vis_fail": "Could not read candles from this image. Tips: crop to the price pane, avoid heavy overlays, use a larger screenshot.",
        "ql_tab_bots": "Bot desk", "ql_monkey": "Monkey test (Davey)", "ql_mc_ret": "MC return p5…med…p95", "ql_mc_dd": "MC drawdown", "ql_prot": "With Freqtrade protections",
        "ql_bots_hint": "Freqtrade pairlist filters applied to the whole watch-list (Age · Volatility · RangeStability · Spread · Price · VolumePairList top-20); Hummingbot Avellaneda–Stoikov reservation price & optimal spread for the selected symbol (with fee edge check); Blackbird cross-venue spread; OctoBot weighted evaluator matrix. Analysis only — nothing is quoted or traded.",
        "ql_bots_run": "Run bot desk", "ql_as_gamma": "γ risk factor", "ql_as_inv": "Base inventory", "ql_as_fee": "Fee / side",
        "ql_as_res": "Reservation price (A-S)", "ql_as_spread": "Optimal spread", "ql_as_edge": "MM edge", "ql_as_after_fees": "after round-trip fees",
        "ql_pl_kept": "Kept", "ql_pl_reason": "Filter", "ql_pl_title": "Freqtrade pairlist (this timeframe)",
        "ql_octo_title": "OctoBot evaluator matrix (−1 bullish … +1 bearish)", "ql_octo_eval": "Evaluator", "ql_octo_val": "Value", "ql_octo_w": "Weighted", "ql_octo_avg": "Weighted average → state",
        "ql_bots_read": "<b>Pairlist:</b> {kept}/{total} symbols pass Freqtrade's filters at this timeframe — the scanner should only spend strategies on these. <b>Blackbird</b> (demo second venue ±5 bps): best net spread {bb_net:+.2f}% (long {bb_long} / short {bb_short}) — below the 0.8% entry threshold means no arbitrage. <b>Monkey test</b> in the Overfitting tab: a strategy must beat the 95th percentile of random entries with the same trade count and holding time.",
        "ql_tab_series": "Series (Chan/de Prado)", "ql_tab_pairs": "Pairs & spreads", "ql_tab_overfit": "Overfitting test", "ql_tab_patterns": "Patterns (Bulkowski/Nison)", "ql_tab_psy": "Psychology desk",
        "ql_analyze": "Analyze series", "ql_half_life": "Half-life", "ql_regime": "Nature of series", "ql_stationary": "stationary", "ql_corr_price": "corr. with price (memory kept)",
        "ql_mr": "MEAN-REVERTING", "ql_mom": "TRENDING", "ql_rw": "random walk", "ql_meaning": "Meaning:",
        "ql_mr_adv": "Hurst < 0.45 and ADF rejects a unit root → Bollinger/z-score reversion strategies are statistically justified here; use look-back ≈ half-life (Chan ch.2–3).",
        "ql_mom_adv": "Hurst > 0.55 → the series trends more than a random walk; breakout / momentum strategies have the statistical edge, mean-reversion will bleed (Chan ch.6).",
        "ql_rw_adv": "Neither test is convincing → this series behaves like a random walk at this timeframe; no linear strategy has a structural edge. Trade only proven playbook setups or stay flat.",
        "ql_scan_pairs": "Scan pairs", "ql_pairs_hint": "Engle–Granger cointegration on log prices for all pairs in the category (Chan ch.3; the same spread logic Blackbird/ArbitrageBot use across exchanges). A tradeable pair needs ADF < −2.86, half-life short (< 60 bars) and |z| > 2 for an entry: long the spread = buy A, sell β×B.",
        "ql_coint": "Cointegrated", "ql_signal": "Spread signal", "ql_not_tradeable": "not cointegrated", "ql_running": "running…",
        "ql_test_overfit": "Test for overfitting", "ql_overfit_hint": "López de Prado: with ~2000 strategy trials, the best backtest Sharpe is expected to be high BY LUCK. Deflated Sharpe = probability the observed Sharpe beats that luck level. PBO = probability the parameter set that looks best in-sample underperforms the median out-of-sample (CSCV over 16 perturbed parameter sets). Davey: Walk-Forward Efficiency ≥ 50% and his incubation checklist before any live money.",
        "ql_incubation": "Davey incubation", "ql_check": "Check", "ql_pass": "Pass", "ql_go": "GO (incubate live)", "ql_nogo": "NO-GO",
        "ql_overfit_read": "Reading: Deflated-Sharpe probability {dsr:.0f}% (≥95% is significant; SR expected from luck alone ≈ {sr0:.2f}). PBO {pbo:.0f}% (<30% good, >50% = the parameters are fitted to noise).",
        "ql_scan_patterns": "Scan patterns", "ql_patterns_hint": "Bulkowski's identification rules + his published bull-market statistics (break-even failure rate, average move, performance rank of 39 patterns) and Nison's 26 candle patterns with Bulkowski's measured reversal rates. Target = measure rule (pattern height).",
        "ql_chart_patterns": "Chart patterns near breakout", "ql_candles": "Candle patterns (last 10 bars)", "ql_pattern": "Pattern", "ql_level": "Breakout level", "ql_confirmed": "Confirmed", "ql_fail_rate": "Fail rate", "ql_avg_move": "Avg move", "ql_rank": "Rank", "ql_pending": "pending", "ql_bar": "Bar", "ql_rev_rate": "Reversal rate",
        "ql_checklist": "Pre-trade checklist (Douglas · Elder · Steenbarger · Kahneman · Taleb)", "ql_cleared": "cleared to trade", "ql_not_cleared": "do NOT place the trade",
        "ql_gates": "Hard gates (Steve Day / prop-firm): ≤1% per trade · ≤3% total open risk · stop for the day at −3% · 24h cooldown after 3 consecutive losses. The Advisor's allocator enforces the first two automatically.",
        "ql_ror": "Risk of ruin (Bernstein MC)", "ql_ror_res": "P(losing 50% of equity within 500 trades) = {:.1f}%. At {:.1f}% risk it would be {:.1f}%. Ruin is a function of size, not of the strategy.",
        "ql_audit": "Journal bias audit (numbers, not sermons)", "ql_audit_run": "Audit my journal + forward-test trades", "ql_audit_empty": "No trades yet — add journal entries or let the forward test collect.",

        "fw_title": "Forward Test — reality grades the backtests",
        "fw_sub": "Every fresh Advisor / Scanner signal is recorded automatically. The bot then follows the next candles and resolves each one exactly like the backtester (gap → stop, stop before target, 200-bar time stop). After 30+ closed records the confidence interval tells you whether the edge is real. Nothing is traded.",
        "fw_update": "Update outcomes", "fw_clear": "Clear log", "fw_clear_q": "Delete all forward-test records?", "fw_auto": "auto-update every 15 min",
        "fw_verdict": "Verdict", "fw_closed_open": "Closed / Open", "fw_gap": "Reality ÷ Backtest (PF)", "fw_need10": "need ≥10 closed",
        "fw_by_strategy": "By strategy (realised)", "fw_by_tf": "By timeframe", "fw_expected": "Backtest expected", "fw_grade": "Grade",
        "fw_records": "Records (double-click → chart)", "fw_status": "Status", "fw_signal_bar": "Signal bar", "fw_exit": "Exit", "fw_reason": "Reason", "fw_source": "Source",
        "fw_open": "open", "fw_closed_s": "closed", "fw_last": "last update:", "fw_updated": "checked {} open · closed {}",
        "fw_v_collecting": "collecting (<30)", "fw_v_confirmed": "EDGE CONFIRMED", "fw_v_positive": "positive, unconfirmed", "fw_v_none": "NO EDGE",
        "hl_title": "Health — self-diagnosis & auto-fix",
        "hl_sub": "The bot checks its own data feeds, playbook age, edge decay, unvalidated strategies, stale forward-test records and crashing strategies — and fixes what it can with one click.",
        "hl_quick": "Quick check", "hl_full": "Full check (downloads data)", "hl_fix_all": "Fix everything", "hl_state": "State", "hl_errors": "Errors", "hl_warns": "Warnings", "hl_infos": "Notes",
        "hl_last": "Last check", "hl_running": "checking…", "hl_done": "check complete", "hl_fixing": "fixing", "hl_bad": "needs attention", "hl_ok_warn": "OK with warnings", "hl_good": "healthy", "hl_none": "No issues found.",
        "hl_maint": "Auto-maintenance log (runs in background: forward update 15 min · safe fixes 6 h · playbook 7 d)", "hl_maint_none": "nothing yet",
        "adv_chase": "Price already moved more than 0.5R past the signal close — entering now is worse than what was backtested. Wait for a pullback or skip.",
        "adv_pb_gate": "gate: n≥30 · PF lower-CI>1 · t≥2 · last-year PF≥0.9", "grade": "Grade", "ci": "95% CI", "need_n": "trades needed for ±8% WR certainty", "adv_alloc": "Portfolio allocation (if you took every signal above)", "adv_take": "take", "adv_skip": "skip", "adv_risk": "risk %", "adv_units": "units", "adv_reason": "note",
        "adv_recorded": "recorded to Forward Test", "adv_grade_hint": "Grade A = n≥100 & PF lower-CI>1.1 & t≥3 · B = n≥50 · C = n≥30 · D = noise. Numbers in brackets are the 95% lower confidence bound — trust those, not the point estimate.",
        "dash_health": "Bot health", "dash_forward": "Forward test",

        "adv_title": "🎯 Advisor — right strategy, right timeframe, right moment",
        "adv_sub": "For one symbol the bot checks 5m → 1d in ~2 s: regime per timeframe, then ONLY the strategies proven out-of-sample on that timeframe & asset class (Timeframe Playbook) and not domain-locked. Stale signals are discarded, a higher-timeframe bias filter is applied, and you get delivery info: expected holding time and minutes until the next bar closes (the next decision point). If nothing proven fires, the honest answer is WAIT.",
        "adv_run": "Advise now", "adv_rebuild": "Rebuild Timeframe Playbook (~6 min)", "adv_running": "analysing…", "adv_pb_done": "playbook rebuilt",
        "adv_verdict": "Verdict", "adv_htf": "Higher-TF bias", "adv_fastest": "Fastest TF with signal", "adv_best_tf": "Best TF", "adv_elapsed": "Answer time",
        "adv_regime": "Regime", "adv_pb_wr": "Proven WR (TF)", "adv_pb_pf": "Proven PF (TF)", "adv_hold": "Expected hold", "adv_next": "Next bar close",
        "adv_wait": "WAIT", "adv_trend": "trend", "adv_range": "range", "adv_mixed": "mixed", "adv_flat": "nothing proven on this TF → flat", "adv_no_fresh": "no fresh signal",
        "adv_rule_exit": "rule exit (SMA5/RSI)", "adv_playbook": "Timeframe Playbook — what the bot learned about each timeframe (OOS, 4 asset groups)",
        "adv_proven": "proven (n≥30 · PF lower-CI>1 · t≥2)", "adv_no_pb": "Playbook not built yet — click Rebuild.",
        "nav_live": "Live Market", "nav_ml": "ML Lab",
        "live_title": "⚡ Live Market — the whole exchange, in real time",
        "live_sub": "One WebSocket streams every Binance USDT pair (≈170–480 symbols, no API key). The top-N by volume also stream candles; on every bar close the validated strategies (Validation-Lab score ≥ threshold) and the Ensemble run instantly, and fresh signals appear here with a notification. Breadth tiles show how healthy the market is before you take any long.",
        "live_start": "Start streaming", "live_stop": "Stop", "live_idle": "idle", "live_stopped": "stopped", "live_topn": "Top N by volume", "live_use_ml": "ML P(win)",
        "live_t_symbols": "Watched / all", "live_t_ticks": "Ticks received", "live_t_breadth": "% > EMA50 / EMA200", "live_t_adv": "Advancers / decliners", "live_t_signals": "Live signals",
        "live_signals_card": "Real-time validated signals (double-click → chart)", "live_market_card": "Whole market (live prices)", "live_now": "Now", "live_vol24": "24h volume", "time": "Time",
        "ml_title": "🧠 ML Lab — the bot learns from the market itself",
        "ml_sub": "≈90 scale-free features (every indicator in the encyclopedia) → gradient-boosting model predicting whether a +2×ATR target is hit before a −1×ATR stop within H bars (triple-barrier labels). Trained with purged walk-forward folds, so every metric shown is OUT-OF-SAMPLE. It also 'meta-labels' strategy signals: P(win) of each signal given current market context.",
        "ml_train": "Train on this market", "ml_load": "Load saved model", "ml_horizon": "Horizon (bars)", "ml_training": "Training…",
        "ml_hint": "Pick a symbol/timeframe and train. Typical honest results: AUC 0.52–0.58. Anything above 0.60 on hourly crypto is suspicious (leakage), not genius.",
        "ml_p_long": "P(long wins) now", "ml_p_short": "P(short wins) now", "ml_lift": "Lift top-20%", "ml_base": "Base rate L / S", "ml_samples": "Samples",
        "ml_learned": "What the model learned (feature importance, OOS permutation)", "ml_calib": "Calibration (predicted vs actual, OOS)", "ml_meta": "Meta-labeled strategy signals (last 5 bars)",
        "ml_pred": "Predicted", "ml_actual": "Actual", "ml_verdict": "OK?", "ml_advice": "Advice", "ml_take": "✔ take", "ml_skip": "✘ skip", "ml_neutral": "~ neutral",
        "ml_v_noise": "✘ No edge found: model is indistinguishable from noise on this market. Do not use its probabilities here.",
        "ml_v_weak": "~ Weak but real edge: use only as a filter (skip signals with P(win) below base rate).",
        "ml_v_ok": "✔ Meaningful edge out-of-sample. Still small — combine with validated strategies and strict risk.",
        "ml_saved": "Saved models", "ml_none": "No saved model for this symbol/timeframe — train one first.",
        "acad_tab_strats": "Strategies", "acad_tab_inds": "Indicator Encyclopedia (71)",
        "ind_how": "How it is computed", "ind_read": "How to read & trade it", "ind_used": "Used by strategies", 
        "ind_ml_note": "This indicator is also one of the ≈90 features the ML Lab model learns from.",
        "nav_lab": "Validation Lab",
        "lab_title": "🧬 Validation Lab — which strategies actually survive?",
        "lab_sub": "Every strategy is re-tested on 14 markets with walk-forward out-of-sample folds and a Monte-Carlo trade shuffle. The Robustness Score (0–100) rewards out-of-sample profit factor, consistency across folds and markets, low simulated drawdown and enough trades — NOT in-sample return. Scores ≥ 55 are considered robust; the ★ Ensemble strategy only trades on the confluence of validated strategies for the specific market.",
        "lab_run": "Run full validation (≈4 min)", "lab_run_sel": "Re-validate selected", "lab_running": "Validating…", "lab_last": "Last run:",
        "lab_t_validated": "Validated", "lab_t_robust": "Robust (≥55)", "lab_t_fail": "Failed (<25)", "lab_t_ens": "Ensemble score",
        "lab_score": "Robustness", "lab_verdict": "Verdict", "lab_oos_pf": "OOS PF", "lab_oos_pos": "OOS folds +", "lab_mc_dd": "MC DD 95%",
        "lab_markets": "Markets", "lab_best": "Best markets (OOS)", "lab_detail": "Per-market breakdown (double-click a row to open on best market)",
        "lab_oos_folds": "OOS PF fold 1·2·3", "lab_not_run": "not run",
        "lab_v_robust": "✔ Robust", "lab_v_ok": "~ Usable with filters", "lab_v_weak": "⚠ Weak", "lab_v_fail": "✘ Failed",
        "lab_expl": "OOS = out-of-sample: the strategy was scored only on data it had no chance to be fitted to. MC DD 95% = the drawdown you should expect in 1 of 20 unlucky orderings of the same trades. A strategy that is green everywhere here is still not a guarantee — but one that is red here should not be traded.",
        "robust": "Robust", "return": "Return", "max_dd": "Max DD",
        "nav_academy": "Strategy Academy",
        "nav_risk": "Risk Manager",
        "nav_journal": "Trade Journal",
        "nav_settings": "Settings",
        "symbol": "Symbol", "timeframe": "Timeframe", "strategy": "Strategy", "load": "Load", "run": "Run",
        "loading": "Loading data…", "ready": "Ready", "category": "Category", "all": "All",
        "signals": "Recent Signals", "time": "Time", "side": "Side", "price": "Price", "stop": "Stop", "target": "Target",
        "rr": "R:R", "long": "LONG", "short": "SHORT", "no_signal": "No signal on last bar",
        "last_signal": "Latest signal", "bars_ago": "bars ago",
        "scan": "Scan Market", "scanning": "Scanning…", "scan_hint": "Runs only the strategies PROVEN on this timeframe & asset class (Timeframe Playbook) on every symbol and lists fresh signals (last N bars). Domain-locked strategies are hidden.",
        "recent_bars": "Signals within last N bars", "min_pf": "Only strategies with historical PF ≥",
        "bt_run": "Run Backtest", "capital": "Initial capital", "risk": "Risk / trade %", "comm": "Commission (bps)",
        "trades": "Trades", "winrate": "Win rate", "pf": "Profit factor", "ret": "Net return", "dd": "Max drawdown",
        "sharpe": "Sharpe", "avg_r": "Avg R", "expect": "Expectancy", "equity": "Equity curve", "trade_list": "Trade list",
        "compare": "Compare all strategies", "comparing": "Comparing…",
        "entry": "Entry", "exit": "Exit", "pnl": "PnL", "r_mult": "R", "bars": "Bars", "reason": "Reason",
        "difficulty": "Difficulty", "author": "Origin", "rules": "Entry rules", "pros": "Strengths", "cons": "Weaknesses",
        "desc": "Description", "params": "Parameters", "reset": "Reset", "apply": "Apply & Re-run",
        "equity_now": "Account equity", "risk_pct": "Risk per trade (%)", "entry_px": "Entry price", "stop_px": "Stop price",
        "leverage": "Leverage", "calc": "Calculate", "units": "Position size (units)", "notional": "Notional value",
        "margin": "Margin required", "risk_amt": "Amount at risk", "dist": "Stop distance",
        "ror": "Risk of ruin (50% DD)", "kelly": "Kelly %", "losses_to_half": "Consecutive losses to -50%",
        "targets": "Targets", "wr_input": "Expected win rate %", "rr_input": "Avg R:R",
        "j_add": "Add trade", "j_del": "Delete selected", "j_notes": "Notes / lesson", "j_export": "Export CSV",
        "j_stats": "Journal stats", "date": "Date", "result": "Result", "emotion": "Emotion",
        "lang": "Language", "theme": "Theme", "data_src": "Data source", "cache_clear": "Clear data cache",
        "about": "About", "disclaimer": ("This software is for education and research only. Backtests are hypothetical, "
                                        "include simplifying assumptions, and past performance never guarantees future results. "
                                        "Most retail traders lose money. Never risk money you cannot afford to lose."),
        "welcome": "Welcome back, trader",
        "welcome_sub": "94 strategies · 15 bots ported · 30 books embedded · Quant Lab · Forward Test · Self-Health · CI-graded Playbook 5m→1d · Advisor + Portfolio · 71 indicators · Whole-market live stream · ML Lab · Validation Lab · Ensemble · Backtester · Academy",
        "quick": "Quick start", "top_strats": "Top strategies on this symbol (backtest)", "market_pulse": "Market pulse",
        "trend": "Trend", "regime": "Regime", "vol": "Volatility (ATR%)", "rsi": "RSI(14)", "change": "24h change",
        "bull": "Bullish", "bear": "Bearish", "range": "Ranging", "trending": "Trending", "high": "High", "low": "Low", "normal": "Normal",
        "lesson": "Lesson of the day",
        "tip_title": "Golden rules",
        "tips": ["Risk max 1–2% of equity per trade — survival first.",
                 "A strategy without a backtest is a guess. A backtest without out-of-sample data is a lie.",
                 "Win rate means nothing without R:R. 35% WR with 1:3 R:R is very profitable.",
                 "Trend strategies lose in ranges; mean-reversion loses in trends. Know the regime.",
                 "Journal every trade. Your journal is your real mentor.",
                 "Higher timeframe bias + lower timeframe entry = the professional pattern.",
                 "If it feels exciting, your position is too big."],
        "wf": "Walk-forward split (%)", "in_sample": "In-sample", "out_sample": "Out-of-sample",
        "export_trades": "Export trades CSV", "no_data": "Failed to load data", "offline": "Offline (synthetic demo data)",
        "long_only": "Long only", "breakeven": "Move stop to BE at 1R",
        "score": "Score", "fresh": "Fresh", "conf": "Confluence",
    },
    "fa": {
        "app": "آکادمی پروتریدر",
        "nav_dash": "داشبورد",
        "nav_chart": "چارت و سیگنال‌ها",
        "nav_scan": "اسکنر بازار",
        "nav_bt": "بک‌تستر",
        "nav_web": "تحلیل‌گر وب",
        "nav_advisor": "مشاور (همهٔ تایم‌ها)",
        "nav_forward": "تست پیش‌رو", "nav_health": "سلامت ربات",
        "nav_quant": "آزمایشگاه کوانت", "acad_tab_lib": "کتابخانه: ۳۰ کتاب · ۱۵ بات", "lib_sub": "هر کتاب و بات برنامهٔ درسی، درسی که از آن استخراج شده، و دقیقاً جایی که آن درس در این برنامه پیاده شده است. هر ادعا را با باز کردن استراتژی یا صفحهٔ ارجاع‌شده بررسی کنید.", "lib_title_c": "عنوان", "lib_author": "نویسنده", "lib_group": "گروه", "lib_lesson": "درس پیاده‌شده", "lib_where": "کجای برنامه", "search": "جستجو…",
        "ql_title": "آزمایشگاه کوانت — چان · لوپز د پرادو · دیوی · بالکوفسکی · نیسون · داگلاس",
        "ql_sub": "ابزارهای فهرست کتاب‌ها روی هر نماد: سری بازگشتی است یا روندی (ADF، هرست، نیمه‌عمر)؟ کدام جفت‌ها هم‌انباشته‌اند؟ بک‌تست یک استراتژی بیش‌برازش دارد (شارپ تعدیل‌شده، PBO، کارایی واک‌فوروارد، چک‌لیست دیوی)؟ کدام الگوهای نموداری/کندلی زنده‌اند و در تاریخ چه کرده‌اند؟ و میز روان‌شناسی: چک‌لیست پیش از معامله، دروازه‌های سخت ریسک، ممیزی سوگیری ژورنال.",
        "j_steen_title": "بازبینی عملکرد استینبارگر", "j_steen_group": "گروه", "j_weekday": "روز هفته",
        "j_steen_empty": "معاملات را ثبت کنید تا ببینید کدام ستاپ‌ها، حالت‌های هیجانی و روزهای هفته واقعاً برایتان پول می‌سازند (یا می‌سوزانند).",
        "j_steen_read": "۱۰٪ معاملات برتر {top:.0f}٪ از سود ناخالص را ساخته‌اند (>۶۰٪ = سود وابسته به چند رخداد نادر — طالب). بدترین رشتهٔ باخت: {streak}. استینبارگر: فقط حالت‌ها و ستاپ‌های با امید ریاضی مثبت را معامله کن؛ در بقیه حجم را کم کن.",
        "nav_vision": "بینایی نمودار", "vis_title": "بینایی نمودار — درک تصویر نمودار",
        "vis_sub": "اسکرین‌شات یا عکس هر نمودار شمعی (TradingView، MetaTrader، Binance، تم روشن یا تیره) را رها کنید. موتور با OpenCV کندل‌ها را جدا می‌کند، سری OHLC را بازسازی می‌کند و همان منطق الگوهای نیسون/بالکوفسکی، روند و حمایت/مقاومتِ داده‌های زنده را روی آن اجرا و توضیح می‌دهد. اختیاری: قیمت بالا و پایین محور قابل‌مشاهده را وارد کنید تا سطوح واقعی به دست آید. تست خودکار دقت اندازه‌گیری‌شده روی نمودارهای مصنوعی را نشان می‌دهد.",
        "vis_open": "باز کردن تصویر", "vis_paste": "چسباندن از کلیپ‌بورد", "vis_demo": "نمودار آزمایشی تصادفی", "vis_selftest": "تست خودکار (کارت مدل)", "vis_cal": "کالیبراسیون محور:", "vis_cal_top": "بالا", "vis_cal_bot": "پایین", "vis_apply": "اعمال",
        "vis_candles": "کندل‌های یافت‌شده", "vis_theme": "تم", "vis_last": "آخرین کندل", "vis_conf": "اطمینان رنگ", "vis_drop": "⬇ تصویر نمودار را اینجا رها کنید یا از دکمه‌های بالا استفاده کنید", "vis_recon": "OHLC بازسازی‌شده (آنچه موتور «می‌بیند»)",
        "vis_explain": "توضیح", "vis_patterns": "الگوهای شناسایی‌شده", "vis_pattern": "الگو", "vis_kind": "نوع", "vis_where": "کجا", "vis_stat": "جهت / آمار", "vis_modelcard": "کارت مدل — دقت استخراج روی نمودارهای مصنوعی", "vis_found": "یافته / واقعی", "vis_diracc": "دقت جهت", "vis_corr": "همبستگی بسته",
        "vis_up": "صعودی", "vis_down": "نزولی", "vis_range": "رنج", "vis_candle_pat": "کندلی (نیسون)", "vis_chart_pat": "نموداری (بالکوفسکی)", "vis_noclip": "تصویری در کلیپ‌بورد نیست.", "vis_fail": "نتوانستم کندل‌ها را از این تصویر بخوانم. راهنمایی: تصویر را به ناحیهٔ قیمت برش دهید، از اندیکاتورهای سنگین روی نمودار بپرهیزید، اسکرین‌شات بزرگ‌تر بدهید.",
        "ql_tab_bots": "میز بات‌ها", "ql_monkey": "تست میمون (دیوی)", "ql_mc_ret": "بازده مونت‌کارلو p5…میانه…p95", "ql_mc_dd": "افت سرمایهٔ مونت‌کارلو", "ql_prot": "با حفاظت‌های Freqtrade",
        "ql_bots_hint": "فیلترهای Pairlist فرق‌ترید روی کل واچ‌لیست (سن · نوسان · پایداری دامنه · اسپرد · قیمت · ۲۰ حجم برتر)؛ قیمت رزرو و اسپرد بهینهٔ آولاندا–استویکوف (Hummingbot) برای نماد انتخابی با بررسی مزیت بعد از کارمزد؛ اسپرد بین‌صرافی Blackbird؛ ماتریس ارزیاب وزنی OctoBot. فقط تحلیل — هیچ سفارشی ثبت نمی‌شود.",
        "ql_bots_run": "اجرای میز بات‌ها", "ql_as_gamma": "γ ضریب ریسک", "ql_as_inv": "موجودی پایه", "ql_as_fee": "کارمزد هر طرف",
        "ql_as_res": "قیمت رزرو (A-S)", "ql_as_spread": "اسپرد بهینه", "ql_as_edge": "مزیت بازارسازی", "ql_as_after_fees": "پس از کارمزد رفت‌وبرگشت",
        "ql_pl_kept": "قبول", "ql_pl_reason": "فیلتر", "ql_pl_title": "Pairlist فرق‌ترید (این تایم‌فریم)",
        "ql_octo_title": "ماتریس ارزیاب OctoBot (−۱ صعودی … +۱ نزولی)", "ql_octo_eval": "ارزیاب", "ql_octo_val": "مقدار", "ql_octo_w": "وزنی", "ql_octo_avg": "میانگین وزنی → وضعیت",
        "ql_bots_read": "<b>Pairlist:</b> {kept}/{total} نماد از فیلترهای فرق‌ترید در این تایم‌فریم عبور کردند — اسکنر باید فقط روی این‌ها استراتژی اجرا کند. <b>Blackbird</b> (صرافی دوم آزمایشی ±۵ bps): بهترین اسپرد خالص {bb_net:+.2f}% (خرید {bb_long} / فروش {bb_short}) — زیر آستانهٔ ورود ۰.۸٪ یعنی آربیتراژی نیست. <b>تست میمون</b> در تب بیش‌برازش: استراتژی باید از صدک ۹۵ ورودهای تصادفی با همان تعداد معامله و مدت نگهداری بهتر باشد.",
        "ql_tab_series": "سری (چان/د پرادو)", "ql_tab_pairs": "جفت‌ها و اسپرد", "ql_tab_overfit": "تست بیش‌برازش", "ql_tab_patterns": "الگوها (بالکوفسکی/نیسون)", "ql_tab_psy": "میز روان‌شناسی",
        "ql_analyze": "تحلیل سری", "ql_half_life": "نیمه‌عمر", "ql_regime": "ماهیت سری", "ql_stationary": "ایستا", "ql_corr_price": "همبستگی با قیمت (حافظه)",
        "ql_mr": "بازگشت به میانگین", "ql_mom": "روندی", "ql_rw": "گام تصادفی", "ql_meaning": "معنی:",
        "ql_mr_adv": "هرست < ۰.۴۵ و ADF ریشهٔ واحد را رد می‌کند → استراتژی‌های بولینگر/z-score اینجا توجیه آماری دارند؛ پنجره ≈ نیمه‌عمر (چان فصل ۲–۳).",
        "ql_mom_adv": "هرست > ۰.۵۵ → سری بیش از گام تصادفی روند دارد؛ شکست/مومنتوم لبهٔ آماری دارد و بازگشت به میانگین خون‌ریزی می‌کند (چان فصل ۶).",
        "ql_rw_adv": "هیچ‌کدام از تست‌ها قانع‌کننده نیست → سری در این تایم‌فریم مثل گام تصادفی رفتار می‌کند؛ هیچ استراتژی خطی لبهٔ ساختاری ندارد. فقط ستاپ‌های اثبات‌شدهٔ کتاب راهنما، یا بی‌معامله.",
        "ql_scan_pairs": "اسکن جفت‌ها", "ql_pairs_hint": "هم‌انباشتگی انگل–گرنجر روی لگاریتم قیمت برای همهٔ جفت‌های دسته (چان فصل ۳؛ همان منطق اسپردی که Blackbird/ArbitrageBot بین صرافی‌ها به کار می‌برند). جفت قابل معامله: ADF < −۲.۸۶، نیمه‌عمر کوتاه (< ۶۰ کندل) و |z| > ۲ برای ورود: خرید اسپرد = خرید A، فروش β×B.",
        "ql_coint": "هم‌انباشته", "ql_signal": "سیگنال اسپرد", "ql_not_tradeable": "هم‌انباشته نیست", "ql_running": "در حال اجرا…",
        "ql_test_overfit": "تست بیش‌برازش", "ql_overfit_hint": "لوپز د پرادو: با ~۲۰۰۰ آزمایش استراتژی، بهترین شارپ بک‌تست به‌طور شانسی بالا خواهد بود. شارپ تعدیل‌شده = احتمال اینکه شارپ مشاهده‌شده از سطح شانس بهتر باشد. PBO = احتمال اینکه پارامتری که در نمونه بهترین است، خارج از نمونه زیر میانه بیفتد (CSCV روی ۱۶ مجموعه پارامتر). دیوی: کارایی واک‌فوروارد ≥ ۵۰٪ و چک‌لیست انکوباسیون قبل از هر پول واقعی.",
        "ql_incubation": "انکوباسیون دیوی", "ql_check": "بررسی", "ql_pass": "قبول", "ql_go": "برو (انکوباسیون زنده)", "ql_nogo": "نرو",
        "ql_overfit_read": "خوانش: احتمال شارپ تعدیل‌شده {dsr:.0f}٪ (≥۹۵٪ معنادار؛ شارپی که فقط از شانس انتظار می‌رود ≈ {sr0:.2f}). PBO {pbo:.0f}٪ (<۳۰٪ خوب، >۵۰٪ = پارامترها روی نویز فیت شده‌اند).",
        "ql_scan_patterns": "اسکن الگوها", "ql_patterns_hint": "قواعد شناسایی بالکوفسکی + آمار منتشرشدهٔ او در بازار صعودی (نرخ شکست سربه‌سر، میانگین حرکت، رتبهٔ عملکرد) و ۲۶ الگوی کندلی نیسون با نرخ برگشت اندازه‌گیری‌شدهٔ بالکوفسکی. هدف = قانون اندازه‌گیری (ارتفاع الگو).",
        "ql_chart_patterns": "الگوهای نموداری نزدیک شکست", "ql_candles": "الگوهای کندلی (۱۰ کندل اخیر)", "ql_pattern": "الگو", "ql_level": "سطح شکست", "ql_confirmed": "تأیید", "ql_fail_rate": "نرخ شکست", "ql_avg_move": "میانگین حرکت", "ql_rank": "رتبه", "ql_pending": "در انتظار", "ql_bar": "کندل", "ql_rev_rate": "نرخ برگشت",
        "ql_checklist": "چک‌لیست پیش از معامله (داگلاس · الدر · استینبارگر · کانمن · طالب)", "ql_cleared": "مجاز به معامله", "ql_not_cleared": "معامله نکنید",
        "ql_gates": "دروازه‌های سخت (استیو دی / پراپ‌فرم): ≤۱٪ هر معامله · ≤۳٪ ریسک باز کل · توقف روز در −۳٪ · ۲۴ ساعت استراحت بعد از ۳ ضرر پیاپی. تخصیص‌دهندهٔ مشاور دو مورد اول را خودکار اعمال می‌کند.",
        "ql_ror": "ریسک ورشکستگی (مونت‌کارلو برنشتاین)", "ql_ror_res": "احتمال از دست دادن ۵۰٪ سرمایه در ۵۰۰ معامله = {:.1f}٪. با ریسک {:.1f}٪ می‌شد {:.1f}٪. ورشکستگی تابع اندازه است، نه استراتژی.",
        "ql_audit": "ممیزی سوگیری ژورنال (با عدد، نه موعظه)", "ql_audit_run": "ممیزی ژورنال من + معاملات تست پیش‌رو", "ql_audit_empty": "هنوز معامله‌ای نیست — ژورنال پر کنید یا بگذارید تست پیش‌رو جمع کند.",

        "fw_title": "تست پیش‌رو — واقعیت به بک‌تست‌ها نمره می‌دهد",
        "fw_sub": "هر سیگنال تازهٔ مشاور / اسکنر به‌طور خودکار ثبت می‌شود. سپس ربات کندل‌های بعدی را دنبال می‌کند و هر رکورد را دقیقاً مثل بک‌تستر می‌بندد (گپ → استاپ، استاپ قبل از هدف، حد زمانی ۲۰۰ کندل). بعد از ۳۰+ رکورد بسته، بازهٔ اطمینان می‌گوید لبه واقعی است یا نه. هیچ معامله‌ای انجام نمی‌شود.",
        "fw_update": "به‌روزرسانی نتایج", "fw_clear": "پاک کردن", "fw_clear_q": "همهٔ رکوردهای تست پیش‌رو حذف شوند؟", "fw_auto": "به‌روزرسانی خودکار هر ۱۵ دقیقه",
        "fw_verdict": "حکم", "fw_closed_open": "بسته / باز", "fw_gap": "واقعیت ÷ بک‌تست (PF)", "fw_need10": "حداقل ۱۰ رکورد بسته لازم است",
        "fw_by_strategy": "به تفکیک استراتژی (واقعی)", "fw_by_tf": "به تفکیک تایم‌فریم", "fw_expected": "انتظار بک‌تست", "fw_grade": "نمره",
        "fw_records": "رکوردها (دابل‌کلیک → نمودار)", "fw_status": "وضعیت", "fw_signal_bar": "کندل سیگنال", "fw_exit": "خروج", "fw_reason": "دلیل", "fw_source": "منبع",
        "fw_open": "باز", "fw_closed_s": "بسته", "fw_last": "آخرین به‌روزرسانی:", "fw_updated": "{} باز بررسی شد · {} بسته شد",
        "fw_v_collecting": "در حال جمع‌آوری (<۳۰)", "fw_v_confirmed": "لبه تأیید شد", "fw_v_positive": "مثبت، تأییدنشده", "fw_v_none": "بدون لبه",
        "hl_title": "سلامت ربات — خودتشخیصی و رفع خودکار",
        "hl_sub": "ربات منبع داده، سنِ کتاب راهنما، افت لبه، استراتژی‌های اعتبارسنجی‌نشده، رکوردهای قدیمی تست پیش‌رو و استراتژی‌های خطادار را خودش بررسی می‌کند — و هرچه را بتواند با یک کلیک رفع می‌کند.",
        "hl_quick": "بررسی سریع", "hl_full": "بررسی کامل (با دانلود داده)", "hl_fix_all": "رفع همهٔ موارد", "hl_state": "وضعیت", "hl_errors": "خطاها", "hl_warns": "هشدارها", "hl_infos": "نکته‌ها",
        "hl_last": "آخرین بررسی", "hl_running": "در حال بررسی…", "hl_done": "بررسی کامل شد", "hl_fixing": "در حال رفع", "hl_bad": "نیاز به توجه", "hl_ok_warn": "سالم با هشدار", "hl_good": "سالم", "hl_none": "مشکلی پیدا نشد.",
        "hl_maint": "گزارش نگهداری خودکار (پس‌زمینه: تست پیش‌رو هر ۱۵ دقیقه · رفع‌های امن هر ۶ ساعت · کتاب راهنما هر ۷ روز)", "hl_maint_none": "هنوز چیزی نیست",
        "adv_chase": "قیمت بیش از ۰.۵R از کلوز سیگنال دور شده — ورود الان بدتر از چیزی است که بک‌تست شده. منتظر پولبک بمانید یا رد کنید.",
        "adv_pb_gate": "شرط قبولی: n≥۳۰ · کران پایین PF>۱ · t≥۲ · PF سال اخیر≥۰.۹", "grade": "نمره", "ci": "بازهٔ ۹۵٪", "need_n": "تعداد معاملهٔ لازم برای قطعیت ±۸٪ در WR", "adv_alloc": "تخصیص پرتفو (اگر همهٔ سیگنال‌های بالا را بگیرید)", "adv_take": "بگیر", "adv_skip": "رد کن", "adv_risk": "ریسک ٪", "adv_units": "واحد", "adv_reason": "توضیح",
        "adv_recorded": "در تست پیش‌رو ثبت شد", "adv_grade_hint": "نمرهٔ A = n≥۱۰۰ و کرانِ پایین PF>۱.۱ و t≥۳ · B = n≥۵۰ · C = n≥۳۰ · D = نویز. عدد داخل کروشه کرانِ پایینِ ۹۵٪ اطمینان است — به آن اعتماد کنید، نه به عدد اصلی.",
        "dash_health": "سلامت ربات", "dash_forward": "تست پیش‌رو",

        "adv_title": "🎯 مشاور — استراتژی درست، تایم‌فریم درست، لحظهٔ درست",
        "adv_sub": "برای یک نماد، بات در ~۲ ثانیه ۵ دقیقه تا ۱ روز را بررسی می‌کند: رژیم هر تایم‌فریم، سپس فقط استراتژی‌هایی که خارج از نمونه روی همان تایم‌فریم و همان کلاس دارایی اثبات شده‌اند (کتاب راهنمای تایم‌فریم) و قفل دامنه ندارند. سیگنال‌های کهنه دور ریخته می‌شوند، فیلتر جهت تایم بالاتر اعمال می‌شود، و اطلاعات تحویل می‌گیرید: مدت نگهداری انتظاری و دقایق تا بسته شدن کندل بعدی (نقطهٔ تصمیم بعدی). اگر هیچ استراتژی اثبات‌شده‌ای فعال نباشد، پاسخ صادقانه «صبر» است.",
        "adv_run": "مشاوره بده", "adv_rebuild": "بازسازی کتاب راهنمای تایم‌فریم (~۶ دقیقه)", "adv_running": "در حال تحلیل…", "adv_pb_done": "کتاب راهنما بازسازی شد",
        "adv_verdict": "حکم", "adv_htf": "جهت تایم بالاتر", "adv_fastest": "سریع‌ترین تایم با سیگنال", "adv_best_tf": "بهترین تایم", "adv_elapsed": "زمان پاسخ",
        "adv_regime": "رژیم", "adv_pb_wr": "وین‌ریت اثبات‌شده (تایم)", "adv_pb_pf": "PF اثبات‌شده (تایم)", "adv_hold": "نگهداری انتظاری", "adv_next": "بسته شدن کندل بعد",
        "adv_wait": "صبر", "adv_trend": "روند", "adv_range": "رنج", "adv_mixed": "مختلط", "adv_flat": "هیچ‌چیز روی این تایم اثبات نشده ← بی‌معامله", "adv_no_fresh": "سیگنال تازه‌ای نیست",
        "adv_rule_exit": "خروج قاعده‌مند (SMA5/RSI)", "adv_playbook": "کتاب راهنمای تایم‌فریم — بات دربارهٔ هر تایم‌فریم چه یاد گرفت (خارج از نمونه، ۴ گروه دارایی)",
        "adv_proven": "اثبات‌شده (n≥۳۰ · کران پایین PF>۱ · t≥۲)", "adv_no_pb": "کتاب راهنما هنوز ساخته نشده — بازسازی را بزنید.",
        "nav_live": "بازار زنده", "nav_ml": "آزمایشگاه ML",
        "live_title": "⚡ بازار زنده — کل صرافی، به‌صورت لحظه‌ای",
        "live_sub": "یک وب‌سوکت همهٔ جفت‌های USDT بایننس (≈۱۷۰–۴۸۰ نماد، بدون کلید API) را استریم می‌کند. N نماد برتر از نظر حجم، کندل هم دریافت می‌کنند؛ با بسته شدن هر کندل، استراتژی‌های تأییدشده (امتیاز آزمایشگاه ≥ آستانه) و آنسامبل فوراً اجرا می‌شوند و سیگنال‌های تازه با اعلان اینجا ظاهر می‌شوند. کاشی‌های «پهنای بازار» سلامت بازار را قبل از هر خرید نشان می‌دهند.",
        "live_start": "شروع استریم", "live_stop": "توقف", "live_idle": "غیرفعال", "live_stopped": "متوقف شد", "live_topn": "N برتر از نظر حجم", "live_use_ml": "احتمال ML",
        "live_t_symbols": "زیر نظر / کل", "live_t_ticks": "تیک دریافتی", "live_t_breadth": "٪ بالای EMA50 / EMA200", "live_t_adv": "صعودی / نزولی", "live_t_signals": "سیگنال زنده",
        "live_signals_card": "سیگنال‌های تأییدشدهٔ لحظه‌ای (دابل‌کلیک ← چارت)", "live_market_card": "کل بازار (قیمت زنده)", "live_now": "اکنون", "live_vol24": "حجم ۲۴س", "time": "زمان",
        "ml_title": "🧠 آزمایشگاه ML — بات از خودِ بازار یاد می‌گیرد",
        "ml_sub": "≈۹۰ ویژگی بدون مقیاس (همهٔ اندیکاتورهای دانشنامه) ← مدل گرادیان‌بوستینگ که پیش‌بینی می‌کند آیا هدف +۲×ATR قبل از استاپ −۱×ATR طی H کندل لمس می‌شود (برچسب سه‌مانعی). با فولدهای واک‌فوروارد پاک‌سازی‌شده آموزش می‌بیند، پس همهٔ اعداد نمایش‌داده‌شده خارج از نمونه‌اند. همچنین سیگنال‌های استراتژی‌ها را «متا-لیبل» می‌کند: احتمال برد هر سیگنال با توجه به شرایط فعلی بازار.",
        "ml_train": "آموزش روی این بازار", "ml_load": "بارگذاری مدل ذخیره‌شده", "ml_horizon": "افق (کندل)", "ml_training": "در حال آموزش…",
        "ml_hint": "نماد/تایم‌فریم را انتخاب و آموزش دهید. نتایج صادقانهٔ معمول: AUC ‏۰.۵۲–۰.۵۸. بالاتر از ۰.۶۰ روی کریپتوی ساعتی مشکوک است (نشت داده)، نه نبوغ.",
        "ml_p_long": "احتمال برد خرید (اکنون)", "ml_p_short": "احتمال برد فروش (اکنون)", "ml_lift": "لیفت ۲۰٪ برتر", "ml_base": "نرخ پایه خ / ف", "ml_samples": "نمونه‌ها",
        "ml_learned": "مدل چه یاد گرفت (اهمیت ویژگی‌ها، خارج از نمونه)", "ml_calib": "کالیبراسیون (پیش‌بینی در برابر واقعی)", "ml_meta": "سیگنال‌های متا-لیبل‌شده (۵ کندل اخیر)",
        "ml_pred": "پیش‌بینی", "ml_actual": "واقعی", "ml_verdict": "درست؟", "ml_advice": "توصیه", "ml_take": "✔ بگیر", "ml_skip": "✘ رد کن", "ml_neutral": "~ خنثی",
        "ml_v_noise": "✘ لبه‌ای پیدا نشد: مدل روی این بازار از نویز قابل‌تشخیص نیست. از احتمال‌هایش اینجا استفاده نکنید.",
        "ml_v_weak": "~ لبهٔ ضعیف ولی واقعی: فقط به‌عنوان فیلتر (سیگنال‌های با احتمال کمتر از نرخ پایه را رد کنید).",
        "ml_v_ok": "✔ لبهٔ معنادار خارج از نمونه. باز هم کوچک است — با استراتژی‌های تأییدشده و ریسک سخت‌گیرانه ترکیب کنید.",
        "ml_saved": "مدل‌های ذخیره‌شده", "ml_none": "مدلی برای این نماد/تایم‌فریم ذخیره نشده — اول آموزش دهید.",
        "acad_tab_strats": "استراتژی‌ها", "acad_tab_inds": "دانشنامهٔ اندیکاتورها (۷۱)",
        "ind_how": "نحوهٔ محاسبه", "ind_read": "نحوهٔ خواندن و معامله", "ind_used": "استفاده‌شده در استراتژی‌های",
        "ind_ml_note": "این اندیکاتور یکی از ≈۹۰ ویژگی‌ای است که مدل آزمایشگاه ML از آن یاد می‌گیرد.",
        "nav_lab": "آزمایشگاه اعتبارسنجی",
        "lab_title": "🧬 آزمایشگاه اعتبارسنجی — کدام استراتژی‌ها واقعاً دوام می‌آورند؟",
        "lab_sub": "هر استراتژی روی ۱۴ بازار با فولدهای واک‌فوروارد خارج از نمونه و شبیه‌سازی مونت‌کارلو (بُر زدن ترتیب معاملات) دوباره آزمایش می‌شود. امتیاز مقاومت (۰–۱۰۰) به پرافیت‌فکتور خارج از نمونه، ثبات بین فولدها و بازارها، افت شبیه‌سازی‌شده کم و تعداد کافی معامله پاداش می‌دهد — نه به بازده درون نمونه. امتیاز ≥ ۵۵ مقاوم محسوب می‌شود؛ استراتژی ★ آنسامبل فقط روی هم‌راستایی استراتژی‌های تأییدشده برای همان بازار معامله می‌کند.",
        "lab_run": "اجرای اعتبارسنجی کامل (≈۴ دقیقه)", "lab_run_sel": "اعتبارسنجی مجدد انتخاب‌شده", "lab_running": "در حال اعتبارسنجی…", "lab_last": "آخرین اجرا:",
        "lab_t_validated": "اعتبارسنجی‌شده", "lab_t_robust": "مقاوم (≥۵۵)", "lab_t_fail": "مردود (<۲۵)", "lab_t_ens": "امتیاز آنسامبل",
        "lab_score": "مقاومت", "lab_verdict": "حکم", "lab_oos_pf": "PF خارج نمونه", "lab_oos_pos": "فولدهای مثبت", "lab_mc_dd": "افت مونت‌کارلو ۹۵٪",
        "lab_markets": "بازارها", "lab_best": "بهترین بازارها (خارج نمونه)", "lab_detail": "تفکیک هر بازار (دابل‌کلیک: باز کردن روی بهترین بازار)",
        "lab_oos_folds": "PF فولد ۱·۲·۳", "lab_not_run": "اجرا نشده",
        "lab_v_robust": "✔ مقاوم", "lab_v_ok": "~ با فیلتر قابل‌استفاده", "lab_v_weak": "⚠ ضعیف", "lab_v_fail": "✘ مردود",
        "lab_expl": "خارج از نمونه یعنی استراتژی فقط روی داده‌ای امتیاز گرفته که امکان فیت شدن روی آن را نداشته. افت مونت‌کارلو ۹۵٪ یعنی افتی که در ۱ از ۲۰ ترتیب بدشانس همین معاملات باید انتظار داشته باشید. استراتژی‌ای که اینجا همه‌جا سبز است باز هم تضمین نیست — اما استراتژی‌ای که اینجا قرمز است نباید معامله شود.",
        "robust": "مقاومت", "return": "بازده", "max_dd": "حداکثر افت",
        "nav_academy": "آکادمی استراتژی",
        "nav_risk": "مدیریت ریسک",
        "nav_journal": "ژورنال معاملات",
        "nav_settings": "تنظیمات",
        "symbol": "نماد", "timeframe": "تایم‌فریم", "strategy": "استراتژی", "load": "بارگذاری", "run": "اجرا",
        "loading": "در حال دریافت داده…", "ready": "آماده", "category": "دسته", "all": "همه",
        "signals": "سیگنال‌های اخیر", "time": "زمان", "side": "جهت", "price": "قیمت", "stop": "حد ضرر", "target": "حد سود",
        "rr": "ریسک/ریوارد", "long": "خرید", "short": "فروش", "no_signal": "روی کندل آخر سیگنالی نیست",
        "last_signal": "آخرین سیگنال", "bars_ago": "کندل قبل",
        "scan": "اسکن بازار", "scanning": "در حال اسکن…", "scan_hint": "فقط استراتژی‌های اثبات‌شده روی این تایم‌فریم و کلاس دارایی (کتاب راهنما) را روی همهٔ نمادها اجرا می‌کند و سیگنال‌های تازه (N کندل آخر) را لیست می‌کند. استراتژی‌های قفل‌شده پنهان‌اند.",
        "recent_bars": "سیگنال‌های N کندل آخر", "min_pf": "فقط استراتژی‌هایی با PF تاریخی ≥",
        "bt_run": "اجرای بک‌تست", "capital": "سرمایه اولیه", "risk": "ریسک هر معامله ٪", "comm": "کارمزد (bps)",
        "trades": "معاملات", "winrate": "وین‌ریت", "pf": "پرافیت فکتور", "ret": "بازده خالص", "dd": "حداکثر افت",
        "sharpe": "شارپ", "avg_r": "میانگین R", "expect": "امید ریاضی", "equity": "منحنی سرمایه", "trade_list": "لیست معاملات",
        "compare": "مقایسه همه استراتژی‌ها", "comparing": "در حال مقایسه…",
        "entry": "ورود", "exit": "خروج", "pnl": "سود/زیان", "r_mult": "R", "bars": "کندل", "reason": "دلیل",
        "difficulty": "سختی", "author": "منشأ", "rules": "قوانین ورود", "pros": "نقاط قوت", "cons": "نقاط ضعف",
        "desc": "توضیحات", "params": "پارامترها", "reset": "بازنشانی", "apply": "اعمال و اجرای مجدد",
        "equity_now": "موجودی حساب", "risk_pct": "ریسک هر معامله (٪)", "entry_px": "قیمت ورود", "stop_px": "قیمت حد ضرر",
        "leverage": "اهرم", "calc": "محاسبه", "units": "حجم پوزیشن (واحد)", "notional": "ارزش اسمی",
        "margin": "مارجین لازم", "risk_amt": "مبلغ در ریسک", "dist": "فاصله حد ضرر",
        "ror": "ریسک نابودی (افت ۵۰٪)", "kelly": "درصد کلی", "losses_to_half": "ضررهای متوالی تا -۵۰٪",
        "targets": "اهداف", "wr_input": "وین‌ریت مورد انتظار ٪", "rr_input": "میانگین R:R",
        "j_add": "افزودن معامله", "j_del": "حذف انتخاب‌شده", "j_notes": "یادداشت / درس", "j_export": "خروجی CSV",
        "j_stats": "آمار ژورنال", "date": "تاریخ", "result": "نتیجه", "emotion": "احساس",
        "lang": "زبان", "theme": "پوسته", "data_src": "منبع داده", "cache_clear": "پاک‌کردن کش داده",
        "about": "درباره", "disclaimer": ("این نرم‌افزار فقط برای آموزش و پژوهش است. بک‌تست‌ها فرضی هستند، شامل ساده‌سازی‌اند، "
                                          "و عملکرد گذشته هرگز تضمین نتایج آینده نیست. اکثر تریدرهای خرد ضرر می‌کنند. "
                                          "هرگز با پولی که توان از دست دادنش را ندارید معامله نکنید."),
        "welcome": "خوش برگشتی، تریدر",
        "welcome_sub": "۹۴ استراتژی · ۱۵ بات · ۳۰ کتاب · آزمایشگاه کوانت · تست پیش‌رو · خودتشخیصی · کتاب راهنمای نمره‌دار (بازهٔ اطمینان) تایم‌فریم ۵m→۱d · مشاور · ۷۱ اندیکاتور · استریم زندهٔ کل بازار · آزمایشگاه ML · اعتبارسنجی · آنسامبل · بک‌تستر · آکادمی",
        "quick": "شروع سریع", "top_strats": "بهترین استراتژی‌ها روی این نماد (بک‌تست)", "market_pulse": "نبض بازار",
        "trend": "روند", "regime": "رژیم", "vol": "نوسان (ATR%)", "rsi": "RSI(14)", "change": "تغییر ۲۴ساعته",
        "bull": "صعودی", "bear": "نزولی", "range": "رنج", "trending": "رونددار", "high": "بالا", "low": "پایین", "normal": "عادی",
        "lesson": "درس امروز",
        "tip_title": "قوانین طلایی",
        "tips": ["حداکثر ۱–۲٪ سرمایه در هر معامله ریسک کن — اول بقا.",
                 "استراتژی بدون بک‌تست حدس است. بک‌تست بدون داده خارج از نمونه دروغ است.",
                 "وین‌ریت بدون R:R بی‌معنی است. وین‌ریت ۳۵٪ با R:R ۱:۳ بسیار سودآور است.",
                 "استراتژی روندی در رنج ضرر می‌دهد؛ بازگشت به میانگین در روند. رژیم بازار را بشناس.",
                 "هر معامله را ژورنال کن. ژورنالت مربی واقعی توست.",
                 "بایاس تایم بالاتر + ورود تایم پایین‌تر = الگوی حرفه‌ای‌ها.",
                 "اگر هیجان‌زده‌ای، پوزیشنت خیلی بزرگ است."],
        "wf": "تقسیم واک‌فوروارد (٪)", "in_sample": "درون‌نمونه", "out_sample": "خارج‌نمونه",
        "export_trades": "خروجی CSV معاملات", "no_data": "دریافت داده ناموفق بود", "offline": "آفلاین (داده نمایشی)",
        "long_only": "فقط خرید", "breakeven": "انتقال استاپ به نقطه سر‌به‌سر در 1R",
        "score": "امتیاز", "fresh": "تازگی", "conf": "هم‌راستایی",
    },
}


class I18N:
    lang = "en"

    @classmethod
    def t(cls, key):
        return STR.get(cls.lang, STR["en"]).get(key, STR["en"].get(key, key))

    @classmethod
    def rtl(cls):
        return cls.lang == "fa"


def t(key):
    return I18N.t(key)
