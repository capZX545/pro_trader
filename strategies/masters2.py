"""
The indicator INVENTORS' own rules — not the internet's simplified versions.
Each strategy here reproduces how the creator said to use their tool, from the primary sources:
  • J. Welles Wilder — "New Concepts in Technical Trading Systems" (1978): DMI with the Extreme Point Rule, ADXR, Parabolic SAR
  • George Lane — Stochastic: divergence + %D turning ("the ONLY signal that matters is divergence")
  • Gerald Appel — MACD: zero-line side + signal-line cross in trend direction, weekly filter
  • John Bollinger — "Bollinger on Bollinger Bands": W-bottom / M-top with %b and volume confirmation
  • Alexander Elder — Triple Screen (weekly MACD-hist tide → daily Force Index wave → buy-stop ripple)
  • Bill Williams — Alligator "wakes" + Fractal breakout outside the mouth
  • Stan Weinstein — Stage 2 breakout: 30-week MA turning up, 2× volume, buy the retest
  • Mark Minervini — Trend Template (8 criteria) + VCP breakout with 7–8% stop
  • William O'Neil — Cup-with-handle pivot + 40–50% volume surge, 7–8% stop
  • Marc Chaikin — CMF + A/D divergence, Chaikin Oscillator zero cross
  • Tushar Chande — Aroon 70/30 + CMO
  • Perry Kaufman — KAMA efficiency-adaptive trend (trade only when ER high)
  • Donald Lambert — CCI original rules (±100 entry/exit)
  • Larry Williams — Williams %R timing with 10-bar rule
  • Martin Pring — KST signal-line cross with long-term filter
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta
from core import indicators2 as I2


def _first(cond):
    return cond & ~cond.shift(1).fillna(False).astype(bool)


class WilderDMIExtreme(Strategy):
    id = "wilder_dmi_extreme"
    name_en = "Wilder DMI with Extreme Point Rule + ADXR (1978 original)"
    name_fa = "DMI وایلدر با قانون نقطهٔ اکسترمم + ADXR (نسخهٔ اصلی ۱۹۷۸)"
    category = "Masters' Indicators"
    author = "J. Welles Wilder Jr. — 'New Concepts in Technical Trading Systems', ch. 3"
    difficulty = 2
    timeframes = "4h – 1d"
    params = {"n": 14, "adx_min": 20}
    description_en = ("Wilder's ORIGINAL rule most people skip: when +DI crosses above −DI, do NOT buy at the cross — place a buy-stop at the HIGH "
                     "of the crossing bar (the Extreme Point). If price never exceeds it, the signal is void. Reverse = extreme low. "
                     "Trade only when ADX > 20 and ADX ≥ ADXR (trend developing).")
    description_fa = ("قانون اصلی وایلدر که اکثراً رد می‌کنند: وقتی +DI از −DI بالا رفت، در همان کراس نخر — یک سفارش خرید در سقف کندل کراس "
                     "(نقطهٔ اکسترمم) بگذار. اگر قیمت هرگز از آن نگذشت، سیگنال باطل است. برعکس = کف اکسترمم. فقط وقتی ADX > ۲۰ و ADX ≥ ADXR.")
    rules_en = ["+DI crosses above −DI → mark extreme point = that bar's high", "Enter only when a later close exceeds the extreme point (within 5 bars)",
                "Filter: ADX > 20 and ADX rising vs ADXR", "Stop: extreme point of the opposite side (cross bar's low)"]
    rules_fa = ["+DI از −DI بالا برود ← نقطهٔ اکسترمم = سقف همان کندل", "فقط وقتی بستهٔ بعدی از نقطهٔ اکسترمم گذشت وارد شو (تا ۵ کندل)",
                "فیلتر: ADX > ۲۰ و ADX در حال رشد نسبت به ADXR", "استاپ: اکسترمم سمت مقابل (کف کندل کراس)"]
    pros_en = ["Kills most DMI whipsaws (Wilder's own fix)"]; cons_en = ["Later entry"]
    pros_fa = ["اکثر ویپساوهای DMI را حذف می‌کند (اصلاح خود وایلدر)"]; cons_fa = ["ورود دیرتر"]

    def run(self, df):
        n = self.p["n"]
        adx, pdi, mdi = ta.adx(df, n)
        adxr = (adx + adx.shift(n)) / 2
        a = ta.atr(df)
        up_x = self.cross_up(pdi, mdi); dn_x = self.cross_down(pdi, mdi)
        ep_hi = df.high.where(up_x).ffill(limit=5); ep_lo_stop = df.low.where(up_x).ffill(limit=5)
        ep_lo = df.low.where(dn_x).ffill(limit=5); ep_hi_stop = df.high.where(dn_x).ffill(limit=5)
        filt = (adx > self.p["adx_min"]) & (adx >= adxr)
        long = _first((df.close > ep_hi) & filt & ep_hi.notna())
        short = _first((df.close < ep_lo) & filt & ep_lo.notna())
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = ep_lo_stop[sig == 1]; stop[sig == -1] = ep_hi_stop[sig == -1]
        r = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 3 * r[sig == 1]; tgt[sig == -1] = df.close[sig == -1] - 3 * r[sig == -1]
        return StrategyResult(sig, stop, tgt, panels={"DMI": {"+DI": pdi, "-DI": mdi, "ADX": adx, "ADXR": adxr}})


class LaneStochDivergence(Strategy):
    id = "lane_stoch_div"
    name_en = "George Lane Stochastic — divergence + %D hook (inventor's rule)"
    name_fa = "استوکاستیک جورج لین — واگرایی + قلاب %D (قانون مخترع)"
    category = "Masters' Indicators"
    author = "George C. Lane — 'Lane's Stochastics' (1984): 'the only signal that will cause you to buy or sell is a divergence'"
    difficulty = 3
    timeframes = "1h – 1d"
    params = {"k": 14, "d": 3, "lookback": 30}
    description_en = ("Lane said overbought/oversold crosses are NOT signals. The signal is: price makes a lower low while %D makes a higher low "
                     "(bullish divergence) below 25, then %D hooks up and %K crosses above %D. Mirror for bearish above 75.")
    description_fa = ("لین گفت کراس‌های اشباع سیگنال نیستند. سیگنال این است: قیمت کف پایین‌تر می‌زند در حالی که %D کف بالاتر می‌زند "
                     "(واگرایی صعودی) زیر ۲۵، سپس %D قلاب می‌زند و %K از %D بالا می‌رود. برعکس برای نزولی بالای ۷۵.")
    rules_en = ["Price low < prior swing low (≤30 bars) AND %D low > prior %D low, both %D lows < 25", "%D turns up and %K crosses above %D",
                "Short: mirror above 75", "Stop below divergence low"]
    rules_fa = ["کف قیمت < کف سوئینگ قبلی (≤۳۰ کندل) و کف %D > کف %D قبلی، هر دو < ۲۵", "%D برمی‌گردد و %K از %D بالا می‌رود",
                "فروش: برعکس بالای ۷۵", "استاپ زیر کف واگرایی"]
    pros_en = ["Inventor-grade signal, far fewer false entries"]; cons_en = ["Rare; needs patience"]
    pros_fa = ["سیگنال در حد مخترع، ورود کاذب بسیار کمتر"]; cons_fa = ["نادر؛ صبر لازم"]

    def run(self, df):
        k, d = ta.stochastic(df, self.p["k"], self.p["d"], 3)[:2]
        lb = self.p["lookback"]
        a = ta.atr(df)
        # swing lows of %D and price (5-bar pivots), shifted so they're known
        sl_price = (df.low == df.low.rolling(11, center=True).min()).shift(5).fillna(False)
        piv_price = df.low.shift(5).where(sl_price).ffill()
        piv_d = d.shift(5).where(sl_price).ffill()
        prev_piv_price = piv_price.where(sl_price).shift(1).ffill()  # placeholder chain
        # simpler robust approach: compare current pivot vs previous pivot values
        pp = df.low.shift(5).where(sl_price); dd = d.shift(5).where(sl_price)
        pp_prev = pp.dropna().shift(1).reindex(df.index).ffill(); dd_prev = dd.dropna().shift(1).reindex(df.index).ffill()
        bull_div = sl_price & (pp < pp_prev) & (dd > dd_prev) & (dd < 25) & (dd_prev < 25)
        bull_arm = bull_div.rolling(lb).max().fillna(0).astype(bool)
        long = _first(bull_arm & self.cross_up(k, d) & (d > d.shift(1)))
        sh_price = (df.high == df.high.rolling(11, center=True).max()).shift(5).fillna(False)
        ph = df.high.shift(5).where(sh_price); dh = d.shift(5).where(sh_price)
        ph_prev = ph.dropna().shift(1).reindex(df.index).ffill(); dh_prev = dh.dropna().shift(1).reindex(df.index).ffill()
        bear_div = sh_price & (ph > ph_prev) & (dh < dh_prev) & (dh > 75) & (dh_prev > 75)
        bear_arm = bear_div.rolling(lb).max().fillna(0).astype(bool)
        short = _first(bear_arm & self.cross_down(k, d) & (d < d.shift(1)))
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.0, 4.0)
        return StrategyResult(sig, st, tp, panels={"Stochastic": {"%K": k, "%D": d}})


class AppelMACD(Strategy):
    id = "appel_macd"
    name_en = "Gerald Appel MACD — zero-line side + signal cross (inventor's rules)"
    name_fa = "MACD جرالد اپل — سمت خط صفر + کراس سیگنال (قوانین مخترع)"
    category = "Masters' Indicators"
    author = "Gerald Appel — 'Technical Analysis: Power Tools for Active Investors' (2005)"
    difficulty = 1
    timeframes = "4h – 1d"
    params = {"fast": 12, "slow": 26, "sig": 9, "htf_mult": 5}
    description_en = ("Appel: buy signal-line crosses only when MACD is BELOW zero (buying a dip in a rising market), and only when the "
                     "slower 'weekly' MACD (5× periods) is rising. Sell crosses only above zero with slow MACD falling. Stop-and-reverse is NOT allowed.")
    description_fa = ("اپل: کراس سیگنال خرید فقط وقتی MACD زیر صفر است (خرید دیپ در بازار صعودی) و فقط وقتی MACD کندتر «هفتگی» (۵ برابر دوره) "
                     "صعودی است. کراس فروش فقط بالای صفر با MACD کند نزولی. استاپ-اند-ریورس مجاز نیست.")
    rules_en = ["Long: MACD crosses above signal while MACD < 0 AND slow MACD(60,130) rising", "Short: MACD crosses below signal while MACD > 0 AND slow MACD falling", "Stop 2 ATR, target 4 ATR"]
    rules_fa = ["خرید: کراس MACD بالای سیگنال در حالی که MACD < ۰ و MACD کند (۶۰،۱۳۰) صعودی", "فروش: کراس زیر سیگنال در حالی که MACD > ۰ و MACD کند نزولی", "استاپ 2 ATR، هدف 4 ATR"]
    pros_en = ["Buys pullbacks, not tops"]; cons_en = ["Misses momentum bursts"]
    pros_fa = ["پولبک می‌خرد نه سقف"]; cons_fa = ["انفجارهای مومنتوم را از دست می‌دهد"]

    def run(self, df):
        p = self.p
        m, s, h = ta.macd(df.close, p["fast"], p["slow"], p["sig"])
        ms, ss, _ = ta.macd(df.close, p["fast"] * p["htf_mult"], p["slow"] * p["htf_mult"], p["sig"] * p["htf_mult"])
        a = ta.atr(df)
        long = self.cross_up(m, s) & (m < 0) & (ms > ms.shift(1))
        short = self.cross_down(m, s) & (m > 0) & (ms < ms.shift(1))
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.0, 4.0)
        return StrategyResult(sig, st, tp, panels={"MACD": {"MACD": m, "Signal": s, "Hist": h}, "Slow MACD": {"MACD×5": ms}})


class BollingerWBottom(Strategy):
    id = "bollinger_w"
    name_en = "John Bollinger W-Bottom / M-Top with %b + volume (book rules)"
    name_fa = "کف W / سقف M جان بولینگر با %b و حجم (قوانین کتاب)"
    category = "Masters' Indicators"
    author = "John Bollinger — 'Bollinger on Bollinger Bands' (2001), ch. 15–16"
    difficulty = 3
    timeframes = "1h – 1d"
    params = {"n": 20, "k": 2.0, "lookback": 25}
    description_en = ("Bollinger's signature setup: first low BELOW the lower band (%b < 0), second low LOWER in price but INSIDE the band "
                     "(%b > 0) — a lower low the indicator refuses to confirm — on lighter volume; buy when price breaks the middle peak. "
                     "Never 'sell at the upper band' — walking the band is the strongest trend signal.")
    description_fa = ("ستاپ امضای بولینگر: کف اول زیر باند پایین (%b < ۰)، کف دوم در قیمت پایین‌تر ولی داخل باند (%b > ۰) — کفی که اندیکاتور تأیید "
                     "نمی‌کند — با حجم کمتر؛ وقتی قیمت از قلهٔ میانی گذشت بخر. هرگز «در باند بالا نفروش» — راه رفتن روی باند قوی‌ترین سیگنال روند است.")
    rules_en = ["Low #1 with %b < 0", "Low #2 (≤25 bars later): price low < low #1 AND %b > 0, volume < volume at low #1", "Entry: close > highest high between the two lows",
                "Stop below low #2; target: upper band"]
    rules_fa = ["کف ۱ با %b < ۰", "کف ۲ (تا ۲۵ کندل بعد): کف قیمت < کف ۱ و %b > ۰، حجم < حجم کف ۱", "ورود: بسته > بالاترین سقف بین دو کف",
                "استاپ زیر کف ۲؛ هدف: باند بالا"]
    pros_en = ["Textbook reversal with built-in non-confirmation logic"]; cons_en = ["Needs volume data; rare"]
    pros_fa = ["برگشت کلاسیک با منطق عدم‌تأیید داخلی"]; cons_fa = ["حجم لازم دارد؛ نادر"]

    def run(self, df):
        p = self.p
        u, m, l = ta.bollinger(df.close, p["n"], p["k"])
        pb = (df.close - l) / (u - l).replace(0, np.nan)
        a = ta.atr(df)
        lb = p["lookback"]
        piv = (df.low == df.low.rolling(7, center=True).min()).shift(3).fillna(False)
        low1_px = df.low.shift(3).where(piv & (pb.shift(3) < 0))
        low1_vol = df.volume.shift(3).where(piv & (pb.shift(3) < 0))
        low1_px_f = low1_px.ffill(limit=lb); low1_vol_f = low1_vol.ffill(limit=lb)
        low2 = piv & (df.low.shift(3) < low1_px_f) & (pb.shift(3) > 0) & ((df.volume.shift(3) < low1_vol_f) | (df.volume.sum() == 0)) & low1_px_f.notna()
        neck = df.high.rolling(lb).max().where(low2).ffill(limit=lb)   # approx: highest high in window
        low2_px = df.low.shift(3).where(low2).ffill(limit=lb)
        long = _first((df.close > neck) & neck.notna())
        # M-top mirror
        pivh = (df.high == df.high.rolling(7, center=True).max()).shift(3).fillna(False)
        hi1 = df.high.shift(3).where(pivh & (pb.shift(3) > 1)).ffill(limit=lb)
        hi2 = pivh & (df.high.shift(3) > hi1) & (pb.shift(3) < 1) & hi1.notna()
        neck_s = df.low.rolling(lb).min().where(hi2).ffill(limit=lb)
        hi2_px = df.high.shift(3).where(hi2).ffill(limit=lb)
        short = _first((df.close < neck_s) & neck_s.notna())
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = low2_px[sig == 1]; tgt[sig == 1] = u[sig == 1]
        stop[sig == -1] = hi2_px[sig == -1]; tgt[sig == -1] = l[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"BB Up": u, "BB Mid": m, "BB Low": l}, panels={"%b": {"%b": pb}})


class ElderTripleScreen(Strategy):
    id = "elder_triple_screen"
    name_en = "Elder Triple Screen (tide → wave → ripple), full original"
    name_fa = "سه‌صافی الدر (جزر و مد ← موج ← ریپل)، نسخهٔ کامل اصلی"
    category = "Masters' Indicators"
    author = "Dr. Alexander Elder — 'Trading for a Living' (1993), ch. 43"
    difficulty = 3
    timeframes = "1h – 1d (uses 5× higher TF internally)"
    params = {"htf_mult": 5, "fi_n": 2}
    description_en = ("Screen 1 (tide): higher-TF MACD-histogram slope (5× periods) sets allowed direction. Screen 2 (wave): 2-bar Force Index "
                     "dips below zero in an uptide (pullback). Screen 3 (ripple): buy-stop one tick above the previous bar's high — "
                     "entered only if price proves strength. Stop below the pullback low.")
    description_fa = ("صافی ۱ (جزر و مد): شیب هیستوگرام MACD تایم بالاتر (۵ برابر) جهت مجاز را تعیین می‌کند. صافی ۲ (موج): Force Index دو کندلی "
                     "در جزر صعودی زیر صفر می‌رود (پولبک). صافی ۳ (ریپل): سفارش خرید یک تیک بالای سقف کندل قبل — فقط اگر قیمت قدرت نشان دهد. استاپ زیر کف پولبک.")
    rules_en = ["Tide: MACD-hist(60,130,45) rising → longs only; falling → shorts only", "Wave: Force Index(2) < 0 (long) / > 0 (short)",
                "Ripple: close > previous high (long) / < previous low (short) within 3 bars of wave", "Stop: lowest low of last 3 bars"]
    rules_fa = ["جزر: هیستوگرام MACD(60,130,45) صعودی ← فقط خرید؛ نزولی ← فقط فروش", "موج: Force Index(2) < ۰ (خرید) / > ۰ (فروش)",
                "ریپل: بسته > سقف قبلی (خرید) / < کف قبلی (فروش) تا ۳ کندل بعد از موج", "استاپ: پایین‌ترین کف ۳ کندل اخیر"]
    pros_en = ["Multi-timeframe by design", "Never fights the tide"]; cons_en = ["Three conditions → fewer trades"]
    pros_fa = ["ذاتاً چندتایم‌فریمی", "هرگز با جزر نمی‌جنگد"]; cons_fa = ["سه شرط ← معاملهٔ کمتر"]

    def run(self, df):
        p = self.p
        k = p["htf_mult"]
        _, _, h_htf = ta.macd(df.close, 12 * k, 26 * k, 9 * k)
        tide_up = h_htf > h_htf.shift(1); tide_dn = h_htf < h_htf.shift(1)
        fi = ta.ema(df.close.diff() * df.volume, p["fi_n"]) if df.volume.sum() > 0 else ta.ema(df.close.diff(), p["fi_n"])
        wave_l = (fi < 0).rolling(3).max().fillna(0).astype(bool); wave_s = (fi > 0).rolling(3).max().fillna(0).astype(bool)
        long = _first(tide_up & wave_l & (df.close > df.high.shift(1)))
        short = _first(tide_dn & wave_s & (df.close < df.low.shift(1)))
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        lo3 = df.low.rolling(3).min(); hi3 = df.high.rolling(3).max()
        stop[sig == 1] = lo3[sig == 1]; stop[sig == -1] = hi3[sig == -1]
        r = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 3 * r[sig == 1]; tgt[sig == -1] = df.close[sig == -1] - 3 * r[sig == -1]
        return StrategyResult(sig, stop, tgt, panels={"Tide (HTF MACD-hist)": {"hist×5": h_htf}, "Force Index(2)": {"FI": fi}})


class WilliamsAlligatorFractal(Strategy):
    id = "bw_alligator_fractal"
    name_en = "Bill Williams Alligator awake + Fractal breakout (Trading Chaos)"
    name_fa = "الیگیتور بیدار + شکست فراکتال بیل ویلیامز (Trading Chaos)"
    category = "Masters' Indicators"
    author = "Bill Williams — 'Trading Chaos' (1995) / 'New Trading Dimensions' (1998)"
    difficulty = 2
    timeframes = "1h – 1d"
    params = {"jaw": 13, "teeth": 8, "lips": 5}
    description_en = ("Alligator = 13/8/5 smoothed MAs of median price shifted 8/5/3 forward. It 'sleeps' when lines intertwine — never trade. "
                     "When lips > teeth > jaw (mouth open up), buy the break of the most recent UP fractal that lies ABOVE the teeth. "
                     "Exit/stop when price closes below the teeth (red line).")
    description_fa = ("الیگیتور = میانگین‌های نرم ۱۳/۸/۵ قیمت میانه با شیفت ۸/۵/۳ به جلو. وقتی خط‌ها در هم پیچیده‌اند «خواب» است — معامله نکن. "
                     "وقتی لب > دندان > آرواره (دهان به بالا باز)، شکست آخرین فراکتال بالا که بالای دندان است را بخر. خروج/استاپ وقتی زیر دندان (خط قرمز) بسته شد.")
    rules_en = ["Mouth open: lips > teeth > jaw (long) or reversed (short), lines separated > 0.3 ATR", "Fractal: 5-bar high with 2 lower highs each side, located above the teeth",
                "Entry: close > fractal high", "Stop: teeth line (dynamic)"]
    rules_fa = ["دهان باز: لب > دندان > آرواره (خرید) یا برعکس (فروش)، فاصلهٔ خطوط > 0.3 ATR", "فراکتال: سقف ۵ کندلی با دو سقف پایین‌تر هر طرف، بالای دندان",
                "ورود: بسته > سقف فراکتال", "استاپ: خط دندان (داینامیک)"]
    pros_en = ["Built-in 'don't trade the range' filter"]; cons_en = ["Lag of forward-shifted MAs"]
    pros_fa = ["فیلتر داخلی «در رنج معامله نکن»"]; cons_fa = ["تأخیر میانگین‌های شیفت‌شده"]

    def run(self, df):
        p = self.p
        mp = (df.high + df.low) / 2
        smma = lambda s, n: s.ewm(alpha=1 / n, adjust=False).mean()
        jaw = smma(mp, p["jaw"]).shift(8); teeth = smma(mp, p["teeth"]).shift(5); lips = smma(mp, p["lips"]).shift(3)
        a = ta.atr(df)
        open_up = (lips > teeth) & (teeth > jaw) & ((lips - jaw) > 0.3 * a)
        open_dn = (lips < teeth) & (teeth < jaw) & ((jaw - lips) > 0.3 * a)
        fr_up = (df.high == df.high.rolling(5, center=True).max()).shift(2).fillna(False)
        fr_dn = (df.low == df.low.rolling(5, center=True).min()).shift(2).fillna(False)
        up_lvl = df.high.shift(2).where(fr_up & (df.high.shift(2) > teeth)).ffill(limit=30)
        dn_lvl = df.low.shift(2).where(fr_dn & (df.low.shift(2) < teeth)).ffill(limit=30)
        long = _first(open_up & (df.close > up_lvl) & up_lvl.notna())
        short = _first(open_dn & (df.close < dn_lvl) & dn_lvl.notna())
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = np.minimum(teeth[sig == 1], df.close[sig == 1] - 1.0 * a[sig == 1])
        stop[sig == -1] = np.maximum(teeth[sig == -1], df.close[sig == -1] + 1.0 * a[sig == -1])
        r = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 3 * r[sig == 1]; tgt[sig == -1] = df.close[sig == -1] - 3 * r[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"Jaw(13)": jaw, "Teeth(8)": teeth, "Lips(5)": lips})


class WeinsteinStage2(Strategy):
    id = "weinstein_stage2"
    name_en = "Stan Weinstein Stage-2 breakout (30-week MA + 2× volume)"
    name_fa = "شکست مرحلهٔ ۲ استن واینستین (میانگین ۳۰ هفته + حجم ۲ برابر)"
    category = "Masters' Indicators"
    author = "Stan Weinstein — 'Secrets for Profiting in Bull and Bear Markets' (1988)"
    difficulty = 2
    timeframes = "1d – 1wk (uses 150-day ≈ 30-week MA on daily)"
    params = {"ma": 150, "base_n": 60, "vol_mult": 2.0}
    description_en = ("Stage analysis: buy the breakout from a Stage-1 base above the 30-week MA when the MA has flattened/turned up and volume "
                     "on the breakout is ≥ 2× its average. Sell when price closes below a declining 30-week MA (Stage 4).")
    description_fa = ("تحلیل مراحل: شکست از پایهٔ مرحلهٔ ۱ به بالای میانگین ۳۰ هفته را بخر وقتی میانگین صاف/صعودی شده و حجم شکست ≥ ۲ برابر میانگین. "
                     "وقتی زیر میانگین ۳۰ هفتهٔ نزولی بسته شد بفروش (مرحلهٔ ۴).")
    rules_en = ["Close > 60-bar high (base breakout)", "Close > MA150 and MA150 ≥ MA150[10] (not declining)", "Volume ≥ 2× 50-bar average",
                "Short (Stage 4): close < 60-bar low, below declining MA150", "Stop: below base high (retest) / 2.5 ATR"]
    rules_fa = ["بسته > سقف ۶۰ کندل (شکست پایه)", "بسته > MA150 و MA150 ≥ مقدار ۱۰ کندل قبل (نزولی نیست)", "حجم ≥ ۲ برابر میانگین ۵۰ کندل",
                "فروش (مرحلهٔ ۴): بسته < کف ۶۰ کندل، زیر MA150 نزولی", "استاپ: زیر سقف پایه / 2.5 ATR"]
    pros_en = ["Catches the start of big moves"]; cons_en = ["Few signals; needs volume"]
    pros_fa = ["شروع حرکت‌های بزرگ را می‌گیرد"]; cons_fa = ["سیگنال کم؛ حجم لازم"]

    def run(self, df):
        p = self.p
        ma = ta.sma(df.close, p["ma"]); a = ta.atr(df)
        hh = df.high.rolling(p["base_n"]).max().shift(1); ll = df.low.rolling(p["base_n"]).min().shift(1)
        vol_ok = (df.volume >= p["vol_mult"] * df.volume.rolling(50).mean()) | (df.volume.sum() == 0)
        long = _first((df.close > hh) & (df.close > ma) & (ma >= ma.shift(10)) & vol_ok)
        short = _first((df.close < ll) & (df.close < ma) & (ma <= ma.shift(10)) & vol_ok)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.5, 7.5)
        return StrategyResult(sig, st, tp, overlays={"MA150 (30-wk)": ma, "Base high": hh, "Base low": ll})


class MinerviniTrendTemplate(Strategy):
    id = "minervini_tt"
    name_en = "Minervini Trend Template (8 criteria) + tight-range breakout, 8% stop"
    name_fa = "الگوی روند مینروینی (۸ معیار) + شکست رنج فشرده، استاپ ۸٪"
    category = "Masters' Indicators"
    author = "Mark Minervini — 'Trade Like a Stock Market Wizard' (2013), US Investing Champion 1997 & 2021"
    difficulty = 3
    timeframes = "1d (stocks)"
    params = {"contract_n": 15, "contract_max_pct": 8.0, "stop_pct": 8.0}
    bt_kwargs = {"allow_short": False, "max_bars": 60}
    description_en = ("All 8 template criteria must pass: price > MA50 > MA150 > MA200; MA200 rising ≥ 1 month; price ≥ 30% above 52-wk low; "
                     "within 25% of 52-wk high; relative strength vs its own 6-month return positive. Then buy the breakout of a tight "
                     "15-day range (VCP proxy: range < 8%) on volume. Hard stop 8% (Minervini's max loss).")
    description_fa = ("هر ۸ معیار باید برقرار باشد: قیمت > MA50 > MA150 > MA200؛ MA200 حداقل ۱ ماه صعودی؛ قیمت ≥ ۳۰٪ بالای کف ۵۲ هفته؛ "
                     "در ۲۵٪ سقف ۵۲ هفته؛ قدرت نسبی ۶ ماهه مثبت. سپس شکست رنج فشردهٔ ۱۵ روزه (تقریب VCP: دامنه < ۸٪) با حجم را بخر. استاپ سخت ۸٪.")
    rules_en = ["Trend Template: C>MA50>MA150>MA200, MA200>MA200[22], C≥1.3×52w-low, C≥0.75×52w-high, ROC(126)>0",
                "15-bar range (high−low)/close < 8% (contraction)", "Entry: close > 15-bar high with volume > 1.4× avg", "Stop 8% below entry; trail with MA50 (exit close < MA50)"]
    rules_fa = ["الگوی روند: C>MA50>MA150>MA200، MA200>MA200[22]، C≥1.3×کف ۵۲ه، C≥0.75×سقف ۵۲ه، ROC(126)>۰",
                "دامنهٔ ۱۵ کندل (سقف−کف)/بسته < ۸٪ (انقباض)", "ورود: بسته > سقف ۱۵ کندل با حجم > ۱.۴ برابر", "استاپ ۸٪؛ خروج بسته < MA50"]
    pros_en = ["Only the strongest leaders qualify"]; cons_en = ["Stocks/daily only; nothing in bear markets (by design)"]
    pros_fa = ["فقط قوی‌ترین لیدرها واجد شرایط‌اند"]; cons_fa = ["فقط سهام/روزانه؛ در بازار خرسی هیچ (عمداً)"]

    def run(self, df):
        p = self.p
        c = df.close
        m50, m150, m200 = ta.sma(c, 50), ta.sma(c, 150), ta.sma(c, 200)
        lo52, hi52 = df.low.rolling(250).min(), df.high.rolling(250).max()
        tt = (c > m50) & (m50 > m150) & (m150 > m200) & (m200 > m200.shift(22)) & (c >= 1.3 * lo52) & (c >= 0.75 * hi52) & (c / c.shift(126) > 1)
        n = p["contract_n"]
        rng = (df.high.rolling(n).max().shift(1) - df.low.rolling(n).min().shift(1)) / c * 100
        vol_ok = (df.volume > 1.4 * df.volume.rolling(50).mean()) | (df.volume.sum() == 0)
        long = _first(tt & (rng < p["contract_max_pct"]) & (c > df.high.rolling(n).max().shift(1)) & vol_ok)
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = c[sig == 1] * (1 - p["stop_pct"] / 100); tgt[sig == 1] = c[sig == 1] * (1 + 3 * p["stop_pct"] / 100)
        return StrategyResult(sig, stop, tgt, overlays={"MA50": m50, "MA150": m150, "MA200": m200}, exit_long=(c < m50), bt_kwargs=dict(self.bt_kwargs))


class ONeilCupHandle(Strategy):
    id = "oneil_cup_handle"
    name_en = "O'Neil Cup-with-Handle pivot breakout (CAN SLIM technicals)"
    name_fa = "شکست پیوت فنجان و دسته اونیل (بخش تکنیکال CAN SLIM)"
    category = "Masters' Indicators"
    author = "William J. O'Neil — 'How to Make Money in Stocks' (1988); IBD rules"
    difficulty = 4
    timeframes = "1d (stocks)"
    params = {"cup_min": 35, "cup_max": 130, "handle_min": 5, "handle_max": 15, "depth_min": 12, "depth_max": 35, "stop_pct": 7.0}
    bt_kwargs = {"allow_short": False, "max_bars": 80}
    description_en = ("Cup: 7–26 weeks, 12–35% deep, U-shaped; handle: 1–3 weeks, drifts DOWN ≤ 12% in the upper half of the cup, on drying volume. "
                     "Buy at the handle high (pivot) + 0.1 with volume ≥ 40% above average; stop 7% (O'Neil's iron rule); exit close < MA50.")
    description_fa = ("فنجان: ۷–۲۶ هفته، عمق ۱۲–۳۵٪، U شکل؛ دسته: ۱–۳ هفته، رانش نزولی ≤ ۱۲٪ در نیمهٔ بالایی فنجان با حجم خشک‌شونده. "
                     "در سقف دسته (پیوت) با حجم ≥ ۴۰٪ بالای میانگین بخر؛ استاپ ۷٪ (قانون آهنین اونیل)؛ خروج بسته < MA50.")
    rules_en = ["Left rim = 35–130-bar high before handle; cup low 12–35% below rim; right side recovers to within 5% of rim",
                "Handle 5–15 bars, low ≥ midpoint of cup, handle volume < cup volume avg", "Entry: close > handle high AND volume ≥ 1.4× avg AND close > MA200", "Stop 7%; exit close < MA50"]
    rules_fa = ["لبهٔ چپ = سقف ۳۵–۱۳۰ کندل پیش از دسته؛ کف فنجان ۱۲–۳۵٪ زیر لبه؛ سمت راست تا ۵٪ لبه بازیابی",
                "دسته ۵–۱۵ کندل، کف ≥ میانهٔ فنجان، حجم دسته < میانگین حجم فنجان", "ورود: بسته > سقف دسته و حجم ≥ ۱.۴ برابر و بسته > MA200", "استاپ ۷٪؛ خروج بسته < MA50"]
    pros_en = ["The most-studied growth-stock base"]; cons_en = ["Pattern detection is approximate; rare"]
    pros_fa = ["پرمطالعه‌ترین پایهٔ سهام رشدی"]; cons_fa = ["تشخیص الگو تقریبی؛ نادر"]

    def run(self, df):
        p = self.p
        c, h, l, v = df.close, df.high, df.low, df.volume
        n = len(df)
        sig = np.zeros(n); stop = np.full(n, np.nan); tgt = np.full(n, np.nan)
        m50 = ta.sma(c, 50).values; m200 = ta.sma(c, 200).values
        vavg = v.rolling(50).mean().values
        hv, lv, cv, vv = h.values, l.values, c.values, v.values
        last_sig = -999
        for i in range(p["cup_max"] + p["handle_max"], n):
            if i - last_sig < 20 or not (cv[i] > m200[i]):
                continue
            for hl in range(p["handle_min"], p["handle_max"] + 1):
                hs, he = i - hl, i - 1                     # handle window
                handle_hi = hv[hs:he + 1].max(); handle_lo = lv[hs:he + 1].min()
                if not (cv[i] > handle_hi and cv[i - 1] <= handle_hi):
                    continue
                for cl in (p["cup_min"], 60, 90, p["cup_max"]):
                    cs = hs - cl
                    if cs < 0:
                        continue
                    rim = hv[cs:cs + max(5, cl // 5)].max()
                    cup_lo = lv[cs:hs].min()
                    depth = (rim - cup_lo) / rim * 100
                    if not (p["depth_min"] <= depth <= p["depth_max"]):
                        continue
                    if handle_hi < rim * 0.95 or handle_hi > rim * 1.05:
                        continue
                    if handle_lo < (rim + cup_lo) / 2:
                        continue
                    if vv[hs:he + 1].mean() > vv[cs:hs].mean() and vv.sum() > 0:
                        continue
                    if vv.sum() > 0 and vv[i] < 1.4 * vavg[i]:
                        continue
                    sig[i] = 1; stop[i] = cv[i] * (1 - p["stop_pct"] / 100); tgt[i] = cv[i] * (1 + 0.25)
                    last_sig = i
                    break
                if sig[i]:
                    break
        sigs = pd.Series(sig, index=df.index)
        return StrategyResult(sigs, pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index),
                              overlays={"MA50": ta.sma(c, 50), "MA200": ta.sma(c, 200)}, exit_long=(c < ta.sma(c, 50)), bt_kwargs=dict(self.bt_kwargs))


class ChaikinMoneyFlow(Strategy):
    id = "chaikin_cmf"
    name_en = "Marc Chaikin — CMF persistence + Chaikin Oscillator zero cross"
    name_fa = "مارک چایکین — پایداری CMF + کراس صفر اسیلاتور چایکین"
    category = "Masters' Indicators"
    author = "Marc Chaikin (creator of A/D line, CMF, Chaikin Oscillator)"
    difficulty = 2
    timeframes = "4h – 1d"
    params = {"cmf_n": 21, "cmf_lvl": 0.10, "persist": 5}
    description_en = ("Chaikin's rule: CMF above +0.10 for several bars (persistent accumulation), then the Chaikin Oscillator crosses above zero "
                     "in the direction of the 90-bar trend. Sustained CMF, not a spike, is what marks institutional buying.")
    description_fa = ("قانون چایکین: CMF بالای +۰.۱۰ برای چند کندل (انباشت پایدار)، سپس اسیلاتور چایکین در جهت روند ۹۰ کندلی از صفر بالا می‌رود. "
                     "CMF پایدار، نه یک جهش، نشان خرید نهادی است.")
    rules_en = ["CMF(21) > +0.10 for 5 consecutive bars", "Chaikin Osc(3,10) crosses above 0", "Close > EMA90", "Short: mirror (CMF < −0.10)"]
    rules_fa = ["CMF(21) > +۰.۱۰ در ۵ کندل متوالی", "اسیلاتور چایکین (۳،۱۰) از صفر بالا برود", "بسته > EMA90", "فروش: برعکس (CMF < −۰.۱۰)"]
    pros_en = ["Volume-confirmed"]; cons_en = ["Needs real volume (no forex)"]
    pros_fa = ["تأیید حجمی"]; cons_fa = ["حجم واقعی لازم (فارکس نه)"]

    def run(self, df):
        p = self.p
        cmf = ta.cmf(df, p["cmf_n"]); co = I2.chaikin_osc(df); e = ta.ema(df.close, 90); a = ta.atr(df)
        acc = (cmf > p["cmf_lvl"]).rolling(p["persist"]).sum() >= p["persist"]
        dist = (cmf < -p["cmf_lvl"]).rolling(p["persist"]).sum() >= p["persist"]
        long = self.cross_up(co, 0) & acc & (df.close > e)
        short = self.cross_down(co, 0) & dist & (df.close < e)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.0, 4.0)
        return StrategyResult(sig, st, tp, overlays={"EMA90": e}, panels={"CMF": {"CMF": cmf}, "Chaikin Osc": {"CO": co}})


class ChandeAroonCMO(Strategy):
    id = "chande_aroon_cmo"
    name_en = "Tushar Chande — Aroon 70/30 trend + CMO pullback"
    name_fa = "توشار چاند — روند آرون ۷۰/۳۰ + پولبک CMO"
    category = "Masters' Indicators"
    author = "Tushar Chande — 'The New Technical Trader' (1994), inventor of Aroon, CMO, VIDYA, StochRSI"
    difficulty = 2
    timeframes = "1h – 1d"
    params = {"aroon_n": 25, "cmo_n": 14, "cmo_pull": -20}
    description_en = ("Chande's trend definition: Aroon-Up > 70 AND Aroon-Down < 30 = established uptrend. Enter on a CMO pullback below −20 "
                     "that turns back up (not at the Aroon cross, which is early and noisy).")
    description_fa = ("تعریف روند چاند: Aroon-Up > ۷۰ و Aroon-Down < ۳۰ = روند صعودی تثبیت‌شده. در پولبک CMO زیر −۲۰ که برمی‌گردد وارد شو (نه در کراس آرون که زود و نویزی است).")
    rules_en = ["Aroon Up > 70 and Aroon Down < 30", "CMO(14) was < −20 within last 3 bars and now rising", "Short: mirror", "Stop 2 ATR, target 4 ATR"]
    rules_fa = ["Aroon Up > ۷۰ و Aroon Down < ۳۰", "CMO(14) طی ۳ کندل اخیر < −۲۰ بوده و حالا صعودی", "فروش: برعکس", "استاپ 2 ATR، هدف 4 ATR"]
    pros_en = ["Trend + timing from one author's toolkit"]; cons_en = ["Misses first leg"]
    pros_fa = ["روند + تایمینگ از جعبه‌ابزار یک نویسنده"]; cons_fa = ["پای اول را از دست می‌دهد"]

    def run(self, df):
        p = self.p
        up, dn, _ = I2.aroon(df, p["aroon_n"]); cmo = I2.cmo(df.close, p["cmo_n"]); a = ta.atr(df)
        pulled_l = (cmo < p["cmo_pull"]).rolling(3).max().fillna(0).astype(bool)
        pulled_s = (cmo > -p["cmo_pull"]).rolling(3).max().fillna(0).astype(bool)
        long = _first((up > 70) & (dn < 30) & pulled_l & (cmo > cmo.shift(1)) & (cmo > p["cmo_pull"]))
        short = _first((dn > 70) & (up < 30) & pulled_s & (cmo < cmo.shift(1)) & (cmo < -p["cmo_pull"]))
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.0, 4.0)
        return StrategyResult(sig, st, tp, panels={"Aroon": {"Up": up, "Down": dn}, "CMO": {"CMO": cmo}})


class KaufmanKAMA(Strategy):
    id = "kaufman_kama"
    name_en = "Perry Kaufman — KAMA direction + Efficiency-Ratio filter"
    name_fa = "پری کافمن — جهت KAMA + فیلتر نسبت کارایی"
    category = "Masters' Indicators"
    author = "Perry J. Kaufman — 'Smarter Trading' (1995), 'Trading Systems and Methods'"
    difficulty = 2
    timeframes = "1h – 1d"
    params = {"n": 10, "er_min": 0.3, "filter_pct": 0.5}
    description_en = ("Kaufman's own entry: KAMA turns up by more than a filter (0.5 × 20-bar std of KAMA changes) AND Efficiency Ratio > 0.3 "
                     "(market is moving efficiently, not noise). Exit on the opposite turn. The ER filter is the point of the whole system.")
    description_fa = ("ورود خود کافمن: KAMA بیش از یک فیلتر (۰.۵ × انحراف معیار ۲۰ کندل تغییرات KAMA) به بالا برمی‌گردد و نسبت کارایی > ۰.۳ "
                     "(بازار کارآمد حرکت می‌کند، نویز نیست). خروج در برگشت مخالف. فیلتر ER کل هدف سیستم است.")
    rules_en = ["ΔKAMA > +filter (long) / < −filter (short), filter = 0.5·σ20(ΔKAMA)", "ER(10) > 0.3", "Stop 2 ATR, target 5 ATR"]
    rules_fa = ["ΔKAMA > +فیلتر (خرید) / < −فیلتر (فروش)، فیلتر = 0.5·σ20(ΔKAMA)", "ER(10) > ۰.۳", "استاپ 2 ATR، هدف 5 ATR"]
    pros_en = ["Adaptive; silent in chop"]; cons_en = ["Gives back in V-reversals"]
    pros_fa = ["تطبیقی؛ در رنج ساکت"]; cons_fa = ["در برگشت‌های V پس می‌دهد"]

    def run(self, df):
        p = self.p
        k = I2.kama(df.close, p["n"]); er = I2.efficiency_ratio(df.close, p["n"]); a = ta.atr(df)
        dk = k.diff(); filt = p["filter_pct"] * dk.rolling(20).std()
        long = _first((dk > filt) & (er > p["er_min"]))
        short = _first((dk < -filt) & (er > p["er_min"]))
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.0, 5.0)
        return StrategyResult(sig, st, tp, overlays={"KAMA": k}, panels={"Efficiency Ratio": {"ER": er}})


class LambertCCI(Strategy):
    id = "lambert_cci"
    name_en = "Donald Lambert CCI — original ±100 entry/exit (1980)"
    name_fa = "CCI دونالد لمبرت — ورود/خروج اصلی ±۱۰۰ (۱۹۸۰)"
    category = "Masters' Indicators"
    author = "Donald Lambert — Commodities magazine, Oct 1980"
    difficulty = 1
    timeframes = "4h – 1d"
    params = {"n": 20, "lvl": 100}
    description_en = ("Lambert designed CCI as a BREAKOUT tool, not overbought/oversold: go long when CCI crosses ABOVE +100 (cycle expansion), "
                      "exit when it drops back below +100. Short below −100. The 'sell above 100' internet version is the opposite of his intent.")
    description_fa = ("لمبرت CCI را ابزار شکست طراحی کرد نه اشباع: وقتی CCI از +۱۰۰ بالا رفت بخر (انبساط سیکل)، وقتی زیر +۱۰۰ برگشت خارج شو. "
                      "فروش زیر −۱۰۰. نسخهٔ اینترنتی «بالای ۱۰۰ بفروش» دقیقاً خلاف نیت اوست.")
    rules_en = ["Long: CCI(20) crosses above +100; exit: CCI < +100", "Short: CCI crosses below −100; exit: CCI > −100", "Trend filter added: EMA100 slope"]
    rules_fa = ["خرید: CCI(20) از +۱۰۰ بالا برود؛ خروج: CCI < +۱۰۰", "فروش: CCI زیر −۱۰۰ برود؛ خروج: CCI > −۱۰۰", "فیلتر اضافه: شیب EMA100"]
    pros_en = ["Rides momentum expansions"]; cons_en = ["Whipsaws around ±100"]
    pros_fa = ["انبساط مومنتوم را سوار می‌شود"]; cons_fa = ["ویپساو حول ±۱۰۰"]

    def run(self, df):
        p = self.p
        c = ta.cci(df, p["n"]); e = ta.ema(df.close, 100); a = ta.atr(df)
        long = self.cross_up(c, p["lvl"]) & (e > e.shift(5))
        short = self.cross_down(c, -p["lvl"]) & (e < e.shift(5))
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.0, 5.0)
        return StrategyResult(sig, st, tp, overlays={"EMA100": e}, panels={"CCI": {"CCI": c}}, exit_long=(c < p["lvl"]), exit_short=(c > -p["lvl"]))


class WilliamsPercentR(Strategy):
    id = "williams_pctr"
    name_en = "Larry Williams %R — oversold + 5-bar hold rule + trend"
    name_fa = "%R لری ویلیامز — اشباع + قانون نگه‌داری ۵ کندل + روند"
    category = "Masters' Indicators"
    author = "Larry Williams — 'How I Made One Million Dollars…' (1973); %R timing rules"
    difficulty = 1
    timeframes = "1h – 1d"
    params = {"n": 10, "os": -90, "ob": -10}
    description_en = ("Williams' rule: %R(10) reaches below −90 (extreme), then rises back above −90 = buy, but ONLY in the direction of the "
                      "longer trend (close > SMA50). Once entered, ignore %R for 5 bars (his 'hold' rule), then exit when %R > −10 or trend breaks.")
    description_fa = ("قانون ویلیامز: %R(10) زیر −۹۰ می‌رود (اکسترمم)، سپس بالای −۹۰ برمی‌گردد = خرید، فقط در جهت روند بلندتر (بسته > SMA50). "
                      "بعد از ورود، %R را ۵ کندل نادیده بگیر (قانون نگه‌داری او)، سپس وقتی %R > −۱۰ یا روند شکست خارج شو.")
    rules_en = ["Close > SMA50 (long) / < SMA50 (short)", "%R(10) crosses back above −90 (long) / below −10 (short)", "Exit: %R > −10 (long) after ≥ 5 bars", "Stop 2 ATR"]
    rules_fa = ["بسته > SMA50 (خرید) / < SMA50 (فروش)", "%R(10) از −۹۰ بالا برگردد (خرید) / زیر −۱۰ (فروش)", "خروج: %R > −۱۰ بعد از ≥ ۵ کندل", "استاپ 2 ATR"]
    pros_en = ["Fast, simple timing"]; cons_en = ["Needs trend filter (included)"]
    pros_fa = ["تایمینگ سریع و ساده"]; cons_fa = ["فیلتر روند لازم (اضافه شده)"]

    def run(self, df):
        p = self.p
        w = ta.williams_r(df, p["n"]); s50 = ta.sma(df.close, 50); a = ta.atr(df)
        long = self.cross_up(w, p["os"]) & (df.close > s50)
        short = self.cross_down(w, p["ob"]) & (df.close < s50)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.0, 4.0)
        # 5-bar hold: exit rule only valid if no entry within last 5 bars
        recent_entry = (sig != 0).rolling(5).max().fillna(0).astype(bool)
        return StrategyResult(sig, st, tp, overlays={"SMA50": s50}, panels={"%R": {"%R": w}},
                              exit_long=(w > p["ob"]) & ~recent_entry, exit_short=(w < p["os"]) & ~recent_entry)


class PringKST(Strategy):
    id = "pring_kst"
    name_en = "Martin Pring — KST signal cross with long-term KST filter"
    name_fa = "مارتین پرینگ — کراس سیگنال KST با فیلتر KST بلندمدت"
    category = "Masters' Indicators"
    author = "Martin J. Pring — 'Technical Analysis Explained', inventor of KST (Know Sure Thing)"
    difficulty = 2
    timeframes = "4h – 1d"
    params = {}
    description_en = ("Pring's method: the short-term KST crossing its signal line is traded only when the long-term KST (4× periods) "
                      "is above its own signal (primary trend up). Summed ROCs smooth out cycle noise.")
    description_fa = ("روش پرینگ: کراس KST کوتاه‌مدت با خط سیگنالش فقط وقتی معامله می‌شود که KST بلندمدت (۴ برابر دوره) بالای سیگنال خودش باشد (روند اصلی صعودی). مجموع ROCها نویز سیکل را نرم می‌کند.")
    rules_en = ["Long: KST crosses above signal AND long-KST > its signal", "Short: mirror", "Stop 2 ATR, target 4 ATR"]
    rules_fa = ["خرید: KST از سیگنال بالا برود و KST بلند > سیگنالش", "فروش: برعکس", "استاپ 2 ATR، هدف 4 ATR"]
    pros_en = ["Smooth, few whipsaws"]; cons_en = ["Slow"]
    pros_fa = ["نرم، ویپساو کم"]; cons_fa = ["کند"]

    def run(self, df):
        k, s = I2.kst(df.close)
        kl, sl = I2.kst(df.close, 40, 60, 80, 120, 40, 40, 40, 60, 36)
        a = ta.atr(df)
        long = self.cross_up(k, s) & (kl > sl)
        short = self.cross_down(k, s) & (kl < sl)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.0, 4.0)
        return StrategyResult(sig, st, tp, panels={"KST": {"KST": k, "Signal": s}, "Long KST": {"KST-L": kl, "Sig-L": sl}})
