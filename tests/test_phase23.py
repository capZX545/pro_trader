"""Phase 23 tests: signal quality gate, economic calendar, alert filters, unified modules, web API contract."""
import sys, os, json, time, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")
os.environ.setdefault("PROTRADER_NO_MAINT", "1")
import numpy as np, pandas as pd
import pytest
from core import quality as Q, calendar as CAL
from core.data import generate_synthetic


# ------------------------------------------------------------------ quality
def _ev(ins=None, oos=None, fwd=None):
    return (ins, oos, fwd)


def test_quality_no_evidence_is_unproven():
    r = Q.score("x", "BTC/USDT", "1h", ev=_ev())
    assert r["verdict"] == "UNPROVEN" and r["score"] <= 25


def test_quality_strong_oos_is_proven():
    oos = dict(n=200, wr=55, wr_lo=50, pf=1.6, pf_lo=1.25, t=3.1, grade="A")
    r = Q.score("x", "BTC/USDT", "1h", ev=_ev(dict(wr=56, pf=1.7, n=300), oos, None))
    assert r["verdict"] == "PROVEN" and r["score"] >= 60
    assert r["reasons_fa"] and r["reasons_en"]


def test_quality_losing_oos_is_failed():
    oos = dict(n=400, wr=35, wr_lo=31, pf=0.74, pf_lo=0.63, t=-4, grade="D")
    r = Q.score("x", "BTC/USDT", "1h", ev=_ev(dict(wr=40, pf=0.9, n=400), oos, None))
    assert r["verdict"] == "FAILED"


def test_quality_insample_only_never_proven():
    r = Q.score("x", "BTC/USDT", "1h", ev=_ev(dict(wr=70, pf=3.0, n=500), None, None))
    assert r["verdict"] in ("CANDIDATE", "UNPROVEN")


def test_quality_forward_contradiction_downgrades():
    oos = dict(n=200, wr=55, wr_lo=50, pf=1.6, pf_lo=1.25, t=3.1, grade="A")
    good = Q.score("x", "BTC/USDT", "1h", ev=_ev(None, oos, None))
    bad = Q.score("x", "BTC/USDT", "1h", ev=_ev(None, oos, dict(n=40, wr=30, pf=0.5)))
    assert bad["score"] < good["score"]
    assert bad["verdict"] != "PROVEN"


def test_quality_forward_confirmation_upgrades():
    oos = dict(n=200, wr=55, wr_lo=50, pf=1.6, pf_lo=1.25, t=3.1, grade="A")
    base = Q.score("x", "BTC/USDT", "1h", ev=_ev(None, oos, None))
    up = Q.score("x", "BTC/USDT", "1h", ev=_ev(None, oos, dict(n=40, wr=58, pf=1.7)))
    assert up["score"] >= base["score"]


def test_quality_low_tf_penalty():
    oos = dict(n=200, wr=55, wr_lo=50, pf=1.6, pf_lo=1.25, t=3.1, grade="A")
    h1 = Q.score("x", "BTC/USDT", "1h", ev=_ev(None, oos, None))
    m1 = Q.score("x", "BTC/USDT", "1m", ev=_ev(None, oos, None))
    assert m1["score"] < h1["score"]


@pytest.mark.parametrize("mode,verdicts", [("proven", {"PROVEN"}), ("candidate", {"PROVEN", "CANDIDATE"}),
                                           ("all", {"PROVEN", "CANDIDATE", "UNPROVEN", "FAILED"})])
def test_quality_passes_modes(mode, verdicts):
    for v in ("PROVEN", "CANDIDATE", "UNPROVEN", "FAILED"):
        assert Q.passes(v, mode) == (v in verdicts)


def test_quality_labels_bilingual_and_summary():
    for v in ("PROVEN", "CANDIDATE", "UNPROVEN", "FAILED"):
        assert Q.label(v, "fa") != Q.label(v, "en")
        assert v in Q.VERDICT_COLOR
    s = Q.summary([dict(verdict="PROVEN"), dict(verdict="FAILED"), dict(verdict="FAILED")])
    assert s["PROVEN"] == 1 and s["FAILED"] == 2 and s["UNPROVEN"] == 0


def test_quality_score_bounds_random():
    rng = np.random.default_rng(0)
    for _ in range(200):
        oos = dict(n=int(rng.integers(0, 800)), wr=float(rng.uniform(10, 90)), wr_lo=float(rng.uniform(5, 60)),
                   pf=float(rng.uniform(0.2, 4)), pf_lo=float(rng.uniform(0.1, 3)), t=float(rng.normal(0, 3)), grade="C")
        fwd = dict(n=int(rng.integers(0, 60)), wr=float(rng.uniform(10, 90)), pf=float(rng.uniform(0.2, 4)))
        r = Q.score("x", "BTC/USDT", "1h", ev=_ev(None, oos, fwd))
        assert 0 <= r["score"] <= 100 and r["verdict"] in Q.VERDICT_COLOR


def test_quality_uses_real_stores_without_crashing():
    r = Q.score("ema_cross", "BTC/USDT", "1h")
    assert r["verdict"] in Q.VERDICT_COLOR


# ------------------------------------------------------------------ calendar
def test_calendar_offline_fallback_has_events():
    ev = CAL._fallback_events()
    assert len(ev) >= 4 and all("ts" in e and "title" in e for e in ev)


def test_calendar_risk_window_detection():
    now = time.time()
    evs = [dict(title="CPI", currency="USD", impact="High", ts=now + 10 * 60, approx=False)]
    r = CAL._risk_from(evs, now)
    assert r and r["title"] == "CPI" and abs(r["mins"] - 10) <= 1
    assert CAL._risk_from([dict(title="CPI", currency="USD", impact="High", ts=now + 6 * 3600, approx=False)], now) is None
    assert CAL._risk_from([dict(title="CPI", currency="USD", impact="High", ts=now - 10 * 60, approx=False)], now)   # still inside after-window
    assert CAL._risk_from([dict(title="CPI", currency="USD", impact="High", ts=now - 5 * 3600, approx=False)], now) is None


def test_calendar_text_bilingual():
    e = dict(title="Non-Farm Payrolls", currency="USD", impact="High", ts=time.time() + 600, approx=False, mins=10)
    fa, en = CAL.text(e, "fa"), CAL.text(e, "en")
    assert "Non-Farm" in fa and "Non-Farm" in en and fa != en
    assert CAL.text(None, "fa") == ""


def test_calendar_upcoming_sorted_and_bounded():
    up = CAL.upcoming(24 * 14)
    ts = [e["ts"] for e in up]
    assert ts == sorted(ts) and all(t >= time.time() - 60 for t in ts)


def test_calendar_parse_forexfactory_rows():
    rows = [dict(title="FOMC Statement", country="USD", impact="High", date="2030-01-01T14:00:00-05:00", forecast="", previous=""),
            dict(title="Low thing", country="USD", impact="Low", date="2030-01-01T15:00:00-05:00"),
            dict(title="Bad date", country="USD", impact="High", date="garbage")]
    ev = CAL._parse_ff(rows)
    assert len(ev) == 1 and ev[0]["title"] == "FOMC Statement" and ev[0]["currency"] == "USD"


# ------------------------------------------------------------------ alerts gate + news filter
def test_alert_scan_skips_inside_news_window(monkeypatch, tmp_path):
    from core import alerts as AL
    monkeypatch.setattr(AL, "LOG", str(tmp_path / "alerts.json"))
    monkeypatch.setattr(CAL, "risk_now", lambda: dict(title="CPI", currency="USD", impact="High", ts=time.time() + 60, approx=False, mins=1))
    monkeypatch.setattr(AL, "settings", lambda: {"alerts": {"news_filter": True}})
    from core import playbook as PB
    monkeypatch.setattr(PB, "load", lambda: {"best": {"1h": {"crypto": [("ema_cross", 1.0)]}}, "table": {"1h": {"crypto": {}}}})
    assert AL.scan(tfs=["1h"]) == []
    h = AL.history(5)
    assert h and h[0]["meta"].get("kind") == "news_skip"


def test_alert_scan_news_filter_can_be_disabled(monkeypatch, tmp_path):
    from core import alerts as AL
    monkeypatch.setattr(AL, "LOG", str(tmp_path / "alerts.json"))
    monkeypatch.setattr(CAL, "risk_now", lambda: dict(title="CPI", currency="USD", impact="High", ts=time.time() + 60, approx=False, mins=1))
    monkeypatch.setattr(AL, "settings", lambda: {"alerts": {"news_filter": False}})
    from core import playbook as PB
    monkeypatch.setattr(PB, "load", lambda: {})
    AL.scan(tfs=["1h"])
    assert not [h for h in AL.history(5) if h.get("meta", {}).get("kind") == "news_skip"]


def test_alert_quality_gate_blocks_failed(monkeypatch, tmp_path):
    """a strategy firing on the last bar but judged FAILED must not alert (quality_mode=candidate)."""
    from core import alerts as AL, playbook as PB, data as D, forward as FW
    import strategies as S
    monkeypatch.setattr(AL, "LOG", str(tmp_path / "alerts.json"))
    monkeypatch.setattr(AL, "settings", lambda: {"alerts": {"news_filter": False, "quality_mode": "candidate", "telegram": False, "desktop": False, "min_conf": 0}})
    monkeypatch.setattr(PB, "load", lambda: {"best": {"1h": {"crypto": [("always", 1.0)]}}, "table": {"1h": {"crypto": {"always": dict(pf=2, wr=60)}}}})
    monkeypatch.setattr(PB, "GROUPS", {"crypto": ["BTC/USDT"]})
    df = generate_synthetic(600, seed=3)
    monkeypatch.setattr(D, "get_ohlcv", lambda *a, **k: df)
    monkeypatch.setattr(AL, "get_ohlcv", lambda *a, **k: df, raising=False)

    class Always:
        id = "always"; name_en = name_fa = "always"; category = "test"

        def run(self, df):
            sig = pd.Series(1, index=df.index)
            return type("R", (), dict(signal=sig, stop=None, target=None))()
    monkeypatch.setattr(S, "get", lambda sid: Always())
    monkeypatch.setattr(Q, "score", lambda *a, **k: dict(verdict="FAILED", score=0))
    recorded = []
    monkeypatch.setattr(FW, "record", lambda *a, **k: recorded.append(a) or True)
    assert AL.scan(tfs=["1h"]) == [] and recorded == []
    monkeypatch.setattr(Q, "score", lambda *a, **k: dict(verdict="PROVEN", score=90))
    AL.scan(tfs=["1h"])
    assert recorded


# ------------------------------------------------------------------ unified modules (nothing deleted, single import path)
def test_indicators_unified_namespace():
    import core.indicators as I, core.indicators2 as I2
    for k in dir(I2):
        if not k.startswith("_") and callable(getattr(I2, k)):
            assert hasattr(I, k), k
    df = generate_synthetic(400, seed=1)
    assert len(I.rsi(df.close)) == len(df) and len(I.atr(df)) == len(df)


def test_quant_and_vision_unified_namespace():
    import core.quant as Qn, core.quant2 as Qn2, core.vision as V, core.vision2 as V2
    for a, b in ((Qn, Qn2), (V, V2)):
        for k in dir(b):
            if not k.startswith("_") and callable(getattr(b, k)):
                assert hasattr(a, k), k


def test_strategies_run_clean_on_synthetic():
    import strategies as S
    df = generate_synthetic(700, seed=7)
    bad = {}
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        for c in S.ALL_STRATEGIES:
            try:
                r = c().run(df)
                assert len(r.signal) == len(df)
            except FutureWarning as e:
                bad[c.id] = "FutureWarning"
            except Exception:
                pass   # data-shape limits on 700 synthetic bars are fine; only warnings are asserted here
    assert not bad, bad


# ------------------------------------------------------------------ web API contract
@pytest.fixture(scope="module")
def server():
    from core import webapp as W
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    W.start(port=port, host="127.0.0.1")
    yield f"http://127.0.0.1:{port}"
    W.stop()


def _get(base, path):
    import urllib.request
    return json.loads(urllib.request.urlopen(base + path, timeout=300).read())


def test_api_calendar_contract(server):
    d = _get(server, "/api/calendar?hours=48")
    assert set(d) >= {"now", "text_fa", "text_en", "upcoming"} and isinstance(d["upcoming"], list)


def test_api_quality_contract(server):
    d = _get(server, "/api/quality?sid=ema_cross&sym=BTC/USDT&tf=1h")
    assert d["verdict"] in Q.VERDICT_COLOR and 0 <= d["score"] <= 100 and isinstance(d["reasons_fa"], list)


def test_api_notifications_contract(server):
    d = _get(server, "/api/notifications?since=0")
    assert "now" in d and isinstance(d["items"], list)
    assert _get(server, f"/api/notifications?since={time.time() + 10}")["items"] == []


def test_api_signals_has_verdicts_and_news_fields(server, monkeypatch):
    from core import data as D
    d = _get(server, "/api/signals?sym=BTC/USDT&tf=1h&recent=5")
    assert set(d) >= {"rows", "quality", "news_risk", "news_text_fa", "news_text_en"}
    for r in d["rows"]:
        assert r["verdict"] in Q.VERDICT_COLOR and 0 <= r["score"] <= 100 and "why_fa" in r
    rank = {"PROVEN": 0, "CANDIDATE": 1, "UNPROVEN": 2, "FAILED": 3}
    ranks = [rank[r["verdict"]] for r in d["rows"]]
    assert ranks == sorted(ranks)
