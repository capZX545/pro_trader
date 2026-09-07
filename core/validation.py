"""
Validation Lab — the "minimum loss" engine.

For every strategy × symbol × timeframe:
  • Full-period backtest
  • Walk-forward: 3 sequential out-of-sample folds (train 60% → test next 40% in chunks)
  • Monte-Carlo trade shuffle: 95th-percentile drawdown
  • Robustness score (0-100) = f(OOS PF, consistency across folds & symbols, MC drawdown, trade count)
Results are cached to data/validation.json and used by Scanner / Dashboard / Web Analyzer to
weight or hide strategies that don't survive out-of-sample.
"""
import os
import json
import time
import numpy as np
import pandas as pd

from core.backtest import run_backtest
from core.data import get_ohlcv

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(APP_DIR, "data", "validation.json")

DEFAULT_UNIVERSE = [
    ("BTC/USDT", "1h"), ("ETH/USDT", "1h"), ("SOL/USDT", "1h"), ("BTC/USDT", "4h"), ("ETH/USDT", "4h"), ("BTC/USDT", "1d"),
    ("Gold (XAU/USD)", "1h"), ("Gold (XAU/USD)", "1d"), ("EUR/USD", "1h"), ("GBP/USD", "4h"),
    ("S&P 500", "1d"), ("Nasdaq 100", "1d"), ("NVIDIA (NVDA)", "1d"), ("Apple (AAPL)", "1d"),
    ("Microsoft (MSFT)", "1d"), ("Meta (META)", "1d"), ("Google (GOOGL)", "1d"), ("AMD", "1d"), ("Dow Jones", "1d"), ("ETH/USDT", "1d"),
]


def _oos_folds(df, strat_cls, kw, n_folds=3, warmup=300):
    """Sequential OOS folds: test on chunk k using only data before it + warmup for indicators."""
    n = len(df)
    start = int(n * 0.4)
    edges = np.linspace(start, n, n_folds + 1).astype(int)
    out = []
    for k in range(n_folds):
        a, b = edges[k], edges[k + 1]
        seg = df.iloc[max(0, a - warmup):b]
        res = strat_cls().run(seg)
        res.signal.iloc[:min(warmup, a)] = 0
        st = run_backtest(seg, res, **kw).stats
        out.append(st)
    return out


def monte_carlo_dd(trades, initial=10_000.0, n_sims=300, seed=7):
    """Shuffle trade order; return 95th percentile max drawdown % and prob of ending below start."""
    if len(trades) < 5:
        return 0.0, 0.0
    rng = np.random.default_rng(seed)
    pnl = np.array([t.pnl for t in trades])
    dds = np.empty(n_sims)
    neg = 0
    for i in range(n_sims):
        p = rng.permutation(pnl)
        eq = initial + np.cumsum(p)
        dd = (eq / np.maximum.accumulate(np.maximum(eq, 1e-9)) - 1).min() * 100
        dds[i] = -dd
        neg += eq[-1] < initial
    return float(np.percentile(dds, 95)), neg / n_sims


def robustness_score(full, folds, mc_dd95, symbols_positive_ratio):
    """0-100. Emphasises OUT-OF-SAMPLE behaviour, not in-sample return."""
    if full["trades"] < 20:
        return 0.0
    pf_oos = np.array([f["profit_factor"] for f in folds if f["trades"] >= 3])
    if len(pf_oos) == 0:
        return 0.0
    pf_oos = np.clip(np.where(np.isinf(pf_oos), 3, pf_oos), 0, 3)
    s_pf = np.clip((pf_oos.mean() - 0.8) / 1.2, 0, 1) * 40          # mean OOS PF 0.8→2.0 maps 0→40
    s_cons = (pf_oos > 1.0).mean() * 20                              # share of OOS folds profitable
    s_dd = np.clip(1 - mc_dd95 / 40, 0, 1) * 15                      # MC 95% DD 0→40% maps 15→0
    s_n = np.clip(np.log10(full["trades"]) / 2.5, 0, 1) * 10         # 20→~50% … 300+ → full
    s_cross = symbols_positive_ratio * 15                            # works across many symbols?
    return float(round(s_pf + s_cons + s_dd + s_n + s_cross, 1))


def validate_strategy(strat_cls, universe=None, kw=None, progress=None):
    kw = kw or {}
    universe = universe or DEFAULT_UNIVERSE
    rows = []
    for i, (sym, tf) in enumerate(universe):
        if progress:
            progress(f"{strat_cls.id} · {sym} {tf}")
        try:
            df = get_ohlcv(sym, tf)
            if len(df) < 500:
                continue
            res = strat_cls().run(df)
            bt = run_backtest(df, res, **kw)
            folds = _oos_folds(df, strat_cls, kw)
            dd95, p_neg = monte_carlo_dd(bt.trades, bt.initial_capital)
            rows.append(dict(symbol=sym, tf=tf, trades=bt.stats["trades"], pf=bt.stats["profit_factor"], wr=bt.stats["win_rate"],
                             ret=bt.stats["return_pct"], dd=bt.stats["max_dd_pct"], sharpe=bt.stats["sharpe"],
                             oos_pf=[f["profit_factor"] for f in folds], oos_ret=[f["return_pct"] for f in folds],
                             oos_trades=[f["trades"] for f in folds], mc_dd95=dd95, p_neg=p_neg))
        except Exception as e:  # pragma: no cover
            rows.append(dict(symbol=sym, tf=tf, error=str(e)))
    ok = [r for r in rows if "error" not in r and r["trades"] >= 10]
    if not ok:
        return dict(id=strat_cls.id, score=0.0, rows=rows, n=0)
    # aggregate
    all_folds = [dict(profit_factor=pf, trades=n) for r in ok for pf, n in zip(r["oos_pf"], r["oos_trades"])]
    full = dict(trades=int(sum(r["trades"] for r in ok)))
    mc = float(np.median([r["mc_dd95"] for r in ok]))
    pos_ratio = float(np.mean([np.mean([x > 1 for x in r["oos_pf"] if x == x]) if r["oos_pf"] else 0 for r in ok]))
    score = robustness_score(full, all_folds, mc, pos_ratio)
    best = sorted(ok, key=lambda r: (np.mean([min(x, 3) for x in r["oos_pf"]]) if r["oos_pf"] else 0), reverse=True)[:5]
    return dict(id=strat_cls.id, score=score, n=len(ok), total_trades=full["trades"],
                oos_pf_mean=float(np.mean([min(f["profit_factor"], 3) for f in all_folds if f["trades"] >= 3] or [0])),
                oos_pos_ratio=pos_ratio, mc_dd95_median=mc, best_markets=[(r["symbol"], r["tf"]) for r in best], rows=rows,
                ts=time.time())


def load_cache():
    if os.path.exists(CACHE):
        try:
            return json.load(open(CACHE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(d):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(d, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)


def score_of(strategy_id, default=None):
    c = load_cache()
    r = c.get(strategy_id)
    return r["score"] if r else default


def best_markets_of(strategy_id):
    c = load_cache()
    r = c.get(strategy_id)
    return [tuple(x) for x in r.get("best_markets", [])] if r else []


def run_all(strategy_classes, universe=None, kw=None, progress=None):
    cache = load_cache()
    for k, cls in enumerate(strategy_classes):
        if progress:
            progress(int(k / len(strategy_classes) * 100), cls.id)
        cache[cls.id] = validate_strategy(cls, universe, kw, progress=None)
        save_cache(cache)
    if progress:
        progress(100, "done")
    return cache


def market_stats(strategy_id, symbol, tf):
    """Per-market validated stats for a strategy: dict(wr, pf, oos_pf_mean, trades) or None if never validated there."""
    r = load_cache().get(strategy_id)
    if not r:
        return None
    for row in r.get("rows", []):
        if row.get("symbol") == symbol and row.get("tf") == tf and "error" not in row:
            pfs = [min(x, 3) for x in row.get("oos_pf", []) if x == x]
            return dict(wr=row["wr"], pf=row["pf"], trades=row["trades"], oos_pf_mean=float(np.mean(pfs)) if pfs else float("nan"))
    return None


def allowed(strategy_id, symbol, tf, min_oos_pf=1.0, min_trades=10):
    """Domain lock: True if the strategy proved itself out-of-sample on THIS market, or was never tested there (unknown → allowed)."""
    st = market_stats(strategy_id, symbol, tf)
    if st is None:
        return True
    if st["trades"] < min_trades:
        return True
    return st["oos_pf_mean"] >= min_oos_pf
