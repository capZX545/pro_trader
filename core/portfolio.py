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
