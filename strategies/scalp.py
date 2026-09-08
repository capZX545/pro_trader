"""
Low-timeframe (1m–15m) signal library — Phase 16 "fast signals".

Sources studied for this module (all summarised in core/library.py ▸ RESEARCH):
  * Stratbase/Upscale/Tradezella/ChartingLens 2026 scalping studies: only VWAP-anchored & limit-style
    mean-reversion setups survive realistic fees on 1m; EMA 9/21 micro-crosses lose after costs; a
    London/NY-overlap time filter lifted VWAP-pullback PF 1.14 → 1.32.
  * Crypto order-flow (CVD / delta divergence, Wyckoff spring + CVD, funding-rate crowding).
  * Bob Volman "Understanding Price Action" (5-min double-pressure / pullback reversal),
    Al Brooks "Trading Price Action Trends" (2-legged pullback H2/L2, EMA-20 gap bars),
    Kevin Davey / Larry Connors intraday variants (time stop), Toby Crabel ORB & NR4/NR7 + inside day,
    Linda Raschke "Turtle Soup" 1m variant, ICT Silver-Bullet FVG, Market-Profile IB extension.

Every strategy: vectorised, returns StrategyResult(signal, stop, target, …); short-timeframe stops are
ATR-based and every scalp has a hard time stop (bt_kwargs max_bars) — scalps that don't work quickly are
closed rather than left to become swing trades.
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta


# ----------------------------------------------------------------------------- helpers
def _bar_minutes(df):
    if isinstance(df.index, pd.DatetimeIndex) and len(df) > 3:
        d = np.diff(df.index.values[-50:]).astype("timedelta64[s]").astype(float)
        d = d[d > 0]
        if len(d):
            return float(np.median(d)) / 60.0
    return 60.0


def _session_mask(df, start_h, end_h):
    """UTC hour window [start_h, end_h). Returns all-True if the index has no time."""
    if not isinstance(df.index, pd.DatetimeIndex):
        return pd.Series(True, index=df.index)
    h = df.index.hour
    if start_h <= end_h:
        m = (h >= start_h) & (h < end_h)
    else:
        m = (h >= start_h) | (h < end_h)
    return pd.Series(m, index=df.index)


def _anchored_vwap(df, anchor):
    """VWAP restarted at every True in `anchor` (session / day / swing)."""
    tp = (df.high + df.low + df.close) / 3
    grp = anchor.astype(int).cumsum()
    pv = (tp * df.volume).groupby(grp).cumsum()
    v = df.volume.groupby(grp).cumsum()
    return pv / v.replace(0, np.nan)


def _vwap_bands(df, vwap, n=60, k=2.0):
    dev = (df.close - vwap)
    sd = dev.rolling(n).std(ddof=0)
    return vwap + k * sd, vwap - k * sd, sd


def _cvd(df):
    """Cumulative volume delta proxy from OHLCV (no tick data): delta = volume × (close−open)/(high−low) style
    body-position estimate (Bulk Volume Classification, Easley/López de Prado/O'Hara)."""
    rng = (df.high - df.low).replace(0, np.nan)
    pos = ((df.close - df.low) / rng).clip(0, 1).fillna(0.5)
    delta = df.volume * (2 * pos - 1)
    return delta.cumsum(), delta


def _relvol(df, n=48):
    return df.volume / df.volume.rolling(n).mean().replace(0, np.nan)


def _pivot_low(s, left, right):
    ok = pd.Series(True, index=s.index)
    for i in range(1, left + 1):
        ok &= s < s.shift(i)
    for i in range(1, right + 1):
        ok &= s < s.shift(-i)
    return ok.fillna(False)


def _pivot_high(s, left, right):
    ok = pd.Series(True, index=s.index)
    for i in range(1, left + 1):
        ok &= s > s.shift(i)
    for i in range(1, right + 1):
        ok &= s > s.shift(-i)
    return ok.fillna(False)


# ----------------------------------------------------------------------------- 1. VWAP pullback scalp
class VWAPPullbackScalp(Strategy):
    id = "vwap_pullback_scalp"
    name_en = "VWAP Pullback Scalp (session-filtered)"
    name_fa = "اسکالپ پولبک به VWAP (با فیلتر سشن)"
    category = "Mean-Reversion"
    author = "Institutional VWAP desks; 2026 1-min backtest studies"
    difficulty = 2
    timeframes = "1m – 15m"
    params = {"trend_ema": 50, "touch_atr": 0.35, "sess_start": 12, "sess_end": 17, "rr": 1.8, "sl_atr": 1.2, "min_relvol": 0.6}
    bt_kwargs = {"max_bars": 24}
    description_en = ("The only 1-minute setup that stayed positive after fees in independent 2026 studies: trade WITH the "
                      "session bias (price above VWAP and EMA50 rising) and buy the first pullback that touches VWAP with a "
                      "rejection candle. Only during the London/New-York overlap (12–17 UTC) where PF improved 1.14 → 1.32.")
    description_fa = ("تنها ستاپ ۱ دقیقه‌ای که در مطالعات مستقل ۲۰۲۶ بعد از کارمزد مثبت ماند: هم‌جهت با سوگیری سشن (قیمت بالای VWAP "
                      "و EMA50 صعودی) و خرید اولین پولبکی که VWAP را لمس و رد می‌کند. فقط در هم‌پوشانی لندن/نیویورک (۱۲–۱۷ UTC) "
                      "که PF از ۱.۱۴ به ۱.۳۲ رسید.")
    rules_en = ["Bias: close > VWAP and EMA50 > EMA50[5] (long) / mirror for short",
                "Trigger: low touches VWAP ± 0.35 ATR and bar closes back in bias direction",
                "Time filter 12:00–17:00 UTC; relative volume ≥ 0.6", "Stop 1.2 ATR, target 1.8 R, time stop 24 bars"]
    rules_fa = ["سوگیری: قیمت > VWAP و EMA50 صعودی (خرید) / برعکس برای فروش",
                "تریگر: کف کندل VWAP ± ۰.۳۵ ATR را لمس کند و کندل در جهت سوگیری بسته شود",
                "فیلتر زمانی ۱۲ تا ۱۷ UTC؛ حجم نسبی ≥ ۰.۶", "حد ضرر ۱.۲ ATR، هدف ۱.۸R، حد زمانی ۲۴ کندل"]
    pros_en = ["Institutional anchor → real order flow", "Positive expectancy after fees in studies", "Clear invalidation"]
    cons_en = ["Few signals per day (3–5)", "Needs liquid majors", "Useless on choppy days with flat VWAP"]
    pros_fa = ["لنگر نهادی → جریان سفارش واقعی", "در مطالعات بعد از کارمزد مثبت", "ابطال واضح"]
    cons_fa = ["سیگنال کم در روز (۳ تا ۵)", "فقط ارزهای نقدشونده", "در روزهای رنج با VWAP صاف بی‌فایده"]

    def run(self, df):
        p = self.p
        v = ta.vwap(df)
        a = ta.atr(df, 14)
        e = ta.ema(df.close, p["trend_ema"])
        sess = _session_mask(df, p["sess_start"], p["sess_end"])
        rv = _relvol(df)
        up_bias = (df.close > v) & (e > e.shift(5))
        dn_bias = (df.close < v) & (e < e.shift(5))
        touch_lo = df.low <= v + p["touch_atr"] * a
        touch_hi = df.high >= v - p["touch_atr"] * a
        bull = df.close > df.open
        bear = df.close < df.open
        long = up_bias & touch_lo & bull & sess & (rv >= p["min_relvol"]) & (df.close.shift(1) > v.shift(1))
        short = dn_bias & touch_hi & bear & sess & (rv >= p["min_relvol"]) & (df.close.shift(1) < v.shift(1))
        # one entry per pullback: skip if previous bar already fired
        long &= ~long.shift(1).fillna(False).astype(bool)
        short &= ~short.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["sl_atr"] * p["rr"])
        ub, lb, _ = _vwap_bands(df, v)
        return StrategyResult(sig, st, tp, overlays={"VWAP": v, "VWAP+2σ": ub, "VWAP-2σ": lb, "EMA50": e},
                              panels={"RelVol": {"rel.volume": rv}}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 2. VWAP 2σ band fade
class VWAPBandFade(Strategy):
    id = "vwap_band_fade"
    name_en = "VWAP 2σ Band Fade (range days)"
    name_fa = "بازگشت از باند ۲σ VWAP (روزهای رنج)"
    category = "Mean-Reversion"
    author = "Brian Shannon (AVWAP) / TradeZella VWAP deviation"
    difficulty = 3
    timeframes = "1m – 15m"
    params = {"band_n": 60, "k": 2.0, "adx_max": 22, "rsi_n": 7, "sl_atr": 1.0}
    bt_kwargs = {"max_bars": 30}
    description_en = ("Fade a stretch to the ±2σ VWAP band when the tape is NOT trending (ADX < 22) and fast RSI(7) is "
                      "extreme; target is VWAP itself. Reported 60–70 % win rate with ~1:1 R:R in range regimes.")
    description_fa = ("وقتی بازار روند ندارد (ADX < 22) و RSI(7) در اشباع است، کشیدگی تا باند ±۲σ VWAP را فِید کن؛ هدف خودِ VWAP. "
                      "وین‌ریت گزارش‌شده ۶۰–۷۰٪ با R:R حدود ۱:۱ در رژیم رنج.")
    rules_en = ["ADX(14) < 22 (no trend)", "Long: low < VWAP − 2σ and RSI(7) < 20 and close back above band",
                "Target VWAP; stop 1 ATR beyond the band; time stop 30 bars"]
    rules_fa = ["ADX(14) < 22 (بدون روند)", "خرید: کف < VWAP − ۲σ و RSI(7) < 20 و بسته شدن دوباره داخل باند",
                "هدف VWAP؛ حد ضرر ۱ ATR پشت باند؛ حد زمانی ۳۰ کندل"]
    pros_en = ["High win rate", "Objective target (VWAP)"]
    cons_en = ["Dies on trend days — the ADX gate is essential", "R:R ≈ 1"]
    pros_fa = ["وین‌ریت بالا", "هدف عینی (VWAP)"]
    cons_fa = ["در روزهای رونددار می‌بازد — گیت ADX حیاتی است", "R:R ≈ ۱"]

    def run(self, df):
        p = self.p
        v = ta.vwap(df)
        ub, lb, sd = _vwap_bands(df, v, p["band_n"], p["k"])
        a = ta.atr(df, 14)
        adx, _, _ = ta.adx(df, 14)
        r = ta.rsi(df.close, p["rsi_n"])
        rng = adx < p["adx_max"]
        long = rng & (df.low < lb) & (df.close > lb) & (r < 20)
        short = rng & (df.high > ub) & (df.close < ub) & (r > 80)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = (lb - p["sl_atr"] * a)[sig == 1]; tgt[sig == 1] = v[sig == 1]
        stop[sig == -1] = (ub + p["sl_atr"] * a)[sig == -1]; tgt[sig == -1] = v[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"VWAP": v, "+2σ": ub, "−2σ": lb},
                              panels={"ADX": {"ADX": adx}, "RSI7": {"RSI(7)": r}}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 3. CVD divergence at level
class CVDDivergence(Strategy):
    id = "cvd_divergence"
    name_en = "CVD (Delta) Divergence at Swing"
    name_fa = "واگرایی دلتای تجمعی (CVD) روی سوینگ"
    category = "Volume"
    author = "Order-flow desks; Bulk-Volume-Classification proxy"
    difficulty = 4
    timeframes = "1m – 15m"
    params = {"pivot": 5, "lookback": 60, "sl_atr": 1.3, "rr": 2.0}
    bt_kwargs = {"max_bars": 40}
    description_en = ("Price prints a lower low but cumulative volume delta prints a higher low → sellers are exhausted / "
                      "being absorbed (accumulation). Mirror for tops. CVD is estimated from bar geometry (BVC) because "
                      "tick data is not needed. Highest conviction when it happens at a prior swing / range extreme.")
    description_fa = ("قیمت کف پایین‌تر می‌زند ولی دلتای تجمعی حجم کف بالاتر می‌سازد → فروشندگان خسته/جذب شده‌اند (انباشت). "
                      "برای سقف برعکس. CVD از هندسه کندل (BVC) تخمین زده می‌شود و به دیتای تیک نیاز ندارد. "
                      "بیشترین اعتبار وقتی روی سوینگ/کران رنج قبلی رخ دهد.")
    rules_en = ["Find pivot lows (5 bars each side)", "Long when new pivot low < previous pivot low AND CVD at pivot > CVD at previous pivot",
                "Entry on close of the confirming bar; stop 1.3 ATR under the low; target 2R; time stop 40 bars"]
    rules_fa = ["کف‌های پیوت (۵ کندل هر طرف) را پیدا کن", "خرید وقتی کف پیوت جدید < قبلی و CVD روی پیوت جدید > CVD پیوت قبلی",
                "ورود روی بسته شدن کندل تأیید؛ حد ضرر ۱.۳ ATR زیر کف؛ هدف 2R؛ حد زمانی ۴۰ کندل"]
    pros_en = ["Reads aggression, not just price", "Works on any liquid market"]
    cons_en = ["Proxy CVD is noisier than true tick delta", "Confirms with a lag of `pivot` bars"]
    pros_fa = ["تهاجم را می‌خواند نه فقط قیمت", "روی هر بازار نقدشونده‌ای کار می‌کند"]
    cons_fa = ["CVD تقریبی از دلتای تیک واقعی نویزی‌تر است", "با تأخیر `pivot` کندل تأیید می‌شود"]

    def run(self, df):
        p = self.p
        cvd, delta = _cvd(df)
        a = ta.atr(df, 14)
        pl = _pivot_low(df.low, p["pivot"], p["pivot"])
        ph = _pivot_high(df.high, p["pivot"], p["pivot"])
        # previous pivot values (forward-filled), compared at the moment a new pivot is CONFIRMED (shift by right bars)
        low_at = df.low.where(pl); cvd_lo_at = cvd.where(pl)
        prev_low = low_at.shift(1).ffill(); prev_cvd_lo = cvd_lo_at.shift(1).ffill()
        bull_div = pl & (df.low < prev_low) & (cvd > prev_cvd_lo)
        high_at = df.high.where(ph); cvd_hi_at = cvd.where(ph)
        prev_high = high_at.shift(1).ffill(); prev_cvd_hi = cvd_hi_at.shift(1).ffill()
        bear_div = ph & (df.high > prev_high) & (cvd < prev_cvd_hi)
        # pivot is only known `pivot` bars later → signal there (no look-ahead)
        long = bull_div.shift(p["pivot"]).fillna(False).astype(bool)
        short = bear_div.shift(p["pivot"]).fillna(False).astype(bool)
        # stale check: within lookback of the pivot pair
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        piv_low = df.low.shift(p["pivot"]); piv_high = df.high.shift(p["pivot"])
        stop[sig == 1] = (piv_low - p["sl_atr"] * a)[sig == 1]
        tgt[sig == 1] = (df.close + p["rr"] * (df.close - stop))[sig == 1]
        stop[sig == -1] = (piv_high + p["sl_atr"] * a)[sig == -1]
        tgt[sig == -1] = (df.close - p["rr"] * (stop - df.close))[sig == -1]
        return StrategyResult(sig, stop, tgt, panels={"CVD": {"CVD": cvd}, "Delta": {"hist": delta}}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 4. Turtle-soup 1m (stop-run reversal)
class StopRunReversalScalp(Strategy):
    id = "stop_run_scalp"
    name_en = "Stop-Run Reversal Scalp (Turtle Soup, intraday)"
    name_fa = "اسکالپ برگشت بعد از استاپ‌ران (تِرتل سوپ روزانه)"
    category = "Smart-Money"
    author = "Linda Raschke & Laurence Connors (Street Smarts), ICT"
    difficulty = 3
    timeframes = "1m – 15m"
    params = {"n": 20, "min_age": 4, "wick_ratio": 0.5, "sl_atr": 0.8, "rr": 2.0, "relvol": 1.2}
    bt_kwargs = {"max_bars": 20}
    description_en = ("Price pokes below the 20-bar low (that low must be ≥ 4 bars old — real resting stops) on above-average "
                      "volume and closes back inside with a long lower wick. The stop-run is the signal: buy the reclaim, stop "
                      "just under the sweep wick, target 2R.")
    description_fa = ("قیمت زیر کف ۲۰ کندلی (که باید ≥ ۴ کندل عمر داشته باشد — استاپ‌های واقعی) با حجم بالاتر از میانگین نفوذ می‌کند و "
                      "با شدوی بلند دوباره داخل بسته می‌شود. خودِ استاپ‌ران سیگنال است: خرید روی پس‌گیری، حد ضرر زیر شدو، هدف 2R.")
    rules_en = ["20-bar low at least 4 bars old", "Bar low < that low, close > that low, lower wick ≥ 50 % of range, rel.volume ≥ 1.2",
                "Stop 0.8 ATR below the wick low; target 2R; time stop 20 bars"]
    rules_fa = ["کف ۲۰ کندلی حداقل ۴ کندل قدیمی", "کف کندل < آن کف، بسته شدن > آن کف، شدوی پایین ≥ ۵۰٪ رنج، حجم نسبی ≥ ۱.۲",
                "حد ضرر ۰.۸ ATR زیر کفِ شدو؛ هدف 2R؛ حد زمانی ۲۰ کندل"]
    pros_en = ["Tiny stop, big R", "Exploits the most common intraday trap"]
    cons_en = ["Fails in genuine breakouts — volume + wick filters matter"]
    pros_fa = ["حد ضرر کوچک، R بزرگ", "از رایج‌ترین تلهٔ روزانه استفاده می‌کند"]
    cons_fa = ["در شکست‌های واقعی شکست می‌خورد — فیلتر حجم و شدو مهم است"]

    def run(self, df):
        p = self.p
        n = p["n"]
        a = ta.atr(df, 14)
        rng = (df.high - df.low).replace(0, np.nan)
        lo_n = df.low.shift(1).rolling(n).min()
        hi_n = df.high.shift(1).rolling(n).max()
        # age of the extreme: bars since the min occurred
        lo_pos = df.low.shift(1).rolling(n).apply(lambda x: n - 1 - int(np.argmin(x)), raw=True)
        hi_pos = df.high.shift(1).rolling(n).apply(lambda x: n - 1 - int(np.argmax(x)), raw=True)
        rv = _relvol(df)
        lw = (np.minimum(df.open, df.close) - df.low) / rng
        uw = (df.high - np.maximum(df.open, df.close)) / rng
        long = (df.low < lo_n) & (df.close > lo_n) & (lo_pos >= p["min_age"]) & (lw >= p["wick_ratio"]) & (rv >= p["relvol"])
        short = (df.high > hi_n) & (df.close < hi_n) & (hi_pos >= p["min_age"]) & (uw >= p["wick_ratio"]) & (rv >= p["relvol"])
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = (df.low - p["sl_atr"] * a)[sig == 1]; tgt[sig == 1] = (df.close + p["rr"] * (df.close - stop))[sig == 1]
        stop[sig == -1] = (df.high + p["sl_atr"] * a)[sig == -1]; tgt[sig == -1] = (df.close - p["rr"] * (stop - df.close))[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={f"Low{n}": lo_n, f"High{n}": hi_n}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 5. Brooks H2/L2 two-legged pullback
class BrooksH2L2(Strategy):
    id = "brooks_h2l2"
    name_en = "Al Brooks H2 / L2 Pullback (EMA20 trend)"
    name_fa = "پولبک دوپایه‌ای H2/L2 آل بروکس (روند EMA20)"
    category = "Price-Action"
    author = "Al Brooks — Trading Price Action Trends"
    difficulty = 4
    timeframes = "1m – 15m (5m classic)"
    params = {"ema": 20, "trend_bars": 10, "sl_atr": 1.0, "rr": 2.0}
    bt_kwargs = {"max_bars": 30}
    description_en = ("In a trend (price mostly on one side of EMA20 for 10 bars), the 2nd attempt to resume — the H2: a bar whose "
                      "high exceeds the prior bar's high for the second time since the pullback began — is the highest-probability "
                      "with-trend entry. Buy the break of that bar's high, stop under the pullback low.")
    description_fa = ("در روند (قیمت ۱۰ کندل عمدتاً یک طرف EMA20)، دومین تلاش برای ادامه — H2: کندلی که برای بار دوم از شروع پولبک، "
                      "سقفش از سقف کندل قبل بالاتر می‌رود — پرشانس‌ترین ورود هم‌جهت روند است. خرید روی شکست سقف آن کندل، حد ضرر زیر کف پولبک.")
    rules_en = ["Trend: ≥ 8 of last 10 closes above EMA20 (long)", "Pullback: at least one bar with low below prior low",
                "H1 = first bar with high > prior high; H2 = second such bar → long at its close", "Stop 1 ATR under pullback low; target 2R"]
    rules_fa = ["روند: ≥ ۸ از ۱۰ بسته‌شدن آخر بالای EMA20 (خرید)", "پولبک: حداقل یک کندل با کف پایین‌تر از کف قبلی",
                "H1 = اولین کندل با سقف > سقف قبلی؛ H2 = دومین → خرید روی بسته شدن آن", "حد ضرر ۱ ATR زیر کف پولبک؛ هدف 2R"]
    pros_en = ["Pure price action, no lagging trigger", "Filters the failed first attempt (H1)"]
    cons_en = ["Needs a real trend; whipsaws in tight ranges"]
    pros_fa = ["پرایس‌اکشن خالص، بدون تریگر تأخیری", "تلاش اول ناموفق (H1) را فیلتر می‌کند"]
    cons_fa = ["روند واقعی می‌خواهد؛ در رنج تنگ اره می‌شود"]

    def run(self, df):
        p = self.p
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df, 14)
        above = (df.close > e).astype(int).rolling(p["trend_bars"]).sum()
        up_tr = above >= p["trend_bars"] - 2
        dn_tr = above <= 2
        h, l = df.high.values, df.low.values
        n = len(df)
        sig = np.zeros(n, dtype=int)
        stop = np.full(n, np.nan); tgt = np.full(n, np.nan)
        # state machines for H-count (long) and L-count (short)
        hcount = 0; in_pb = False; pb_low = np.nan
        lcount = 0; in_pb_s = False; pb_high = np.nan
        ut = up_tr.values; dt = dn_tr.values; av = a.values
        for i in range(1, n):
            # ---- long side
            if ut[i]:
                if l[i] < l[i - 1]:                        # pullback leg
                    if not in_pb:
                        in_pb, hcount, pb_low = True, 0, l[i]
                    else:
                        pb_low = min(pb_low, l[i])
                elif in_pb and h[i] > h[i - 1]:
                    hcount += 1
                    if hcount == 2:
                        sig[i] = 1; stop[i] = pb_low - p["sl_atr"] * av[i] if av[i] == av[i] else np.nan
                        in_pb, hcount = False, 0
            else:
                in_pb, hcount = False, 0
            # ---- short side
            if dt[i]:
                if h[i] > h[i - 1]:
                    if not in_pb_s:
                        in_pb_s, lcount, pb_high = True, 0, h[i]
                    else:
                        pb_high = max(pb_high, h[i])
                elif in_pb_s and l[i] < l[i - 1]:
                    lcount += 1
                    if lcount == 2 and sig[i] == 0:
                        sig[i] = -1; stop[i] = pb_high + p["sl_atr"] * av[i] if av[i] == av[i] else np.nan
                        in_pb_s, lcount = False, 0
            else:
                in_pb_s, lcount = False, 0
        c = df.close.values
        m = sig != 0
        tgt[m] = c[m] + p["rr"] * (c[m] - stop[m])
        return StrategyResult(pd.Series(sig, index=df.index), pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index),
                              overlays={"EMA20": e}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 6. Volman double pressure / Keltner-ATR squeeze pop
class MicroSqueezePop(Strategy):
    id = "micro_squeeze_pop"
    name_en = "Micro Squeeze Pop (BB inside Keltner, 1m–5m)"
    name_fa = "پاپ اسکوئیز کوچک (بولینگر داخل کلتنر، ۱ تا ۵ دقیقه)"
    category = "Volatility"
    author = "John Carter TTM Squeeze, Bob Volman double-pressure"
    difficulty = 2
    timeframes = "1m – 15m"
    params = {"n": 20, "bb_k": 2.0, "kc_mult": 1.5, "min_sq": 6, "relvol": 1.3, "sl_atr": 1.0, "rr": 1.6}
    bt_kwargs = {"max_bars": 20}
    description_en = ("Bollinger bands inside Keltner channel for ≥ 6 bars = compression. The first close outside the Bollinger "
                      "band with relative volume ≥ 1.3 and momentum (close − SMA20) in the same direction is the pop. Small target "
                      "(1.6 R) because on low timeframes expansions are short.")
    description_fa = ("بولینگر داخل کانال کلتنر برای ≥ ۶ کندل = فشردگی. اولین بسته شدن بیرون بولینگر با حجم نسبی ≥ ۱.۳ و مومنتوم "
                      "(قیمت − SMA20) هم‌جهت = پاپ. هدف کوچک (۱.۶R) چون در تایم پایین انبساط‌ها کوتاه‌اند.")
    rules_en = ["Squeeze: BB upper < KC upper and BB lower > KC lower for ≥ 6 bars", "Release bar: close > BB upper (long) with rel.volume ≥ 1.3",
                "Stop 1 ATR; target 1.6 R; time stop 20 bars"]
    rules_fa = ["اسکوئیز: باند بالای BB < کلتنر و پایین BB > کلتنر برای ≥ ۶ کندل", "کندل آزادسازی: بسته شدن > BB بالا (خرید) با حجم نسبی ≥ ۱.۳",
                "حد ضرر ۱ ATR؛ هدف ۱.۶R؛ حد زمانی ۲۰ کندل"]
    pros_en = ["Objective compression definition", "Volume-confirmed"]
    cons_en = ["First pop can be a fake — time stop limits damage"]
    pros_fa = ["تعریف عینی فشردگی", "تأیید حجمی"]
    cons_fa = ["اولین پاپ می‌تواند فیک باشد — حد زمانی خسارت را محدود می‌کند"]

    def run(self, df):
        p = self.p
        ub, mb, lb = ta.bollinger(df.close, p["n"], p["bb_k"])
        ku, km, kl = ta.keltner(df, p["n"], p["kc_mult"])
        a = ta.atr(df, 14)
        sq = (ub < ku) & (lb > kl)
        sq_len = sq.astype(int).groupby((~sq).cumsum()).cumsum()
        was_sq = sq_len.shift(1) >= p["min_sq"]
        rv = _relvol(df)
        mom = df.close - mb
        long = was_sq & (df.close > ub) & (rv >= p["relvol"]) & (mom > 0)
        short = was_sq & (df.close < lb) & (rv >= p["relvol"]) & (mom < 0)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["sl_atr"] * p["rr"])
        return StrategyResult(sig, st, tp, overlays={"BB up": ub, "BB lo": lb, "KC up": ku, "KC lo": kl},
                              panels={"Squeeze": {"squeeze": sq.astype(int), "momentum": mom}}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 7. Session-open range (crypto: 00 UTC / London 07 / NY 13:30)
class SessionORBCrypto(Strategy):
    id = "session_orb"
    name_en = "Session Opening-Range Breakout (Asia/London/NY)"
    name_fa = "شکست رنج ابتدای سشن (آسیا/لندن/نیویورک)"
    category = "Price-Action"
    author = "Toby Crabel ORB, adapted to 24/7 crypto sessions"
    difficulty = 2
    timeframes = "1m – 15m"
    params = {"range_min": 15, "sessions": "0,7,13", "expire_min": 180, "relvol": 1.1, "rr": 1.5, "nr_filter": True}
    bt_kwargs = {"max_bars": 48}
    description_en = ("Crypto has three volatility injections: 00:00 UTC (daily candle / funding), 07:00 London, 13:30 New York. "
                      "Mark the first 15 minutes of each; trade the first close outside on relative volume, valid for 3 h. "
                      "Optional Crabel NR filter: only when the previous 4 h range was the narrowest of the last 7 sessions.")
    description_fa = ("کریپتو سه تزریق نوسان دارد: ۰۰:۰۰ UTC (کندل روزانه/فاندینگ)، ۰۷:۰۰ لندن، ۱۳:۳۰ نیویورک. ۱۵ دقیقهٔ اول هر کدام را "
                      "علامت بزن؛ اولین بسته شدن بیرون آن با حجم نسبی را معامله کن؛ تا ۳ ساعت معتبر. فیلتر NR کرابل اختیاری.")
    rules_en = ["Opening range = high/low of first 15 min of session", "Long: close > OR high, rel.volume ≥ 1.1, within 3 h of open",
                "Stop: OR mid; target 1.5 × OR height; one trade per session"]
    rules_fa = ["رنج بازگشایی = سقف/کف ۱۵ دقیقهٔ اول سشن", "خرید: بسته شدن > سقف رنج، حجم نسبی ≥ ۱.۱، تا ۳ ساعت بعد از باز شدن",
                "حد ضرر: وسط رنج؛ هدف ۱.۵ × ارتفاع رنج؛ یک معامله در هر سشن"]
    pros_en = ["Time-based edge independent of indicators", "Defined risk from the range"]
    cons_en = ["Fake breaks in low-vol sessions", "Needs bar timestamps in UTC"]
    pros_fa = ["لبهٔ زمانی مستقل از اندیکاتور", "ریسک مشخص از روی رنج"]
    cons_fa = ["شکست فیک در سشن‌های کم‌نوسان", "تایم‌استمپ باید UTC باشد"]

    def run(self, df):
        p = self.p
        n = len(df)
        sig = np.zeros(n, dtype=int); stop = np.full(n, np.nan); tgt = np.full(n, np.nan)
        orh = np.full(n, np.nan); orl = np.full(n, np.nan)
        if not isinstance(df.index, pd.DatetimeIndex) or n < 100:
            z = pd.Series(sig, index=df.index)
            return StrategyResult(z, pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index))
        bm = _bar_minutes(df)
        rb = max(1, int(round(p["range_min"] / bm)))
        exp_bars = max(rb + 1, int(p["expire_min"] / bm))
        hours = [int(x) for x in str(p["sessions"]).split(",") if x.strip() != ""]
        mins = df.index.hour * 60 + df.index.minute
        starts = np.zeros(n, dtype=bool)
        for hh in hours:
            m0 = hh * 60 + (30 if hh == 13 else 0)
            hit = (mins >= m0) & (mins < m0 + bm)
            starts |= np.asarray(hit)
        rv = _relvol(df).values
        h, l, c = df.high.values, df.low.values, df.close.values
        idx = np.where(starts)[0]
        for s0 in idx:
            if s0 + rb >= n:
                break
            hh_, ll_ = h[s0:s0 + rb].max(), l[s0:s0 + rb].min()
            height = hh_ - ll_
            if height <= 0:
                continue
            done = False
            for k in range(s0 + rb, min(n, s0 + exp_bars)):
                orh[k], orl[k] = hh_, ll_
                if done or starts[k]:
                    continue
                if c[k] > hh_ and rv[k] >= p["relvol"]:
                    sig[k] = 1; stop[k] = (hh_ + ll_) / 2; tgt[k] = c[k] + p["rr"] * height; done = True
                elif c[k] < ll_ and rv[k] >= p["relvol"]:
                    sig[k] = -1; stop[k] = (hh_ + ll_) / 2; tgt[k] = c[k] - p["rr"] * height; done = True
        return StrategyResult(pd.Series(sig, index=df.index), pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index),
                              overlays={"OR high": pd.Series(orh, index=df.index), "OR low": pd.Series(orl, index=df.index)},
                              bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 8. EMA-9/21 + VWAP + Stoch triple confirmation (Upscale hybrid #1)
class TripleConfirmScalp(Strategy):
    id = "triple_confirm_scalp"
    name_en = "Triple-Confirmation Scalp (EMA 9/21 + VWAP side + Stoch)"
    name_fa = "اسکالپ سه‌تأییده (EMA 9/21 + سمت VWAP + استوکاستیک)"
    category = "Momentum"
    author = "Upscale 'Hybrid #1' / common prop-desk template"
    difficulty = 2
    timeframes = "1m – 15m"
    params = {"fast": 9, "slow": 21, "stoch_k": 9, "os": 25, "ob": 75, "sl_atr": 1.2, "rr": 1.5}
    bt_kwargs = {"max_bars": 24}
    description_en = ("Trend (EMA9 > EMA21) + value (price pulled back to/under VWAP but still above EMA21 zone) + momentum "
                      "(Stochastic(9) crosses up from < 25). All three in the same bar window → entry. Stand-alone EMA crosses lose "
                      "after fees; the VWAP + stochastic gates cut trades ~70 % and keep the good ones.")
    description_fa = ("روند (EMA9 > EMA21) + ارزش (پولبک قیمت تا/زیر VWAP ولی هنوز بالای ناحیهٔ EMA21) + مومنتوم (استوکاستیک(9) از زیر ۲۵ "
                      "به بالا کراس کند). هر سه با هم → ورود. کراس EMA به‌تنهایی بعد از کارمزد ضرر می‌دهد؛ گیت VWAP+استوک ~۷۰٪ معاملات را حذف می‌کند.")
    rules_en = ["EMA9 > EMA21 and EMA21 rising", "Low of last 3 bars ≤ VWAP (pullback to value)", "Stoch %K(9) crosses above 25",
                "Stop 1.2 ATR, target 1.5 R, time stop 24 bars"]
    rules_fa = ["EMA9 > EMA21 و EMA21 صعودی", "کف ۳ کندل آخر ≤ VWAP (پولبک به ارزش)", "%K(9) استوکاستیک از ۲۵ به بالا کراس کند",
                "حد ضرر ۱.۲ ATR، هدف ۱.۵R، حد زمانی ۲۴ کندل"]
    pros_en = ["Simple, mechanical", "Three independent confirmations"]
    cons_en = ["Lags a few bars", "Choppy VWAP days = few valid signals"]
    pros_fa = ["ساده و مکانیکی", "سه تأیید مستقل"]
    cons_fa = ["چند کندل تأخیر", "روزهای رنج = سیگنال معتبر کم"]

    def run(self, df):
        p = self.p
        ef, es = ta.ema(df.close, p["fast"]), ta.ema(df.close, p["slow"])
        v = ta.vwap(df)
        k, d = ta.stochastic(df, p["stoch_k"], 3, 3)
        a = ta.atr(df, 14)
        pb_lo = df.low.rolling(3).min() <= v
        pb_hi = df.high.rolling(3).max() >= v
        long = (ef > es) & (es > es.shift(3)) & pb_lo & self.cross_up(k, p["os"])
        short = (ef < es) & (es < es.shift(3)) & pb_hi & self.cross_down(k, p["ob"])
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["sl_atr"] * p["rr"])
        return StrategyResult(sig, st, tp, overlays={"EMA9": ef, "EMA21": es, "VWAP": v}, panels={"Stoch": {"%K": k, "%D": d}},
                              bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 9. RSI(7) divergence at BB extreme (fast)
class FastRSIDivergenceScalp(Strategy):
    id = "fast_rsi_div_scalp"
    name_en = "Fast RSI(7) Divergence at Band Extreme"
    name_fa = "واگرایی سریع RSI(7) روی کران باند"
    category = "Momentum"
    author = "Scalping literature (RSI-7 replaces RSI-14 on 1m)"
    difficulty = 3
    timeframes = "1m – 15m"
    params = {"rsi_n": 7, "pivot": 3, "bb_n": 20, "sl_atr": 1.2, "rr": 1.8}
    bt_kwargs = {"max_bars": 30}
    description_en = ("Default RSI-14 lags too much on a 1-minute chart. Use RSI(7): a lower price low outside/at the lower Bollinger "
                      "band with a higher RSI low (3-bar pivots) is a micro-exhaustion; enter on the pivot confirmation bar.")
    description_fa = ("RSI-14 پیش‌فرض روی ۱ دقیقه خیلی تأخیر دارد. RSI(7): کف قیمتی پایین‌تر روی/بیرون باند پایین بولینگر با کف RSI بالاتر "
                      "(پیوت ۳ کندلی) = خستگی خرد؛ ورود روی کندل تأیید پیوت.")
    rules_en = ["Pivot lows (3/3) in price and RSI(7)", "Price LL & RSI HL & pivot low ≤ BB lower → long on confirmation bar",
                "Stop 1.2 ATR under pivot; target 1.8 R"]
    rules_fa = ["پیوت کف (۳/۳) در قیمت و RSI(7)", "قیمت LL و RSI HL و کف پیوت ≤ باند پایین BB → خرید روی کندل تأیید",
                "حد ضرر ۱.۲ ATR زیر پیوت؛ هدف ۱.۸R"]
    pros_en = ["Reported ~65 % win rate in scalping studies", "Band filter removes mid-range noise"]
    cons_en = ["Divergences can stack in strong trends"]
    pros_fa = ["وین‌ریت گزارش‌شده ~۶۵٪ در مطالعات اسکالپ", "فیلتر باند نویز وسط رنج را حذف می‌کند"]
    cons_fa = ["در روند قوی واگرایی‌ها پشت‌سرهم شکست می‌خورند"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, p["rsi_n"])
        ub, mb, lb = ta.bollinger(df.close, p["bb_n"], 2.0)
        a = ta.atr(df, 14)
        pv = p["pivot"]
        pl = _pivot_low(df.low, pv, pv); ph = _pivot_high(df.high, pv, pv)
        low_at = df.low.where(pl); r_lo_at = r.where(pl)
        prev_low, prev_r_lo = low_at.shift(1).ffill(), r_lo_at.shift(1).ffill()
        bull = pl & (df.low < prev_low) & (r > prev_r_lo) & (df.low <= lb)
        high_at = df.high.where(ph); r_hi_at = r.where(ph)
        prev_high, prev_r_hi = high_at.shift(1).ffill(), r_hi_at.shift(1).ffill()
        bear = ph & (df.high > prev_high) & (r < prev_r_hi) & (df.high >= ub)
        long = bull.shift(pv).fillna(False).astype(bool)
        short = bear.shift(pv).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = (df.low.shift(pv) - p["sl_atr"] * a)[sig == 1]; tgt[sig == 1] = (df.close + p["rr"] * (df.close - stop))[sig == 1]
        stop[sig == -1] = (df.high.shift(pv) + p["sl_atr"] * a)[sig == -1]; tgt[sig == -1] = (df.close - p["rr"] * (stop - df.close))[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"BB up": ub, "BB lo": lb}, panels={"RSI7": {"RSI(7)": r}}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 10. Volume-climax exhaustion (Wyckoff SC/BC on LTF)
class VolumeClimaxReversal(Strategy):
    id = "volume_climax_scalp"
    name_en = "Volume Climax Reversal (Wyckoff SC/BC, intraday)"
    name_fa = "برگشت کلایمکس حجمی (SC/BC وایکاف، روزانه)"
    category = "Volume"
    author = "Wyckoff / Anna Coulling (VPA)"
    difficulty = 3
    timeframes = "1m – 15m"
    params = {"vol_z": 3.0, "n": 60, "ext_atr": 2.0, "sl_atr": 1.0, "rr": 1.5}
    bt_kwargs = {"max_bars": 20}
    description_en = ("A bar with volume ≥ 3σ above its 60-bar mean, closing ≥ 2 ATR away from EMA20 and with a wick against the move "
                      "(close in the opposite half) is a selling/buying climax: the last aggressive participants are in. Fade it toward EMA20.")
    description_fa = ("کندلی با حجم ≥ ۳σ بالاتر از میانگین ۶۰ کندل، بسته شدن ≥ ۲ ATR دور از EMA20 و شدوی مخالف حرکت (بسته شدن در نیمهٔ مخالف) "
                      "= کلایمکس فروش/خرید: آخرین مهاجم‌ها وارد شده‌اند. آن را به سمت EMA20 فِید کن.")
    rules_en = ["volume z-score ≥ 3 (60 bars)", "close ≤ EMA20 − 2 ATR (long) and close in upper half of bar", "Stop 1 ATR under bar low; target EMA20 (capped 1.5 R)"]
    rules_fa = ["z-score حجم ≥ ۳ (۶۰ کندل)", "بسته شدن ≤ EMA20 − ۲ATR (خرید) و بسته شدن در نیمهٔ بالایی کندل", "حد ضرر ۱ ATR زیر کف؛ هدف EMA20 (حداکثر ۱.۵R)"]
    pros_en = ["Rare but high-quality", "Objective climax definition"]
    cons_en = ["News-driven climaxes may continue — the wick condition is required"]
    pros_fa = ["نادر ولی باکیفیت", "تعریف عینی کلایمکس"]
    cons_fa = ["کلایمکس خبری ممکن است ادامه یابد — شرط شدو لازم است"]

    def run(self, df):
        p = self.p
        e = ta.ema(df.close, 20)
        a = ta.atr(df, 14)
        vm = df.volume.rolling(p["n"]).mean(); vs = df.volume.rolling(p["n"]).std(ddof=0).replace(0, np.nan)
        z = (df.volume - vm) / vs
        rng = (df.high - df.low).replace(0, np.nan)
        pos = (df.close - df.low) / rng
        long = (z >= p["vol_z"]) & (df.close <= e - p["ext_atr"] * a) & (pos >= 0.5)
        short = (z >= p["vol_z"]) & (df.close >= e + p["ext_atr"] * a) & (pos <= 0.5)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = (df.low - p["sl_atr"] * a)[sig == 1]
        tgt[sig == 1] = np.minimum(e, df.close + p["rr"] * (df.close - stop))[sig == 1]
        stop[sig == -1] = (df.high + p["sl_atr"] * a)[sig == -1]
        tgt[sig == -1] = np.maximum(e, df.close - p["rr"] * (stop - df.close))[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"EMA20": e}, panels={"VolZ": {"hist": z}}, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 11. Funding/derivatives-aware reversal (uses attrs if present)
class FundingCrowdReversal(Strategy):
    id = "funding_crowd_reversal"
    name_en = "Funding-Crowd Reversal (perp positioning + CVD)"
    name_fa = "برگشت ازدحام فاندینگ (پوزیشن پرپچوال + CVD)"
    category = "Smart-Money"
    author = "Crypto derivatives desks (funding × CVD confluence)"
    difficulty = 4
    timeframes = "5m – 1h"
    params = {"fund_hi": 0.0003, "fund_lo": -0.0001, "n": 20, "sl_atr": 1.5, "rr": 2.0}
    bt_kwargs = {"max_bars": 48}
    description_en = ("When perpetual funding is elevated (longs crowded, paying ≥ 0.03 %/8h) AND price makes a 20-bar high that CVD does not "
                      "confirm, the squeeze fuel is on the wrong side → short the failure. Mirror with negative funding at 20-bar lows. "
                      "Funding is read from df.attrs['funding'] (core.derivs fetches OKX/Binance); without it the strategy falls back to a "
                      "price-only proxy: 20-bar range extension ≥ 3 ATR as the 'crowding' condition.")
    description_fa = ("وقتی فاندینگ پرپچوال بالاست (لانگ‌ها شلوغ، ≥ ۰.۰۳٪/۸ساعت) و قیمت سقف ۲۰ کندلی می‌زند که CVD تأییدش نمی‌کند، سوخت اسکوئیز سمت "
                      "اشتباه است → شورت روی شکست ناموفق. برعکس با فاندینگ منفی روی کف ۲۰ کندلی. فاندینگ از df.attrs['funding'] خوانده می‌شود؛ "
                      "بدون آن از پراکسی قیمتی (کشیدگی ≥ ۳ATR) استفاده می‌کند.")
    rules_en = ["funding ≥ +0.03 %/8h (or proxy: close ≥ EMA50 + 3 ATR)", "close ≥ 20-bar high but CVD < CVD at previous 20-bar high",
                "Short on the next bar closing back below the prior high; stop 1.5 ATR; target 2R"]
    rules_fa = ["فاندینگ ≥ +۰.۰۳٪/۸ساعت (یا پراکسی: قیمت ≥ EMA50 + ۳ATR)", "قیمت ≥ سقف ۲۰ کندلی ولی CVD < CVD سقف ۲۰ کندلی قبلی",
                "شورت روی کندل بعدی که زیر سقف قبلی بسته شود؛ حد ضرر ۱.۵ATR؛ هدف 2R"]
    pros_en = ["Combines positioning + order flow", "Targets forced liquidations (fast moves)"]
    cons_en = ["Needs derivatives data for full power", "Crowded can stay crowded in parabolic trends"]
    pros_fa = ["ترکیب پوزیشن‌گیری + جریان سفارش", "لیکوییدیشن اجباری را هدف می‌گیرد (حرکت سریع)"]
    cons_fa = ["برای قدرت کامل دیتای مشتقه لازم است", "در روند سهمی، ازدحام می‌تواند ادامه یابد"]

    def run(self, df):
        p = self.p
        n = p["n"]
        a = ta.atr(df, 14)
        e = ta.ema(df.close, 50)
        cvd, _ = _cvd(df)
        from core.derivs import get_series
        fund = get_series(df, "funding")
        if isinstance(fund, pd.Series) and len(fund):
            f = fund.reindex(df.index, method="ffill")
            crowded_long = f >= p["fund_hi"]
            crowded_short = f <= p["fund_lo"]
        else:
            crowded_long = df.close >= e + 3 * a
            crowded_short = df.close <= e - 3 * a
        hi_n = df.high.rolling(n).max(); lo_n = df.low.rolling(n).min()
        new_hi = df.high >= hi_n.shift(1); new_lo = df.low <= lo_n.shift(1)
        cvd_at_hi = cvd.where(new_hi).ffill().shift(1)
        cvd_at_lo = cvd.where(new_lo).ffill().shift(1)
        fail_hi = new_hi.shift(1).fillna(False).astype(bool) & (df.close < hi_n.shift(2)) & (cvd.shift(1) < cvd_at_hi.shift(1))
        fail_lo = new_lo.shift(1).fillna(False).astype(bool) & (df.close > lo_n.shift(2)) & (cvd.shift(1) > cvd_at_lo.shift(1))
        short = crowded_long & fail_hi
        long = crowded_short & fail_lo
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["sl_atr"] * p["rr"])
        panels = {"CVD": {"CVD": cvd}}
        if isinstance(fund, pd.Series) and len(fund):
            panels["Funding"] = {"funding": fund.reindex(df.index, method="ffill") * 100}
        return StrategyResult(sig, st, tp, overlays={"EMA50": e}, panels=panels, bt_kwargs=dict(self.bt_kwargs))


# ----------------------------------------------------------------------------- 12. Initial-balance (Market Profile) extension
class InitialBalanceExtension(Strategy):
    id = "ib_extension"
    name_en = "Initial-Balance Extension (Market Profile, first hour)"
    name_fa = "گسترش تعادل اولیه (مارکت پروفایل، ساعت اول)"
    category = "Price-Action"
    author = "Peter Steidlmayer / Jim Dalton — Mind over Markets"
    difficulty = 3
    timeframes = "5m – 15m"
    params = {"ib_min": 60, "session_hour": 13, "session_min": 30, "ext": 0.5, "rr": 1.5}
    bt_kwargs = {"max_bars": 36}
    description_en = ("The first hour after the NY open builds the Initial Balance. A close beyond IB high by 50 % of its height "
                      "with the day still 'trend-type' (no return inside) is a range-extension day: go with it, stop at IB mid.")
    description_fa = ("ساعت اول بعد از باز شدن نیویورک تعادل اولیه (IB) را می‌سازد. بسته شدن بالای سقف IB به اندازهٔ ۵۰٪ ارتفاعش، بدون "
                      "برگشت به داخل = روز گسترش رنج: هم‌جهت برو، حد ضرر وسط IB.")
    rules_en = ["IB = high/low of first 60 min after 13:30 UTC", "Long: close ≥ IB high + 0.5 × IB height", "Stop IB mid; target 1.5 R; one per day"]
    rules_fa = ["IB = سقف/کف ۶۰ دقیقهٔ اول بعد از ۱۳:۳۰ UTC", "خرید: بسته شدن ≥ سقف IB + ۰.۵ × ارتفاع IB", "حد ضرر وسط IB؛ هدف ۱.۵R؛ یکی در روز"]
    pros_en = ["Classic auction-theory day-type read"]
    cons_en = ["Only one setup per day", "Needs a session-driven market (stocks, indices, BTC during US hours)"]
    pros_fa = ["خوانش کلاسیک نوع روز بر پایهٔ نظریهٔ حراج"]
    cons_fa = ["فقط یک ستاپ در روز", "بازار سشن‌محور می‌خواهد (سهام، شاخص، BTC در ساعات آمریکا)"]

    def run(self, df):
        p = self.p
        n = len(df)
        sig = np.zeros(n, dtype=int); stop = np.full(n, np.nan); tgt = np.full(n, np.nan)
        ibh = np.full(n, np.nan); ibl = np.full(n, np.nan)
        if not isinstance(df.index, pd.DatetimeIndex) or n < 100:
            return StrategyResult(pd.Series(sig, index=df.index))
        bm = _bar_minutes(df)
        rb = max(2, int(round(p["ib_min"] / bm)))
        mins = np.asarray(df.index.hour * 60 + df.index.minute)
        m0 = p["session_hour"] * 60 + p["session_min"]
        starts = np.where((mins >= m0) & (mins < m0 + bm))[0]
        h, l, c = df.high.values, df.low.values, df.close.values
        day = np.asarray(df.index.normalize().values)
        for s0 in starts:
            if s0 + rb >= n:
                break
            hh_, ll_ = h[s0:s0 + rb].max(), l[s0:s0 + rb].min(); ht = hh_ - ll_
            if ht <= 0:
                continue
            done = False
            k = s0 + rb
            while k < n and day[k] == day[s0]:
                ibh[k], ibl[k] = hh_, ll_
                if not done:
                    if c[k] >= hh_ + p["ext"] * ht:
                        sig[k] = 1; stop[k] = (hh_ + ll_) / 2; tgt[k] = c[k] + p["rr"] * (c[k] - stop[k]); done = True
                    elif c[k] <= ll_ - p["ext"] * ht:
                        sig[k] = -1; stop[k] = (hh_ + ll_) / 2; tgt[k] = c[k] - p["rr"] * (stop[k] - c[k]); done = True
                k += 1
        return StrategyResult(pd.Series(sig, index=df.index), pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index),
                              overlays={"IB high": pd.Series(ibh, index=df.index), "IB low": pd.Series(ibl, index=df.index)},
                              bt_kwargs=dict(self.bt_kwargs))


SCALP_STRATEGIES = [VWAPPullbackScalp, VWAPBandFade, CVDDivergence, StopRunReversalScalp, BrooksH2L2, MicroSqueezePop,
                    SessionORBCrypto, TripleConfirmScalp, FastRSIDivergenceScalp, VolumeClimaxReversal, FundingCrowdReversal,
                    InitialBalanceExtension]
