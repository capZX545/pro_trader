"""
Hummingbot-style Avellaneda–Stoikov market-making calculator (analysis only, no order placement).

Formulas (Avellaneda & Stoikov 2008; Hummingbot 'Technical deep dive'):
    reservation price   r = s - q * gamma * sigma^2 * (T - t)
    optimal total spread δa+δb = gamma*sigma^2*(T-t) + (2/gamma) * ln(1 + gamma/kappa)
    bid = r - spread/2 ; ask = r + spread/2
    q = (base_inventory_value - target)/total  (normalised inventory deviation; Hummingbot uses target %)
    kappa (order-book liquidity) – estimated from trading intensity; offline we approximate via
      kappa = 1 / (median abs candle return)   (higher activity per unit price ⇒ higher kappa)
Also: Pure market making (Hummingbot pure_market_making) – symmetrical spreads around mid with inventory skew,
and 'ping-pong' logic; and Blackbird-style cross-exchange spread check (spread_entry / spread_exit).
"""
import math
import numpy as np


def instant_volatility(close, n=100):
    c = np.asarray(close, dtype=float)[-n - 1:]
    if len(c) < 5:
        return 0.0
    return float(np.std(np.diff(c), ddof=1))  # absolute price volatility per candle (Hummingbot instant_volatility)


def estimate_kappa(close, n=100):
    c = np.asarray(close, dtype=float)[-n - 1:]
    r = np.abs(np.diff(c)) / c[:-1]
    r = r[r > 0]
    if len(r) == 0:
        return 1.0
    return float(1.0 / np.median(r))


def avellaneda_quotes(mid, sigma, q, gamma=0.1, kappa=None, t_frac=0.0, close=None):
    """
    mid: mid price; sigma: price volatility per unit time (same units as mid); q: inventory deviation
    (+ long vs target, - short); gamma: risk factor; kappa: liquidity; t_frac: fraction of session elapsed
    (0..1; use 0 for infinite horizon behaviour). Returns dict with reservation, spread, bid, ask.
    """
    if kappa is None:
        kappa = estimate_kappa(close) if close is not None else 1.0
    gamma = max(gamma, 1e-9)
    T_t = max(1.0 - t_frac, 0.0)
    res = mid - q * gamma * sigma ** 2 * T_t
    spread = gamma * sigma ** 2 * T_t + (2.0 / gamma) * math.log(1.0 + gamma / kappa)
    bid = res - spread / 2
    ask = res + spread / 2
    return dict(reservation=res, spread=spread, spread_pct=spread / mid * 100 if mid else 0,
                bid=bid, ask=ask, skew_pct=(res - mid) / mid * 100 if mid else 0,
                kappa=kappa, sigma=sigma, gamma=gamma, ok=bid > 0)


def pure_mm_quotes(mid, bid_spread=0.002, ask_spread=0.002, inventory_skew=0.0, levels=1, level_step=0.001):
    """Hummingbot pure_market_making: symmetric % spreads with inventory skew; multiple levels."""
    out = []
    for i in range(levels):
        bs = bid_spread + i * level_step + max(inventory_skew, 0)
        as_ = ask_spread + i * level_step + max(-inventory_skew, 0)
        out.append(dict(level=i + 1, bid=mid * (1 - bs), ask=mid * (1 + as_), bid_pct=bs * 100, ask_pct=as_ * 100))
    return out


def blackbird_spread(bid_a, ask_a, bid_b, ask_b, fee_a=0.001, fee_b=0.001, spread_entry=0.008, spread_exit=-0.002):
    """
    Blackbird: long on exchange with lower ask, short on the one with higher bid, when
    (bid_short - ask_long)/ask_long - fees > spread_entry ; close when spread < spread_exit.
    """
    res = []
    for long_ex, ask_l, short_ex, bid_s in (("A", ask_a, "B", bid_b), ("B", ask_b, "A", bid_a)):
        gross = (bid_s - ask_l) / ask_l
        net = gross - 2 * (fee_a + fee_b)
        res.append(dict(long=long_ex, short=short_ex, gross_pct=gross * 100, net_pct=net * 100,
                        signal=net > spread_entry, exit=net < spread_exit))
    return res


def market_making_edge_report(df, gamma=0.1, target_inventory=0.5, current_inventory=0.5, fee=0.001):
    """Given OHLCV, estimate whether A-S quotes clear round-trip fees (spread > 2*fee) – the MM 'edge' check."""
    close = df["close"].values
    mid = float(close[-1])
    # work in normalised (return) units: s=1, sigma = per-candle return std, kappa = 1/median|return|  (consistent units)
    sigma = instant_volatility(close) / mid
    kappa = estimate_kappa(close)
    q = (current_inventory - target_inventory) * 2  # -1..1
    qn = avellaneda_quotes(1.0, sigma, q, gamma, kappa, 0.0)
    qt = dict(qn)
    for k in ("reservation", "bid", "ask", "spread"):
        qt[k] = qn[k] * mid
    qt["spread_pct"] = qn["spread"] * 100
    qt["skew_pct"] = (qn["reservation"] - 1.0) * 100
    rt_fee_pct = 2 * fee * 100
    qt["fee_rt_pct"] = rt_fee_pct
    qt["edge_pct"] = qt["spread_pct"] - rt_fee_pct
    qt["viable"] = qt["ok"] and qt["edge_pct"] > 0
    return qt
