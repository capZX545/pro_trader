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
    from core import success as SR, clock, playbook as PB
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
        out.append(dict(sid=cls.id, name=cls.name_en, name_fa=cls.name_fa, category=cls.category, side=int(sig[i]), ago=n - 1 - i, time=clock.fmt(df.index[i]),
                        px=px, sl=_clean(sl), tp=_clean(tp), rr=rr, wr=d["wr"], pf=d["pf"], n=d["n"], grade=pbst.get("grade"), oos_wr=pbst.get("wr")))
    SR.flush()
    out.sort(key=lambda r: (-(r["pf"] >= 1), r["ago"], -r["pf"]))
    res = dict(sym=sym, tf=tf, last=float(df.close.values[-1]), time=clock.fmt(df.index[-1]), rows=out)
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


ROUTES = {"/api/meta": api_meta, "/api/symbols": api_symbols, "/api/strategies": api_strategies, "/api/ohlcv": api_ohlcv, "/api/run": api_run,
          "/api/signals": api_signals, "/api/advise": api_advise, "/api/fast": api_fast, "/api/library": api_library, "/api/clock": api_clock,
          "/api/success": api_success}


class Handler(BaseHTTPRequestHandler):
    server_version = "ProTraderWeb/1.0"

    def log_message(self, *a):        # quiet
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in ROUTES:
            try:
                self._send(200, json.dumps(_clean(ROUTES[u.path](q)), ensure_ascii=False))
            except Exception as e:
                self._send(500, json.dumps(dict(error=str(e)[:300], trace=traceback.format_exc()[-800:])))
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
