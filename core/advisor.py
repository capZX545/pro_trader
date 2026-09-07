"""
Advisor — "right strategy, right timeframe, right moment, fastest answer".

advise(symbol, timeframes) → for each timeframe the proven strategies (playbook) are run on fresh data; returns the
best actionable signal per timeframe plus a cross-timeframe verdict:
  • regime per TF (trend/range via ADX + Choppiness), HTF bias (1d/4h EMA50-200)
  • only strategies proven OOS on this TF & asset group (playbook) AND not domain-locked (validation) are considered
  • freshness: signals older than `max_age_bars` are discarded (a 5m signal from 2 hours ago is worthless)
  • delivery time: expected hold in minutes, and the next bar close (when the next decision can be made)
  • confidence 0–100 = playbook PF & WR, agreement with HTF bias, confluence across TFs, freshness
Speed: data is cached; strategies are the ~5 proven ones per TF, not all 63 → answer in ~1–3 s per symbol.
"""
import time
import numpy as np
import pandas as pd

from core.data import get_ohlcv
from core.backtest import run_backtest
from core import indicators as ta
from core import playbook as PB
from core import validation as V

TF_MIN = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720, "1d": 1440, "3d": 4320, "1wk": 10080, "1mo": 43200}
MAX_AGE = {"1m": 3, "3m": 2, "5m": 2, "15m": 2, "30m": 2, "1h": 2, "2h": 1, "4h": 1, "6h": 1, "12h": 1, "1d": 1, "3d": 1, "1wk": 1, "1mo": 1}   # bars


def regime(df):
    adx, _, _ = ta.adx(df)
    from core.indicators2 import choppiness
    ch = choppiness(df).iloc[-1]
    a = adx.iloc[-1]
    e50, e200 = ta.ema(df.close, 50).iloc[-1], ta.ema(df.close, 200).iloc[-1]
    px = df.close.iloc[-1]
    bias = 1 if px > e50 > e200 else (-1 if px < e50 < e200 else 0)
    kind = "trend" if (a > 25 and ch < 55) else ("range" if (a < 20 or ch > 61.8) else "mixed")
    return dict(adx=float(a), chop=float(ch), bias=bias, kind=kind, atr_pct=float(ta.atr(df).iloc[-1] / px * 100))


def next_close_minutes(df, tf):
    last = df.index[-1]
    now = pd.Timestamp.utcnow().tz_localize(None)
    step = pd.Timedelta(minutes=TF_MIN[tf])
    nxt = last + step
    while nxt < now:
        nxt += step
    return max(0.0, (nxt - now).total_seconds() / 60)


def advise(symbol, timeframes=("1m", "5m", "15m", "30m", "1h", "2h", "4h", "12h", "1d", "1wk"), k=5, progress=None, record=True):
    import strategies as S
    out = {"symbol": symbol, "ts": time.time(), "tfs": {}, "verdict": None}
    htf_bias = 0
    # HTF bias from daily (fallback 4h)
    for tf in ("1d", "4h"):
        try:
            d = get_ohlcv(symbol, tf)
            htf_bias = regime(d)["bias"]
            break
        except Exception:
            continue
    out["htf_bias"] = htf_bias
    all_sigs = []
    for tf in timeframes:
        if progress:
            progress(tf)
        try:
            df = get_ohlcv(symbol, tf)
        except Exception as e:
            out["tfs"][tf] = dict(error=str(e)[:80])
            continue
        if len(df) < 300:
            out["tfs"][tf] = dict(error="not enough history")
            continue
        rg = regime(df)
        cands = PB.best_for(tf, symbol, k=k)
        if not cands:
            out["tfs"][tf] = dict(regime=rg, signal=None, note="no strategy proven on this timeframe/asset — bot stays flat",
                                  next_close_min=next_close_minutes(df, tf))
            continue
        n = len(df)
        best = None
        for sid, sc, st in cands:
            if not V.allowed(sid, symbol, tf, min_oos_pf=1.0):
                continue
            cls = S.REGISTRY.get(sid)
            if not cls:
                continue
            try:
                res = cls().run(df)
            except Exception:
                continue
            sig = res.signal.values
            idx = np.where(sig[-(MAX_AGE[tf] + 1):] != 0)[0]
            if len(idx) == 0:
                continue
            i = n - (MAX_AGE[tf] + 1) + idx[-1]
            side = int(sig[i])
            if getattr(cls, "bt_kwargs", {}).get("allow_short") is False and side == -1:
                continue
            px = float(df.close.values[i])
            sl = float(res.stop.values[i]) if res.stop is not None and res.stop.values[i] == res.stop.values[i] else float("nan")
            tp = float(res.target.values[i]) if res.target is not None and res.target.values[i] == res.target.values[i] else float("nan")
            rr = abs(tp - px) / abs(px - sl) if sl == sl and tp == tp and px != sl else 0.0
            ago = n - 1 - i
            agree = 1.0 if side == htf_bias else (0.5 if htf_bias == 0 else 0.0)
            reg_fit = 1.0 if (cls.category in ("Trend", "Bot-Ported", "Ensemble") and rg["kind"] == "trend") or \
                             (cls.category in ("Mean-Reversion", "High Win-Rate") and rg["kind"] != "trend") else 0.6
            conf = (min(st["pf"], 2.5) / 2.5 * 35 + st["wr"] / 100 * 20 + agree * 20 + reg_fit * 10 + (1 - ago / (MAX_AGE[tf] + 1)) * 15)
            rule_exit = res.exit_long is not None
            # chase guard: how far the market already moved from the signal close (in R). >0.5R → entry is worse than tested
            last_px = float(df.close.values[-1])
            rpu = abs(px - sl) if sl == sl and px != sl else float("nan")
            chase_r = ((last_px - px) * side / rpu) if rpu == rpu and rpu > 0 else 0.0
            chase_r = float(chase_r)
            # honest confidence: shrink toward the LOWER confidence bound and penalise small samples / grade
            pf_lo = st.get("pf_lo", st["pf"]) if st.get("pf_lo", 0) == st.get("pf_lo", 0) else st["pf"] * 0.7
            wr_lo = st.get("wr_lo", st["wr"])
            gpen = {"A": 1.0, "B": 0.9, "C": 0.75, "D": 0.5}.get(st.get("grade", "D"), 0.5)
            conf = (min(pf_lo, 2.5) / 2.5 * 35 + wr_lo / 100 * 20 + agree * 20 + reg_fit * 10 + (1 - ago / (MAX_AGE[tf] + 1)) * 15) * gpen
            d = dict(sid=sid, name=cls.name_en, name_fa=cls.name_fa, side=side, ago=ago, px=px, sl=sl, tp=tp, rr=rr,
                     pb_wr=st["wr"], pb_pf=st["pf"], pb_n=st["n"], pb_wr_lo=wr_lo, pb_pf_lo=pf_lo, grade=st.get("grade", "D"),
                     hold_min=st["hold"] * TF_MIN[tf], conf=float(conf), rule_exit=rule_exit, category=cls.category,
                     bar=df.index[i].isoformat(), stop_pct=abs(px - sl) / px * 100 if sl == sl else float("nan"),
                     chase_r=chase_r, last_px=last_px, chase_ok=chase_r <= 0.5)
            if chase_r > 0.5:
                d["conf"] *= 0.6   # already ran away: still shown, but heavily discounted and flagged
            all_sigs.append((tf, d))
            if best is None or d["conf"] > best["conf"]:
                best = d
        out["tfs"][tf] = dict(regime=rg, signal=best, next_close_min=next_close_minutes(df, tf), last=float(df.close.iloc[-1]),
                              signal_bar=best["bar"] if best else None, last_bar=df.index[-1].isoformat(),
                              candidates=[(sid, st["wr"], st["pf"], st.get("grade", "D"), st["n"]) for sid, sc, st in cands])
    # cross-TF verdict
    longs = [d["conf"] for tf, d in all_sigs if d["side"] == 1]
    shorts = [d["conf"] for tf, d in all_sigs if d["side"] == -1]
    if not all_sigs:
        out["verdict"] = dict(action="wait", reason="no fresh proven signal on any timeframe", conf=0)
    else:
        side = 1 if sum(longs) >= sum(shorts) else -1
        pool = longs if side == 1 else shorts
        conf = float(np.mean(pool)) + 5 * (len(pool) - 1) - 10 * len(shorts if side == 1 else longs)
        conf = float(np.clip(conf, 0, 100))
        fastest = min((tf for tf, d in all_sigs if d["side"] == side), key=lambda x: TF_MIN[x])
        best_tf = max((tf for tf, d in all_sigs if d["side"] == side), key=lambda x: out["tfs"][x]["signal"]["conf"] if out["tfs"][x]["signal"] else 0)
        out["verdict"] = dict(action="long" if side == 1 else "short", conf=conf, n_tfs=len(pool), against=len(shorts if side == 1 else longs),
                              fastest_tf=fastest, best_tf=best_tf, htf_bias=htf_bias)
    # auto forward-test log (never trades; just remembers what it said, so reality can grade it later)
    if record:
        try:
            from core import forward as FW
            out["recorded"] = FW.record_from_advice(out)
        except Exception:
            out["recorded"] = 0
    return out
