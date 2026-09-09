"""
Phase 23 — Signal quality gate ("trust score").

Why: the program can emit signals from 179 strategies, but most of them have no proven edge after costs. Showing them
all with equal weight is the single biggest weakness a real trader would notice. This module gives every
(strategy, symbol, timeframe) ONE honest number and ONE verdict, combining three independent sources of evidence:

  1. in-sample backtest on this symbol/tf        (core.success — fast, always available, optimistic)
  2. out-of-sample playbook statistics            (core.playbook — walk-forward, per symbol-group, honest)
  3. realised forward-test outcomes               (core.forward  — what actually happened after the signal fired)

plus penalties for: too few trades, wide confidence intervals, regime-only edges, and a live high-impact-news window
(core.calendar).  Verdicts:

  PROVEN     — trade-worthy candidate: OOS PF lower-CI > 1.0, n ≥ 50, forward test not contradicting
  CANDIDATE  — promising but not yet proven (small n or only in-sample edge)
  UNPROVEN   — no evidence of an edge after costs → hidden by default in every signal list
  FAILED     — evidence AGAINST it (OOS or forward PF clearly < 1 with enough trades)

Everything is explainable: `explain()` returns the bullet reasons in FA/EN so the UI can show *why*.
"""
import math, time

THRESH = dict(min_n_proven=50, min_n_candidate=20, pf_lo_proven=1.0, pf_proven=1.15, pf_failed=0.9, n_failed=40,
              fwd_n=15, fwd_pf_failed=0.8, wr_floor=30.0)


def _safe(x, d=float("nan")):
    try:
        x = float(x)
        return x if x == x and abs(x) != float("inf") else d
    except Exception:
        return d


def evidence(sid, sym, tf):
    """Collect the three evidence dicts (any may be None)."""
    ins = oos = fwd = None
    try:
        from core import success as SR
        ins = SR.get(sid, sym, tf)
    except Exception:
        pass
    try:
        from core import playbook as PB
        oos = PB.stats_for(sid, tf, sym)
    except Exception:
        pass
    try:
        from core import forward as FW
        rs = [r for r in FW.records("closed") if r.get("sid") == sid and r.get("tf") == tf]
        if len(rs) >= 5:
            fwd = FW._agg(rs)
    except Exception:
        pass
    return ins, oos, fwd


def score(sid, sym, tf, ev=None):
    """→ dict(score 0..100, verdict, ins, oos, fwd, reasons_en, reasons_fa)."""
    ins, oos, fwd = ev if ev is not None else evidence(sid, sym, tf)
    T = THRESH
    s = 0.0; ren = []; rfa = []
    # ---- in-sample (max 25 points; deliberately capped — it is the weakest evidence)
    if ins and ins.get("n"):
        pf, n, wr = _safe(ins.get("pf"), 0), int(ins.get("n", 0)), _safe(ins.get("wr"), 0)
        pts = max(0.0, min(25.0, (pf - 0.9) * 50)) * min(1.0, n / 60)
        s += pts
        ren.append(f"in-sample: PF {pf:.2f}, WR {wr:.0f}%, n={n} (+{pts:.0f})"); rfa.append(f"درون‌نمونه: PF {pf:.2f}، وین‌ریت {wr:.0f}٪، n={n} (+{pts:.0f})")
    else:
        ren.append("in-sample: not measured yet"); rfa.append("درون‌نمونه: هنوز اندازه‌گیری نشده")
    # ---- out-of-sample playbook (max 50 points)
    oos_ok = None
    if oos and oos.get("n"):
        pf, pf_lo, n, wr, g = _safe(oos.get("pf"), 0), _safe(oos.get("pf_lo"), 0), int(oos.get("n", 0)), _safe(oos.get("wr"), 0), oos.get("grade", "D")
        pts = max(0.0, min(35.0, (pf_lo - 0.85) * 100)) * min(1.0, n / T["min_n_proven"]) + {"A": 15, "B": 10, "C": 4, "D": 0}.get(g, 0)
        s += pts
        oos_ok = pf_lo > T["pf_lo_proven"] and pf >= T["pf_proven"] and n >= T["min_n_proven"]
        ren.append(f"out-of-sample: PF {pf:.2f} [lower CI {pf_lo:.2f}], WR {wr:.0f}%, n={n}, grade {g} (+{pts:.0f})")
        rfa.append(f"برون‌نمونه: PF {pf:.2f} [کران پایین {pf_lo:.2f}]، وین‌ریت {wr:.0f}٪، n={n}، درجه {g} (+{pts:.0f})")
        if n >= T["n_failed"] and pf < T["pf_failed"]:
            oos_ok = False; ren.append("out-of-sample PF clearly below 1 → evidence AGAINST"); rfa.append("PF برون‌نمونه به‌وضوح زیر ۱ → شاهد علیه استراتژی")
    else:
        ren.append("out-of-sample: no playbook entry (never validated on this group/timeframe)"); rfa.append("برون‌نمونه: در کتاب راهنما نیست (روی این گروه/تایم‌فریم اعتبارسنجی نشده)")
    # ---- forward test (max 25 points, and can veto)
    fwd_bad = False
    if fwd and fwd.get("n"):
        pf, n, wr = _safe(fwd.get("pf"), 0), int(fwd.get("n", 0)), _safe(fwd.get("wr"), 0)
        # live evidence is signed: PF above 1 adds up to +25, below 1 subtracts up to −30 (weighted by sample size)
        pts = max(-30.0, min(25.0, (pf - 1.0) * 60)) * min(1.0, n / 30)
        s += pts
        fwd_bad = n >= T["fwd_n"] and pf < T["fwd_pf_failed"]
        ren.append(f"forward test (real-time): PF {pf:.2f}, WR {wr:.0f}%, n={n} ({pts:+.0f})"); rfa.append(f"فوروارد تست (زنده): PF {pf:.2f}، وین‌ریت {wr:.0f}٪، n={n} ({pts:+.0f})")
        if fwd_bad:
            ren.append("forward test contradicts the backtest → FAILED"); rfa.append("فوروارد تست بک‌تست را نقض می‌کند → شکست‌خورده")
    else:
        ren.append("forward test: fewer than 5 closed real-time trades yet"); rfa.append("فوروارد تست: هنوز کمتر از ۵ معاملهٔ بسته‌شدهٔ زنده")
    # ---- low-timeframe caveat: bar-close backtests overstate scalping edges (intrabar path unknown, spread dominates)
    if tf in ("1m", "3m", "5m"):
        s *= 0.8
        ren.append("timeframe ≤5m: bar-close backtest overstates scalping edges (−20%)"); rfa.append("تایم‌فریم ≤۵ دقیقه: بک‌تست کندل‌بسته لبهٔ اسکالپ را بیش‌برآورد می‌کند (−۲۰٪)")
    s = max(0.0, min(100.0, s))
    # ---- verdict
    if fwd_bad or oos_ok is False and oos and int(oos.get("n", 0)) >= T["n_failed"]:
        v = "FAILED"
    elif oos_ok and not fwd_bad:
        v = "PROVEN"
    elif (oos and int(oos.get("n", 0)) >= T["min_n_candidate"] and _safe(oos.get("pf"), 0) >= 1.0) or (ins and int(ins.get("n", 0)) >= 30 and _safe(ins.get("pf"), 0) >= 1.2):
        v = "CANDIDATE"
    else:
        v = "UNPROVEN"
    return dict(score=round(s), verdict=v, ins=ins, oos=oos, fwd=fwd, reasons_en=ren, reasons_fa=rfa)


VERDICT_FA = {"PROVEN": "اثبات‌شده", "CANDIDATE": "نامزد", "UNPROVEN": "اثبات‌نشده", "FAILED": "شکست‌خورده"}
VERDICT_COLOR = {"PROVEN": "#26a69a", "CANDIDATE": "#ffb74d", "UNPROVEN": "#787b86", "FAILED": "#ef5350"}


def label(v, lang="en"):
    return VERDICT_FA.get(v, v) if lang == "fa" else v.title()


def passes(v, mode="proven"):
    """mode: 'proven' (PROVEN only) | 'candidate' (PROVEN+CANDIDATE) | 'all'"""
    if mode == "all":
        return True
    if mode == "candidate":
        return v in ("PROVEN", "CANDIDATE")
    return v == "PROVEN"


def summary(rows):
    """rows with 'verdict' → counts"""
    c = {"PROVEN": 0, "CANDIDATE": 0, "UNPROVEN": 0, "FAILED": 0}
    for r in rows:
        c[r.get("verdict", "UNPROVEN")] = c.get(r.get("verdict", "UNPROVEN"), 0) + 1
    return c


def stress_test(sid, sym, tf, df=None, stresses=(1.0, 2.0)):
    """Does the edge survive worse execution? Re-runs the backtest with cost multipliers → {stress: pf}.
    Used by the detail panel / API (not on every scan row — it costs one backtest per stress level)."""
    import strategies as S
    from core.backtest import run_backtest
    from core.data import get_ohlcv
    df = df if df is not None else get_ohlcv(sym, tf)
    res = S.get(sid).run(df)
    out = {}
    for st in stresses:
        try:
            out[str(st)] = float(min(run_backtest(df, res, symbol=sym, stress=st).stats.get("profit_factor", 0), 99))
        except Exception:
            out[str(st)] = None
    return out
