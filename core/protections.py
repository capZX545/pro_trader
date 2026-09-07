"""
Freqtrade-style Protections (docs: freqtrade.io/en/stable/plugins/#protections), re-implemented for our backtester,
forward test and live engine.

  StoplossGuard   – if ≥ trade_limit stop-loss exits happened in the last lookback candles → lock for stop_duration
  MaxDrawdown     – if drawdown of closed trades in lookback > max_allowed_drawdown → lock
  CooldownPeriod  – no new entry for N candles after any exit (avoids immediate re-entry)
  LowProfitPairs  – if the pair's profit over lookback < required_profit (with ≥ trade_limit trades) → lock that pair

All locks are in candles and are evaluated at the candle where a new entry is considered.
A ProtectionManager is fed closed trades (exit_bar_index, pnl_pct, reason) and answers `locked(bar_index)`.
"""
from dataclasses import dataclass, field

DEFAULT_PROTECTIONS = [
    dict(method="CooldownPeriod", stop_duration_candles=2),
    dict(method="StoplossGuard", lookback_period_candles=48, trade_limit=4, stop_duration_candles=12, only_per_pair=False),
    dict(method="MaxDrawdown", lookback_period_candles=200, trade_limit=10, max_allowed_drawdown=0.15, stop_duration_candles=48),
    dict(method="LowProfitPairs", lookback_period_candles=120, trade_limit=6, required_profit=0.0, stop_duration_candles=60),
]


@dataclass
class ClosedTrade:
    exit_bar: int
    pnl_pct: float
    reason: str
    pair: str = ""


@dataclass
class ProtectionManager:
    config: list = field(default_factory=lambda: [dict(p) for p in DEFAULT_PROTECTIONS])
    trades: list = field(default_factory=list)
    lock_until: int = -1
    lock_reason: str = ""
    lock_log: list = field(default_factory=list)

    def on_close(self, exit_bar, pnl_pct, reason, pair=""):
        self.trades.append(ClosedTrade(exit_bar, pnl_pct, reason, pair))
        self._evaluate(exit_bar, pair)

    def _recent(self, bar, lookback, pair=None):
        return [t for t in self.trades if bar - t.exit_bar <= lookback and (pair is None or t.pair == pair)]

    def _lock(self, until, reason):
        if until > self.lock_until:
            self.lock_until = until
            self.lock_reason = reason
            self.lock_log.append((until, reason))

    def _evaluate(self, bar, pair=""):
        for p in self.config:
            m = p["method"]
            dur = p.get("stop_duration_candles", 0)
            if m == "CooldownPeriod":
                self._lock(bar + dur, "cooldown")
            elif m == "StoplossGuard":
                rec = self._recent(bar, p.get("lookback_period_candles", 48), pair if p.get("only_per_pair") else None)
                n_sl = sum(1 for t in rec if t.reason.startswith("stop") and t.pnl_pct < p.get("required_profit", 0.0))
                if n_sl >= p.get("trade_limit", 4):
                    self._lock(bar + dur, f"stoploss_guard({n_sl})")
            elif m == "MaxDrawdown":
                rec = self._recent(bar, p.get("lookback_period_candles", 200))
                if len(rec) >= p.get("trade_limit", 10):
                    eq, peak, dd = 1.0, 1.0, 0.0
                    for t in sorted(rec, key=lambda x: x.exit_bar):
                        eq *= 1 + t.pnl_pct / 100
                        peak = max(peak, eq)
                        dd = max(dd, 1 - eq / peak)
                    if dd > p.get("max_allowed_drawdown", 0.15):
                        self._lock(bar + dur, f"max_drawdown({dd * 100:.0f}%)")
            elif m == "LowProfitPairs":
                rec = self._recent(bar, p.get("lookback_period_candles", 120), pair)
                if len(rec) >= p.get("trade_limit", 6):
                    prof = sum(t.pnl_pct for t in rec)
                    if prof < p.get("required_profit", 0.0) * 100:
                        self._lock(bar + dur, f"low_profit({prof:+.1f}%)")

    def locked(self, bar):
        return bar <= self.lock_until

    def summary(self):
        from collections import Counter
        c = Counter(r.split("(")[0] for _, r in self.lock_log)
        return dict(c)
