"""
Engine-parity layer (Phase 11 — LEAN/QuantConnect, Zipline, Backtrader, TensorTrade, Freqtrade+TF).

The four engines differ in API but agree on the mechanics that matter. What we ported:

  Backtrader  → event-driven `next()` loop, bracket orders, `Sizer`s, commission schemes (per-share / percent / futures
                 margin+mult), `cheat_on_open` off by default (fills at NEXT bar), analyzers (SQN!, DrawDown, Returns).
                 → `EventEngine` + `Strategy` adapter + `sqn()`
  Zipline     → Pipeline factors (cross-sectional ranks computed once per bar over the universe), slippage models
                 VolumeShareSlippage(volume_limit=0.025, price_impact=0.1) and FixedBasisPointsSlippage; PerShare
                 commission with minimum per order.                                     → `pipeline_rank()`, `volume_share_slippage()`
  LEAN        → Resolution/consolidators (multi-timeframe), Reality Modelling (fill/fee/slippage/buying-power models),
                 Insights → Portfolio Construction → Risk Management → Execution ("Algorithm Framework").
                 → `AlgorithmFramework` (alpha → portfolio → risk → execution), `consolidate()`
  TensorTrade → same separation applied to RL (see core/rl.py).
  Freqtrade+TF / FreqAI → feature engineering & label pipeline with train/backtest windows and *live retraining
                 cadence*; ports to core/ml.py; here `freqai_schedule()` computes retrain/backtest windows.

The event engine is checked for PARITY with our vectorised backtester (core/backtest.py) in `parity_check()` — the
kind of test Backtrader/Zipline users run before trusting either.
"""
import numpy as np
import pandas as pd


# ------------------------------------------------------------------ commission & slippage models
class PercentCommission:
    def __init__(self, pct=0.001, minimum=0.0):
        self.pct, self.minimum = pct, minimum
    def __call__(self, price, size):
        return max(abs(price * size) * self.pct, self.minimum)


class PerShareCommission:  # Zipline PerShare(cost=0.001, min_trade_cost=1.0)
    def __init__(self, cost=0.001, min_trade_cost=1.0):
        self.cost, self.min = cost, min_trade_cost
    def __call__(self, price, size):
        return max(abs(size) * self.cost, self.min)


class FuturesCommission:  # Backtrader CommInfo with margin & mult
    def __init__(self, per_contract=2.0, mult=1.0, margin=None):
        self.per_contract, self.mult, self.margin = per_contract, mult, margin
    def __call__(self, price, size):
        return abs(size) * self.per_contract


def fixed_bps_slippage(price, side, bps=5.0):
    return price * (1 + side * bps / 1e4)


def volume_share_slippage(price, side, order_size, bar_volume, volume_limit=0.025, price_impact=0.1):
    """Zipline VolumeShareSlippage: fill up to volume_limit×bar volume; impact = price_impact × (share)²"""
    max_fill = bar_volume * volume_limit
    fill = min(abs(order_size), max_fill) if bar_volume > 0 else abs(order_size)
    share = fill / bar_volume if bar_volume > 0 else volume_limit
    impact = price_impact * share ** 2
    return price * (1 + side * impact), fill


# ------------------------------------------------------------------ event-driven engine (Backtrader-style)
class Order:
    __slots__ = ("side", "size", "kind", "price", "stop", "limit", "parent", "status", "created", "reason")

    def __init__(self, side, size, kind="market", price=None, stop=None, limit=None, reason=""):
        self.side, self.size, self.kind, self.price, self.stop, self.limit = side, size, kind, price, stop, limit
        self.status, self.created, self.reason = "submitted", None, reason


class Strategy:
    """Backtrader-like strategy: implement `next(i, bar)` and call self.buy()/self.sell()/self.close()/self.bracket()."""
    params = {}

    def __init__(self, engine):
        self.e = engine
        self.p = dict(self.params)

    def start(self):
        pass

    def next(self, i, bar):
        raise NotImplementedError

    # order helpers
    def buy(self, size=None, **kw):
        return self.e.submit(Order(+1, size, **kw))

    def sell(self, size=None, **kw):
        return self.e.submit(Order(-1, size, **kw))

    def close(self, reason="close", at="close"):
        """at='close' → Backtrader Order.Close (fills at this bar's close); at='open' → next bar's open"""
        if self.e.position != 0:
            od = Order(-np.sign(self.e.position), abs(self.e.position), kind="close" if at == "close" else "market", reason=reason)
            if at == "close":
                od.created = self.e.i; self.e._fill(od, self.e.c[self.e.i], self.e.i, reason); return od
            return self.e.submit(od)

    def bracket(self, side, size, stop, limit, reason="entry"):
        o = self.e.submit(Order(side, size, reason=reason))
        self.e.pending_bracket = (stop, limit)
        return o

    @property
    def position(self):
        return self.e.position


class EventEngine:
    def __init__(self, df, cash=10_000.0, commission=None, slippage_bps=2.0, cheat_on_open=False, risk_pct=1.0, max_bars=200,
                 default_sl_atr=2.0, default_tp_atr=4.0):
        self.df = df
        self.max_bars, self.default_sl_atr, self.default_tp_atr = max_bars, default_sl_atr, default_tp_atr
        from core.indicators import atr as _atr
        self.atr = _atr(df).bfill().values
        self.o, self.h, self.l, self.c, self.v = (df[k].values.astype(float) for k in ("open", "high", "low", "close", "volume"))
        self.cash0 = self.cash = cash
        self.comm = commission or PercentCommission(0.0005)
        self.slip = slippage_bps
        self.coo = cheat_on_open
        self.risk_pct = risk_pct
        self.position = 0.0
        self.entry_px = 0.0
        self.stop = self.limit = None
        self.orders, self.queue, self.trades, self.equity = [], [], [], []
        self.pending_bracket = None
        self.i = 0

    def submit(self, order):
        order.created = self.i
        self.queue.append(order)
        return order

    def _fill(self, order, px, i, reason):
        px = fixed_bps_slippage(px, order.side, self.slip)
        size = order.size
        if size is None:  # risk-based sizer (Backtrader Sizer): risk_pct of equity to the bracket stop (finalised below)
            stop = self.pending_bracket[0] if self.pending_bracket else None
            size = self.cash * self.risk_pct / 100 / abs(px - stop) if stop is not None and np.isfinite(stop) and abs(px - stop) > 0 else self.cash * 0.95 / px
            size = min(size, self.cash * 5 / px)
        fee = 0.0
        if self.position == 0:
            self.position = order.side * size; self.entry_px = px; self.entry_i = i
            if self.pending_bracket:
                self.stop, self.limit = self.pending_bracket; self.pending_bracket = None
            sd = order.side; a = self.atr[max(i - 1, 0)]
            if self.stop is None or not np.isfinite(self.stop) or (sd > 0 and self.stop >= px) or (sd < 0 and self.stop <= px):
                self.stop = px - sd * self.default_sl_atr * a
            if self.limit is None or not np.isfinite(self.limit) or (sd > 0 and self.limit <= px) or (sd < 0 and self.limit >= px):
                self.limit = px + sd * self.default_tp_atr * a
            if order.size is None:  # re-size on the actual (default) stop; risk distance includes round-trip commission
                rpu = abs(px * (1 + sd * getattr(self.comm, "pct", 0.0)) - self.stop)
                if rpu > 0:
                    size = min(self.cash * self.risk_pct / 100 / rpu, self.cash * 5 / px); self.position = sd * size
        else:
            pnl = (px - self.entry_px) * self.position
            fee = self.comm(self.entry_px, abs(self.position)) + self.comm(px, abs(self.position))
            self.cash += pnl - fee
            self.trades.append(dict(entry_i=self.entry_i, exit_i=i, side=int(np.sign(self.position)), entry=self.entry_px, exit=px, pnl=pnl - fee,
                                    pnl_pct=pnl / (self.entry_px * abs(self.position)) * 100, bars=i - self.entry_i, reason=reason))
            self.position = 0.0; self.stop = self.limit = None
        order.status = "filled"; self.orders.append(order)

    def run(self, strategy_cls, **params):
        strat = strategy_cls(self)
        strat.p.update(params)
        strat.start()
        n = len(self.df)
        for i in range(n):
            self.i = i
            # 1) fill queued orders at this bar's open (orders created on previous bar) — Backtrader default
            for od in list(self.queue):
                if od.created < i or self.coo:
                    self._fill(od, self.o[i], i, od.reason); self.queue.remove(od)
            # 2) bracket exits inside the bar (stop first — conservative, like Backtrader's default ordering)
            if self.position != 0 and (self.stop is not None or self.limit is not None):
                side = np.sign(self.position)
                hit_stop = self.stop is not None and ((side > 0 and self.l[i] <= self.stop) or (side < 0 and self.h[i] >= self.stop))
                hit_lim = self.limit is not None and ((side > 0 and self.h[i] >= self.limit) or (side < 0 and self.l[i] <= self.limit))
                if hit_stop:
                    gap = (side > 0 and self.o[i] < self.stop) or (side < 0 and self.o[i] > self.stop)
                    self._fill(Order(-side, abs(self.position)), self.o[i] if gap else self.stop, i, "stop")
                elif hit_lim:
                    self._fill(Order(-side, abs(self.position)), self.limit, i, "limit")
            # 2b) time stop (max_bars) — closes at the bar close like Backtrader's Order.Close
            if self.position != 0 and self.max_bars and i - self.entry_i >= self.max_bars:
                self._fill(Order(-np.sign(self.position), abs(self.position)), self.c[i], i, "time")
            # 3) strategy logic on the closed bar
            bar = dict(open=self.o[i], high=self.h[i], low=self.l[i], close=self.c[i], volume=self.v[i])
            strat.next(i, bar)
            # 4) mark-to-market
            mtm = self.cash + ((self.c[i] - self.entry_px) * self.position if self.position != 0 else 0.0)
            self.equity.append(mtm)
        if self.position != 0:
            self._fill(Order(-np.sign(self.position), abs(self.position)), self.c[-1], n - 1, "end")
            self.equity[-1] = self.cash
        return self.analyzers()

    # ------------------------------------------------------------------ analyzers (Backtrader names)
    def analyzers(self):
        eq = pd.Series(self.equity, index=self.df.index[:len(self.equity)])
        tr = pd.DataFrame(self.trades)
        dd = (eq / eq.cummax() - 1).min() * 100 if len(eq) else 0.0
        out = dict(trades=int(len(tr)), return_pct=float(eq.iloc[-1] / self.cash0 * 100 - 100) if len(eq) else 0.0, max_dd_pct=float(-dd))
        if len(tr):
            out["win_rate"] = float((tr.pnl > 0).mean() * 100)
            out["profit_factor"] = float(tr.pnl[tr.pnl > 0].sum() / max(-tr.pnl[tr.pnl <= 0].sum(), 1e-9))
            out["sqn"] = sqn(tr.pnl.values)
        return out, eq, tr


def sqn(pnls):
    """Van Tharp's System Quality Number (Backtrader analyzer): sqrt(N) × mean(pnl) / std(pnl); 1.6–1.9 below avg,
    2.0–2.4 average, 2.5–2.9 good, 3–5 excellent, 5–6.9 superb, 7+ 'Holy Grail' (Tharp's scale)."""
    p = np.asarray(pnls, float)
    if len(p) < 2 or p.std(ddof=1) == 0:
        return 0.0
    return float(np.sqrt(min(len(p), 100)) * p.mean() / p.std(ddof=1))


def sqn_label(x):
    for th, lab in ((7, "Holy Grail?"), (5, "superb"), (3, "excellent"), (2.5, "good"), (2.0, "average"), (1.6, "below average")):
        if x >= th:
            return lab
    return "poor"


# ------------------------------------------------------------------ adapter: any ProTrader strategy → event engine
class SignalStrategy(Strategy):
    """Runs a ProTrader StrategyResult inside the event engine (bracket = strategy's stop/target)."""
    params = {"res": None, "allow_short": True}

    def start(self):
        r = self.p["res"]
        self.sig = r.signal.fillna(0).astype(int).values
        self.st = r.stop.values if r.stop is not None else np.full(len(self.sig), np.nan)
        self.tg = r.target.values if r.target is not None else np.full(len(self.sig), np.nan)
        self.xl = r.exit_long.fillna(False).values if getattr(r, "exit_long", None) is not None else np.zeros(len(self.sig), bool)
        self.xs = r.exit_short.fillna(False).values if getattr(r, "exit_short", None) is not None else np.zeros(len(self.sig), bool)

    def next(self, i, bar):
        pos = np.sign(self.e.position)
        if pos != 0:
            if (pos > 0 and self.xl[i] and i > self.e.entry_i) or (pos < 0 and self.xs[i] and i > self.e.entry_i) or self.sig[i] == -pos:
                self.close("reverse" if self.sig[i] == -pos else "rule")
                pos = 0  # the close fills at this bar's close; a fresh signal on the same bar enters next open (vectorised parity)
            else:
                return
        s = self.sig[i]
        if s != 0 and (self.p["allow_short"] or s == 1) and not self.e.queue:
            self.bracket(int(s), None, self.st[i] if np.isfinite(self.st[i]) else None, self.tg[i] if np.isfinite(self.tg[i]) else None)


def parity_check(df, res, **kw):
    """Compare vectorised backtester vs event engine on the same signals; returns dict with both stats & difference."""
    from core.backtest import run_backtest
    sym = df.attrs.get("symbol")
    comm_bps, slip_bps = 5.0, 2.0
    if sym:
        from core.costs import cost_for
        cm = cost_for(sym, 1.0); comm_bps, slip_bps = cm["commission_bps"], cm["slippage_bps"]
    vec = run_backtest(df, res, commission_bps=comm_bps, slippage_bps=slip_bps, slip_atr=0.0, symbol=sym)
    bk = getattr(res, "bt_kwargs", None) or {}
    eng = EventEngine(df, commission=PercentCommission(comm_bps / 1e4), slippage_bps=slip_bps, max_bars=bk.get("max_bars", 200))
    ev, eq, tr = eng.run(SignalStrategy, res=res, allow_short=bk.get("allow_short", True))
    return dict(vectorised=dict(trades=vec.stats["trades"], return_pct=float(vec.stats["return_pct"]), max_dd_pct=float(vec.stats["max_dd_pct"]), pf=float(vec.stats["profit_factor"])),
                event=dict(trades=ev["trades"], return_pct=ev["return_pct"], max_dd_pct=ev["max_dd_pct"], pf=ev.get("profit_factor", 0.0), sqn=ev.get("sqn", 0.0)),
                trade_count_gap=abs(vec.stats["trades"] - ev["trades"]), return_gap_pct=abs(float(vec.stats["return_pct"]) - ev["return_pct"]))


# ------------------------------------------------------------------ Zipline pipeline + LEAN consolidators / framework
def pipeline_rank(price_dict, window=126, top=3):
    """Zipline-style cross-sectional factor: momentum (window-return) rank across the universe on the last bar."""
    rows = []
    for sym, df in price_dict.items():
        if len(df) > window + 1:
            c = df["close"]
            rows.append(dict(symbol=sym, momentum=float(c.iloc[-1] / c.iloc[-window - 1] - 1), volatility=float(np.log(c).diff().tail(window).std() * np.sqrt(252))))
    f = pd.DataFrame(rows)
    if f.empty:
        return f
    f["mom_rank"] = f["momentum"].rank(ascending=False).astype(int)
    f["vol_rank"] = f["volatility"].rank().astype(int)
    f["score"] = f["mom_rank"] * 0.7 + f["vol_rank"] * 0.3
    f = f.sort_values("score").reset_index(drop=True)
    top = max(1, min(top, len(f) // 2))
    f["longs"] = f.index < top
    f["shorts"] = f.index >= len(f) - top
    return f


def consolidate(df, factor):
    """LEAN consolidator: n base bars → 1 bar (only completed bars)."""
    idx = np.arange(len(df)) // factor
    g = df.groupby(idx)
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last(), "volume": g["volume"].sum()})
    out.index = g.apply(lambda x: x.index[-1])
    full = g.size() == factor
    return out[full.values]


class AlgorithmFramework:
    """LEAN Algorithm Framework: Alpha (insights) → PortfolioConstruction (weights) → RiskManagement → Execution (orders).
    Pure-function composition so the desk can display each stage."""

    def __init__(self, alpha, portfolio="equal", max_weight=0.25, max_dd_pct=15.0):
        self.alpha, self.portfolio, self.max_w, self.max_dd = alpha, portfolio, max_weight, max_dd_pct

    def run(self, price_dict, equity_curve=None):
        insights = self.alpha(price_dict)  # dict sym -> (+1/-1/0, confidence 0..1)
        active = {s: v for s, v in insights.items() if v[0] != 0}
        # portfolio construction
        if self.portfolio == "equal":
            w = {s: v[0] / max(len(active), 1) for s, v in active.items()}
        else:  # confidence-weighted (InsightWeightingPortfolioConstructionModel)
            tot = sum(v[1] for v in active.values()) or 1
            w = {s: v[0] * v[1] / tot for s, v in active.items()}
        # risk management: max weight per asset & drawdown kill-switch (MaximumDrawdownPercentPortfolio)
        w = {s: float(np.clip(x, -self.max_w, self.max_w)) for s, x in w.items()}
        halted = False
        if equity_curve is not None and len(equity_curve) > 1:
            dd = (1 - equity_curve[-1] / np.max(equity_curve)) * 100
            if dd > self.max_dd:
                w = {s: 0.0 for s in w}; halted = True
        # execution: immediate (ImmediateExecutionModel) → list of target orders
        orders = [dict(symbol=s, target_weight=x, action="BUY" if x > 0 else ("SELL" if x < 0 else "FLAT")) for s, x in w.items()]
        return dict(insights=insights, weights=w, orders=orders, halted=halted)


def freqai_schedule(n_bars, train_period=2000, backtest_period=200, live_retrain_every=200):
    """FreqAI: rolling train_period_days / backtest_period_days windows; returns list of (train_start, train_end, test_end)."""
    out = []
    start = 0
    while start + train_period + backtest_period <= n_bars:
        out.append((start, start + train_period, start + train_period + backtest_period))
        start += backtest_period
    return out
