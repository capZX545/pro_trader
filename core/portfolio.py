"""
Portfolio layer — answers "5 signals came at once, which do I take and how big?"

• correlation(symbols, tf): rolling 90-bar return correlation matrix (cached data).
• allocate(signals, equity, risk_pct, max_total_risk, max_corr): greedy selection by confidence with
  correlation clustering — two long signals on BTC and ETH (ρ≈0.85) are ONE bet, so the second gets
  its risk cut (or is skipped) and the total open risk never exceeds `max_total_risk` % of equity.
• kelly_fraction(wr, payoff): the Kelly optimum and the quarter-Kelly we actually recommend.
"""
import numpy as np
import pandas as pd
from core.data import get_ohlcv


def correlation(symbols, tf="1d", window=90):
    rets = {}
    for s in symbols:
        try:
            df = get_ohlcv(s, tf)
            r = df.close.pct_change().tail(window)
            r.index = r.index.tz_localize(None) if r.index.tz is not None else r.index
            rets[s] = r
        except Exception:
            continue
    if len(rets) < 2:
        return pd.DataFrame(np.eye(len(rets)), index=list(rets), columns=list(rets))
    m = pd.DataFrame(rets).dropna(how="all").ffill()
    return m.corr().fillna(0.0)


def kelly_fraction(wr, payoff):
    """wr in 0..1, payoff = avg win / avg loss. Returns (full_kelly, quarter_kelly) as fraction of equity."""
    if payoff <= 0:
        return 0.0, 0.0
    k = wr - (1 - wr) / payoff
    k = max(0.0, k)
    return float(k), float(k / 4)


def allocate(signals, equity=10_000.0, risk_pct=0.5, max_total_risk=2.0, max_corr=0.7, tf="1d"):
    """
    signals: list of dict(symbol, side, entry, stop, conf, [wr, payoff])
    Returns list of dict(signal, take: bool, risk_pct, size_units, notional, reason, cluster)
    """
    if not signals:
        return []
    syms = sorted({s["symbol"] for s in signals})
    corr = correlation(syms, tf)
    ranked = sorted(signals, key=lambda s: -(s.get("conf") or 0))
    taken = []
    used_risk = 0.0
    out = []
    for s in ranked:
        rp = risk_pct
        # cap by quarter-Kelly if strategy stats are known
        if s.get("wr") and s.get("payoff"):
            _, qk = kelly_fraction(s["wr"] / 100 if s["wr"] > 1 else s["wr"], s["payoff"])
            if qk > 0:
                rp = min(rp, qk * 100)
        reason, cluster = "ok", None
        for tk in taken:
            try:
                rho = float(corr.loc[s["symbol"], tk["symbol"]])
            except Exception:
                rho = 0.0
            same_dir = np.sign(s["side"]) == np.sign(tk["side"])
            if abs(rho) >= max_corr and (same_dir if rho > 0 else not same_dir):
                cluster = tk["symbol"]
                rp *= 0.5
                reason = f"correlated with {tk['symbol']} (ρ={rho:.2f}) → half risk"
                break
        if used_risk + rp > max_total_risk + 1e-9:
            out.append(dict(signal=s, take=False, risk_pct=0.0, size_units=0.0, notional=0.0,
                            reason=f"total open risk would exceed {max_total_risk}%", cluster=cluster))
            continue
        rpu = abs(s["entry"] - s["stop"])
        if rpu <= 0:
            out.append(dict(signal=s, take=False, risk_pct=0.0, size_units=0.0, notional=0.0, reason="invalid stop", cluster=cluster))
            continue
        units = equity * rp / 100 / rpu
        out.append(dict(signal=s, take=True, risk_pct=round(rp, 3), size_units=units, notional=units * s["entry"],
                        reason=reason, cluster=cluster))
        taken.append(s)
        used_risk += rp
    return out


# ------------------------------------------------------------------ Phase 12: proven-only portfolio
def build_proven_portfolio(tf="4h", max_n=6, max_corr=0.6, equity=10_000.0, risk_per_trade=1.0, progress=None):
    """Select proven (tf, group, strategy) combos with LOW pairwise correlation of their OOS equity curves, size each with
    EQUAL RISK (1/N of a total risk budget) and report the combined curve. This is the 'what should I actually run'
    answer: unproven strategies never enter; two strategies that win/lose together count as one."""
    from core import playbook as PB
    from core.backtest import run_backtest
    import strategies as S
    rows = [r for r in PB.proven_table() if r[0] == tf]
    if not rows:
        return dict(rows=[], curves=None, corr=None, stats={}, note="no proven strategies on this timeframe")
    curves = {}
    meta = {}
    for k, (tf_, g, sid, sc, st) in enumerate(rows[:max_n * 3]):
        if progress:
            progress(int(k / min(len(rows), max_n * 3) * 80), f"{sid} {g}")
        syms = PB.GROUPS[g][:6]
        parts = []
        for sym in syms:
            try:
                df = get_ohlcv(sym, tf, max_age_sec=6 * 3600).tail(PB.MAX_BARS.get(tf, 20000))
                n = len(df); a = int(n * 0.4)
                res = S.get(sid).run(df)
                res.signal.iloc[:a] = 0
                bt = run_backtest(df, res, symbol=sym, risk_pct=risk_per_trade)
                eq = bt.equity.iloc[a:] / bt.equity.iloc[a] - 1
                parts.append(eq.resample("1D").last().ffill())
            except Exception:
                continue
        if not parts:
            continue
        m = pd.concat(parts, axis=1).ffill().fillna(0.0)
        curve = m.mean(axis=1)
        curves[f"{sid}@{g}"] = curve
        meta[f"{sid}@{g}"] = dict(tf=tf, group=g, sid=sid, score=sc, stats=st)
    if not curves:
        return dict(rows=[], curves=None, corr=None, stats={}, note="no data")
    M = pd.concat(curves, axis=1).ffill().fillna(0.0)
    R = M.diff().fillna(0.0)
    corr = R.corr().fillna(0.0)
    # greedy low-correlation selection by score
    order = sorted(curves, key=lambda k: -meta[k]["score"])
    chosen = []
    for k in order:
        if all(abs(corr.loc[k, c]) < max_corr for c in chosen):
            chosen.append(k)
        if len(chosen) >= max_n:
            break
    w = 1.0 / len(chosen)
    combo = (R[chosen] * w).sum(axis=1).cumsum()
    dd = (combo - combo.cummax()).min()
    daily = (R[chosen] * w).sum(axis=1)
    sharpe = float(daily.mean() / daily.std() * np.sqrt(365)) if daily.std() > 0 else 0.0
    yrs = max((combo.index[-1] - combo.index[0]).days / 365.25, 0.1)
    stats = dict(n=len(chosen), total_return_pct=float(combo.iloc[-1] * 100), cagr_pct=float(((1 + combo.iloc[-1]) ** (1 / yrs) - 1) * 100),
                 max_dd_pct=float(-dd * 100), sharpe=sharpe, years=round(yrs, 1), risk_each_pct=round(risk_per_trade * w, 3))
    out_rows = [dict(key=k, **meta[k], weight=w, corr_max=float(max([abs(corr.loc[k, c]) for c in chosen if c != k] or [0.0]))) for k in chosen]
    return dict(rows=out_rows, curves=M[chosen], combo=combo, corr=corr.loc[chosen, chosen], stats=stats, note="")
