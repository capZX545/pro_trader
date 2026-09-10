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

from core.paths import DATA_DIR as CACHE_DIR
os.makedirs(CACHE_DIR, exist_ok=True)

# --- Resilient network layer (anti-filter) ---
try:
    from core.resilient import session as resilient_session, detect_system_proxy, health_check as resilient_health
    _RESILIENT_AVAILABLE = True
    # Patch requests Session globally to use resilient
    _RESILIENT_SESSION = resilient_session()
except Exception as _e:
    print(f"[data] resilient layer not available: {_e}")
    _RESILIENT_AVAILABLE = False
    _RESILIENT_SESSION = requests.Session()
    _RESILIENT_SESSION.headers["User-Agent"] = "ProTrader/2.0"

# --- Iran Gold integration ---
try:
    from core import iran_gold as _IRAN_GOLD
    _IRAN_GOLD_AVAILABLE = True
except Exception as _e:
    print(f"[data] iran_gold not available: {_e}")
    _IRAN_GOLD_AVAILABLE = False
    _IRAN_GOLD = None


# ---- Universe (symbol -> yahoo ticker, binance symbol or None) ----
UNIVERSE = {
    "Crypto": {
        "BTC/USDT": ("BTC-USD", "BTCUSDT"), "ETH/USDT": ("ETH-USD", "ETHUSDT"), "SOL/USDT": ("SOL-USD", "SOLUSDT"),
        "BNB/USDT": ("BNB-USD", "BNBUSDT"), "XRP/USDT": ("XRP-USD", "XRPUSDT"), "ADA/USDT": ("ADA-USD", "ADAUSDT"),
        "DOGE/USDT": ("DOGE-USD", "DOGEUSDT"), "AVAX/USDT": ("AVAX-USD", "AVAXUSDT"), "LINK/USDT": ("LINK-USD", "LINKUSDT"),
        "DOT/USDT": ("DOT-USD", "DOTUSDT"), "TON/USDT": ("TON11419-USD", "TONUSDT"), "LTC/USDT": ("LTC-USD", "LTCUSDT"),
        "TRX/USDT": ("TRX-USD", "TRXUSDT"), "NEAR/USDT": ("NEAR-USD", "NEARUSDT"), "UNI/USDT": ("UNI7083-USD", "UNIUSDT"),
        "ATOM/USDT": ("ATOM-USD", "ATOMUSDT"), "APT/USDT": ("APT21794-USD", "APTUSDT"), "ARB/USDT": ("ARB11841-USD", "ARBUSDT"),
        "OP/USDT": ("OP-USD", "OPUSDT"), "SUI/USDT": ("SUI20947-USD", "SUIUSDT"), "BCH/USDT": ("BCH-USD", "BCHUSDT"),
        "ETC/USDT": ("ETC-USD", "ETCUSDT"), "FIL/USDT": ("FIL-USD", "FILUSDT"), "INJ/USDT": ("INJ-USD", "INJUSDT"),
    },
    "Forex": {
        "EUR/USD": ("EURUSD=X", None), "GBP/USD": ("GBPUSD=X", None), "USD/JPY": ("USDJPY=X", None), "USD/CHF": ("USDCHF=X", None),
        "AUD/USD": ("AUDUSD=X", None), "USD/CAD": ("USDCAD=X", None), "NZD/USD": ("NZDUSD=X", None), "EUR/GBP": ("EURGBP=X", None),
        "EUR/JPY": ("EURJPY=X", None), "GBP/JPY": ("GBPJPY=X", None), "AUD/JPY": ("AUDJPY=X", None), "EUR/CHF": ("EURCHF=X", None),
        "DXY": ("DX-Y.NYB", None),
    },
    "Commodities": {
        "Gold (XAU/USD)": ("GC=F", None), "Silver (XAG/USD)": ("SI=F", None), "Crude Oil (WTI)": ("CL=F", None), "Brent Oil": ("BZ=F", None),
        "Natural Gas": ("NG=F", None), "Copper": ("HG=F", None), "Platinum": ("PL=F", None), "Corn": ("ZC=F", None), "Wheat": ("ZW=F", None),
    },
    "Indices": {
        "S&P 500": ("^GSPC", None), "Nasdaq 100": ("^NDX", None), "Dow Jones": ("^DJI", None), "Russell 2000": ("^RUT", None),
        "DAX": ("^GDAXI", None), "FTSE 100": ("^FTSE", None), "Nikkei 225": ("^N225", None), "Euro Stoxx 50": ("^STOXX50E", None),
        "Hang Seng": ("^HSI", None), "VIX": ("^VIX", None),
    },
    "Stocks": {
        "Apple (AAPL)": ("AAPL", None), "Microsoft (MSFT)": ("MSFT", None), "NVIDIA (NVDA)": ("NVDA", None), "Tesla (TSLA)": ("TSLA", None),
        "Amazon (AMZN)": ("AMZN", None), "Google (GOOGL)": ("GOOGL", None), "Meta (META)": ("META", None), "AMD": ("AMD", None),
        "Coinbase (COIN)": ("COIN", None), "MicroStrategy (MSTR)": ("MSTR", None), "JPMorgan (JPM)": ("JPM", None), "Exxon (XOM)": ("XOM", None),
        "Johnson & Johnson (JNJ)": ("JNJ", None), "Walmart (WMT)": ("WMT", None), "Netflix (NFLX)": ("NFLX", None), "Boeing (BA)": ("BA", None),
        "Berkshire (BRK-B)": ("BRK-B", None), "Visa (V)": ("V", None), "UnitedHealth (UNH)": ("UNH", None), "Caterpillar (CAT)": ("CAT", None),
    },
    "ETFs": {
        "SPY": ("SPY", None), "QQQ": ("QQQ", None), "IWM": ("IWM", None), "GLD": ("GLD", None), "TLT": ("TLT", None), "XLE": ("XLE", None),
        "XLF": ("XLF", None), "EEM": ("EEM", None), "HYG": ("HYG", None), "USO": ("USO", None),
    },
    "Iran Gold": {
        "طلای 18 عیار / 750": ("IR-GOLD-18K", None),
        "طلای 24 عیار": ("IR-GOLD-24K", None),
        "مثقال طلا": ("IR-MESGHAL", None),
        "انس طلا": ("IR-OUNCE", None),
        "سکه امامی": ("IR-SEKEH-EMAMI", None),
        "سکه بهار آزادی": ("IR-SEKEH-BAHAR", None),
        "نیم سکه": ("IR-NIM", None),
        "ربع سکه": ("IR-ROB", None),
        "سکه گرمی": ("IR-GERAMI", None),
        "دلار آزاد": ("IR-USD", None),
        "یورو آزاد": ("IR-EUR", None),
        "Gold 18K (Iran)": ("IR-GOLD-18K", None),
        "Gold 24K (Iran)": ("IR-GOLD-24K", None),
        "Mesghal Gold": ("IR-MESGHAL", None),
        "Emami Coin": ("IR-SEKEH-EMAMI", None),
        "Bahar Azadi Coin": ("IR-SEKEH-BAHAR", None),
        "Half Coin": ("IR-NIM", None),
        "Quarter Coin": ("IR-ROB", None),
        "Gram Coin": ("IR-GERAMI", None),
        "USD/IRR Free": ("IR-USD", None),
    },
}

IRAN_GOLD_UNIVERSE = UNIVERSE.get("Iran Gold", {})

TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1wk", "1mo"]   # 1 minute → 1 month
# bars of history to request from Binance per timeframe (≈ 70d / 100d / 120d / 1y / 2.7y / 4y)
# multi-year history (Phase 12): 5m ≈ 6 mo, 15m ≈ 1.4 y, 30m ≈ 2 y, 1h ≈ 4 y, 4h ≈ 8 y, 1d = full history
_BINANCE_LIMIT = {"1m": 40000, "3m": 40000, "5m": 50000, "15m": 50000, "30m": 35000, "1h": 35000, "2h": 20000, "4h": 18000, "6h": 12000, "12h": 6000,
                  "1d": 4000, "3d": 1500, "1wk": 600, "1mo": 150}

# how much history to request per timeframe
_PERIOD = {"1m": "7d", "3m": "7d", "5m": "60d", "15m": "60d", "30m": "60d", "1h": "730d", "2h": "730d", "4h": "730d", "6h": "730d", "12h": "730d",
           "1d": "max", "3d": "max", "1wk": "max", "1mo": "max"}
_BINANCE_TF = {"1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "12h": "12h", "1d": "1d",
               "3d": "3d", "1wk": "1w", "1mo": "1M"}
# Yahoo has no 3m/2h/4h/6h/12h/3d → fetch a finer interval and resample
_YF_BASE = {"3m": "1m", "2h": "1h", "4h": "1h", "6h": "1h", "12h": "1h", "3d": "1d"}


def resolve(symbol_name: str):
    # Iran Gold first (priority for Iranian users)
    if _IRAN_GOLD_AVAILABLE and _IRAN_GOLD:
        try:
            if _IRAN_GOLD.is_iran_gold_symbol(symbol_name):
                # Return as custom category with Iran Gold handling
                return "Iran Gold", (symbol_name, None)
        except Exception:
            pass
    
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
        df.to_parquet(path)
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


BINANCE_HOSTS = ["https://data-api.binance.vision", "https://api.binance.com"]   # kept for backward compat


def _fetch_binance(bsym: str, tf: str, limit: int = 1500, since_ms=None) -> pd.DataFrame:
    """Crypto OHLCV via multi-venue failover (binance-vision → OKX → KuCoin → Gate → MEXC).
    api.binance.com is geo-blocked (HTTP 451) in many countries — that was the reason the chart page stayed empty."""
    from core import sources
    base = bsym[:-4] if bsym.upper().endswith("USDT") else bsym
    df, venue = sources.fetch_crypto(base, tf, limit=limit, since_ms=since_ms)
    return df


def _fetch_yahoo(ticker: str, tf: str) -> pd.DataFrame:
    import yfinance as yf
    # Apply resilient proxy detection for yfinance
    if _RESILIENT_AVAILABLE:
        try:
            from core.resilient import detect_system_proxy
            proxy = detect_system_proxy()
            if proxy:
                import os
                os.environ.setdefault("HTTP_PROXY", proxy)
                os.environ.setdefault("HTTPS_PROXY", proxy)
        except Exception:
            pass
    
    interval = tf
    period = _PERIOD.get(tf, "2y")
    if tf in _YF_BASE:  # yahoo lacks this interval -> build from a finer one
        base = _YF_BASE[tf]
        raw = None
        for attempt in range(5):  # increased retries with resilient layer
            try:
                raw = yf.download(ticker, period=_PERIOD[base], interval=base, progress=False, auto_adjust=True, threads=False)
                if raw is not None and not raw.empty:
                    break
            except Exception:
                raw = None
            time.sleep(1.5 * (attempt + 1))
        if raw is None or raw.empty:
            raise RuntimeError(f"No data for {ticker} (yahoo base {base})")
        raw = _normalize(raw)
        return resample(raw, tf)
    raw = None
    for attempt in range(5):                      # Yahoo throttles (429) → short backoff then retry (enhanced)
        try:
            raw = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True, threads=False)
        except Exception as e:
            # If yfinance fails, try direct Yahoo API via resilient session
            if _RESILIENT_AVAILABLE and attempt >= 2:
                try:
                    from core.resilient import session as _rs
                    import pandas as pd
                    # Direct Yahoo chart API as fallback
                    urls = [
                        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={period}&interval={interval}",
                        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range={period}&interval={interval}",
                    ]
                    for url in urls:
                        try:
                            r = _rs().get(url, timeout=15)
                            if r.status_code == 200:
                                j = r.json()
                                chart = j.get("chart", {}).get("result", [{}])[0]
                                ts = chart.get("timestamp", [])
                                quote = chart.get("indicators", {}).get("quote", [{}])[0]
                                if ts and quote:
                                    import pandas as pd
                                    df = pd.DataFrame({
                                        "open": quote.get("open", []),
                                        "high": quote.get("high", []),
                                        "low": quote.get("low", []),
                                        "close": quote.get("close", []),
                                        "volume": quote.get("volume", []),
                                    }, index=pd.to_datetime(ts, unit="s"))
                                    if not df.empty:
                                        raw = df
                                        break
                        except Exception:
                            continue
                except Exception:
                    pass
            raw = None
        if raw is not None and not raw.empty:
            break
        time.sleep(1.5 * (attempt + 1) + (0.5 if _RESILIENT_AVAILABLE else 0))
    if raw is None or raw.empty:
        raise RuntimeError(f"No data for {ticker}")
    return _normalize(raw)


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    r = {"1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "12h": "12h",
         "1d": "1D", "3d": "3D", "1wk": "1W", "1mo": "1MS"}.get(rule, rule)
    o = df.resample(r, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(subset=["open"])
    return o


def get_ohlcv(symbol_name: str, tf: str = "1h", use_cache: bool = True, max_age_sec: int = 300) -> pd.DataFrame:
    # --- Iran Gold handling (طلای ایران) ---
    if _IRAN_GOLD_AVAILABLE and _IRAN_GOLD:
        try:
            if _IRAN_GOLD.is_iran_gold_symbol(symbol_name):
                # Use Iran Gold module directly
                df = _IRAN_GOLD.get_ohlcv_iran_gold(symbol_name, tf)
                df.attrs.update(symbol=symbol_name, tf=tf, source="iran_gold", iran_gold=True)
                return df
        except Exception as e:
            print(f"[data] Iran Gold fetch failed for {symbol_name}: {e}, falling back")
            # fall through to normal flow

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
    cached = None
    if os.path.exists(path):
        try:
            cached = _read_cache(path)
        except Exception:
            cached = None
    if bs:
        try:
            want = _BINANCE_LIMIT.get(tf, 1500)
            if cached is not None and len(cached) >= min(want, 2000) * 0.9 and len(cached) > 100:
                # incremental top-up: fetch only bars after the last cached (drop the last cached bar: it may have been open)
                last_ms = int(cached.index[-2].value // 1_000_000)
                new = _fetch_binance(bs, tf, since_ms=last_ms)
                df = pd.concat([cached.iloc[:-1], new]) if len(new) else cached
                df = df[~df.index.duplicated(keep="last")].sort_index()
                if len(df) < want * 0.8 and len(cached) < want * 0.8:   # cache predates the multi-year limits → full refetch
                    df = _fetch_binance(bs, tf, want)
            else:
                df = _fetch_binance(bs, tf, want)
        except Exception as e:
            errors.append(f"binance: {e}")
    if df is None or df.empty:
        try:
            df = _fetch_yahoo(yt, tf)
            if cached is not None and len(cached) > len(df):   # yahoo intraday windows are short: keep older cached bars
                df = pd.concat([cached, df]); df = df[~df.index.duplicated(keep="last")].sort_index()
        except Exception as e:
            errors.append(f"yahoo: {e}")
    if df is None or df.empty:
        # last resort: stale cache (flagged so the UI can warn)
        if cached is not None:
            cached.attrs.update(symbol=symbol_name, tf=tf, stale=True)
            return cached
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
