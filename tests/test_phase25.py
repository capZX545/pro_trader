"""Phase 25 — trading-desk briefing (core.desk) + meta-strategy recursion guard."""
import numpy as np, pytest
from core import desk as D


def _plan(sym, side, risk, trust=80):
    return dict(sym=sym, tf="1d", sid="x", side=side, ago=0, entry=100.0, stop=95.0, tp2=110.0, rr=2.0, name_en="X", name_fa="ایکس",
                trust=dict(score=trust, verdict="PROVEN"), size=dict(risk_pct=risk, note_en="", note_fa=""), avoid_en=[], avoid_fa=[],
                verdict_en="GO", verdict_fa="ورود")


def test_allocate_caps_total(monkeypatch):
    from core import edge as E
    monkeypatch.setattr(E, "cluster_risk", lambda rows, tf="1d": [])
    plans = [_plan("A", 1, 1.0), _plan("B", 1, 1.0), _plan("C", 1, 1.0), _plan("D", 1, 1.0)]
    out = D.allocate(plans, open_risk_pct=0.5)          # budget 2.5
    assert [p["alloc_pct"] for p in out] == [1.0, 1.0, 0.5, 0.0]
    assert out[2]["alloc_note"] == "cut" and out[3]["alloc_note"] == "cap"


def test_allocate_halves_correlated(monkeypatch):
    from core import edge as E
    monkeypatch.setattr(E, "cluster_risk", lambda rows, tf="1d": [dict(symbols=["A", "B"], side=1, avg_corr=0.9)])
    out = D.allocate([_plan("A", 1, 1.0), _plan("B", 1, 1.0), _plan("C", -1, 1.0)], open_risk_pct=0.0)
    assert out[0]["alloc_pct"] == 1.0 and out[0]["cluster"]["halved"] is False
    assert out[1]["alloc_pct"] == 0.5 and out[1]["cluster"]["halved"] is True
    assert out[2]["cluster"] is None and out[2]["alloc_pct"] == 1.0


def test_open_positions_streak(monkeypatch):
    import pandas as pd
    from core import forward as FW
    now = pd.Timestamp.utcnow().tz_localize(None)
    closed = [dict(status="closed", r=-1.0, exit_time=(now - pd.Timedelta(minutes=1)).isoformat(), bar="3"),
              dict(status="closed", r=-0.5, exit_time=(now - pd.Timedelta(minutes=2)).isoformat(), bar="2"),
              dict(status="closed", r=2.0, exit_time=(now - pd.Timedelta(days=3)).isoformat(), bar="1")]
    monkeypatch.setattr(FW, "records", lambda status=None: closed if status == "closed" else [])
    rows, open_risk, today_loss, consec, last_h = D.open_positions()
    assert rows == [] and open_risk == 0.0 and consec == 2 and today_loss == pytest.approx(1.5) and 0 <= last_h < 1


def test_render_both_languages():
    b = dict(ts=0, took=0.1, news=None, upcoming=[], gate=dict(ok=False, reasons_en=["daily loss limit hit"], reasons_fa=["سقف ضرر روزانه"]),
             open_risk_pct=1.0, today_loss_pct=3.0, consec_losses=1, positions=[], regimes={"crypto": dict(symbol="BTC/USDT", price=1.0, kind="trend", bias=1, chg_pct=1.0)},
             plans=[dict(_plan("BTC/USDT", 1, 1.0), alloc_pct=0.0, alloc_note="cap", cluster=None)], rejected=2,
             decay=[dict(sid="s", symbol="BTC/USDT", tf="4h", pf_recent=0.8, pf_all=1.2, status="decayed")],
             forward=dict(n_closed=0, verdict="collecting", gap_pf=None), total_alloc_pct=0.0)
    fa, en = D.render(b, "fa"), D.render(b, "en")
    assert "⛔" in fa and "⛔" in en and "سقف ضرر" in fa and "daily loss" in en
    assert "decayed" in en and "فرسوده" in fa and "BTC/USDT" in en


def test_meta_strategies_do_not_nest():
    """ensemble ↔ regime_ensemble used to recurse forever (found by the desk scan)."""
    import strategies as S
    from core.data import generate_synthetic
    df = generate_synthetic(n=800, seed=3)
    df.attrs.update(symbol="BTC/USDT", tf="1d")
    import signal as _sg
    for sid in ("ensemble", "regime_ensemble"):
        if sid in S.REGISTRY:
            r = S.get(sid).run(df)
            assert len(r.signal) == len(df)
    ens = S.REGISTRY["ensemble"]()
    ids = ens.members(df)
    assert "regime_ensemble" not in ids and "ensemble" not in ids


def test_api_desk_route():
    from core import webapp as W
    assert "/api/desk" in W.ROUTES
