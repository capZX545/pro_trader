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
QFrame#clockbar {{ background: {C['panel']}; border-bottom: 1px solid {C['border']}; }}
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
        "nav_irangold": "Iran Gold 🇮🇷",
        "nav_forward": "Forward Test", "nav_health": "Health", "nav_desk": "Trading Desk", "desk_sub": "Daily briefing: safety gates → market regimes → open forward positions → ranked trade plans (proven strategies only, portfolio-capped) → edge decay → reality vs backtest.", "desk_run": "Build briefing", "desk_mode": "Strategies", "desk_equity": "Equity", "desk_copy": "Copy",
        "nav_quant": "Quant Lab", "acad_tab_lib": "Library: 30 books · 15 bots", "lib_sub": "Every book and bot from the curriculum, the lesson extracted from it, and exactly where that lesson is implemented in this app. Double-check any claim by opening the referenced strategy or page.", "lib_title_c": "Title", "lib_author": "Author", "lib_group": "Group", "lib_lesson": "Lesson embedded", "lib_where": "Where in the app", "search": "search…",
        "ql_title": "Quant Lab — Chan · López de Prado · Davey · Bulkowski · Nison · Douglas",
        "ql_sub": "Tools from the reading list, applied to any symbol: is the series mean-reverting or trending (ADF, Hurst, half-life)? Which pairs cointegrate? Is a strategy's backtest overfit (Deflated Sharpe, PBO, Walk-Forward Efficiency, Davey's incubation)? Which chart/candle patterns are live and what did they historically do? And the psychology desk: pre-trade checklist, hard risk gates, journal bias audit.",
        "j_steen_title": "Steenbarger performance review", "j_steen_group": "Group", "j_weekday": "Weekday",
        "j_steen_empty": "Log trades to see which setups, emotional states and weekdays actually make (or lose) your money.",
        "j_steen_read": "Top-10% trades produce {top:.0f}% of gross profit (>60% = P&L depends on rare outliers — Taleb). Worst losing streak: {streak}. Steenbarger: trade the states and setups with positive expectancy; shrink size in the others.",
        "vis_img_pat": "image pattern (learned)", "vis_ask": "Ask", "vis_ask_ph": "Ask the analyst about this chart (trend? levels? risk? pattern?) — offline",
        "ai_tab_an": "Analyst (offline LLM)", "ai_llm_status": "llama-cpp {llama} · GGUF models in data/models: {gguf} · mode: {mode}", "ai_llm_rules": "grounded rule-writer (no model file)",
        "ai_bias": "Bias", "ai_confl": "Confluence", "ai_agree": "Agreement", "ai_evidence": "Evidence", "ai_brief": "Analyst brief",
        "ai_an_note": "What FinGPT / finance-tuned Llama·Mistral·DeepSeek·Qwen·Falcon are actually good for: turning many signals into one grounded brief. This runs fully offline. Every sentence cites a number produced by the app; the writer never invents figures and never issues orders. Drop a finance-tuned GGUF (e.g. Qwen2.5-7B-Instruct fin, Mistral-7B fin) into data/models and install llama-cpp-python to swap the rule-writer for a real local LLM — same grounding prompt.",
        "proven_only": "proven only", "proven_only_tip": "Show only strategies proven out-of-sample in the Playbook (breadth-gated) and clean in the audit.",
        "nav_portfolio": "Portfolio", "pf_title": "Proven-strategy portfolio", "pf_sub": "Only strategies that passed the audit and the out-of-sample Playbook (breadth-gated) can enter. Members are chosen for LOW correlation of their equity curves and each gets an equal share of the risk budget — two strategies that win and lose together count as one.",
        "pf_max_n": "max strategies", "pf_max_corr": "max ρ", "pf_risk": "risk / trade", "pf_build": "Build portfolio", "pf_n_strats": "Strategies", "cagr": "CAGR", "pf_risk_each": "risk each",
        "pf_curve": "Out-of-sample equity (last 60 % of history, daily, %)", "pf_members": "Members", "pf_breadth": "breadth sym/yr", "pf_weight": "weight", "pf_combined": "combined",
        "pf_corr_avg": "average pairwise ρ", "pf_years": "years", "pf_none": "No proven strategies on this timeframe yet — build the Playbook first (Advisor → Build).",
        "pf_note": "⚠ Out-of-sample but still historical: real results are usually 30–50 % worse (costs modelled, but not every regime). Rebuild monthly; drop a member if its forward-test PF falls below 1 for 30+ trades.",
        "al_tg": "Telegram", "al_desktop": "Desktop", "al_channels": "Channels", "al_min_conf": "Min confidence", "al_tfs": "Timeframes", "al_test": "Send test", "al_scan_now": "Scan now",
        "al_test_body": "Desktop notifications work.", "al_sent": "new alerts", "alerts": "Alerts (Telegram / desktop)", "save": "Save", "saved": "saved",
        "train_idle": "Self-training status…", "train_running": "Self-training", "train_audit": "strategy audit", "train_quick": "quick playbook (1d/4h/1h)", "train_full": "full playbook (all timeframes)",
        "train_done": "Bot is trained & watching the market", "train_proven": "proven combos", "train_tfs": "timeframes", "days": "days old",
        "nav_ai": "AI Desk", "ai_title": "AI Desk — forecasting, sentiment, reinforcement learning, engine parity",
        "ai_sub": "Everything here is evaluated honestly against naive baselines. A model that does not beat 'tomorrow = today' is shown as such.",
        "ai_tab_fc": "Forecast", "ai_tab_sent": "Sentiment", "ai_tab_rl": "RL agent", "ai_tab_eng": "Engines",
        "ai_run": "Run", "ai_horizon": "Horizon (bars)", "ai_model": "Model", "ai_mase": "MASE", "ai_rmse": "RMSE", "ai_diracc": "Direction acc.", "ai_vsnaive": "vs naive", "ai_pval": "p-value",
        "ai_fc_note": "MASE < 1 and 'vs naive' < 1 mean the model beat the naive forecast out-of-sample over {n} rolling origins. Direction accuracy near 50% on liquid markets is normal — that is the efficient-market baseline.",
        "ai_fc_band": "Prophet-like trend + changepoints band", "ai_q": "Quantile forecast (GBR pinball)", "ai_cp": "CUSUM changepoints", "ai_verdict": "Verdict",
        "ai_fc_good": "Some models beat naive — use as a weak tilt only, never as a signal on its own.", "ai_fc_bad": "No model beats naive here — forecasting adds nothing on this series; rely on price-action & risk.",
        "ai_headlines": "Headlines (one per line) — or fetch", "ai_fetch": "Fetch news", "ai_score": "Score", "ai_headline": "Headline", "ai_compound": "Compound", "ai_subj": "Subjectivity", "ai_tickers": "Tickers", "ai_regime": "Regime", "ai_crowded": "Crowded?", "ai_sent_mean": "Mean sentiment", "ai_pos": "Positive %", "ai_neg": "Negative %", "ai_backend": "Backend",
        "ai_sent_note": "Lexicon = VADER-style rules (negation, boosters, ALL-CAPS, '!') + Loughran-McDonald finance words. If transformers + FinBERT are installed the FinBERT column is filled. 'Crowded' = unanimous + emotional + subjective → contrarian risk flag (Kahneman / Douglas).",
        "ai_agent": "Agent", "ai_episodes": "Episodes", "ai_seeds": "Seeds", "ai_reward": "Reward", "ai_seed": "Seed", "ai_train": "Train", "ai_val": "Val", "ai_test": "Test", "ai_dd": "Test DD", "ai_sharpe": "Test Sharpe", "ai_trades": "Trades",
        "ai_bh": "Buy & hold (test)", "ai_rand95": "Random p95 (test)", "ai_gap": "Overfit gap", "ai_rl_note": "Linear Q-learning / policy-gradient agents on a TensorTrade-style env (window features, costs, log-return or differential-Sharpe reward). Stable-Baselines3 is used automatically if installed. Read the TEST column only; train is always flattering. An agent that fails to beat random-p95 or buy&hold has learned noise.",
        "ai_rl_good": "Agent beats buy&hold AND the 95th percentile of random agents on the test split — still fragile; treat as research.", "ai_rl_bad": "Agent does not beat random/buy&hold out-of-sample. This is the normal outcome and the honest one.",
        "ai_parity": "Vectorised vs event-driven parity", "ai_engine": "Engine", "ai_ret": "Return %", "ai_pf": "PF", "ai_sqn": "SQN", "ai_eng_note": "The Backtrader-style event engine (next-bar fills, bracket orders, risk sizer, SQN analyzer) is run on the same signals as the vectorised backtester. A small gap (< 1% return, equal trade count) means both are trustworthy; a large gap points at look-ahead or fill assumptions.",
        "ai_pipeline": "Zipline pipeline — cross-sectional momentum rank", "ai_framework": "LEAN framework — Alpha → Portfolio → Risk → Execution", "ai_freqai": "FreqAI retrain schedule",
        "ai_running": "Running…", "ai_done": "Done", "ai_offline": "No headlines fetched (offline?) — paste some.",
        "nav_vision": "Chart Vision", "vis_title": "Chart Vision — understand a chart IMAGE", 
        "vis_sub": "Drop a screenshot or photo of any candlestick chart (TradingView, MetaTrader, Binance, light or dark). The engine segments the candles with OpenCV, rebuilds the OHLC series, then runs the same Nison/Bulkowski pattern logic, trend and S/R analysis used on live data — and explains it. Optional: enter the top & bottom price of the visible axis to get real price levels. Self-test shows measured accuracy on synthetic charts. Tested on real MetaTrader / TradingView / Binance-app screenshots (11/11 within ±20 % candle count). Best input: a clean screenshot; photos of a monitor lose ~30 % of candles — crop to the price pane if you must use one.",
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
        "nav_fast": "Fast Signals", "tg_token": "Telegram bot token (optional)", "tg_chat": "Telegram chat id", "web_mobile": "Web & mobile", "web_start": "Start web/mobile server", "web_stop": "Stop web server", "web_tip": "Serves the same engine (charts, signals with success %, advisor, fast signals, academy) to any phone or browser on your network. For internet access run a tunnel (e.g. cloudflared / ngrok) to this port.", "web_hint": "Open on your phone (same Wi-Fi) or scan the QR. Add to home screen for an app-like experience.", "ql_vol_ann": "Volatility (ann.)", "ql_range_pct": "Range %", "ql_spread_proxy": "Spread proxy %", "ql_quote_vol": "Quote vol", "success_rate_all": "Success rate across tested markets", "median_pf": "median PF", "pos_share": "profitable share", "markets": "markets", "success_unknown": "Success rate not computed yet for this strategy — open it on a chart, run the Scanner, or press Settings ▸ compute success rates.", "tz_local": "Computer clock (local)", "time_display": "Time display", "succ_compute": "compute success rates (all strategies × 5 majors × 4 TFs)", "succ_compute_tip": "Backtests every strategy on BTC/ETH/SOL/BNB/XRP at 15m/1h/4h/1d with fees and stores WR/PF next to every signal. 10–20 min, runs in background.", "clock_tip": "Local time = your computer clock (exact system timezone) · UTC = world time", "tool_cursor": "Cursor (click a signal marker to inspect it)", "tool_trend": "Trend line (2 clicks)", "tool_ray": "Ray (2 clicks)", "tool_hline": "Horizontal line", "tool_vline": "Vertical line", "tool_rect": "Rectangle / zone (2 clicks)", "tool_fib": "Fibonacci retracement (2 clicks: swing low → swing high)", "tool_text": "Text note", "tool_text_prompt": "Note text:", "tool_measure": "Measure (price % · bars · time)", "tool_erase": "Eraser (click a drawing)", "tool_undo": "Undo last drawing", "tool_clear": "Clear all drawings on this chart", "ind_add": "Add indicator", "ind_list_tip": "Indicators on this chart", "ind_remove": "Remove selected indicator", "ind_templates": "Indicator templates", "tpl_ichimoku": "Ichimoku cloud", "tpl_classic": "Classic (EMA 20/50/200 + RSI + MACD)", "tpl_scalp": "Scalping (VWAP, BB, Stoch, CVD, RVOL)", "tpl_volume": "Volume (profile, OBV, CMF, MFI)", "tpl_trend": "Trend (SuperTrend, ADX, KAMA, PSAR)", "refresh_keep": "Refresh", "refresh_keep_tip": "Reload data & re-apply settings WITHOUT losing your zoom/scroll position", "tz_toggle_tip": "Toggle chart time: local (computer clock) ↔ UTC", "outcome": "Outcome", "signals_click_tip": "Click a row → the chart jumps to that signal and marks where/when it was", "win": "win", "loss": "loss", "open_or_na": "open / n.a.", "success_rate": "Success rate (this symbol & timeframe)", "in_sample": "in-sample, incl. fees", "oos_rate": "Out-of-sample (playbook)", "local_time": "local", "bars": "bars", "search": "Search…", "fs_wfo": "Walk-forward tune", "fs_wfo_tip": "Anchored walk-forward of the 4 confluence knobs (votes, window, ATR stop, RR) per symbol; shows out-of-sample PF and WFE. Takes 1–3 min.", "fs_wfo_head": "Walk-forward (out-of-sample) verdict per symbol — only 'edge' means the confluence rule survived unseen data:", "fs_wfo_done": "walk-forward done · defaults updated", "fs_verdict_edge": "✅ edge", "fs_verdict_weak": "⚠ weak", "fs_verdict_none": "❌ none", "fs_title": "⚡ Fast Signals — low-timeframe confluence radar", "fs_sub": "Scans the top pairs on 1m–15m with 21 scalping / order-flow methods (VWAP pullback/bands, value-area bounce, Triple-A flow, stacked imbalance, LVN breakout, anchored TF, flat-BB stoch, NFI dip, unfinished auction, CVD divergence, stop-run, Brooks H2/L2, squeeze pop, session ORB, triple-confirm, fast RSI divergence, volume climax, funding-crowd, IB extension) plus the classic intraday set. A setup is shown only when several independent methods agree, the trend gate passes and the expected move covers fees. Every row carries the honest in-sample WR/PF of that rule on that symbol.", "fs_scan": "Scan now", "fs_auto": "auto every 5 min", "fs_min_votes": "min. agreeing methods", "fs_fee_tier": "fee tier", "fs_scanned": "Scanned", "fs_setups": "Setups", "fs_best": "Best", "fs_cost_ok": "Cost-viable", "fs_session": "Session", "fs_table": "Confluence setups (double-click → chart)", "fs_score": "Score", "fs_votes": "Votes", "fs_move": "Exp. move", "fs_cost": "Round-trip cost", "fs_agree": "Agreeing methods", "fs_explain": "Why this setup (and why it might fail)", "fs_done": "done · {n} setups", "fs_note": "Honesty note: on 50 000-bar tests of BTC/ETH/SOL (5m/15m) every single scalping method alone LOSES after realistic fees (PF 0.2–0.9). Only ≥3-method confluence with a trend gate reached PF ≈ 1.0–1.8 and on few trades. Treat these as candidates to forward-test (Forward Test page records them), not as guaranteed profits. Maker fees (limit orders) roughly double the viable setups.",
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
        "acad_tab_strats": "Strategies", "acad_tab_inds": "Indicator Encyclopedia (80)",
        "ind_how": "How it is computed", "ind_read": "How to read & trade it", "ind_used": "Used by strategies", 
        "ind_params": "Parameters", "ind_uses": "All the ways it is used", "ind_signals": "Concrete signal rules", "ind_pitfalls": "Pitfalls", "ind_combos": "Works best with",
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
        "nav_tv": "Advanced Chart",
        "symbol": "Symbol", "timeframe": "Timeframe", "strategy": "Strategy", "load": "Load", "run": "Run",
        "loading": "Loading data…", "ready": "Ready", "next_bar": "next bar in", "chart_renderer": "Chart renderer", "chart_auto": "Auto (detect blank canvas)", "chart_compat": "Compatibility (software, always visible)", "chart_renderer_tip": "If the chart area stays empty on your PC, choose Compatibility. Auto switches by itself when it detects a blank canvas.", "stale_cache": "stale cache — no live source reachable", "category": "Category", "all": "All",
        "signals": "Recent Signals", "time": "Time", "side": "Side", "price": "Price", "stop": "Stop", "target": "Target",
        "rr": "R:R", "long": "LONG", "short": "SHORT", "no_signal": "No signal on last bar",
        "last_signal": "Latest signal", "bars_ago": "bars ago",
        "q_filter": "Quality", "q_proven_only": "Proven only", "q_candidate": "Proven + candidates", "q_all": "Show all (incl. unproven)",
        "q_tip": "Trust gate: PROVEN = out-of-sample PF lower-CI > 1, n ≥ 50, forward test not contradicting. Unproven/failed strategies are hidden by default.",
        "q_verdict": "Verdict", "q_hidden": "hidden by quality gate", "q_why": "Why this verdict",
        "news_filter": "Pause alerts around high-impact news (FOMC/CPI/NFP)", "quality_mode": "Alert only for",
        "scan": "Scan Market", "scanning": "Scanning…", "plan": "Trade plan", "plan_hint": "Right-click a row (or select it and press Trade plan) for regime fit, edge decay, higher-TF alignment, Monte-Carlo and suggested size.", "scan_hint": "Runs only the strategies PROVEN on this timeframe & asset class (Timeframe Playbook) on every symbol and lists fresh signals (last N bars). Domain-locked strategies are hidden.",
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
        "welcome_sub": "{n} strategies (Ichimoku · Indicators · World Masters) · 15 bots ported · 37 books embedded · Quant Lab · Forward Test · Self-Health · CI-graded Playbook 5m→1d · Advisor + Portfolio · 73 indicators + success % beside every signal · Whole-market live stream · ML Lab · Validation Lab · Ensemble · Backtester · Academy",
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
        "nav_irangold": "طلای ایران 🇮🇷",
        "nav_forward": "تست پیش‌رو", "nav_desk": "میز معامله", "desk_sub": "بریفینگ روزانه: گیت‌های ایمنی → رژیم بازارها → پوزیشن‌های باز فوروارد → برنامه‌های معاملهٔ رتبه‌بندی‌شده (فقط استراتژی‌های اثبات‌شده، با سقف ریسک پرتفوی) → فرسایش لبه → واقعیت در برابر بک‌تست.", "desk_run": "ساخت بریفینگ", "desk_mode": "استراتژی‌ها", "desk_equity": "سرمایه", "desk_copy": "کپی", "nav_health": "سلامت ربات",
        "nav_quant": "آزمایشگاه کوانت", "acad_tab_lib": "کتابخانه: ۳۰ کتاب · ۱۵ بات", "lib_sub": "هر کتاب و بات برنامهٔ درسی، درسی که از آن استخراج شده، و دقیقاً جایی که آن درس در این برنامه پیاده شده است. هر ادعا را با باز کردن استراتژی یا صفحهٔ ارجاع‌شده بررسی کنید.", "lib_title_c": "عنوان", "lib_author": "نویسنده", "lib_group": "گروه", "lib_lesson": "درس پیاده‌شده", "lib_where": "کجای برنامه", "search": "جستجو…",
        "ql_title": "آزمایشگاه کوانت — چان · لوپز د پرادو · دیوی · بالکوفسکی · نیسون · داگلاس",
        "ql_sub": "ابزارهای فهرست کتاب‌ها روی هر نماد: سری بازگشتی است یا روندی (ADF، هرست، نیمه‌عمر)؟ کدام جفت‌ها هم‌انباشته‌اند؟ بک‌تست یک استراتژی بیش‌برازش دارد (شارپ تعدیل‌شده، PBO، کارایی واک‌فوروارد، چک‌لیست دیوی)؟ کدام الگوهای نموداری/کندلی زنده‌اند و در تاریخ چه کرده‌اند؟ و میز روان‌شناسی: چک‌لیست پیش از معامله، دروازه‌های سخت ریسک، ممیزی سوگیری ژورنال.",
        "j_steen_title": "بازبینی عملکرد استینبارگر", "j_steen_group": "گروه", "j_weekday": "روز هفته",
        "j_steen_empty": "معاملات را ثبت کنید تا ببینید کدام ستاپ‌ها، حالت‌های هیجانی و روزهای هفته واقعاً برایتان پول می‌سازند (یا می‌سوزانند).",
        "j_steen_read": "۱۰٪ معاملات برتر {top:.0f}٪ از سود ناخالص را ساخته‌اند (>۶۰٪ = سود وابسته به چند رخداد نادر — طالب). بدترین رشتهٔ باخت: {streak}. استینبارگر: فقط حالت‌ها و ستاپ‌های با امید ریاضی مثبت را معامله کن؛ در بقیه حجم را کم کن.",
        "vis_img_pat": "الگوی تصویری (یادگرفته)", "vis_ask": "بپرس", "vis_ask_ph": "از تحلیل‌گر دربارهٔ این نمودار بپرس (روند؟ سطوح؟ ریسک؟ الگو؟) — آفلاین",
        "ai_tab_an": "تحلیل‌گر (LLM آفلاین)", "ai_llm_status": "llama-cpp {llama} · مدل‌های GGUF در data/models: {gguf} · حالت: {mode}", "ai_llm_rules": "نویسندهٔ قاعده‌مند مستند (بدون فایل مدل)",
        "ai_bias": "سوگیری", "ai_confl": "هم‌راستایی", "ai_agree": "توافق", "ai_evidence": "شواهد", "ai_brief": "خلاصهٔ تحلیل‌گر",
        "ai_an_note": "کاربرد واقعی FinGPT و نسخه‌های مالی Llama·Mistral·DeepSeek·Qwen·Falcon: تبدیل سیگنال‌های متعدد به یک خلاصهٔ مستند. این بخش کاملاً آفلاین است. هر جمله به عددی که خود برنامه تولید کرده ارجاع می‌دهد؛ نویسنده هرگز عدد نمی‌سازد و دستور خرید/فروش نمی‌دهد. اگر یک GGUF مالی (مثل Qwen2.5-7B-Instruct مالی یا Mistral-7B مالی) در data/models بگذارید و llama-cpp-python نصب کنید، نویسندهٔ قاعده‌مند با LLM محلی واقعی جایگزین می‌شود — با همان پرامپت مستندسازی.",
        "proven_only": "فقط اثبات‌شده", "proven_only_tip": "فقط استراتژی‌هایی که در پلی‌بوک برون‌نمونه اثبات شده‌اند (با گیت وسعت) و در ممیزی پاک‌اند.",
        "nav_portfolio": "پرتفوی", "pf_title": "پرتفوی استراتژی‌های اثبات‌شده", "pf_sub": "فقط استراتژی‌هایی وارد می‌شوند که ممیزی و پلی‌بوک برون‌نمونه (با گیت وسعت) را گذرانده‌اند. اعضا با همبستگی پایین منحنی سرمایه انتخاب می‌شوند و هرکدام سهم برابری از بودجهٔ ریسک می‌گیرند — دو استراتژی که با هم می‌برند و می‌بازند یکی حساب می‌شوند.",
        "pf_max_n": "حداکثر استراتژی", "pf_max_corr": "حداکثر ρ", "pf_risk": "ریسک هر معامله", "pf_build": "ساخت پرتفوی", "pf_n_strats": "استراتژی‌ها", "cagr": "CAGR", "pf_risk_each": "ریسک هرکدام",
        "pf_curve": "سرمایهٔ برون‌نمونه (۶۰٪ آخر تاریخچه، روزانه، ٪)", "pf_members": "اعضا", "pf_breadth": "وسعت نماد/سال", "pf_weight": "وزن", "pf_combined": "ترکیبی",
        "pf_corr_avg": "میانگین ρ دوبه‌دو", "pf_years": "سال", "pf_none": "هنوز استراتژی اثبات‌شده‌ای در این تایم‌فریم نیست — اول پلی‌بوک را بسازید (مشاور ← ساخت).",
        "pf_note": "⚠ برون‌نمونه است ولی همچنان تاریخی: نتایج واقعی معمولاً ۳۰–۵۰٪ بدترند (هزینه‌ها مدل شده، ولی نه هر رژیمی). ماهانه بازسازی کنید؛ اگر PF فوروارد عضوی در ۳۰+ معامله زیر ۱ رفت حذفش کنید.",
        "al_tg": "تلگرام", "al_desktop": "دسکتاپ", "al_channels": "کانال‌ها", "al_min_conf": "حداقل اطمینان", "al_tfs": "تایم‌فریم‌ها", "al_test": "ارسال آزمایشی", "al_scan_now": "اسکن اکنون",
        "al_test_body": "اعلان دسکتاپ کار می‌کند.", "al_sent": "هشدار جدید", "alerts": "هشدارها (تلگرام / دسکتاپ)", "save": "ذخیره", "saved": "ذخیره شد",
        "train_idle": "وضعیت خودآموزی…", "train_running": "خودآموزی", "train_audit": "ممیزی استراتژی‌ها", "train_quick": "پلی‌بوک سریع (1d/4h/1h)", "train_full": "پلی‌بوک کامل (همهٔ تایم‌فریم‌ها)",
        "train_done": "بات آموزش دیده و بازار را زیر نظر دارد", "train_proven": "ترکیب اثبات‌شده", "train_tfs": "تایم‌فریم‌ها", "days": "روز پیش",
        "nav_ai": "میز هوش مصنوعی", "ai_title": "میز هوش مصنوعی — پیش‌بینی، احساسات، یادگیری تقویتی، هم‌ارزی موتورها",
        "ai_sub": "همه‌چیز اینجا صادقانه با خطوط پایهٔ ساده مقایسه می‌شود. مدلی که «فردا = امروز» را شکست ندهد، همان‌طور نشان داده می‌شود.",
        "ai_tab_fc": "پیش‌بینی", "ai_tab_sent": "احساسات", "ai_tab_rl": "عامل RL", "ai_tab_eng": "موتورها",
        "ai_run": "اجرا", "ai_horizon": "افق (کندل)", "ai_model": "مدل", "ai_mase": "MASE", "ai_rmse": "RMSE", "ai_diracc": "دقت جهت", "ai_vsnaive": "نسبت به ساده", "ai_pval": "p-value",
        "ai_fc_note": "MASE < 1 و «نسبت به ساده» < 1 یعنی مدل در {n} مبدأ غلتان برون‌نمونه‌ای پیش‌بینی ساده را شکست داده. دقت جهت نزدیک ۵۰٪ در بازارهای نقد طبیعی است — این خط پایهٔ بازار کاراست.",
        "ai_fc_band": "روند Prophet-گونه + باند نقاط تغییر", "ai_q": "پیش‌بینی چندکی (GBR pinball)", "ai_cp": "نقاط تغییر CUSUM", "ai_verdict": "حکم",
        "ai_fc_good": "بعضی مدل‌ها ساده را شکست دادند — فقط به‌عنوان تمایل ضعیف استفاده کنید، هرگز به‌تنهایی سیگنال نیست.", "ai_fc_bad": "هیچ مدلی اینجا ساده را شکست نداد — پیش‌بینی روی این سری چیزی اضافه نمی‌کند؛ به پرایس‌اکشن و ریسک تکیه کنید.",
        "ai_headlines": "تیترها (هر خط یکی) — یا دریافت کنید", "ai_fetch": "دریافت اخبار", "ai_score": "امتیازدهی", "ai_headline": "تیتر", "ai_compound": "امتیاز مرکب", "ai_subj": "ذهنیت", "ai_tickers": "نمادها", "ai_regime": "رژیم", "ai_crowded": "شلوغ؟", "ai_sent_mean": "میانگین احساس", "ai_pos": "٪ مثبت", "ai_neg": "٪ منفی", "ai_backend": "موتور",
        "ai_sent_note": "واژه‌نامه = قواعد VADER (نفی، تشدیدکننده، حروف بزرگ، «!») + واژگان مالی Loughran-McDonald. اگر transformers + FinBERT نصب باشد ستون FinBERT پر می‌شود. «شلوغ» = هم‌صدا + هیجانی + ذهنی → پرچم ریسک خلاف‌جهت (کانمن / داگلاس).",
        "ai_agent": "عامل", "ai_episodes": "اپیزود", "ai_seeds": "بذرها", "ai_reward": "پاداش", "ai_seed": "بذر", "ai_train": "آموزش", "ai_val": "اعتبارسنجی", "ai_test": "آزمون", "ai_dd": "افت آزمون", "ai_sharpe": "شارپ آزمون", "ai_trades": "معاملات",
        "ai_bh": "خرید و نگهداری (آزمون)", "ai_rand95": "تصادفی p95 (آزمون)", "ai_gap": "شکاف بیش‌برازش", "ai_rl_note": "عامل‌های Q-learning خطی / policy-gradient روی محیطی به سبک TensorTrade (ویژگی‌های پنجره‌ای، هزینه، پاداش لگ‌بازده یا شارپ تفاضلی). اگر Stable-Baselines3 نصب باشد خودکار استفاده می‌شود. فقط ستون «آزمون» را بخوانید؛ آموزش همیشه فریبنده است. عاملی که تصادفی-p95 یا خرید‌ونگهداری را شکست ندهد، نویز یاد گرفته.",
        "ai_rl_good": "عامل در بخش آزمون هم خرید‌ونگهداری و هم صدک ۹۵ عامل‌های تصادفی را شکست داد — همچنان شکننده است؛ پژوهشی بدانید.", "ai_rl_bad": "عامل برون‌نمونه تصادفی/خرید‌ونگهداری را شکست نمی‌دهد. این نتیجهٔ عادی و صادقانه است.",
        "ai_parity": "هم‌ارزی برداری در برابر رویدادمحور", "ai_engine": "موتور", "ai_ret": "بازده ٪", "ai_pf": "PF", "ai_sqn": "SQN", "ai_eng_note": "موتور رویدادمحور به سبک Backtrader (پرشدن در کندل بعد، سفارش براکت، سایزر ریسک، تحلیل‌گر SQN) روی همان سیگنال‌های بک‌تستر برداری اجرا می‌شود. شکاف کوچک (< ۱٪ بازده، تعداد معاملهٔ برابر) یعنی هر دو قابل‌اعتمادند؛ شکاف بزرگ نشانهٔ نگاه‌به‌آینده یا فرض پرشدن است.",
        "ai_pipeline": "پایپ‌لاین Zipline — رتبهٔ مومنتوم مقطعی", "ai_framework": "چارچوب LEAN — آلفا ← پرتفوی ← ریسک ← اجرا", "ai_freqai": "برنامهٔ بازآموزی FreqAI",
        "ai_running": "در حال اجرا…", "ai_done": "انجام شد", "ai_offline": "تیتری دریافت نشد (آفلاین؟) — چند تیتر بچسبانید.",
        "nav_vision": "بینایی نمودار", "vis_title": "بینایی نمودار — درک تصویر نمودار",
        "vis_sub": "اسکرین‌شات یا عکس هر نمودار شمعی (TradingView، MetaTrader، Binance، تم روشن یا تیره) را رها کنید. موتور با OpenCV کندل‌ها را جدا می‌کند، سری OHLC را بازسازی می‌کند و همان منطق الگوهای نیسون/بالکوفسکی، روند و حمایت/مقاومتِ داده‌های زنده را روی آن اجرا و توضیح می‌دهد. اختیاری: قیمت بالا و پایین محور قابل‌مشاهده را وارد کنید تا سطوح واقعی به دست آید. تست خودکار دقت اندازه‌گیری‌شده روی نمودارهای مصنوعی را نشان می‌دهد. روی اسکرین‌شات‌های واقعی متاتریدر / تریدینگ‌ویو / اپ بایننس تست شده (۱۱ از ۱۱ با خطای شمارش ≤۲۰٪). بهترین ورودی: اسکرین‌شات تمیز؛ عکس از مانیتور حدود ۳۰٪ کندل‌ها را از دست می‌دهد — اگر مجبورید، فقط ناحیهٔ قیمت را برش دهید.",
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
        "nav_fast": "سیگنال سریع", "tg_token": "توکن بات تلگرام (اختیاری)", "tg_chat": "شناسهٔ چت تلگرام", "web_mobile": "وب و موبایل", "web_start": "راه‌اندازی سرور وب/موبایل", "web_stop": "توقف سرور وب", "web_tip": "همان موتور (چارت، سیگنال‌ها با درصد موفقیت، مشاور، سیگنال سریع، آکادمی) را به هر گوشی یا مرورگر در شبکهٔ شما می‌دهد. برای دسترسی اینترنتی یک تونل (cloudflared / ngrok) روی این پورت بزنید.", "web_hint": "در گوشی (همان وای‌فای) باز کنید یا QR را اسکن کنید. «افزودن به صفحهٔ اصلی» = تجربهٔ اپ.", "ql_vol_ann": "نوسان (سالانه)", "ql_range_pct": "رنج ٪", "ql_spread_proxy": "تخمین اسپرد ٪", "ql_quote_vol": "حجم (ارز مظنه)", "success_rate_all": "درصد موفقیت در همهٔ بازارهای تست‌شده", "median_pf": "میانهٔ PF", "pos_share": "سهم سودده", "markets": "بازار", "success_unknown": "درصد موفقیت این استراتژی هنوز محاسبه نشده — آن را روی چارت باز کنید، اسکنر را اجرا کنید یا در تنظیمات «محاسبهٔ درصد موفقیت» را بزنید.", "tz_local": "ساعت کامپیوتر (محلی)", "time_display": "نمایش زمان", "succ_compute": "محاسبهٔ درصد موفقیت (همهٔ استراتژی‌ها × ۵ ارز اصلی × ۴ تایم‌فریم)", "succ_compute_tip": "همهٔ استراتژی‌ها را روی BTC/ETH/SOL/BNB/XRP در ۱۵m/۱h/۴h/۱d با کارمزد بک‌تست می‌کند و WR/PF را کنار هر سیگنال ذخیره می‌کند. ۱۰ تا ۲۰ دقیقه، در پس‌زمینه.", "clock_tip": "زمان محلی = ساعت کامپیوتر شما (دقیقاً منطقهٔ زمانی سیستم) · UTC = زمان جهانی", "tool_cursor": "نشانگر (روی مارکر سیگنال کلیک کنید تا جزئیاتش را ببینید)", "tool_trend": "خط روند (۲ کلیک)", "tool_ray": "پرتو (۲ کلیک)", "tool_hline": "خط افقی", "tool_vline": "خط عمودی", "tool_rect": "مستطیل / ناحیه (۲ کلیک)", "tool_fib": "فیبوناچی اصلاحی (۲ کلیک: کف → سقف)", "tool_text": "یادداشت متنی", "tool_text_prompt": "متن یادداشت:", "tool_measure": "اندازه‌گیری (درصد قیمت · کندل · زمان)", "tool_erase": "پاک‌کن (روی رسم کلیک کنید)", "tool_undo": "برگرداندن آخرین رسم", "tool_clear": "پاک‌کردن همهٔ رسم‌های این چارت", "ind_add": "افزودن اندیکاتور", "ind_list_tip": "اندیکاتورهای روی این چارت", "ind_remove": "حذف اندیکاتور انتخاب‌شده", "ind_templates": "قالب‌های اندیکاتور", "tpl_ichimoku": "ابر ایچیموکو", "tpl_classic": "کلاسیک (EMA 20/50/200 + RSI + MACD)", "tpl_scalp": "اسکالپ (VWAP، BB، استوکاستیک، CVD، RVOL)", "tpl_volume": "حجم (پروفایل، OBV، CMF، MFI)", "tpl_trend": "روند (سوپرترند، ADX، KAMA، PSAR)", "refresh_keep": "رفرش", "refresh_keep_tip": "بارگذاری مجدد داده و اعمال تنظیمات جدید بدون از دست رفتن زوم/موقعیت شما", "tz_toggle_tip": "تغییر زمان چارت: محلی (ساعت کامپیوتر) ↔ UTC", "outcome": "نتیجه", "signals_click_tip": "روی ردیف کلیک کنید → چارت به همان سیگنال می‌رود و محل و زمانش را نشان می‌دهد", "win": "برد", "loss": "باخت", "open_or_na": "باز / ندارد", "success_rate": "درصد موفقیت (این نماد و تایم‌فریم)", "in_sample": "درون‌نمونه، با کارمزد", "oos_rate": "برون‌نمونه (پلی‌بوک)", "local_time": "محلی", "bars": "کندل", "search": "جستجو…", "fs_wfo": "تنظیم واک‌فوروارد", "fs_wfo_tip": "واک‌فوروارد لنگری ۴ دستگیرهٔ هم‌گرایی (رأی، پنجره، استاپ ATR، RR) برای هر نماد؛ PF برون‌نمونه و WFE را نشان می‌دهد. ۱ تا ۳ دقیقه.", "fs_wfo_head": "حکم واک‌فوروارد (برون‌نمونه) برای هر نماد — فقط «لبه» یعنی قانون هم‌گرایی روی دادهٔ دیده‌نشده دوام آورده:", "fs_wfo_done": "واک‌فوروارد تمام شد · پیش‌فرض‌ها به‌روز شد", "fs_verdict_edge": "✅ لبه", "fs_verdict_weak": "⚠ ضعیف", "fs_verdict_none": "❌ هیچ", "fs_title": "⚡ سیگنال سریع — رادار هم‌گرایی تایم‌فریم پایین", "fs_sub": "جفت‌های برتر را روی ۱ تا ۱۵ دقیقه با ۲۱ روش اسکالپ/اردرفلو (پولبک/باند VWAP، برگشت ناحیهٔ ارزش، جریان Triple-A، عدم‌تعادل انباشته، شکست LVN، تایم‌فریم لنگر، استوکاستیک BB صاف، دیپ NFI، حراج ناتمام، واگرایی CVD، استاپ‌ران، H2/L2 بروکس، پاپ اسکوئیز، ORB سشن، سه‌تأییده، واگرایی RSI سریع، کلایمکس حجمی، ازدحام فاندینگ، گسترش IB) به‌علاوهٔ ست کلاسیک روزانه اسکن می‌کند. ستاپ فقط وقتی نمایش داده می‌شود که چند روش مستقل هم‌نظر باشند، گیت روند رد شود و حرکت مورد انتظار کارمزد را پوشش دهد. هر ردیف وین‌ریت/PF صادقانهٔ همان قانون روی همان نماد را دارد.", "fs_scan": "اسکن کن", "fs_auto": "خودکار هر ۵ دقیقه", "fs_min_votes": "حداقل روش‌های هم‌نظر", "fs_fee_tier": "سطح کارمزد", "fs_scanned": "اسکن‌شده", "fs_setups": "ستاپ‌ها", "fs_best": "بهترین", "fs_cost_ok": "از نظر هزینه قابل قبول", "fs_session": "سشن", "fs_table": "ستاپ‌های هم‌گرایی (دابل‌کلیک → چارت)", "fs_score": "امتیاز", "fs_votes": "رأی", "fs_move": "حرکت مورد انتظار", "fs_cost": "هزینهٔ رفت‌وبرگشت", "fs_agree": "روش‌های هم‌نظر", "fs_explain": "چرا این ستاپ (و چرا ممکن است شکست بخورد)", "fs_done": "تمام · {n} ستاپ", "fs_note": "نکتهٔ صادقانه: در تست ۵۰٬۰۰۰ کندلی BTC/ETH/SOL (۵ و ۱۵ دقیقه) هر روش اسکالپ به‌تنهایی بعد از کارمزد واقعی ضرر می‌دهد (PF ۰.۲ تا ۰.۹). فقط هم‌گرایی ≥۳ روش با گیت روند به PF ≈ ۱.۰ تا ۱.۸ رسید، آن هم با معاملات کم. این‌ها را کاندیدای فوروارد تست بدانید (صفحهٔ فوروارد تست ثبتشان می‌کند)، نه سود تضمینی. کارمزد میکر (سفارش لیمیت) تعداد ستاپ‌های قابل قبول را تقریباً دو برابر می‌کند.",
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
        "acad_tab_strats": "استراتژی‌ها", "acad_tab_inds": "دانشنامهٔ اندیکاتورها (۸۰)",
        "ind_how": "نحوهٔ محاسبه", "ind_read": "نحوهٔ خواندن و معامله", "ind_used": "استفاده‌شده در استراتژی‌های",
        "ind_params": "پارامترها", "ind_uses": "همهٔ کاربردها", "ind_signals": "قواعد سیگنال مشخص", "ind_pitfalls": "دام‌ها", "ind_combos": "بهترین ترکیب با",
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
        "nav_tv": "چارت پیشرفته",
        "symbol": "نماد", "timeframe": "تایم‌فریم", "strategy": "استراتژی", "load": "بارگذاری", "run": "اجرا",
        "loading": "در حال دریافت داده…", "ready": "آماده", "next_bar": "کندل بعدی تا", "chart_renderer": "موتور رسم چارت", "chart_auto": "خودکار (تشخیص چارت خالی)", "chart_compat": "سازگار (نرم‌افزاری، همیشه نمایش داده می‌شود)", "chart_renderer_tip": "اگر ناحیهٔ چارت روی سیستم شما خالی می‌ماند، «سازگار» را انتخاب کنید. حالت خودکار در صورت تشخیص چارت خالی خودش سوئیچ می‌کند.", "stale_cache": "کش قدیمی — منبع زنده در دسترس نیست", "category": "دسته", "all": "همه",
        "signals": "سیگنال‌های اخیر", "time": "زمان", "side": "جهت", "price": "قیمت", "stop": "حد ضرر", "target": "حد سود",
        "rr": "ریسک/ریوارد", "long": "خرید", "short": "فروش", "no_signal": "روی کندل آخر سیگنالی نیست",
        "last_signal": "آخرین سیگنال", "bars_ago": "کندل قبل",
        "q_filter": "کیفیت", "q_proven_only": "فقط اثبات‌شده", "q_candidate": "اثبات‌شده + نامزدها", "q_all": "نمایش همه (حتی اثبات‌نشده)",
        "q_tip": "دروازهٔ اعتماد: اثبات‌شده = کران پایین PF برون‌نمونه > ۱، n ≥ ۵۰، فوروارد تست مخالف نباشد. استراتژی‌های اثبات‌نشده/شکست‌خورده به‌طور پیش‌فرض پنهان‌اند.",
        "q_verdict": "حکم", "q_hidden": "پنهان‌شده توسط دروازهٔ کیفیت", "q_why": "دلیل این حکم",
        "news_filter": "توقف هشدارها حوالی اخبار پرریسک (FOMC/CPI/NFP)", "quality_mode": "هشدار فقط برای",
        "scan": "اسکن بازار", "plan": "برنامهٔ معامله", "plan_hint": "روی یک ردیف راست‌کلیک کنید (یا انتخاب و دکمهٔ برنامهٔ معامله) تا سازگاری با رژیم، فرسایش لبه، هم‌جهتی با تایم‌فریم بالاتر، مونت‌کارلو و حجم پیشنهادی را ببینید.", "scanning": "در حال اسکن…", "scan_hint": "فقط استراتژی‌های اثبات‌شده روی این تایم‌فریم و کلاس دارایی (کتاب راهنما) را روی همهٔ نمادها اجرا می‌کند و سیگنال‌های تازه (N کندل آخر) را لیست می‌کند. استراتژی‌های قفل‌شده پنهان‌اند.",
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
        "welcome_sub": "{n} استراتژی (ایچیموکو · اندیکاتورها · استادان جهان) · ۱۵ بات · ۳۷ کتاب · آزمایشگاه کوانت · تست پیش‌رو · خودتشخیصی · کتاب راهنمای نمره‌دار (بازهٔ اطمینان) تایم‌فریم ۵m→۱d · مشاور · ۷۳ اندیکاتور + درصد موفقیت کنار هر سیگنال · استریم زندهٔ کل بازار · آزمایشگاه ML · اعتبارسنجی · آنسامبل · بک‌تستر · آکادمی",
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
