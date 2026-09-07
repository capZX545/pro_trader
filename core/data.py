"""
Data layer: unified OHLCV fetching for crypto / forex / stocks / commodities.
Primary source: Binance public API for crypto (no key needed).
Fallback + everything else: Yahoo Finance via yfinance.
Local CSV cache in ./data/
"""
import os
import time
import json
import hashlib
import numpy as np
import pandas as pd
import requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(CACHE_DIR, exist_ok=True)

# ---- Universe (symbol -> yahoo ticker, binance symbol or None) ----
UNIVERSE = {
    "Crypto": {
        "BTC/USDT": ("BTC-USD", "BTCUSDT"),
        "ETH/USDT": ("ETH-USD", "ETHUSDT"),
        "SOL/USDT": ("SOL-USD", "SOLUSDT"),
        "BNB/USDT": ("BNB-USD", "BNBUSDT"),
        "XRP/USDT": ("XRP-USD", "XRPUSDT"),
        "ADA/USDT": ("ADA-USD", "ADAUSDT"),
        "DOGE/USDT": ("DOGE-USD", "DOGEUSDT"),
        "AVAX/USDT": ("AVAX-USD", "AVAXUSDT"),
        "LINK/USDT": ("LINK-USD", "LINKUSDT"),
        "DOT/USDT": ("DOT-USD", "DOTUSDT"),
        "TON/USDT": ("TON11419-USD", "TONUSDT"),
        "LTC/USDT": ("LTC-USD", "LTCUSDT"),
    },
    "Forex": {
        "EUR/USD": ("EURUSD=X", None),
        "GBP/USD": ("GBPUSD=X", None),
        "USD/JPY": ("USDJPY=X", None),
        "USD/CHF": ("USDCHF=X", None),
        "AUD/USD": ("AUDUSD=X", None),
        "USD/CAD": ("USDCAD=X", None),
        "NZD/USD": ("NZDUSD=X", None),
        "EUR/GBP": ("EURGBP=X", None),
        "EUR/JPY": ("EURJPY=X", None),
        "GBP/JPY": ("GBPJPY=X", None),
        "DXY": ("DX-Y.NYB", None),
    },
    "Commodities": {
        "Gold (XAU/USD)": ("GC=F", None),
        "Silver (XAG/USD)": ("SI=F", None),
        "Crude Oil (WTI)": ("CL=F", None),
        "Brent Oil": ("BZ=F", None),
        "Natural Gas": ("NG=F", None),
        "Copper": ("HG=F", None),
    },
    "Indices": {
        "S&P 500": ("^GSPC", None),
        "Nasdaq 100": ("^NDX", None),
        "Dow Jones": ("^DJI", None),
        "DAX": ("^GDAXI", None),
        "FTSE 100": ("^FTSE", None),
        "Nikkei 225": ("^N225", None),
        "VIX": ("^VIX", None),
    },
    "Stocks": {
        "Apple (AAPL)": ("AAPL", None),
        "Microsoft (MSFT)": ("MSFT", None),
        "NVIDIA (NVDA)": ("NVDA", None),
        "Tesla (TSLA)": ("TSLA", None),
        "Amazon (AMZN)": ("AMZN", None),
        "Google (GOOGL)": ("GOOGL", None),
        "Meta (META)": ("META", None),
        "AMD": ("AMD", None),
        "Coinbase (COIN)": ("COIN", None),
        "MicroStrategy (MSTR)": ("MSTR", None),
    },
}

TIMEFRAMES = ["5m", "15m", "30m", "1h", "4h", "1d", "1wk"]
# bars of history to request from Binance per timeframe (≈ 70d / 100d / 120d / 1y / 2.7y / 4y)
_BINANCE_LIMIT = {"1m": 5000, "5m": 20000, "15m": 10000, "30m": 6000, "1h": 9000, "4h": 6000, "1d": 1500, "1wk": 600}

# how much history to request per timeframe
_PERIOD = {"1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d", "1h": "730d", "4h": "730d", "1d": "10y", "1wk": "max"}
_BINANCE_TF = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1d", "1wk": "1w"}


def resolve(symbol_name: str):
    for cat, d in UNIVERSE.items():
        if symbol_name in d:
            return cat, d[symbol_name]
    # any "XXX/USDT" → Binance symbol (whole-market support); otherwise free-text yahoo ticker
    if symbol_name.upper().endswith("/USDT"):
        base = symbol_name.upper().split("/")[0]
        return "Crypto", (f"{base}-USD", f"{base}USDT")
    return "Custom", (symbol_name, None)


def _read_cache(path):
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.read_pickle(path)


def _write_cache(df, path):
    try:
        _write_cache(df, path)
    except Exception:
        df.to_pickle(path)   # pyarrow/fastparquet not installed → pickle fallback (same filename)


def _cache_path(key: str):
    return os.path.join(CACHE_DIR, hashlib.md5(key.encode()).hexdigest()[:16] + ".parquet")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [str(c).lower() for c in df.columns]
    keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep].astype(float)
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = df[~df.index.duplicated(keep="last")].dropna(subset=["close"])
    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)
    df.index.name = "time"
    return df


BINANCE_HOSTS = ["https://api.binance.com", "https://data-api.binance.vision"]


def _fetch_binance(bsym: str, tf: str, limit: int = 1500) -> pd.DataFrame:
    last_err = None
    for host in BINANCE_HOSTS:
        try:
            return _fetch_binance_host(host, bsym, tf, limit)
        except Exception as e:
            last_err = e
    raise last_err


def _fetch_binance_host(host: str, bsym: str, tf: str, limit: int = 1500) -> pd.DataFrame:
    url = f"{host}/api/v3/klines"
    frames = []
    end = None
    remaining = limit
    while remaining > 0:
        params = {"symbol": bsym, "interval": _BINANCE_TF[tf], "limit": min(1000, remaining)}
        if end:
            params["endTime"] = end
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        frames.append(rows)
        end = rows[0][0] - 1
        remaining -= len(rows)
        if len(rows) < params["limit"]:
            break
    rows = [x for f in reversed(frames) for x in f]
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "volume", "ct", "qv", "n", "tb", "tq", "i"])
    df["time"] = pd.to_datetime(df["t"], unit="ms")
    df = df.set_index("time")[["open", "high", "low", "close", "volume"]].astype(float)
    return _normalize(df)


def _fetch_yahoo(ticker: str, tf: str) -> pd.DataFrame:
    import yfinance as yf
    interval = tf
    period = _PERIOD.get(tf, "2y")
    if tf == "4h":  # yahoo has no 4h -> build from 1h
        raw = yf.download(ticker, period="730d", interval="1h", progress=False, auto_adjust=True, threads=False)
        raw = _normalize(raw)
        return resample(raw, "4h")
    raw = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True, threads=False)
    if raw is None or raw.empty:
        raise RuntimeError(f"No data for {ticker}")
    return _normalize(raw)


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    r = {"1h": "1h", "4h": "4h", "1d": "1D", "1wk": "1W"}.get(rule, rule)
    o = df.resample(r, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(subset=["open"])
    return o


def get_ohlcv(symbol_name: str, tf: str = "1h", use_cache: bool = True, max_age_sec: int = 300) -> pd.DataFrame:
    cat, (yt, bs) = resolve(symbol_name)
    key = f"{symbol_name}|{tf}"
    path = _cache_path(key)
    if use_cache and os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_sec:
        try:
            df = _read_cache(path)
            df.attrs.update(symbol=symbol_name, tf=tf)
            return df
        except Exception:
            pass
    df = None
    errors = []
    if bs:
        try:
            df = _fetch_binance(bs, tf, _BINANCE_LIMIT.get(tf, 1500))
        except Exception as e:
            errors.append(f"binance: {e}")
    if df is None or df.empty:
        try:
            df = _fetch_yahoo(yt, tf)
        except Exception as e:
            errors.append(f"yahoo: {e}")
    if df is None or df.empty:
        # last resort: stale cache
        if os.path.exists(path):
            return _read_cache(path)
        raise RuntimeError("; ".join(errors) or "no data")
    try:
        _write_cache(df, path)
    except Exception:
        pass
    df.attrs.update(symbol=symbol_name, tf=tf)
    return df


def generate_synthetic(n: int = 1500, seed: int = 42, start_price: float = 100.0) -> pd.DataFrame:
    """Offline fallback: realistic-ish random walk with regimes, for demo/tests."""
    rng = np.random.default_rng(seed)
    regime = np.cumsum(rng.normal(0, 0.0004, n))
    rets = rng.normal(0, 0.008, n) + regime * 0.02
    close = start_price * np.exp(np.cumsum(rets))
    open_ = np.roll(close, 1)
    open_[0] = start_price
    spread = np.abs(rng.normal(0, 0.005, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    vol = rng.lognormal(10, 0.5, n) * (1 + np.abs(rets) * 30)
    idx = pd.date_range(end=pd.Timestamp.utcnow().tz_localize(None), periods=n, freq="1h")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)
