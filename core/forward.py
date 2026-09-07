"""
Forward-Test engine — the only scientific answer to "does the bot really work?".

• record(): every fresh signal the Advisor / Scanner / Live engine produces is written to data/forward.json
  (symbol, tf, strategy, side, entry, stop, target, bar time, backtest expectation at that moment).
  Duplicate (symbol, tf, strategy, bar) is ignored, so re-running the Advisor does not double-count.
• update(): later, fresh candles are fetched and each open record is resolved exactly like the backtester would
  (gap → stop at open, stop before target inside a bar, time-stop after max_bars, rule/reverse ignored → we track
  pure stop/target/time outcome, which is what a human following the signal would do).
• report(): realised WR / PF / expectancy with confidence intervals, split by strategy and timeframe, and the
  "backtest vs reality" gap. The gap is what tells you how much to discount every backtest number.

Nothing here places orders. It's a lab notebook that fills itself in.
"""
import json
import os
import time
import threading
import numpy as np
import pandas as pd

from core.data import get_ohlcv
from core.costs import cost_for

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(APP_DIR, "data", "forward.json")
_lock = threading.Lock()
MAX_BARS = 200
TF_MIN = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440, "1wk": 10080}


def _load():
    if os.path.exists(PATH):
        try:
            return json.load(open(PATH, encoding="utf-8"))
        except Exception:
            pass
    return {"records": [], "created": time.time()}


def _save(d):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0, default=float)
    os.replace(tmp, PATH)


def _key(r):
    return f"{r['symbol']}|{r['tf']}|{r['sid']}|{r['bar']}"


def record(symbol, tf, sid, side, bar_time, entry, stop, target, source="advisor", expect=None, conf=None):
    """Store a signal. Returns True if new. `bar_time` = close time of the signal bar (ISO or Timestamp)."""
    if stop != stop or target != target or entry != entry or side == 0:
        return False
    bar = pd.Timestamp(bar_time).isoformat()
    r = dict(symbol=symbol, tf=tf, sid=sid, side=int(side), bar=bar, entry=float(entry), stop=float(stop),
             target=float(target), source=source, ts=time.time(), status="open", expect=expect or {}, conf=conf,
             exit=None, exit_time=None, reason=None, pnl_pct=None, r=None, bars=0, mfe_r=0.0, mae_r=0.0)
    with _lock:
        d = _load()
        keys = {_key(x) for x in d["records"]}
        if _key(r) in keys:
            return False
        d["records"].append(r)
        _save(d)
    return True


def record_from_advice(advice):
    """Convenience: feed the dict returned by core.advisor.advise()."""
    n = 0
    for tf, blk in advice.get("tfs", {}).items():
        s = blk.get("signal") if isinstance(blk, dict) else None
        if not s:
            continue
        bar = blk.get("signal_bar") or blk.get("last_bar")
        if bar is None:
            continue
        ok = record(advice["symbol"], tf, s["sid"], s["side"], bar, s["px"], s["sl"], s["tp"], source="advisor",
                    expect=dict(wr=s.get("pb_wr"), pf=s.get("pb_pf"), n=s.get("pb_n")), conf=s.get("conf"))
        n += int(ok)
    return n


def _resolve(r, df):
    """Walk bars after the signal bar; apply backtester fill rules. Mutates r; returns True if closed."""
    bar = pd.Timestamp(r["bar"])
    if df.index.tz is not None:
        df = df.tz_localize(None)
    after = df[df.index > bar]
    if after.empty:
        return False
    side, sp, tp = r["side"], r["stop"], r["target"]
    cm = cost_for(r["symbol"])
    cost = (cm["commission_bps"] + cm["slippage_bps"]) / 10_000
    # entry at next open (same as backtester)
    if r.get("fill") is None:
        o0 = float(after.open.iloc[0])
        r["fill"] = o0 * (1 + cost * side)
        r["fill_time"] = after.index[0].isoformat()
    fill = r["fill"]
    rpu = abs(fill - sp) or 1e-9
    o, h, l, c = after.open.values, after.high.values, after.low.values, after.close.values
    for i in range(len(after)):
        fav = (h[i] - fill) if side == 1 else (fill - l[i])
        adv = (fill - l[i]) if side == 1 else (h[i] - fill)
        r["mfe_r"] = max(r["mfe_r"], fav / rpu)
        r["mae_r"] = max(r["mae_r"], adv / rpu)
        r["bars"] = i + 1
        px = reason = None
        if (side == 1 and o[i] < sp) or (side == -1 and o[i] > sp):
            px, reason = o[i], "stop(gap)"
        elif (side == 1 and l[i] <= sp) or (side == -1 and h[i] >= sp):
            px, reason = sp, "stop"
        elif (side == 1 and h[i] >= tp) or (side == -1 and l[i] <= tp):
            px, reason = tp, "target"
        elif i + 1 >= MAX_BARS:
            px, reason = c[i], "time"
        if px is not None:
            px_eff = px * (1 - cost * side)
            r["exit"] = float(px_eff)
            r["exit_time"] = after.index[i].isoformat()
            r["reason"] = reason
            r["pnl_pct"] = float((px_eff - fill) / fill * 100 * side)
            r["r"] = float((px_eff - fill) * side / rpu)
            r["status"] = "closed"
            return True
    # still open: mark to market
    r["pnl_pct"] = float((c[-1] - fill) / fill * 100 * side)
    r["r"] = float((c[-1] - fill) * side / rpu)
    return False


def update(progress=None, max_age_sec=120):
    """Resolve open records with fresh data. Returns (n_checked, n_closed)."""
    with _lock:
        d = _load()
    open_recs = [r for r in d["records"] if r["status"] == "open"]
    groups = {}
    for r in open_recs:
        groups.setdefault((r["symbol"], r["tf"]), []).append(r)
    closed = 0
    for k, (key, recs) in enumerate(groups.items()):
        if progress:
            progress(int(k / max(len(groups), 1) * 100), f"{key[0]} {key[1]}")
        try:
            df = get_ohlcv(key[0], key[1], max_age_sec=max_age_sec)
        except Exception:
            continue
        for r in recs:
            try:
                if _resolve(r, df):
                    closed += 1
            except Exception:
                continue
    with _lock:
        d2 = _load()
        by = {_key(r): r for r in d["records"]}
        d2["records"] = [by.get(_key(r), r) for r in d2["records"]]
        d2["last_update"] = time.time()
        _save(d2)
    return len(open_recs), closed


def records(status=None):
    d = _load()
    rs = d["records"]
    if status:
        rs = [r for r in rs if r["status"] == status]
    return sorted(rs, key=lambda r: r["bar"], reverse=True)


def _agg(rs):
    from core.stats import full_report
    p = np.array([r["pnl_pct"] for r in rs if r["pnl_pct"] is not None], float)
    rep = full_report(p) if len(p) else dict(n=0, wr=0, wr_lo=0, wr_hi=0, pf=0, pf_lo=float("nan"), pf_hi=float("nan"), t=0, grade="D", exp=0)
    rep["avg_r"] = float(np.mean([r["r"] for r in rs if r["r"] is not None])) if rs else 0.0
    rep["exp_wr"] = float(np.mean([r["expect"].get("wr") for r in rs if r.get("expect", {}).get("wr")])) if rs else float("nan")
    rep["exp_pf"] = float(np.mean([min(r["expect"].get("pf"), 5) for r in rs if r.get("expect", {}).get("pf")])) if rs else float("nan")
    rep["reasons"] = {k: sum(1 for r in rs if r["reason"] == k) for k in ("target", "stop", "stop(gap)", "time")}
    return rep


def report():
    """Overall + per strategy + per tf + per symbol realised statistics, and the backtest→reality gap."""
    rs = records("closed")
    op = records("open")
    out = dict(n_closed=len(rs), n_open=len(op), overall=_agg(rs), by_sid={}, by_tf={}, by_symbol={},
               first=min([r["bar"] for r in rs + op], default=None), last_update=_load().get("last_update"))
    for keyname, field in (("by_sid", "sid"), ("by_tf", "tf"), ("by_symbol", "symbol")):
        for v in sorted({r[field] for r in rs}):
            out[keyname][v] = _agg([r for r in rs if r[field] == v])
    o = out["overall"]
    if o["n"] >= 10 and o["exp_pf"] == o["exp_pf"] and o["exp_pf"] > 0:
        out["gap_pf"] = o["pf"] / o["exp_pf"]           # 1.0 = reality matches backtest; 0.6 = 40% worse
        out["gap_wr"] = o["wr"] - o["exp_wr"]            # percentage points
    else:
        out["gap_pf"] = out["gap_wr"] = None
    # verdict text
    if o["n"] < 30:
        out["verdict"] = "collecting"
    elif o["pf_lo"] == o["pf_lo"] and o["pf_lo"] > 1.0:
        out["verdict"] = "edge_confirmed"
    elif o["pf"] > 1.0:
        out["verdict"] = "positive_unconfirmed"
    else:
        out["verdict"] = "no_edge"
    return out


def clear():
    with _lock:
        _save({"records": [], "created": time.time()})
