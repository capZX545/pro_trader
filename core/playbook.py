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

from core.paths import SRC_ROOT as APP_DIR, data as _data
PATH = _data("playbook.json")

TFS = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1wk"]   # 1mo has too few bars to prove anything
GROUPS = {
    "crypto": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "LINK/USDT", "ADA/USDT", "DOGE/USDT", "AVAX/USDT",
               "DOT/USDT", "LTC/USDT", "TRX/USDT", "ATOM/USDT", "BCH/USDT", "ETC/USDT", "UNI/USDT"],
    "stocks": ["NVIDIA (NVDA)", "Apple (AAPL)", "Microsoft (MSFT)", "Tesla (TSLA)", "Amazon (AMZN)", "Google (GOOGL)", "Meta (META)",
               "JPMorgan (JPM)", "Exxon (XOM)", "Walmart (WMT)", "Caterpillar (CAT)", "S&P 500", "Nasdaq 100", "Dow Jones", "Russell 2000",
               "DAX", "SPY", "QQQ", "IWM", "EEM"],
    "commodities": ["Gold (XAU/USD)", "Silver (XAG/USD)", "Crude Oil (WTI)", "Brent Oil", "Copper", "Natural Gas", "Platinum", "GLD", "USO"],
    "forex": ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "USD/CHF", "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY", "AUD/JPY"],
}
# min bars of history for a (tf) to be worth testing
MIN_BARS = {"1m": 5000, "3m": 4000, "5m": 3000, "15m": 2000, "30m": 1500, "1h": 1500, "2h": 1200, "4h": 800, "6h": 700, "12h": 600, "1d": 600, "3d": 300, "1wk": 200, "1mo": 100}
# breadth gates (Phase 12): a strategy is "proven" only if it is positive on ≥60 % of symbols AND ≥60 % of calendar years
MIN_SYMBOL_BREADTH = 0.6
MIN_YEAR_BREADTH = 0.6
# evaluation window per tf (bars). Intraday is capped for compute (2-core laptop: full build ≈ 1–2 h); still 5–10× the old 1000-bar window
MAX_BARS = {"1m": 12000, "3m": 12000, "5m": 12000, "15m": 12000, "30m": 12000, "1h": 15000, "2h": 12000, "4h": 12000, "6h": 8000, "12h": 5000, "1d": 5000, "3d": 1500, "1wk": 600}


def group_of(symbol):
    for g, syms in GROUPS.items():
        if symbol in syms:
            return g
    if symbol.upper().endswith("/USDT"):
        return "crypto"
    return "stocks"


def _oos(df, cls, warm=300):
    """Trades from sequential OOS folds over the last 60% of data (one fold per ~1500 bars, min 3)."""
    n = len(df)
    k = int(max(3, min(8, n * 0.6 // 1500)))
    edges = np.linspace(int(n * 0.4), n, k + 1).astype(int)
    trades = []
    for k in range(len(edges) - 1):
        a, b = edges[k], edges[k + 1]
        seg = df.iloc[max(0, a - warm):b]
        res = cls().run(seg)
        res.signal.iloc[:min(warm, a)] = 0
        trades += run_backtest(seg, res, symbol=df.attrs.get("symbol")).trades
    return trades


def _breadth(by_symbol, trades):
    """share of symbols with positive net PnL and share of calendar years with positive net PnL"""
    sym_pos = [sum(t.pnl for t in ts) > 0 for ts in by_symbol.values() if len(ts) >= 3]
    years = {}
    for t in trades:
        y = getattr(t.exit_time, "year", None)
        if y is not None:
            years[y] = years.get(y, 0.0) + t.pnl
    yr_pos = [v > 0 for v in years.values()]
    return dict(symbols=int(len(sym_pos)), symbols_pos=float(np.mean(sym_pos)) if sym_pos else 0.0,
                years=int(len(yr_pos)), years_pos=float(np.mean(yr_pos)) if yr_pos else 0.0,
                worst_year=float(min(years.values())) if years else 0.0)


def _stats(trades, by_symbol=None):
    """Honest stats: point estimates + Wilson/bootstrap confidence intervals + t-stat + reliability grade + breadth."""
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
                last_year_pf=_recent_pf(trades), **({"breadth": _breadth(by_symbol, trades)} if by_symbol else {}))


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


PARTIAL = PATH + ".partial"


def build_playbook(strategy_classes, progress=None, tfs=TFS, groups=GROUPS, resume=True):
    """Returns dict[tf][group][strategy_id] = stats. Also stores per-tf overall ranking.
    Resumable: each finished timeframe is written to playbook.json.partial; a restart skips finished tfs."""
    pb = {"ts": time.time(), "tfs": list(tfs), "table": {}, "best": {}}
    done_tfs = set()
    if resume and os.path.exists(PARTIAL):
        try:
            part = json.load(open(PARTIAL))
            if time.time() - part.get("ts", 0) < 3 * 86400:
                pb["table"] = part.get("table", {}); done_tfs = set(pb["table"].keys())
        except Exception:
            pass
    try:
        from core.audit import failed_ids
        bad = failed_ids()
        strategy_classes = [c for c in strategy_classes if c.id not in bad]
    except Exception:
        pass
    tot_s = len(strategy_classes)
    todo = [tf for tf in tfs if tf not in done_tfs]
    max_syms = int(os.environ.get("PB_MAX_SYMS", "0") or 0)        # compute cap for small machines / CI
    if max_syms:
        groups = {g: s[:max_syms] for g, s in groups.items()}
    for ti, tf in enumerate(todo):
        data = {}
        for g, syms in groups.items():
            for sym in syms:
                if progress:
                    progress(int(ti / max(len(todo), 1) * 100), f"data {sym} {tf}")
                try:
                    df = get_ohlcv(sym, tf, max_age_sec=6 * 3600)
                    if len(df) >= MIN_BARS[tf]:
                        data[(tf, g, sym)] = df.tail(MAX_BARS.get(tf, 12000))
                except Exception:
                    pass
        for si, cls in enumerate(strategy_classes):
            if progress:
                progress(int((ti + si / tot_s) / max(len(todo), 1) * 100), f"{tf} {cls.id}")
            for g in groups:
                trades = []; by_symbol = {}
                for sym in groups[g]:
                    df = data.get((tf, g, sym))
                    if df is None:
                        continue
                    try:
                        ts = _oos(df, cls)
                    except Exception:
                        continue
                    trades += ts; by_symbol[sym] = ts
                st = _stats(trades, by_symbol)
                if st:
                    pb["table"].setdefault(tf, {}).setdefault(g, {})[cls.id] = st
        pb["table"].setdefault(tf, {})
        try:
            json.dump(dict(ts=time.time(), table=pb["table"]), open(PARTIAL, "w"), default=float)
        except Exception:
            pass
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
                # breadth gates: must work on most symbols of the group and in most years (not one lucky market/regime)
                br = st.get("breadth") or {}
                if br.get("symbols", 0) >= 3 and br.get("symbols_pos", 0) < MIN_SYMBOL_BREADTH:
                    continue
                if br.get("years", 0) >= 2 and br.get("years_pos", 0) < MIN_YEAR_BREADTH:
                    continue
                score = min(st["pf_lo"], 3) * np.sqrt(min(st["n"], 200) / 200) * {"A": 1.0, "B": 0.9, "C": 0.7, "D": 0.5}[st["grade"]]
                score *= 0.5 + 0.5 * min(br.get("symbols_pos", 1.0), br.get("years_pos", 1.0))   # breadth-weighted
                rows.append((sid, round(float(score), 3), st))
            rows.sort(key=lambda r: -r[1])
            pb["best"].setdefault(tf, {})[g] = [(sid, sc) for sid, sc, _ in rows[:6]]
            # high win-rate subset (WR ≥ 50 % with lower-CI WR ≥ 45 %) — same proof gates, ranked by WR
            hw = [(sid, sc, st) for sid, sc, st in rows if st["wr"] >= 50 and st.get("wr_lo", st["wr"]) >= 45]
            hw.sort(key=lambda r: -r[2]["wr"])
            pb.setdefault("best_wr", {}).setdefault(tf, {})[g] = [(sid, round(float(st["wr"]), 1)) for sid, sc, st in hw[:6]]
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump(pb, open(PATH, "w"), indent=1, default=float)
    try:
        os.remove(PARTIAL)
    except Exception:
        pass
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


def proven_ids(tf=None):
    """set of strategy ids proven anywhere (or on a given tf) — used to hide unproven strategies from default pickers"""
    pb = load()
    if not pb:
        return set()
    out = set()
    for tf_, gd in pb.get("best", {}).items():
        if tf and tf_ != tf:
            continue
        for g, rows in gd.items():
            out.update(sid for sid, _ in rows)
    try:
        from core.audit import failed_ids
        out -= failed_ids()
    except Exception:
        pass
    return out


def proven_table():
    """flat rows for the Portfolio page: (tf, group, sid, score, stats)"""
    pb = load()
    rows = []
    if not pb:
        return rows
    for tf, gd in pb.get("best", {}).items():
        for g, lst in gd.items():
            for sid, sc in lst:
                rows.append((tf, g, sid, sc, pb["table"][tf][g][sid]))
    rows.sort(key=lambda r: -r[3])
    return rows
