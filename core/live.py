"""
Live market engine — whole-market coverage.

• Universe: ALL Binance spot USDT pairs (≈480, via data-api.binance.vision exchangeInfo) + the non-crypto UNIVERSE.
• Stream: one WebSocket (wss://data-stream.binance.vision) with !miniTicker@arr (every symbol's price each second)
  + kline streams for the symbols the user is watching (bar-close events trigger recomputation).
• Analysis: for each symbol/timeframe the engine keeps a rolling OHLCV cache; on every bar close it runs the
  validated strategies (score ≥ min_score) + the ensemble + optional ML meta-label and emits fresh signals.
• Non-crypto symbols (Yahoo) are polled on a timer (no websocket available).
Works without any API key. Thread-safe; UI subscribes via callbacks.
"""
import json
import time
import threading
import queue
import requests
import numpy as np
import pandas as pd

from core.data import UNIVERSE, get_ohlcv, _normalize
from core.backtest import run_backtest

BINANCE_DATA = "https://data-api.binance.vision"
BINANCE_WS = "wss://data-stream.binance.vision/stream?streams="
STABLES = {"USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "EUR", "EURI", "AEUR", "USD1", "USDE", "XUSD", "BFUSD", "PAXG", "TRY", "BRL", "ARS", "COP", "JPY", "ZAR", "PLN", "RON", "UAH", "CZK", "MXN"}
_TF = {"1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "12h": "12h", "1d": "1d", "3d": "3d", "1wk": "1w", "1mo": "1M"}


# ---------------------------------------------------------------- universe
_universe_cache = {"ts": 0, "symbols": []}


def binance_usdt_universe(min_quote_volume_24h=1_000_000, force=False):
    """All TRADING spot pairs quoted in USDT, filtered by 24h quote volume, sorted by volume desc. Cached 1h."""
    if not force and _universe_cache["symbols"] and time.time() - _universe_cache["ts"] < 3600:
        return _universe_cache["symbols"]
    try:
        info = requests.get(f"{BINANCE_DATA}/api/v3/exchangeInfo", timeout=20).json()
    except Exception:
        # binance-vision blocked → OKX spot tickers (same shape: symbol, quoteVolume, 24h %, last)
        j = requests.get("https://www.okx.com/api/v5/market/tickers", params={"instType": "SPOT"}, timeout=20).json()
        rows = []
        for t in j.get("data", []):
            inst = t["instId"]
            if not inst.endswith("-USDT"):
                continue
            base = inst[:-5]
            if base in STABLES or any(x in base for x in ("UP", "DOWN", "BULL", "BEAR")):
                continue
            last, o = float(t["last"] or 0), float(t["open24h"] or 0)
            qv = float(t.get("volCcy24h") or 0)          # volCcy24h is already in quote (USDT)
            if qv >= min_quote_volume_24h:
                rows.append((base + "USDT", qv, (last / o - 1) * 100 if o else 0.0, last))
        rows.sort(key=lambda r: -r[1])
        _universe_cache.update(ts=time.time(), symbols=rows)
        return rows
    syms = {s["symbol"] for s in info["symbols"] if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
            and s["isSpotTradingAllowed"] and not any(x in s["baseAsset"] for x in ("UP", "DOWN", "BULL", "BEAR"))
            and s["baseAsset"] not in STABLES}
    tick = requests.get(f"{BINANCE_DATA}/api/v3/ticker/24hr", timeout=20).json()
    rows = [(t["symbol"], float(t["quoteVolume"]), float(t["priceChangePercent"]), float(t["lastPrice"]))
            for t in tick if t["symbol"] in syms and float(t["quoteVolume"]) >= min_quote_volume_24h]
    rows.sort(key=lambda r: -r[1])
    _universe_cache.update(ts=time.time(), symbols=rows)
    return rows


def fetch_klines(bsym, tf="1h", limit=1000):
    """History for one symbol via multi-venue failover (binance-vision → OKX → KuCoin → Gate → MEXC)."""
    from core import sources
    base = bsym[:-4] if bsym.upper().endswith("USDT") else bsym
    df, venue = sources.fetch_crypto(base, tf, limit=limit)
    df.attrs.update(symbol=bsym, tf=tf, venue=venue)
    return df


def pretty(bsym):
    return bsym[:-4] + "/USDT" if bsym.endswith("USDT") else bsym


# ---------------------------------------------------------------- engine
class LiveEngine:
    """Background threads: ticker websocket, kline websocket, analysis worker. Callbacks run in engine threads —
    the UI wraps them with Qt signals."""

    def __init__(self, timeframe="1h", min_score=40, top_n=150, use_ml=False, on_tick=None, on_signal=None, on_status=None):
        self.tf = timeframe
        self.min_score = min_score
        self.top_n = top_n
        self.use_ml = use_ml
        self.on_tick = on_tick or (lambda d: None)
        self.on_signal = on_signal or (lambda d: None)
        self.on_status = on_status or (lambda s: None)
        self.prices = {}          # bsym -> dict(price, chg24, vol24, ts)
        self.bars = {}            # bsym -> DataFrame
        self.signals = {}         # (bsym, strategy_id) -> signal dict
        self.symbols = []         # watched bsyms (top_n by volume)
        self._q = queue.Queue()
        self._stop = threading.Event()
        self._threads = []
        self._members = None
        self._ml = {}
        self.stats = dict(ticks=0, bars_closed=0, analyzed=0, signals=0, started=None, errors=0)
        self._lock = threading.Lock()

    # ---------------- lifecycle
    def start(self):
        self._stop.clear()
        self.stats["started"] = time.time()
        for fn in (self._ticker_loop, self._kline_loop, self._analysis_loop, self._bootstrap):
            t = threading.Thread(target=fn, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self):
        self._stop.set()
        for ws in getattr(self, "_sockets", []):
            try:
                ws.close()
            except Exception:
                pass

    # ---------------- members (validated strategies)
    def members(self):
        if self._members is None:
            import strategies as S
            from core.validation import load_cache
            cache = load_cache()
            ids = [k for k, v in cache.items() if v.get("score", 0) >= self.min_score]
            if "ensemble" not in ids:
                ids.append("ensemble")
            self._members = [S.REGISTRY[i] for i in ids if i in S.REGISTRY]
        return self._members

    # ---------------- bootstrap: universe + history
    def _bootstrap(self):
        try:
            self.on_status("loading universe…")
            uni = binance_usdt_universe()
            self.symbols = [r[0] for r in uni[: self.top_n]]
            for s, qv, chg, px in uni:
                self.prices[s] = dict(price=px, chg24=chg, vol24=qv, ts=time.time())
            self.on_status(f"universe: {len(uni)} USDT pairs · watching top {len(self.symbols)} · loading history…")
            for i, s in enumerate(self.symbols):
                if self._stop.is_set():
                    return
                try:
                    self.bars[s] = fetch_klines(s, self.tf, 1000)
                    self._q.put(s)
                except Exception:
                    self.stats["errors"] += 1
                if i % 10 == 0:
                    self.on_status(f"history {i + 1}/{len(self.symbols)} · queue {self._q.qsize()}")
                time.sleep(0.05)  # stay far below Binance weight limits
            self.on_status(f"live · {len(self.symbols)} symbols streaming on {self.tf}")
        except Exception as e:
            self.on_status(f"bootstrap error: {e}")

    # ---------------- websockets
    def _ws_connect(self, streams):
        import websocket
        ws = websocket.create_connection(BINANCE_WS + streams, timeout=30)
        self._sockets = getattr(self, "_sockets", []) + [ws]
        return ws

    def _ticker_loop(self):
        while not self._stop.is_set():
            try:
                ws = self._ws_connect("!miniTicker@arr")
                while not self._stop.is_set():
                    msg = json.loads(ws.recv())
                    arr = msg.get("data", [])
                    now = time.time()
                    batch = []
                    for t in arr:
                        s = t["s"]
                        if not s.endswith("USDT"):
                            continue
                        px = float(t["c"]); o = float(t["o"])
                        d = dict(price=px, chg24=(px / o - 1) * 100 if o else 0, vol24=float(t["q"]), ts=now)
                        self.prices[s] = d
                        batch.append((s, d))
                        # update the live (unclosed) bar so charts/levels are current
                        df = self.bars.get(s)
                        if df is not None and len(df):
                            last = df.index[-1]
                            df.iat[-1, 3] = px
                            if px > df.iat[-1, 1]:
                                df.iat[-1, 1] = px
                            if px < df.iat[-1, 2]:
                                df.iat[-1, 2] = px
                    self.stats["ticks"] += len(batch)
                    if batch:
                        self.on_tick(batch)
            except Exception as e:
                self.stats["errors"] += 1
                if not self._stop.is_set():
                    time.sleep(3)

    def _kline_loop(self):
        # wait for symbols
        while not self.symbols and not self._stop.is_set():
            time.sleep(0.5)
        while not self._stop.is_set():
            try:
                # Binance allows up to 1024 streams per connection; chunk at 200 for safety
                chunks = [self.symbols[i:i + 200] for i in range(0, len(self.symbols), 200)]
                socks = [self._ws_connect("/".join(f"{s.lower()}@kline_{_TF[self.tf]}" for s in ch)) for ch in chunks]
                import select
                while not self._stop.is_set():
                    for ws in socks:
                        ws.settimeout(0.2)
                        try:
                            msg = json.loads(ws.recv())
                        except Exception:
                            continue
                        k = msg.get("data", {}).get("k")
                        if not k:
                            continue
                        s = k["s"]
                        t = pd.to_datetime(k["t"], unit="ms")
                        row = [float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]), float(k["v"])]
                        df = self.bars.get(s)
                        if df is None:
                            continue
                        if t in df.index:
                            df.loc[t, ["open", "high", "low", "close", "volume"]] = row
                        else:
                            df.loc[t] = row
                            self.bars[s] = df.iloc[-1500:]
                        if k["x"]:  # bar closed → analyze
                            self.stats["bars_closed"] += 1
                            self._q.put(s)
            except Exception:
                self.stats["errors"] += 1
                if not self._stop.is_set():
                    time.sleep(3)

    # ---------------- analysis
    def analyze_symbol(self, s):
        df = self.bars.get(s)
        if df is None or len(df) < 300:
            return []
        df = df.copy()
        df.attrs.update(symbol=pretty(s), tf=self.tf)
        out = []
        n = len(df)
        from core import playbook as PB
        proven = [S_id for S_id, _, _ in PB.best_for(self.tf, pretty(s), k=8)]
        if proven:
            import strategies as S
            classes = [S.REGISTRY[i] for i in proven if i in S.REGISTRY]
        else:
            classes = []   # nothing proven on this TF for crypto → the honest answer is no signals
        for cls in classes:
            try:
                res = cls().run(df)
            except Exception:
                continue
            sig = res.signal.values
            idx = np.where(sig[-3:] != 0)[0]
            if len(idx) == 0:
                continue
            i = n - 3 + idx[-1]
            try:
                st = run_backtest(df, res).stats
            except Exception:
                continue
            if st["trades"] < 8 or st["profit_factor"] < 1.0:
                continue
            from core.validation import allowed
            if not allowed(cls.id, pretty(s), self.tf):
                continue
            side = int(sig[i])
            px = float(df.close.values[i])
            sl = float(res.stop.values[i]) if res.stop is not None and res.stop.values[i] == res.stop.values[i] else float("nan")
            tp = float(res.target.values[i]) if res.target is not None and res.target.values[i] == res.target.values[i] else float("nan")
            rr = abs(tp - px) / abs(px - sl) if sl == sl and tp == tp and px != sl else 0.0
            d = dict(sym=pretty(s), bsym=s, tf=self.tf, sid=cls.id, side=side, ago=n - 1 - i, px=px, sl=sl, tp=tp, rr=rr,
                     wr=st["win_rate"], pf=st["profit_factor"], trades=st["trades"], ts=time.time(), last=float(df.close.values[-1]),
                     p_ml=float("nan"))
            if self.use_ml:
                d["p_ml"] = self._ml_prob(s, df, side)
            pbst = PB.stats_for(cls.id, self.tf, pretty(s)) or {}
            d["grade"] = pbst.get("grade", "D")
            if d["ago"] <= 1 and sl == sl and tp == tp:
                try:
                    from core import forward as FW
                    FW.record(pretty(s), self.tf, cls.id, side, df.index[i], px, sl, tp, source="live",
                              expect=dict(wr=pbst.get("wr", d["wr"]), pf=pbst.get("pf", d["pf"]), n=pbst.get("n", d["trades"])))
                except Exception:
                    pass
            out.append(d)
        with self._lock:
            for d in out:
                self.signals[(s, d["sid"])] = d
            # drop stale
            for key in [k for k, v in self.signals.items() if k[0] == s and v["ts"] < time.time() - 1]:
                if key not in {(s, d["sid"]) for d in out}:
                    self.signals.pop(key, None)
        self.stats["analyzed"] += 1
        self.stats["signals"] = len(self.signals)
        return out

    def _ml_prob(self, s, df, side):
        try:
            from core import ml
            b = self._ml.get("global")
            if b is None:
                b = ml.load_bundle("BTC/USDT", self.tf) or ml.load_bundle("BTC/USDT", "1h")
                self._ml["global"] = b or False
            if not b:
                return float("nan")
            pl, ps = ml.predict(b, df.tail(400))
            return float(pl.iloc[-1] if side == 1 else ps.iloc[-1])
        except Exception:
            return float("nan")

    def _analysis_loop(self):
        while not self._stop.is_set():
            try:
                s = self._q.get(timeout=1)
            except queue.Empty:
                continue
            try:
                out = self.analyze_symbol(s)
                if out:
                    self.on_signal(out)
            except Exception:
                self.stats["errors"] += 1

    # ---------------- snapshots for UI
    def snapshot_signals(self):
        with self._lock:
            rows = list(self.signals.values())
        for d in rows:
            p = self.prices.get(d["bsym"])
            if p:
                d["last"] = p["price"]
        rows.sort(key=lambda d: (d["ago"], -d["pf"]))
        return rows

    def snapshot_market(self):
        rows = [(s, d["price"], d["chg24"], d["vol24"]) for s, d in self.prices.items()]
        rows.sort(key=lambda r: -r[3])
        return rows

    def breadth(self):
        """Market breadth: % of watched symbols above EMA50/200, advancers, average 24h change."""
        from core.indicators import ema
        above50 = above200 = n = 0
        for s in self.symbols:
            df = self.bars.get(s)
            if df is None or len(df) < 210:
                continue
            c = df.close
            n += 1
            above50 += c.iloc[-1] > ema(c, 50).iloc[-1]
            above200 += c.iloc[-1] > ema(c, 200).iloc[-1]
        chg = [d["chg24"] for d in self.prices.values()]
        adv = sum(1 for x in chg if x > 0)
        return dict(n=n, pct_above50=100 * above50 / n if n else 0, pct_above200=100 * above200 / n if n else 0,
                    advancers=adv, decliners=len(chg) - adv, avg_chg=float(np.mean(chg)) if chg else 0,
                    btc_chg=self.prices.get("BTCUSDT", {}).get("chg24", 0))
