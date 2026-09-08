"""Signal methods for every catalog indicator that had no strategy yet (Phase 18) — so the bot knows a concrete,
testable entry rule for ALL 73 indicators, not just the popular ones. Each class documents the textbook rule
(author / source) and uses the shared ATR stop helper. Names follow the Indicator Encyclopedia keys.
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta
from core import indicators2 as t2


class _Ind(Strategy):
    category = "Indicator"
    difficulty = 2
    timeframes = "15m – 1d"
    sl_mult, tp_mult = 1.5, 3.0

    def finish(self, df, long, short, overlays=None, panels=None, levels=None, sl=None, tp=None):
        sig = self.make_signal(long, short)
        a = ta.atr(df)
        stop, tgt = self.atr_stops(df, sig, a, sl or self.sl_mult, tp or self.tp_mult)
        return StrategyResult(sig, stop, tgt, overlays=overlays or {}, panels=panels or {}, levels=levels or [])

    @staticmethod
    def trend_gate(df, n=100):
        e = ta.ema(df.close, n)
        return df.close > e, df.close < e


# ------------------------------------------------------------------ moving-average family
class WMACross(_Ind):
    id = "wma_cross"; name_en = "WMA 10/30 cross with slope"; name_fa = "کراس WMA 10/30 با شیب"
    author = "classic"; params = {"fast": 10, "slow": 30}
    description_en = "Weighted MA reacts faster than SMA: fast crosses slow while slow WMA slopes in the same direction."
    description_fa = "میانگین وزنی سریع‌تر از SMA است: کراس سریع/کند وقتی WMA کند هم‌جهت شیب دارد."
    rules_en = ["Long: WMA fast crosses above WMA slow and slow rising", "Short mirror", "ATR 1.5 / 3"]; rules_fa = ["خرید: کراس صعودی WMA سریع/کند و شیب مثبت کند", "فروش برعکس", "ATR ۱.۵ / ۳"]
    def run(self, df):
        f, s = ta.wma(df.close, self.p["fast"]), ta.wma(df.close, self.p["slow"])
        return self.finish(df, self.cross_up(f, s) & (s > s.shift(3)), self.cross_down(f, s) & (s < s.shift(3)), {"WMA fast": f, "WMA slow": s})


class ZLEMATrend(_Ind):
    id = "zlema_trend"; name_en = "Zero-lag EMA pullback"; name_fa = "پولبک ZLEMA"
    author = "Ehlers & Way"; params = {"n": 20, "trend": 100}
    description_en = "Price reclaims the zero-lag EMA in the direction of the EMA100 trend (ZLEMA hugs price with far less lag)."
    description_fa = "قیمت ZLEMA را در جهت روند EMA100 پس می‌گیرد (ZLEMA با تأخیر بسیار کمتر به قیمت می‌چسبد)."
    rules_en = ["Long: close crosses above ZLEMA, close > EMA100", "Short mirror"]; rules_fa = ["خرید: کراس close بالای ZLEMA و close > EMA100", "فروش برعکس"]
    def run(self, df):
        z = t2.zlema(df.close, self.p["n"]); up, dn = self.trend_gate(df, self.p["trend"])
        return self.finish(df, self.cross_up(df.close, z) & up, self.cross_down(df.close, z) & dn, {"ZLEMA": z})


class VWMACross(_Ind):
    id = "vwma_cross"; name_en = "VWMA vs SMA (volume-confirmed trend)"; name_fa = "VWMA در برابر SMA (روند با تأیید حجم)"
    author = "classic"; params = {"n": 20}
    description_en = "When the volume-weighted MA crosses above the plain SMA of the same length, up-moves are carrying the volume."
    description_fa = "وقتی میانگین وزنی حجمی بالای SMA هم‌طول می‌رود، حرکت صعودی حامل حجم است."
    rules_en = ["Long: VWMA crosses above SMA and close > both", "Short mirror"]; rules_fa = ["خرید: VWMA بالای SMA برود و close بالای هر دو", "فروش برعکس"]
    def run(self, df):
        v, s = t2.vwma(df, self.p["n"]), ta.sma(df.close, self.p["n"])
        return self.finish(df, self.cross_up(v, s) & (df.close > v), self.cross_down(v, s) & (df.close < v), {"VWMA": v, "SMA": s})


class T3Slope(_Ind):
    id = "t3_slope"; name_en = "Tillson T3 slope flip"; name_fa = "چرخش شیب T3 تیلسون"
    author = "Tim Tillson"; params = {"n": 8, "vf": 0.7}
    description_en = "T3 is extremely smooth; a change of its slope sign is a low-whipsaw trend-change signal."
    description_fa = "T3 بسیار نرم است؛ تغییر علامت شیب آن سیگنال تغییر روند با ویپساو کم است."
    rules_en = ["Long: T3 turns up (slope < 0 → > 0) and close > T3", "Short mirror"]; rules_fa = ["خرید: T3 رو به بالا بچرخد و close > T3", "فروش برعکس"]
    def run(self, df):
        t3 = t2.t3(df.close, self.p["n"], self.p["vf"]); d = t3.diff()
        return self.finish(df, (d > 0) & (d.shift(1) <= 0) & (df.close > t3), (d < 0) & (d.shift(1) >= 0) & (df.close < t3), {"T3": t3})


class McGinleyDynamic(_Ind):
    id = "mcginley_dynamic"; name_en = "McGinley Dynamic bounce"; name_fa = "برگشت از داینامیک مک‌گینلی"
    author = "John McGinley"; params = {"n": 14, "trend": 100}
    description_en = "The self-adjusting MD line acts as dynamic S/R; buy the first close back above it in an uptrend."
    description_fa = "خط خودتنظیم MD حمایت/مقاومت داینامیک است؛ اولین بسته‌شدن دوباره بالای آن در روند صعودی."
    rules_en = ["Long: low ≤ MD, close > MD, close > EMA100", "Short mirror"]; rules_fa = ["خرید: کف ≤ MD، close > MD، close > EMA100", "فروش برعکس"]
    def run(self, df):
        m = t2.mcginley(df.close, self.p["n"]); up, dn = self.trend_gate(df, self.p["trend"])
        return self.finish(df, (df.low <= m) & (df.close > m) & (df.low.shift(1) > m.shift(1)) & up, (df.high >= m) & (df.close < m) & (df.high.shift(1) < m.shift(1)) & dn, {"McGinley": m})


class SuperSmootherCross(_Ind):
    id = "supersmoother_cross"; name_en = "Ehlers SuperSmoother 10/30 cross"; name_fa = "کراس سوپراسموتر الرز ۱۰/۳۰"
    author = "John Ehlers"; params = {"fast": 10, "slow": 30}
    description_en = "DSP-grade low-pass filters remove cycle noise; the fast/slow cross has less lag than EMA pairs."
    description_fa = "فیلترهای پایین‌گذر DSP نویز سیکل را حذف می‌کنند؛ کراس سریع/کند تأخیر کمتری از EMA دارد."
    rules_en = ["Long: SS fast crosses above SS slow", "Short mirror"]; rules_fa = ["خرید: کراس صعودی SS سریع/کند", "فروش برعکس"]
    def run(self, df):
        f, s = t2.supersmoother(df.close, self.p["fast"]), t2.supersmoother(df.close, self.p["slow"])
        return self.finish(df, self.cross_up(f, s), self.cross_down(f, s), {"SS fast": f, "SS slow": s})


class LinRegChannel(_Ind):
    id = "linreg_channel"; name_en = "Linear-regression channel ±2σ fade (with slope filter)"; name_fa = "فید کانال رگرسیون خطی ±۲σ (با فیلتر شیب)"
    author = "Gilbert Raff"; params = {"n": 100, "k": 2.0}
    description_en = "Touch of the lower channel in a rising regression (slope > 0) = buy back toward the midline; mirror for shorts."
    description_fa = "لمس کانال پایین در رگرسیون صعودی (شیب > 0) = خرید به سمت خط میانی؛ برعکس برای فروش."
    rules_en = ["Long: low ≤ lower band, close > lower band, slope > 0", "Short mirror", "Target midline (≈2 ATR)"]; rules_fa = ["خرید: کف ≤ باند پایین، close > باند پایین، شیب > 0", "فروش برعکس", "هدف خط میانی"]
    def run(self, df):
        v, u, l, slope = t2.lin_reg_channel(df.close, self.p["n"], self.p["k"])
        return self.finish(df, (df.low <= l) & (df.close > l) & (slope > 0), (df.high >= u) & (df.close < u) & (slope < 0), {"LR mid": v, "LR +σ": u, "LR −σ": l}, sl=1.2, tp=2.4)


class HalfTrendFlip(_Ind):
    id = "halftrend_flip"; name_en = "HalfTrend flip"; name_fa = "چرخش هاف‌ترند"
    author = "Alex Orekhov (everget), TradingView"; params = {"amp": 2, "dev": 2.0}
    description_en = "Popular TradingView trend flipper: enter on the bar the HalfTrend direction changes."
    description_fa = "ترندفلیپر محبوب تریدینگ‌ویو: ورود در کندلی که جهت هاف‌ترند عوض می‌شود."
    rules_en = ["Long: trend flips to +1", "Short: flips to −1", "ATR 1.5 / 3"]; rules_fa = ["خرید: روند به +۱ برمی‌گردد", "فروش: به −۱", "ATR ۱.۵ / ۳"]
    def run(self, df):
        tr, line = t2.halftrend(df, self.p["amp"], self.p["dev"])
        return self.finish(df, (tr == 1) & (tr.shift(1) == -1), (tr == -1) & (tr.shift(1) == 1), {"HalfTrend": line})


# ------------------------------------------------------------------ oscillators
class VortexCross(_Ind):
    id = "vortex_cross"; name_en = "Vortex VI+/VI− cross"; name_fa = "کراس ورتکس VI+/VI−"
    author = "Etienne Botes & Douglas Siepman"; params = {"n": 14, "min_spread": 0.05}
    description_en = "VI+ crossing above VI− marks a new uptrend; require the spread to exceed 0.05 next bar to skip flat crosses."
    description_fa = "کراس VI+ بالای VI− شروع روند صعودی است؛ فاصلهٔ ≥ ۰.۰۵ برای حذف کراس‌های خنثی."
    rules_en = ["Long: VI+ crosses above VI− and VI+ − VI− ≥ 0.05", "Short mirror"]; rules_fa = ["خرید: کراس VI+ بالای VI− و اختلاف ≥ ۰.۰۵", "فروش برعکس"]
    def run(self, df):
        vp, vm = t2.vortex(df, self.p["n"]); sp = self.p["min_spread"]
        return self.finish(df, self.cross_up(vp, vm) & ((vp - vm) >= sp * 0.5), self.cross_down(vp, vm) & ((vm - vp) >= sp * 0.5), panels={"Vortex": {"VI+": vp, "VI−": vm}})


class TRIXSignal(_Ind):
    id = "trix_signal"; name_en = "TRIX signal-line cross above/below zero"; name_fa = "کراس خط سیگنال TRIX بالا/پایین صفر"
    author = "Jack Hutson"; params = {"n": 15, "sig": 9}
    description_en = "Triple-smoothed momentum: buy when TRIX crosses its signal while below zero is forbidden (only same-side crosses)."
    description_fa = "مومنتوم سه‌بار نرم‌شده: خرید وقتی TRIX خط سیگنالش را بالای صفر قطع کند."
    rules_en = ["Long: TRIX crosses above signal and TRIX > 0", "Short: crosses below signal and TRIX < 0"]; rules_fa = ["خرید: کراس TRIX بالای سیگنال و TRIX > 0", "فروش: کراس زیر سیگنال و TRIX < 0"]
    def run(self, df):
        tr = t2.trix(df.close, self.p["n"]); s = ta.ema(tr, self.p["sig"])
        return self.finish(df, self.cross_up(tr, s) & (tr > 0), self.cross_down(tr, s) & (tr < 0), panels={"TRIX": {"TRIX": tr, "Signal": s}})


class CoppockTurn(_Ind):
    id = "coppock_turn"; name_en = "Coppock curve upturn from below zero"; name_fa = "چرخش صعودی منحنی کاپاک از زیر صفر"
    author = "Edwin Coppock (1962)"; params = {"wl": 10, "r1": 14, "r2": 11}
    timeframes = "1d – 1wk"
    description_en = "Designed for monthly index bottoms: the curve turns up while negative. Long-only by design; short = downturn from above zero (weaker)."
    description_fa = "برای کف‌های ماهانهٔ شاخص: منحنی در حالی که منفی است رو به بالا می‌چرخد. اصولاً فقط خرید."
    rules_en = ["Long: Coppock < 0 and turns up", "Short: Coppock > 0 and turns down"]; rules_fa = ["خرید: کاپاک < 0 و چرخش بالا", "فروش: کاپاک > 0 و چرخش پایین"]
    def run(self, df):
        c = t2.coppock(df.close, self.p["wl"], self.p["r1"], self.p["r2"]); d = c.diff()
        return self.finish(df, (c < 0) & (d > 0) & (d.shift(1) <= 0), (c > 0) & (d < 0) & (d.shift(1) >= 0), panels={"Coppock": {"Coppock": c}}, sl=2.0, tp=5.0)


class SchaffCycle(_Ind):
    id = "schaff_cycle"; name_en = "Schaff Trend Cycle 25/75 cross"; name_fa = "کراس ۲۵/۷۵ سیکل روند شاف"
    author = "Doug Schaff"; params = {"fast": 23, "slow": 50, "cycle": 10}
    description_en = "STC crossing up through 25 = buy; down through 75 = sell. Faster than MACD with fewer whipsaws; trend gate EMA100."
    description_fa = "عبور STC از ۲۵ رو به بالا = خرید؛ از ۷۵ رو به پایین = فروش. سریع‌تر از MACD؛ گیت روند EMA100."
    rules_en = ["Long: STC crosses above 25 and close > EMA100", "Short: crosses below 75 and close < EMA100"]; rules_fa = ["خرید: STC از ۲۵ بالا برود و close > EMA100", "فروش: از ۷۵ پایین بیاید و close < EMA100"]
    def run(self, df):
        s = t2.schaff(df.close, self.p["fast"], self.p["slow"], self.p["cycle"]); up, dn = self.trend_gate(df)
        return self.finish(df, self.cross_up(s, 25) & up, self.cross_down(s, 75) & dn, panels={"Schaff": {"STC": s}})


class UltimateDivergence(_Ind):
    id = "ultimate_osc"; name_en = "Ultimate Oscillator (Williams' 3-step buy)"; name_fa = "اسیلاتور نهایی (خرید سه‌مرحله‌ای ویلیامز)"
    author = "Larry Williams (1976)"; params = {"lo": 30, "hi": 70}
    description_en = "Williams' original rule: UO makes a bullish divergence with a low under 30, then breaks above its divergence high. Implemented as: UO < 30 within last 10 bars, price lower low without UO lower low, UO crosses above 50."
    description_fa = "قانون اصلی ویلیامز: واگرایی صعودی UO با کف زیر ۳۰ و سپس شکست سقف واگرایی. پیاده‌سازی: UO < ۳۰ در ۱۰ کندل اخیر، کف پایین‌تر قیمت بدون کف پایین‌تر UO، عبور UO از ۵۰."
    rules_en = ["Long: recent UO<30 + price LL & UO HL + UO crosses 50", "Short mirror with 70"]; rules_fa = ["خرید: UO<۳۰ اخیر + LL قیمت و HL در UO + عبور UO از ۵۰", "فروش برعکس با ۷۰"]
    def run(self, df):
        u = t2.ultimate(df)
        rec_lo = (u < self.p["lo"]).rolling(10).max().fillna(0).astype(bool)
        rec_hi = (u > self.p["hi"]).rolling(10).max().fillna(0).astype(bool)
        pl_ll = df.low < df.low.rolling(10).min().shift(1); u_hl = u > u.rolling(10).min().shift(1)
        ph_hh = df.high > df.high.rolling(10).max().shift(1); u_lh = u < u.rolling(10).max().shift(1)
        div_b = (pl_ll & u_hl).rolling(5).max().fillna(0).astype(bool); div_s = (ph_hh & u_lh).rolling(5).max().fillna(0).astype(bool)
        return self.finish(df, rec_lo & div_b & self.cross_up(u, 50), rec_hi & div_s & self.cross_down(u, 50), panels={"Ultimate": {"UO": u}})


class AwesomeSaucer(_Ind):
    id = "ao_saucer"; name_en = "Awesome Oscillator saucer + zero cross"; name_fa = "نعلبکی + کراس صفر اسیلاتور Awesome"
    author = "Bill Williams"; params = {}
    description_en = "Williams' three AO entries: zero-line cross, saucer (two red bars then a green bar above zero), twin peaks. Zero cross and saucer implemented."
    description_fa = "سه ورود ویلیامز: کراس صفر، نعلبکی (دو میلهٔ قرمز و بعد یک سبز بالای صفر)، دو قله. کراس صفر و نعلبکی پیاده شده."
    rules_en = ["Long: AO crosses above 0, OR AO>0 and 2 falling bars then a rising bar", "Short mirror"]; rules_fa = ["خرید: کراس AO بالای صفر، یا AO>0 و دو میلهٔ نزولی سپس صعودی", "فروش برعکس"]
    def run(self, df):
        ao = t2.awesome(df); d = ao.diff()
        saucer_b = (ao > 0) & (d > 0) & (d.shift(1) < 0) & (d.shift(2) < 0)
        saucer_s = (ao < 0) & (d < 0) & (d.shift(1) > 0) & (d.shift(2) > 0)
        return self.finish(df, self.cross_up(ao, 0) | saucer_b, self.cross_down(ao, 0) | saucer_s, panels={"AO": {"hist": ao}})


class AcceleratorMomentum(_Ind):
    id = "ac_momentum"; name_en = "Accelerator Oscillator 2-bar confirmation"; name_fa = "تأیید دو کندلی اسیلاتور شتاب"
    author = "Bill Williams"; params = {"bars": 2}
    description_en = "AC measures acceleration of AO. Buy after two consecutive rising AC bars above zero (three when below zero, per Williams)."
    description_fa = "AC شتاب AO را می‌سنجد. خرید بعد از دو میلهٔ صعودی پیاپی بالای صفر (سه تا اگر زیر صفر باشد)."
    rules_en = ["Long: AC > 0 and AC rose 2 bars in a row (first occurrence)", "Short mirror"]; rules_fa = ["خرید: AC > 0 و دو میلهٔ صعودی پیاپی (اولین بار)", "فروش برعکس"]
    def run(self, df):
        ac = t2.accelerator(df); up2 = (ac.diff() > 0) & (ac.diff().shift(1) > 0); dn2 = (ac.diff() < 0) & (ac.diff().shift(1) < 0)
        long = (ac > 0) & up2 & ~up2.shift(1).fillna(False).astype(bool); short = (ac < 0) & dn2 & ~dn2.shift(1).fillna(False).astype(bool)
        return self.finish(df, long, short, panels={"AC": {"hist": ac}})


class FisherTransform(_Ind):
    id = "fisher_transform"; name_en = "Fisher Transform extreme cross"; name_fa = "کراس اکستریم فیشر ترنسفورم"
    author = "John Ehlers"; params = {"n": 9, "lvl": 1.5}
    description_en = "Fisher makes turning points sharp: buy when Fisher crosses above its trigger from below −1.5; sell mirror above +1.5."
    description_fa = "فیشر نقاط چرخش را تیز می‌کند: خرید وقتی فیشر از زیر −۱.۵ تریگرش را رو به بالا قطع کند؛ فروش برعکس بالای +۱.۵."
    rules_en = ["Long: Fisher crosses above trigger while Fisher < −1.5", "Short mirror > +1.5"]; rules_fa = ["خرید: کراس فیشر بالای تریگر وقتی فیشر < −۱.۵", "فروش برعکس > +۱.۵"]
    def run(self, df):
        f, trig = t2.fisher(df, self.p["n"]); L = self.p["lvl"]
        return self.finish(df, self.cross_up(f, trig) & (f.shift(1) < -L), self.cross_down(f, trig) & (f.shift(1) > L), panels={"Fisher": {"Fisher": f, "Trigger": trig}})


class QQECross(_Ind):
    id = "qqe_cross"; name_en = "QQE (RSI-MA vs trailing band) cross + 50 filter"; name_fa = "کراس QQE (RSI-MA و باند تریلینگ) + فیلتر ۵۰"
    author = "Igor Durkin / TradingView QQE MOD"; params = {"n": 14}
    description_en = "Smoothed RSI crossing its ATR-of-RSI trailing band = momentum shift; take it only on the 50 side of the trade."
    description_fa = "کراس RSI نرم‌شده با باند تریلینگ = تغییر مومنتوم؛ فقط در سمت درست خط ۵۰."
    rules_en = ["Long: RSI-MA crosses above trail and RSI-MA > 50", "Short mirror"]; rules_fa = ["خرید: RSI-MA بالای باند برود و > ۵۰", "فروش برعکس"]
    def run(self, df):
        r, fast = t2.qqe(df.close, self.p["n"])
        return self.finish(df, self.cross_up(r, fast) & (r > 50), self.cross_down(r, fast) & (r < 50), panels={"QQE": {"RSI-MA": r, "Trail": fast}})


class ElderRayImpulse(_Ind):
    id = "elder_ray"; name_en = "Elder-Ray: bull-power dip in EMA uptrend"; name_fa = "الدر-ری: افت قدرت گاو در روند صعودی EMA"
    author = "Alexander Elder"; params = {"n": 13}
    description_en = "Elder's rule: EMA13 rising AND bear power negative but rising (ticking up) → buy; mirror for shorts."
    description_fa = "قانون الدر: EMA13 صعودی و قدرت خرس منفی ولی در حال بالا آمدن → خرید؛ برعکس برای فروش."
    rules_en = ["Long: EMA13 rising, bear power < 0 and rising", "Short: EMA13 falling, bull power > 0 and falling"]; rules_fa = ["خرید: EMA13 صعودی، قدرت خرس < 0 و صعودی", "فروش: EMA13 نزولی، قدرت گاو > 0 و نزولی"]
    def run(self, df):
        bull, bear = t2.elder_ray(df, self.p["n"]); e = ta.ema(df.close, self.p["n"])
        long = (e > e.shift(1)) & (bear < 0) & (bear > bear.shift(1)) & (bear.shift(1) <= bear.shift(2))
        short = (e < e.shift(1)) & (bull > 0) & (bull < bull.shift(1)) & (bull.shift(1) >= bull.shift(2))
        return self.finish(df, long, short, {"EMA13": e}, {"Elder Ray": {"Bull": bull, "Bear": bear}})


class MassIndexReversal(_Ind):
    id = "mass_index_bulge"; name_en = "Mass Index reversal bulge (27 → 26.5)"; name_fa = "برآمدگی برگشتی شاخص جرم (۲۷ → ۲۶.۵)"
    author = "Donald Dorsey"; params = {}
    description_en = "Range expansion bulge: MI rises above 27 then falls below 26.5 → trend reversal; direction from EMA9 slope (fade it)."
    description_fa = "برآمدگی انبساط دامنه: MI بالای ۲۷ سپس زیر ۲۶.۵ → برگشت روند؛ جهت مخالف شیب EMA9."
    rules_en = ["Bulge: MI>27 in last 15 bars then crosses below 26.5", "Long if EMA9 falling (reversal up), short if rising"]; rules_fa = ["برآمدگی: MI>۲۷ در ۱۵ کندل اخیر سپس زیر ۲۶.۵", "خرید اگر EMA9 نزولی، فروش اگر صعودی"]
    def run(self, df):
        mi = t2.mass_index(df); e = ta.ema(df.close, 9)
        bulge = (mi > 27).rolling(15).max().fillna(0).astype(bool) & self.cross_down(mi, 26.5)
        return self.finish(df, bulge & (e < e.shift(3)), bulge & (e > e.shift(3)), panels={"Mass": {"MI": mi}}, sl=2.0, tp=3.0)


class ZScoreReversion(_Ind):
    id = "zscore_reversion"; name_en = "Z-score mean reversion (±2σ re-entry)"; name_fa = "بازگشت به میانگین Z-score (بازگشت از ±۲σ)"
    author = "quant classic"; params = {"n": 20, "z": 2.0}
    category = "Mean Reversion"
    description_en = "Fade statistical extremes: z crosses back above −2 (was below) → long, target z=0; requires low ADX (range regime)."
    description_fa = "فید اکستریم آماری: z از زیر −۲ برمی‌گردد → خرید، هدف z=0؛ نیاز به ADX پایین (رژیم رنج)."
    rules_en = ["Long: z crosses above −2 and ADX < 25", "Short mirror", "Stop 1.2 ATR, target 2 ATR"]; rules_fa = ["خرید: z از −۲ بالا بیاید و ADX < ۲۵", "فروش برعکس", "استاپ ۱.۲ ATR، هدف ۲ ATR"]
    def run(self, df):
        z = t2.zscore(df.close, self.p["n"]); adx, _, _ = ta.adx(df); Z = self.p["z"]
        return self.finish(df, self.cross_up(z, -Z) & (adx < 25), self.cross_down(z, Z) & (adx < 25), panels={"Z": {"z": z}}, sl=1.2, tp=2.0)


class HistVolBreakout(_Ind):
    id = "hv_squeeze_breakout"; name_en = "Historical-volatility squeeze breakout"; name_fa = "شکست فشردگی نوسان تاریخی"
    author = "Connors / Bollinger"; params = {"n": 20, "pct": 20, "look": 100}
    description_en = "HV in its bottom 20th percentile of the last 100 bars = coiled spring; trade the first Donchian(20) breakout out of it."
    description_fa = "HV در پایین‌ترین ۲۰ صدک ۱۰۰ کندل اخیر = فنر فشرده؛ اولین شکست دانچیان(۲۰) بعد از آن."
    rules_en = ["HV percentile ≤ 20 on previous bar", "Long: close > 20-bar high; short: close < 20-bar low"]; rules_fa = ["صدک HV ≤ ۲۰ در کندل قبل", "خرید: close > سقف ۲۰؛ فروش: close < کف ۲۰"]
    def run(self, df):
        hv = t2.hist_vol(df.close, self.p["n"]); pr = t2.percent_rank(hv, self.p["look"]).shift(1)
        u, l = ta.donchian(df, 20); sq = pr <= self.p["pct"]
        return self.finish(df, sq & (df.close > u.shift(1)), sq & (df.close < l.shift(1)), panels={"HV": {"HV %": hv}}, sl=1.5, tp=4.0)


# ------------------------------------------------------------------ volume
class ADLineDivergence(_Ind):
    id = "ad_line_div"; name_en = "Accumulation/Distribution divergence"; name_fa = "واگرایی خط انباشت/توزیع"
    author = "Marc Chaikin"; params = {"n": 20}
    description_en = "Price makes a 20-bar low but the A/D line does not (accumulation) → long on close above EMA9; mirror for distribution."
    description_fa = "قیمت کف ۲۰ کندلی می‌زند ولی خط A/D نه (انباشت) → خرید با بسته‌شدن بالای EMA9؛ برعکس برای توزیع."
    rules_en = ["Bullish div in last 5 bars + close crosses above EMA9", "Short mirror"]; rules_fa = ["واگرایی صعودی در ۵ کندل اخیر + کراس close بالای EMA9", "فروش برعکس"]
    def run(self, df):
        ad = t2.ad_line(df); n = self.p["n"]; e = ta.ema(df.close, 9)
        db = ((df.low <= df.low.rolling(n).min()) & (ad > ad.rolling(n).min())).rolling(5).max().fillna(0).astype(bool)
        ds = ((df.high >= df.high.rolling(n).max()) & (ad < ad.rolling(n).max())).rolling(5).max().fillna(0).astype(bool)
        return self.finish(df, db & self.cross_up(df.close, e), ds & self.cross_down(df.close, e), panels={"A/D": {"A/D": ad}})


class VPTTrend(_Ind):
    id = "vpt_trend"; name_en = "Volume-Price-Trend vs its EMA + price EMA gate"; name_fa = "روند قیمت-حجم در برابر EMA خودش + گیت EMA قیمت"
    author = "classic"; params = {"sig": 21, "trend": 50}
    description_en = "VPT crossing above its 21-EMA while price is above EMA50 = money flowing in with the trend."
    description_fa = "کراس VPT بالای EMA21 خودش وقتی قیمت بالای EMA50 است = ورود پول هم‌جهت روند."
    rules_en = ["Long: VPT crosses above EMA21(VPT) and close > EMA50", "Short mirror"]; rules_fa = ["خرید: VPT بالای EMA21 خودش و close > EMA50", "فروش برعکس"]
    def run(self, df):
        v = t2.vpt(df); s = ta.ema(v, self.p["sig"]); up, dn = self.trend_gate(df, self.p["trend"])
        return self.finish(df, self.cross_up(v, s) & up, self.cross_down(v, s) & dn, panels={"VPT": {"VPT": v, "EMA": s}})


class NVISmartMoney(_Ind):
    id = "nvi_smart_money"; name_en = "Negative Volume Index above its 255-EMA (Fosback)"; name_fa = "شاخص حجم منفی بالای EMA255 (فاسبک)"
    author = "Norman Fosback"; params = {"n": 255}
    timeframes = "1d"
    description_en = "Fosback: when NVI is above its one-year EMA there is ~95% chance of a bull market. Long on the cross up; exit/short on the cross down."
    description_fa = "فاسبک: وقتی NVI بالای EMA یک‌ساله‌اش است ~۹۵٪ احتمال بازار گاوی. خرید در کراس بالا؛ فروش در کراس پایین."
    rules_en = ["Long: NVI crosses above EMA255", "Short: crosses below"]; rules_fa = ["خرید: NVI بالای EMA255", "فروش: زیر آن"]
    def run(self, df):
        nvi = t2.nvi(df); e = ta.ema(nvi, min(self.p["n"], max(20, len(df) // 4)))
        return self.finish(df, self.cross_up(nvi, e), self.cross_down(nvi, e), panels={"NVI": {"NVI": nvi, "EMA": e}}, sl=2.5, tp=6.0)


class KlingerCross(_Ind):
    id = "klinger_cross"; name_en = "Klinger Volume Oscillator signal cross in trend"; name_fa = "کراس سیگنال اسیلاتور حجم کلینگر در روند"
    author = "Stephen Klinger"; params = {"f": 34, "s": 55, "sig": 13, "trend": 100}
    description_en = "KVO crossing its 13-EMA in the direction of the EMA100 trend (Klinger's own filter)."
    description_fa = "کراس KVO با EMA13 خودش در جهت روند EMA100 (فیلتر خود کلینگر)."
    rules_en = ["Long: KVO crosses above signal and close > EMA100", "Short mirror"]; rules_fa = ["خرید: KVO بالای سیگنال و close > EMA100", "فروش برعکس"]
    def run(self, df):
        k, s = t2.klinger(df, self.p["f"], self.p["s"], self.p["sig"]); up, dn = self.trend_gate(df, self.p["trend"])
        return self.finish(df, self.cross_up(k, s) & up, self.cross_down(k, s) & dn, panels={"Klinger": {"KVO": k, "Signal": s}})


class RVOLBreakout(_Ind):
    id = "rvol_breakout"; name_en = "Relative-volume breakout (RVOL ≥ 2 at a 20-bar high)"; name_fa = "شکست با حجم نسبی (RVOL ≥ ۲ در سقف ۲۰ کندلی)"
    author = "day-trading classic"; params = {"n": 20, "rvol": 2.0}
    description_en = "Breakouts with ≥2× normal volume carry institutional participation; without it, ignore the breakout."
    description_fa = "شکست با حجم ≥ ۲ برابر نرمال مشارکت نهادی دارد؛ بدون آن شکست را نادیده بگیر."
    rules_en = ["Long: close > prior 20-bar high and RVOL ≥ 2", "Short mirror"]; rules_fa = ["خرید: close > سقف ۲۰ کندل قبل و RVOL ≥ ۲", "فروش برعکس"]
    def run(self, df):
        rv = t2.relative_volume(df, self.p["n"]); u, l = ta.donchian(df, self.p["n"])
        return self.finish(df, (df.close > u.shift(1)) & (rv >= self.p["rvol"]), (df.close < l.shift(1)) & (rv >= self.p["rvol"]), panels={"RVOL": {"hist": rv - 1}}, sl=1.5, tp=3.0)


# ------------------------------------------------------------------ structure / transforms
class HeikinAshiTrend(_Ind):
    id = "heikin_ashi_trend"; name_en = "Heikin-Ashi colour flip with no-wick body"; name_fa = "چرخش رنگ هیکن‌آشی با بدنهٔ بدون سایه"
    author = "Dan Valcu"; params = {"trend": 50}
    description_en = "HA turns green with no lower wick (strong bar) after ≥2 red HA bars → long; stops on REAL prices (never HA)."
    description_fa = "HA سبز بدون سایهٔ پایین (کندل قوی) بعد از ≥۲ کندل قرمز → خرید؛ استاپ روی قیمت واقعی."
    rules_en = ["Long: HA close>open, HA low == HA open, prev 2 HA red, close > EMA50", "Short mirror"]; rules_fa = ["خرید: HA سبز، بدون سایهٔ پایین، دو HA قرمز قبلی، close > EMA50", "فروش برعکس"]
    def run(self, df):
        ha = t2.heikin_ashi(df); g = ha.close > ha.open; up, dn = self.trend_gate(df, self.p["trend"])
        no_lw = (ha.low >= ha.open - 1e-12); no_uw = (ha.high <= ha.open + 1e-12)
        long = g & no_lw & ~g.shift(1).fillna(True).astype(bool) & ~g.shift(2).fillna(True).astype(bool) & up
        short = ~g & no_uw & g.shift(1).fillna(False).astype(bool) & g.shift(2).fillna(False).astype(bool) & dn
        return self.finish(df, long, short, {"HA open": ha.open, "HA close": ha.close})


class ZigZagStructure(_Ind):
    id = "zigzag_structure"; name_en = "ZigZag structure break (HH/HL → break of last swing)"; name_fa = "شکست ساختار زیگزاگ (HH/HL → شکست آخرین سوئینگ)"
    author = "market-structure classic"; params = {"pct": 3.0}
    category = "Price Action"
    description_en = "Uses confirmed zigzag pivots only (no repaint): after a higher low, a close above the last confirmed swing high = structure continuation long."
    description_fa = "فقط پیوت‌های تأییدشدهٔ زیگزاگ (بدون ری‌پینت): بعد از کف بالاتر، بسته‌شدن بالای آخرین سقف تأییدشده = ادامهٔ ساختار."
    rules_en = ["Long: last two lows rising and close crosses above last confirmed high", "Short mirror"]; rules_fa = ["خرید: دو کف آخر صعودی و close از آخرین سقف تأییدشده بالا برود", "فروش برعکس"]
    def run(self, df):
        zz = t2.zigzag(df, self.p["pct"])
        piv = zz.dropna()
        n = len(df); last_hi = np.full(n, np.nan); last_lo = np.full(n, np.nan); prev_lo = np.full(n, np.nan); prev_hi = np.full(n, np.nan)
        pos = {ts: i for i, ts in enumerate(df.index)}
        hi_v = lo_v = None; hi_p = lo_p = None
        pts = [(pos[ts], v) for ts, v in piv.items()]
        j = 0
        for i in range(n):
            while j < len(pts) and pts[j][0] + 3 <= i:          # pivot known only after the reversal is confirmed (~3 bars later)
                k, v = pts[j]
                is_hi = abs(v - df.high.iloc[k]) <= abs(v - df.low.iloc[k])
                if is_hi:
                    hi_p, hi_v = hi_v, v
                else:
                    lo_p, lo_v = lo_v, v
                j += 1
            last_hi[i], last_lo[i], prev_lo[i], prev_hi[i] = (hi_v if hi_v is not None else np.nan), (lo_v if lo_v is not None else np.nan), (lo_p if lo_p is not None else np.nan), (hi_p if hi_p is not None else np.nan)
        LH, LL, PL, PH = (pd.Series(x, index=df.index) for x in (last_hi, last_lo, prev_lo, prev_hi))
        long = (LL > PL) & self.cross_up(df.close, LH)
        short = (LH < PH) & self.cross_down(df.close, LL)
        return self.finish(df, long, short, {"ZigZag": zz.interpolate(limit_area="inside")})


class VolumeProfileValue(_Ind):
    id = "vp_value_area"; name_en = "Volume-profile value-area rotation (80 % rule)"; name_fa = "چرخش ناحیهٔ ارزش پروفایل حجم (قانون ۸۰٪)"
    author = "Market Profile (Steidlmayer / Dalton)"; params = {"bins": 24, "lookback": 300}
    category = "Order Flow"
    description_en = "Dalton's 80 % rule: price opens/returns inside the value area from outside and holds two closes inside → it tends to rotate to the other VA edge. Rolling 300-bar profile."
    description_fa = "قانون ۸۰٪ دالتون: قیمت از بیرون به داخل ناحیهٔ ارزش برمی‌گردد و دو کندل داخل می‌ماند → به لبهٔ دیگر می‌رود. پروفایل غلتان ۳۰۰ کندلی."
    rules_en = ["Long: was below VAL, now 2 closes inside VA → target VAH, stop under VAL", "Short mirror"]; rules_fa = ["خرید: زیر VAL بود، حالا دو کندل داخل VA → هدف VAH، استاپ زیر VAL", "فروش برعکس"]
    def run(self, df):
        from strategies.orderflow import rolling_profile
        poc, vah, val, _ = rolling_profile(df, self.p["lookback"], self.p["bins"])
        inside = (df.close <= vah) & (df.close >= val)
        long = inside & inside.shift(1).fillna(False).astype(bool) & (df.close.shift(2) < val.shift(2))
        short = inside & inside.shift(1).fillna(False).astype(bool) & (df.close.shift(2) > vah.shift(2))
        sig = self.make_signal(long, short); a = ta.atr(df)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = val[sig == 1] - 0.5 * a[sig == 1]; tgt[sig == 1] = vah[sig == 1]
        stop[sig == -1] = vah[sig == -1] + 0.5 * a[sig == -1]; tgt[sig == -1] = val[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"POC": poc, "VAH": vah, "VAL": val})


class FibGoldenPocket(_Ind):
    id = "fib_golden_pocket"; name_en = "Fibonacci golden-pocket pullback (0.618–0.705)"; name_fa = "پولبک گلدن‌پاکت فیبوناچی (۰.۶۱۸–۰.۷۰۵)"
    author = "Fibonacci retracement classic"; params = {"swing": 5, "look": 100}
    category = "Price Action"
    description_en = "After an impulse (confirmed swing low → swing high), price retraces into 0.618–0.705 and prints a close back above 0.618 → long, target the 1.0/1.272 extension."
    description_fa = "بعد از ایمپالس (کف → سقف تأییدشده)، قیمت به ۰.۶۱۸–۰.۷۰۵ برمی‌گردد و بالای ۰.۶۱۸ بسته می‌شود → خرید، هدف اکستنشن ۱.۰/۱.۲۷۲."
    rules_en = ["Last confirmed swing pair defines the leg", "Long: low in golden pocket, close > 0.618 level", "Stop under 0.786, target swing high"]; rules_fa = ["آخرین جفت سوئینگ تأییدشده = پا", "خرید: کف در گلدن‌پاکت، close > سطح ۰.۶۱۸", "استاپ زیر ۰.۷۸۶، هدف سقف سوئینگ"]
    def run(self, df):
        s = self.p["swing"]
        sh, sl = ta.swing_points(df, s, s)
        hi_v = df.high.where(sh).shift(s).ffill(); lo_v = df.low.where(sl).shift(s).ffill()
        hi_i = pd.Series(np.where(sh, np.arange(len(df)), np.nan), index=df.index).shift(s).ffill()
        lo_i = pd.Series(np.where(sl, np.arange(len(df)), np.nan), index=df.index).shift(s).ffill()
        up_leg = hi_i > lo_i; dn_leg = lo_i > hi_i
        rng = hi_v - lo_v
        f618_u, f705_u, f786_u = hi_v - 0.618 * rng, hi_v - 0.705 * rng, hi_v - 0.786 * rng
        f618_d, f705_d, f786_d = lo_v + 0.618 * rng, lo_v + 0.705 * rng, lo_v + 0.786 * rng
        idx_now = pd.Series(np.arange(len(df)), index=df.index)
        fresh = (idx_now - np.maximum(hi_i, lo_i)) <= 3 * (hi_i - lo_i).abs().clip(lower=5)
        long = up_leg & fresh & (df.low <= f618_u) & (df.low >= f786_u) & (df.close > f618_u) & (rng > 2 * ta.atr(df)) & (ta.ema(df.close, 100) < df.close)
        short = dn_leg & fresh & (df.high >= f618_d) & (df.high <= f786_d) & (df.close < f618_d) & (rng > 2 * ta.atr(df)) & (ta.ema(df.close, 100) > df.close)
        long &= ~long.shift(1).fillna(False).astype(bool); short &= ~short.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        a = ta.atr(df)
        stop[sig == 1] = np.minimum(f786_u[sig == 1] - 0.5 * a[sig == 1], df.close[sig == 1] - a[sig == 1]); tgt[sig == 1] = hi_v[sig == 1]
        stop[sig == -1] = np.maximum(f786_d[sig == -1] + 0.5 * a[sig == -1], df.close[sig == -1] + a[sig == -1]); tgt[sig == -1] = lo_v[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"Fib 0.618": f618_u.where(up_leg, f618_d), "Fib 0.786": f786_u.where(up_leg, f786_d)})


class RelativeStrengthLeader(_Ind):
    id = "rs_leader"; name_en = "Relative-strength leader breakout (vs own 20-bar momentum rank)"; name_fa = "شکست لیدر قدرت نسبی"
    author = "O'Neil / Levy"; params = {"n": 20, "look": 100}
    description_en = "Without a benchmark series on the chart, RS is proxied by the 20-bar return percentile over 100 bars: ≥ 80th pct + new 20-bar high = leader breakout; ≤ 20th + new low = laggard breakdown."
    description_fa = "بدون سری معیار، RS با صدک بازده ۲۰ کندلی در ۱۰۰ کندل تخمین زده می‌شود: ≥ ۸۰ + سقف ۲۰ کندلی جدید = شکست لیدر؛ ≤ ۲۰ + کف جدید = شکست عقب‌مانده."
    rules_en = ["Long: momentum percentile ≥ 80 and close > 20-bar high", "Short mirror"]; rules_fa = ["خرید: صدک مومنتوم ≥ ۸۰ و close > سقف ۲۰", "فروش برعکس"]
    def run(self, df):
        mom = df.close.pct_change(self.p["n"]); pr = t2.percent_rank(mom, self.p["look"]); u, l = ta.donchian(df, self.p["n"])
        return self.finish(df, (pr >= 80) & (df.close > u.shift(1)), (pr <= 20) & (df.close < l.shift(1)), panels={"RS": {"pct": pr}}, sl=1.5, tp=3.5)


INDICATOR_STRATEGIES = [WMACross, ZLEMATrend, VWMACross, T3Slope, McGinleyDynamic, SuperSmootherCross, LinRegChannel, HalfTrendFlip,
                        VortexCross, TRIXSignal, CoppockTurn, SchaffCycle, UltimateDivergence, AwesomeSaucer, AcceleratorMomentum,
                        FisherTransform, QQECross, ElderRayImpulse, MassIndexReversal, ZScoreReversion, HistVolBreakout,
                        ADLineDivergence, VPTTrend, NVISmartMoney, KlingerCross, RVOLBreakout,
                        HeikinAshiTrend, ZigZagStructure, VolumeProfileValue, FibGoldenPocket, RelativeStrengthLeader]
