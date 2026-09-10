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
    # Iran Gold - real market costs (much higher than international)
    # طلای ایران: کارمزد طلا فروشی + اسپرد خرید/فروش
    # 18 عیار: 1% commission + 0.5% spread = 1.5% per side, 3% roundtrip
    # سکه: 0.5% commission + 0.3% spread = 0.8% per side, 1.6% roundtrip
    # ولی برای احتیاط بیشتر: commission بالاتر
    "iran_gold":   dict(commission=100.0, spread_half=50.0, slip_atr=0.05),  # 1% + 0.5% = 150 bps per side
    "iran_coin":   dict(commission=50.0, spread_half=30.0, slip_atr=0.04),   # 0.5% + 0.3% = 80 bps
    "iran_coin_half": dict(commission=80.0, spread_half=50.0, slip_atr=0.05), # نیم: 0.8% + 0.5%
    "iran_coin_quarter": dict(commission=100.0, spread_half=80.0, slip_atr=0.06), # ربع: 1% + 0.8%
    "iran_coin_gram": dict(commission=150.0, spread_half=100.0, slip_atr=0.08), # گرمی: 1.5% + 1%
    "iran_dollar": dict(commission=20.0, spread_half=20.0, slip_atr=0.03), # دلار آزاد: 0.2% + 0.2%
    "default":     dict(commission=5.0,  spread_half=2.0, slip_atr=0.03),
}
MAJORS = {"BTC/USDT", "ETH/USDT"}


def asset_class(symbol_name):
    # Iran Gold specific - must check first
    if any(x in symbol_name for x in ["طلای 18", "طلای 24", "مثقال", "Gold 18K (Iran)", "Gold 24K (Iran)", "Mesghal"]):
        return "iran_gold"
    if "سکه امامی" in symbol_name or "سکه بهار" in symbol_name or "Emami Coin" in symbol_name or "Bahar Azadi" in symbol_name:
        return "iran_coin"
    if "نیم سکه" in symbol_name or "Half Coin" in symbol_name:
        return "iran_coin_half"
    if "ربع سکه" in symbol_name or "Quarter Coin" in symbol_name:
        return "iran_coin_quarter"
    if "گرمی" in symbol_name or "Gram Coin" in symbol_name:
        return "iran_coin_gram"
    if "دلار آزاد" in symbol_name or "USD/IRR" in symbol_name or "IR-USD" in symbol_name:
        return "iran_dollar"
    if "انس طلا" in symbol_name or "IR-OUNCE" in symbol_name:
        return "commodities"  # Ounce is international
    
    for cat, d in UNIVERSE.items():
        if symbol_name in d:
            c = cat.lower()
            if "iran" in c or "gold" in c.lower() and "iran" in c:
                # Iran Gold category
                if "سکه" in symbol_name or "Coin" in symbol_name:
                    if "نیم" in symbol_name or "Half" in symbol_name:
                        return "iran_coin_half"
                    if "ربع" in symbol_name or "Quarter" in symbol_name:
                        return "iran_coin_quarter"
                    if "گرمی" in symbol_name or "Gram" in symbol_name:
                        return "iran_coin_gram"
                    return "iran_coin"
                if "دلار" in symbol_name or "Dollar" in symbol_name or "USD" in symbol_name:
                    return "iran_dollar"
                return "iran_gold"
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


# ------------------------------------------------------------------ Phase 12: dynamic, per-bar cost model
# What was missing (and why the old numbers were optimistic):
#   * spread widens when volatility spikes and when volume is thin (news, Asian session, weekends in crypto);
#   * market impact grows with order size relative to bar volume (square-root law, Almgren/Kyle);
#   * perpetual-futures / CFD positions pay funding / overnight swap while held;
#   * every asset class has a session pattern (FX spread ×2–3 at 22:00–00:00 UTC, equities only RTH).
FUNDING = {  # per-day carry cost in bps when holding leveraged/CFD positions (used only if the backtest is told the position is leveraged)
    "crypto": 3.0, "crypto_alt": 4.0, "forex": 0.5, "indices": 1.0, "commodities": 1.2, "stocks": 1.5, "default": 2.0,
}


def dynamic_costs(df, symbol_name, stress=1.0, notional=10_000.0, leveraged=False):
    """Per-bar arrays (bps): spread_half, slippage(extra adverse on market/stop fills), impact, funding_per_bar.
    spread_half_t = base × (0.6 + 0.4 × vol_ratio_t) × session_mult_t × (1 + thin_volume_penalty_t)
    impact_t      = 10 bps × sqrt(notional / dollar_volume_t) (square-root law, capped)
    """
    import numpy as np, pandas as pd
    c = COSTS.get(asset_class(symbol_name), COSTS["default"])
    cls = asset_class(symbol_name)
    n = len(df)
    close = df["close"].values
    r = pd.Series(np.log(close)).diff().abs()
    vol = r.rolling(20, min_periods=5).mean(); vol_ratio = (vol / vol.rolling(200, min_periods=20).median()).fillna(1.0).clip(0.5, 4.0).values
    v = df["volume"].values.astype(float)
    if np.nansum(v) > 0:
        rv = (pd.Series(v) / pd.Series(v).rolling(50, min_periods=10).median()).fillna(1.0).clip(0.1, 10).values
        thin = np.where(rv < 0.5, (0.5 - rv) * 2.0, 0.0)          # up to +100 % spread when volume < 50 % of normal
        dollar_vol = v * close
        impact = np.where(dollar_vol > 0, 10.0 * np.sqrt(notional / np.maximum(dollar_vol, 1.0)), 0.0)
        impact = np.clip(impact, 0.0, 50.0)
    else:
        thin = np.zeros(n); impact = np.zeros(n)
    sess = np.ones(n)
    if isinstance(df.index, pd.DatetimeIndex):
        h = df.index.hour.values; dow = df.index.dayofweek.values
        if cls == "forex":
            sess = np.where((h >= 21) | (h < 1), 2.5, np.where((h >= 7) & (h < 17), 1.0, 1.4))   # rollover / Asia wider
            sess = np.where(dow >= 5, 3.0, sess)
        elif cls.startswith("crypto"):
            sess = np.where(dow >= 5, 1.3, 1.0)                                                   # weekend liquidity
        elif cls in ("stocks", "indices"):
            sess = np.where((h < 14) | (h >= 20), 1.8, 1.0)                                       # outside US RTH (UTC)
    spread_half = c["spread_half"] * (0.6 + 0.4 * vol_ratio) * sess * (1 + thin) * stress
    slippage = spread_half * 0.5 + impact * 0.5                                                 # extra adverse on market/stop fills
    funding_bar = np.zeros(n)
    if leveraged and isinstance(df.index, pd.DatetimeIndex) and n > 2:
        bar_days = ((df.index[1:] - df.index[:-1]).median() / pd.Timedelta(days=1))
        funding_bar[:] = FUNDING.get(cls, FUNDING["default"]) * bar_days * stress
    return dict(spread_half=spread_half, slippage=slippage, impact=impact, funding_bar=funding_bar, commission=c["commission"] * stress,
                slip_atr=c["slip_atr"] * stress)


def cost_summary(df, symbol_name, stress=1.0):
    """average round-trip cost in bps for the UI ('what one trade costs here')"""
    import numpy as np
    d = dynamic_costs(df, symbol_name, stress)
    rt = 2 * (d["commission"] + float(np.nanmean(d["spread_half"])) + float(np.nanmean(d["slippage"])))
    return dict(round_trip_bps=rt, spread_half_avg=float(np.nanmean(d["spread_half"])), spread_half_max=float(np.nanmax(d["spread_half"])),
                impact_avg=float(np.nanmean(d["impact"])), commission=d["commission"])
