"""
Realistic transaction-cost model (per asset class), replacing the flat 5+2 bps used before.

All values are ROUND-TRIP-HALF (i.e. applied on each side) in basis points of price:
  commission  — exchange/broker fee per side
  spread_half — half the typical bid/ask spread (you buy at ask, sell at bid)
  slippage    — extra adverse fill vs. intended price on market/stop orders, in ATR% units
                (stops get filled worse in fast markets; scaled by the bar's ATR)
Sources (typical retail conditions 2024-25): Binance spot taker 10 bps; IBKR/US equities ≈1 bps + spread;
FX ECN 0.1-0.3 pip EUR/USD ≈ 0.1-0.3 bps + commission ~0.2 bps; CFD gold spread ≈ 2-3 bps; index CFD ≈ 1-2 bps.
"""
from core.data import UNIVERSE

# per asset class: commission bps, half-spread bps, slippage as fraction of ATR
COSTS = {
    "crypto":      dict(commission=10.0, spread_half=1.0, slip_atr=0.03),
    "crypto_alt":  dict(commission=10.0, spread_half=3.0, slip_atr=0.05),
    "stocks":      dict(commission=1.0,  spread_half=1.5, slip_atr=0.03),
    "indices":     dict(commission=0.5,  spread_half=1.0, slip_atr=0.02),
    "forex":       dict(commission=0.3,  spread_half=0.8, slip_atr=0.02),
    "commodities": dict(commission=0.5,  spread_half=2.0, slip_atr=0.03),
    "default":     dict(commission=5.0,  spread_half=2.0, slip_atr=0.03),
}
MAJORS = {"BTC/USDT", "ETH/USDT"}


def asset_class(symbol_name):
    for cat, d in UNIVERSE.items():
        if symbol_name in d:
            c = cat.lower()
            if c.startswith("crypto"):
                return "crypto" if symbol_name in MAJORS else "crypto_alt"
            if "forex" in c or "fx" in c:
                return "forex"
            if "commod" in c or "metal" in c or "energy" in c:
                return "commodities"
            if "ind" in c:
                return "indices"
            if "stock" in c or "equit" in c:
                return "stocks"
    return "default"


def cost_for(symbol_name, stress=1.0):
    """Returns dict(commission_bps, slippage_bps_fixed, slip_atr) for run_backtest. stress>1 multiplies everything
    (use 2.0 for a pessimistic 'bad broker / thin liquidity' scenario)."""
    c = COSTS.get(asset_class(symbol_name), COSTS["default"])
    return dict(commission_bps=c["commission"] * stress, slippage_bps=c["spread_half"] * stress,
                slip_atr=c["slip_atr"] * stress)
