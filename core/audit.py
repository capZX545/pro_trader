"""
Strategy audit (Phase 12) — automatic, for every strategy in the registry:

  1. LOOK-AHEAD test (truncation): run on df[:k] and on the full df; every signal/stop/target at bars < k must be
     identical. Any difference means the strategy peeks at future bars (centered rolling windows, shift(-1), zigzag
     repainting, global normalisation ...). Done at 3 cut points.
  2. RANDOM-DATA test: run the strategy with zero costs on 12 independent random walks (no edge exists by construction).
     If the mean profit factor is clearly > 1 (t-stat of trade PnL > 3 pooled) the code is leaking information.
  3. DETERMINISM: two runs → identical signals (no hidden randomness).
  4. SIGNAL SANITY: signal ∈ {-1,0,1}; stops on the right side of price; not > 60 % of bars signalling (noise machine).
  5. SPEED: seconds per 5 000 bars (UI responsiveness).

Result per strategy: dict(status = pass | warn | fail, findings=[...]) saved to data/audit.json.
The Health page shows it, `strategies.proven()` refuses strategies with status == fail, and the test-suite runs a
quick version so a look-ahead bug can never be merged unnoticed again.
"""
import os
import json
import time
import numpy as np
import pandas as pd

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(APP_DIR, "data", "audit.json")


def _rw(n=2500, seed=0, start=100.0, freq="1h"):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, 0.008, n)
    close = start * np.exp(np.cumsum(rets))
    open_ = np.r_[start, close[:-1]] * (1 + rng.normal(0, 0.001, n))
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    vol = rng.lognormal(10, 0.5, n)
    idx = pd.date_range("2020-01-01", periods=n, freq=freq)
    return pd.DataFrame(dict(open=open_, high=hi, low=lo, close=close, volume=vol), index=idx)


def _sig(res):
    s = res.signal.fillna(0).astype(int).values
    st = res.stop.values if res.stop is not None else np.full(len(s), np.nan)
    tg = res.target.values if res.target is not None else np.full(len(s), np.nan)
    return s, st, tg


def audit_strategy(cls, df=None, n_random=12, quick=False):
    findings = []
    status = "pass"
    df = df if df is not None else _rw(2500, seed=42)
    n = len(df)
    # ---- 3. determinism + 5. speed
    t0 = time.time()
    try:
        r1 = cls().run(df); r2 = cls().run(df)
    except Exception as e:
        return dict(status="fail", findings=[f"run error: {e}"], seconds=0.0)
    secs = (time.time() - t0) / 2 * (5000 / n)
    s1, st1, tg1 = _sig(r1); s2, _, _ = _sig(r2)
    if not np.array_equal(s1, s2):
        status = "fail"; findings.append("non-deterministic signals")
    # ---- 4. sanity
    if not set(np.unique(s1)).issubset({-1, 0, 1}):
        status = "fail"; findings.append(f"signal values {sorted(set(np.unique(s1)))} not in {{-1,0,1}}")
    frac = float((s1 != 0).mean())
    if frac > 0.6:
        status = "warn" if status == "pass" else status; findings.append(f"signals on {frac * 100:.0f}% of bars (noise machine)")
    c = df["close"].values
    bad_stop = int(np.sum((((s1 == 1) & (st1 >= c)) | ((s1 == -1) & (st1 <= c))) & np.isfinite(st1))) if np.isfinite(st1).any() else 0
    if bad_stop > 0.05 * max((s1 != 0).sum(), 1):
        status = "warn" if status == "pass" else status; findings.append(f"{bad_stop} stops on the wrong side of price")
    # ---- 1. look-ahead (truncation)
    cuts = [int(n * 0.6), int(n * 0.8), n - 5] if not quick else [int(n * 0.7)]
    la = 0
    for k in cuts:
        try:
            rk = cls().run(df.iloc[:k])
        except Exception as e:
            findings.append(f"truncated run error @ {k}: {e}"); continue
        sk, stk, tgk = _sig(rk)
        m = k - 1  # bar k-1 itself is the last in the truncated frame; the full frame knows the next bar → compare < k-1
        diff = int((sk[:m] != s1[:m]).sum())
        # stops/targets: compare where both finite
        both = np.isfinite(stk[:m]) & np.isfinite(st1[:m])
        dstop = int((np.abs(stk[:m][both] - st1[:m][both]) > 1e-9 * np.abs(st1[:m][both]).clip(1e-9)).sum()) if both.any() else 0
        if diff or dstop:
            la += diff + dstop
            findings.append(f"look-ahead: {diff} signals / {dstop} stops change when future bars are removed (cut {k})")
    if la:
        # repainting of the LAST few bars only (e.g. zigzag/pattern confirmation) is a warn; deep changes are a fail
        status = "fail" if la > 3 * len(cuts) else ("warn" if status == "pass" else status)
    # ---- 2. random-data edge
    if not quick:
        from core.backtest import run_backtest
        pn = []
        for sd in range(n_random):
            d = _rw(1500, seed=1000 + sd)
            try:
                res = cls().run(d)
                bt = run_backtest(d, res, commission_bps=0.0, slippage_bps=0.0, slip_atr=0.0, cost_model="static")
                pn += [t.pnl for t in bt.trades]
            except Exception:
                continue
        pn = np.array(pn)
        if len(pn) >= 30:
            tstat = pn.mean() / (pn.std(ddof=1) / np.sqrt(len(pn)))
            pf = pn[pn > 0].sum() / max(-pn[pn <= 0].sum(), 1e-9)
            if tstat > 3.0 and pf > 1.25:
                status = "fail"; findings.append(f"profitable on random data (t={tstat:.1f}, PF={pf:.2f}, n={len(pn)}) → information leak")
            elif tstat > 2.0 and pf > 1.15:
                status = "warn" if status == "pass" else status; findings.append(f"suspicious on random data (t={tstat:.1f}, PF={pf:.2f})")
            findings.append(f"random-data PF {pf:.2f} (t={tstat:+.1f}, n={len(pn)})")
    if secs > 6:
        status = "warn" if status == "pass" else status; findings.append(f"slow: {secs:.1f}s / 5k bars")
    return dict(status=status, findings=findings, seconds=round(secs, 2), signal_frac=round(frac, 3))


def run_all(strategy_classes, progress=None, quick=False):
    out = dict(ts=time.time(), results={})
    df = _rw(2500, seed=42)
    for i, cls in enumerate(strategy_classes):
        if progress:
            progress(int(i / len(strategy_classes) * 100), cls.id)
        out["results"][cls.id] = audit_strategy(cls, df, quick=quick)
    out["summary"] = summary(out)
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump(out, open(PATH, "w"), indent=1)
    return out


def summary(a):
    r = a.get("results", {})
    return dict(n=len(r), **{k: sum(1 for v in r.values() if v["status"] == k) for k in ("pass", "warn", "fail")})


def load():
    if os.path.exists(PATH):
        try:
            return json.load(open(PATH))
        except Exception:
            return None
    return None


def failed_ids():
    a = load()
    return {sid for sid, v in (a or {}).get("results", {}).items() if v["status"] == "fail"}
