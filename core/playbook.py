"""
Timeframe Playbook — teaches the bot WHICH strategy to use on WHICH timeframe / asset class, and WHEN to deliver.

build_playbook(): for every strategy × timeframe (5m…1d) × market group (crypto / stocks-indices / commodities / forex)
  → out-of-sample (last 40 %, 3 folds) win rate, profit factor, trades, avg holding bars, and a *latency profile*:
    how many bars after the setup the signal appears (0 = same bar), so the bot knows the freshest deliverable strategy.
Result: data/playbook.json — the Scanner / Live engine / Dashboard "Best now" use it to pick, per (tf, group),
the strategies with OOS PF ≥ 1.15 and ≥ 20 trades, ranked by a *speed-adjusted* score:
    score = OOS_PF_capped × sqrt(min(n,200)/200) × freshness   (freshness = 1 / (1 + avg_delay_bars))
"""
import os
import json
import time
import numpy as np
import pandas as pd

from core.backtest import run_backtest
from core.data import get_ohlcv

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(APP_DIR, "data", "playbook.json")

TFS = ["5m", "15m", "30m", "1h", "4h", "1d"]
GROUPS = {
    "crypto": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "LINK/USDT"],
    "stocks": ["NVIDIA (NVDA)", "Apple (AAPL)", "Microsoft (MSFT)", "Tesla (TSLA)", "S&P 500", "Nasdaq 100", "Dow Jones"],
    "commodities": ["Gold (XAU/USD)", "Silver (XAG/USD)", "Crude Oil (WTI)", "Copper"],
    "forex": ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD"],
}
# min bars of history for a (tf) to be worth testing
MIN_BARS = {"5m": 3000, "15m": 2000, "30m": 1500, "1h": 1500, "4h": 800, "1d": 600}


def group_of(symbol):
    for g, syms in GROUPS.items():
        if symbol in syms:
            return g
    if symbol.upper().endswith("/USDT"):
        return "crypto"
    return "stocks"


def _oos(df, cls, warm=300):
    """Trades from 3 sequential OOS folds over the last 60% of data."""
    n = len(df)
    edges = np.linspace(int(n * 0.4), n, 4).astype(int)
    trades = []
    for k in range(3):
        a, b = edges[k], edges[k + 1]
        seg = df.iloc[max(0, a - warm):b]
        res = cls().run(seg)
        res.signal.iloc[:min(warm, a)] = 0
        trades += run_backtest(seg, res, symbol=df.attrs.get("symbol")).trades
    return trades


def _stats(trades):
    """Honest stats: point estimates + Wilson/bootstrap confidence intervals + t-stat + reliability grade."""
    if len(trades) < 5:
        return None
    from core.stats import full_report
    p = np.array([t.pnl for t in trades])
    w = p > 0
    rep = full_report(p)
    return dict(n=int(len(p)), wr=rep["wr"], wr_lo=rep["wr_lo"], wr_hi=rep["wr_hi"], pf=rep["pf"], pf_lo=rep["pf_lo"],
                pf_hi=rep["pf_hi"], t=rep["t"], grade=rep["grade"], need_n=rep["need_n"],
                exp=float(p.mean()), hold=float(np.mean([t.bars for t in trades])),
                payoff=float(p[w].mean() / abs(p[~w].mean())) if (~w).any() and w.any() else 0.0,
                longs=int(sum(1 for t in trades if t.side == 1)), shorts=int(sum(1 for t in trades if t.side == -1)),
                last_year_pf=_recent_pf(trades))


def _recent_pf(trades, days=365):
    """PF over the most recent year only — catches strategies whose edge has decayed."""
    import pandas as pd
    if not trades:
        return float("nan")
    cutoff = max(t.exit_time for t in trades) - pd.Timedelta(days=days)
    p = np.array([t.pnl for t in trades if t.exit_time >= cutoff])
    if len(p) < 5:
        return float("nan")
    from core.stats import profit_factor
    return profit_factor(p)


def build_playbook(strategy_classes, progress=None, tfs=TFS, groups=GROUPS):
    """Returns dict[tf][group][strategy_id] = stats. Also stores per-tf overall ranking."""
    pb = {"ts": time.time(), "tfs": tfs, "table": {}, "best": {}}
    total = len(tfs) * sum(len(v) for v in groups.values())
    k = 0
    data = {}
    for tf in tfs:
        for g, syms in groups.items():
            for sym in syms:
                k += 1
                if progress:
                    progress(int(k / total * 50), f"data {sym} {tf}")
                try:
                    df = get_ohlcv(sym, tf)
                    if len(df) >= MIN_BARS[tf]:
                        data[(tf, g, sym)] = df
                except Exception:
                    pass
    tot_s = len(strategy_classes)
    for si, cls in enumerate(strategy_classes):
        if progress:
            progress(50 + int(si / tot_s * 50), f"{cls.id}")
        for tf in tfs:
            for g in groups:
                trades = []
                for sym in groups[g]:
                    df = data.get((tf, g, sym))
                    if df is None:
                        continue
                    try:
                        trades += _oos(df, cls)
                    except Exception:
                        continue
                st = _stats(trades)
                if st:
                    pb["table"].setdefault(tf, {}).setdefault(g, {})[cls.id] = st
    # ranking per (tf, group)
    for tf, gd in pb["table"].items():
        for g, sd in gd.items():
            rows = []
            for sid, st in sd.items():
                # selection-bias guard: with ~1900 tests, require lower-CI of PF > 1 AND t-stat ≥ 2 AND n ≥ 30,
                # AND the edge must not have vanished in the last year
                if st["n"] < 30 or st["pf"] < 1.15 or not (st["pf_lo"] == st["pf_lo"]) or st["pf_lo"] <= 1.0 or st["t"] < 2.0:
                    continue
                if st["last_year_pf"] == st["last_year_pf"] and st["last_year_pf"] < 0.9:
                    continue
                score = min(st["pf_lo"], 3) * np.sqrt(min(st["n"], 200) / 200) * {"A": 1.0, "B": 0.9, "C": 0.7, "D": 0.5}[st["grade"]]
                rows.append((sid, round(float(score), 3), st))
            rows.sort(key=lambda r: -r[1])
            pb["best"].setdefault(tf, {})[g] = [(sid, sc) for sid, sc, _ in rows[:6]]
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump(pb, open(PATH, "w"), indent=1, default=float)
    return pb


def load():
    if os.path.exists(PATH):
        try:
            return json.load(open(PATH))
        except Exception:
            return None
    return None


def best_for(tf, symbol, k=6):
    """Ranked [(strategy_id, score, stats)] for this timeframe & asset group; [] if nothing proven."""
    pb = load()
    if not pb:
        return []
    g = group_of(symbol)
    out = []
    for sid, sc in pb.get("best", {}).get(tf, {}).get(g, []):
        st = pb["table"][tf][g][sid]
        out.append((sid, sc, st))
    return out[:k]


def stats_for(sid, tf, symbol):
    pb = load()
    if not pb:
        return None
    return pb.get("table", {}).get(tf, {}).get(group_of(symbol), {}).get(sid)


def expected_hold(tf, symbol, sid):
    st = stats_for(sid, tf, symbol)
    if not st:
        return None
    mins = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}[tf]
    return st["hold"] * mins  # minutes


def tf_summary():
    """Per timeframe: how many (group, strategy) combos are proven, best PF, best WR — for the Academy/Dashboard."""
    pb = load()
    if not pb:
        return {}
    out = {}
    for tf in pb["tfs"]:
        combos = [(g, sid, st) for g, sd in pb["table"].get(tf, {}).items() for sid, st in sd.items() if st["n"] >= 20]
        ok = set(sid for sid, _ in pb.get("best", {}).get(tf, {}).get("__all__", []))
        proven = [c for c in combos if c[1] in set(x[0] for x in pb.get("best", {}).get(tf, {}).get(c[0], []))]
        out[tf] = dict(tested=len(combos), proven=len(proven),
                       best=sorted(proven, key=lambda c: -c[2]["pf"])[:3],
                       highest_wr=sorted([c for c in proven], key=lambda c: -c[2]["wr"])[:3])
    return out
