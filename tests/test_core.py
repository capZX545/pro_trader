"""Fast regression tests (no GUI): every strategy runs, stats/CI/grade sane, forward-test round trip, health quick check."""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
import strategies as S
from core.data import generate_synthetic
from core.backtest import run_backtest
from core import stats as ST, forward as FW, health as H, portfolio as P, costs as CO

def test_all_strategies_run():
    df = generate_synthetic(1500)
    df.attrs.update(symbol="BTC/USDT", tf="1d")
    bad = []
    for cls in S.ALL_STRATEGIES:
        try:
            r = cls().run(df); assert len(r.signal) == len(df)
            run_backtest(df, r)
        except Exception as e:
            bad.append((cls.id, str(e)))
    assert not bad, bad

def test_stats():
    rng = np.random.default_rng(0)
    p = rng.normal(0.3, 1, 200)
    rep = ST.full_report(p)
    assert rep["n"] == 200 and 0 <= rep["wr_lo"] <= rep["wr"] <= rep["wr_hi"] <= 100
    assert rep["pf_lo"] <= rep["pf"] <= rep["pf_hi"]
    assert rep["grade"] in "ABCD"
    assert ST.required_t() > 3.5
    assert ST.grade(20, 2.0, 5) == "D"       # small n is never A

def test_costs():
    assert CO.asset_class("BTC/USDT") == "crypto" and CO.asset_class("EUR/USD") == "forex"
    assert CO.cost_for("BTC/USDT")["commission_bps"] > CO.cost_for("EUR/USD")["commission_bps"]

def test_forward_roundtrip(tmp_path=None):
    import core.forward as F
    old = F.PATH; F.PATH = "/tmp/_fw_test.json"
    try:
        F.clear()
        df = generate_synthetic(400, seed=3)
        bar = df.index[100]
        px = float(df.close.iloc[100]); sl = px * 0.97; tp = px * 1.06
        assert F.record("BTC/USDT", "1d", "rsi2", 1, bar, px, sl, tp) is True
        assert F.record("BTC/USDT", "1d", "rsi2", 1, bar, px, sl, tp) is False   # dedupe
        r = F.records()[0]
        closed = F._resolve(r, df)
        assert closed and r["reason"] in ("stop", "stop(gap)", "target", "time") and r["r"] is not None
        rep = F.report(); assert rep["verdict"] == "collecting" or rep["n_closed"] == 0
    finally:
        F.PATH = old

def test_portfolio():
    sig = [dict(symbol="BTC/USDT", side=1, entry=100, stop=95, conf=70), dict(symbol="BTC/USDT", side=1, entry=100, stop=95, conf=60)]
    out = P.allocate(sig, max_total_risk=0.6, risk_pct=0.5)
    assert out[0]["take"] and not out[1]["take"]

def test_health_quick():
    fs = H.run_checks(quick=True)
    assert all(f.severity in ("error", "warn", "info") for f in fs)

if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v(); print("PASS", k)
