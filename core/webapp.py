"""Web / mobile module (Phase 20): the SAME engine as the desktop app served over HTTP so a phone or any browser on the
network (or the internet via a tunnel / VPS) can use it. Zero extra dependencies — Python's ThreadingHTTPServer — so it
ships unchanged inside the PyInstaller release.

    python main.py --web            # headless server on 0.0.0.0:8765
    Settings ▸ Web & mobile ▸ Start # inside the desktop app (same process, shares caches & success rates)

Endpoints (JSON):  /api/meta  /api/symbols  /api/strategies?sym&tf  /api/ohlcv?sym&tf&n  /api/run?sym&tf&sid&n
                   /api/signals?sym&tf  /api/advise?sym  /api/fast?tf  /api/library  /api/clock  /api/success?sid&sym&tf
Static UI:         /  (web/index.html — mobile-first, FA/EN, canvas candlestick chart with signals, hover/tap success %)
"""
import json, os, sys, threading, time, traceback, math
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(getattr(sys, "_MEIPASS", ROOT), "web")
DEFAULT_PORT = int(os.environ.get("PROTRADER_WEB_PORT", "8765"))
_server = None
_thread = None
_cache = {}
_lock = threading.Lock()


def _clean(x):
    """make numpy/pandas/NaN JSON-safe"""
    import numpy as np
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if (x != x or x in (float("inf"), float("-inf"))) else float(x)
    if isinstance(x, np.ndarray):
        return _clean(x.tolist())
    if isinstance(x, (bytes, bytearray)):
        return None
    if hasattr(x, "to_dict") and hasattr(x, "index"):          # pandas Series / DataFrame
        try:
            if hasattr(x, "columns"):
                return _clean(x.reset_index().to_dict("records")[-500:])
            return _clean({str(k): v for k, v in x.tail(500).items()}) if not str(x.index.dtype).startswith("int") else _clean(x.tail(500).tolist())
        except Exception:
            return None
    if isinstance(x, (bool, int, str)) or x is None:
        return x
    if hasattr(x, "isoformat"):
        return x.isoformat()
    if hasattr(x, "item"):
        try:
            return _clean(x.item())
        except Exception:
            pass
    return x


def _ts_list(idx):
    import pandas as pd
    return [int(pd.Timestamp(t).timestamp()) for t in idx]


# ------------------------------------------------------------------------------------------ API implementations
def api_meta(q):
    import strategies as S
    from core import clock
    return dict(app="ProTrader", version=_version(), strategies=len(S.REGISTRY), categories=S.CATEGORIES, tz=clock.tz_name(),
                langs=["en", "fa"], tfs=["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk"])


def _version():
    try:
        for line in open(os.path.join(ROOT, "RELEASE_NOTES.md"), encoding="utf-8"):
            if line.startswith("## v"):
                return line.split()[1]
    except Exception:
        pass
    return "dev"


def api_symbols(q):
    from core.data import UNIVERSE
    return {cat: list(d.keys()) for cat, d in UNIVERSE.items()}


def api_strategies(q):
    import strategies as S
    from core import success as SR
    sym, tf, lang = q.get("sym", "BTC/USDT"), q.get("tf", "1h"), q.get("lang", "en")
    out = []
    for c in S.ALL_STRATEGIES:
        d = SR.get(c.id, sym, tf); o = SR.oos(c.id, sym, tf)
        out.append(dict(id=c.id, name=c.name_fa if lang == "fa" else c.name_en, category=c.category, author=c.author, difficulty=c.difficulty,
                        timeframes=c.timeframes, description=c.description_fa if lang == "fa" else c.description_en,
                        rules=c.rules_fa if lang == "fa" else c.rules_en, params=c.params,
                        success=d, oos=o, label=SR.label(c.id, sym, tf, short=True)))
    return out


def _df(sym, tf, n):
    from core.data import get_ohlcv
    key = (sym, tf)
    with _lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[0] < 60:
        df = hit[1]
    else:
        df = get_ohlcv(sym, tf)
        with _lock:
            _cache[key] = (time.time(), df)
    return df.tail(int(n)) if n else df


def api_chart_config(q):
    """TradingView-style chart config: type, indicators, drawings"""
    return dict(
        chart_types=["candle", "line", "area", "heikin", "renko"],
        timeframes=["1m","3m","5m","15m","30m","1h","2h","4h","6h","12h","1d","1wk","1mo"],
        drawing_tools=["cursor","trend","hline","vline","ray","rect","fib","measure","text"],
        indicators_count=73,
    )

def api_ohlcv(q):
    df = _df(q.get("sym", "BTC/USDT"), q.get("tf", "1h"), q.get("n", 600))
    return dict(t=_ts_list(df.index), o=df.open.round(8).tolist(), h=df.high.round(8).tolist(), l=df.low.round(8).tolist(),
                c=df.close.round(8).tolist(), v=df.volume.round(2).tolist(), venue=df.attrs.get("venue", ""), stale=bool(df.attrs.get("stale", False)))


def api_run(q):
    """strategy on symbol/tf: candles (last n), signals with entry/SL/TP, overlays, backtest stats, success record"""
    import strategies as S
    from core.backtest import run_backtest
    from core import success as SR, clock
    sym, tf, sid, n = q.get("sym", "BTC/USDT"), q.get("tf", "1h"), q.get("sid", "ema_cross"), int(q.get("n", 600))
    full = _df(sym, tf, 0)
    cls = S.REGISTRY[sid]
    res = cls().run(full)
    bt = run_backtest(full, res, symbol=sym)
    SR.put(sid, sym, tf, bt.stats); SR.flush()
    df = full.tail(n); off = len(full) - len(df)
    sig = res.signal.values[off:]
    import numpy as np
    idx = np.where(sig != 0)[0]
    signals = [dict(i=int(i), t=int(df.index[i].timestamp()), time=clock.fmt(df.index[i]), side=int(sig[i]), px=float(df.close.values[i]),
                    sl=_clean(res.stop.values[off + i]) if res.stop is not None else None,
                    tp=_clean(res.target.values[off + i]) if res.target is not None else None) for i in idx]
    overlays = {k: _clean(v.values[off:].tolist()) for k, v in (res.overlays or {}).items() if hasattr(v, "values")}
    panels = {}
    for pname, sd in (res.panels or {}).items():
        if not isinstance(sd, dict):
            sd = {pname: sd}
        panels[pname] = {k: _clean(v.values[off:].tolist()) for k, v in sd.items() if hasattr(v, "values")}
    trades = [dict(entry=clock.fmt(t.entry_time), exit=clock.fmt(t.exit_time), side=t.side, r=_clean(getattr(t, "r_multiple", getattr(t, "r", 0))), pnl=_clean(t.pnl), reason=getattr(t, "reason", ""))
              for t in list(bt.trades)[-30:]]
    st = _clean(bt.stats)
    return dict(sym=sym, tf=tf, sid=sid, name=cls.name_en, name_fa=cls.name_fa, candles=api_ohlcv(dict(sym=sym, tf=tf, n=n)), signals=signals,
                overlays=overlays, panels=panels, stats=st, trades=trades, success=SR.get(sid, sym, tf), oos=SR.oos(sid, sym, tf),
                levels=[dict(px=float(l[0]), label=l[1], color=(l[2] if len(l) > 2 else "#888")) for l in (res.levels or [])])


def api_signals(q):
    """all strategies on one symbol/tf → fresh signals in the last `recent` bars, ranked like the desktop scanner, each with success %"""
    import strategies as S, numpy as np
    from core.backtest import run_backtest
    from core import success as SR, clock, playbook as PB, quality as Q, calendar as CAL
    sym, tf, recent = q.get("sym", "BTC/USDT"), q.get("tf", "1h"), int(q.get("recent", 5))
    ck = ("signals", sym, tf, recent)
    with _lock:
        hit = _cache.get(ck)
    if hit and time.time() - hit[0] < 120:
        return hit[1]
    df = _df(sym, tf, 15000); n = len(df); out = []
    for cls in S.ALL_STRATEGIES:
        try:
            res = cls().run(df)
        except Exception:
            continue
        sig = res.signal.values; idx = np.where(sig[-recent:] != 0)[0]
        if len(idx) == 0:
            continue
        i = n - recent + idx[-1]
        d = SR.get(cls.id, sym, tf)
        if d is None or time.time() - d.get("ts", 0) > 7 * 86400:
            d = SR.put(cls.id, sym, tf, run_backtest(df, res, symbol=sym).stats)
        px = float(df.close.values[i]); sl = res.stop.values[i] if res.stop is not None else float("nan"); tp = res.target.values[i] if res.target is not None else float("nan")
        rr = abs(tp - px) / abs(px - sl) if sl == sl and tp == tp and px != sl else None
        pbst = PB.stats_for(cls.id, tf, sym) or {}
        qs = Q.score(cls.id, sym, tf, ev=(d, pbst or None, None))
        out.append(dict(sid=cls.id, name=cls.name_en, name_fa=cls.name_fa, category=cls.category, side=int(sig[i]), ago=n - 1 - i, time=clock.fmt(df.index[i]),
                        px=px, sl=_clean(sl), tp=_clean(tp), rr=rr, wr=d["wr"], pf=d["pf"], n=d["n"], grade=pbst.get("grade"), oos_wr=pbst.get("wr"),
                        oos_pf=pbst.get("pf"), oos_n=pbst.get("n"), score=qs["score"], verdict=qs["verdict"], why_en=qs["reasons_en"], why_fa=qs["reasons_fa"]))
    SR.flush()
    # Phase 23: forward-test evidence (one pass, cheap) can upgrade/downgrade verdicts
    try:
        from core import forward as FW
        closed = FW.records("closed")
        for r in out:
            rs = [x for x in closed if x.get("sid") == r["sid"] and x.get("tf") == tf]
            if len(rs) >= 5:
                qs = Q.score(r["sid"], sym, tf, ev=(dict(wr=r["wr"], pf=r["pf"], n=r["n"]), PB.stats_for(r["sid"], tf, sym), FW._agg(rs)))
                r.update(score=qs["score"], verdict=qs["verdict"], why_en=qs["reasons_en"], why_fa=qs["reasons_fa"], fwd_pf=qs["fwd"]["pf"], fwd_n=qs["fwd"]["n"])
    except Exception:
        pass
    rank = {"PROVEN": 0, "CANDIDATE": 1, "UNPROVEN": 2, "FAILED": 3}
    out.sort(key=lambda r: (rank[r["verdict"]], -r["score"], r["ago"]))
    news = CAL.risk_now()
    res = dict(sym=sym, tf=tf, last=float(df.close.values[-1]), time=clock.fmt(df.index[-1]), rows=out, quality=Q.summary(out),
               news_risk=_clean(news), news_text_fa=CAL.text(news, "fa"), news_text_en=CAL.text(news, "en"))
    with _lock:
        _cache[ck] = (time.time(), res)
    return res


def api_advise(q):
    from core import advisor
    return _clean(advisor.advise(q.get("sym", "BTC/USDT"), record=False))


def api_fast(q):
    from core import fastsignals as F
    return _clean(F.scan(tf=q.get("tf", "5m"), top_n=int(q.get("n", 20))))


def api_library(q):
    from core import library as L
    lang = q.get("lang", "en")
    return dict(books=[dict(title=b[0], author=b[1], category=b[2], lesson=b[4] if lang == "fa" else b[3], where=b[5]) for b in L.BOOKS],
                bots=[dict(name=b[0], kind=b[1], what=b[2], where=b[3]) for b in getattr(L, "BOTS", [])])


def api_clock(q):
    from core import clock
    loc, day, utc = clock.now_strings()
    return dict(local=f"{day} {loc}", tz=clock.tz_name(), utc=utc, world=clock.world_line(), epoch=time.time())


def api_success(q):
    from core import success as SR
    if q.get("sid"):
        return dict(record=SR.get(q["sid"], q.get("sym", "BTC/USDT"), q.get("tf", "1h")), oos=SR.oos(q["sid"], q.get("sym", "BTC/USDT"), q.get("tf", "1h")))
    return SR.summary()


# ------------------------------------------------------------------------------------------ Phase 21: full desktop parity
def api_indicators(q):
    """catalog of all chart indicators (key, placement, default params) — same SPECS the desktop chart uses"""
    from core.chart_indicators import SPECS
    try:
        from core.indicator_uses import U
    except Exception:
        U = {}
    lang = q.get("lang", "en")
    out = []
    for k, (place, dflt) in SPECS.items():
        u = U.get(k) or {}
        out.append(dict(key=k, place=place, params=dflt, uses=_clean(u.get("uses_" + lang, u.get("uses_en", []))), signals=_clean(u.get("signals_" + lang, u.get("signals_en", []))), pitfalls=_clean(u.get("pitfalls_" + lang, []))))
    return out


def api_indicator(q):
    """compute one indicator on sym/tf with params → overlays / panels / levels aligned to the last n candles"""
    from core.chart_indicators import compute
    sym, tf, key, n = q.get("sym", "BTC/USDT"), q.get("tf", "1h"), q.get("key", "ema"), int(q.get("n", 600))
    params = json.loads(q.get("params", "{}") or "{}")
    full = _df(sym, tf, 0); off = max(0, len(full) - n)
    r = compute(full, key, **params)
    ov = {k: _clean(v.values[off:].tolist()) for k, v in (r.get("overlays") or {}).items() if hasattr(v, "values")}
    pn = {p: {k: _clean(v.values[off:].tolist()) for k, v in d.items() if hasattr(v, "values")} for p, d in (r.get("panels") or {}).items()}
    lv = [dict(px=float(l[0]), label=str(l[1]), color=(l[2] if len(l) > 2 else "#888")) for l in (r.get("levels") or []) if l and l[0] == l[0]]
    return dict(key=key, overlays=ov, panels=pn, levels=lv, bands=_clean(r.get("bands") or []))


def api_drawings(q, body=None):
    """GET: drawings for sym|tf (shared with desktop data/drawings.json). POST: replace list."""
    from core import drawings as D
    sym, tf = q.get("sym", "BTC/USDT"), q.get("tf", "1h")
    if body is not None:
        D.save(sym, tf, body if isinstance(body, list) else body.get("items", []))
    return dict(sym=sym, tf=tf, items=D.load(sym, tf))


def api_forward(q):
    from core import forward as FW
    if q.get("update") == "1":
        FW.update()
    return dict(report=_clean(FW.report()), open=_clean(FW.records("open"))[-100:], closed=_clean(FW.records("closed"))[-200:])


def api_portfolio(q):
    from core import portfolio as P
    return _clean(P.build_proven_portfolio(tf=q.get("tf", "4h"), max_n=int(q.get("n", 6)), equity=float(q.get("equity", 10000))))


def api_risk(q):
    from core import risk as R
    eq, rp, en, st = float(q.get("equity", 10000)), float(q.get("risk_pct", 1)), float(q.get("entry", 100)), float(q.get("stop", 98))
    wr, rr = float(q.get("wr", 45)), float(q.get("rr", 2))
    ps = R.position_size(eq, rp, en, st)
    return dict(position=_clean(ps), targets=_clean(R.rr_targets(en, st)), kelly=_clean(R.kelly_fraction(wr, rr, 1.0)),
                ruin=_clean(R.risk_of_ruin(wr, rr, rp)), expectancy=_clean(R.expectancy(wr, rr, 1.0)), max_trades_to_ruin=_clean(R.max_trades_to_ruin(rp)))


def _journal_path():
    from core.paths import data as _d
    return _d("journal.json")


def api_journal(q, body=None):
    """GET list; POST {op:add,row}|{op:delete,idx}|{op:replace,rows}. Same journal.json as the desktop page + Steenbarger audit."""
    import os
    path = _journal_path()
    rows = []
    if os.path.exists(path):
        try:
            rows = json.load(open(path, encoding="utf-8"))
        except Exception:
            rows = []
    if body:
        op = body.get("op")
        if op == "add":
            rows.append(body["row"])
        elif op == "delete":
            i = int(body["idx"])
            if 0 <= i < len(rows):
                rows.pop(i)
        elif op == "replace":
            rows = list(body.get("rows", []))
        json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    audit = None
    try:
        from core import psychology as PSY
        audit = _clean(PSY.audit_journal(rows))
    except Exception:
        pass
    return dict(rows=rows, audit=audit)


def api_health(q):
    from core import health as H
    f = H.run_checks(quick=q.get("quick", "1") == "1")
    lang = q.get("lang", "en")
    return dict(summary=_clean(H.summary(f)), findings=[dict(area=x.area, level=x.severity, text=(x.fa if lang == "fa" else x.en), fix=bool(x.fix)) for x in f])


def api_patterns(q):
    from core import patterns as PT
    df = _df(q.get("sym", "BTC/USDT"), q.get("tf", "1h"), 2000)
    return _clean(PT.summarize(df, recent=int(q.get("recent", 5))))


def api_analyst(q):
    """offline grounded analyst report (+ Ask box) for sym/tf, same as the desktop AI page"""
    from core import analyst as AN
    sym, tf, lang = q.get("sym", "BTC/USDT"), q.get("tf", "1h"), q.get("lang", "en")
    df = _df(sym, tf, 3000)
    ctx = dict(df=df, symbol=sym, tf=tf)
    try:
        from core import playbook as PB
        ctx["playbook"] = PB.best_for(tf, sym) if hasattr(PB, "best_for") else None
    except Exception:
        pass
    out = dict(report=AN.report(ctx, lang=lang))
    if q.get("q"):
        out["answer"] = AN.ask(q["q"], ctx, lang=lang)
    return _clean(out)


def api_vision(q, body=None):
    """POST raw image bytes (or JSON {b64}) → chart-image understanding (candles, patterns, MAs, drawn lines) like the Vision page"""
    import base64, tempfile
    if body is None:
        return dict(error="POST an image")
    data = body if isinstance(body, (bytes, bytearray)) else base64.b64decode(body.get("b64", ""))
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(data); path = f.name
    try:
        from core import vision2 as V2
        u = V2.understand(path, lang=q.get("lang", "en"))
        u.pop("image", None)
        for k in list(u.keys()):
            if hasattr(u[k], "shape"):
                u.pop(k)
        return _clean(u)
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def api_ml(q):
    from core import ml as ML
    sym, tf = q.get("sym", "BTC/USDT"), q.get("tf", "1h")
    if q.get("train") == "1":
        df = _df(sym, tf, 20000)
        b = ML.train_market_model(df); ML.save_bundle(sym, tf, b)
    b = ML.load_bundle(sym, tf)
    out = dict(models=_clean(ML.list_models()), has_model=bool(b))
    if b:
        out["meta"] = _clean({k: v for k, v in b.items() if k not in ("model", "scaler", "clf")})
        try:
            df = _df(sym, tf, 3000); p = ML.predict(b, df)
            out["p_last"] = _clean(float(p[-1])) if hasattr(p, "__len__") else _clean(p)
        except Exception:
            pass
    return out


def api_quant(q):
    """ADF / Hurst / half-life on the close of sym/tf (+ pair cointegration if sym2 given)"""
    from core import quant as Q
    import numpy as np
    sym, tf = q.get("sym", "BTC/USDT"), q.get("tf", "1d")
    df = _df(sym, tf, 2000); x = np.log(df.close.values)
    out = dict(adf=_clean(Q.adf_test(x)), hurst=_clean(Q.hurst(x)), half_life=_clean(Q.half_life(x)))
    if q.get("sym2"):
        df2 = _df(q["sym2"], tf, 2000); j = df.close.to_frame("a").join(df2.close.rename("b"), how="inner").dropna()
        out["coint"] = _clean(Q.cointegration(np.log(j.a.values), np.log(j.b.values))); out["hedge"] = _clean(Q.hedge_ratio(np.log(j.a.values), np.log(j.b.values)))
    return out


def api_alerts(q, body=None):
    from core import alerts as AL
    if body:
        AL.save_settings(body)
    st = dict(AL.settings()); st.pop("token", None)
    return dict(settings=st, history=_clean(AL.history(50)))


def api_status(q):
    """training/maintenance status, playbook age, success-rate coverage, venue status — the Dashboard 'bot status' tile"""
    out = {}
    try:
        from core import maintenance as M; out["training"] = _clean(M.training_status())
    except Exception:
        pass
    try:
        from core import maintenance as M2; out["log"] = M2.tail(15)
    except Exception:
        pass
    try:
        from core import success as SR; out["success"] = _clean(SR.summary())
    except Exception:
        pass
    return out


def api_success_precompute(q):
    """start bulk success-rate computation in a background thread (same as Settings ▸ compute success rates)"""
    from core import success as SR
    st = _cache.setdefault("succ_job", {"running": False, "p": 0, "m": ""})
    if not st["running"]:
        st.update(running=True, p=0, m="start")
        def run():
            try:
                SR.precompute(progress=lambda p, m: st.update(p=p, m=m))
            finally:
                st["running"] = False
        threading.Thread(target=run, daemon=True).start()
    return st


def api_symbol_search(q):
    from core.data import UNIVERSE
    s = q.get("q", "").lower()
    return [x for cat, d in UNIVERSE.items() for x in d if s in x.lower()][:50]


def api_quality(q):
    """trust score + verdict + reasons for one strategy on sym/tf (hover / detail panel)"""
    from core import quality as Q
    sid, sym, tf = q.get("sid", "ema_cross"), q.get("sym", "BTC/USDT"), q.get("tf", "1h")
    r = Q.score(sid, sym, tf)
    if q.get("stress") == "1":
        r["stress"] = Q.stress_test(sid, sym, tf, df=_df(sym, tf, 0))
    return _clean(r)


def api_plan(q):
    """Phase 24 trade plan: regime fit, edge decay, HTF alignment, Monte-Carlo, ¼-Kelly size, entry/stop/TP1/TP2 (FA+EN)."""
    from core import edge as E
    sid, sym, tf = q.get("sid", "ema_cross"), q.get("sym", "BTC/USDT"), q.get("tf", "1h")
    return _clean(E.trade_plan(sym, tf, sid, df=_df(sym, tf, 0), equity=float(q.get("equity", 10000) or 10000), cap_pct=float(q.get("cap", 1.0) or 1.0)))


def api_desk(q):
    """Phase 25 daily trading-desk briefing (safety → regimes → open positions → ranked plans → decay → reality)."""
    from core import desk as D
    tfs = tuple(x for x in (q.get("tfs") or "4h,1d").split(",") if x)
    b = D.briefing(tfs=tfs, equity=float(q.get("equity", 10000) or 10000), mode=q.get("mode", "proven"), recent=int(q.get("recent", 3)),
                   max_age=0 if q.get("refresh") == "1" else 600)
    return _clean(b)


def api_cluster(q):
    """same-direction signals on highly correlated symbols = one bet (Phase 24)."""
    from core import edge as E
    import json as _j
    rows = _j.loads(q.get("rows", "[]"))
    return _clean(E.cluster_risk(rows, tf=q.get("tf", "1d")))


def api_calendar(q):
    from core import calendar as CAL
    now = CAL.risk_now()
    return dict(now=_clean(now), text_fa=CAL.text(now, "fa"), text_en=CAL.text(now, "en"), upcoming=_clean(CAL.upcoming(int(q.get("hours", 72)))))


def api_notifications(q):
    """push feed for the mobile app / desktop tray: new alerts since `since` (unix ts). The Android shell polls this
    every minute from its foreground service and raises system notifications."""
    from core import alerts as AL
    since = float(q.get("since", 0) or 0)
    hist = [h for h in AL.history(200) if float(h.get("ts", 0) or 0) > since]
    return dict(now=time.time(), items=_clean(hist[-30:]))


def api_alert_scan(q):
    """run the alert scanner now (same as desktop 'scan & notify'); dry=1 only lists"""
    from core import alerts as AL
    return _clean(AL.scan(tfs=[t for t in q.get("tfs", "1h,4h").split(",") if t], lang=q.get("lang", "fa"), dry=q.get("dry") == "1"))


def api_intelligence(q):
    """🧠 Strategy Intelligence - auto-select best strategy for symbol/tf based on regime, timeframe, and proven performance"""
    from core.strategy_intelligence import select_best_strategy
    sym = q.get("sym", "BTC/USDT")
    tf = q.get("tf", "1h")
    
    try:
        result = select_best_strategy(sym, tf)
        
        # Convert to JSON-safe dict
        market = dict(
            regime=result.market.regime,
            regime_fa=result.market.regime_fa,
            regime_en=result.market.regime_en,
            trend_strength=result.market.trend_strength,
            volatility_level=result.market.volatility_level,
            volatility_vs_median=result.market.volatility_vs_median,
            adx=result.market.adx,
            rsi=result.market.rsi,
            ema_trend=result.market.ema_trend,
            volume_trend=result.market.volume_trend,
            confidence=result.market.confidence,
        )
        
        def score_to_dict(s):
            return dict(
                id=s.strategy_id,
                name=s.strategy_name,
                name_fa=s.strategy_name_fa,
                category=s.category,
                score=s.total_score,
                breakdown=s.breakdown,
                win_rate=s.win_rate,
                profit_factor=s.profit_factor,
                grade=s.grade,
                success_label=s.success_label,
                reasoning_fa=s.reasoning_fa,
                reasoning_en=s.reasoning_en,
                confidence=s.confidence,
            )
        
        best = score_to_dict(result.best) if result.best else None
        top_5 = [score_to_dict(s) for s in result.top_5]
        top_20 = [score_to_dict(s) for s in result.all_scored[:20]]
        
        # Build summaries from result (avoid double computation)
        summary_fa = f"""🧠 هوش استراتژی - {sym} {tf}
بازار: {result.market.regime_fa} (ADX {result.market.adx:.0f}, RSI {result.market.rsi:.0f})
قدرت روند: {result.market.trend_strength:.0f}% | نوسان: {result.market.volatility_level:.0f}%
✅ بهترین: {result.best.strategy_name_fa} ({result.best.strategy_id}) - امتیاز {result.best.total_score:.0f}/100
دلیل: {result.best.reasoning_fa}
"""
        summary_en = f"""🧠 Strategy Intelligence - {sym} {tf}
Market: {result.market.regime_en} (ADX {result.market.adx:.0f}, RSI {result.market.rsi:.0f})
Trend: {result.market.trend_strength:.0f}% | Volatility: {result.market.volatility_level:.0f}%
✅ Best: {result.best.strategy_name} ({result.best.strategy_id}) - Score {result.best.total_score:.0f}/100
Reason: {result.best.reasoning_en}
"""
        
        return dict(
            symbol=sym,
            timeframe=tf,
            market=market,
            best=best,
            top_5=top_5,
            top_20=top_20,
            total_scored=len(result.all_scored),
            analysis_time_ms=result.analysis_time_ms,
            summary_fa=summary_fa,
            summary_en=summary_en,
        )
    except Exception as e:
        import traceback
        return dict(error=str(e), trace=traceback.format_exc()[-1000:])


ROUTES = {"/api/meta": api_meta, "/api/chart_config": api_chart_config, "/api/quality": api_quality, "/api/plan": api_plan, "/api/desk": api_desk, "/api/cluster": api_cluster, "/api/calendar": api_calendar, "/api/notifications": api_notifications, "/api/alert_scan": api_alert_scan, "/api/intelligence": api_intelligence, "/api/symbols": api_symbols, "/api/strategies": api_strategies, "/api/ohlcv": api_ohlcv, "/api/run": api_run,
          "/api/signals": api_signals, "/api/advise": api_advise, "/api/fast": api_fast, "/api/library": api_library, "/api/clock": api_clock,
          "/api/success": api_success,
          "/api/indicators": api_indicators, "/api/indicator": api_indicator, "/api/drawings": api_drawings, "/api/forward": api_forward,
          "/api/portfolio": api_portfolio, "/api/risk": api_risk, "/api/journal": api_journal, "/api/health": api_health, "/api/patterns": api_patterns,
          "/api/analyst": api_analyst, "/api/vision": api_vision, "/api/ml": api_ml, "/api/quant": api_quant, "/api/alerts": api_alerts,
          "/api/status": api_status, "/api/success_precompute": api_success_precompute, "/api/search": api_symbol_search}
POST_ROUTES = {"/api/drawings", "/api/journal", "/api/vision", "/api/alerts"}


class Handler(BaseHTTPRequestHandler):
    server_version = "ProTraderWeb/1.0"

    def log_message(self, *a):        # quiet
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204); self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS"); self.send_header("Access-Control-Allow-Headers", "Content-Type"); self.end_headers()

    def do_POST(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        n = int(self.headers.get("Content-Length") or 0); raw = self.rfile.read(n) if n else b""
        ctype = self.headers.get("Content-Type", "")
        body = raw if ctype.startswith("image/") or ctype.startswith("application/octet-stream") else (json.loads(raw or b"{}") if raw else {})
        if u.path in POST_ROUTES:
            try:
                self._send(200, json.dumps(_clean(ROUTES[u.path](q, body)), ensure_ascii=False))
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as e:
                try:
                    self._send(500, json.dumps(dict(error=str(e)[:300], trace=traceback.format_exc()[-800:])))
                except (BrokenPipeError, ConnectionResetError):
                    pass
            return
        self._send(404, json.dumps(dict(error="not found")))

    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in ROUTES:
            try:
                self._send(200, json.dumps(_clean(ROUTES[u.path](q)), ensure_ascii=False))
            except (BrokenPipeError, ConnectionResetError):
                return                                   # client went away (phone locked / navigated) — not an error
            except Exception as e:
                try:
                    self._send(500, json.dumps(dict(error=str(e)[:300], trace=traceback.format_exc()[-800:])))
                except (BrokenPipeError, ConnectionResetError):
                    pass
            return
        path = "index.html" if u.path in ("/", "") else u.path.lstrip("/")
        fp = os.path.normpath(os.path.join(WEB_DIR, path))
        if fp.startswith(os.path.normpath(WEB_DIR)) and os.path.isfile(fp):
            ct = {"html": "text/html; charset=utf-8", "js": "application/javascript", "css": "text/css", "png": "image/png", "svg": "image/svg+xml",
                  "json": "application/json", "webmanifest": "application/manifest+json"}.get(fp.rsplit(".", 1)[-1], "application/octet-stream")
            self._send(200, open(fp, "rb").read(), ct)
        else:
            self._send(404, json.dumps(dict(error="not found")))


def lan_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "127.0.0.1"


def start(port=DEFAULT_PORT, host="0.0.0.0"):
    """start in background thread; returns (url_lan, port). Idempotent."""
    global _server, _thread
    if _server is not None:
        return f"http://{lan_ip()}:{_server.server_address[1]}", _server.server_address[1]
    last = None
    for p in range(port, port + 10):
        try:
            _server = ThreadingHTTPServer((host, p), Handler); _server.daemon_threads = True; break
        except OSError as e:
            last = e
    if _server is None:
        raise last
    _thread = threading.Thread(target=_server.serve_forever, name="protrader-web", daemon=True); _thread.start()
    return f"http://{lan_ip()}:{_server.server_address[1]}", _server.server_address[1]


def stop():
    global _server, _thread
    if _server is not None:
        try:
            _server.shutdown(); _server.server_close()
        except Exception:
            pass
    _server = None; _thread = None


def running():
    return _server is not None


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=DEFAULT_PORT); ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args(argv)
    url, port = start(a.port, a.host)
    print(f"ProTrader web/mobile: {url}   (local: http://127.0.0.1:{port})  — Ctrl+C to stop", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop()


if __name__ == "__main__":
    sys.path.insert(0, ROOT); main()
