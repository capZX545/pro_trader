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


def test_phase11_vision2_understand():
    import os
    from core import vision2 as V2
    p = os.path.join(os.path.dirname(__file__), "vision_samples", "tv_channel.png")
    det = V2.PatternDetector.load()
    if det is None:
        det = V2.PatternDetector(); det.train(n_per_class=15)
    u = V2.understand(p, detector=det)
    assert u["calibration"] is not None and 70_000 < u["df"]["close"].iloc[-1] < 95_000   # axis OCR: BTC ≈ 83k
    kinds = {l["kind"] for l in u["overlays"]["lines"]}
    assert "trendline_down" in kinds                                                       # the drawn channel
    assert u["numeric"]["trend"] == "down"
    top = u["whole_chart"][0][0]
    assert top in ("triangle_desc", "wedge_falling", "channel_down", "downtrend", "triangle_sym", "none")


def test_phase11_analyst_grounded():
    from core import analyst as AN, vision as V
    import pandas as pd, numpy as np
    rng = np.random.default_rng(1); c = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.01, 150)))
    df = pd.DataFrame(dict(open=c, high=c * 1.004, low=c * 0.996, close=c, volume=1.0))
    num = V.analyse_chart(df)
    ctx = dict(vision=dict(numeric=num, df=df, image_patterns=[], overlays=dict(lines=[], curves=[]), calibration=None), calibrated=True)
    txt, meta = AN.report(ctx, "fa")
    assert "سوگیری" in txt and -1 <= meta["score"] <= 1
    ans, be = AN.ask("روند چیه؟", ctx, "fa")
    assert "روند" in ans and be in ("rules", "local-llm")
    assert AN._side(-1) == -1 and AN._side("bull") == 1


def test_phase12_audit_quick():
    """look-ahead + determinism + sanity on 12 representative strategies (fast); full run: python -m core.audit"""
    import strategies as S
    from core import audit as A
    ids = ["ema_cross", "supertrend", "turtle", "rsi_div", "ichimoku", "bollinger_mr", "vwap_reversion", "zigzag_hs", "macd_hist", "connors_rsi2", "donchian_breakout", "keltner_pullback"]
    cls = [S.REGISTRY[i] for i in ids if i in S.REGISTRY] or S.ALL_STRATEGIES[:12]
    df = A._rw(1500, seed=7)
    for c in cls:
        r = A.audit_strategy(c, df, quick=True)
        assert r["status"] != "fail", (c.id, r["findings"])


def test_phase12_costs_and_catalog():
    from core.costs import dynamic_costs, cost_summary
    from core import audit as A
    df = A._rw(600, seed=3)
    d = dynamic_costs(df, "EUR/USD")
    assert len(d["spread_half"]) == len(df) and (d["spread_half"] > 0).all()
    assert cost_summary(df, "BTC/USDT")["round_trip_bps"] > 5
    from core.indicator_uses import coverage
    n, m = coverage()
    assert n >= 80 and m == n
    from core.backtest import run_backtest
    import strategies as S
    res = S.get("ema_cross").run(df)
    a = run_backtest(df, res, symbol="BTC/USDT", cost_model="static").stats["return_pct"]
    b = run_backtest(df, res, symbol="BTC/USDT", stress=3.0).stats["return_pct"]
    assert b <= a + 1e-9   # stressed dynamic costs can never beat static baseline


def test_phase12_alerts_offline():
    from core import alerts as AL
    ok, msg = AL.telegram_send("x", token="", chat_id="")
    assert not ok
    body = AL.format_signal("BTC/USDT", "4h", "ema_cross", 1, 100.0, 95.0, 110.0, 70, dict(pf=1.3, wr=48, n=120), "en")
    assert "LONG" in body and "R:R 2.0" in body


def test_phase12_vision_real_screenshots():
    """real MetaTrader / TradingView / Binance-app screenshots: candle count within ±20 % of the hand count"""
    from core.vision import real_report
    rep = real_report()
    scored = [r for r in rep if r["ok"] is not None]
    assert scored, "real chart set missing"
    bad = [(r["file"], r["found"], r["expected"]) for r in scored if not r["ok"]]
    assert len(bad) <= 1, bad     # allow one flaky image


def test_phase14_sources_offline_shapes():
    """multi-venue source layer: frame builder + venue ordering/health logic (no network)."""
    from core import sources
    df = sources._frame([(1_700_000_000_000, "1", "2", "0.5", "1.5", "10"), (1_700_003_600_000, 1.5, 2.5, 1.0, 2.0, 5)])
    assert list(df.columns) == ["open", "high", "low", "close", "volume"] and len(df) == 2 and df.index.is_monotonic_increasing
    assert df.index.tz is None and df.close.iloc[-1] == 2.0
    names = [n for n, _ in sources._order()]
    assert set(names) == {n for n, _ in sources.VENUES}
    assert sources.TF_SECONDS["1h"] == 3600 and sources.TF_SECONDS["1d"] == 86400
    st = sources.venue_status(); assert "health" in st and "active" in st


def test_phase14_live_bar_update_logic():
    """ChartWidget.update_last_bar semantics on a plain DataFrame (in-place update vs append vs stale)."""
    import pandas as pd
    from core.data import generate_synthetic
    df = generate_synthetic(50)
    last = df.index[-1]
    # same timestamp → in place
    df.iloc[-1, df.columns.get_indexer(["open", "high", "low", "close", "volume"])] = [1, 2, 0.5, 1.5, 3]
    assert df.close.iloc[-1] == 1.5 and len(df) == 50
    # newer timestamp → append
    ts = last + (df.index[-1] - df.index[-2])
    df.loc[ts, ["open", "high", "low", "close", "volume"]] = [1.5, 1.6, 1.4, 1.55, 1]
    assert len(df) == 51 and df.index[-1] == ts


def test_phase18_indicator_strategies_and_success():
    import strategies as S
    from strategies.indicator_signals import INDICATOR_STRATEGIES
    assert len(INDICATOR_STRATEGIES) == 31 and all(c.id in S.REGISTRY for c in INDICATOR_STRATEGIES)
    from core import indicators2 as t2, success as SR, clock
    df = generate_synthetic(3000)
    assert t2.zigzag(df, 2.0).notna().sum() >= 4
    for cls in INDICATOR_STRATEGIES:
        r = cls().run(df)
        assert len(r.signal) == len(df), cls.id
    d = SR.compute("halftrend_flip", "TEST", "1h", df)
    assert d is not None and SR.get("halftrend_flip", "TEST", "1h")["n"] == d["n"]
    assert SR.label("halftrend_flip", "TEST", "1h", short=True).endswith("%")
    assert "UTC" in clock.world_line()


def test_phase19_world_masters():
    import strategies as S
    from strategies.world_masters import WORLD_STRATEGIES
    assert len(WORLD_STRATEGIES) == 16 and all(c.id in S.REGISTRY for c in WORLD_STRATEGIES)
    df = generate_synthetic(3000)
    for cls in WORLD_STRATEGIES:
        r = cls().run(df); assert len(r.signal) == len(df), cls.id
        assert cls.description_fa and cls.rules_fa and cls.description_en and cls.rules_en, cls.id
    from core import library as L
    assert any("Chan Lun" in b[0] for b in L.BOOKS)


def test_phase20_web_and_qr():
    import json, urllib.request, threading, time
    from core import webapp, qr
    M = qr.matrix("http://192.168.1.10:8765"); assert len(M) in (25, 29) and M[0][0] == 1
    url, port = webapp.start(port=18765, host="127.0.0.1")
    try:
        for ep in ("/api/meta", "/api/clock", "/api/symbols", "/api/strategies?sym=BTC/USDT&tf=1h&lang=fa", "/", "/manifest.webmanifest"):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{ep}", timeout=30) as r:
                assert r.status == 200, ep
                body = r.read()
                if ep.startswith("/api"):
                    d = json.loads(body); assert "error" not in d, (ep, d)
        d = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/meta").read())
        assert d["strategies"] >= 179 and "fa" in d["langs"]
    finally:
        webapp.stop()
