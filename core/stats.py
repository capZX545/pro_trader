"""
Honest statistics for trading results.

Problems these functions fix:
  • small-sample optimism  → confidence intervals (Wilson for win-rate, bootstrap for profit factor / expectancy)
  • selection bias         → multiple-testing-aware threshold (we test ~2000 strategy×tf×group combos;
                             a "proven" edge must survive a Bonferroni-style stricter t-stat)
  • "PF 2.8 on 20 trades"  → reliability grade A/B/C/D that the UI shows next to every number
"""
import math
import numpy as np

# how many independent hypothesis tests the playbook performs (strategies × timeframes × groups)
N_TESTS_DEFAULT = 78 * 6 * 4


def wilson_ci(wins, n, z=1.96):
    """Wilson score interval for a proportion. Returns (lo, hi) in 0..1."""
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def profit_factor(p):
    p = np.asarray(p, float)
    g = p[p > 0].sum()
    l = -p[p < 0].sum()
    if l <= 0:
        return 3.0 if g > 0 else 0.0
    return float(min(g / l, 9.99))


def bootstrap_ci(p, fn=profit_factor, n_boot=1000, alpha=0.05, seed=11):
    """Percentile bootstrap CI of a statistic of the trade-PnL vector."""
    p = np.asarray(p, float)
    if len(p) < 5:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(p), size=(n_boot, len(p)))
    vals = np.array([fn(p[i]) for i in idx])
    return (float(np.percentile(vals, 100 * alpha / 2)), float(np.percentile(vals, 100 * (1 - alpha / 2))))


def t_stat(p):
    """t-statistic of mean trade PnL vs zero (edge significance)."""
    p = np.asarray(p, float)
    if len(p) < 3 or p.std(ddof=1) == 0:
        return 0.0
    return float(p.mean() / (p.std(ddof=1) / math.sqrt(len(p))))


def required_t(n_tests=N_TESTS_DEFAULT, alpha=0.05):
    """Bonferroni-adjusted one-sided z threshold: with ~1900 tests, alpha 5% → z ≈ 4.0 (vs 1.65 for a single test)."""
    from statistics import NormalDist
    return float(NormalDist().inv_cdf(1 - alpha / max(n_tests, 1)))


def grade(n, pf_lo, t):
    """Reliability grade shown in the UI.
       A: n≥100, PF lower-CI>1.1, t≥3     — trust it
       B: n≥50,  PF lower-CI>1.0, t≥2     — decent, size small
       C: n≥30,  PF point>1.15, t≥1.5     — suggestive only
       D: anything else                    — noise / do not trade on it
    """
    if n >= 100 and pf_lo > 1.1 and t >= 3:
        return "A"
    if n >= 50 and pf_lo > 1.0 and t >= 2:
        return "B"
    if n >= 30 and t >= 1.5:
        return "C"
    return "D"


def min_trades_for(wr, target_half_width=0.08, z=1.96):
    """How many trades are needed so the win-rate CI half-width is ≤ target (default ±8%)."""
    wr = min(max(wr, 0.01), 0.99)
    return int(math.ceil(z * z * wr * (1 - wr) / target_half_width ** 2))


def full_report(pnls, n_tests=N_TESTS_DEFAULT):
    """One dict with everything the UI / playbook needs."""
    p = np.asarray(pnls, float)
    n = len(p)
    if n == 0:
        return dict(n=0, wr=0.0, wr_lo=0.0, wr_hi=1.0, pf=0.0, pf_lo=float("nan"), pf_hi=float("nan"), t=0.0,
                    t_req=required_t(n_tests), grade="D", exp=0.0, exp_lo=float("nan"), exp_hi=float("nan"), need_n=0)
    wins = int((p > 0).sum())
    wr_lo, wr_hi = wilson_ci(wins, n)
    pf = profit_factor(p)
    pf_lo, pf_hi = bootstrap_ci(p)
    ex_lo, ex_hi = bootstrap_ci(p, fn=lambda x: float(np.mean(x)), n_boot=600)
    t = t_stat(p)
    return dict(n=n, wr=100 * wins / n, wr_lo=100 * wr_lo, wr_hi=100 * wr_hi, pf=pf, pf_lo=pf_lo, pf_hi=pf_hi, t=t,
                t_req=required_t(n_tests), grade=grade(n, pf_lo if pf_lo == pf_lo else 0, t),
                exp=float(p.mean()), exp_lo=ex_lo, exp_hi=ex_hi, need_n=min_trades_for(wins / n))


def regime_coverage(close):
    """Share of the tested history spent in up / down / flat regimes (EMA50 vs EMA200 + slope).
       A strategy tested only in a bull market gets a 'coverage' warning."""
    import pandas as pd
    c = pd.Series(close).astype(float)
    if len(c) < 250:
        return dict(up=0.0, down=0.0, flat=1.0, warn=True)
    e50, e200 = c.ewm(span=50).mean(), c.ewm(span=200).mean()
    slope = e200.pct_change(20)
    up = ((e50 > e200) & (slope > 0.005)).mean()
    down = ((e50 < e200) & (slope < -0.005)).mean()
    flat = 1 - up - down
    return dict(up=float(up), down=float(down), flat=float(flat), warn=bool(max(up, down, flat) > 0.75))
