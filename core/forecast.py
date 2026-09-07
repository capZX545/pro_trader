"""
Time-series forecasting desk (Phase 11 — Prophet / Kats / Darts / PyTorch-Forecasting / GluonTS / NeuralProphet / sktime).

What each library taught us, and what is implemented here (dependency-free, numpy + sklearn):

  Prophet / NeuralProphet  → decomposable model  y = trend(piecewise-linear w/ changepoints) + seasonality(Fourier) + noise,
                             with uncertainty from residual/changepoint simulation.           → `prophet_like()`
  sktime / Kats            → classical baselines that regularly beat deep nets on finance: Naive, Drift, Theta, SES/Holt
                             (ETS), plus Kats-style changepoint detection (CUSUM) & "backtesting by sliding window".
                                                                                                → `theta()`, `holt()`, `naive()`, `drift()`
  Darts / PyTorch-Forecasting → global "N-BEATS"-style windowed regressor (lags → horizon, MLP), multi-step direct
                             forecasting, and *historical forecasts* (expanding-window backtest).  → `nbeats_like()`, `historical_forecasts()`
  GluonTS / DeepAR         → probabilistic outputs (quantiles instead of a point) & scoring by CRPS / pinball loss.
                                                                                                → `quantile_forecast()`, `pinball()`
  All                      → the honest part: compare every model with the naive random-walk on log-returns using
                             walk-forward MASE/direction-accuracy. In liquid markets most models ≈ naive; the desk shows it.

Nothing here claims to predict price. It measures whether a forecaster carries *any* information beyond noise.
"""
import numpy as np
import pandas as pd


# ------------------------------------------------------------------ baselines (sktime-style)
def naive(y, h):
    return np.repeat(y[-1], h)


def drift(y, h):
    slope = (y[-1] - y[0]) / max(len(y) - 1, 1)
    return y[-1] + slope * np.arange(1, h + 1)


def ses(y, h, alpha=None):
    """simple exponential smoothing with alpha fitted by SSE grid"""
    if alpha is None:
        best, alpha = np.inf, 0.3
        for a in np.linspace(0.05, 0.95, 19):
            l = y[0]; sse = 0.0
            for v in y[1:]:
                sse += (v - l) ** 2; l = a * v + (1 - a) * l
            if sse < best:
                best, alpha = sse, a
    l = y[0]
    for v in y[1:]:
        l = alpha * v + (1 - alpha) * l
    return np.repeat(l, h)


def holt(y, h, alpha=0.5, beta=0.1, damped=0.9):
    """Holt linear trend, damped (ETS(A,Ad,N)) — sktime's default robust trend model"""
    l, b = y[0], y[1] - y[0]
    for v in y[1:]:
        l_new = alpha * v + (1 - alpha) * (l + damped * b)
        b = beta * (l_new - l) + (1 - beta) * damped * b
        l = l_new
    phis = np.cumsum(damped ** np.arange(1, h + 1))
    return l + phis * b


def theta(y, h):
    """Theta method (Assimakopoulos & Nikolopoulos) — M3 winner, sktime ThetaForecaster: SES on theta=2 line + drift"""
    n = len(y)
    x = np.arange(n)
    b, a = np.polyfit(x, y, 1)
    theta2 = 2 * y - (a + b * x)  # theta line with theta=2
    f_ses = ses(theta2, h)
    f_lin = a + b * np.arange(n, n + h)
    return 0.5 * (f_ses + f_lin)


# ------------------------------------------------------------------ Prophet-like decomposable model
def _fourier(t, period, K):
    cols = []
    for k in range(1, K + 1):
        cols.append(np.sin(2 * np.pi * k * t / period)); cols.append(np.cos(2 * np.pi * k * t / period))
    return np.column_stack(cols) if cols else np.zeros((len(t), 0))


def prophet_like(y, h, n_changepoints=15, changepoint_range=0.8, seasonal_periods=(), fourier_k=3, ridge=1.0, n_sims=200, seed=0, anchor_last=True):
    """
    y = k*t + m + Σ δ_j (t - s_j)_+  (piecewise linear trend)  + Fourier seasonality ; fitted by ridge regression
    (Prophet uses MAP with Laplace prior on δ ≈ L1; ridge is the closed-form stand-in). Uncertainty: Prophet's own
    recipe — future changepoints drawn with the historical rate & magnitude of δ, plus residual noise.
    returns dict(yhat, lo, hi, trend, changepoints, delta)
    """
    y = np.asarray(y, float); n = len(y); t = np.arange(n, dtype=float)
    cps = np.linspace(0, int(n * changepoint_range), n_changepoints + 2)[1:-1].astype(int) if n_changepoints else np.array([], int)
    def design(tt):
        cols = [tt, np.ones_like(tt)]
        for s in cps:
            cols.append(np.clip(tt - s, 0, None))
        X = np.column_stack(cols)
        for p in seasonal_periods:
            X = np.hstack([X, _fourier(tt, p, fourier_k)])
        return X
    X = design(t)
    # scale-aware ridge (don't shrink slope/intercept)
    lam = np.full(X.shape[1], ridge); lam[:2] = 0.0
    A = X.T @ X + np.diag(lam) * n
    beta = np.linalg.solve(A, X.T @ y)
    fitted = X @ beta
    resid = y - fitted
    tf = np.arange(n, n + h, dtype=float)
    Xf = design(tf)
    yhat = Xf @ beta
    # Prophet's known failure mode on prices: the last trend segment is extrapolated forever. We damp the slope beyond
    # the horizon (Holt-style φ=0.9) — closer to what practitioners do when they use Prophet on markets.
    k_last = beta[0] + float(np.sum(beta[2:2 + len(cps)]))
    damp = 0.9 ** np.arange(1, h + 1)
    yhat = yhat - k_last * np.arange(1, h + 1) + k_last * np.cumsum(damp)
    if anchor_last:
        # Prophet fits the mean path, so the forecast starts from the trend line, not from the last price (a well-known
        # source of huge errors on random-walk-like series). Anchoring shifts the path by the last residual (decaying).
        gap = y[-1] - fitted[-1]
        yhat = yhat + gap * (0.97 ** np.arange(1, h + 1))
    delta = beta[2:2 + len(cps)]
    # uncertainty simulation (Prophet style)
    rng = np.random.default_rng(seed)
    sims = np.zeros((n_sims, h))
    lam_cp = len(cps) / max(n * changepoint_range, 1)     # changepoints per bar
    scale = np.mean(np.abs(delta)) if len(delta) else 0.0
    sigma = resid.std(ddof=1) if n > 3 else 0.0
    for s in range(n_sims):
        k_extra = np.zeros(h)
        n_new = rng.poisson(lam_cp * h)
        for _ in range(n_new):
            pos = rng.integers(0, h); d = rng.laplace(0, scale) if scale > 0 else 0.0
            k_extra[pos:] += d * (np.arange(pos, h) - pos + 1)
        sims[s] = yhat + k_extra + rng.normal(0, sigma, h)
    lo, hi = np.percentile(sims, 10, axis=0), np.percentile(sims, 90, axis=0)
    trend_f = Xf[:, :2 + len(cps)] @ beta[:2 + len(cps)]
    return dict(yhat=yhat, lo=lo, hi=hi, trend=trend_f, changepoints=cps, delta=delta, fitted=fitted, sigma=sigma)


# ------------------------------------------------------------------ N-BEATS-like global windowed model
def _windows(y, lookback, horizon):
    Xs, Ys = [], []
    for i in range(lookback, len(y) - horizon + 1):
        Xs.append(y[i - lookback:i]); Ys.append(y[i:i + horizon])
    return np.array(Xs), np.array(Ys)


def nbeats_like(y, h, lookback=None, hidden=(64, 64), max_iter=300, seed=0, model="mlp"):
    """
    N-BEATS in spirit: a fully-connected network maps the last `lookback` values (normalised per window — this is
    N-BEATS' 'backcast normalisation' that makes it work on non-stationary series) directly to the next `h` values
    (direct multi-step, as in Darts/PyTorch-Forecasting). `model='ridge'` gives the linear analogue (a strong baseline).
    Trained on log-returns implicitly by predicting window-relative differences.
    """
    y = np.asarray(y, float); n = len(y)
    lookback = lookback or max(2 * h, 20)
    if n < lookback + h + 30:
        return np.repeat(y[-1], h)
    X, Y = _windows(y, lookback, h)
    last = X[:, -1:]
    Xn = X - last; Yn = Y - last
    scale = np.std(Xn, axis=1, keepdims=True) + 1e-9
    Xn = Xn / scale; Yn = Yn / scale
    if model == "ridge":
        from sklearn.linear_model import Ridge
        m = Ridge(alpha=1.0).fit(Xn, Yn)
    else:
        from sklearn.neural_network import MLPRegressor
        m = MLPRegressor(hidden_layer_sizes=hidden, max_iter=max_iter, random_state=seed, early_stopping=True, n_iter_no_change=15, alpha=1e-3)
        m.fit(Xn, Yn)
    xq = y[-lookback:]; lq = xq[-1]; sq = np.std(xq - lq) + 1e-9
    pred = m.predict(((xq - lq) / sq)[None, :])[0]
    return lq + pred * sq


# ------------------------------------------------------------------ probabilistic (GluonTS/DeepAR-style) via quantile regression on windows
def quantile_forecast(y, h, quantiles=(0.1, 0.5, 0.9), lookback=None):
    """Gradient-boosted quantile regressors on window features → q10/q50/q90 for step 1..h (direct)."""
    from sklearn.ensemble import GradientBoostingRegressor
    y = np.asarray(y, float); n = len(y)
    lookback = lookback or max(2 * h, 20)
    if n < lookback + h + 60:
        return {q: np.repeat(y[-1], h) for q in quantiles}
    X, Y = _windows(y, lookback, h)
    last = X[:, -1:]; scale = np.std(X - last, axis=1, keepdims=True) + 1e-9
    Xn = (X - last) / scale; Yn = (Y - last) / scale
    xq = y[-lookback:]; lq = xq[-1]; sq = np.std(xq - lq) + 1e-9
    out = {q: np.zeros(h) for q in quantiles}
    steps = sorted(set([0, h // 2, h - 1]))  # fit a few horizons & interpolate (speed)
    for q in quantiles:
        vals = []
        for s in steps:
            m = GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=120, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=1)
            m.fit(Xn, Yn[:, s]); vals.append(m.predict(((xq - lq) / sq)[None, :])[0])
        out[q] = lq + np.interp(np.arange(h), steps, vals) * sq
    return out


def pinball(y_true, q_pred, q):
    d = y_true - q_pred
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))


# ------------------------------------------------------------------ Kats-style changepoints (CUSUM on mean)
def cusum_changepoints(y, threshold=8.0, drift=0.5):
    y = np.asarray(y, float); r = np.diff(np.log(np.clip(y, 1e-9, None)))
    if len(r) < 10:
        return []
    z = (r - r.mean()) / (r.std() + 1e-12)
    s_pos = s_neg = 0.0; cps = []
    for i, v in enumerate(z):
        s_pos = max(0.0, s_pos + v - drift); s_neg = min(0.0, s_neg + v + drift)
        if s_pos > threshold:
            cps.append((i + 1, "up")); s_pos = s_neg = 0.0
        elif s_neg < -threshold:
            cps.append((i + 1, "down")); s_pos = s_neg = 0.0
    return cps


# ------------------------------------------------------------------ Darts-style historical forecasts (walk-forward backtest)
MODELS = {
    "naive": lambda y, h: naive(y, h),
    "drift": lambda y, h: drift(y, h),
    "theta": lambda y, h: theta(y, h),
    "holt_damped": lambda y, h: holt(y, h),
    "prophet_like": lambda y, h: prophet_like(y, h, n_sims=1)["yhat"],
    "nbeats_ridge": lambda y, h: nbeats_like(y, h, model="ridge"),
    "nbeats_mlp": lambda y, h: nbeats_like(y, h, model="mlp", max_iter=150),
}


def historical_forecasts(y, h=5, models=None, n_origins=30, min_train=200, stride=None, use_log=True):
    """Expanding-window backtest: at each origin fit on y[:o] and forecast y[o:o+h]. Returns a DataFrame of metrics per
    model: MASE (vs in-sample naive), RMSE, direction accuracy of the h-step move, and 'beats_naive' (MASE ratio)."""
    y = np.asarray(y, float)
    z = np.log(y) if use_log else y
    n = len(z)
    models = models or list(MODELS)
    stride = stride or max(1, (n - min_train - h) // n_origins)
    origins = list(range(min_train, n - h, stride))[-n_origins:]
    if not origins:
        return pd.DataFrame()
    rows = {m: dict(abs_err=[], sq_err=[], dir_ok=[], naive_abs=[]) for m in models}
    for o in origins:
        train, truth = z[:o], z[o:o + h]
        scale = np.mean(np.abs(np.diff(train[-200:])))  # MASE denominator: 1-step naive in-sample MAE
        for m in models:
            try:
                f = MODELS[m](train, h)
            except Exception:
                f = naive(train, h)
            e = truth - f
            rows[m]["abs_err"].append(np.mean(np.abs(e)) / (scale + 1e-12))
            rows[m]["sq_err"].append(np.mean(e ** 2))
            rows[m]["dir_ok"].append(float(np.sign(f[-1] - train[-1]) == np.sign(truth[-1] - train[-1])))
    out = []
    for m in models:
        r = rows[m]
        out.append(dict(model=m, MASE=float(np.mean(r["abs_err"])), RMSE=float(np.sqrt(np.mean(r["sq_err"]))),
                        dir_acc=float(np.mean(r["dir_ok"])), n=len(origins)))
    df = pd.DataFrame(out)
    base = df.loc[df.model == "naive", "MASE"].values
    df["vs_naive"] = df["MASE"] / (base[0] if len(base) else np.nan)
    # binomial p-value for direction accuracy vs 50%
    from math import comb
    def pval(k, n):
        return float(sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n) if n <= 60 else float(0.5 * (1 - np.math.erf((k - n / 2) / np.sqrt(n / 4) / np.sqrt(2))))
    df["dir_pval"] = [pval(int(round(a * n)), n) for a, n in zip(df["dir_acc"], df["n"])]
    return df.sort_values("MASE").reset_index(drop=True)


def forecast_panel(close, h=10, seasonal_periods=()):
    """everything the UI needs for one symbol: point forecasts of each model, prophet band, quantiles, changepoints"""
    y = np.asarray(close, float)
    z = np.log(y)
    out = {"h": h, "last": float(y[-1])}
    fc = {}
    for m in MODELS:
        try:
            fc[m] = np.exp(MODELS[m](z, h))
        except Exception:
            fc[m] = np.exp(naive(z, h))
    out["forecasts"] = fc
    pr = prophet_like(z, h, seasonal_periods=seasonal_periods)
    out["prophet"] = dict(yhat=np.exp(pr["yhat"]), lo=np.exp(pr["lo"]), hi=np.exp(pr["hi"]), changepoints=pr["changepoints"].tolist(), delta=pr["delta"].tolist(), sigma=float(pr["sigma"]))
    q = quantile_forecast(z, h)
    out["quantiles"] = {k: np.exp(v) for k, v in q.items()}
    out["changepoints"] = cusum_changepoints(y)
    return out
