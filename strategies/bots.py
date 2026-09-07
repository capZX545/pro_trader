"""
Strategies ported from the most-used open-source trading bots & top community scripts (2026 research pass).
Sources studied (rules re-implemented, then re-tested in our engine):
  • freqtrade/freqtrade-strategies (berlinguyinca): BinHV45, ClucMay72018, BbandRsi, ADXMomentum, MACD_crossed, Quickie
  • paulcpk/freqtrade-strategies-that-work (2y backtest 2018-2020, 8 pairs): EMA800 price cross (+118%),
    Double-EMA with trend (+122%), RSI directional slow (+33%)
  • NostalgiaForInfinity (core idea: multi-condition dip-buy with EMA/BB/RSI/volume protections)
  • TradingView community: WaveTrend (LazyBear), Elder Impulse System, Chandelier Exit, Choppiness-Index regime lock
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta


def choppiness(df, n=14):
    tr = ta.true_range(df)
    atr_sum = tr.rolling(n).sum()
    rng = (df.high.rolling(n).max() - df.low.rolling(n).min()).replace(0, np.nan)
    return 100 * np.log10(atr_sum / rng) / np.log10(n)


def wavetrend(df, n1=10, n2=21):
    ap = (df.high + df.low + df.close) / 3
    esa = ta.ema(ap, n1)
    d = ta.ema((ap - esa).abs(), n1)
    ci = (ap - esa) / (0.015 * d.replace(0, np.nan))
    wt1 = ta.ema(ci, n2)
    wt2 = ta.sma(wt1, 4)
    return wt1, wt2


class FT_EMA800Cross(Strategy):
    id = "ft_ema800"
    name_en = "Bot: EMA-800 Price Cross (freqtrade, +118% 2y)"
    name_fa = "بات: کراس قیمت با EMA۸۰۰ (freqtrade، +۱۱۸٪ در ۲ سال)"
    category = "Bot-Ported"
    author = "paulcpk / freqtrade-strategies-that-work — 1h, 8 pairs, 2018–2020"
    difficulty = 1
    timeframes = "1h"
    params = {"ema": 800, "exit_threshold_pct": 1.0, "sl_atr": 3.0, "tp_atr": 8.0}
    description_en = ("Simplest bot strategy that survived a 2-year multi-pair backtest: buy when price crosses above a very "
                      "long EMA (800 × 1h ≈ 33 days), exit when it closes 1% below it. Few trades, rides big trends.")
    description_fa = ("ساده‌ترین استراتژی باتی که از بک‌تست ۲ ساله چندجفتی جان سالم به در برد: وقتی قیمت بالای EMA خیلی بلند "
                      "(۸۰۰×۱h ≈ ۳۳ روز) رفت بخر، وقتی ۱٪ زیر آن بسته شد خارج شو. معاملات کم، روندهای بزرگ را سوار می‌شود.")
    rules_en = ["Long: close crosses above EMA800", "Exit: close crosses below EMA800×0.99 (or trailing/target)", "Original stop: -15%"]
    rules_fa = ["خرید: قیمت از بالای EMA800 رد شود", "خروج: قیمت زیر EMA800×۰.۹۹ بسته شود (یا تریلینگ/هدف)", "حد ضرر اصلی: -۱۵٪"]
    pros_en = ["Extremely robust, low frequency"]
    cons_en = ["Long-only, wide stop", "Needs long history (800 bars)"]
    pros_fa = ["بسیار مقاوم، فرکانس کم"]
    cons_fa = ["فقط خرید، حد ضرر بزرگ", "به تاریخچه بلند نیاز دارد (۸۰۰ کندل)"]

    def run(self, df):
        p = self.p
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df)
        long = self.cross_up(df.close, e)
        short = self.cross_down(df.close, e * (1 - p["exit_threshold_pct"] / 100))
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["tp_atr"])
        return StrategyResult(sig, st, tp, overlays={"EMA800": e})


class FT_DoubleEMATrend(Strategy):
    id = "ft_double_ema"
    name_en = "Bot: Double EMA 9/21 + low>EMA200 (freqtrade, +122% 2y)"
    name_fa = "بات: EMA دوگانه ۹/۲۱ + کف بالای EMA۲۰۰ (freqtrade، +۱۲۲٪)"
    category = "Bot-Ported"
    author = "paulcpk (inspired by Trading Rush) — 1h, 2018–2020"
    difficulty = 1
    timeframes = "1h – 4h"
    params = {"fast": 9, "slow": 21, "trend": 200, "sl_atr": 2.0, "tp_atr": 5.0}
    description_en = ("Stricter version of the EMA crossover: the whole candle (its LOW) must be above EMA200, and exit as soon "
                      "as the low dips below EMA200 or EMAs cross back. Bot-tested best performer of its repo.")
    description_fa = ("نسخه سخت‌گیرانه‌تر کراس EMA: کل کندل (کفش) باید بالای EMA۲۰۰ باشد، و به‌محض اینکه کف زیر EMA۲۰۰ رفت "
                      "یا EMAها برگشتند خارج شو. بهترین عملکرد ریپوی خودش در تست بات.")
    rules_en = ["Long: EMA9 crosses above EMA21 AND candle low > EMA200", "Exit: EMA9 crosses below EMA21 OR low < EMA200"]
    rules_fa = ["خرید: EMA9 از بالای EMA21 رد شود و کف کندل > EMA200", "خروج: EMA9 زیر EMA21 برود یا کف < EMA200"]
    pros_en = ["Cleaner than plain crossover", "Fast exit protects capital"]
    cons_en = ["Chop losses", "Long-only original"]
    pros_fa = ["تمیزتر از کراس ساده", "خروج سریع سرمایه را حفظ می‌کند"]
    cons_fa = ["ضرر در رنج", "نسخه اصلی فقط خرید"]

    def run(self, df):
        p = self.p
        f, s, t = ta.ema(df.close, p["fast"]), ta.ema(df.close, p["slow"]), ta.ema(df.close, p["trend"])
        a = ta.atr(df)
        long = self.cross_up(f, s) & (df.low > t)
        short = self.cross_down(f, s) & (df.high < t)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, p["sl_atr"], p["tp_atr"])
        return StrategyResult(sig, st, tp, overlays={"EMA9": f, "EMA21": s, "EMA200": t})


class FT_RSIDirectional(Strategy):
    id = "ft_rsi_dir"
    name_en = "Bot: RSI(10) cross 25 above EMA600 (freqtrade)"
    name_fa = "بات: کراس RSI(10) از ۲۵ بالای EMA۶۰۰ (freqtrade)"
    category = "Bot-Ported"
    author = "paulcpk — RSIDirectionalWithTrendSlow"
    difficulty = 1
    timeframes = "1h"
    params = {"rsi_n": 10, "level": 25, "ema": 600}
    description_en = "Deep short-term oversold (RSI10 back above 25) while the candle low stays above the 600 EMA long-term trend."
    description_fa = "اشباع فروش کوتاه‌مدت عمیق (RSI10 دوباره بالای ۲۵) در حالی که کف کندل بالای روند بلندمدت EMA۶۰۰ می‌ماند."
    rules_en = ["Long: RSI(10) crosses above 25 AND low > EMA600", "Exit: RSI(10) < 20 OR low < EMA600"]
    rules_fa = ["خرید: RSI(10) از ۲۵ بالا برود و کف > EMA600", "خروج: RSI(10) < ۲۰ یا کف < EMA600"]
    pros_en = ["Buys real dips in bull trends"]
    cons_en = ["Rare signals"]
    pros_fa = ["دیپ‌های واقعی در روند صعودی را می‌خرد"]
    cons_fa = ["سیگنال کم"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, p["rsi_n"])
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df)
        long = self.cross_up(r, p["level"]) & (df.low > e)
        short = self.cross_down(r, 100 - p["level"]) & (df.high < e)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.5, 5.0)
        return StrategyResult(sig, st, tp, overlays={"EMA600": e}, panels={"RSI10": {"RSI": r}})


class BinHV45(Strategy):
    id = "binhv45"
    name_en = "Bot: BinHV45 (Bollinger dip-buy, freqtrade classic)"
    name_fa = "بات: BinHV45 (خرید دیپ بولینگر، کلاسیک freqtrade)"
    category = "Bot-Ported"
    author = "freqtrade-strategies / berlinguyinca (originally 1m–5m)"
    difficulty = 3
    timeframes = "5m – 1h"
    params = {"bb_n": 40, "bbdelta": 0.008, "closedelta": 0.0175, "tail": 0.25, "ema_filter": 200}
    description_en = ("One of the most-copied freqtrade strategies. Buys a sharp down-candle that closes below the previous "
                      "lower Bollinger band (40) with a tiny lower tail (no bounce yet) when bands are wide enough. Exit at middle band.")
    description_fa = ("یکی از پرکپی‌ترین استراتژی‌های freqtrade. کندل نزولی تندی که زیر باند پایین بولینگر (۴۰) قبلی بسته می‌شود "
                      "با سایه پایین خیلی کوچک (هنوز برگشت نکرده) وقتی باندها به‌اندازه کافی باز هستند را می‌خرد. خروج در باند میانی.")
    rules_en = ["(mid − lower) > 0.8% of close (bands wide)", "|close − prev close| > 1.75% (sharp move)",
                "(close − low) < 25% of band delta (small tail)", "close < previous lower band AND close ≤ previous close",
                "Filter added: price > EMA200 (not in original). Target: mid band"]
    rules_fa = ["(میانی − پایین) > ۰.۸٪ قیمت (باند باز)", "|بسته − بسته قبلی| > ۱.۷۵٪ (حرکت تند)",
                "(بسته − کف) < ۲۵٪ فاصله باند (سایه کوچک)", "بسته < باند پایین قبلی و بسته ≤ بسته قبلی",
                "فیلتر اضافه: قیمت > EMA200 (در اصل نبود). هدف: باند میانی"]
    pros_en = ["High win rate in normal markets"]
    cons_en = ["Catastrophic in crashes without trend filter (that's why we add EMA200)"]
    pros_fa = ["وین‌ریت بالا در بازار عادی"]
    cons_fa = ["در سقوط‌ها بدون فیلتر روند فاجعه (به همین دلیل EMA200 اضافه کردیم)"]

    def run(self, df):
        p = self.p
        mid = ta.sma(df.close, p["bb_n"])
        lower = mid - 2 * df.close.rolling(p["bb_n"]).std(ddof=0)
        bbdelta = (mid - lower).abs()
        closedelta = (df.close - df.close.shift(1)).abs()
        tail = (df.close - df.low).abs()
        e = ta.ema(df.close, p["ema_filter"])
        a = ta.atr(df)
        long = ((lower.shift(1) > 0) & (bbdelta > df.close * p["bbdelta"]) & (closedelta > df.close * p["closedelta"])
                & (tail < bbdelta * p["tail"]) & (df.close < lower.shift(1)) & (df.close <= df.close.shift(1)) & (df.close > e * 0.97))
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.close[sig == 1] - 2.0 * a[sig == 1]
        tgt[sig == 1] = mid[sig == 1]
        return StrategyResult(sig, stop, tgt, overlays={"BB Mid(40)": mid, "BB Low(40)": lower, "EMA200": e})


class ClucMay(Strategy):
    id = "clucmay"
    name_en = "Bot: ClucMay72018 (deep BB dip + volume sanity)"
    name_fa = "بات: ClucMay72018 (دیپ عمیق بولینگر + کنترل حجم)"
    category = "Bot-Ported"
    author = "freqtrade-strategies (Cluc, May 2018)"
    difficulty = 2
    timeframes = "5m – 1h"
    params = {"bb_n": 20, "depth": 0.985, "ema": 50, "vol_mult": 20}
    description_en = "Buy when close < 98.5% of the lower Bollinger band while below EMA50 (panic dip), exit at middle band. Volume must not be a 20× spike."
    description_fa = "وقتی بسته < ۹۸.۵٪ باند پایین بولینگر و زیر EMA50 (دیپ وحشت) بخر، خروج در باند میانی. حجم نباید جهش ۲۰ برابری باشد."
    rules_en = ["close < EMA50", "close < 0.985 × BB lower(20, typical price)", "volume < 20 × 30-bar mean", "Exit: close > BB mid"]
    rules_fa = ["بسته < EMA50", "بسته < ۰.۹۸۵ × باند پایین (۲۰، قیمت تیپیکال)", "حجم < ۲۰ × میانگین ۳۰ کندل", "خروج: بسته > باند میانی"]
    pros_en = ["Catches capitulation wicks"]
    cons_en = ["Knife-catching; needs hard stop"]
    pros_fa = ["سایه‌های تسلیم را می‌گیرد"]
    cons_fa = ["چاقوگیری؛ حد ضرر سخت لازم"]

    def run(self, df):
        p = self.p
        tp_ = (df.high + df.low + df.close) / 3
        mid = ta.sma(tp_, p["bb_n"])
        lower = mid - 2 * tp_.rolling(p["bb_n"]).std(ddof=0)
        e = ta.ema(df.close, p["ema"])
        vm = df.volume.rolling(30).mean().shift(1)
        a = ta.atr(df)
        vol_ok = (df.volume < vm * p["vol_mult"]) | (df.volume.sum() == 0)
        long = (df.close < e) & (df.close < p["depth"] * lower) & vol_ok
        long = long & ~long.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.close[sig == 1] - 2.0 * a[sig == 1]
        tgt[sig == 1] = mid[sig == 1]
        return StrategyResult(sig, stop, tgt, overlays={"BB Mid": mid, "BB Low": lower, "EMA50": e})


class BbandRsiBot(Strategy):
    id = "bband_rsi_bot"
    name_en = "Bot: BbandRsi (RSI<30 + close<BB lower)"
    name_fa = "بات: BbandRsi (RSI<۳۰ + بسته زیر باند پایین)"
    category = "Bot-Ported"
    author = "freqtrade-strategies — flagged 'promising' in community backtests"
    difficulty = 1
    timeframes = "1h"
    params = {"rsi_n": 14, "rsi_buy": 30, "rsi_exit": 70, "bb_n": 20}
    description_en = "Double oversold confirmation: RSI<30 AND close below the lower band. Exit when RSI>70 or upper band."
    description_fa = "تأیید دوگانه اشباع فروش: RSI<۳۰ و بسته زیر باند پایین. خروج وقتی RSI>۷۰ یا باند بالا."
    rules_en = ["Long: RSI(14) < 30 and close < BB lower(20,2)", "Short (added): RSI > 70 and close > BB upper", "Target: opposite band"]
    rules_fa = ["خرید: RSI(14) < ۳۰ و بسته < باند پایین", "فروش (اضافه): RSI > ۷۰ و بسته > باند بالا", "هدف: باند مقابل"]
    pros_en = ["Two independent confirmations"]
    cons_en = ["Trend days hurt"]
    pros_fa = ["دو تأیید مستقل"]
    cons_fa = ["روزهای رونددار ضرر می‌زند"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, p["rsi_n"])
        tp_ = (df.high + df.low + df.close) / 3
        u, m, l = ta.bollinger(tp_, p["bb_n"], 2.0)
        a = ta.atr(df)
        long = (r < p["rsi_buy"]) & (df.close < l)
        short = (r > p["rsi_exit"]) & (df.close > u)
        long = long & ~long.shift(1).fillna(False).astype(bool)
        short = short & ~short.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.close[sig == 1] - 2.0 * a[sig == 1]
        stop[sig == -1] = df.close[sig == -1] + 2.0 * a[sig == -1]
        tgt[sig == 1] = m[sig == 1]
        tgt[sig == -1] = m[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"BB Up": u, "BB Mid": m, "BB Low": l}, panels={"RSI": {"RSI": r}})


class ADXMomentumBot(Strategy):
    id = "adx_momentum_bot"
    name_en = "Bot: ADX Momentum (ADX>25, +DI>25, MOM>0)"
    name_fa = "بات: مومنتوم ADX (ADX>۲۵، +DI>۲۵، MOM>۰)"
    category = "Bot-Ported"
    author = "freqtrade-strategies — ADXMomentum"
    difficulty = 1
    timeframes = "1h – 4h"
    params = {"adx_n": 14, "di_n": 25, "mom_n": 14, "level": 25}
    description_en = "Trend + momentum agreement: ADX>25, +DI(25)>25 and above −DI, 14-bar momentum positive. Mirror for shorts."
    description_fa = "توافق روند + مومنتوم: ADX>۲۵، +DI(25)>۲۵ و بالای −DI، مومنتوم ۱۴ کندل مثبت. برعکس برای فروش."
    rules_en = ["Long: ADX>25 & +DI>25 & +DI>−DI & MOM(14)>0 (first bar true)", "Short: mirror"]
    rules_fa = ["خرید: ADX>۲۵ و +DI>۲۵ و +DI>−DI و MOM(14)>۰ (اولین کندل)", "فروش: برعکس"]
    pros_en = ["Only trades when trend is measurable"]
    cons_en = ["Late"]
    pros_fa = ["فقط وقتی روند قابل‌اندازه‌گیری است"]
    cons_fa = ["دیر"]

    def run(self, df):
        p = self.p
        adx, _, _ = ta.adx(df, p["adx_n"])
        _, pdi, mdi = ta.adx(df, p["di_n"])
        mom = ta.momentum(df.close, p["mom_n"])
        a = ta.atr(df)
        lc = (adx > p["level"]) & (mom > 0) & (pdi > p["level"]) & (pdi > mdi)
        sc = (adx > p["level"]) & (mom < 0) & (mdi > p["level"]) & (pdi < mdi)
        long = lc & ~lc.shift(1).fillna(False).astype(bool)
        short = sc & ~sc.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.0, 4.0)
        return StrategyResult(sig, st, tp, panels={"ADX/DI": {"ADX": adx, "+DI": pdi, "-DI": mdi}})


class MACDCCIBot(Strategy):
    id = "macd_cci_bot"
    name_en = "Bot: MACD cross + CCI filter"
    name_fa = "بات: کراس MACD با فیلتر CCI"
    category = "Bot-Ported"
    author = "freqtrade-strategies — MACDStrategy_crossed"
    difficulty = 1
    timeframes = "15m – 1h"
    params = {"cci_buy": -50, "cci_sell": 100}
    description_en = "MACD signal cross taken only when CCI confirms it happened from an oversold (≤−50) / overbought (≥100) state."
    description_fa = "کراس سیگنال MACD فقط وقتی CCI تأیید کند از حالت اشباع فروش (≤−۵۰) / اشباع خرید (≥۱۰۰) رخ داده."
    rules_en = ["Long: MACD crosses above signal AND CCI ≤ −50", "Short: MACD crosses below signal AND CCI ≥ 100"]
    rules_fa = ["خرید: MACD از بالای سیگنال رد شود و CCI ≤ −۵۰", "فروش: MACD زیر سیگنال برود و CCI ≥ ۱۰۰"]
    pros_en = ["Filters mid-range MACD noise"]
    cons_en = ["Still lagging"]
    pros_fa = ["نویز MACD وسط رنج را فیلتر می‌کند"]
    cons_fa = ["همچنان تأخیری"]

    def run(self, df):
        p = self.p
        m, s, h = ta.macd(df.close)
        c = ta.cci(df, 20)
        a = ta.atr(df)
        long = self.cross_up(m, s) & (c <= p["cci_buy"])
        short = self.cross_down(m, s) & (c >= p["cci_sell"])
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 1.5, 3.0)
        return StrategyResult(sig, st, tp, panels={"MACD": {"MACD": m, "Signal": s, "Hist": h}, "CCI": {"CCI": c}})


class WaveTrendStrat(Strategy):
    id = "wavetrend"
    name_en = "WaveTrend Oscillator (LazyBear) cross in OS/OB"
    name_fa = "اسیلاتور ویوترند (LazyBear) — کراس در اشباع"
    category = "Momentum"
    author = "LazyBear — one of the most-used TradingView scripts (#1 freqst weekly: WaveTrendStra)"
    difficulty = 2
    timeframes = "15m – 4h"
    params = {"n1": 10, "n2": 21, "os": -60, "ob": 60, "ema": 200}
    description_en = ("Smoothed CCI-like oscillator. Buy when WT1 crosses above WT2 below −60 in an uptrend; sell when it crosses "
                      "below WT2 above +60 in a downtrend. Loved by crypto bots for its clean signals.")
    description_fa = ("اسیلاتور نرم‌شده شبیه CCI. وقتی WT1 زیر −۶۰ از بالای WT2 رد شد در روند صعودی بخر؛ وقتی بالای +۶۰ زیر WT2 رفت "
                      "در روند نزولی بفروش. بات‌های کریپتو به‌خاطر سیگنال‌های تمیزش دوستش دارند.")
    rules_en = ["Long: WT1 crosses above WT2, WT1 < −60, price > EMA200", "Short: mirror above +60, price < EMA200"]
    rules_fa = ["خرید: WT1 از بالای WT2 رد شود، WT1 < −۶۰، قیمت > EMA200", "فروش: برعکس بالای +۶۰، قیمت < EMA200"]
    pros_en = ["Clear, smooth", "Good divergence tool"]
    cons_en = ["Extremes can persist"]
    pros_fa = ["واضح و نرم", "ابزار واگرایی خوب"]
    cons_fa = ["اکسترمم‌ها می‌توانند ادامه یابند"]

    def run(self, df):
        p = self.p
        wt1, wt2 = wavetrend(df, p["n1"], p["n2"])
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df)
        long = self.cross_up(wt1, wt2) & (wt1 < p["os"]) & (df.close > e)
        short = self.cross_down(wt1, wt2) & (wt1 > p["ob"]) & (df.close < e)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 1.5, 3.0)
        return StrategyResult(sig, st, tp, overlays={"EMA200": e}, panels={"WaveTrend": {"WT1": wt1, "WT2": wt2}})


class ElderImpulse(Strategy):
    id = "elder_impulse"
    name_en = "Elder Impulse System (EMA13 slope + MACD-hist slope)"
    name_fa = "سیستم ایمپالس الدر (شیب EMA13 + شیب هیستوگرام MACD)"
    category = "Trend"
    author = "Dr. Alexander Elder — Come Into My Trading Room"
    difficulty = 2
    timeframes = "1h – 1d"
    params = {"ema": 13, "trend_ema": 100}
    description_en = ("Green bar = EMA13 rising AND MACD-hist rising (inertia + momentum agree). Enter on first green after a "
                      "non-green bar with HTF trend; exit when a red bar appears. Elder's own screening system.")
    description_fa = ("کندل سبز = EMA13 صعودی و هیستوگرام MACD صعودی (اینرسی + مومنتوم موافق). در اولین سبز بعد از غیرسبز با روند "
                      "تایم بالا وارد شو؛ با ظهور کندل قرمز خارج شو. سیستم غربالگری خود الدر.")
    rules_en = ["Green: EMA13 > EMA13[1] and hist > hist[1]", "Red: both falling", "Long: first green bar with price > EMA100",
                "Short: first red bar with price < EMA100"]
    rules_fa = ["سبز: EMA13 > قبلی و هیستوگرام > قبلی", "قرمز: هر دو نزولی", "خرید: اولین کندل سبز با قیمت > EMA100",
                "فروش: اولین کندل قرمز با قیمت < EMA100"]
    pros_en = ["Simple visual system", "Never trades against momentum"]
    cons_en = ["Frequent flips in chop"]
    pros_fa = ["سیستم بصری ساده", "هرگز خلاف مومنتوم معامله نمی‌کند"]
    cons_fa = ["برگشت‌های مکرر در رنج"]

    def run(self, df):
        p = self.p
        e = ta.ema(df.close, p["ema"])
        _, _, h = ta.macd(df.close)
        te = ta.ema(df.close, p["trend_ema"])
        a = ta.atr(df)
        green = (e > e.shift(1)) & (h > h.shift(1))
        red = (e < e.shift(1)) & (h < h.shift(1))
        long = green & ~green.shift(1).fillna(False).astype(bool) & (df.close > te)
        short = red & ~red.shift(1).fillna(False).astype(bool) & (df.close < te)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 1.5, 3.0)
        return StrategyResult(sig, st, tp, overlays={"EMA13": e, "EMA100": te}, panels={"MACD Hist": {"Hist": h}})


class ChandelierChopStrat(Strategy):
    id = "chandelier_chop"
    name_en = "Chandelier Exit + Choppiness Regime Lock"
    name_fa = "خروج شاندلیه + قفل رژیم با شاخص چاپینس"
    category = "Trend"
    author = "Chuck LeBeau (Chandelier), E.W. Dreiss (Choppiness); pattern used by top TradingView 'quant engine' scripts"
    difficulty = 3
    timeframes = "15m – 4h"
    params = {"atr_n": 22, "mult": 3.0, "chop_n": 14, "chop_max": 55}
    description_en = ("Two ideas that keep bots alive: (1) don't trade when Choppiness Index > 55 (ranging) — the #1 killer of "
                      "trend bots; (2) Chandelier stop = highest high − 3×ATR(22) trails winners without premature breakeven.")
    description_fa = ("دو ایده که بات‌ها را زنده نگه می‌دارد: (۱) وقتی شاخص چاپینس > ۵۵ (رنج) معامله نکن — قاتل شماره ۱ بات‌های روندی؛ "
                      "(۲) استاپ شاندلیه = بالاترین سقف − ۳×ATR(22) بدون سر‌به‌سر زودهنگام برنده‌ها را تریل می‌کند.")
    rules_en = ["Regime: CHOP(14) < 55 (trending)", "Long: close crosses above long Chandelier line (HH22 − 3·ATR)",
                "Short: close crosses below short line (LL22 + 3·ATR)", "Stop = Chandelier line"]
    rules_fa = ["رژیم: CHOP(14) < ۵۵ (رونددار)", "خرید: بسته از بالای خط شاندلیه بلند رد شود (HH22 − 3·ATR)",
                "فروش: بسته زیر خط شاندلیه کوتاه برود (LL22 + 3·ATR)", "حد ضرر = خط شاندلیه"]
    pros_en = ["Avoids chop by design", "Lets winners run"]
    cons_en = ["Misses first part of moves"]
    pros_fa = ["ذاتاً از رنج دوری می‌کند", "می‌گذارد برنده‌ها بدوند"]
    cons_fa = ["ابتدای حرکت را از دست می‌دهد"]

    def run(self, df):
        p = self.p
        a = ta.atr(df, p["atr_n"])
        hh = df.high.rolling(p["atr_n"]).max()
        ll = df.low.rolling(p["atr_n"]).min()
        long_line = hh - p["mult"] * a
        short_line = ll + p["mult"] * a
        chop = choppiness(df, p["chop_n"])
        trending = chop < p["chop_max"]
        long = self.cross_up(df.close, short_line) & trending
        short = self.cross_down(df.close, long_line) & trending
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = long_line[sig == 1]
        stop[sig == -1] = short_line[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2.5 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2.5 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"Chandelier Long": long_line, "Chandelier Short": short_line},
                              panels={"Choppiness": {"CHOP": chop}})


class NFILiteDip(Strategy):
    id = "nfi_lite"
    name_en = "Bot: NFI-lite Protected Dip Buy (NostalgiaForInfinity idea)"
    name_fa = "بات: خرید دیپ محافظت‌شده NFI-lite (ایده NostalgiaForInfinity)"
    category = "Bot-Ported"
    author = "Inspired by iterativ/NostalgiaForInfinity (most-starred freqtrade strategy)"
    difficulty = 4
    timeframes = "5m – 1h"
    params = {"ema_fast": 26, "ema_slow": 200, "rsi_max": 36, "bb_n": 20, "dip_pct": 0.02, "vol_min_mult": 0.5}
    description_en = ("NFI's core philosophy distilled: buy dips ONLY with layered protections — long-term uptrend (EMA200 rising), "
                      "close near/below lower BB, RSI < 36, candle 2% below EMA26, and volume not dead. Many small wins, "
                      "few knife catches.")
    description_fa = ("فلسفه اصلی NFI خلاصه‌شده: دیپ‌ها را فقط با لایه‌های محافظ بخر — روند بلندمدت صعودی (EMA200 صعودی)، بسته نزدیک/زیر "
                      "باند پایین، RSI < ۳۶، کندل ۲٪ زیر EMA26، و حجم زنده. سودهای کوچک زیاد، چاقوگیری کم.")
    rules_en = ["EMA200 rising (EMA200 > EMA200[12])", "close < EMA26 × 0.98", "close ≤ BB lower × 1.005", "RSI(14) < 36",
                "volume > 0.5 × 20-bar mean", "Target: EMA26; Stop: 2.5 ATR"]
    rules_fa = ["EMA200 صعودی (EMA200 > مقدار ۱۲ کندل قبل)", "بسته < EMA26 × ۰.۹۸", "بسته ≤ باند پایین × ۱.۰۰۵", "RSI(14) < ۳۶",
                "حجم > ۰.۵ × میانگین ۲۰ کندل", "هدف: EMA26؛ حد ضرر: 2.5 ATR"]
    pros_en = ["Multi-layer protection = low loss frequency"]
    cons_en = ["Long-only", "Misses breakouts entirely"]
    pros_fa = ["محافظت چندلایه = فرکانس ضرر پایین"]
    cons_fa = ["فقط خرید", "شکست‌ها را کاملاً از دست می‌دهد"]

    def run(self, df):
        p = self.p
        ef = ta.ema(df.close, p["ema_fast"])
        es = ta.ema(df.close, p["ema_slow"])
        r = ta.rsi(df.close)
        u, m, l = ta.bollinger(df.close, p["bb_n"], 2.0)
        a = ta.atr(df)
        vm = df.volume.rolling(20).mean()
        vol_ok = (df.volume > vm * p["vol_min_mult"]) | (df.volume.sum() == 0)
        long = (es > es.shift(12)) & (df.close < ef * (1 - p["dip_pct"])) & (df.close <= l * 1.005) & (r < p["rsi_max"]) & vol_ok
        long = long & ~long.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.close[sig == 1] - 2.5 * a[sig == 1]
        tgt[sig == 1] = ef[sig == 1]
        return StrategyResult(sig, stop, tgt, overlays={"EMA26": ef, "EMA200": es, "BB Low": l}, panels={"RSI": {"RSI": r}})
