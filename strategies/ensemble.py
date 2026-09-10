"""
Robust Ensemble — the "minimum loss" strategy.
Only enters when ≥ K validated strategies (robustness score ≥ threshold from Validation Lab) agree on direction
within a small window, AND the regime filter passes (Choppiness < 60, ATR not exploding). Uses the tightest
stop among agreeing strategies and a conservative 2R target.
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta


class RobustEnsemble(Strategy):
    id = "ensemble"
    name_en = "★ Robust Ensemble (validated-strategy confluence)"
    name_fa = "★ آنسامبل مقاوم (هم‌راستایی استراتژی‌های تأییدشده)"
    category = "Ensemble"
    author = "ProTrader Validation Lab — built from strategies that survived out-of-sample tests"
    difficulty = 2
    timeframes = "1h – 1d"
    params = {"min_score": 45, "min_agree": 2, "window": 3, "chop_max": 60, "atr_spike": 2.5, "tp_r": 2.0}
    description_en = ("Instead of trusting one strategy, trade only when at least 2 strategies that passed walk-forward validation "
                      "(robustness score ≥ 45) fire in the same direction within 3 bars, and the market is not choppy or in a "
                      "volatility spike. Fewer trades, much lower loss frequency. Re-run the Validation Lab to refresh members.")
    description_fa = ("به‌جای اعتماد به یک استراتژی، فقط وقتی معامله کن که حداقل ۲ استراتژی که از اعتبارسنجی واک‌فوروارد گذشته‌اند "
                      "(امتیاز مقاومت ≥ ۴۵) طی ۳ کندل در یک جهت سیگنال بدهند و بازار رنج یا در جهش نوسان نباشد. "
                      "معاملات کمتر، فرکانس ضرر بسیار کمتر. برای به‌روزرسانی اعضا، آزمایشگاه اعتبارسنجی را دوباره اجرا کن.")
    rules_en = ["Members: strategies with Validation Lab score ≥ min_score", "Signal: ≥ min_agree members same direction within `window` bars",
                "Regime: Choppiness(14) < 60 AND ATR < 2.5× its 100-bar median", "Stop: tightest member stop (capped 3 ATR); Target: 2R"]
    rules_fa = ["اعضا: استراتژی‌هایی با امتیاز آزمایشگاه ≥ min_score", "سیگنال: ≥ min_agree عضو در یک جهت طی `window` کندل",
                "رژیم: چاپینس(14) < ۶۰ و ATR < ۲.۵ برابر میانه ۱۰۰ کندل", "حد ضرر: کوچک‌ترین استاپ اعضا (حداکثر 3 ATR)؛ هدف: 2R"]
    pros_en = ["Diversified across logics", "Built-in regime & volatility filters", "Self-updating from validation results"]
    cons_en = ["Fewer trades", "Depends on validation data being fresh"]
    pros_fa = ["متنوع بین منطق‌های مختلف", "فیلترهای رژیم و نوسان داخلی", "خودکار از نتایج اعتبارسنجی به‌روز می‌شود"]
    cons_fa = ["معاملات کمتر", "به تازه بودن داده اعتبارسنجی وابسته است"]

    last_members = []
    abstain_reason = ""

    def members(self, df=None):
        """Market-aware membership: prefer strategies proven OUT-OF-SAMPLE on this very symbol/timeframe
        (mean OOS PF ≥ 1.1, ≥10 trades). Fall back to globally robust strategies (score ≥ min_score)."""
        from core.validation import load_cache
        import strategies as S
        cache = load_cache()
        sym, tf = (df.attrs.get("symbol"), df.attrs.get("tf")) if df is not None else (None, None)
        ids = []
        if sym:
            for k, v in cache.items():
                if k == self.id:
                    continue
                for row in v.get("rows", []):
                    if row.get("symbol") == sym and row.get("tf") == tf and row.get("trades", 0) >= 10 and row.get("oos_pf"):
                        pfs = [min(x, 3) for x in row["oos_pf"] if x == x]
                        if pfs and np.mean(pfs) >= 1.1 and np.mean([x > 1 for x in pfs]) >= 0.5:
                            ids.append(k)
        # Honest abstention: this market was validated and NOTHING held up out-of-sample → no members, no trades.
        validated_here = sym and any(row.get("symbol") == sym and row.get("tf") == tf
                                     for v in cache.values() for row in v.get("rows", []))
        if validated_here and len(ids) < self.p["min_agree"]:
            self.last_members = []
            self.abstain_reason = f"No strategy passed out-of-sample validation on {sym} {tf} — ensemble stays flat."
            return []
        if len(ids) < self.p["min_agree"]:
            ids = [k for k, v in cache.items() if v.get("score", 0) >= self.p["min_score"] and k != self.id]
        if len(ids) < self.p["min_agree"]:  # fallback default members if lab not run yet
            ids = ["binhv45", "nfi_lite", "silver_bullet", "holy_grail", "triple_rsi", "ibs", "macd_cci_bot", "clucmay"]
        # meta-strategies must never nest (ensemble ↔ regime_ensemble recursion would never terminate)
        META = {"ensemble", "regime_ensemble", "strategy_tournament", "meta_router"}
        ids = [i for i in ids if i not in META]
        self.last_members = ids
        return [S.REGISTRY[i] for i in ids if i in S.REGISTRY]

    def run(self, df):
        p = self.p
        from .bots import choppiness
        a = ta.atr(df)
        chop = choppiness(df, 14)
        regime = (chop < p["chop_max"]) & (a < a.rolling(100).median() * p["atr_spike"])
        n = len(df)
        votes_l = np.zeros(n)
        votes_s = np.zeros(n)
        stop_l = np.full(n, np.nan)
        stop_s = np.full(n, np.nan)
        overlays = {}
        for cls in self.members(df):
            try:
                r = cls().run(df)
            except Exception:
                continue
            s = r.signal.values
            st = r.stop.values if r.stop is not None else np.full(n, np.nan)
            l = (s == 1).astype(float)
            sh = (s == -1).astype(float)
            # spread each vote over `window` bars
            lw = pd.Series(l).rolling(p["window"], min_periods=1).max().values
            sw = pd.Series(sh).rolling(p["window"], min_periods=1).max().values
            votes_l += lw
            votes_s += sw
            # carry member stops forward within window
            stl = pd.Series(np.where(s == 1, st, np.nan)).ffill(limit=p["window"] - 1).values
            sts = pd.Series(np.where(s == -1, st, np.nan)).ffill(limit=p["window"] - 1).values
            stop_l = np.fmax(stop_l, stl)   # tightest long stop = highest
            stop_s = np.fmin(stop_s, sts)   # tightest short stop = lowest
        long = pd.Series((votes_l >= p["min_agree"]) & (votes_l > votes_s), index=df.index) & regime
        short = pd.Series((votes_s >= p["min_agree"]) & (votes_s > votes_l), index=df.index) & regime
        # trigger only on first bar the threshold is met
        long = long & ~long.shift(1).fillna(False).astype(bool)
        short = short & ~short.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        c = df.close.values
        av = a.values
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        li = np.where(sig.values == 1)[0]
        si = np.where(sig.values == -1)[0]
        for i in li:
            s_ = stop_l[i] if stop_l[i] == stop_l[i] else c[i] - 2 * av[i]
            s_ = max(s_, c[i] - 3 * av[i])
            if s_ >= c[i]:
                s_ = c[i] - 1.5 * av[i]
            stop.iloc[i] = s_
            tgt.iloc[i] = c[i] + p["tp_r"] * (c[i] - s_)
        for i in si:
            s_ = stop_s[i] if stop_s[i] == stop_s[i] else c[i] + 2 * av[i]
            s_ = min(s_, c[i] + 3 * av[i])
            if s_ <= c[i]:
                s_ = c[i] + 1.5 * av[i]
            stop.iloc[i] = s_
            tgt.iloc[i] = c[i] - p["tp_r"] * (s_ - c[i])
        return StrategyResult(sig, stop, tgt, panels={"Votes": {"Long votes": pd.Series(votes_l, index=df.index),
                                                                 "Short votes": pd.Series(-votes_s, index=df.index)},
                                                       "Choppiness": {"CHOP": chop}})
