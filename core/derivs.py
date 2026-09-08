"""Perpetual-futures positioning data (funding rate, open interest) — Phase 16.
Public endpoints, no key. OKX is primary (reachable worldwide incl. where Binance futures is geo-blocked);
Binance USDⓈ-M is tried second. Results are cached on disk for 30 min. Everything is best-effort: callers get an
empty Series on failure and strategies fall back to price-only proxies."""
import json, os, time
import pandas as pd, requests
from core.paths import data as _data

_S = requests.Session(); _S.headers["User-Agent"] = "ProTrader/1.3"
_TO = 8
_CACHE_DIR = _data("cache_derivs")


def _cache_path(kind, base):
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return os.path.join(_CACHE_DIR, f"{kind}_{base}.json")


def _cached(kind, base, max_age=1800):
    p = _cache_path(kind, base)
    try:
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < max_age:
            return json.load(open(p))
    except Exception:
        pass
    return None


def _store(kind, base, rows):
    try:
        json.dump(rows, open(_cache_path(kind, base), "w"))
    except Exception:
        pass


def funding_history(base="BTC", limit=300) -> pd.Series:
    """Series indexed by funding time (UTC, naive) → rate per 8h (e.g. 0.0001 = 0.01 %)."""
    base = base.upper().replace("/USDT", "")
    rows = _cached("funding", base)
    if rows is None:
        rows = []
        try:  # OKX: newest first, 100 per page
            after = None
            for _ in range(max(1, min(5, limit // 100))):
                prm = {"instId": f"{base}-USDT-SWAP", "limit": 100}
                if after:
                    prm["after"] = after
                j = _S.get("https://www.okx.com/api/v5/public/funding-rate-history", params=prm, timeout=_TO).json()
                d = j.get("data", [])
                if not d:
                    break
                rows += [(int(x["fundingTime"]), float(x["realizedRate"] if x.get("realizedRate") else x["fundingRate"])) for x in d]
                after = d[-1]["fundingTime"]
        except Exception:
            rows = []
        if not rows:
            try:
                j = _S.get("https://fapi.binance.com/fapi/v1/fundingRate", params={"symbol": f"{base}USDT", "limit": min(1000, limit)}, timeout=_TO).json()
                rows = [(int(x["fundingTime"]), float(x["fundingRate"])) for x in j]
            except Exception:
                rows = []
        if rows:
            _store("funding", base, rows)
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series({pd.to_datetime(t, unit="ms"): r for t, r in rows}).sort_index()
    return s[~s.index.duplicated(keep="last")]


def funding_now(base="BTC") -> dict:
    base = base.upper().replace("/USDT", "")
    try:
        j = _S.get("https://www.okx.com/api/v5/public/funding-rate", params={"instId": f"{base}-USDT-SWAP"}, timeout=_TO).json()
        d = j["data"][0]
        return dict(rate=float(d["fundingRate"]), next_rate=float(d.get("nextFundingRate") or 0), ts=int(d["fundingTime"]), venue="okx")
    except Exception:
        pass
    try:
        j = _S.get("https://fapi.binance.com/fapi/v1/premiumIndex", params={"symbol": f"{base}USDT"}, timeout=_TO).json()
        return dict(rate=float(j["lastFundingRate"]), next_rate=0.0, ts=int(j["nextFundingTime"]), venue="binance")
    except Exception:
        return {}


def open_interest_history(base="BTC", period="5m", limit=288) -> pd.Series:
    """OI in contracts/USD (venue-native) indexed by time. OKX 'open-interest-history' (rubik) then Binance."""
    base = base.upper().replace("/USDT", "")
    key = f"oi_{period}"
    rows = _cached(key, base, 600)
    if rows is None:
        rows = []
        try:
            j = _S.get("https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-history",
                       params={"instId": f"{base}-USDT-SWAP", "period": period, "limit": min(limit, 1440)}, timeout=_TO).json()
            rows = [(int(x[0]), float(x[1])) for x in j.get("data", [])]
        except Exception:
            rows = []
        if not rows:
            try:
                j = _S.get("https://fapi.binance.com/futures/data/openInterestHist",
                           params={"symbol": f"{base}USDT", "period": period, "limit": min(limit, 500)}, timeout=_TO).json()
                rows = [(int(x["timestamp"]), float(x["sumOpenInterest"])) for x in j]
            except Exception:
                rows = []
        if rows:
            _store(key, base, rows)
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series({pd.to_datetime(t, unit="ms"): v for t, v in rows}).sort_index()
    return s[~s.index.duplicated(keep="last")]


def long_short_ratio(base="BTC", period="5m", limit=288) -> pd.Series:
    base = base.upper().replace("/USDT", "")
    try:
        j = _S.get("https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio",
                   params={"ccy": base, "period": period}, timeout=_TO).json()
        rows = [(int(x[0]), float(x[1])) for x in j.get("data", [])][:limit]
        s = pd.Series({pd.to_datetime(t, unit="ms"): v for t, v in rows}).sort_index()
        return s
    except Exception:
        return pd.Series(dtype=float)


class _Held:
    """Opaque holder: pandas compares df.attrs with == during concat, so a bare Series in attrs breaks every indicator.
    Wrapping it in an object with identity-equality keeps attrs comparable."""
    __slots__ = ("s",)

    def __init__(self, s):
        self.s = s

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)


def get_series(df, key):
    """Series stored via attach() or None."""
    h = df.attrs.get(key)
    return h.s if isinstance(h, _Held) else (h if isinstance(h, pd.Series) else None)


def attach(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Attach funding (and OI if available) to df.attrs for strategies that use them. Silent on failure."""
    try:
        if not str(symbol).upper().endswith("/USDT"):
            return df
        base = symbol.split("/")[0]
        f = funding_history(base)
        if len(f):
            df.attrs["funding"] = _Held(f)
        oi = open_interest_history(base)
        if len(oi):
            df.attrs["oi"] = _Held(oi)
    except Exception:
        pass
    return df


def positioning_summary(symbol: str) -> dict:
    """Human-readable read for the Advisor / Live pages."""
    out = {}
    try:
        base = symbol.split("/")[0]
        fn = funding_now(base)
        fh = funding_history(base)
        oi = open_interest_history(base)
        if fn:
            r = fn["rate"]
            out["funding"] = r
            out["funding_pct_8h"] = r * 100
            out["funding_annual_pct"] = r * 3 * 365 * 100
            if len(fh) >= 30:
                pct = float((fh < r).mean() * 100)
                out["funding_percentile"] = pct
                out["crowd"] = "longs crowded" if pct >= 85 else ("shorts crowded" if pct <= 15 else "balanced")
        if len(oi) >= 12:
            out["oi_change_1h_pct"] = float((oi.iloc[-1] / oi.iloc[-13] - 1) * 100) if len(oi) > 13 else 0.0
            out["oi_change_24h_pct"] = float((oi.iloc[-1] / oi.iloc[0] - 1) * 100)
    except Exception:
        pass
    return out
