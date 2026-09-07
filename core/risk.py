"""Risk management utilities."""
import math


def position_size(equity: float, risk_pct: float, entry: float, stop: float, contract_size: float = 1.0,
                  leverage: float = 1.0):
    """Return dict with units, notional, margin, risk amount, R:R helpers."""
    risk_amt = equity * risk_pct / 100.0
    dist = abs(entry - stop)
    if dist <= 0 or entry <= 0:
        return None
    units = risk_amt / (dist * contract_size)
    notional = units * entry * contract_size
    margin = notional / max(leverage, 1e-9)
    return {
        "risk_amount": risk_amt,
        "stop_distance": dist,
        "stop_distance_pct": dist / entry * 100,
        "units": units,
        "notional": notional,
        "margin_required": margin,
        "leverage_used": notional / equity if equity else 0,
    }


def rr_targets(entry: float, stop: float, ratios=(1, 1.5, 2, 3)):
    side = 1 if entry > stop else -1
    dist = abs(entry - stop)
    return {r: entry + side * dist * r for r in ratios}


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float):
    """Kelly % (as fraction). Use half-Kelly in practice."""
    if avg_loss == 0:
        return 0.0
    b = abs(avg_win / avg_loss)
    p = win_rate / 100.0
    q = 1 - p
    k = (b * p - q) / b
    return max(k, 0.0)


def risk_of_ruin(win_rate: float, rr: float, risk_per_trade_pct: float, ruin_level_pct: float = 50.0):
    """Approximate risk of ruin using the classic formula with fixed fractional betting."""
    p = win_rate / 100.0
    q = 1 - p
    if p * rr <= q:
        return 1.0
    # Edge per unit risk
    a = (p * rr - q)  # expectancy in R
    units = ruin_level_pct / risk_per_trade_pct
    try:
        ror = ((1 - a) / (1 + a)) ** units
    except Exception:
        ror = 1.0
    return min(max(ror, 0.0), 1.0)


def expectancy(win_rate: float, avg_win_r: float, avg_loss_r: float = 1.0):
    p = win_rate / 100.0
    return p * avg_win_r - (1 - p) * avg_loss_r


def max_trades_to_ruin(risk_pct: float, ruin_pct: float = 50.0):
    """How many consecutive losses to lose ruin_pct of account with fixed % risk."""
    if risk_pct <= 0:
        return math.inf
    return math.ceil(math.log(1 - ruin_pct / 100) / math.log(1 - risk_pct / 100))
