"""
Event-driven bar backtester.
- One position at a time (long or short)
- Entry at close of signal bar (or next open if `next_open=True`)
- Exit on stop / target (intrabar, conservative: stop checked first) or opposite signal or max_bars
- Position sizing: fixed fractional risk (% of equity per trade)
- Commission + slippage in bps
"""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: int              # +1 long, -1 short
    entry: float
    exit: float
    stop: float
    target: float
    size: float            # units
    pnl: float
    pnl_pct: float
    r_multiple: float
    bars: int
    reason: str


@dataclass
class BacktestResult:
    trades: list
    equity: pd.Series
    stats: dict
    signals: pd.Series
    initial_capital: float


def run_backtest(df: pd.DataFrame, res, initial_capital=10_000.0, risk_pct=1.0, commission_bps=5.0,
                 slippage_bps=2.0, max_bars=200, default_sl_atr=2.0, default_tp_atr=4.0, next_open=True,
                 allow_short=True, breakeven_at_r=None, slip_atr=None, symbol=None, stress=1.0,
                 protections=None, cost_model="dynamic", leveraged=False) -> BacktestResult:
    """slip_atr: extra adverse slippage on STOP fills as a fraction of ATR (fast-market fills). If `symbol` is given
    (or df.attrs['symbol'] is set) and costs are not explicitly passed, the per-asset-class cost model is used.
    protections: None | True (Freqtrade-style defaults) | list of protection dicts (see core/protections.py)."""
    pm = None
    if protections:
        from core.protections import ProtectionManager, DEFAULT_PROTECTIONS
        pm = ProtectionManager([dict(x) for x in (DEFAULT_PROTECTIONS if protections is True else protections)])
    from core.indicators import atr as _atr
    symbol = symbol or df.attrs.get("symbol")
    if symbol:
        from core.costs import cost_for
        cm = cost_for(symbol, stress)
        if commission_bps == 5.0 and slippage_bps == 2.0:   # defaults untouched → use realistic model
            commission_bps, slippage_bps = cm["commission_bps"], cm["slippage_bps"]
        if slip_atr is None:
            slip_atr = cm["slip_atr"]
    slip_atr = slip_atr or 0.0
    # Phase 12: dynamic per-bar spread/impact/funding when a symbol is known (cost_model="dynamic", default)
    dyn = None
    if symbol and cost_model == "dynamic":
        try:
            from core.costs import dynamic_costs
            dyn = dynamic_costs(df, symbol, stress, notional=initial_capital * risk_pct, leveraged=leveraged)
            commission_bps = dyn["commission"]
        except Exception:
            dyn = None
    bk = getattr(res, "bt_kwargs", None) or {}
    if bk:  # strategy-defined overrides (time stop / long-only) — part of the strategy's definition
        max_bars = bk.get("max_bars", max_bars)
        allow_short = bk.get("allow_short", allow_short)
        if protections is None and bk.get("protections"):
            from core.protections import ProtectionManager, DEFAULT_PROTECTIONS
            pr = bk["protections"]
            pm = ProtectionManager([dict(x) for x in (DEFAULT_PROTECTIONS if pr is True else pr)])
    sig = res.signal.fillna(0).astype(int).values
    o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
    n = len(df)
    atr_v = _atr(df).bfill().values
    stops = res.stop.values if res.stop is not None else np.full(n, np.nan)
    tgts = res.target.values if res.target is not None else np.full(n, np.nan)
    cost = (commission_bps + slippage_bps) / 10_000.0
    if dyn is not None:
        cost_arr = (commission_bps + dyn["spread_half"]) / 10_000.0          # limit-ish fills: commission + half spread
        cost_mkt = (commission_bps + dyn["spread_half"] + dyn["slippage"]) / 10_000.0   # market/stop fills: + slippage/impact
        fund_arr = dyn["funding_bar"] / 10_000.0
    else:
        cost_arr = np.full(n, cost); cost_mkt = np.full(n, cost); fund_arr = np.zeros(n)
    xl = res.exit_long.fillna(False).astype(bool).values if getattr(res, "exit_long", None) is not None else np.zeros(n, bool)
    xs = res.exit_short.fillna(False).astype(bool).values if getattr(res, "exit_short", None) is not None else np.zeros(n, bool)

    equity = np.full(n, initial_capital, dtype=float)
    cash = initial_capital
    pos = 0
    entry_px = stop_px = tgt_px = size = 0.0
    entry_i = 0
    trades = []
    be_moved = False

    def close_pos(i, px, reason):
        nonlocal cash, pos, be_moved
        c_i = cost_mkt[i] if reason.startswith("stop") or reason == "reverse" else cost_arr[i]
        px_eff = px * (1 - c_i * pos)  # slippage against us
        pnl = (px_eff - entry_px) * size * pos
        held = max(i - entry_i, 0)
        if held and fund_arr[entry_i:i].any():
            pnl -= float(fund_arr[entry_i:i].sum()) * entry_px * size   # funding / swap while held
        cash += pnl
        risk_per_unit = abs(entry_px - stop_px)
        r = (px_eff - entry_px) * pos / risk_per_unit if risk_per_unit > 0 else 0.0
        trades.append(Trade(df.index[entry_i], df.index[i], pos, entry_px, px_eff, stop_px, tgt_px, size,
                            pnl, pnl / (entry_px * size) * 100 * 1, r, i - entry_i, reason))
        pos = 0
        be_moved = False
        if pm is not None:
            pm.on_close(i, trades[-1].pnl_pct, reason, symbol or "")

    for i in range(n):
        # manage open position
        if pos != 0:
            hit_stop = (l[i] <= stop_px) if pos == 1 else (h[i] >= stop_px)
            hit_tgt = (h[i] >= tgt_px) if pos == 1 else (l[i] <= tgt_px)
            # gap through stop at open
            if pos == 1 and o[i] < stop_px:
                close_pos(i, o[i] - slip_atr * atr_v[i], "stop(gap)")
            elif pos == -1 and o[i] > stop_px:
                close_pos(i, o[i] + slip_atr * atr_v[i], "stop(gap)")
            elif hit_stop:
                close_pos(i, stop_px - pos * slip_atr * atr_v[i], "stop")
            elif hit_tgt:
                close_pos(i, tgt_px, "target")
            elif i - entry_i >= max_bars:
                close_pos(i, c[i], "time")
            elif sig[i] == -pos:
                close_pos(i, c[i], "reverse")
            elif i > entry_i and ((pos == 1 and xl[i]) or (pos == -1 and xs[i])):
                close_pos(i, c[i], "rule")
            else:
                if breakeven_at_r and not be_moved:
                    rpu = abs(entry_px - stop_px)
                    if rpu > 0:
                        fav = (h[i] - entry_px) if pos == 1 else (entry_px - l[i])
                        if fav >= breakeven_at_r * rpu:
                            stop_px = entry_px
                            be_moved = True
        # new entry
        if pos == 0 and sig[i] != 0 and (allow_short or sig[i] == 1) and not (pm is not None and pm.locked(i)):
            side = sig[i]
            if next_open:
                if i + 1 >= n:
                    equity[i] = cash
                    continue
                ei = i + 1
                px = o[ei]
            else:
                ei = i
                px = c[i]
            px_eff = px * (1 + cost_mkt[min(ei, n - 1)] * side)
            sp = stops[i]
            tp = tgts[i]
            if np.isnan(sp) or (side == 1 and sp >= px_eff) or (side == -1 and sp <= px_eff):
                sp = px_eff - side * default_sl_atr * atr_v[i]
            if np.isnan(tp) or (side == 1 and tp <= px_eff) or (side == -1 and tp >= px_eff):
                tp = px_eff + side * default_tp_atr * atr_v[i]
            risk_amt = cash * risk_pct / 100.0
            rpu = abs(px_eff - sp)
            if rpu <= 0:
                equity[i] = cash
                continue
            sz = risk_amt / rpu
            # cap notional at 5x equity (leverage guard)
            sz = min(sz, cash * 5 / px_eff)
            pos, entry_px, stop_px, tgt_px, size, entry_i = side, px_eff, sp, tp, sz, ei
            if next_open and ei == i + 1:
                pass  # position opens next bar; mark equity flat this bar
        # mark-to-market
        if pos != 0 and i >= entry_i:
            equity[i] = cash + (c[i] - entry_px) * size * pos
        else:
            equity[i] = cash
    if pos != 0:
        close_pos(n - 1, c[n - 1], "open")
        equity[n - 1] = cash

    eq = pd.Series(equity, index=df.index)
    stats = compute_stats(trades, eq, initial_capital, df)
    if pm is not None:
        stats["protection_locks"] = pm.summary()
    return BacktestResult(trades, eq, stats, res.signal, initial_capital)


def compute_stats(trades, eq: pd.Series, initial, df):
    n = len(trades)
    if n == 0:
        return {"trades": 0, "net_profit": 0, "return_pct": 0, "win_rate": 0, "profit_factor": 0, "max_dd_pct": 0,
                "sharpe": 0, "avg_r": 0, "expectancy": 0, "avg_win": 0, "avg_loss": 0, "best": 0, "worst": 0,
                "avg_bars": 0, "longs": 0, "shorts": 0, "long_wr": 0, "short_wr": 0, "max_consec_loss": 0,
                "final_equity": initial, "cagr": 0, "calmar": 0, "recovery": 0}
    pnl = np.array([t.pnl for t in trades])
    r = np.array([t.r_multiple for t in trades])
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    gross_p = wins.sum()
    gross_l = -losses.sum()
    dd = (eq / eq.cummax() - 1) * 100
    rets = eq.pct_change().dropna()
    # annualisation factor from median bar spacing
    try:
        delta = (df.index[1:] - df.index[:-1]).median()
        bars_per_year = pd.Timedelta(days=365) / delta
    except Exception:
        bars_per_year = 252
    sharpe = (rets.mean() / rets.std() * np.sqrt(bars_per_year)) if rets.std() > 0 else 0.0
    years = max((df.index[-1] - df.index[0]).days / 365.25, 1e-6) if isinstance(df.index, pd.DatetimeIndex) else 1
    final = eq.iloc[-1]
    cagr = ((final / initial) ** (1 / years) - 1) * 100 if final > 0 and years > 0.05 else (final / initial - 1) * 100
    max_dd = -dd.min()
    consec = cur = 0
    for p in pnl:
        cur = cur + 1 if p <= 0 else 0
        consec = max(consec, cur)
    longs = [t for t in trades if t.side == 1]
    shorts = [t for t in trades if t.side == -1]
    try:
        from core.stats import full_report
        rep = full_report(pnl)
    except Exception:
        rep = {}
    return {
        "wr_lo": rep.get("wr_lo", 0), "wr_hi": rep.get("wr_hi", 100), "pf_lo": rep.get("pf_lo", float("nan")),
        "pf_hi": rep.get("pf_hi", float("nan")), "t_stat": rep.get("t", 0), "grade": rep.get("grade", "D"),
        "need_n": rep.get("need_n", 0),
        "trades": n,
        "net_profit": pnl.sum(),
        "return_pct": (final / initial - 1) * 100,
        "final_equity": final,
        "win_rate": len(wins) / n * 100,
        "profit_factor": min(gross_p / gross_l, 9.99) if gross_l > 0 else 9.99,
        "max_dd_pct": max_dd,
        "sharpe": sharpe,
        "avg_r": r.mean(),
        "expectancy": pnl.mean(),
        "avg_win": wins.mean() if len(wins) else 0,
        "avg_loss": losses.mean() if len(losses) else 0,
        "best": pnl.max(),
        "worst": pnl.min(),
        "avg_bars": np.mean([t.bars for t in trades]),
        "longs": len(longs),
        "shorts": len(shorts),
        "long_wr": (sum(1 for t in longs if t.pnl > 0) / len(longs) * 100) if longs else 0,
        "short_wr": (sum(1 for t in shorts if t.pnl > 0) / len(shorts) * 100) if shorts else 0,
        "max_consec_loss": consec,
        "cagr": cagr,
        "calmar": (cagr / max_dd) if max_dd > 0 else 0,
        "recovery": (pnl.sum() / (max_dd / 100 * initial)) if max_dd > 0 else 0,
    }
