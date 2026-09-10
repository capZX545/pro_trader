"""
Multi-venue crypto OHLCV sources with automatic failover (Phase 14).

Why: api.binance.com answers HTTP 451 (geo-block) in many regions and Yahoo rate-limits (429),
so the chart page ended up empty / synthetic.  Every venue below is public, key-less and serves
the same OHLCV shape.  `fetch_crypto()` tries them in order of measured health and remembers
which one worked (sticky), so a blocked venue costs one timeout only once per session.

Venues (all spot, USDT quote):
  binance-vision  data-api.binance.vision   (Binance public mirror – works where api.binance.com is blocked)
  okx             www.okx.com               (history-candles, 100/req, paginates by `after`)
  kucoin          api.kucoin.com            (1500/req, startAt/endAt seconds)
  gate            api.gateio.ws             (1000/req, `to` seconds)
  mexc            api.mexc.com              (1000/req, endTime ms)

All return a UTC-naive DatetimeIndex DataFrame [open, high, low, close, volume] sorted ascending,
last row = the currently *open* candle (same convention as Binance).
"""
import time
import threading
import requests
import pandas as pd

# --- Resilient layer integration (anti-filter) ---
try:
    from core.resilient import session as _resilient_session_factory, detect_system_proxy
    _S = _resilient_session_factory()
    _S.headers["User-Agent"] = "ProTrader/2.5 (+resilient anti-filter + Iran Gold)"
    print("[sources] Using resilient session with anti-filter")
except Exception as e:
    print(f"[sources] Resilient not available, fallback: {e}")
    _S = requests.Session()
    _S.headers["User-Agent"] = "ProTrader/1.1 (+desktop analysis app)"
_TIMEOUT = 12

# --- Iran Gold live price cache integration ---
try:
    from core import iran_gold as _IRAN_GOLD_SRC
    _IRAN_AVAILABLE = True
except Exception:
    _IRAN_AVAILABLE = False


# ------------------------------------------------------------------ interval maps
_OKX_TF = {"1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "12h": "12H",
           "1d": "1Dutc", "3d": "3Dutc", "1wk": "1Wutc", "1mo": "1Mutc"}
_KUCOIN_TF = {"1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1hour", "2h": "2hour", "4h": "4hour",
              "6h": "6hour", "12h": "12hour", "1d": "1day", "1wk": "1week", "1mo": "1month"}
_GATE_TF = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1d", "1wk": "7d", "1mo": "30d"}
_MEXC_TF = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m", "4h": "4h", "1d": "1d", "1wk": "1W", "1mo": "1M"}
_BINANCE_TF = {"1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "12h": "12h",
               "1d": "1d", "3d": "3d", "1wk": "1w", "1mo": "1M"}
TF_SECONDS = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
              "1d": 86400, "3d": 259200, "1wk": 604800, "1mo": 2592000}


def _frame(rows, unit="ms"):
    """rows: iterable of (t, o, h, l, c, v)."""
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["t"].astype("int64"), unit=unit)
    df = df.set_index("time")[["open", "high", "low", "close", "volume"]].astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index.name = "time"
    return df


# ------------------------------------------------------------------ venue fetchers
# each: fn(base, tf, limit, since_ms=None) -> DataFrame ; raises on failure / unsupported tf

def _binance_vision(base, tf, limit, since_ms=None):
    url = "https://data-api.binance.vision/api/v3/klines"
    sym = f"{base}USDT"
    out, end, remaining = [], None, limit
    if since_ms is not None:
        start = since_ms + 1
        while True:
            r = _S.get(url, params={"symbol": sym, "interval": _BINANCE_TF[tf], "startTime": start, "limit": 1000}, timeout=_TIMEOUT)
            r.raise_for_status(); rows = r.json()
            if not rows:
                break
            out += rows; start = rows[-1][0] + 1
            if len(rows) < 1000:
                break
        return _frame([(x[0], x[1], x[2], x[3], x[4], x[5]) for x in out])
    while remaining > 0:
        p = {"symbol": sym, "interval": _BINANCE_TF[tf], "limit": min(1000, remaining)}
        if end:
            p["endTime"] = end
        r = _S.get(url, params=p, timeout=_TIMEOUT)
        r.raise_for_status(); rows = r.json()
        if not rows:
            break
        out = rows + out; end = rows[0][0] - 1; remaining -= len(rows)
        if len(rows) < p["limit"]:
            break
    return _frame([(x[0], x[1], x[2], x[3], x[4], x[5]) for x in out])


def _okx(base, tf, limit, since_ms=None):
    inst, bar = f"{base}-USDT", _OKX_TF[tf]
    out, after = [], None
    # OKX: /market/candles = latest 300 (includes open candle); /market/history-candles = older pages of 100
    r = _S.get("https://www.okx.com/api/v5/market/candles", params={"instId": inst, "bar": bar, "limit": 300}, timeout=_TIMEOUT)
    r.raise_for_status(); j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(f"okx {j.get('msg')}")
    rows = j["data"]
    out += rows
    if since_ms is not None:
        rows = [x for x in rows if int(x[0]) > since_ms]
        return _frame([(x[0], x[1], x[2], x[3], x[4], x[5]) for x in rows])
    after = rows[-1][0] if rows else None
    pages = 0
    while after and len(out) < limit and pages < 60:      # cap: 60 pages ≈ 6000 bars (rate-limit 20 req/2 s)
        r = _S.get("https://www.okx.com/api/v5/market/history-candles", params={"instId": inst, "bar": bar, "after": after, "limit": 100}, timeout=_TIMEOUT)
        r.raise_for_status(); rows = r.json().get("data", [])
        if not rows:
            break
        out += rows; after = rows[-1][0]; pages += 1
        if pages % 10 == 0:
            time.sleep(0.6)
    return _frame([(x[0], x[1], x[2], x[3], x[4], x[5]) for x in out])


def _kucoin(base, tf, limit, since_ms=None):
    sym, typ = f"{base}-USDT", _KUCOIN_TF[tf]
    sec = TF_SECONDS[tf]
    out, end = [], int(time.time())
    if since_ms is not None:
        r = _S.get("https://api.kucoin.com/api/v1/market/candles", params={"symbol": sym, "type": typ, "startAt": since_ms // 1000}, timeout=_TIMEOUT)
        r.raise_for_status(); j = r.json()
        if j.get("code") != "200000":
            raise RuntimeError(f"kucoin {j.get('msg')}")
        rows = j["data"]
    else:
        rows = []
        while len(rows) < limit:
            start = end - 1500 * sec
            r = _S.get("https://api.kucoin.com/api/v1/market/candles", params={"symbol": sym, "type": typ, "startAt": start, "endAt": end}, timeout=_TIMEOUT)
            r.raise_for_status(); j = r.json()
            if j.get("code") != "200000":
                raise RuntimeError(f"kucoin {j.get('msg')}")
            page = j["data"]
            if not page:
                break
            rows += page; end = start
            if len(page) < 100:
                break
    # kucoin row: [time, open, close, high, low, volume, turnover]
    return _frame([(x[0], x[1], x[3], x[4], x[2], x[5]) for x in rows], unit="s")


def _gate(base, tf, limit, since_ms=None):
    pair, iv = f"{base}_USDT", _GATE_TF[tf]
    sec = TF_SECONDS[tf]
    if since_ms is not None:
        p = {"currency_pair": pair, "interval": iv, "from": since_ms // 1000}
        r = _S.get("https://api.gateio.ws/api/v4/spot/candlesticks", params=p, timeout=_TIMEOUT); r.raise_for_status(); rows = r.json()
    else:
        rows, to = [], int(time.time())
        while len(rows) < limit:
            r = _S.get("https://api.gateio.ws/api/v4/spot/candlesticks", params={"currency_pair": pair, "interval": iv, "limit": 1000, "to": to}, timeout=_TIMEOUT)
            r.raise_for_status(); page = r.json()
            if not isinstance(page, list) or not page:
                break
            rows = page + rows; to = int(page[0][0]) - sec
            if len(page) < 1000:
                break
    # gate row: [t, quote_vol, close, high, low, open, base_vol, closed]
    return _frame([(x[0], x[5], x[3], x[4], x[2], x[6]) for x in rows], unit="s")


def _mexc(base, tf, limit, since_ms=None):
    sym, iv = f"{base}USDT", _MEXC_TF[tf]
    url = "https://api.mexc.com/api/v3/klines"
    if since_ms is not None:
        r = _S.get(url, params={"symbol": sym, "interval": iv, "startTime": since_ms + 1, "limit": 1000}, timeout=_TIMEOUT); r.raise_for_status(); rows = r.json()
    else:
        rows, end, remaining = [], None, limit
        while remaining > 0:
            p = {"symbol": sym, "interval": iv, "limit": min(500, remaining)}   # MEXC hard-caps at 500
            if end:
                p["endTime"] = end
            r = _S.get(url, params=p, timeout=_TIMEOUT); r.raise_for_status(); page = r.json()
            if not page:
                break
            rows = page + rows; end = page[0][0] - 1; remaining -= len(page)
            if len(page) < p["limit"]:
                break
    return _frame([(x[0], x[1], x[2], x[3], x[4], x[5]) for x in rows])


VENUES = [("binance-vision", _binance_vision), ("okx", _okx), ("kucoin", _kucoin), ("gate", _gate), ("mexc", _mexc)]
_health = {n: {"ok": 0, "fail": 0, "last_fail": 0.0} for n, _ in VENUES}
_sticky = {"venue": None}
_lock = threading.Lock()


def _order():
    """Sticky venue first, then by (fewest recent failures, most successes); venues that failed <60 s ago go last."""
    now = time.time()
    def key(item):
        n = item[0]
        h = _health[n]
        return (0 if n == _sticky["venue"] else 1, 1 if now - h["last_fail"] < 60 else 0, h["fail"] - h["ok"])
    return sorted(VENUES, key=key)


def fetch_crypto(base: str, tf: str, limit: int = 1500, since_ms=None, min_bars: int = 50):
    """Fetch OHLCV for `base`/USDT from the first healthy venue. Returns (df, venue_name). Raises if all fail.
    Enhanced with resilient anti-filter layer and Iran Gold support.
    """
    base = base.upper()
    errors = []
    for name, fn in _order():
        try:
            df = fn(base, tf, limit, since_ms)
        except KeyError:
            continue                                  # timeframe unsupported on that venue
        except Exception as e:
            with _lock:
                _health[name]["fail"] += 1; _health[name]["last_fail"] = time.time()
                if _sticky["venue"] == name:
                    _sticky["venue"] = None
            errors.append(f"{name}: {str(e)[:80]}")
            continue
        if since_ms is None and len(df) < min_bars:
            errors.append(f"{name}: only {len(df)} bars")
            continue
        with _lock:
            _health[name]["ok"] += 1; _sticky["venue"] = name
        df.attrs["venue"] = name
        return df, name
    raise RuntimeError("all venues failed → " + " | ".join(errors))


def venue_status():
    return {"active": _sticky["venue"], "health": {k: dict(v) for k, v in _health.items()}}


# ------------------------------------------------------------------ live streaming (websocket)
class CandleStream(threading.Thread):
    """Real-time candle stream for ONE symbol/timeframe with venue failover.

    on_candle(ts_ms:int, o,h,l,c,v: float, closed: bool) is called from the stream thread on every update
    (Binance-vision pushes ~1/s, OKX ~1/s). If no websocket venue works, falls back to REST polling every
    `poll_sec` seconds so the chart still updates. `status` is a short human string for the UI.
    """

    def __init__(self, base: str, tf: str, on_candle, on_status=None, poll_sec: float = 5.0):
        super().__init__(daemon=True)
        self.base, self.tf = base.upper(), tf
        self.on_candle = on_candle
        self.on_status = on_status or (lambda s: None)
        self.poll_sec = poll_sec
        self._stop = threading.Event()
        self._ws = None
        self.status = "connecting"
        self.venue = None

    def stop(self):
        """Non-blocking: closing a websocket does a TLS shutdown handshake (up to seconds on a slow link) — do it
        off the UI thread. Late callbacks are suppressed by the `_stop` flag."""
        self._stop.set()
        ws, self._ws = self._ws, None
        cb = self.on_candle
        self.on_candle = lambda *a, **k: None
        self.on_status = lambda *a, **k: None
        if ws is not None:
            def _close():
                try:
                    ws.close(timeout=1)
                except Exception:
                    try:
                        ws.shutdown()
                    except Exception:
                        pass
            threading.Thread(target=_close, daemon=True).start()

    def _set(self, s):
        self.status = s
        self.on_status(s)

    def run(self):
        backoff = 2
        while not self._stop.is_set():
            for name, fn in (("binance-vision", self._ws_binance), ("okx", self._ws_okx)):
                if self._stop.is_set():
                    return
                try:
                    self.venue = name
                    fn()                       # returns only on error / stop
                    backoff = 2
                except Exception as e:
                    self._set(f"{name} ws error: {str(e)[:60]}")
                if self._stop.is_set():
                    return
            # both websockets failed → REST polling for a while, then retry websockets
            self._set("polling (REST)")
            t_end = time.time() + 60
            while not self._stop.is_set() and time.time() < t_end:
                try:
                    df, v = fetch_crypto(self.base, self.tf, limit=3, min_bars=1)
                    self.venue = v
                    for ts, r in df.iterrows():
                        self.on_candle(int(ts.value // 1_000_000), r.open, r.high, r.low, r.close, r.volume, False)
                    self._set(f"live · {v} (poll)")
                except Exception as e:
                    self._set(f"offline: {str(e)[:50]}")
                self._stop.wait(self.poll_sec)
            time.sleep(min(backoff, 30)); backoff *= 2

    # -- venues
    def _ws_binance(self):
        import websocket, json
        url = f"wss://data-stream.binance.vision/ws/{self.base.lower()}usdt@kline_{_BINANCE_TF[self.tf]}"
        self._ws = websocket.create_connection(url, timeout=15)
        self._set("live · binance-vision")
        while not self._stop.is_set():
            k = json.loads(self._ws.recv()).get("k")
            if k:
                self.on_candle(int(k["t"]), float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]), float(k["v"]), bool(k["x"]))

    def _ws_okx(self):
        import websocket, json
        self._ws = websocket.create_connection("wss://ws.okx.com:8443/ws/v5/business", timeout=15)
        self._ws.send(json.dumps({"op": "subscribe", "args": [{"channel": f"candle{_OKX_TF[self.tf]}", "instId": f"{self.base}-USDT"}]}))
        self._set("live · okx")
        last_ping = time.time()
        while not self._stop.is_set():
            self._ws.settimeout(20)
            try:
                raw = self._ws.recv()
            except Exception:
                self._ws.send("ping"); continue
            if raw == "pong":
                continue
            msg = json.loads(raw)
            for x in msg.get("data", []) or []:
                self.on_candle(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5]), x[8] == "1")
            if time.time() - last_ping > 20:
                self._ws.send("ping"); last_ping = time.time()
