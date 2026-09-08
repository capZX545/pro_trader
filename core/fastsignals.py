"""Fast-signal (scalp) radar — Phase 16.

Scans the top-N crypto pairs on a low timeframe (1m/3m/5m/15m) with the 20 scalp/order-flow strategies + the classic intraday set,
then applies what the research and our own 50 000-bar backtests say is REQUIRED for a low-timeframe edge:
  1. confluence  – ≥ `min_votes` independent methods agree on the same bar window (single methods lose after fees:
                   PF 0.2–0.9 on BTC/ETH/SOL 5m–15m; ≥3 votes + trend filter reaches PF ≈ 1.0–1.8),
  2. trend gate  – EMA50 > EMA200 and EMA200 rising for longs (mirror for shorts),
  3. cost gate   – expected move (target distance) must be ≥ `cost_mult` × round-trip cost, otherwise the setup is
                   mathematically dead regardless of pattern quality,
  4. session     – London/NY overlap gets a bonus; dead Asian hours a penalty,
  5. positioning – funding-rate percentile (OKX/Binance perp) flags crowded sides.
Each result carries a transparent score + the list of agreeing strategies + realistic in-sample WR/PF of the confluence
rule on that symbol so the user sees the (usually thin) edge instead of a bare arrow."""
import time
import numpy as np
import pandas as pd

from core import indicators as ta

FAST_TFS = ["1m", "3m", "5m", "15m"]
SCALP_IDS = ["vwap_pullback_scalp", "vwap_band_fade", "cvd_divergence", "stop_run_scalp", "brooks_h2l2", "micro_squeeze_pop",
             "session_orb", "triple_confirm_scalp", "fast_rsi_div_scalp", "volume_climax_scalp", "funding_crowd_reversal", "ib_extension",
             "value_area_bounce", "triple_a_flow", "stacked_imbalance_retest", "lvn_breakout", "anchored_scalp", "flat_bb_stoch", "nfi_dip_multi", "unfinished_auction", "ichimoku_tk_strong", "ichimoku_kijun_bounce", "ichimoku_mtf"]
INDICATOR_VOTES = ["halftrend_flip", "qqe_cross", "schaff_cycle", "fisher_transform", "vortex_cross", "klinger_cross", "rvol_breakout", "hv_squeeze_breakout",
                   "heikin_ashi_trend", "mass_index_bulge", "coppock_turn", "ultimate_osc", "zigzag_structure", "fib_golden_pocket",
                   "chan_buy1", "gerchik_false_break", "gerchik_paranormal_bar", "lw_setup_92", "stormer_81", "rtm_quasimodo", "rtm_ftr", "sakata_sanpo"]
CLASSIC_INTRADAY = ["orb", "silver_bullet", "liquidity_sweep", "ict_fvg", "bb_squeeze", "vwap", "rsi_div", "engulfing", "pinbar", "supertrend"]
ROUND_TRIP_BPS = {"spot_taker": 24.0, "fut_taker": 13.0, "fut_maker": 5.0}     # commission×2 + spread + slippage


def _classes(ids):
    import strategies as S
    return [(i, S.REGISTRY[i]) for i in ids if i in S.REGISTRY]


def votes_frame(df, ids=None):
    """DataFrame of per-strategy signals (+1/−1/0), one column per strategy id."""
    cols = {}
    for sid, cls in _classes(ids or (SCALP_IDS + CLASSIC_INTRADAY + INDICATOR_VOTES)):
        try:
            cols[sid] = cls().run(df).signal.reindex(df.index).fillna(0).astype(int)
        except Exception:
            continue
    return pd.DataFrame(cols, index=df.index)


def confluence_signal(df, M, min_votes=3, window=3, trend=True):
    """Bar-level confluence: votes counted over the last `window` bars; opposite votes veto."""
    L = (M == 1).rolling(window).sum().sum(axis=1)
    Sh = (M == -1).rolling(window).sum().sum(axis=1)
    if trend:
        e50, e200 = ta.ema(df.close, 50), ta.ema(df.close, 200)
        up = (e50 > e200) & (e200 > e200.shift(20)); dn = (e50 < e200) & (e200 < e200.shift(20))
    else:
        up = dn = pd.Series(True, index=df.index)
    sig = pd.Series(0, index=df.index, dtype=int)
    sig[(L >= min_votes) & (Sh == 0) & up] = 1
    sig[(Sh >= min_votes) & (L == 0) & dn] = -1
    # one entry per cluster
    sig[(sig != 0) & (sig.shift(1) == sig)] = 0
    return sig, L, Sh


def stops_for(df, sig, sl_atr=2.5, floor_bps=40, rr=1.5):
    a = ta.atr(df, 14); c = df.close
    dist = np.maximum(sl_atr * a, floor_bps / 1e4 * c)
    st = pd.Series(np.nan, index=df.index); tp = st.copy()
    st[sig == 1] = (c - dist)[sig == 1]; tp[sig == 1] = (c + rr * dist)[sig == 1]
    st[sig == -1] = (c + dist)[sig == -1]; tp[sig == -1] = (c - rr * dist)[sig == -1]
    return st, tp, dist


def session_factor(ts):
    """London/NY overlap 12–17 UTC best, NY 17–21 & London 7–12 fine, Asia dead zone 21–07 penalised."""
    h = pd.Timestamp(ts).hour
    if 12 <= h < 17:
        return 1.15, "LDN/NY overlap"
    if 7 <= h < 12 or 17 <= h < 21:
        return 1.0, "London" if h < 12 else "New York"
    return 0.8, "Asia / thin"


def evaluate_symbol(sym, df, min_votes=3, fee_tier="fut_taker", cost_mult=3.0, rr=1.5, lookback_bars=3, funding=None):
    """Return a dict for the most recent confluence setup (or None) plus in-sample stats of the rule on this symbol."""
    if df is None or len(df) < 400:
        return None
    df = df.copy(); df.attrs.update(symbol=sym)
    M = votes_frame(df)
    if M.empty:
        return None
    sig, L, Sh = confluence_signal(df, M, min_votes=min_votes)
    st, tp, dist = stops_for(df, sig, rr=rr)
    # in-sample honesty check of THIS rule on THIS symbol (realistic taker costs)
    stats = None
    try:
        from core.backtest import run_backtest
        from strategies.base import StrategyResult
        bps = ROUND_TRIP_BPS[fee_tier]
        bt = run_backtest(df, StrategyResult(sig, st, tp), max_bars=60, commission_bps=bps / 2 * 0.8, slippage_bps=bps / 2 * 0.2, cost_model="static")
        stats = bt.stats
    except Exception:
        pass
    recent = np.where(sig.values[-lookback_bars:] != 0)[0]
    if len(recent) == 0:
        return dict(sym=sym, setup=None, stats=stats)
    i = len(df) - lookback_bars + recent[-1]
    side = int(sig.iloc[i]); px = float(df.close.iloc[i]); last = float(df.close.iloc[-1])
    agree = [c for c in M.columns if (M[c].iloc[max(0, i - 2):i + 1] == side).any()]
    cost_bps = ROUND_TRIP_BPS[fee_tier]
    move_bps = float(abs(tp.iloc[i] - px) / px * 1e4)
    cost_ok = move_bps >= cost_mult * cost_bps
    sf, sess = session_factor(df.index[i])
    fund_note, fund_pen = "", 1.0
    if funding:
        pct = funding.get("funding_percentile")
        if pct is not None:
            if side == 1 and pct >= 85:
                fund_note, fund_pen = "longs crowded (funding p%d)" % pct, 0.85
            elif side == -1 and pct <= 15:
                fund_note, fund_pen = "shorts crowded (funding p%d)" % pct, 0.85
            elif (side == 1 and pct <= 15) or (side == -1 and pct >= 85):
                fund_note, fund_pen = "squeeze fuel on our side", 1.1
    votes = int(L.iloc[i] if side == 1 else Sh.iloc[i])
    pf = (stats or {}).get("profit_factor", 0) or 0
    n = (stats or {}).get("trades", 0) or 0
    edge = min(max(pf - 0.8, 0), 1.2) / 1.2                                  # 0 at PF 0.8, 1 at PF 2.0
    score = 100 * min(1.0, (0.45 * min(votes, 6) / 6 + 0.35 * edge + 0.2 * (1 if cost_ok else 0)) * sf * fund_pen)
    return dict(sym=sym, setup=dict(side=side, ts=df.index[i], px=px, last=last, sl=float(st.iloc[i]), tp=float(tp.iloc[i]),
                                    rr=rr, votes=votes, agree=agree, move_bps=move_bps, cost_bps=cost_bps, cost_ok=cost_ok,
                                    session=sess, funding_note=fund_note, score=round(score), ago=len(df) - 1 - i),
                stats=stats)


def scan(tf="5m", top_n=40, min_votes=3, fee_tier="fut_taker", bars=3000, progress=None, symbols=None, stop=None):
    """Full radar pass. Returns list of result dicts sorted by score (setups first)."""
    from core.data import get_ohlcv
    from core import derivs
    from core.live import binance_usdt_universe, pretty
    if symbols is None:
        try:
            uni = binance_usdt_universe()
            symbols = [pretty(r[0]) for r in uni[:top_n]]
        except Exception:
            symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "LTC/USDT"][:top_n]
    out = []
    t0 = time.time()
    for k, sym in enumerate(symbols):
        if stop is not None and stop():
            break
        if progress:
            progress(int(100 * k / max(1, len(symbols))), f"{sym} · {tf}")
        try:
            df = get_ohlcv(sym, tf, max_age_sec=60)
            if df is None or len(df) < 400:
                continue
            df = df.tail(bars)
            fund = derivs.positioning_summary(sym) if k < 12 else None     # rate-limit friendly: majors only
            derivs.attach(df, sym)
            mv = min_votes
            try:                                                   # per-symbol walk-forward knobs (core/scalp_wfo), if tuned
                from core.scalp_wfo import params_for
                wp, verdict = params_for(sym, tf, fee_tier)
                if wp and verdict in ("edge", "weak"):
                    mv = max(min_votes, int(wp["min_votes"]))
            except Exception:
                wp, verdict = None, None
            r = evaluate_symbol(sym, df, min_votes=mv, fee_tier=fee_tier, funding=fund)
            if r:
                r["tf"] = tf; r["funding"] = fund or {}; r["wfo"] = verdict
                out.append(r)
        except Exception as e:
            out.append(dict(sym=sym, tf=tf, setup=None, stats=None, error=str(e)[:80]))
    out.sort(key=lambda r: (-(r.get("setup") or {}).get("score", -1), r["sym"]))
    if progress:
        progress(100, f"done · {len(out)} symbols · {time.time() - t0:.0f}s")
    return out


def explain(r, lang="en"):
    """One-paragraph honest explanation for a result row."""
    s = r.get("setup"); st = r.get("stats") or {}
    if not s:
        return ("No confluence setup in the last bars." if lang == "en" else "در کندل‌های اخیر ستاپ هم‌گرایی وجود ندارد.")
    side = ("LONG" if s["side"] == 1 else "SHORT") if lang == "en" else ("خرید" if s["side"] == 1 else "فروش")
    if lang == "en":
        txt = (f"{side} {r['sym']} {r['tf']} — {s['votes']} methods agree ({', '.join(s['agree'][:6])}). Entry {s['px']:,.6g}, "
               f"stop {s['sl']:,.6g}, target {s['tp']:,.6g} (R:R 1:{s['rr']}). Expected move {s['move_bps']:.0f} bps vs round-trip cost "
               f"{s['cost_bps']:.0f} bps → {'cost OK' if s['cost_ok'] else 'TOO SMALL for fees'}. Session: {s['session']}. ")
        if s["funding_note"]:
            txt += f"Positioning: {s['funding_note']}. "
        if st.get("trades"):
            txt += (f"This confluence rule on this symbol (in-sample, realistic costs): {st['trades']} trades, WR {st['win_rate']:.0f} %, "
                    f"PF {st['profit_factor']:.2f}. ")
        txt += "Low-timeframe edges are thin: paper-trade first, risk ≤ 0.5 % and never trade without the stop."
    else:
        txt = (f"{side} {r['sym']} {r['tf']} — {s['votes']} روش هم‌نظرند ({', '.join(s['agree'][:6])}). ورود {s['px']:,.6g}، "
               f"حد ضرر {s['sl']:,.6g}، هدف {s['tp']:,.6g} (R:R ۱:{s['rr']}). حرکت مورد انتظار {s['move_bps']:.0f} bps در برابر هزینهٔ رفت‌وبرگشت "
               f"{s['cost_bps']:.0f} bps → {'از نظر کارمزد قابل قبول' if s['cost_ok'] else 'برای کارمزد خیلی کوچک است'}. سشن: {s['session']}. ")
        if s["funding_note"]:
            txt += f"پوزیشن‌گیری: {s['funding_note']}. "
        if st.get("trades"):
            txt += (f"همین قانون هم‌گرایی روی همین نماد (درون‌نمونه، با هزینهٔ واقعی): {st['trades']} معامله، وین‌ریت {st['win_rate']:.0f}٪، "
                    f"PF {st['profit_factor']:.2f}. ")
        txt += "لبهٔ تایم پایین نازک است: اول کاغذی معامله کن، ریسک ≤ ۰.۵٪ و هرگز بدون حد ضرر وارد نشو."
    return txt
