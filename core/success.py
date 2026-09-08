"""Success-rate registry (Phase 18): one number the user can trust next to EVERY signal.

For (strategy_id, symbol, tf) we keep {wr, pf, n, exp_r, ts} computed by the real backtester on the cached history
(fees included). It is filled lazily by whoever shows a signal (chart page, scanner, live radar, fast signals) and in
bulk by `precompute()` (maintenance / Settings ▸ "compute success rates"). Two layers are reported:
  • in-sample WR/PF on this exact symbol/timeframe (this file), and
  • out-of-sample playbook WR with confidence interval when the playbook has that (strategy, tf, asset group).
`label()` formats both for tables: "38% · PF 1.12 · n=214" (+ " | OOS 41% [35–47]").
"""
import json, os, threading, time
import numpy as np
from core.paths import data as _data

PATH = _data("success.json")
_lock = threading.Lock()
_cache = None
MAX_AGE = 7 * 86400


def _load():
    global _cache
    if _cache is None:
        try:
            _cache = json.load(open(PATH))
        except Exception:
            _cache = {}
    return _cache


def _save():
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        tmp = PATH + ".tmp"
        json.dump(_cache, open(tmp, "w"))
        os.replace(tmp, PATH)
    except Exception:
        pass


def key(sid, sym, tf):
    return f"{sid}|{sym}|{tf}"


def get(sid, sym, tf):
    with _lock:
        return _load().get(key(sid, sym, tf))


def put(sid, sym, tf, stats):
    """stats: backtest .stats dict (or dict with win_rate/profit_factor/trades)."""
    d = dict(wr=float(stats.get("win_rate", 0)), pf=float(min(stats.get("profit_factor", 0), 99)), n=int(stats.get("trades", 0)),
             exp_r=float(stats.get("avg_r", stats.get("expectancy_r", 0)) or 0), ts=time.time())
    with _lock:
        _load()[key(sid, sym, tf)] = d
        if len(_cache) % 25 == 0:
            _save()
    return d


def flush():
    with _lock:
        _save()


def compute(sid, sym, tf, df=None, bars=15000):
    """Backtest now (blocking) and store. Returns the stats dict or None."""
    try:
        import strategies as S
        from core.backtest import run_backtest
        if df is None:
            from core.data import get_ohlcv
            df = get_ohlcv(sym, tf)
        df = df.tail(bars)
        res = S.REGISTRY[sid]().run(df)
        st = run_backtest(df, res, symbol=sym).stats
        return put(sid, sym, tf, st)
    except Exception:
        return None


def get_or_compute(sid, sym, tf, df=None, max_age=MAX_AGE):
    d = get(sid, sym, tf)
    if d and time.time() - d.get("ts", 0) < max_age:
        return d
    return compute(sid, sym, tf, df)


def oos(sid, sym, tf):
    try:
        from core import playbook as PB
        return PB.stats_for(sid, tf, sym)
    except Exception:
        return None


def label(sid, sym, tf, df=None, compute_missing=False, short=False):
    """'38% · PF 1.12 · n=214' (+ OOS). Empty string when unknown and compute_missing is False."""
    d = get(sid, sym, tf)
    if d is None and compute_missing:
        d = compute(sid, sym, tf, df)
    parts = []
    if d and d.get("n"):
        parts.append(f"{d['wr']:.0f}%" if short else f"{d['wr']:.0f}% · PF {d['pf']:.2f} · n={d['n']}")
    o = oos(sid, sym, tf)
    if o:
        parts.append(f"OOS {o['wr']:.0f}%" if short else f"OOS {o['wr']:.0f}% [{o['wr_lo']:.0f}–{o['wr_hi']:.0f}] · PF {o['pf']:.2f} · {o.get('grade', '')}")
    return " | ".join(parts)


def grade_color(d):
    """traffic light for a stats dict: PF ≥ 1.2 & n ≥ 30 green, PF ≥ 1.0 yellow, else red."""
    if not d or not d.get("n"):
        return "muted"
    if d["pf"] >= 1.2 and d["n"] >= 30:
        return "green"
    if d["pf"] >= 1.0:
        return "yellow"
    return "red"


def precompute(symbols=("BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"), tfs=("15m", "1h", "4h", "1d"), sids=None,
               progress=None, stop=None, bars=12000):
    """Bulk fill for the default universe (≈ 160 strategies × 5 symbols × 4 tfs ≈ 3 200 backtests ≈ 10–20 min on a laptop)."""
    import strategies as S
    from core.data import get_ohlcv
    from core.backtest import run_backtest
    sids = list(sids or S.REGISTRY.keys())
    total = len(symbols) * len(tfs); k = 0
    for sym in symbols:
        for tf in tfs:
            k += 1
            if stop is not None and stop():
                flush(); return
            if progress:
                progress(int(100 * k / total), f"{sym} {tf}")
            try:
                df = get_ohlcv(sym, tf).tail(bars)
            except Exception:
                continue
            for sid in sids:
                d = get(sid, sym, tf)
                if d and time.time() - d.get("ts", 0) < MAX_AGE:
                    continue
                try:
                    st = run_backtest(df, S.REGISTRY[sid]().run(df), symbol=sym).stats
                    put(sid, sym, tf, st)
                except Exception:
                    pass
            flush()
    if progress:
        progress(100, "done")


def summary():
    """Aggregate per strategy across everything computed: mean WR, mean PF, share of (sym,tf) with PF>1 — for the Academy table."""
    _load()
    agg = {}
    for k, d in _cache.items():
        sid = k.split("|")[0]
        a = agg.setdefault(sid, dict(n_cells=0, wr=[], pf=[], pos=0, n=0))
        if d.get("n", 0) < 10:
            continue
        a["n_cells"] += 1; a["wr"].append(d["wr"]); a["pf"].append(d["pf"]); a["pos"] += d["pf"] > 1; a["n"] += d["n"]
    out = {}
    for sid, a in agg.items():
        if a["n_cells"]:
            out[sid] = dict(cells=a["n_cells"], wr=float(np.mean(a["wr"])), pf=float(np.median(a["pf"])), pos_share=a["pos"] / a["n_cells"], n=a["n"])
    return out
