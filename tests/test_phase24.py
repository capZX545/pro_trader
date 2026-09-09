"""Phase 24 — edge analytics / trade plan (core.edge)."""
import numpy as np, pandas as pd, pytest
from core import edge as E
from core.data import generate_synthetic
import strategies as S
from core.backtest import run_backtest


@pytest.fixture(scope="module")
def df():
    return generate_synthetic(n=3000, seed=7)


@pytest.fixture(scope="module")
def bt(df):
    res = S.get("ema_cross").run(df)
    return res, run_backtest(df, res)


def test_regime_series_labels(df):
    r = E.regime_series(df)
    assert len(r) == len(df)
    assert set(r["kind"].unique()) <= {"trend", "range", "mixed"}
    assert set(r["bias"].unique()) <= {-1, 0, 1}
    cur = E.current_regime(df)
    assert cur["kind"] in ("trend", "range", "mixed")


def test_regime_fit_partitions_all_trades(df, bt):
    _, b = bt
    f = E.regime_fit(df, b.trades)
    n = len(b.trades)
    assert sum(f["by"][k]["n"] for k in ("trend", "range", "mixed")) == n
    assert sum(f["by"][k]["n"] for k in ("bull", "bear", "flat")) == n
    assert f["kind_fit"] in ("fits", "misfit", "neutral", "unknown")


def test_regime_fit_empty(df):
    f = E.regime_fit(df, [])
    assert f["kind_fit"] == "unknown" and f["by"]["trend"]["n"] == 0


def test_edge_decay(bt):
    _, b = bt
    d = E.edge_decay(b.trades)
    assert d["status"] in ("stable", "improving", "decayed", "unknown")
    assert E.edge_decay([])["status"] == "unknown"


def test_mc_next_trades_shape(bt):
    _, b = bt
    m = E.mc_next_trades(b.trades, risk_pct=1.0, n_sims=500)
    assert 0 <= m["prob_loss"] <= 100
    assert m["ret_p5"] <= m["ret_med"] <= m["ret_p95"]
    assert 0 <= m["dd_p95"] <= 100
    assert m["streak_p95"] >= 1
    # more risk → bigger drawdown
    m2 = E.mc_next_trades(b.trades, risk_pct=3.0, n_sims=500)
    assert m2["dd_p95"] > m["dd_p95"]


def test_mc_too_few():
    assert E.mc_next_trades([])["n_src"] == 0


class _T:
    def __init__(self, r): self.r_multiple = r; self.pnl_pct = r; self.pnl = r; self.bars = 5


def test_suggested_risk_positive_edge():
    trades = [_T(2.0) if i % 2 == 0 else _T(-1.0) for i in range(60)]        # WR 50%, b=2 → Kelly 25%
    fit = dict(kind_fit="fits"); htf = dict(aligned=True); decay = dict(status="stable")
    s = E.suggested_risk(trades, 80, fit, htf, decay, cap_pct=1.0)
    assert abs(s["kelly_full"] - 25.0) < 1e-6
    assert s["kelly_quarter"] == pytest.approx(6.25)
    assert s["risk_pct"] == 1.0                                              # capped
    s2 = E.suggested_risk(trades, 80, dict(kind_fit="misfit"), htf, decay)
    assert s2["risk_pct"] == 0.0
    s3 = E.suggested_risk(trades, 80, fit, dict(aligned=False), dict(status="decayed"))
    assert 0 < s3["risk_pct"] < s["risk_pct"]


def test_suggested_risk_negative_edge():
    trades = [_T(1.0) if i % 3 == 0 else _T(-1.0) for i in range(60)]        # WR 33%, b=1 → negative Kelly
    s = E.suggested_risk(trades, 80, dict(kind_fit="fits"), dict(aligned=True), dict(status="stable"))
    assert s["risk_pct"] == 0.0 and s["kelly_full"] == 0.0


def test_suggested_risk_few_trades():
    s = E.suggested_risk([_T(1)] * 5, 90, dict(kind_fit="fits"), dict(aligned=True), dict(status="stable"))
    assert s["risk_pct"] == 0.0


def test_htf_alignment_from_df():
    idx = pd.date_range("2024-01-01", periods=400, freq="4h")
    up = pd.DataFrame({"open": np.arange(400.0), "high": np.arange(400.0) + 1, "low": np.arange(400.0) - 1, "close": np.arange(400.0) + 100, "volume": 1.0}, index=idx)
    h = E.htf_alignment("X", "1h", 1, df_htf=up)
    assert h["tf"] == "4h" and h["bias"] == 1 and h["aligned"] is True
    assert E.htf_alignment("X", "1h", -1, df_htf=up)["aligned"] is False
    assert E.htf_alignment("X", "1mo", 1)["aligned"] is None


def test_trade_plan_end_to_end(df, bt, monkeypatch):
    res, b = bt
    monkeypatch.setattr(E, "htf_alignment", lambda *a, **k: dict(tf="4h", bias=0, slope_pct=0.0, aligned=None))
    p = E.trade_plan("SYN", "1h", "ema_cross", df=df, res=res, bt=b, equity=5000)
    assert p["side"] in (1, -1)
    assert (p["stop"] < p["entry"] < p["tp2"]) if p["side"] == 1 else (p["stop"] > p["entry"] > p["tp2"])
    assert p["tp1"] == pytest.approx(p["entry"] + p["side"] * abs(p["entry"] - p["stop"]))
    assert p["verdict_en"] in ("GO", "REDUCED", "NO-TRADE")
    assert p["position"]["risk_amount"] == pytest.approx(5000 * p["size"]["risk_pct"] / 100)
    assert "ورود" in p["text_fa"] and "Entry" in p["text_en"]
    import json; json.dumps(p, default=str)


def test_trade_plan_no_signal(df):
    res = S.get("ema_cross").run(df)
    res.signal[:] = 0
    p = E.trade_plan("SYN", "1h", "ema_cross", df=df, res=res)
    assert p.get("error") == "no signal"


def test_cluster_risk_no_pairs():
    assert E.cluster_risk([dict(sym="A", side=1)]) == []


def test_api_plan_route():
    from core import webapp as W
    assert "/api/plan" in W.ROUTES and "/api/cluster" in W.ROUTES
