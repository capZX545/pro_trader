"""Walk-forward optimisation of the Fast-Signals confluence rule per symbol/timeframe (Phase 16 round 2).

Instead of fitting 20 strategies' parameters (overfit heaven), we fit only the 4 knobs of the confluence rule:
    min_votes ∈ {2,3,4}, window ∈ {2,3,5}, sl_atr ∈ {1.5,2.5,3.5}, rr ∈ {1.2,1.5,2.0}
on rolling in-sample windows and evaluate the chosen combination on the following out-of-sample window
(anchored walk-forward, Davey-style). The report gives OOS trades/WR/PF and Walk-Forward-Efficiency so the user can see
whether a symbol has *any* persistent low-timeframe confluence edge. Results are cached in data/scalp_wfo.json and used
by the Fast Signals page as the default knobs for that symbol."""
import itertools, json, os, time
import numpy as np
import pandas as pd

from core.paths import data as _data
from core import fastsignals as F

PATH = _data("scalp_wfo.json")
GRID = dict(min_votes=[2, 3, 4], window=[2, 3, 5], sl_atr=[1.5, 2.5, 3.5], rr=[1.2, 1.5, 2.0])


def _bt(df, M, votes, window, sl_atr, rr, bps):
    from core.backtest import run_backtest
    from strategies.base import StrategyResult
    sig, _, _ = F.confluence_signal(df, M, min_votes=votes, window=window)
    st, tp, _ = F.stops_for(df, sig, sl_atr=sl_atr, rr=rr)
    r = run_backtest(df, StrategyResult(sig, st, tp), max_bars=60, commission_bps=bps / 2 * 0.8, slippage_bps=bps / 2 * 0.2, cost_model="static")
    return r.stats


def _score(st):
    n = st.get("trades", 0)
    if n < 15:
        return -1
    return min(st["profit_factor"], 3) * np.sqrt(min(n, 150) / 150) - 0.01 * st.get("max_dd_pct", 0)


def walk_forward(df, sym, fee_tier="fut_taker", n_folds=4, progress=None):
    bps = F.ROUND_TRIP_BPS[fee_tier]
    M = F.votes_frame(df)
    n = len(df)
    edges = np.linspace(int(n * 0.35), n, n_folds + 1).astype(int)
    combos = list(itertools.product(GRID["min_votes"], GRID["window"], GRID["sl_atr"], GRID["rr"]))
    oos_trades, oos_pf_num, oos_pf_den, folds = 0, 0.0, 0.0, []
    is_pf, oos_pf = [], []
    for k in range(n_folds):
        a, b = edges[k], edges[k + 1]
        ins = slice(0, a); oos = slice(max(0, a - 300), b)
        best, best_sc = None, -9
        for j, (v, w, sl, rr) in enumerate(combos):
            if progress and j % 20 == 0:
                progress(int(100 * (k * len(combos) + j) / (n_folds * len(combos))), f"{sym} fold {k + 1}/{n_folds}")
            st = _bt(df.iloc[ins], M.iloc[ins], v, w, sl, rr, bps)
            sc = _score(st)
            if sc > best_sc:
                best, best_sc, best_st = (v, w, sl, rr), sc, st
        if best is None:
            continue
        st_o = _bt(df.iloc[oos], M.iloc[oos], *best, bps)
        folds.append(dict(fold=k + 1, params=dict(zip(("min_votes", "window", "sl_atr", "rr"), best)),
                          is_n=int(best_st["trades"]), is_pf=round(float(best_st["profit_factor"]), 2), is_wr=round(float(best_st["win_rate"]), 1),
                          oos_n=int(st_o["trades"]), oos_pf=round(float(st_o["profit_factor"]), 2), oos_wr=round(float(st_o["win_rate"]), 1), oos_ret=round(float(st_o["return_pct"]), 2)))
        oos_trades += int(st_o["trades"])
        is_pf.append(best_st["profit_factor"]); oos_pf.append(st_o["profit_factor"] if st_o["trades"] else np.nan)
    if not folds:
        return None
    # consensus params = most frequent choice across folds
    from collections import Counter
    cnt = Counter(json.dumps(f["params"], sort_keys=True) for f in folds)
    params = json.loads(cnt.most_common(1)[0][0])
    oos_pf_mean = float(np.nanmean(oos_pf)) if np.isfinite(np.nanmean(oos_pf)) else 0.0
    wfe = float(oos_pf_mean / np.mean(is_pf)) if np.mean(is_pf) > 0 else 0.0
    verdict = "edge" if (oos_pf_mean >= 1.1 and oos_trades >= 30 and wfe >= 0.5) else ("weak" if oos_pf_mean >= 0.95 else "none")
    return dict(sym=sym, fee_tier=fee_tier, ts=time.time(), params=params, folds=folds, oos_trades=oos_trades,
                oos_pf=round(oos_pf_mean, 2), is_pf=round(float(np.mean(is_pf)), 2), wfe=round(wfe, 2), verdict=verdict)


def load():
    try:
        return json.load(open(PATH))
    except Exception:
        return {}


def save(d):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump(d, open(PATH, "w"), indent=1)


def run(symbols=("BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"), tf="5m", fee_tier="fut_taker", bars=20000, progress=None, stop=None):
    from core.data import get_ohlcv
    out = load()
    for i, sym in enumerate(symbols):
        if stop is not None and stop():
            break
        try:
            df = get_ohlcv(sym, tf).tail(bars)
            df.attrs.update(symbol=sym, tf=tf)
            r = walk_forward(df, sym, fee_tier, progress=lambda p, m: progress and progress(int((i + p / 100) / len(symbols) * 100), m))
            if r:
                out[f"{sym}|{tf}|{fee_tier}"] = r
                save(out)
        except Exception as e:
            out[f"{sym}|{tf}|{fee_tier}"] = dict(sym=sym, error=str(e)[:120], ts=time.time())
    if progress:
        progress(100, "done")
    return out


def params_for(sym, tf, fee_tier="fut_taker"):
    r = load().get(f"{sym}|{tf}|{fee_tier}")
    return (r or {}).get("params"), (r or {}).get("verdict")
