"""
Extended indicator library (≈60 additional indicators) + bilingual INDICATOR_CATALOG used by the Academy encyclopedia
and the ML feature builder. All functions accept a DataFrame (open/high/low/close/volume) or a Series and return Series.
"""
import numpy as np
import pandas as pd
from core.indicators import sma, ema, wma, hma, rsi, atr, true_range, macd, bollinger, adx, obv, mfi, cci, stochastic

# ------------------------------------------------------------------ moving averages
def dema(s, n=20):
    e = ema(s, n)
    return 2 * e - ema(e, n)


def tema(s, n=20):
    e1 = ema(s, n); e2 = ema(e1, n); e3 = ema(e2, n)
    return 3 * e1 - 3 * e2 + e3


def zlema(s, n=20):
    lag = (n - 1) // 2
    return ema(s + (s - s.shift(lag)), n)


def vwma(df, n=20):
    v = df.volume.replace(0, np.nan)
    return (df.close * v).rolling(n).sum() / v.rolling(n).sum()


def kama(s, n=10, fast=2, slow=30):
    change = (s - s.shift(n)).abs()
    vol = (s - s.shift(1)).abs().rolling(n).sum()
    er = (change / vol.replace(0, np.nan)).fillna(0)
    sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
    out = np.full(len(s), np.nan)
    vals = s.values
    scv = sc.values
    start = n
    if len(s) <= n:
        return pd.Series(out, index=s.index)
    out[start] = vals[start]
    for i in range(start + 1, len(s)):
        out[i] = out[i - 1] + scv[i] * (vals[i] - out[i - 1])
    return pd.Series(out, index=s.index)


def alma(s, n=9, offset=0.85, sigma=6):
    m = offset * (n - 1)
    sd = n / sigma
    w = np.exp(-((np.arange(n) - m) ** 2) / (2 * sd * sd))
    w /= w.sum()
    return s.rolling(n).apply(lambda x: np.dot(x, w), raw=True)


def t3(s, n=5, vf=0.7):
    e1 = ema(s, n); e2 = ema(e1, n); e3 = ema(e2, n); e4 = ema(e3, n); e5 = ema(e4, n); e6 = ema(e5, n)
    c1 = -vf ** 3; c2 = 3 * vf ** 2 + 3 * vf ** 3; c3 = -6 * vf ** 2 - 3 * vf - 3 * vf ** 3; c4 = 1 + 3 * vf + vf ** 3 + 3 * vf ** 2
    return c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3


def mcginley(s, n=14):
    out = np.full(len(s), np.nan)
    v = s.values
    out[0] = v[0]
    for i in range(1, len(v)):
        prev = out[i - 1]
        ratio = v[i] / prev if prev else 1
        out[i] = prev + (v[i] - prev) / (n * ratio ** 4) if ratio > 0 else v[i]
    return pd.Series(out, index=s.index)


def supersmoother(s, n=10):
    a1 = np.exp(-1.414 * np.pi / n)
    b1 = 2 * a1 * np.cos(1.414 * np.pi / n)
    c2, c3 = b1, -a1 * a1
    c1 = 1 - c2 - c3
    out = np.full(len(s), np.nan)
    v = s.values
    out[0], out[1] = v[0], v[1]
    for i in range(2, len(v)):
        out[i] = c1 * (v[i] + v[i - 1]) / 2 + c2 * out[i - 1] + c3 * out[i - 2]
    return pd.Series(out, index=s.index)


def linreg(s, n=14):
    x = np.arange(n)
    xm = x.mean()
    den = ((x - xm) ** 2).sum()
    slope = s.rolling(n).apply(lambda y: ((x - xm) * (y - y.mean())).sum() / den, raw=True)
    intercept = s.rolling(n).mean() - slope * xm
    return intercept + slope * (n - 1), slope


def lin_reg_channel(s, n=100, k=2.0):
    val, slope = linreg(s, n)
    resid = s - val
    sd = resid.rolling(n).std()
    return val, val + k * sd, val - k * sd, slope


# ------------------------------------------------------------------ oscillators
def aroon(df, n=25):
    up = df.high.rolling(n + 1).apply(lambda x: 100 * x.argmax() / n, raw=True)
    dn = df.low.rolling(n + 1).apply(lambda x: 100 * x.argmin() / n, raw=True)
    return up, dn, up - dn


def vortex(df, n=14):
    tr = true_range(df).rolling(n).sum()
    vmp = (df.high - df.low.shift(1)).abs().rolling(n).sum()
    vmm = (df.low - df.high.shift(1)).abs().rolling(n).sum()
    return vmp / tr, vmm / tr


def trix(s, n=15):
    e = ema(ema(ema(s, n), n), n)
    return 100 * (e / e.shift(1) - 1)


def ultimate(df, s1=7, s2=14, s3=28):
    bp = df.close - pd.concat([df.low, df.close.shift(1)], axis=1).min(axis=1)
    tr = true_range(df)
    a1 = bp.rolling(s1).sum() / tr.rolling(s1).sum()
    a2 = bp.rolling(s2).sum() / tr.rolling(s2).sum()
    a3 = bp.rolling(s3).sum() / tr.rolling(s3).sum()
    return 100 * (4 * a1 + 2 * a2 + a3) / 7


def awesome(df, f=5, s=34):
    mp = (df.high + df.low) / 2
    return sma(mp, f) - sma(mp, s)


def accelerator(df):
    ao = awesome(df)
    return ao - sma(ao, 5)


def dpo(s, n=20):
    return s.shift(n // 2 + 1) - sma(s, n)


def kst(s, r1=10, r2=15, r3=20, r4=30, n1=10, n2=10, n3=10, n4=15, sig=9):
    roc = lambda n: 100 * (s / s.shift(n) - 1)
    k = sma(roc(r1), n1) + 2 * sma(roc(r2), n2) + 3 * sma(roc(r3), n3) + 4 * sma(roc(r4), n4)
    return k, sma(k, sig)


def coppock(s, wl=10, r1=14, r2=11):
    roc = 100 * (s / s.shift(r1) - 1) + 100 * (s / s.shift(r2) - 1)
    return wma(roc, wl)


def ppo(s, fast=12, slow=26, sig=9):
    p = 100 * (ema(s, fast) - ema(s, slow)) / ema(s, slow)
    return p, ema(p, sig)


def cmo(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).rolling(n).sum()
    dn = (-d.clip(upper=0)).rolling(n).sum()
    return 100 * (up - dn) / (up + dn).replace(0, np.nan)


def fisher(df, n=9):
    mp = (df.high + df.low) / 2
    lo = mp.rolling(n).min(); hi = mp.rolling(n).max()
    x = (2 * (mp - lo) / (hi - lo).replace(0, np.nan) - 1).clip(-0.999, 0.999).fillna(0)
    v = np.zeros(len(x)); f = np.zeros(len(x))
    xv = x.values
    for i in range(1, len(xv)):
        v[i] = 0.33 * xv[i] + 0.67 * v[i - 1]
        vi = min(max(v[i], -0.999), 0.999)
        f[i] = 0.5 * np.log((1 + vi) / (1 - vi)) + 0.5 * f[i - 1]
    f = pd.Series(f, index=df.index)
    return f, f.shift(1)


def schaff(s, fast=23, slow=50, cycle=10):
    m = ema(s, fast) - ema(s, slow)
    lo = m.rolling(cycle).min(); hi = m.rolling(cycle).max()
    st1 = (100 * (m - lo) / (hi - lo).replace(0, np.nan)).fillna(50).ewm(span=3, adjust=False).mean()
    lo2 = st1.rolling(cycle).min(); hi2 = st1.rolling(cycle).max()
    return (100 * (st1 - lo2) / (hi2 - lo2).replace(0, np.nan)).fillna(50).ewm(span=3, adjust=False).mean()


def rvi(df, n=10):
    num = (df.close - df.open) + 2 * (df.close - df.open).shift(1) + 2 * (df.close - df.open).shift(2) + (df.close - df.open).shift(3)
    den = (df.high - df.low) + 2 * (df.high - df.low).shift(1) + 2 * (df.high - df.low).shift(2) + (df.high - df.low).shift(3)
    r = sma(num, n) / sma(den, n).replace(0, np.nan)
    sig = (r + 2 * r.shift(1) + 2 * r.shift(2) + r.shift(3)) / 6
    return r, sig


def connors_rsi(s, n1=3, n2=2, n3=100):
    d = np.sign(s.diff())
    streak = d.groupby((d != d.shift()).cumsum()).cumsum()
    pr = s.pct_change().rolling(n3).apply(lambda x: (x[:-1] < x[-1]).mean() * 100, raw=True)
    return (rsi(s, n1) + rsi(streak.fillna(0), n2) + pr) / 3


def qqe(s, n=14, sf=5, wf=4.236):
    r = ema(rsi(s, n), sf)
    d = r.diff().abs()
    w = n * 2 - 1
    dar = ema(ema(d, w), w) * wf
    longband = np.zeros(len(r)); shortband = np.zeros(len(r)); trend = np.ones(len(r))
    rv = r.values; dv = dar.values
    for i in range(1, len(rv)):
        nl = rv[i] - dv[i]; ns = rv[i] + dv[i]
        longband[i] = max(longband[i - 1], nl) if rv[i - 1] > longband[i - 1] and rv[i] > longband[i - 1] else nl
        shortband[i] = min(shortband[i - 1], ns) if rv[i - 1] < shortband[i - 1] and rv[i] < shortband[i - 1] else ns
        if rv[i] > shortband[i - 1]:
            trend[i] = 1
        elif rv[i] < longband[i - 1]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]
    fast = pd.Series(np.where(trend == 1, longband, shortband), index=s.index)
    return r, fast


def squeeze_momentum(df, bb_n=20, bb_k=2.0, kc_n=20, kc_k=1.5):
    """LazyBear Squeeze Momentum: squeeze_on (BB inside KC) and momentum (linreg of price − midline)."""
    u, m, l = bollinger(df.close, bb_n, bb_k)
    a = atr(df, kc_n)
    kc_u, kc_l = m + kc_k * a, m - kc_k * a
    on = (l > kc_l) & (u < kc_u)
    mid = (df.high.rolling(kc_n).max() + df.low.rolling(kc_n).min()) / 2
    src = df.close - (mid + sma(df.close, kc_n)) / 2
    val, _ = linreg(src, kc_n)
    return on, val


def williams_ad(df):
    trh = pd.concat([df.high, df.close.shift(1)], axis=1).max(axis=1)
    trl = pd.concat([df.low, df.close.shift(1)], axis=1).min(axis=1)
    ad = np.where(df.close > df.close.shift(1), df.close - trl, np.where(df.close < df.close.shift(1), df.close - trh, 0))
    return pd.Series(ad, index=df.index).cumsum()


def elder_ray(df, n=13):
    e = ema(df.close, n)
    return df.high - e, df.low - e


def mass_index(df, n=9, s=25):
    r = df.high - df.low
    ratio = ema(r, n) / ema(ema(r, n), n)
    return ratio.rolling(s).sum()


def choppiness(df, n=14):
    tr = true_range(df).rolling(n).sum()
    rng = (df.high.rolling(n).max() - df.low.rolling(n).min()).replace(0, np.nan)
    return 100 * np.log10(tr / rng) / np.log10(n)


def efficiency_ratio(s, n=10):
    return ((s - s.shift(n)).abs() / (s - s.shift(1)).abs().rolling(n).sum().replace(0, np.nan)).fillna(0)


def hurst(s, n=100):
    """Rolling simplified Hurst exponent via rescaled range (>0.5 trending, <0.5 mean-reverting)."""
    def _h(x):
        x = np.diff(np.log(x))
        if len(x) < 20 or x.std() == 0:
            return 0.5
        lags = range(2, 20)
        tau = [np.std(np.cumsum(x)[l:] - np.cumsum(x)[:-l]) for l in lags]
        return float(np.clip(np.polyfit(np.log(list(lags)), np.log(tau), 1)[0], 0, 1))
    # evaluate every `step` bars for speed, forward-fill in between
    step = 10
    vals = s.values
    out = np.full(len(s), np.nan)
    for i in range(n, len(s), step):
        out[i] = _h(vals[i - n:i])
    return pd.Series(out, index=s.index).ffill()


def zscore(s, n=20):
    return (s - s.rolling(n).mean()) / s.rolling(n).std().replace(0, np.nan)


def percent_rank(s, n=100):
    return s.rolling(n).apply(lambda x: (x[:-1] < x[-1]).mean() * 100, raw=True)


def hist_vol(s, n=20, ann=365):
    return np.log(s / s.shift(1)).rolling(n).std() * np.sqrt(ann) * 100


def stdev_bands(s, n=20, k=2.0):
    m = sma(s, n); sd = s.rolling(n).std()
    return m + k * sd, m, m - k * sd, (2 * k * sd) / m * 100  # bandwidth


def bb_percent_b(s, n=20, k=2.0):
    u, m, l = bollinger(s, n, k)
    return (s - l) / (u - l).replace(0, np.nan)


# ------------------------------------------------------------------ volume
def ad_line(df):
    clv = ((df.close - df.low) - (df.high - df.close)) / (df.high - df.low).replace(0, np.nan)
    return (clv.fillna(0) * df.volume).cumsum()


def chaikin_osc(df, f=3, s=10):
    ad = ad_line(df)
    return ema(ad, f) - ema(ad, s)


def force_index(df, n=13):
    return ema(df.close.diff() * df.volume, n)


def eom(df, n=14):
    mid_move = ((df.high + df.low) / 2) - ((df.high.shift(1) + df.low.shift(1)) / 2)
    box = (df.volume / 1e6) / (df.high - df.low).replace(0, np.nan)
    return sma(mid_move / box.replace(0, np.nan), n)


def vpt(df):
    return (df.volume * df.close.pct_change()).cumsum()


def nvi(df):
    pc = df.close.pct_change().fillna(0)
    out = np.ones(len(df)) * 1000
    v = df.volume.values; pcv = pc.values
    for i in range(1, len(df)):
        out[i] = out[i - 1] * (1 + pcv[i]) if v[i] < v[i - 1] else out[i - 1]
    return pd.Series(out, index=df.index)


def pvi(df):
    pc = df.close.pct_change().fillna(0)
    out = np.ones(len(df)) * 1000
    v = df.volume.values; pcv = pc.values
    for i in range(1, len(df)):
        out[i] = out[i - 1] * (1 + pcv[i]) if v[i] > v[i - 1] else out[i - 1]
    return pd.Series(out, index=df.index)


def klinger(df, f=34, s=55, sig=13):
    hlc = df.high + df.low + df.close
    trend = np.where(hlc > hlc.shift(1), 1, -1)
    dm = df.high - df.low
    cm = np.zeros(len(df)); dmv = dm.values
    for i in range(1, len(df)):
        cm[i] = cm[i - 1] + dmv[i] if trend[i] == trend[i - 1] else dmv[i - 1] + dmv[i]
    vf = df.volume * np.abs(2 * (dm / pd.Series(cm, index=df.index).replace(0, np.nan)) - 1) * trend * 100
    kvo = ema(vf, f) - ema(vf, s)
    return kvo, ema(kvo, sig)


def relative_volume(df, n=20):
    return df.volume / df.volume.rolling(n).mean().replace(0, np.nan)


def volume_profile(df, bins=24, lookback=300):
    """Returns (poc_price, value_area_low, value_area_high, hist DataFrame) over the last `lookback` bars."""
    d = df.tail(lookback)
    lo, hi = d.low.min(), d.high.max()
    edges = np.linspace(lo, hi, bins + 1)
    vol = np.zeros(bins)
    for h, l, v in zip(d.high.values, d.low.values, d.volume.values):
        i0 = np.searchsorted(edges, l, side="right") - 1
        i1 = np.searchsorted(edges, h, side="right") - 1
        i0, i1 = max(i0, 0), min(i1, bins - 1)
        share = v / (i1 - i0 + 1)
        vol[i0:i1 + 1] += share
    poc = int(vol.argmax())
    total = vol.sum()
    lo_i = hi_i = poc
    acc = vol[poc]
    while acc < 0.7 * total and (lo_i > 0 or hi_i < bins - 1):
        left = vol[lo_i - 1] if lo_i > 0 else -1
        right = vol[hi_i + 1] if hi_i < bins - 1 else -1
        if right >= left:
            hi_i += 1; acc += vol[hi_i]
        else:
            lo_i -= 1; acc += vol[lo_i]
    centers = (edges[:-1] + edges[1:]) / 2
    return centers[poc], edges[lo_i], edges[hi_i + 1], pd.DataFrame({"price": centers, "volume": vol})


# ------------------------------------------------------------------ price transforms / patterns
def heikin_ashi(df):
    ha = pd.DataFrame(index=df.index)
    ha["close"] = (df.open + df.high + df.low + df.close) / 4
    o = np.zeros(len(df)); o[0] = (df.open.iloc[0] + df.close.iloc[0]) / 2
    hc = ha.close.values
    for i in range(1, len(df)):
        o[i] = (o[i - 1] + hc[i - 1]) / 2
    ha["open"] = o
    ha["high"] = pd.concat([df.high, ha.open, ha.close], axis=1).max(axis=1)
    ha["low"] = pd.concat([df.low, ha.open, ha.close], axis=1).min(axis=1)
    ha["volume"] = df.volume
    return ha[["open", "high", "low", "close", "volume"]]


def zigzag(df, pct=5.0):
    """Returns Series with pivot prices at pivot bars (NaN elsewhere) using % reversal (last leg is provisional)."""
    hi, lo = df.high.values, df.low.values
    n = len(df)
    out = np.full(n, np.nan)
    if n < 2:
        return pd.Series(out, index=df.index)
    th = pct / 100.0
    trend = 0                       # 0 unknown, +1 seeking a high (uptrend), −1 seeking a low
    last_i, last_p = 0, hi[0]
    lo_i, lo_p = 0, lo[0]
    for i in range(1, n):
        if trend == 0:
            if hi[i] > last_p:
                last_i, last_p = i, hi[i]
            if lo[i] < lo_p:
                lo_i, lo_p = i, lo[i]
            if hi[i] >= lo_p * (1 + th):
                trend = 1; out[lo_i] = lo_p; last_i, last_p = i, hi[i]
            elif lo[i] <= last_p * (1 - th):
                trend = -1; out[last_i] = last_p; last_i, last_p = i, lo[i]
        elif trend == 1:
            if hi[i] > last_p:
                last_i, last_p = i, hi[i]
            elif lo[i] <= last_p * (1 - th):
                out[last_i] = last_p; trend = -1; last_i, last_p = i, lo[i]
        else:
            if lo[i] < last_p:
                last_i, last_p = i, lo[i]
            elif hi[i] >= last_p * (1 + th):
                out[last_i] = last_p; trend = 1; last_i, last_p = i, hi[i]
    out[last_i] = last_p            # provisional last pivot
    return pd.Series(out, index=df.index)


def pivots_fib(df):
    p = (df.high.shift(1) + df.low.shift(1) + df.close.shift(1)) / 3
    r = df.high.shift(1) - df.low.shift(1)
    return {"P": p, "R1": p + 0.382 * r, "R2": p + 0.618 * r, "R3": p + r, "S1": p - 0.382 * r, "S2": p - 0.618 * r, "S3": p - r}


def pivots_camarilla(df):
    c, r = df.close.shift(1), df.high.shift(1) - df.low.shift(1)
    return {"R4": c + r * 1.1 / 2, "R3": c + r * 1.1 / 4, "R2": c + r * 1.1 / 6, "R1": c + r * 1.1 / 12,
            "S1": c - r * 1.1 / 12, "S2": c - r * 1.1 / 6, "S3": c - r * 1.1 / 4, "S4": c - r * 1.1 / 2}


def pivots_woodie(df):
    p = (df.high.shift(1) + df.low.shift(1) + 2 * df.open) / 4
    return {"P": p, "R1": 2 * p - df.low.shift(1), "S1": 2 * p - df.high.shift(1),
            "R2": p + df.high.shift(1) - df.low.shift(1), "S2": p - df.high.shift(1) + df.low.shift(1)}


def halftrend(df, amp=2, dev=2.0):
    """Simplified HalfTrend (trend series 1/-1 + line)."""
    a = atr(df, 100) / 2
    hp = df.high.rolling(amp).max(); lp = df.low.rolling(amp).min()
    hma_ = sma(df.high, amp); lma_ = sma(df.low, amp)
    n = len(df)
    trend = np.zeros(n); maxlow = np.zeros(n); minhigh = np.zeros(n); line = np.full(n, np.nan)
    maxlow[0] = df.low.iloc[0]; minhigh[0] = df.high.iloc[0]
    for i in range(1, n):
        trend[i] = trend[i - 1]; maxlow[i] = maxlow[i - 1]; minhigh[i] = minhigh[i - 1]
        if trend[i] == 0:
            maxlow[i] = max(lp.iloc[i], maxlow[i - 1]) if lp.iloc[i] == lp.iloc[i] else maxlow[i - 1]
            if hma_.iloc[i] < maxlow[i] and df.close.iloc[i] < df.low.iloc[i - 1]:
                trend[i] = 1; minhigh[i] = hp.iloc[i]
            line[i] = maxlow[i]
        else:
            minhigh[i] = min(hp.iloc[i], minhigh[i - 1]) if hp.iloc[i] == hp.iloc[i] else minhigh[i - 1]
            if lma_.iloc[i] > minhigh[i] and df.close.iloc[i] > df.high.iloc[i - 1]:
                trend[i] = 0; maxlow[i] = lp.iloc[i]
            line[i] = minhigh[i]
    return pd.Series(np.where(trend == 0, 1, -1), index=df.index), pd.Series(line, index=df.index)


def rs_vs(df, bench_close, n=20):
    """Relative strength of df.close vs a benchmark series (e.g. BTC): ratio momentum over n bars."""
    b = bench_close.reindex(df.index).ffill()
    ratio = df.close / b
    return 100 * (ratio / ratio.shift(n) - 1)


# ------------------------------------------------------------------ catalog (Academy encyclopedia + ML feature names)
# fields: key, name_en, name_fa, group, how_en, how_fa, read_en (interpretation), read_fa
INDICATOR_CATALOG = [
    # Trend / MAs
    dict(key="sma", group="Trend", name_en="Simple Moving Average (SMA)", name_fa="میانگین متحرک ساده (SMA)",
         how_en="Arithmetic mean of the last N closes.", how_fa="میانگین حسابی N قیمت بسته آخر.",
         read_en="Price above rising SMA = uptrend; 50/200 crosses define golden/death cross. Lags by ~N/2 bars.",
         read_fa="قیمت بالای SMA صعودی = روند صعودی؛ کراس ۵۰/۲۰۰ تقاطع طلایی/مرگ. حدود N/2 کندل تأخیر دارد."),
    dict(key="ema", group="Trend", name_en="Exponential MA (EMA)", name_fa="میانگین متحرک نمایی (EMA)",
         how_en="Weighted mean giving more weight to recent bars (α=2/(N+1)).", how_fa="میانگین وزنی با وزن بیشتر به کندل‌های اخیر (α=2/(N+1)).",
         read_en="Faster than SMA. EMA 9/21 for momentum, 50 for swing trend, 200 for regime.", read_fa="سریع‌تر از SMA. EMA ۹/۲۱ برای مومنتوم، ۵۰ برای روند سوئینگ، ۲۰۰ برای رژیم."),
    dict(key="wma", group="Trend", name_en="Weighted MA (WMA)", name_fa="میانگین وزنی (WMA)", how_en="Linear weights 1..N.", how_fa="وزن‌های خطی ۱ تا N.",
         read_en="Building block of HMA; slightly faster than SMA.", read_fa="جزء سازندهٔ HMA؛ کمی سریع‌تر از SMA."),
    dict(key="hma", group="Trend", name_en="Hull MA (HMA)", name_fa="میانگین هال (HMA)", how_en="WMA(2·WMA(N/2) − WMA(N), √N).", how_fa="WMA(2·WMA(N/2) − WMA(N), √N).",
         read_en="Very low lag; slope color flips are used as trend signals. Overshoots in chop.", read_fa="تأخیر خیلی کم؛ تغییر شیب سیگنال روند است. در رنج اورشوت می‌کند."),
    dict(key="dema", group="Trend", name_en="Double EMA (DEMA)", name_fa="EMA دوگانه (DEMA)", how_en="2·EMA − EMA(EMA).", how_fa="2·EMA − EMA(EMA).",
         read_en="Reduces lag of EMA; use like EMA with tighter reaction.", read_fa="تأخیر EMA را کم می‌کند؛ مثل EMA ولی واکنش سریع‌تر."),
    dict(key="tema", group="Trend", name_en="Triple EMA (TEMA)", name_fa="EMA سه‌گانه (TEMA)", how_en="3·E1 − 3·E2 + E3.", how_fa="3·E1 − 3·E2 + E3.",
         read_en="Even lower lag; freqtrade 'Quickie' uses TEMA vs BB mid.", read_fa="تأخیر کمتر؛ استراتژی Quickie از TEMA در برابر میانهٔ بولینگر استفاده می‌کند."),
    dict(key="zlema", group="Trend", name_en="Zero-Lag EMA", name_fa="EMA بدون تأخیر (ZLEMA)", how_en="EMA of price + (price − price[lag]).", how_fa="EMA از قیمت + (قیمت − قیمت[lag]).",
         read_en="Compensates lag by extrapolating momentum; noisier.", read_fa="با برون‌یابی مومنتوم تأخیر را جبران می‌کند؛ نویزی‌تر."),
    dict(key="kama", group="Trend", name_en="Kaufman Adaptive MA (KAMA)", name_fa="میانگین تطبیقی کافمن (KAMA)", how_en="EMA whose speed adapts to Efficiency Ratio.", how_fa="EMA که سرعتش با نسبت کارایی تطبیق می‌یابد.",
         read_en="Flat in chop, fast in trends — great trend filter: trade only when KAMA slopes.", read_fa="در رنج صاف، در روند سریع — فیلتر روند عالی: فقط وقتی KAMA شیب دارد معامله کن."),
    dict(key="alma", group="Trend", name_en="Arnaud Legoux MA (ALMA)", name_fa="میانگین آرنو لگو (ALMA)", how_en="Gaussian-weighted MA with offset.", how_fa="میانگین با وزن گاوسی و آفست.",
         read_en="Smooth and responsive; popular in TradingView trend scripts.", read_fa="نرم و پاسخگو؛ در اسکریپت‌های روندی تریدینگ‌ویو محبوب."),
    dict(key="t3", group="Trend", name_en="Tillson T3", name_fa="T3 تیلسون", how_en="Six-fold EMA with volume factor.", how_fa="EMA شش‌لایه با ضریب حجم.",
         read_en="Very smooth; slope change = trend change with little whipsaw.", read_fa="بسیار نرم؛ تغییر شیب = تغییر روند با ویپساو کم."),
    dict(key="mcginley", group="Trend", name_en="McGinley Dynamic", name_fa="داینامیک مک‌گینلی", how_en="Self-adjusting MA that speeds up in falls.", how_fa="میانگین خودتنظیم که در ریزش سریع‌تر می‌شود.",
         read_en="Hugs price better than EMA; use as dynamic support/resistance.", read_fa="بهتر از EMA به قیمت می‌چسبد؛ به‌عنوان حمایت/مقاومت داینامیک."),
    dict(key="supersmoother", group="Trend", name_en="Ehlers Super Smoother", name_fa="سوپر اسموتر الرز", how_en="2-pole Butterworth low-pass filter.", how_fa="فیلتر پایین‌گذر باترورث دوقطبی.",
         read_en="Removes noise above the cycle period with minimal lag; DSP-grade MA.", read_fa="نویز بالاتر از دورهٔ سیکل را با کمترین تأخیر حذف می‌کند."),
    dict(key="linreg", group="Trend", name_en="Linear Regression / Channel", name_fa="رگرسیون خطی / کانال", how_en="Least-squares line over N bars ± k·σ.", how_fa="خط کمترین مربعات روی N کندل ± k·σ.",
         read_en="Slope = trend strength; touches of ±2σ = mean-reversion zones.", read_fa="شیب = قدرت روند؛ برخورد به ±2σ = نواحی بازگشت به میانگین."),
    dict(key="ichimoku", group="Trend", name_en="Ichimoku Kinko Hyo", name_fa="ایچیموکو", how_en="Tenkan 9, Kijun 26, Senkou A/B (cloud), Chikou.", how_fa="تنکان ۹، کیجون ۲۶، سنکو A/B (ابر)، چیکو.",
         read_en="Price above green cloud + TK cross + Chikou free = strong long.", read_fa="قیمت بالای ابر سبز + کراس TK + چیکو آزاد = خرید قوی."),
    dict(key="supertrend", group="Trend", name_en="SuperTrend", name_fa="سوپرترند", how_en="ATR(10)×3 trailing band that flips with close.", how_fa="باند تریلینگ ATR(10)×۳ که با بسته شدن قیمت برمی‌گردد.",
         read_en="Flip = trend change; use with ADX>20 to cut whipsaws.", read_fa="برگشت = تغییر روند؛ با ADX>۲۰ ویپساو کم می‌شود."),
    dict(key="psar", group="Trend", name_en="Parabolic SAR", name_fa="پارابولیک SAR", how_en="Accelerating stop dots (AF 0.02→0.2).", how_fa="نقاط استاپ شتاب‌دار (AF ۰.۰۲→۰.۲).",
         read_en="Dots below = long. Best as trailing stop, poor as entry in ranges.", read_fa="نقاط زیر = خرید. بهترین کاربرد استاپ تریلینگ، در رنج ورود ضعیف."),
    dict(key="halftrend", group="Trend", name_en="HalfTrend", name_fa="هاف‌ترند", how_en="Channel of recent highs/lows that flips when breached with ATR filter.", how_fa="کانال سقف/کف اخیر که با شکست و فیلتر ATR برمی‌گردد.",
         read_en="Popular TradingView trend flipper; fewer flips than SuperTrend.", read_fa="ترندفلیپر محبوب تریدینگ‌ویو؛ برگشت کمتر از سوپرترند."),
    dict(key="adx", group="Trend", name_en="ADX / DMI", name_fa="ADX / DMI", how_en="Smoothed |+DI − −DI| / (+DI + −DI).", how_fa="نرم‌شدهٔ |+DI − −DI| / (+DI + −DI).",
         read_en="ADX>25 trending, <20 ranging. Direction from +DI/−DI. Rising ADX = strengthening.", read_fa="ADX>۲۵ روند، <۲۰ رنج. جهت از +DI/−DI. ADX صعودی = تقویت."),
    dict(key="aroon", group="Trend", name_en="Aroon Up/Down", name_fa="آرون", how_en="Bars since N-period high/low, scaled 0–100.", how_fa="کندل‌های گذشته از سقف/کف N دوره، ۰–۱۰۰.",
         read_en="Up>70 & Down<30 = strong uptrend; crosses signal new trends early.", read_fa="Up>۷۰ و Down<۳۰ = روند صعودی قوی؛ کراس‌ها روند جدید را زود نشان می‌دهند."),
    dict(key="vortex", group="Trend", name_en="Vortex (VI+ / VI−)", name_fa="ورتکس", how_en="Sum of |high − prev low| vs |low − prev high| over TR.", how_fa="مجموع |سقف − کف قبلی| در برابر |کف − سقف قبلی| بر TR.",
         read_en="VI+ crossing above VI− = uptrend start.", read_fa="کراس VI+ بالای VI− = شروع روند صعودی."),
    dict(key="trix", group="Trend", name_en="TRIX", name_fa="TRIX", how_en="1-bar % change of triple-smoothed EMA.", how_fa="درصد تغییر یک‌کندلی EMA سه‌بار نرم‌شده.",
         read_en="Zero-line cross = trend; filters noise cycles shorter than N.", read_fa="کراس خط صفر = روند؛ سیکل‌های کوتاه‌تر از N را فیلتر می‌کند."),
    dict(key="kst", group="Trend", name_en="Know Sure Thing (KST)", name_fa="KST پرینگ", how_en="Weighted sum of 4 smoothed ROCs.", how_fa="مجموع وزنی ۴ ROC نرم‌شده.",
         read_en="Signal-line cross for long-term momentum turns.", read_fa="کراس خط سیگنال برای چرخش مومنتوم بلندمدت."),
    dict(key="coppock", group="Trend", name_en="Coppock Curve", name_fa="منحنی کاپاک", how_en="WMA10 of ROC14 + ROC11 (monthly origin).", how_fa="WMA10 از ROC14 + ROC11.",
         read_en="Upturn from below zero = major bottom (index investing classic).", read_fa="چرخش صعودی از زیر صفر = کف بزرگ (کلاسیک سرمایه‌گذاری شاخصی)."),
    dict(key="dpo", group="Cycle", name_en="Detrended Price Oscillator", name_fa="اسیلاتور قیمت روندزدایی‌شده", how_en="Price shifted − SMA(N).", how_fa="قیمت جابه‌جاشده − SMA(N).",
         read_en="Isolates cycles; peaks/troughs spacing estimates cycle length.", read_fa="سیکل‌ها را جدا می‌کند؛ فاصلهٔ قله‌ها طول سیکل را تخمین می‌زند."),
    dict(key="schaff", group="Cycle", name_en="Schaff Trend Cycle", name_fa="سیکل روند شاف", how_en="Double stochastic of MACD.", how_fa="استوکاستیک دوگانه از MACD.",
         read_en="Cross up from <25 = buy; faster than MACD with less whipsaw.", read_fa="کراس بالا از <۲۵ = خرید؛ سریع‌تر از MACD با ویپساو کمتر."),
    dict(key="hurst", group="Cycle", name_en="Hurst Exponent", name_fa="نمای هرست", how_en="Rescaled-range estimate of persistence.", how_fa="تخمین دامنهٔ بازمقیاس‌شدهٔ پایداری.",
         read_en=">0.55 trending (use trend systems), <0.45 mean-reverting (use RSI/BB).", read_fa=">۰.۵۵ رونددار (سیستم روندی)، <۰.۴۵ بازگشتی (RSI/BB)."),
    dict(key="efficiency_ratio", group="Cycle", name_en="Kaufman Efficiency Ratio", name_fa="نسبت کارایی کافمن", how_en="Net move / sum of moves.", how_fa="حرکت خالص / مجموع حرکات.",
         read_en="Near 1 = clean trend; near 0 = noise. Regime filter.", read_fa="نزدیک ۱ = روند تمیز؛ نزدیک ۰ = نویز. فیلتر رژیم."),
    dict(key="choppiness", group="Cycle", name_en="Choppiness Index", name_fa="شاخص چاپینس", how_en="log10(ΣTR / range) / log10(N) ×100.", how_fa="log10(ΣTR / دامنه) / log10(N) ×۱۰۰.",
         read_en=">61.8 choppy — don't trend-trade; <38.2 strong trend.", read_fa=">۶۱.۸ رنج — روندی معامله نکن؛ <۳۸.۲ روند قوی."),
    # Momentum
    dict(key="rsi", group="Momentum", name_en="RSI", name_fa="RSI", how_en="100 − 100/(1 + avg gain/avg loss), Wilder N=14.", how_fa="100 − 100/(1 + میانگین سود/زیان)، وایلدر N=۱۴.",
         read_en="<30/>70 extremes; 40–60 range in trends; divergences and 50-line as trend filter. RSI(2)<10 = Connors dip.", read_fa="<۳۰/>۷۰ اشباع؛ در روند ۴۰–۶۰؛ واگرایی و خط ۵۰ فیلتر روند. RSI(2)<۱۰ = دیپ کانرز."),
    dict(key="stoch", group="Momentum", name_en="Stochastic %K/%D", name_fa="استوکاستیک", how_en="(close − lowN)/(highN − lowN).", how_fa="(بسته − کف N)/(سقف N − کف N).",
         read_en="Crosses in <20/>80 zones; stays pinned in strong trends (don't fade).", read_fa="کراس در <۲۰/>۸۰؛ در روند قوی می‌چسبد (خلاف نرو)."),
    dict(key="stoch_rsi", group="Momentum", name_en="Stochastic RSI", name_fa="استوکاستیک RSI", how_en="Stochastic applied to RSI.", how_fa="استوکاستیک روی RSI.",
         read_en="Very sensitive; <0.2 cross up in uptrend = pullback entry.", read_fa="بسیار حساس؛ کراس بالا از <۰.۲ در روند صعودی = ورود پولبک."),
    dict(key="macd", group="Momentum", name_en="MACD", name_fa="MACD", how_en="EMA12 − EMA26, signal EMA9, histogram.", how_fa="EMA12 − EMA26، سیگنال EMA9، هیستوگرام.",
         read_en="Histogram turning = earliest; signal cross = confirm; zero cross = trend.", read_fa="چرخش هیستوگرام زودترین؛ کراس سیگنال تأیید؛ کراس صفر روند."),
    dict(key="ppo", group="Momentum", name_en="Percentage Price Oscillator", name_fa="اسیلاتور درصدی قیمت", how_en="MACD expressed in %.", how_fa="MACD به درصد.",
         read_en="Comparable across symbols — good for ranking/screening.", read_fa="بین نمادها قابل مقایسه — برای رتبه‌بندی خوب."),
    dict(key="cci", group="Momentum", name_en="CCI", name_fa="CCI", how_en="(TP − SMA)/(0.015·mean dev).", how_fa="(TP − SMA)/(0.015·انحراف میانگین).",
         read_en="±100 breakouts = momentum; ±200 extremes = reversal watch.", read_fa="شکست ±۱۰۰ = مومنتوم؛ ±۲۰۰ = مراقب برگشت."),
    dict(key="williams_r", group="Momentum", name_en="Williams %R", name_fa="ویلیامز %R", how_en="Inverted stochastic, −100..0.", how_fa="استوکاستیک معکوس، −۱۰۰..۰.",
         read_en="<−80 oversold, >−20 overbought; Larry Williams' own timing tool.", read_fa="<−۸۰ اشباع فروش، >−۲۰ اشباع خرید؛ ابزار خود لری ویلیامز."),
    dict(key="roc", group="Momentum", name_en="Rate of Change / Momentum", name_fa="نرخ تغییر / مومنتوم", how_en="% change over N bars.", how_fa="درصد تغییر طی N کندل.",
         read_en="12-month ROC>0 = Dual Momentum 'risk-on'.", read_fa="ROC ۱۲ ماهه >۰ = مومنتوم دوگانه «ریسک‌پذیر»."),
    dict(key="cmo", group="Momentum", name_en="Chande Momentum Oscillator", name_fa="اسیلاتور مومنتوم چاند", how_en="(Σup − Σdown)/(Σup + Σdown)·100.", how_fa="(Σصعود − Σنزول)/(Σصعود + Σنزول)·۱۰۰.",
         read_en="±50 extremes; unsmoothed RSI cousin.", read_fa="±۵۰ اشباع؛ خویشاوند نرم‌نشدهٔ RSI."),
    dict(key="ultimate", group="Momentum", name_en="Ultimate Oscillator", name_fa="اسیلاتور نهایی", how_en="Weighted buying pressure over 7/14/28.", how_fa="فشار خرید وزنی روی ۷/۱۴/۲۸.",
         read_en="Bullish divergence below 30 then break above prior high = buy (Williams' rules).", read_fa="واگرایی صعودی زیر ۳۰ سپس شکست سقف قبلی = خرید."),
    dict(key="awesome", group="Momentum", name_en="Awesome Oscillator (Bill Williams)", name_fa="اسیلاتور اوسام", how_en="SMA5 − SMA34 of median price.", how_fa="SMA5 − SMA34 قیمت میانه.",
         read_en="Saucer, zero cross, twin peaks setups.", read_fa="ستاپ‌های نعلبکی، کراس صفر، دو قله."),
    dict(key="accelerator", group="Momentum", name_en="Accelerator Oscillator", name_fa="اسیلاتور شتاب", how_en="AO − SMA5(AO).", how_fa="AO − SMA5(AO).",
         read_en="Acceleration of momentum; color change before AO turns.", read_fa="شتاب مومنتوم؛ تغییر رنگ قبل از چرخش AO."),
    dict(key="fisher", group="Momentum", name_en="Fisher Transform", name_fa="تبدیل فیشر", how_en="Gaussianizes normalized price.", how_fa="قیمت نرمال‌شده را گاوسی می‌کند.",
         read_en="Sharp turning points; cross of trigger at extremes.", read_fa="نقاط چرخش تیز؛ کراس تریگر در اکسترمم‌ها."),
    dict(key="rvi", group="Momentum", name_en="Relative Vigor Index", name_fa="شاخص قدرت نسبی (RVI)", how_en="(close − open)/(high − low) smoothed.", how_fa="(بسته − باز)/(سقف − کف) نرم‌شده.",
         read_en="Signal cross; confirms candle conviction.", read_fa="کراس سیگنال؛ قاطعیت کندل را تأیید می‌کند."),
    dict(key="connors_rsi", group="Momentum", name_en="Connors RSI", name_fa="RSI کانرز", how_en="Avg of RSI(3), streak RSI(2), percent-rank(100).", how_fa="میانگین RSI(3)، RSI استریک، رتبهٔ درصدی.",
         read_en="<10 = short-term dip buy in uptrend; >90 = exit.", read_fa="<۱۰ = خرید دیپ کوتاه‌مدت در روند صعودی؛ >۹۰ = خروج."),
    dict(key="qqe", group="Momentum", name_en="QQE (Quantitative Qualitative Estimation)", name_fa="QQE", how_en="Smoothed RSI with ATR-like trailing band.", how_fa="RSI نرم‌شده با باند تریلینگ شبه ATR.",
         read_en="RSI-MA crossing its fast band = signal; very popular TradingView script.", read_fa="کراس RSI-MA با باند سریع = سیگنال؛ اسکریپت بسیار محبوب."),
    dict(key="squeeze", group="Volatility", name_en="Squeeze Momentum (LazyBear / TTM)", name_fa="مومنتوم اسکوییز", how_en="BB inside Keltner = squeeze; linreg momentum.", how_fa="بولینگر داخل کلتنر = اسکوییز؛ مومنتوم رگرسیونی.",
         read_en="First bar squeeze releases in direction of momentum = breakout entry.", read_fa="اولین کندل آزاد شدن اسکوییز در جهت مومنتوم = ورود شکست."),
    dict(key="elder_ray", group="Momentum", name_en="Elder Ray (Bull/Bear Power)", name_fa="الدر ری", how_en="High − EMA13, Low − EMA13.", how_fa="سقف − EMA13، کف − EMA13.",
         read_en="Buy when EMA rising & bear power negative but rising.", read_fa="خرید وقتی EMA صعودی و Bear Power منفی ولی صعودی."),
    # Volatility
    dict(key="atr", group="Volatility", name_en="Average True Range", name_fa="ATR", how_en="Wilder mean of true range.", how_fa="میانگین وایلدر از دامنهٔ واقعی.",
         read_en="Position sizing & stops (1.5–3×ATR). Rising ATR = expansion.", read_fa="اندازهٔ پوزیشن و استاپ (۱.۵–۳×ATR). ATR صعودی = انبساط."),
    dict(key="bollinger", group="Volatility", name_en="Bollinger Bands / %B / Bandwidth", name_fa="باند بولینگر / %B / پهنا", how_en="SMA20 ± 2σ.", how_fa="SMA20 ± 2σ.",
         read_en="Bandwidth lows = squeeze; %B>1 walking the band in trend; touches fade only in range.", read_fa="پهنای کم = اسکوییز؛ %B>۱ راه رفتن روی باند در روند؛ برخوردها فقط در رنج معکوس."),
    dict(key="keltner", group="Volatility", name_en="Keltner Channel", name_fa="کانال کلتنر", how_en="EMA20 ± 1.5·ATR.", how_fa="EMA20 ± 1.5·ATR.",
         read_en="Closes outside = strong momentum (unlike BB, don't fade).", read_fa="بسته شدن بیرون = مومنتوم قوی (برخلاف BB، خلاف نرو)."),
    dict(key="donchian", group="Volatility", name_en="Donchian Channel", name_fa="کانال دانچین", how_en="N-bar high/low.", how_fa="سقف/کف N کندل.",
         read_en="Turtle breakout 20/55; width = volatility.", read_fa="شکست لاک‌پشتی ۲۰/۵۵؛ پهنا = نوسان."),
    dict(key="hist_vol", group="Volatility", name_en="Historical Volatility", name_fa="نوسان تاریخی", how_en="Annualized σ of log returns.", how_fa="σ سالانهٔ بازده لگاریتمی.",
         read_en="Low percentile = expansion ahead; use for regime & options.", read_fa="صدک پایین = انبساط در پیش؛ برای رژیم و آپشن."),
    dict(key="mass_index", group="Volatility", name_en="Mass Index", name_fa="شاخص مس", how_en="Σ25 of EMA9(range)/EMA9(EMA9(range)).", how_fa="Σ25 از EMA9(دامنه)/EMA9(EMA9(دامنه)).",
         read_en="Reversal bulge: >27 then <26.5 = trend reversal likely.", read_fa="برآمدگی برگشت: >۲۷ سپس <۲۶.۵ = احتمال برگشت روند."),
    dict(key="zscore", group="Volatility", name_en="Z-Score", name_fa="نمرهٔ Z", how_en="(price − mean)/σ.", how_fa="(قیمت − میانگین)/σ.",
         read_en="±2 = statistically stretched; pairs/mean-reversion staple.", read_fa="±۲ = کشیدگی آماری؛ پایهٔ معاملات جفتی/بازگشتی."),
    # Volume
    dict(key="obv", group="Volume", name_en="On-Balance Volume", name_fa="حجم تعادلی (OBV)", how_en="Cumulative ±volume by close direction.", how_fa="حجم تجمعی ± بر اساس جهت بسته.",
         read_en="OBV new high before price = accumulation; divergence = warning.", read_fa="سقف جدید OBV قبل از قیمت = انباشت؛ واگرایی = هشدار."),
    dict(key="ad_line", group="Volume", name_en="Accumulation/Distribution", name_fa="انباشت/توزیع", how_en="Σ CLV·volume.", how_fa="Σ CLV·حجم.",
         read_en="Like OBV but uses close location in range.", read_fa="مثل OBV ولی با جایگاه بسته در دامنه."),
    dict(key="chaikin_osc", group="Volume", name_en="Chaikin Oscillator", name_fa="اسیلاتور چایکین", how_en="EMA3 − EMA10 of A/D.", how_fa="EMA3 − EMA10 از A/D.",
         read_en="Zero cross confirms money flow shifts.", read_fa="کراس صفر تغییر جریان پول را تأیید می‌کند."),
    dict(key="cmf", group="Volume", name_en="Chaikin Money Flow", name_fa="جریان پول چایکین", how_en="Σ20 CLV·vol / Σ20 vol.", how_fa="Σ20 CLV·حجم / Σ20 حجم.",
         read_en=">0.1 buying pressure, <−0.1 selling.", read_fa=">۰.۱ فشار خرید، <−۰.۱ فروش."),
    dict(key="mfi", group="Volume", name_en="Money Flow Index", name_fa="شاخص جریان پول", how_en="Volume-weighted RSI.", how_fa="RSI وزن‌دار با حجم.",
         read_en="<20/>80; divergence stronger than RSI's.", read_fa="<۲۰/>۸۰؛ واگرایی‌اش قوی‌تر از RSI."),
    dict(key="force_index", group="Volume", name_en="Force Index (Elder)", name_fa="شاخص نیرو (الدر)", how_en="EMA13 of Δclose·volume.", how_fa="EMA13 از Δبسته·حجم.",
         read_en="2-day FI<0 in uptrend = buy pullback (Elder).", read_fa="FI دو روزه <۰ در روند صعودی = خرید پولبک."),
    dict(key="eom", group="Volume", name_en="Ease of Movement", name_fa="سهولت حرکت", how_en="Mid move / (volume / range).", how_fa="حرکت میانه / (حجم / دامنه).",
         read_en="Positive & rising = price advancing on light volume easily.", read_fa="مثبت و صعودی = قیمت با حجم کم راحت بالا می‌رود."),
    dict(key="vpt", group="Volume", name_en="Volume Price Trend", name_fa="روند قیمت-حجم", how_en="Σ volume·%change.", how_fa="Σ حجم·درصد تغییر.",
         read_en="OBV variant weighted by move size.", read_fa="نسخهٔ OBV وزن‌دار با اندازهٔ حرکت."),
    dict(key="nvi_pvi", group="Volume", name_en="Negative / Positive Volume Index", name_fa="شاخص حجم منفی/مثبت", how_en="Price change accumulated only on lower/higher volume days.", how_fa="تغییر قیمت فقط در روزهای حجم کمتر/بیشتر.",
         read_en="NVI above its 255-EMA = 'smart money' bull market (Fosback).", read_fa="NVI بالای EMA255 = بازار گاوی «پول هوشمند» (فاسبک)."),
    dict(key="klinger", group="Volume", name_en="Klinger Volume Oscillator", name_fa="اسیلاتور حجم کلینگر", how_en="EMA34 − EMA55 of volume force.", how_fa="EMA34 − EMA55 نیروی حجم.",
         read_en="Signal-line cross in trend direction.", read_fa="کراس خط سیگنال در جهت روند."),
    dict(key="relative_volume", group="Volume", name_en="Relative Volume (RVOL)", name_fa="حجم نسبی", how_en="Volume / 20-bar average.", how_fa="حجم / میانگین ۲۰ کندل.",
         read_en=">2 on breakout = institutional participation; <0.5 = ignore breakout.", read_fa=">۲ در شکست = مشارکت نهادی؛ <۰.۵ = شکست را نادیده بگیر."),
    dict(key="vwap", group="Volume", name_en="VWAP", name_fa="VWAP", how_en="Σ price·vol / Σ vol (session).", how_fa="Σ قیمت·حجم / Σ حجم (جلسه).",
         read_en="Institutional benchmark; above = buyers in control; reclaim = long.", read_fa="معیار نهادی؛ بالای آن = کنترل خریداران؛ بازپس‌گیری = خرید."),
    dict(key="volume_profile", group="Volume", name_en="Volume Profile (POC / Value Area)", name_fa="پروفایل حجم (POC / ناحیهٔ ارزش)", how_en="Volume by price bins; POC = max; VA = 70%.", how_fa="حجم به تفکیک قیمت؛ POC = بیشینه؛ VA = ۷۰٪.",
         read_en="POC = magnet/support; VA edges = fade zones; low-volume nodes = fast moves.", read_fa="POC = آهنربا/حمایت؛ لبه‌های VA = نواحی معکوس؛ گره‌های کم‌حجم = حرکت سریع."),
    # Structure / levels
    dict(key="pivots", group="Levels", name_en="Pivot Points (Classic/Fib/Camarilla/Woodie)", name_fa="پیوت‌ها (کلاسیک/فیبو/کاماریلا/وودی)", how_en="Levels from previous H/L/C.", how_fa="سطوح از سقف/کف/بستهٔ قبلی.",
         read_en="Intraday S/R; Camarilla R3/S3 fade, R4/S4 breakout.", read_fa="حمایت/مقاومت روزانه؛ کاماریلا R3/S3 معکوس، R4/S4 شکست."),
    dict(key="fibonacci", group="Levels", name_en="Fibonacci Retracement/Extension", name_fa="فیبوناچی", how_en="38.2/50/61.8/78.6 of swing; 127/161.8 ext.", how_fa="۳۸.۲/۵۰/۶۱.۸/۷۸.۶ سوئینگ؛ ۱۲۷/۱۶۱.۸ اکستنشن.",
         read_en="Golden pocket 61.8–65 in trend = entry; extensions = targets.", read_fa="گلدن پاکت ۶۱.۸–۶۵ در روند = ورود؛ اکستنشن = هدف."),
    dict(key="zigzag", group="Levels", name_en="ZigZag", name_fa="زیگزاگ", how_en="Connects swings > X% reversal.", how_fa="سوئینگ‌های با برگشت > X٪ را وصل می‌کند.",
         read_en="Structure (HH/HL), Elliott counting, harmonic legs. Repaints last leg!", read_fa="ساختار (HH/HL)، شمارش الیوت، پاهای هارمونیک. پای آخر ری‌پینت می‌شود!"),
    dict(key="heikin_ashi", group="Levels", name_en="Heikin Ashi", name_fa="هیکن آشی", how_en="Averaged candles.", how_fa="کندل‌های میانگین‌گیری‌شده.",
         read_en="Long bodies no lower wick = strong trend; dojis = pause. Never place stops on HA prices.", read_fa="بدنهٔ بلند بدون سایهٔ پایین = روند قوی؛ دوجی = مکث. استاپ روی قیمت HA نگذارید."),
    dict(key="rs_vs", group="Levels", name_en="Relative Strength vs Benchmark", name_fa="قدرت نسبی در برابر معیار", how_en="Ratio momentum vs BTC/SPX.", how_fa="مومنتوم نسبت به BTC/SPX.",
         read_en="Buy leaders (RS rising) on market pullbacks; avoid laggards.", read_fa="در پولبک بازار، لیدرها (RS صعودی) را بخر؛ از عقب‌مانده‌ها دوری کن."),
]


def catalog_groups():
    return sorted({d["group"] for d in INDICATOR_CATALOG}, key=lambda g: ["Trend", "Momentum", "Volatility", "Volume", "Cycle", "Levels"].index(g))
