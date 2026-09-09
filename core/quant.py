"""
Quant toolkit — Ernie Chan (Algorithmic / Quantitative / Machine Trading) + Marcos López de Prado (AFML)
+ Kevin Davey (Building Winning Algorithmic Trading Systems).

Chan:      ADF stationarity test (no statsmodels; OLS + MacKinnon critical values), Hurst exponent, half-life of
           mean reversion (Ornstein-Uhlenbeck), Engle-Granger cointegration for pairs, Bollinger z-score pairs signal,
           Kelly with covariance.
de Prado:  CUSUM event filter, fractional differentiation (fixed-width window), bet sizing from probabilities,
           Deflated Sharpe Ratio (multiple-testing-corrected), Probability of Backtest Overfitting (CSCV).
Davey:     Walk-Forward Efficiency, Monte-Carlo "incubation" pass criteria.
"""
import math
import numpy as np
import pandas as pd
from itertools import combinations

# ------------------------------------------------------------------ Chan: stationarity & mean reversion
_ADF_CV = {"1%": -3.43, "5%": -2.86, "10%": -2.57}   # MacKinnon, constant, large n


def adf_test(x, lags=1):
    """Augmented Dickey-Fuller (constant, no trend). Returns dict(stat, pvalue_approx, stationary_5pct)."""
    x = np.asarray(pd.Series(x).dropna(), float)
    dx = np.diff(x)
    n = len(dx) - lags
    if n < 30:
        return dict(stat=0.0, stationary=False, cv=_ADF_CV)
    y = dx[lags:]
    X = [np.ones(n), x[lags:-1]]
    for k in range(1, lags + 1):
        X.append(dx[lags - k:-k])
    X = np.column_stack(X)
    beta, res, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    s2 = resid @ resid / (n - X.shape[1])
    cov = s2 * np.linalg.inv(X.T @ X)
    stat = beta[1] / math.sqrt(cov[1, 1])
    return dict(stat=float(stat), stationary=bool(stat < _ADF_CV["5%"]), cv=_ADF_CV,
                strength="strong" if stat < _ADF_CV["1%"] else ("ok" if stat < _ADF_CV["5%"] else ("weak" if stat < _ADF_CV["10%"] else "none")))


def hurst(x, max_lag=100):
    """Hurst exponent by variance of lagged differences. <0.5 mean-reverting, ≈0.5 random walk, >0.5 trending."""
    x = np.asarray(pd.Series(x).dropna(), float)
    if len(x) < max_lag * 2:
        max_lag = max(10, len(x) // 4)
    lags = range(2, max_lag)
    tau = [np.std(x[l:] - x[:-l]) for l in lags]
    tau = np.array(tau)
    ok = tau > 0
    if ok.sum() < 5:
        return 0.5
    return float(np.polyfit(np.log(np.array(list(lags))[ok]), np.log(tau[ok]), 1)[0])


def half_life(x):
    """OU half-life in bars: regress Δx on x_{t-1}; hl = -ln2/λ."""
    x = pd.Series(x).dropna()
    lag = x.shift(1).dropna()
    dx = x.diff().dropna()
    lag, dx = lag.align(dx, join="inner")
    X = np.column_stack([np.ones(len(lag)), lag.values])
    beta = np.linalg.lstsq(X, dx.values, rcond=None)[0]
    lam = beta[1]
    if lam >= 0:
        return float("inf")
    return float(-math.log(2) / lam)


def hedge_ratio(y, x):
    """OLS hedge ratio y = a + b x."""
    X = np.column_stack([np.ones(len(x)), np.asarray(x, float)])
    return float(np.linalg.lstsq(X, np.asarray(y, float), rcond=None)[0][1])


def cointegration(y, x):
    """Engle–Granger: spread = y − β x; ADF on spread. Returns dict(beta, adf, half_life, hurst, spread)."""
    y, x = pd.Series(y).astype(float), pd.Series(x).astype(float)
    y, x = y.align(x, join="inner")
    b = hedge_ratio(y.values, x.values)
    spread = y - b * x
    a = adf_test(spread.values)
    return dict(beta=b, adf_stat=a["stat"], cointegrated=a["stationary"], strength=a["strength"],
                half_life=half_life(spread), hurst=hurst(spread.values), spread=spread)


def zscore_signal(spread, window=None, entry=2.0, exit_=0.5):
    """Bollinger-band pairs signal on the spread (Chan ch.3): +1 long spread (buy y sell x), −1 short, 0 flat."""
    spread = pd.Series(spread)
    w = int(window or max(10, min(100, half_life(spread) * 2 if np.isfinite(half_life(spread)) else 30)))
    z = (spread - spread.rolling(w).mean()) / spread.rolling(w).std()
    pos = pd.Series(0, index=spread.index)
    cur = 0
    for i, v in enumerate(z.values):
        if np.isnan(v):
            continue
        if cur == 0:
            if v < -entry:
                cur = 1
            elif v > entry:
                cur = -1
        elif cur == 1 and v > -exit_:
            cur = 0
        elif cur == -1 and v < exit_:
            cur = 0
        pos.iloc[i] = cur
    return z, pos, w


def scan_pairs(price_dict, min_bars=250):
    """Try every pair; return rows sorted by ADF strength (Chan's pair screening)."""
    rows = []
    for a, b in combinations(sorted(price_dict), 2):
        pa, pb = price_dict[a], price_dict[b]
        idx = pa.index.intersection(pb.index)
        if len(idx) < min_bars:
            continue
        c = cointegration(np.log(pa.loc[idx]), np.log(pb.loc[idx]))
        z, pos, w = zscore_signal(c["spread"])
        rows.append(dict(a=a, b=b, beta=c["beta"], adf=c["adf_stat"], coint=c["cointegrated"], strength=c["strength"],
                         half_life=c["half_life"], hurst=c["hurst"], z=float(z.iloc[-1]) if len(z) else float("nan"),
                         signal=int(pos.iloc[-1]), window=w, n=len(idx)))
    rows.sort(key=lambda r: r["adf"])
    return rows


def kelly_multi(returns: pd.DataFrame, risk_free=0.0):
    """Chan ch.6: optimal leverage vector f = C⁻¹ (μ − r). Returns f and its half."""
    mu = returns.mean().values - risk_free
    C = np.cov(returns.values.T)
    try:
        f = np.linalg.solve(C, mu)
    except np.linalg.LinAlgError:
        f = mu / np.diag(C)
    return pd.Series(f, index=returns.columns), pd.Series(f / 2, index=returns.columns)


# ------------------------------------------------------------------ de Prado
def cusum_filter(close, threshold):
    """Symmetric CUSUM filter (AFML 2.5.2.1): event timestamps where cumulative log-return exceeds threshold."""
    c = pd.Series(close).astype(float)
    r = np.log(c).diff().dropna()
    s_pos = s_neg = 0.0
    events = []
    for t, v in r.items():
        s_pos = max(0.0, s_pos + v)
        s_neg = min(0.0, s_neg + v)
        if s_neg < -threshold:
            s_neg = 0.0; events.append(t)
        elif s_pos > threshold:
            s_pos = 0.0; events.append(t)
    return pd.DatetimeIndex(events)


def frac_diff_weights(d, thresh=1e-4):
    w = [1.0]
    k = 1
    while True:
        w_ = -w[-1] / k * (d - k + 1)
        if abs(w_) < thresh:
            break
        w.append(w_); k += 1
    return np.array(w[::-1])


def frac_diff(series, d=0.4, thresh=1e-4):
    """Fixed-width-window fractional differentiation (AFML ch.5): stationary but memory-preserving."""
    s = pd.Series(series).astype(float)
    w = frac_diff_weights(d, thresh)
    width = len(w)
    out = pd.Series(np.nan, index=s.index)
    vals = s.values
    for i in range(width - 1, len(s)):
        out.iloc[i] = np.dot(w, vals[i - width + 1:i + 1])
    return out


def min_ffd(series, ds=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0)):
    """Smallest d that passes ADF at 5% (AFML 5.6)."""
    rows = []
    for d in ds:
        fd = frac_diff(np.log(series), d).dropna()
        if len(fd) < 50:
            continue
        a = adf_test(fd.values)
        corr = float(np.corrcoef(fd.values, np.log(series).loc[fd.index].values)[0, 1])
        rows.append(dict(d=d, adf=a["stat"], stationary=a["stationary"], corr_with_price=corr))
    best = next((r for r in rows if r["stationary"]), None)
    return rows, best


def bet_size(prob, n_classes=2):
    """AFML 10.3: size from predicted probability via z = (p − 1/K)/sqrt(p(1−p)); size = 2Φ(z) − 1."""
    from statistics import NormalDist
    p = np.clip(np.asarray(prob, float), 1e-6, 1 - 1e-6)
    z = (p - 1 / n_classes) / np.sqrt(p * (1 - p))
    return 2 * np.array([NormalDist().cdf(v) for v in z]) - 1


def sharpe(returns, periods=252):
    r = np.asarray(returns, float)
    return float(r.mean() / r.std(ddof=1) * math.sqrt(periods)) if len(r) > 2 and r.std(ddof=1) > 0 else 0.0


def deflated_sharpe(sr_observed, n_trials, n_obs, skew=0.0, kurt=3.0, sr_var=None, periods=252):
    """Bailey & López de Prado (2014). Returns dict(dsr_prob, sr0): probability the observed SR beats the
    expected max SR of `n_trials` random strategies. sr in per-period units (we convert from annualised)."""
    from statistics import NormalDist
    if n_trials < 1 or n_obs < 10:
        return dict(dsr=0.0, sr0=0.0)
    sr = sr_observed / math.sqrt(periods)
    v = sr_var if sr_var is not None else (1.0 / periods)  # variance of trial SRs (unknown → assume 1 ann. SR unit)
    em = 0.5772156649
    N = NormalDist()
    sr0 = math.sqrt(v) * ((1 - em) * N.inv_cdf(1 - 1 / n_trials) + em * N.inv_cdf(1 - 1 / (n_trials * math.e)))
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr * sr))
    z = (sr - sr0) * math.sqrt(n_obs - 1) / denom
    return dict(dsr=float(N.cdf(z)), sr0=float(sr0 * math.sqrt(periods)))


def pbo_cscv(returns_matrix: np.ndarray, n_splits=8):
    """Probability of Backtest Overfitting via Combinatorially Symmetric Cross-Validation (Bailey et al. 2015).
    returns_matrix: T × N (periods × strategy variants). Returns PBO in 0..1 (>0.5 = likely overfit)."""
    T, N = returns_matrix.shape
    if N < 2 or T < n_splits * 10:
        return float("nan")
    S = n_splits if n_splits % 2 == 0 else n_splits + 1
    blocks = np.array_split(np.arange(T), S)
    logits = []
    for train_idx in combinations(range(S), S // 2):
        tr = np.concatenate([blocks[i] for i in train_idx])
        te = np.concatenate([blocks[i] for i in range(S) if i not in train_idx])
        def _sr(m):
            mu, sd = m.mean(0), m.std(0, ddof=1) + 1e-12
            return mu / sd
        best = int(np.argmax(_sr(returns_matrix[tr])))
        rank_oos = (np.argsort(np.argsort(_sr(returns_matrix[te])))[best] + 1) / (N + 1)
        logits.append(math.log(rank_oos / (1 - rank_oos)))
    logits = np.array(logits)
    return float((logits <= 0).mean())


# ------------------------------------------------------------------ Davey
def walk_forward_efficiency(is_annual_return, oos_annual_return):
    """Davey: WFE = OOS return / IS return; ≥ 50% is a pass."""
    if is_annual_return <= 0:
        return 0.0
    return float(oos_annual_return / is_annual_return)


def trial_sr_variance(periods=252):
    """Variance of per-period Sharpe across the playbook's tested strategy×tf×group trials (de Prado uses the trials'
    own dispersion). Falls back to a modest 0.5 annual-SR std if playbook is absent."""
    try:
        from core import playbook as PB
        pb = PB.load()
        srs = []
        for tf, gd in pb["table"].items():
            for g, sd in gd.items():
                for st in sd.values():
                    if st.get("n", 0) >= 20 and st.get("hold"):
                        # approx annualised SR from expectancy/σ: exp per trade & payoff → crude per-trade t / sqrt(n) scaling
                        srs.append(st.get("t", 0) / math.sqrt(max(st["n"], 1)) * math.sqrt(periods / max(st["hold"], 1)))
        if len(srs) >= 30:
            sd = min(float(np.std(srs)), 1.0)   # cap: trials are heavily correlated, raw dispersion overstates independent spread
            return sd * sd / periods
    except Exception:
        pass
    return 0.25 / periods


def davey_incubation(stats, mc_dd95_pct, wfe, min_trades=30, biggest_trade_share=0.0):
    """Davey's go/no-go checklist for a system before live 'incubation'."""
    checks = {
        "trades ≥ 30": stats.get("trades", 0) >= min_trades,
        "profit factor > 1.2": stats.get("profit_factor", 0) > 1.2,
        "OOS/IS efficiency ≥ 0.5": wfe >= 0.5,
        "MC 95% drawdown < 25%": mc_dd95_pct < 25,
        "return/drawdown ≥ 2": (stats.get("return_pct", 0) / max(stats.get("max_dd_pct", 1e-9), 1e-9)) >= 2,
        "no single trade > 20% of net": biggest_trade_share <= 0.2 or stats.get("net_profit", 0) <= 0,
    }
    return checks, all(checks.values())


# ---------------------------------------------------------------------------------------------------------------
# Phase 23 unified entry point: everything from core.quant2 (the Phase-12/13 extension set) is also reachable from this
# module, so callers only need one import path. Resolved lazily (PEP 562) to stay import-order safe: core.quant2
# itself imports this module, so an eager re-export would see a half-initialised module.
def __getattr__(name):
    if name.startswith("_"):
        raise AttributeError(name)
    import importlib
    m = importlib.import_module("core.quant2")
    try:
        return getattr(m, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


def __dir__():
    import importlib
    return sorted(set(globals()) | {k for k in dir(importlib.import_module("core.quant2")) if not k.startswith("_")})
