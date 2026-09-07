"""
Strategy base class. Every strategy produces a `signal` Series:
   +1 = long entry, -1 = short entry, 0 = nothing
optionally plus `stop` and `target` Series (absolute prices) used by backtester.
"""
from dataclasses import dataclass, field
import pandas as pd
import numpy as np


@dataclass
class StrategyResult:
    signal: pd.Series                       # +1 / -1 / 0
    stop: pd.Series | None = None           # stop-loss price per entry bar
    target: pd.Series | None = None         # take-profit price per entry bar
    overlays: dict = field(default_factory=dict)   # name -> Series drawn on price chart
    panels: dict = field(default_factory=dict)     # name -> {series_name: Series} drawn in sub-panels
    levels: list = field(default_factory=list)     # list of (price, label, color) horizontal lines
    zones: list = field(default_factory=list)      # list of (start_idx, end_idx, lo, hi, color, label)
    exit_long: pd.Series | None = None      # rule-based exit for longs (True = close at this bar's close)
    exit_short: pd.Series | None = None     # rule-based exit for shorts
    bt_kwargs: dict = field(default_factory=dict)   # backtester overrides bundled with the strategy


class Strategy:
    # metadata
    id: str = "base"
    bt_kwargs: dict = {}          # backtester overrides (e.g. time stop, long-only) that are part of the strategy definition
    name_en: str = "Base"
    name_fa: str = "پایه"
    category: str = "Trend"          # Trend / Momentum / Mean-Reversion / Price-Action / Smart-Money / Volatility / Volume
    author: str = ""                 # who popularised it
    difficulty: int = 1              # 1..5
    timeframes: str = "any"
    params: dict = {}                # default params (editable in UI)
    description_en: str = ""
    description_fa: str = ""
    rules_en: list = []
    rules_fa: list = []
    pros_en: list = []
    cons_en: list = []
    pros_fa: list = []
    cons_fa: list = []

    def __init__(self, **kw):
        self.p = dict(self.params)
        self.p.update(kw)

    def run(self, df: pd.DataFrame) -> StrategyResult:
        raise NotImplementedError

    # ---- helpers ----
    @staticmethod
    def cross_up(a: pd.Series, b) -> pd.Series:
        b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
        return (a > b) & (a.shift(1) <= b.shift(1))

    @staticmethod
    def cross_down(a: pd.Series, b) -> pd.Series:
        b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
        return (a < b) & (a.shift(1) >= b.shift(1))

    @staticmethod
    def make_signal(long_cond: pd.Series, short_cond: pd.Series) -> pd.Series:
        sig = pd.Series(0, index=long_cond.index, dtype=int)
        sig[long_cond.fillna(False).astype(bool)] = 1
        sig[short_cond.fillna(False).astype(bool)] = -1
        return sig

    @staticmethod
    def atr_stops(df, sig, atr_s, sl_mult=1.5, tp_mult=3.0):
        stop = pd.Series(np.nan, index=df.index)
        target = pd.Series(np.nan, index=df.index)
        lo = sig == 1
        sh = sig == -1
        stop[lo] = df.close[lo] - sl_mult * atr_s[lo]
        target[lo] = df.close[lo] + tp_mult * atr_s[lo]
        stop[sh] = df.close[sh] + sl_mult * atr_s[sh]
        target[sh] = df.close[sh] - tp_mult * atr_s[sh]
        return stop, target
