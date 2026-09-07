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


def test_phase11_forecast_sentiment_rl_engines():
    import numpy as np, pandas as pd
    from core import forecast as F, sentiment as SE, rl as RL, engines as E
    rng = np.random.default_rng(0); n = 900
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    res = F.historical_forecasts(c, h=5, n_origins=8)
    assert set(["naive", "theta", "prophet_like"]).issubset(res.model) and (res.MASE > 0).all()
    df_s, agg = SE.score_headlines(["AAPL beats estimates, shares surge", "TSLA plunges after weak guidance"])
    assert df_s.compound.iloc[0] > 0 > df_s.compound.iloc[1] and "regime" in agg
    df = pd.DataFrame({"open": c, "high": c * 1.005, "low": c * 0.995, "close": c, "volume": 1.0}, index=pd.date_range("2024", periods=n, freq="h"))
    r, summ, curves = RL.train_and_evaluate(df, "q", episodes=3, seeds=(0,))
    assert len(r) == 1 and "random_p95" in summ and len(curves[0]) > 10
    import strategies as S
    sr = S.get("ema_cross").run(df)
    par = E.parity_check(df, sr)
    assert par["trade_count_gap"] == 0 and par["return_gap_pct"] < 2.0
    assert E.sqn_label(3.2) == "excellent"
