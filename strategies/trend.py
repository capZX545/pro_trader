import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta


class EMACross(Strategy):
    id = "ema_cross"
    name_en = "EMA Crossover (9/21) + 200 EMA Filter"
    name_fa = "کراس EMA (۹/۲۱) با فیلتر EMA ۲۰۰"
    category = "Trend"
    author = "Classic — used by most retail trend traders"
    difficulty = 1
    timeframes = "1h – 1d"
    params = {"fast": 9, "slow": 21, "trend": 200, "sl_atr": 1.5, "tp_atr": 3.0}
    description_en = ("Enter when the fast EMA crosses the slow EMA in the direction of the 200 EMA trend. "
                      "The simplest, most robust trend-following system; loses in choppy markets.")
    description_fa = ("وقتی EMA سریع، EMA کند را در جهت روند EMA ۲۰۰ قطع کند وارد می‌شویم. "
                      "ساده‌ترین و مقاوم‌ترین سیستم روندی؛ در بازار رنج ضرر می‌دهد.")
    rules_en = ["Long: EMA9 crosses above EMA21 AND price > EMA200",
                "Short: EMA9 crosses below EMA21 AND price < EMA200",
                "Stop: 1.5×ATR, Target: 3×ATR (R:R = 1:2)"]
    rules_fa = ["خرید: EMA9 از بالای EMA21 رد شود و قیمت بالای EMA200 باشد",
                "فروش: EMA9 از زیر EMA21 رد شود و قیمت زیر EMA200 باشد",
                "حد ضرر: ۱.۵ برابر ATR، حد سود: ۳ برابر ATR (ریسک به ریوارد ۱:۲)"]
    pros_en = ["Very simple", "Catches big trends", "Works on all markets"]
    cons_en = ["Many false signals in ranges", "Late entries"]
    pros_fa = ["بسیار ساده", "روندهای بزرگ را می‌گیرد", "روی همه بازارها کار می‌کند"]
    cons_fa = ["سیگنال‌های اشتباه زیاد در رنج", "ورود دیرهنگام"]

    def run(self, df):
        p = self.p
        f, s, t = ta.ema(df.close, p["fast"]), ta.ema(df.close, p["slow"]), ta.ema(df.close, p["trend"])
        a = ta.atr(df)
        long = self.cross_up(f, s) & (df.close > t)
        short = self.cross_down(f, s) & (df.close < t)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["tp_atr"])
        return StrategyResult(sig, st, tp, overlays={f"EMA{p['fast']}": f, f"EMA{p['slow']}": s, f"EMA{p['trend']}": t})


class TripleEMA(Strategy):
    id = "triple_ema"
    name_en = "Triple EMA Ribbon (Pullback Entry)"
    name_fa = "سه EMA — ورود در پولبک"
    category = "Trend"
    author = "Popularised by Rayner Teo / Trading Rush"
    difficulty = 2
    timeframes = "15m – 4h"
    params = {"e1": 8, "e2": 21, "e3": 55, "sl_atr": 1.2, "tp_atr": 2.5}
    description_en = ("When EMAs are stacked (8>21>55) the trend is strong. Wait for price to pull back to the 21 EMA and "
                      "resume — a lower-risk entry than a crossover.")
    description_fa = ("وقتی EMAها مرتب شده‌اند (۸>۲۱>۵۵) روند قوی است. منتظر می‌مانیم قیمت به EMA۲۱ پولبک بزند و "
                      "دوباره حرکت کند — ورودی کم‌ریسک‌تر از کراس.")
    rules_en = ["Trend up: EMA8 > EMA21 > EMA55", "Long: previous candle low touches EMA21, current candle closes above EMA8",
                "Mirror for shorts"]
    rules_fa = ["روند صعودی: EMA8 > EMA21 > EMA55", "خرید: کندل قبل EMA21 را لمس کند و کندل فعلی بالای EMA8 بسته شود",
                "برعکس برای فروش"]
    pros_en = ["Better entry price than crossovers", "Clear trend filter"]
    cons_en = ["Misses moves without pullbacks"]
    pros_fa = ["قیمت ورود بهتر از کراس", "فیلتر روند واضح"]
    cons_fa = ["حرکاتی که پولبک ندارند را از دست می‌دهد"]

    def run(self, df):
        p = self.p
        e1, e2, e3 = ta.ema(df.close, p["e1"]), ta.ema(df.close, p["e2"]), ta.ema(df.close, p["e3"])
        a = ta.atr(df)
        up = (e1 > e2) & (e2 > e3)
        dn = (e1 < e2) & (e2 < e3)
        long = up & (df.low.shift(1) <= e2.shift(1)) & (df.close > e1) & (df.close > df.open)
        short = dn & (df.high.shift(1) >= e2.shift(1)) & (df.close < e1) & (df.close < df.open)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["tp_atr"])
        return StrategyResult(sig, st, tp, overlays={"EMA8": e1, "EMA21": e2, "EMA55": e3})


class GoldenCross(Strategy):
    id = "golden_cross"
    name_en = "Golden / Death Cross (50/200 SMA)"
    name_fa = "کراس طلایی / مرگ (SMA ۵۰/۲۰۰)"
    category = "Trend"
    author = "Classic institutional signal"
    difficulty = 1
    timeframes = "1d – 1wk"
    params = {"fast": 50, "slow": 200}
    description_en = "Long-term regime signal watched by funds worldwide. Very few trades, large moves."
    description_fa = "سیگنال بلندمدت که صندوق‌های سراسر دنیا دنبال می‌کنند. تعداد معامله کم، حرکات بزرگ."
    rules_en = ["Golden cross: SMA50 crosses above SMA200 → long", "Death cross: SMA50 crosses below SMA200 → exit/short"]
    rules_fa = ["کراس طلایی: SMA50 از بالای SMA200 رد شود → خرید", "کراس مرگ: SMA50 از زیر SMA200 رد شود → خروج/فروش"]
    pros_en = ["Extremely reliable long-term", "Low noise"]
    cons_en = ["Very late", "Only a handful of trades per decade"]
    pros_fa = ["در بلندمدت بسیار قابل اعتماد", "نویز کم"]
    cons_fa = ["خیلی دیر", "تنها چند معامله در دهه"]

    def run(self, df):
        f, s = ta.sma(df.close, self.p["fast"]), ta.sma(df.close, self.p["slow"])
        sig = self.make_signal(self.cross_up(f, s), self.cross_down(f, s))
        return StrategyResult(sig, overlays={"SMA50": f, "SMA200": s})


class SupertrendStrat(Strategy):
    id = "supertrend"
    name_en = "Supertrend + ADX Filter"
    name_fa = "سوپرترند با فیلتر ADX"
    category = "Trend"
    author = "Olivier Seban (Supertrend), Welles Wilder (ADX)"
    difficulty = 2
    timeframes = "15m – 1d"
    params = {"period": 10, "mult": 3.0, "adx_min": 20}
    description_en = "Supertrend flips give entries; ADX>20 ensures a trend actually exists. Trail stop on the Supertrend line."
    description_fa = "تغییر جهت سوپرترند سیگنال ورود است؛ ADX>۲۰ تضمین می‌کند روند واقعی وجود دارد. حد ضرر روی خط سوپرترند تریل می‌شود."
    rules_en = ["Long: Supertrend flips bullish and ADX > 20", "Short: flips bearish and ADX > 20", "Stop = Supertrend line"]
    rules_fa = ["خرید: سوپرترند صعودی شود و ADX > ۲۰", "فروش: نزولی شود و ADX > ۲۰", "حد ضرر = خط سوپرترند"]
    pros_en = ["Built-in trailing stop", "Visual and clear"]
    cons_en = ["Whipsaws when ATR expands suddenly"]
    pros_fa = ["حد ضرر تریلینگ داخلی", "بصری و واضح"]
    cons_fa = ["در انبساط ناگهانی ATR اره می‌شود"]

    def run(self, df):
        st, d = ta.supertrend(df, self.p["period"], self.p["mult"])
        adx, _, _ = ta.adx(df)
        a = ta.atr(df)
        long = (d == 1) & (d.shift(1) == -1) & (adx > self.p["adx_min"])
        short = (d == -1) & (d.shift(1) == 1) & (adx > self.p["adx_min"])
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        stop[sig != 0] = st[sig != 0]
        tgt = pd.Series(np.nan, index=df.index)
        tgt[sig == 1] = df.close[sig == 1] + 3 * a[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 3 * a[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"Supertrend": st}, panels={"ADX": {"ADX": adx}})


class IchimokuStrat(Strategy):
    id = "ichimoku"
    name_en = "Ichimoku Kinko Hyo (Full System)"
    name_fa = "ایچیموکو (سیستم کامل)"
    category = "Trend"
    author = "Goichi Hosoda (Japan, 1960s)"
    difficulty = 3
    timeframes = "4h – 1wk"
    params = {"tenkan": 9, "kijun": 26, "senkou": 52}
    description_en = ("A complete system: TK cross + price above cloud + cloud bullish + lagging span free. "
                      "All conditions aligned = high probability trend trade.")
    description_fa = ("سیستم کامل: کراس تنکان/کیجون + قیمت بالای ابر + ابر صعودی + چیکو اسپن آزاد. "
                      "هم‌راستایی همه شرایط = معامله روندی با احتمال بالا.")
    rules_en = ["Long: Tenkan crosses above Kijun, price above cloud, Span A > Span B",
                "Short: mirror", "Stop below Kijun-sen"]
    rules_fa = ["خرید: تنکان از بالای کیجون رد شود، قیمت بالای ابر، اسپن A > اسپن B",
                "فروش: برعکس", "حد ضرر زیر کیجون‌سن"]
    pros_en = ["Trend, momentum, S/R in one tool", "Strong filter"]
    cons_en = ["Slow", "Useless in ranges"]
    pros_fa = ["روند، مومنتوم و حمایت/مقاومت در یک ابزار", "فیلتر قوی"]
    cons_fa = ["کند", "در رنج بی‌فایده"]

    def run(self, df):
        p = self.p
        t, k, sa, sb, lag = ta.ichimoku(df, p["tenkan"], p["kijun"], p["senkou"])
        a = ta.atr(df)
        cloud_top = pd.concat([sa, sb], axis=1).max(axis=1)
        cloud_bot = pd.concat([sa, sb], axis=1).min(axis=1)
        long = self.cross_up(t, k) & (df.close > cloud_top) & (sa > sb)
        short = self.cross_down(t, k) & (df.close < cloud_bot) & (sa < sb)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = k[sig == 1] - 0.5 * a[sig == 1]
        stop[sig == -1] = k[sig == -1] + 0.5 * a[sig == -1]
        tgt = pd.Series(np.nan, index=df.index)
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"Tenkan": t, "Kijun": k, "Senkou A": sa, "Senkou B": sb})


class ParabolicSARStrat(Strategy):
    id = "psar"
    name_en = "Parabolic SAR + EMA Trend"
    name_fa = "پارابولیک SAR با روند EMA"
    category = "Trend"
    author = "J. Welles Wilder"
    difficulty = 1
    timeframes = "1h – 1d"
    params = {"af": 0.02, "af_max": 0.2, "ema": 100}
    description_en = "SAR dots flip = entry, but only in direction of EMA100. Stop trails on SAR."
    description_fa = "تغییر نقاط SAR = ورود، ولی فقط در جهت EMA۱۰۰. حد ضرر روی SAR تریل می‌شود."
    rules_en = ["Long: SAR flips below price and price > EMA100", "Short: SAR flips above and price < EMA100"]
    rules_fa = ["خرید: SAR زیر قیمت برود و قیمت بالای EMA100", "فروش: SAR بالای قیمت برود و قیمت زیر EMA100"]
    pros_en = ["Automatic trailing stop"]
    cons_en = ["Terrible in sideways markets"]
    pros_fa = ["حد ضرر تریلینگ خودکار"]
    cons_fa = ["در بازار خنثی افتضاح"]

    def run(self, df):
        sar = ta.parabolic_sar(df, self.p["af"], self.p["af_max"])
        e = ta.ema(df.close, self.p["ema"])
        a = ta.atr(df)
        below = sar < df.close
        long = below & ~below.shift(1).fillna(False).astype(bool) & (df.close > e)
        short = ~below & below.shift(1).fillna(False).astype(bool) & (df.close < e)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        stop[sig != 0] = sar[sig != 0]
        tgt = pd.Series(np.nan, index=df.index)
        tgt[sig == 1] = df.close[sig == 1] + 3 * a[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 3 * a[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"PSAR": sar, "EMA100": e})


class TurtleBreakout(Strategy):
    id = "turtle"
    name_en = "Turtle Trading (Donchian Breakout)"
    name_fa = "سیستم لاک‌پشت‌ها (شکست دانچیان)"
    category = "Trend"
    author = "Richard Dennis & William Eckhardt (1983)"
    difficulty = 2
    timeframes = "4h – 1d"
    params = {"entry": 20, "exit": 10, "atr_stop": 2.0}
    description_en = ("The legendary experiment that turned novices into millionaires. Buy 20-day highs, sell 20-day lows, "
                      "exit on 10-day opposite extreme, 2N stop. Pure trend following.")
    description_fa = ("آزمایش افسانه‌ای که تازه‌کارها را میلیونر کرد. خرید در سقف ۲۰ روزه، فروش در کف ۲۰ روزه، "
                      "خروج در اکسترمم مخالف ۱۰ روزه، حد ضرر 2N. روندگیری خالص.")
    rules_en = ["Long: close > highest high of last 20 bars", "Short: close < lowest low of last 20 bars",
                "Stop: 2×ATR(20)", "Position size: 1% risk per N"]
    rules_fa = ["خرید: بسته شدن بالای بالاترین سقف ۲۰ کندل", "فروش: بسته شدن زیر پایین‌ترین کف ۲۰ کندل",
                "حد ضرر: ۲ برابر ATR(20)", "سایز پوزیشن: ۱٪ ریسک به ازای هر N"]
    pros_en = ["Proven for 40 years", "Mechanical, no discretion"]
    cons_en = ["Win rate ~35-40%", "Big drawdowns"]
    pros_fa = ["۴۰ سال اثبات شده", "مکانیکی، بدون نظر شخصی"]
    cons_fa = ["وین‌ریت ۳۵-۴۰٪", "دراودان بزرگ"]

    def run(self, df):
        p = self.p
        hh, ll = ta.donchian(df, p["entry"])
        a = ta.atr(df, 20)
        long = df.close > hh.shift(1)
        short = df.close < ll.shift(1)
        # only signal on first breakout
        long = long & ~long.shift(1).fillna(False).astype(bool)
        short = short & ~short.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["atr_stop"], p["atr_stop"] * 2.5)
        return StrategyResult(sig, st, tp, overlays={"Donchian High": hh.shift(1), "Donchian Low": ll.shift(1)})


class MACDTrend(Strategy):
    id = "macd_trend"
    name_en = "MACD Zero-Line + Signal Cross"
    name_fa = "MACD — کراس سیگنال بالای/زیر خط صفر"
    category = "Momentum"
    author = "Gerald Appel"
    difficulty = 1
    timeframes = "1h – 1d"
    params = {"fast": 12, "slow": 26, "signal": 9, "ema": 200}
    description_en = "Only take MACD signal crosses on the correct side of zero and in direction of 200 EMA — filters most noise."
    description_fa = "فقط کراس‌های MACD را در سمت درست خط صفر و در جهت EMA۲۰۰ می‌گیریم — بیشتر نویز را حذف می‌کند."
    rules_en = ["Long: MACD crosses above signal while MACD < 0 (early) and price > EMA200",
                "Short: MACD crosses below signal while MACD > 0 and price < EMA200"]
    rules_fa = ["خرید: MACD از بالای سیگنال رد شود در حالی که MACD < 0 و قیمت بالای EMA200",
                "فروش: MACD از زیر سیگنال رد شود در حالی که MACD > 0 و قیمت زیر EMA200"]
    pros_en = ["Catches pullback resumptions"]
    cons_en = ["Lagging"]
    pros_fa = ["ادامه‌ی روند بعد از پولبک را می‌گیرد"]
    cons_fa = ["تأخیری"]

    def run(self, df):
        p = self.p
        m, s, h = ta.macd(df.close, p["fast"], p["slow"], p["signal"])
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df)
        long = self.cross_up(m, s) & (m < 0) & (df.close > e)
        short = self.cross_down(m, s) & (m > 0) & (df.close < e)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 1.5, 3.0)
        return StrategyResult(sig, st, tp, overlays={"EMA200": e}, panels={"MACD": {"MACD": m, "Signal": s, "Hist": h}})


class ADXTrend(Strategy):
    id = "adx_dmi"
    name_en = "ADX + DMI Crossover"
    name_fa = "ADX با کراس DMI"
    category = "Trend"
    author = "J. Welles Wilder"
    difficulty = 2
    timeframes = "1h – 1d"
    params = {"n": 14, "adx_min": 25}
    description_en = "+DI/-DI cross while ADX rising above 25 = fresh strong trend."
    description_fa = "کراس +DI/-DI وقتی ADX بالای ۲۵ و در حال افزایش = روند قوی تازه."
    rules_en = ["Long: +DI crosses above -DI, ADX > 25 and rising", "Short: -DI crosses above +DI, ADX > 25 and rising"]
    rules_fa = ["خرید: +DI از بالای -DI رد شود، ADX > ۲۵ و صعودی", "فروش: -DI از بالای +DI رد شود، ADX > ۲۵ و صعودی"]
    pros_en = ["Measures trend strength objectively"]
    cons_en = ["Lags at trend starts"]
    pros_fa = ["قدرت روند را عینی می‌سنجد"]
    cons_fa = ["در شروع روند تأخیر دارد"]

    def run(self, df):
        adx, pdi, mdi = ta.adx(df, self.p["n"])
        a = ta.atr(df)
        strong = (adx > self.p["adx_min"]) & (adx > adx.shift(1))
        sig = self.make_signal(self.cross_up(pdi, mdi) & strong, self.cross_up(mdi, pdi) & strong)
        st, tp = self.atr_stops(df, sig, a, 2.0, 4.0)
        return StrategyResult(sig, st, tp, panels={"ADX/DMI": {"ADX": adx, "+DI": pdi, "-DI": mdi}})


class HullMA(Strategy):
    id = "hull"
    name_en = "Hull Moving Average Turn"
    name_fa = "تغییر جهت میانگین هال (HMA)"
    category = "Trend"
    author = "Alan Hull"
    difficulty = 1
    timeframes = "15m – 4h"
    params = {"n": 55}
    description_en = "HMA has almost no lag. Enter when its slope flips direction."
    description_fa = "HMA تقریباً تأخیر ندارد. وقتی شیب آن تغییر جهت داد وارد می‌شویم."
    rules_en = ["Long: HMA turns up (HMA > HMA[1] after HMA[1] < HMA[2])", "Short: mirror"]
    rules_fa = ["خرید: HMA رو به بالا برگردد", "فروش: برعکس"]
    pros_en = ["Fast, smooth"]
    cons_en = ["Overshoots, many flips in chop"]
    pros_fa = ["سریع و نرم"]
    cons_fa = ["اورشوت می‌کند، در رنج زیاد برمی‌گردد"]

    def run(self, df):
        h = ta.hma(df.close, self.p["n"])
        a = ta.atr(df)
        up = h > h.shift(1)
        long = up & ~up.shift(1).fillna(False).astype(bool)
        short = ~up & up.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 1.5, 3.0)
        return StrategyResult(sig, st, tp, overlays={"HMA": h})
