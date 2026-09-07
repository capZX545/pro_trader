"""
Freqtrade-style Pairlist filters (docs: freqtrade.io/en/stable/plugins/#pairlists-and-pairlist-handlers)
adapted to OHLCV data for the Scanner: filter the symbol universe BEFORE running strategies.

  VolumePairList        – rank by quote volume (close*volume) over lookback, keep top N
  AgeFilter             – at least min_candles of history
  VolatilityFilter      – annualised std of log returns over lookback within [min, max]
  RangeStabilityFilter  – (high-low)/low over lookback ≥ min_rate_of_change (avoid dead/flat pairs)
  SpreadFilter          – proxy: median (high-low)/close of last candles ≤ max_spread_ratio*k (no L2 book offline)
  PriceFilter           – low_price_ratio: 1 tick relative to price ≤ ratio (uses min price increment estimate)
  PerformanceFilter     – uses playbook/journal performance: drop symbols with negative expectancy (optional)
"""
import math
import numpy as np


def _log_ret(close):
    c = np.asarray(close, dtype=float)
    c = c[c > 0]
    if len(c) < 3:
        return np.array([])
    return np.diff(np.log(c))


def quote_volume(df, lookback=96):
    d = df.tail(lookback)
    return float((d["close"] * d["volume"]).sum())


def volatility(df, lookback=96, periods_per_year=365 * 24):
    r = _log_ret(df["close"].tail(lookback + 1))
    if len(r) < 5:
        return 0.0
    return float(r.std(ddof=1) * math.sqrt(periods_per_year))


def rate_of_change(df, lookback=96):
    d = df.tail(lookback)
    lo = float(d["low"].min())
    hi = float(d["high"].max())
    return (hi - lo) / lo if lo > 0 else 0.0


def spread_proxy(df, n=30):
    d = df.tail(n)
    s = ((d["high"] - d["low"]) / d["close"]).median()
    return float(s) if np.isfinite(s) else 1.0


def tick_ratio(df):
    """estimate price increment from the smallest non-zero decimal step in recent closes"""
    c = df["close"].tail(200).values
    diffs = np.abs(np.diff(c))
    diffs = diffs[diffs > 0]
    if len(diffs) == 0:
        return 0.0
    return float(diffs.min() / c[-1])


DEFAULT_PAIRLIST = [
    dict(method="AgeFilter", min_candles=300),
    dict(method="VolatilityFilter", lookback=96, min_volatility=0.05, max_volatility=3.0),
    dict(method="RangeStabilityFilter", lookback=96, min_rate_of_change=0.01),
    dict(method="SpreadFilter", max_spread_ratio=0.02),
    dict(method="PriceFilter", low_price_ratio=0.01),
]


def apply_pairlist(datasets, config=None, periods_per_year=365 * 24, top_n=None):
    """
    datasets: dict symbol -> DataFrame(open,high,low,close,volume)
    returns (kept: list[symbol], report: dict symbol -> {"kept": bool, "reason": str, metrics...})
    """
    config = config or DEFAULT_PAIRLIST
    report = {}
    kept = []
    for sym, df in datasets.items():
        if df is None or len(df) == 0:
            report[sym] = dict(kept=False, reason="no data")
            continue
        vol = volatility(df, periods_per_year=periods_per_year)
        roc = rate_of_change(df)
        spr = spread_proxy(df)
        qv = quote_volume(df)
        tr = tick_ratio(df)
        m = dict(volatility=vol, roc=roc, spread=spr, quote_volume=qv, tick_ratio=tr, candles=len(df))
        reason = ""
        for f in config:
            k = f["method"]
            if k == "AgeFilter" and len(df) < f.get("min_candles", 300):
                reason = f"AgeFilter ({len(df)} < {f.get('min_candles', 300)})"
            elif k == "VolatilityFilter":
                if vol < f.get("min_volatility", 0) or vol > f.get("max_volatility", 99):
                    reason = f"VolatilityFilter ({vol:.2f})"
            elif k == "RangeStabilityFilter" and roc < f.get("min_rate_of_change", 0.01):
                reason = f"RangeStabilityFilter ({roc * 100:.2f}%)"
            elif k == "SpreadFilter" and spr > f.get("max_spread_ratio", 0.02):
                reason = f"SpreadFilter ({spr * 100:.2f}%)"
            elif k == "PriceFilter" and tr > f.get("low_price_ratio", 0.01):
                reason = f"PriceFilter (tick {tr * 100:.2f}%)"
            if reason:
                break
        m["kept"] = not reason
        m["reason"] = reason or "ok"
        report[sym] = m
        if not reason:
            kept.append(sym)
    # VolumePairList ranking — within each asset class (quote volumes are not comparable across classes)
    kept.sort(key=lambda s: -report[s]["quote_volume"])
    if top_n:
        from collections import defaultdict
        groups = defaultdict(list)
        for s in kept:
            groups[_asset_class(s)].append(s)
        out = []
        for g, lst in groups.items():
            for s in lst[top_n:]:
                report[s]["kept"] = False
                report[s]["reason"] = "VolumePairList (rank)"
            out += lst[:top_n]
        kept = out
    return kept, report


def _asset_class(sym):
    try:
        from core.costs import asset_class
        return asset_class(sym)
    except Exception:
        return "crypto" if "/USDT" in sym else ("forex" if "/" in sym and len(sym) == 7 else "other")
