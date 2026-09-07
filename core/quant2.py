"""
Phase-10 deepening of the quant toolkit.

Ernie Chan (Algorithmic Trading, ch.3)      : Kalman-filter dynamic hedge ratio + spread/zscore, Bollinger-on-spread
López de Prado (AFML ch.3-4)                : triple-barrier labels, uniqueness/sample weights, sequential bootstrap
Kevin Davey (Building Winning Algo Systems) : monkey test (random-entry benchmark), MC drawdown/return distribution
Alexander Elder (Come Into My Trading Room) : SafeZone stop, Impulse system colouring, 2% + 6% rules
William O'Neil (How to Make Money in Stocks): 7-8% sell rule, climax-top, 20-25% profit taking, 50-day MA break
Brett Steenbarger (Psychology of Trading)   : per-setup / per-time performance metrics for the journal
Jesse                                        : anchor-timeframe filter helper
OctoBot                                      : weighted evaluator matrix
"""
import numpy as np
import pandas as pd


# ------------------------------------------------------------------ Chan: Kalman hedge ratio
def kalman_hedge(y, x, delta=1e-4, ve=1e-3):
    """Chan's Kalman filter: y_t = beta_t * x_t + alpha_t + e ; state = [beta, alpha] random walk.
    Returns DataFrame(beta, alpha, spread_err e, sqrt_Q) aligned to y index."""
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    n = len(y)
    Vw = delta / (1 - delta) * np.eye(2)
    R = np.zeros((2, 2))
    P = np.zeros((2, 2))
    theta = np.zeros(2)  # beta, alpha
    beta = np.zeros(n)
    alpha = np.zeros(n)
    e = np.zeros(n)
    Q = np.zeros(n)
    for t in range(n):
        F = np.array([x[t], 1.0])
        if t > 0:
            R = P + Vw
        yhat = F @ theta
        Q[t] = F @ R @ F + ve
        e[t] = y[t] - yhat
        K = R @ F / Q[t]
        theta = theta + K * e[t]
        P = R - np.outer(K, F) @ R
        beta[t], alpha[t] = theta
    return pd.DataFrame({"beta": beta, "alpha": alpha, "e": e, "sqrtQ": np.sqrt(Q)})


def kalman_pairs_signal(y, x, delta=1e-4, ve=1e-3, entry=1.0, exit_=0.0):
    """Chan's trading rule: long spread when e < -entry*sqrt(Q), short when e > +entry*sqrt(Q); exit when e crosses back."""
    k = kalman_hedge(y, x, delta, ve)
    z = k["e"] / k["sqrtQ"].replace(0, np.nan)
    sig = pd.Series(0, index=range(len(k)))
    pos = 0
    out = np.zeros(len(k), int)
    for i, zi in enumerate(z.values):
        if np.isnan(zi):
            out[i] = pos
            continue
        if pos == 0:
            if zi < -entry:
                pos = 1
            elif zi > entry:
                pos = -1
        elif pos == 1 and zi >= -exit_:
            pos = 0
        elif pos == -1 and zi <= exit_:
            pos = 0
        out[i] = pos
    k["z"] = z
    k["position"] = out
    return k


# ------------------------------------------------------------------ de Prado: labels & weights
def triple_barrier(close, events_idx, pt=1.0, sl=1.0, max_h=20, vol=None):
    """AFML 3.4: for each event index, find first touch of profit-take (pt*vol), stop-loss (sl*vol) or vertical barrier.
    Returns DataFrame(t0, t1, ret, label{-1,0,1})."""
    c = np.asarray(close, float)
    n = len(c)
    if vol is None:
        r = pd.Series(c).pct_change()
        vol = r.ewm(span=50).std().bfill().values
    rows = []
    for i in events_idx:
        if i >= n - 1:
            continue
        up = pt * vol[i]
        dn = -sl * vol[i]
        t1 = min(i + max_h, n - 1)
        lab, hit = 0, t1
        for j in range(i + 1, t1 + 1):
            ret = c[j] / c[i] - 1
            if ret >= up:
                lab, hit = 1, j
                break
            if ret <= dn:
                lab, hit = -1, j
                break
        rows.append((i, hit, c[hit] / c[i] - 1, lab))
    return pd.DataFrame(rows, columns=["t0", "t1", "ret", "label"])


def concurrency(t0, t1, n):
    """number of overlapping labels at each bar"""
    conc = np.zeros(n)
    for a, b in zip(t0, t1):
        conc[a:b + 1] += 1
    return conc


def sample_weights(t0, t1, close):
    """AFML 4.3-4.5: average uniqueness and return-attribution weights (normalised to sum = N)."""
    c = np.asarray(close, float)
    n = len(c)
    conc = concurrency(t0, t1, n)
    lr = np.diff(np.log(c), prepend=np.log(c[0]))
    uniq, w = [], []
    for a, b in zip(t0, t1):
        cc = conc[a:b + 1]
        uniq.append(np.mean(1.0 / cc))
        w.append(abs(np.sum(lr[a + 1:b + 1] / cc[1:] if b > a else 0.0)))
    w = np.asarray(w)
    if w.sum() > 0:
        w = w * len(w) / w.sum()
    return pd.DataFrame({"uniqueness": uniq, "weight": w})


def sequential_bootstrap(t0, t1, n, size=None, seed=0):
    """AFML 4.5.2: draw samples so that each new draw favours labels with low overlap with those already drawn."""
    rng = np.random.default_rng(seed)
    m = len(t0)
    size = size or m
    ind = np.zeros((m, n), bool)
    for k, (a, b) in enumerate(zip(t0, t1)):
        ind[k, a:b + 1] = True
    phi = []
    for _ in range(size):
        conc = ind[phi].sum(0) if phi else np.zeros(n)
        avg_u = np.zeros(m)
        for k in range(m):
            cc = conc[ind[k]] + 1.0
            avg_u[k] = np.mean(1.0 / cc) if cc.size else 0
        p = avg_u / avg_u.sum() if avg_u.sum() > 0 else np.ones(m) / m
        phi.append(rng.choice(m, p=p))
    return np.array(phi)


# ------------------------------------------------------------------ Davey: monkey test + MC
def monkey_test(df, strategy_stats_pnl_pct, n_trades=None, holding_bars=10, n_sims=500, seed=7, allow_short=True):
    """Random-entry benchmark: same number of trades & mean holding; returns percentile of the strategy's total
    return vs. random and the random distribution stats. Strategy must beat ≥ 95th pct to be 'better than luck'."""
    c = df["close"].values
    n = len(c)
    rng = np.random.default_rng(seed)
    n_trades = n_trades or len(strategy_stats_pnl_pct)
    strat_total = float(np.sum(strategy_stats_pnl_pct))
    tot = np.zeros(n_sims)
    for s in range(n_sims):
        idx = rng.integers(0, n - holding_bars - 1, n_trades)
        side = rng.choice([1, -1], n_trades) if allow_short else np.ones(n_trades)
        r = (c[idx + holding_bars] / c[idx] - 1) * 100 * side
        tot[s] = r.sum()
    pct = float((tot < strat_total).mean() * 100)
    return dict(strategy_total_pct=strat_total, random_mean=float(tot.mean()), random_p95=float(np.percentile(tot, 95)),
                percentile=pct, passed=pct >= 95)


def monte_carlo_trades(pnl_pct, n_sims=2000, seed=3, start_equity=10000.0, risk_scale=1.0):
    """Davey ch.: shuffle trade order & resample with replacement; report return / max-DD distribution."""
    p = np.asarray(pnl_pct, float) / 100 * risk_scale
    if len(p) == 0:
        return {}
    rng = np.random.default_rng(seed)
    rets, dds = np.zeros(n_sims), np.zeros(n_sims)
    for s in range(n_sims):
        seq = rng.choice(p, len(p), replace=True)
        eq = start_equity * np.cumprod(1 + seq)
        peak = np.maximum.accumulate(eq)
        dds[s] = (1 - eq / peak).max() * 100
        rets[s] = eq[-1] / start_equity * 100 - 100
    return dict(ret_p5=float(np.percentile(rets, 5)), ret_med=float(np.median(rets)), ret_p95=float(np.percentile(rets, 95)),
                dd_med=float(np.median(dds)), dd_p95=float(np.percentile(dds, 95)), dd_max=float(dds.max()),
                prob_loss=float((rets < 0).mean() * 100), ret_over_dd=float(np.median(rets) / max(np.percentile(dds, 95), 1e-9)))


# ------------------------------------------------------------------ Elder
def safezone_stop(df, lookback=10, coef=2.0, side=1):
    """Elder SafeZone: average downside penetration (for longs: low[t] < low[t-1]) × coef, subtracted from the low."""
    h, l = df["high"], df["low"]
    if side == 1:
        pen = (l.shift(1) - l).clip(lower=0)
        cnt = (pen > 0).rolling(lookback).sum().replace(0, np.nan)
        avg = pen.rolling(lookback).sum() / cnt
        stop = l - coef * avg.fillna(0)
        return stop.cummax() if False else stop.rolling(3).max()  # never lower the stop within the last 3 bars
    pen = (h - h.shift(1)).clip(lower=0)
    cnt = (pen > 0).rolling(lookback).sum().replace(0, np.nan)
    avg = pen.rolling(lookback).sum() / cnt
    stop = h + coef * avg.fillna(0)
    return stop.rolling(3).min()


def impulse_system(df, ema_n=13, fast=12, slow=26, sig=9):
    """Elder Impulse: green = EMA up & MACD-hist up (may buy), red = both down (may short), blue = neutral."""
    c = df["close"]
    ema = c.ewm(span=ema_n, adjust=False).mean()
    macd = c.ewm(span=fast, adjust=False).mean() - c.ewm(span=slow, adjust=False).mean()
    hist = macd - macd.ewm(span=sig, adjust=False).mean()
    up = (ema > ema.shift(1)) & (hist > hist.shift(1))
    dn = (ema < ema.shift(1)) & (hist < hist.shift(1))
    return pd.Series(np.where(up, 1, np.where(dn, -1, 0)), index=df.index)


def elder_money_rules(equity, month_start_equity, open_risk_pct, proposed_risk_pct, month_loss_limit=6.0, trade_limit=2.0):
    """2% rule per trade and 6% rule per month (stop trading for the month once down 6%)."""
    month_dd = (month_start_equity - equity) / month_start_equity * 100
    ok_trade = proposed_risk_pct <= trade_limit
    ok_month = month_dd + open_risk_pct + proposed_risk_pct <= month_loss_limit
    return dict(month_drawdown_pct=month_dd, ok_trade=ok_trade, ok_month=ok_month, allowed=ok_trade and ok_month)


# ------------------------------------------------------------------ O'Neil sell rules
def oneil_sell_rules(df, entry_price, entry_idx):
    """Evaluate O'Neil's sell rules on the latest bar: 7-8% loss cut, 20-25% profit take (unless 20% in <3 weeks →
    hold 8 weeks), close below 50-day MA on volume, climax top (largest daily gain since start of run after a long
    advance). Returns list of triggered rule names."""
    c = df["close"]
    v = df["volume"]
    last = float(c.iloc[-1])
    ret = last / entry_price - 1
    trig = []
    if ret <= -0.08:
        trig.append("cut_loss_8pct")
    elif ret <= -0.07:
        trig.append("cut_loss_7pct_warning")
    bars_held = len(df) - 1 - entry_idx
    if ret >= 0.20:
        if bars_held < 15:
            trig.append("20pct_in_<3w → hold 8 weeks (leader)")
        else:
            trig.append("take_profit_20_25pct")
    ma50 = c.rolling(50).mean()
    if len(df) > 50 and last < ma50.iloc[-1] and v.iloc[-1] > v.rolling(50).mean().iloc[-1] * 1.5:
        trig.append("break_50dma_on_volume")
    seg = c.iloc[max(entry_idx, len(df) - 60):]
    if len(seg) > 10:
        gains = seg.pct_change()
        if gains.iloc[-1] == gains.max() and ret > 0.25:
            trig.append("climax_top_largest_gain")
    return trig


# ------------------------------------------------------------------ Steenbarger metrics
def steenbarger_metrics(trades_df):
    """trades_df columns: pnl_r, setup, hour (0-23), weekday, hold_bars, emotion(optional).
    Returns dict of tables: by setup / hour / weekday, and the 'edge concentration' (share of P&L from top 10% trades)."""
    out = {}
    if trades_df is None or len(trades_df) == 0:
        return out
    t = trades_df.copy()
    for k in ("setup", "hour", "weekday", "emotion"):
        if k in t:
            g = t.groupby(k)["pnl_r"]
            out[k] = pd.DataFrame({"n": g.size(), "win_rate": g.apply(lambda s: (s > 0).mean() * 100),
                                   "expectancy_r": g.mean(), "total_r": g.sum()}).sort_values("total_r", ascending=False)
    p = t["pnl_r"].sort_values(ascending=False)
    k = max(1, int(len(p) * 0.1))
    out["top10_share"] = float(p.head(k).sum() / p[p > 0].sum() * 100) if (p > 0).any() else 0.0
    out["worst_streak"] = _worst_streak(t["pnl_r"].values)
    if "hold_bars" in t:
        out["hold_win_vs_loss"] = (float(t.loc[t.pnl_r > 0, "hold_bars"].mean()), float(t.loc[t.pnl_r <= 0, "hold_bars"].mean()))
    return out


def _worst_streak(p):
    s = w = 0
    for x in p:
        s = s + 1 if x <= 0 else 0
        w = max(w, s)
    return w


# ------------------------------------------------------------------ Jesse anchor timeframe + OctoBot matrix
def anchor_trend(df, factor=4, ema_n=50):
    """Jesse-style anchor timeframe: resample to `factor`× the base timeframe, EMA slope gives trend bias (1/-1/0)."""
    n = len(df)
    idx = np.arange(n) // factor
    c = df["close"].groupby(idx).last()
    ema = c.ewm(span=ema_n, adjust=False).mean()
    bias = np.sign(ema.diff()).fillna(0)
    return pd.Series(bias.reindex(idx).values, index=df.index).shift(1).fillna(0)  # use only completed anchor candles


def octobot_matrix(evaluations: dict, weights: dict = None, threshold=0.4):
    """OctoBot: evaluators return values in [-1,1]; the strategy averages them (weighted); decision when |avg|>threshold."""
    weights = weights or {}
    num = sum(v * weights.get(k, 1.0) for k, v in evaluations.items())
    den = sum(weights.get(k, 1.0) for k in evaluations) or 1.0
    avg = num / den
    state = "LONG" if avg <= -threshold else ("SHORT" if avg >= threshold else "NEUTRAL")  # OctoBot: -1 = very bullish
    return dict(average=avg, state=state, contributions={k: v * weights.get(k, 1.0) / den for k, v in evaluations.items()})
