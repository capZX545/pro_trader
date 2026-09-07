"""
ML engine — the bot "learns" from the market.

1. build_features(df): ~90 normalized, stationary features from indicators.py + indicators2.py
   (all scale-free: ratios to price/ATR, oscillators, ranks — so one model transfers across symbols).
2. Label: triple-barrier — did price hit +k·ATR before −k·ATR within H bars? (1 long-win / 0 otherwise);
   also a symmetric short label. Uses forward information ONLY for labels, never for features.
3. Model: HistGradientBoosting (sklearn, no extra deps). Purged walk-forward CV with embargo to avoid leakage.
4. Output: P(long wins), P(short wins) per bar + feature importances (what the bot learned) + reliability
   (out-of-sample accuracy / Brier / lift vs base rate) — shown honestly in the ML page.
5. Also: signal_quality(strategy signals) — P(win) of each strategy signal given market context (meta-labeling, López de Prado).
"""
import os
import json
import time
import pickle
import numpy as np
import pandas as pd

from core import indicators as ta
from core import indicators2 as I2

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from core.paths import data as _data
MODEL_DIR = _data("models")
os.makedirs(MODEL_DIR, exist_ok=True)


# ---------------------------------------------------------------- features
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    c, h, l, o, v = df.close, df.high, df.low, df.open, df.volume
    a = ta.atr(df, 14)
    ap = a / c
    F = pd.DataFrame(index=df.index)
    # returns
    for n in (1, 2, 3, 5, 10, 20, 50):
        F[f"ret_{n}"] = c.pct_change(n) / (ap * np.sqrt(n))
    # MA distances (ATR units)
    for n in (9, 21, 50, 100, 200):
        e = ta.ema(c, n)
        F[f"ema{n}_dist"] = (c - e) / a
        F[f"ema{n}_slope"] = e.pct_change(5) / ap
    F["ema9_21"] = (ta.ema(c, 9) - ta.ema(c, 21)) / a
    F["ema50_200"] = (ta.ema(c, 50) - ta.ema(c, 200)) / a
    F["kama_dist"] = (c - I2.kama(c)) / a
    F["hma_slope"] = ta.hma(c, 21).pct_change(3) / ap
    F["t3_slope"] = I2.t3(c, 8).pct_change(3) / ap
    _, slope = I2.linreg(c, 20)
    F["lr_slope20"] = slope / a
    # oscillators
    F["rsi14"] = ta.rsi(c, 14) / 100
    F["rsi2"] = ta.rsi(c, 2) / 100
    F["rsi_slope"] = ta.rsi(c, 14).diff(3) / 100
    k, d = ta.stochastic(df)[:2]
    F["stoch_k"] = k / 100
    F["stoch_kd"] = (k - d) / 100
    m, s, hist = ta.macd(c)
    F["macd_hist"] = hist / a
    F["macd_hist_d"] = hist.diff() / a
    F["macd_sig"] = (m - s) / a
    F["cci"] = ta.cci(df, 20) / 200
    F["willr"] = ta.williams_r(df) / 100
    F["cmo"] = I2.cmo(c) / 100
    F["ultimate"] = I2.ultimate(df) / 100
    F["ao"] = I2.awesome(df) / a
    F["trix"] = I2.trix(c, 15)
    F["schaff"] = I2.schaff(c) / 100
    F["crsi"] = I2.connors_rsi(c) / 100
    fi, _ = I2.fisher(df)
    F["fisher"] = fi.clip(-5, 5) / 5
    r_, rs_ = I2.rvi(df)
    F["rvi"] = (r_ - rs_).clip(-1, 1)
    F["ppo"] = I2.ppo(c)[0]
    F["dpo"] = I2.dpo(c) / a
    # trend strength / regime
    adx, pdi, mdi = ta.adx(df)
    F["adx"] = adx / 100
    F["di_diff"] = (pdi - mdi) / 100
    F["adx_slope"] = adx.diff(5) / 100
    au, ad_, aosc = I2.aroon(df)
    F["aroon"] = aosc / 100
    vp, vm = I2.vortex(df)
    F["vortex"] = vp - vm
    F["chop"] = I2.choppiness(df) / 100
    F["er"] = I2.efficiency_ratio(c, 10)
    F["hurst"] = I2.hurst(c, 100)
    st_line, st_dir = ta.supertrend(df)[:2] if isinstance(ta.supertrend(df), tuple) else (ta.supertrend(df), None)
    try:
        F["st_dir"] = st_dir.astype(float)
    except Exception:
        F["st_dir"] = np.sign(c - st_line)
    F["psar"] = np.sign(c - ta.parabolic_sar(df))
    ht_dir, _ = I2.halftrend(df)
    F["halftrend"] = ht_dir
    # volatility
    F["atr_pct"] = ap * 100
    F["atr_ratio"] = a / a.rolling(100).mean()
    u, mid, lo = ta.bollinger(c)
    F["bb_pctb"] = (c - lo) / (u - lo).replace(0, np.nan)
    F["bb_width"] = (u - lo) / mid
    F["bb_width_rank"] = I2.percent_rank(F["bb_width"], 100) / 100
    ku, km, kl = ta.keltner(df)
    F["kc_pos"] = (c - km) / (ku - kl).replace(0, np.nan)
    sq_on, sq_val = I2.squeeze_momentum(df)
    F["squeeze_on"] = sq_on.astype(float)
    F["squeeze_mom"] = sq_val / a
    dh, dl = ta.donchian(df, 20)[:2]
    F["donch_pos"] = (c - dl) / (dh - dl).replace(0, np.nan)
    F["hv_rank"] = I2.percent_rank(I2.hist_vol(c), 100) / 100
    F["zscore20"] = I2.zscore(c, 20).clip(-4, 4)
    F["mass"] = I2.mass_index(df) / 27
    # volume
    has_vol = v.sum() > 0
    if has_vol:
        F["rvol"] = I2.relative_volume(df).clip(0, 5)
        F["mfi"] = ta.mfi(df) / 100
        F["cmf"] = ta.cmf(df)
        F["obv_slope"] = ta.obv(df).diff(10) / (v.rolling(10).sum().replace(0, np.nan))
        F["force"] = I2.force_index(df) / (a * v.rolling(13).mean().replace(0, np.nan))
        F["eom"] = I2.eom(df).clip(-3, 3)
        F["chaikin"] = I2.chaikin_osc(df) / v.rolling(20).mean().replace(0, np.nan)
        F["vwma_dist"] = (c - I2.vwma(df)) / a
        kvo, ksig = I2.klinger(df)
        F["klinger"] = np.sign(kvo - ksig)
    else:
        for k_ in ("rvol", "mfi", "cmf", "obv_slope", "force", "eom", "chaikin", "vwma_dist", "klinger"):
            F[k_] = 0.0
    # candle anatomy
    rng = (h - l).replace(0, np.nan)
    F["body"] = (c - o) / rng
    F["upper_wick"] = (h - np.maximum(c, o)) / rng
    F["lower_wick"] = (np.minimum(c, o) - l) / rng
    F["range_atr"] = (h - l) / a
    F["gap"] = (o - c.shift(1)) / a
    F["close_pos_5"] = (c - l.rolling(5).min()) / (h.rolling(5).max() - l.rolling(5).min()).replace(0, np.nan)
    F["ibs"] = (c - l) / rng
    F["consec"] = np.sign(c.diff()).groupby((np.sign(c.diff()) != np.sign(c.diff()).shift()).cumsum()).cumsum() / 5
    # structure
    F["dist_hi20"] = (h.rolling(20).max() - c) / a
    F["dist_lo20"] = (c - l.rolling(20).min()) / a
    F["dist_hi100"] = (h.rolling(100).max() - c) / a
    F["dist_lo100"] = (c - l.rolling(100).min()) / a
    F["days_since_hi50"] = h.rolling(50).apply(lambda x: (len(x) - 1 - x.argmax()) / 50, raw=True)
    # time
    if isinstance(df.index, pd.DatetimeIndex):
        F["hour_sin"] = np.sin(2 * np.pi * df.index.hour / 24)
        F["hour_cos"] = np.cos(2 * np.pi * df.index.hour / 24)
        F["dow"] = df.index.dayofweek / 6
    F = F.replace([np.inf, -np.inf], np.nan)
    return F


FEATURE_GROUPS = {
    "Trend": ["ema", "kama", "hma", "t3", "lr_", "adx", "di_", "aroon", "vortex", "st_dir", "psar", "halftrend", "trix", "ppo"],
    "Momentum": ["ret_", "rsi", "stoch", "macd", "cci", "willr", "cmo", "ultimate", "ao", "schaff", "crsi", "fisher", "rvi", "dpo"],
    "Volatility": ["atr", "bb_", "kc_", "squeeze", "donch", "hv_", "zscore", "mass"],
    "Volume": ["rvol", "mfi", "cmf", "obv", "force", "eom", "chaikin", "vwma", "klinger"],
    "Regime": ["chop", "er", "hurst"],
    "Candle/Structure": ["body", "wick", "range_atr", "gap", "close_pos", "ibs", "consec", "dist_", "days_since"],
    "Time": ["hour", "dow"],
}


def group_of(feat):
    for g, keys in FEATURE_GROUPS.items():
        if any(feat.startswith(k) or k in feat for k in keys):
            return g
    return "Other"


# ---------------------------------------------------------------- labels (triple barrier)
def triple_barrier(df, k_tp=2.0, k_sl=1.0, horizon=24):
    """Returns (y_long, y_short, t_end). y=1 if TP hit before SL within horizon, else 0. NaN for last `horizon` bars."""
    c, h, l = df.close.values, df.high.values, df.low.values
    a = ta.atr(df, 14).values
    n = len(df)
    yl = np.full(n, np.nan); ys = np.full(n, np.nan)
    for i in range(n - horizon):
        if not a[i] == a[i]:
            continue
        tp_l, sl_l = c[i] + k_tp * a[i], c[i] - k_sl * a[i]
        tp_s, sl_s = c[i] - k_tp * a[i], c[i] + k_sl * a[i]
        rl = rs = 0
        dl = ds = False
        for j in range(i + 1, i + 1 + horizon):
            if not dl:
                if l[j] <= sl_l:
                    rl, dl = 0, True
                elif h[j] >= tp_l:
                    rl, dl = 1, True
            if not ds:
                if h[j] >= sl_s:
                    rs, ds = 0, True
                elif l[j] <= tp_s:
                    rs, ds = 1, True
            if dl and ds:
                break
        yl[i], ys[i] = rl, rs
    return pd.Series(yl, index=df.index), pd.Series(ys, index=df.index)


# ---------------------------------------------------------------- model
def _model():
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.04, max_depth=5, min_samples_leaf=60,
                                          l2_regularization=1.0, early_stopping=False, random_state=7)


def purged_walk_forward(X, y, n_folds=4, embargo=50):
    """Yield (train_idx, test_idx) for sequential folds; purge `embargo` bars around test start to avoid label overlap."""
    n = len(X)
    start = int(n * 0.4)
    edges = np.linspace(start, n, n_folds + 1).astype(int)
    for k in range(n_folds):
        a, b = edges[k], edges[k + 1]
        tr = np.arange(0, max(0, a - embargo))
        te = np.arange(a, b)
        yield tr, te


def train_market_model(df, horizon=24, k_tp=2.0, k_sl=1.0, progress=None):
    """Train long & short models on one market. Returns dict with OOS metrics, importances, latest probabilities."""
    from sklearn.metrics import roc_auc_score, brier_score_loss
    if progress:
        progress("features")
    X = build_features(df)
    yl, ys = triple_barrier(df, k_tp, k_sl, horizon)
    feats = X.columns.tolist()
    out = {"horizon": horizon, "k_tp": k_tp, "k_sl": k_sl, "n": int(len(df)), "features": feats}
    for side, y in (("long", yl), ("short", ys)):
        if progress:
            progress(f"train {side}")
        mask = y.notna() & X.notna().mean(axis=1).gt(0.8)
        Xm, ym = X[mask].values, y[mask].values.astype(int)
        base = ym.mean()
        oos_p = np.full(len(ym), np.nan)
        aucs, briers, lifts = [], [], []
        for tr, te in purged_walk_forward(Xm, ym):
            if len(tr) < 300 or len(te) < 50 or len(np.unique(ym[tr])) < 2:
                continue
            m = _model().fit(Xm[tr], ym[tr])
            p = m.predict_proba(Xm[te])[:, 1]
            oos_p[te] = p
            if len(np.unique(ym[te])) == 2:
                aucs.append(roc_auc_score(ym[te], p))
                briers.append(brier_score_loss(ym[te], p))
                top = p >= np.quantile(p, 0.8)
                lifts.append(ym[te][top].mean() / max(ym[te].mean(), 1e-9))
        final = _model().fit(Xm, ym)
        # permutation-free importance: use gain-like proxy via sklearn's permutation_importance on last fold subset (fast: 1 repeat)
        try:
            from sklearn.inspection import permutation_importance
            sub = slice(max(0, len(Xm) - 1500), len(Xm))
            pi = permutation_importance(final, Xm[sub], ym[sub], n_repeats=2, random_state=1, scoring="roc_auc")
            imp = dict(zip(feats, pi.importances_mean.tolist()))
        except Exception:
            imp = {}
        p_now = float(final.predict_proba(X.iloc[[-1]].fillna(0).values)[0, 1]) if X.iloc[-1].notna().mean() > 0.8 else float("nan")
        # calibration bins (OOS)
        valid = ~np.isnan(oos_p)
        bins = []
        if valid.sum() > 200:
            qs = np.quantile(oos_p[valid], np.linspace(0, 1, 6))
            for i in range(5):
                sel = valid & (oos_p >= qs[i]) & (oos_p <= qs[i + 1])
                if sel.sum() > 10:
                    bins.append((float(oos_p[sel].mean()), float(ym[sel].mean()), int(sel.sum())))
        out[side] = dict(base_rate=float(base), auc=float(np.mean(aucs)) if aucs else float("nan"),
                         brier=float(np.mean(briers)) if briers else float("nan"),
                         lift_top20=float(np.mean(lifts)) if lifts else float("nan"),
                         p_now=p_now, importances=imp, calibration=bins, n_train=int(len(ym)))
        out[f"_model_{side}"] = final
        out[f"_oos_{side}"] = pd.Series(oos_p, index=X.index[mask])
    # group importance
    g = {}
    for side in ("long", "short"):
        for f, v in out[side]["importances"].items():
            g[group_of(f)] = g.get(group_of(f), 0) + max(v, 0)
    tot = sum(g.values()) or 1
    out["group_importance"] = {k: v / tot for k, v in sorted(g.items(), key=lambda x: -x[1])}
    out["ts"] = time.time()
    return out


def predict(model_bundle, df):
    X = build_features(df).fillna(0)
    pl = model_bundle["_model_long"].predict_proba(X.values)[:, 1]
    ps = model_bundle["_model_short"].predict_proba(X.values)[:, 1]
    return pd.Series(pl, index=df.index), pd.Series(ps, index=df.index)


def meta_label_signals(model_bundle, df, res):
    """Meta-labeling: attach P(win) from the ML model to each strategy signal; returns Series aligned with signals."""
    pl, ps = predict(model_bundle, df)
    sig = res.signal
    out = pd.Series(np.nan, index=df.index)
    out[sig == 1] = pl[sig == 1]
    out[sig == -1] = ps[sig == -1]
    return out


# ---------------------------------------------------------------- persistence
def _key(symbol, tf):
    import hashlib
    return hashlib.md5(f"{symbol}|{tf}".encode()).hexdigest()[:12]


def save_bundle(symbol, tf, bundle):
    light = {k: v for k, v in bundle.items() if not k.startswith("_")}
    with open(os.path.join(MODEL_DIR, _key(symbol, tf) + ".pkl"), "wb") as f:
        pickle.dump({"models": {"long": bundle["_model_long"], "short": bundle["_model_short"]}, "meta": light}, f)
    idx_path = os.path.join(MODEL_DIR, "index.json")
    idx = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    idx[f"{symbol}|{tf}"] = dict(ts=bundle["ts"], auc_long=bundle["long"]["auc"], auc_short=bundle["short"]["auc"],
                                 lift_long=bundle["long"]["lift_top20"], lift_short=bundle["short"]["lift_top20"], n=bundle["n"])
    json.dump(idx, open(idx_path, "w"), indent=1, default=float)


def load_bundle(symbol, tf):
    p = os.path.join(MODEL_DIR, _key(symbol, tf) + ".pkl")
    if not os.path.exists(p):
        return None
    d = pickle.load(open(p, "rb"))
    b = dict(d["meta"])
    b["_model_long"], b["_model_short"] = d["models"]["long"], d["models"]["short"]
    return b


def list_models():
    idx_path = os.path.join(MODEL_DIR, "index.json")
    return json.load(open(idx_path)) if os.path.exists(idx_path) else {}
