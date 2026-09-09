"""
Phase 24 — Edge analytics & trade plan ("how should I actually trade this signal?").

The quality gate (core.quality) answers *whether* a strategy has an edge. This module answers the questions a
professional asks right after that, for ONE concrete signal:

  1. regime fit      — does this strategy make money in the CURRENT market regime (trend / range / mixed, bull / bear)?
                       Trades are split by the regime that prevailed at their entry bar; PF and n per regime.
  2. edge decay      — PF of the last 12 months vs. the whole history (a decayed edge is not an edge).
  3. HTF alignment   — is the signal with or against the higher-timeframe trend (EMA50/200 + slope on the next tf up)?
  4. Monte-Carlo risk — for the NEXT 50 trades at a given risk %: P(loss), median return, 95th-percentile drawdown.
  5. suggested risk  — fractional Kelly (¼) capped by the trust score, regime fit and HTF alignment → "risk x % of equity".
  6. trade plan      — entry / stop / TP1 (1R) / TP2 (strategy target) / expected hold / invalidation / avoid-if list,
                       in FA and EN, with every number explainable.

Everything is derived from the same backtest the rest of the program uses (core.backtest.run_backtest with the realistic
cost model), so the plan is consistent with the success % shown next to the signal.
"""
import math
import numpy as np
import pandas as pd

NEXT_TF = {"1m": "5m", "3m": "15m", "5m": "15m", "15m": "1h", "30m": "4h", "1h": "4h", "2h": "1d", "4h": "1d", "12h": "1d", "1d": "1wk", "1wk": "1mo"}
TF_MIN = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240, "12h": 720, "1d": 1440, "1wk": 10080, "1mo": 43200}


# ------------------------------------------------------------------------------------------------- regime series
def regime_series(df):
    """Per-bar regime labels (vectorised): kind ∈ {trend, range, mixed}, bias ∈ {+1, -1, 0}.
    Same thresholds as core.advisor.regime (ADX 25/20, choppiness 55/61.8, EMA50/200 stack) so the UI stays consistent."""
    from core import indicators as ta
    from core.indicators2 import choppiness
    adx, _, _ = ta.adx(df)
    ch = choppiness(df)
    e50, e200 = ta.ema(df.close, 50), ta.ema(df.close, 200)
    px = df.close
    bias = np.where((px > e50) & (e50 > e200), 1, np.where((px < e50) & (e50 < e200), -1, 0))
    kind = np.where((adx > 25) & (ch < 55), "trend", np.where((adx < 20) | (ch > 61.8), "range", "mixed"))
    return pd.DataFrame({"kind": kind, "bias": bias}, index=df.index)


def current_regime(df):
    r = regime_series(df).iloc[-1]
    return dict(kind=str(r["kind"]), bias=int(r["bias"]))


# ------------------------------------------------------------------------------------------------- regime fit
def _pf(p):
    p = np.asarray(p, float)
    g, l = p[p > 0].sum(), -p[p < 0].sum()
    return float(min(g / l, 99.0)) if l > 0 else (99.0 if g > 0 else 0.0)


def regime_fit(df, trades, reg=None):
    """Split the backtest trades by the regime at entry → {regime_key: dict(n, pf, wr, avg_r)} plus the current regime key.
    Keys: 'trend', 'range', 'mixed' and 'bull', 'bear', 'flat'."""
    reg = reg if reg is not None else regime_series(df)
    kinds = reg["kind"].reindex([t.entry_time for t in trades]).values if trades else np.array([])
    biases = reg["bias"].reindex([t.entry_time for t in trades]).values if trades else np.array([])
    out = {}
    pnl = np.array([t.pnl_pct for t in trades], float) if trades else np.array([])
    rr = np.array([t.r_multiple for t in trades], float) if trades else np.array([])
    for key, mask in (("trend", kinds == "trend"), ("range", kinds == "range"), ("mixed", kinds == "mixed"),
                      ("bull", biases == 1), ("bear", biases == -1), ("flat", biases == 0)):
        m = np.asarray(mask, bool)
        if m.sum() == 0:
            out[key] = dict(n=0, pf=float("nan"), wr=float("nan"), avg_r=float("nan"))
            continue
        out[key] = dict(n=int(m.sum()), pf=_pf(pnl[m]), wr=float((pnl[m] > 0).mean() * 100), avg_r=float(rr[m].mean()))
    cur = reg.iloc[-1]
    now_kind, now_bias = str(cur["kind"]), int(cur["bias"])
    bias_key = {1: "bull", -1: "bear", 0: "flat"}[now_bias]
    fit_k, fit_b = out[now_kind], out[bias_key]
    # fit verdict: needs ≥15 trades in this regime to say anything; PF≥1.1 = fits, <0.9 = does not fit
    def verdict(d):
        if d["n"] < 15:
            return "unknown"
        return "fits" if d["pf"] >= 1.1 else ("misfit" if d["pf"] < 0.9 else "neutral")
    return dict(by=out, now_kind=now_kind, now_bias=now_bias, kind_fit=verdict(fit_k), bias_fit=verdict(fit_b),
                kind_stats=fit_k, bias_stats=fit_b)


# ------------------------------------------------------------------------------------------------- decay
def edge_decay(trades, days=365):
    """PF last `days` vs overall. ratio < 0.7 with ≥10 recent trades → 'decayed'."""
    if not trades:
        return dict(pf_all=float("nan"), pf_recent=float("nan"), n_recent=0, ratio=float("nan"), status="unknown")
    pnl_all = np.array([t.pnl_pct for t in trades], float)
    cutoff = max(t.exit_time for t in trades) - pd.Timedelta(days=days)
    rec = np.array([t.pnl_pct for t in trades if t.exit_time >= cutoff], float)
    pf_all = _pf(pnl_all); pf_rec = _pf(rec) if len(rec) else float("nan")
    ratio = pf_rec / pf_all if pf_all and pf_all == pf_all and pf_rec == pf_rec and pf_all > 0 else float("nan")
    if len(rec) < 10:
        st = "unknown"
    elif ratio < 0.7 or pf_rec < 0.9:
        st = "decayed"
    elif ratio > 1.15:
        st = "improving"
    else:
        st = "stable"
    return dict(pf_all=pf_all, pf_recent=pf_rec, n_recent=int(len(rec)), ratio=ratio, status=st)


# ------------------------------------------------------------------------------------------------- HTF alignment
def htf_alignment(sym, tf, side, df_htf=None):
    """Higher-timeframe bias via EMA50/200 stack + 20-bar EMA200 slope on the next timeframe up.
    → dict(tf, bias, slope_pct, aligned ∈ {True, False, None})."""
    htf = NEXT_TF.get(tf)
    if not htf:
        return dict(tf=None, bias=0, slope_pct=0.0, aligned=None)
    try:
        if df_htf is None:
            from core.data import get_ohlcv
            df_htf = get_ohlcv(sym, htf)
        from core import indicators as ta
        e50, e200 = ta.ema(df_htf.close, 50), ta.ema(df_htf.close, 200)
        px = float(df_htf.close.iloc[-1]); a, b = float(e50.iloc[-1]), float(e200.iloc[-1])
        slope = float(e200.iloc[-1] / e200.iloc[-21] - 1) * 100 if len(e200) > 21 else 0.0
        bias = 1 if (px > a > b) else (-1 if (px < a < b) else (1 if px > b and slope > 0 else (-1 if px < b and slope < 0 else 0)))
        aligned = None if bias == 0 else (bias == side)
        return dict(tf=htf, bias=bias, slope_pct=slope, aligned=aligned)
    except Exception:
        return dict(tf=htf, bias=0, slope_pct=0.0, aligned=None)


# ------------------------------------------------------------------------------------------------- Monte Carlo
def mc_next_trades(trades, risk_pct=1.0, horizon=50, n_sims=3000, seed=5):
    """Bootstrap the R-multiples of past trades → distribution of the NEXT `horizon` trades at `risk_pct` per trade
    (equity compounding). Returns P(loss), median / p5 / p95 return %, p95 max drawdown %, and the longest losing
    streak you should be prepared for (p95)."""
    r = np.array([t.r_multiple for t in trades], float) if trades else np.array([])
    r = r[np.isfinite(r)]
    if len(r) < 10:
        return dict(n_src=int(len(r)), prob_loss=float("nan"), ret_med=float("nan"), ret_p5=float("nan"), ret_p95=float("nan"),
                    dd_p95=float("nan"), streak_p95=0, horizon=horizon, risk_pct=risk_pct)
    rng = np.random.default_rng(seed)
    f = risk_pct / 100.0
    seq = rng.choice(r, size=(n_sims, horizon), replace=True)
    eq = np.cumprod(1 + np.clip(seq * f, -0.95, None), axis=1)
    peak = np.maximum.accumulate(eq, axis=1)
    dd = (1 - eq / peak).max(axis=1) * 100
    ret = (eq[:, -1] - 1) * 100
    # losing streaks
    loss = seq <= 0
    streaks = np.zeros(n_sims)
    for s in range(n_sims):
        best = cur = 0
        for x in loss[s]:
            cur = cur + 1 if x else 0
            best = max(best, cur)
        streaks[s] = best
    return dict(n_src=int(len(r)), prob_loss=float((ret < 0).mean() * 100), ret_med=float(np.median(ret)), ret_p5=float(np.percentile(ret, 5)),
                ret_p95=float(np.percentile(ret, 95)), dd_p95=float(np.percentile(dd, 95)), streak_p95=int(np.percentile(streaks, 95)),
                horizon=horizon, risk_pct=risk_pct)


# ------------------------------------------------------------------------------------------------- suggested risk
def suggested_risk(trades, trust_score, fit, htf, decay, cap_pct=1.0, floor_pct=0.1):
    """¼-Kelly from the R-multiple distribution, then scaled by trust (0..1), regime fit and HTF alignment.
    Returns dict(kelly_full, kelly_quarter, risk_pct, factors, note_en, note_fa). Never above cap_pct; 0 when the
    evidence says 'do not trade'."""
    r = np.array([t.r_multiple for t in trades], float) if trades else np.array([])
    r = r[np.isfinite(r)]
    reasons_en, reasons_fa = [], []
    if len(r) < 20:
        return dict(kelly_full=0.0, kelly_quarter=0.0, risk_pct=0.0, factors={}, note_en="fewer than 20 trades — no size recommendation", note_fa="کمتر از ۲۰ معامله — پیشنهاد حجم داده نمی‌شود")
    wr = float((r > 0).mean()); aw = float(r[r > 0].mean()) if (r > 0).any() else 0.0; al = float(-r[r <= 0].mean()) if (r <= 0).any() else 1.0
    b = aw / al if al > 0 else 0.0
    kelly = (wr * b - (1 - wr)) / b if b > 0 else 0.0
    kelly = max(0.0, kelly)                       # fraction of equity to risk per trade (in units of "1R = avg loss")
    kq = kelly / 4
    factors = {}
    factors["trust"] = max(0.0, min(1.0, trust_score / 100.0))
    factors["regime"] = {"fits": 1.0, "neutral": 0.8, "unknown": 0.7, "misfit": 0.0}[fit["kind_fit"]]
    factors["htf"] = 1.0 if htf.get("aligned") is True else (0.6 if htf.get("aligned") is False else 0.85)
    factors["decay"] = {"improving": 1.0, "stable": 1.0, "unknown": 0.85, "decayed": 0.3}[decay["status"]]
    scale = 1.0
    for v in factors.values():
        scale *= v
    risk = kq * 100 * scale                       # kq is a fraction; express in % of equity
    risk = 0.0 if scale == 0 else max(floor_pct, min(cap_pct, risk))
    if kelly <= 0:
        risk = 0.0; reasons_en.append("negative Kelly (no positive expectancy)"); reasons_fa.append("کِلی منفی (امید ریاضی مثبت نیست)")
    if factors["regime"] == 0:
        reasons_en.append("strategy loses in the current regime"); reasons_fa.append("استراتژی در رژیم فعلی بازار ضررده است")
    if factors["htf"] < 1:
        reasons_en.append("against / without higher-timeframe trend"); reasons_fa.append("خلاف روند تایم‌فریم بالاتر یا بدون تأیید آن")
    if factors["decay"] < 1:
        reasons_en.append(f"edge {decay['status']}"); reasons_fa.append({"decayed": "لبه فرسوده شده", "unknown": "روند لبه نامشخص"}.get(decay["status"], ""))
    return dict(kelly_full=round(kelly * 100, 2), kelly_quarter=round(kq * 100, 2), risk_pct=round(risk, 2), factors=factors,
                note_en="; ".join(reasons_en) or "full size (within cap)", note_fa="؛ ".join(x for x in reasons_fa if x) or "حجم کامل (تا سقف)")


# ------------------------------------------------------------------------------------------------- trade plan
def trade_plan(sym, tf, sid, df=None, res=None, bt=None, i=None, equity=10_000.0, cap_pct=1.0, lang_both=True):
    """Everything above for the latest (or i-th) signal of `sid` on sym/tf → one JSON-able dict.
    Heavy parts (backtest) are reused if `bt`/`res` are passed by the caller (scanner / API cache)."""
    import strategies as S
    from core.backtest import run_backtest
    from core import quality as Q, calendar as CAL, playbook as PB
    if df is None:
        from core.data import get_ohlcv
        df = get_ohlcv(sym, tf)
    cls = S.REGISTRY[sid]
    res = res if res is not None else cls().run(df)
    bt = bt if bt is not None else run_backtest(df, res, symbol=sym)
    sig = res.signal.fillna(0).astype(int).values
    if i is None:
        nz = np.where(sig != 0)[0]
        if len(nz) == 0:
            return dict(error="no signal", sym=sym, tf=tf, sid=sid)
        i = int(nz[-1])
    side = int(sig[i]); px = float(df.close.values[i])
    sl = float(res.stop.values[i]) if res.stop is not None and res.stop.values[i] == res.stop.values[i] else float("nan")
    tp = float(res.target.values[i]) if res.target is not None and res.target.values[i] == res.target.values[i] else float("nan")
    from core.indicators import atr as _atr
    atr = float(_atr(df).bfill().values[i])
    if not (sl == sl) or (side == 1 and sl >= px) or (side == -1 and sl <= px):
        sl = px - side * 2.0 * atr
    if not (tp == tp) or (side == 1 and tp <= px) or (side == -1 and tp >= px):
        tp = px + side * 4.0 * atr
    risk_per_unit = abs(px - sl)
    tp1 = px + side * risk_per_unit                     # 1R partial
    rr = abs(tp - px) / risk_per_unit if risk_per_unit > 0 else float("nan")
    reg = regime_series(df)
    fit = regime_fit(df, bt.trades, reg)
    decay = edge_decay(bt.trades)
    htf = htf_alignment(sym, tf, side)
    qs = Q.score(sid, sym, tf)
    mc1 = mc_next_trades(bt.trades, risk_pct=1.0)
    size = suggested_risk(bt.trades, qs["score"], fit, htf, decay, cap_pct=cap_pct)
    mc = mc_next_trades(bt.trades, risk_pct=size["risk_pct"]) if size["risk_pct"] > 0 else mc1
    risk_amt = equity * size["risk_pct"] / 100
    units = risk_amt / risk_per_unit if risk_per_unit > 0 and size["risk_pct"] > 0 else 0.0
    hold_min = PB.expected_hold(tf, sym, sid) if tf in ("5m", "15m", "30m", "1h", "4h", "1d") else None
    if hold_min is None:
        bars = [t.bars for t in bt.trades]
        hold_min = float(np.median(bars)) * TF_MIN.get(tf, 60) if bars else None
    news = CAL.risk_now()
    # avoid-if list
    avoid_en, avoid_fa = [], []
    if news:
        avoid_en.append("high-impact news window is open"); avoid_fa.append("در بازهٔ خبر پرریسک هستیم")
    if fit["kind_fit"] == "misfit":
        avoid_en.append(f"strategy loses in '{fit['now_kind']}' regime (PF {fit['kind_stats']['pf']:.2f}, n={fit['kind_stats']['n']})")
        avoid_fa.append(f"استراتژی در رژیم «{ {'trend': 'روند', 'range': 'رنج', 'mixed': 'مختلط'}[fit['now_kind']] }» ضررده است (PF {fit['kind_stats']['pf']:.2f}، n={fit['kind_stats']['n']})")
    if htf.get("aligned") is False:
        avoid_en.append(f"against the {htf['tf']} trend"); avoid_fa.append(f"خلاف روند {htf['tf']}")
    if decay["status"] == "decayed":
        avoid_en.append(f"edge decayed: PF last 12m {decay['pf_recent']:.2f} vs {decay['pf_all']:.2f} overall")
        avoid_fa.append(f"لبه فرسوده شده: PF ۱۲ ماه اخیر {decay['pf_recent']:.2f} در برابر {decay['pf_all']:.2f} کل")
    if qs["verdict"] in ("UNPROVEN", "FAILED"):
        avoid_en.append(f"strategy verdict is {qs['verdict']}"); avoid_fa.append(f"حکم استراتژی: {Q.VERDICT_FA[qs['verdict']]}")
    if rr == rr and rr < 1.0:
        avoid_en.append(f"reward:risk only {rr:.2f}"); avoid_fa.append(f"نسبت سود به ریسک فقط {rr:.2f}")
    go = (size["risk_pct"] > 0) and not avoid_en
    hold_txt = None
    if hold_min:
        hold_txt = f"{hold_min / 60:.1f} h" if hold_min < 2880 else f"{hold_min / 1440:.1f} d"
    plan = dict(sym=sym, tf=tf, sid=sid, name_en=cls.name_en, name_fa=cls.name_fa, side=side, bar=str(df.index[i]), ago=int(len(df) - 1 - i),
                entry=px, stop=sl, tp1=tp1, tp2=tp, rr=rr, atr=atr, stop_atr=risk_per_unit / atr if atr else float("nan"),
                regime=dict(kind=fit["now_kind"], bias=fit["now_bias"], kind_fit=fit["kind_fit"], bias_fit=fit["bias_fit"], by=fit["by"]),
                decay=decay, htf=htf, trust=dict(score=qs["score"], verdict=qs["verdict"]), mc=mc, size=size,
                position=dict(equity=equity, risk_pct=size["risk_pct"], risk_amount=risk_amt, units=units, notional=units * px),
                expected_hold=hold_txt, news=bool(news), go=go, avoid_en=avoid_en, avoid_fa=avoid_fa,
                verdict_en="GO" if go else ("REDUCED" if size["risk_pct"] > 0 else "NO-TRADE"),
                verdict_fa="ورود" if go else ("ورود با حجم کم" if size["risk_pct"] > 0 else "بدون معامله"))
    plan["text_en"] = plan_text(plan, "en"); plan["text_fa"] = plan_text(plan, "fa")
    return plan


def plan_text(p, lang="en"):
    fa = lang == "fa"
    side = ("خرید" if p["side"] == 1 else "فروش") if fa else ("LONG" if p["side"] == 1 else "SHORT")
    kind_fa = {"trend": "روند", "range": "رنج", "mixed": "مختلط"}
    L = []
    if fa:
        L.append(f"**{p['verdict_fa']}** — {side} {p['sym']} در {p['tf']} با {p['name_fa']} (اعتماد {p['trust']['score']}/۱۰۰)")
        L.append(f"ورود {p['entry']:,.6g} · استاپ {p['stop']:,.6g} ({p['stop_atr']:.1f}×ATR) · هدف۱ {p['tp1']:,.6g} (۱R) · هدف۲ {p['tp2']:,.6g} (R:R {p['rr']:.2f})")
        L.append(f"حجم پیشنهادی: ریسک {p['size']['risk_pct']:.2f}٪ سرمایه = {p['position']['risk_amount']:,.0f}$ → {p['position']['units']:,.4g} واحد (کِلی کامل {p['size']['kelly_full']:.1f}٪، یک‌چهارم {p['size']['kelly_quarter']:.2f}٪) — {p['size']['note_fa']}")
        r = p["regime"]; ks = r["by"].get(r["kind"], {})
        L.append(f"رژیم فعلی: {kind_fa.get(r['kind'], r['kind'])} / {'صعودی' if r['bias'] == 1 else ('نزولی' if r['bias'] == -1 else 'خنثی')} — عملکرد استراتژی در این رژیم: PF {ks.get('pf', float('nan')):.2f}، n={ks.get('n', 0)} ({ {'fits': 'سازگار', 'misfit': 'ناسازگار', 'neutral': 'خنثی', 'unknown': 'نامشخص'}[r['kind_fit']] })")
        h = p["htf"]
        L.append(f"تایم‌فریم بالاتر ({h.get('tf')}): {'هم‌جهت ✓' if h.get('aligned') else ('خلاف ✗' if h.get('aligned') is False else 'بدون روند مشخص')}")
        d = p["decay"]
        L.append(f"فرسایش لبه: PF ۱۲ ماه اخیر {d['pf_recent']:.2f} در برابر کل {d['pf_all']:.2f} → { {'stable': 'پایدار', 'improving': 'رو به بهبود', 'decayed': 'فرسوده', 'unknown': 'نامشخص'}[d['status']] }")
        m = p["mc"]
        if m["n_src"] >= 10:
            L.append(f"شبیه‌سازی ۵۰ معاملهٔ بعدی با ریسک {m['risk_pct']:.2f}٪: احتمال ضرر {m['prob_loss']:.0f}٪ · بازده میانه {m['ret_med']:+.1f}٪ (بدترین ۵٪: {m['ret_p5']:+.1f}٪) · افت سرمایهٔ ۹۵٪: {m['dd_p95']:.1f}٪ · آماده باشید برای {m['streak_p95']} ضرر پیاپی")
        if p["expected_hold"]:
            L.append(f"مدت نگهداری مورد انتظار: ~{p['expected_hold']}")
        if p["avoid_fa"]:
            L.append("⚠ دلایل احتیاط: " + " · ".join(p["avoid_fa"]))
    else:
        L.append(f"**{p['verdict_en']}** — {side} {p['sym']} on {p['tf']} via {p['name_en']} (trust {p['trust']['score']}/100)")
        L.append(f"Entry {p['entry']:,.6g} · Stop {p['stop']:,.6g} ({p['stop_atr']:.1f}×ATR) · TP1 {p['tp1']:,.6g} (1R) · TP2 {p['tp2']:,.6g} (R:R {p['rr']:.2f})")
        L.append(f"Suggested size: risk {p['size']['risk_pct']:.2f}% of equity = ${p['position']['risk_amount']:,.0f} → {p['position']['units']:,.4g} units (full Kelly {p['size']['kelly_full']:.1f}%, ¼ {p['size']['kelly_quarter']:.2f}%) — {p['size']['note_en']}")
        r = p["regime"]; ks = r["by"].get(r["kind"], {})
        L.append(f"Regime now: {r['kind']} / {'bull' if r['bias'] == 1 else ('bear' if r['bias'] == -1 else 'flat')} — strategy in this regime: PF {ks.get('pf', float('nan')):.2f}, n={ks.get('n', 0)} ({r['kind_fit']})")
        h = p["htf"]
        L.append(f"Higher timeframe ({h.get('tf')}): {'aligned ✓' if h.get('aligned') else ('AGAINST ✗' if h.get('aligned') is False else 'no clear trend')}")
        d = p["decay"]
        L.append(f"Edge decay: PF last 12m {d['pf_recent']:.2f} vs overall {d['pf_all']:.2f} → {d['status']}")
        m = p["mc"]
        if m["n_src"] >= 10:
            L.append(f"Monte-Carlo next 50 trades at {m['risk_pct']:.2f}% risk: P(loss) {m['prob_loss']:.0f}% · median {m['ret_med']:+.1f}% (worst 5%: {m['ret_p5']:+.1f}%) · p95 drawdown {m['dd_p95']:.1f}% · be ready for {m['streak_p95']} losses in a row")
        if p["expected_hold"]:
            L.append(f"Expected hold: ~{p['expected_hold']}")
        if p["avoid_en"]:
            L.append("⚠ Caution: " + " · ".join(p["avoid_en"]))
    return "\n".join(L)


# ------------------------------------------------------------------------------------------------- cluster risk
def cluster_risk(signals, tf="1d", max_corr=0.7):
    """Given scanner rows (dicts with sym, side), flag groups of same-direction signals on highly correlated symbols —
    taking all of them is ONE bet, not several. Returns list of dict(symbols, side, avg_corr)."""
    try:
        from core.portfolio import correlation
    except Exception:
        return []
    out = []
    for side in (1, -1):
        syms = sorted({r["sym"] for r in signals if r.get("side") == side})
        if len(syms) < 2:
            continue
        try:
            C = correlation(syms, tf=tf)
        except Exception:
            continue
        seen = set()
        for a in syms:
            if a in seen or a not in C.index:
                continue
            grp = [b for b in syms if b != a and b in C.columns and C.loc[a, b] >= max_corr]
            if grp:
                members = [a] + grp; seen.update(members)
                vals = [C.loc[x, y] for x in members for y in members if x < y]
                out.append(dict(symbols=members, side=side, avg_corr=float(np.mean(vals)) if vals else 1.0))
    return out
