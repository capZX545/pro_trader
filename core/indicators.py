"""
Technical indicators library — pure pandas/numpy, no TA-Lib dependency.
All functions take a DataFrame with columns: open, high, low, close, volume
"""
import numpy as np
import pandas as pd


# ---------- Moving averages ----------
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def wma(s: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def hma(s: pd.Series, n: int) -> pd.Series:
    half = wma(s, n // 2)
    full = wma(s, n)
    return wma(2 * half - full, int(np.sqrt(n)))


def vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df.high + df.low + df.close) / 3
    # session-reset VWAP: reset each day
    day = df.index.normalize() if isinstance(df.index, pd.DatetimeIndex) else pd.Series(0, index=df.index)
    pv = (tp * df.volume).groupby(day).cumsum()
    v = df.volume.groupby(day).cumsum()
    return pv / v.replace(0, np.nan)


# ---------- Oscillators ----------
def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    ru = up.ewm(alpha=1 / n, adjust=False).mean()
    rd = dn.ewm(alpha=1 / n, adjust=False).mean()
    rs = ru / rd.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd(s: pd.Series, fast=12, slow=26, sig=9):
    m = ema(s, fast) - ema(s, slow)
    sl = ema(m, sig)
    return m, sl, m - sl


def stochastic(df: pd.DataFrame, k=14, d=3, smooth=3):
    ll = df.low.rolling(k).min()
    hh = df.high.rolling(k).max()
    raw = 100 * (df.close - ll) / (hh - ll).replace(0, np.nan)
    kk = raw.rolling(smooth).mean()
    dd = kk.rolling(d).mean()
    return kk, dd


def stoch_rsi(s: pd.Series, n=14, k=3, d=3):
    r = rsi(s, n)
    lo = r.rolling(n).min()
    hi = r.rolling(n).max()
    sr = (r - lo) / (hi - lo).replace(0, np.nan) * 100
    kk = sr.rolling(k).mean()
    dd = kk.rolling(d).mean()
    return kk, dd


def cci(df: pd.DataFrame, n=20) -> pd.Series:
    tp = (df.high + df.low + df.close) / 3
    ma = tp.rolling(n).mean()
    md = (tp - ma).abs().rolling(n).mean()
    return (tp - ma) / (0.015 * md.replace(0, np.nan))


def williams_r(df: pd.DataFrame, n=14) -> pd.Series:
    hh = df.high.rolling(n).max()
    ll = df.low.rolling(n).min()
    return -100 * (hh - df.close) / (hh - ll).replace(0, np.nan)


def momentum(s: pd.Series, n=10) -> pd.Series:
    return s - s.shift(n)


def roc(s: pd.Series, n=12) -> pd.Series:
    return (s / s.shift(n) - 1) * 100


# ---------- Volatility ----------
def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df.close.shift(1)
    return pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n=14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False).mean()


def bollinger(s: pd.Series, n=20, k=2.0):
    m = sma(s, n)
    sd = s.rolling(n).std(ddof=0)
    return m + k * sd, m, m - k * sd


def keltner(df: pd.DataFrame, n=20, mult=1.5):
    m = ema(df.close, n)
    a = atr(df, n)
    return m + mult * a, m, m - mult * a


def donchian(df: pd.DataFrame, n=20):
    return df.high.rolling(n).max(), df.low.rolling(n).min()


def supertrend(df: pd.DataFrame, n=10, mult=3.0):
    a = atr(df, n)
    hl2 = (df.high + df.low) / 2
    ub = hl2 + mult * a
    lb = hl2 - mult * a
    st = pd.Series(np.nan, index=df.index)
    direction = pd.Series(1, index=df.index)
    ubv, lbv, cl = ub.values, lb.values, df.close.values
    fub = ubv.copy()
    flb = lbv.copy()
    d = np.ones(len(df), dtype=int)
    stv = np.full(len(df), np.nan)
    for i in range(1, len(df)):
        fub[i] = ubv[i] if (ubv[i] < fub[i - 1] or cl[i - 1] > fub[i - 1]) else fub[i - 1]
        flb[i] = lbv[i] if (lbv[i] > flb[i - 1] or cl[i - 1] < flb[i - 1]) else flb[i - 1]
        if d[i - 1] == 1:
            d[i] = -1 if cl[i] < flb[i] else 1
        else:
            d[i] = 1 if cl[i] > fub[i] else -1
        stv[i] = flb[i] if d[i] == 1 else fub[i]
    return pd.Series(stv, index=df.index), pd.Series(d, index=df.index)


# ---------- Trend strength ----------
def adx(df: pd.DataFrame, n=14):
    up = df.high.diff()
    dn = -df.low.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(df)
    atr_ = tr.ewm(alpha=1 / n, adjust=False).mean()
    pdi = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / atr_
    mdi = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / atr_
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean(), pdi, mdi


def ichimoku(df: pd.DataFrame, t=9, k=26, s=52):
    conv = (df.high.rolling(t).max() + df.low.rolling(t).min()) / 2
    base = (df.high.rolling(k).max() + df.low.rolling(k).min()) / 2
    span_a = ((conv + base) / 2).shift(k)
    span_b = ((df.high.rolling(s).max() + df.low.rolling(s).min()) / 2).shift(k)
    lag = df.close.shift(-k)
    return conv, base, span_a, span_b, lag


def parabolic_sar(df: pd.DataFrame, af0=0.02, af_max=0.2) -> pd.Series:
    h, l = df.high.values, df.low.values
    n = len(df)
    sar = np.zeros(n)
    bull = True
    af = af0
    ep = h[0]
    sar[0] = l[0]
    for i in range(1, n):
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
        if bull:
            sar[i] = min(sar[i], l[i - 1], l[i - 2] if i > 1 else l[i - 1])
            if h[i] > ep:
                ep = h[i]
                af = min(af + af0, af_max)
            if l[i] < sar[i]:
                bull = False
                sar[i] = ep
                ep = l[i]
                af = af0
        else:
            sar[i] = max(sar[i], h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if l[i] < ep:
                ep = l[i]
                af = min(af + af0, af_max)
            if h[i] > sar[i]:
                bull = True
                sar[i] = ep
                ep = h[i]
                af = af0
    return pd.Series(sar, index=df.index)


# ---------- Volume ----------
def obv(df: pd.DataFrame) -> pd.Series:
    return (np.sign(df.close.diff()).fillna(0) * df.volume).cumsum()


def mfi(df: pd.DataFrame, n=14) -> pd.Series:
    tp = (df.high + df.low + df.close) / 3
    mf = tp * df.volume
    pos = mf.where(tp > tp.shift(1), 0.0).rolling(n).sum()
    neg = mf.where(tp < tp.shift(1), 0.0).rolling(n).sum()
    return 100 - 100 / (1 + pos / neg.replace(0, np.nan))


def cmf(df: pd.DataFrame, n=20) -> pd.Series:
    mfm = ((df.close - df.low) - (df.high - df.close)) / (df.high - df.low).replace(0, np.nan)
    return (mfm * df.volume).rolling(n).sum() / df.volume.rolling(n).sum()


# ---------- Structure / price action helpers ----------
def swing_points(df: pd.DataFrame, left=5, right=5):
    """Return boolean Series for swing highs & lows (fractal)."""
    hi = df.high
    lo = df.low
    sh = pd.Series(True, index=df.index)
    sl = pd.Series(True, index=df.index)
    for i in range(1, left + 1):
        sh &= hi > hi.shift(i)
        sl &= lo < lo.shift(i)
    for i in range(1, right + 1):
        sh &= hi > hi.shift(-i)
        sl &= lo < lo.shift(-i)
    return sh.fillna(False), sl.fillna(False)


def pivot_points(df: pd.DataFrame):
    """Classic daily floor pivots based on previous bar (use with daily data)."""
    p = (df.high.shift(1) + df.low.shift(1) + df.close.shift(1)) / 3
    r1 = 2 * p - df.low.shift(1)
    s1 = 2 * p - df.high.shift(1)
    r2 = p + (df.high.shift(1) - df.low.shift(1))
    s2 = p - (df.high.shift(1) - df.low.shift(1))
    return p, r1, s1, r2, s2


def fibonacci_levels(high: float, low: float, up: bool = True) -> dict:
    diff = high - low
    ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.705, 0.786, 1.0]
    if up:
        return {r: high - diff * r for r in ratios}
    return {r: low + diff * r for r in ratios}


def body(df):
    return (df.close - df.open).abs()


def upper_wick(df):
    return df.high - df[["open", "close"]].max(axis=1)


def lower_wick(df):
    return df[["open", "close"]].min(axis=1) - df.low


def candle_range(df):
    return (df.high - df.low).replace(0, np.nan)


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience: attach commonly used indicators as columns."""
    out = df.copy()
    out["ema9"] = ema(df.close, 9)
    out["ema21"] = ema(df.close, 21)
    out["ema50"] = ema(df.close, 50)
    out["ema200"] = ema(df.close, 200)
    out["sma20"] = sma(df.close, 20)
    out["rsi"] = rsi(df.close)
    m, s, h = macd(df.close)
    out["macd"], out["macd_sig"], out["macd_hist"] = m, s, h
    out["atr"] = atr(df)
    u, mid, l = bollinger(df.close)
    out["bb_up"], out["bb_mid"], out["bb_lo"] = u, mid, l
    a, p, mi = adx(df)
    out["adx"], out["pdi"], out["mdi"] = a, p, mi
    out["obv"] = obv(df)
    out["vol_sma"] = sma(df.volume, 20)
    return out
