"""
Strategies learned from specific master traders & quantified research (2026 research pass).
Sources: Linda Raschke (Street Smarts), Larry Williams, Toby Crabel, QuantifiedStrategies.com
(IBS, Triple RSI, Turnaround Tuesday, NR7), ICT (Silver Bullet, Power of Three), Al Brooks, HyroTrader false-breakout study.
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta


def ibs(df):
    return ((df.close - df.low) / (df.high - df.low).replace(0, np.nan)).fillna(0.5)


class RaschkeHolyGrail(Strategy):
    id = "holy_grail"
    name_en = "Raschke 'Holy Grail' (ADX>30 + first 20-EMA pullback)"
    name_fa = "جام مقدس لیندا راشکی (ADX>۳۰ + اولین پولبک به EMA۲۰)"
    category = "Trend"
    author = "Linda Bradford Raschke & Laurence Connors — Street Smarts (1995)"
    difficulty = 2
    timeframes = "15m – 1d"
    params = {"adx_min": 30, "ema": 20, "adx_n": 14}
    description_en = ("Named semi-humorously for its reliability. When ADX(14) > 30 and rising, the trend is proven. "
                      "Buy the FIRST pullback that touches the 20 EMA, entering above the high of the touching bar. "
                      "Stop under the pullback low; trail under the EMA or take profit at the prior swing high.")
    description_fa = ("به شوخی به‌خاطر قابل‌اعتماد بودنش «جام مقدس» نام گرفته. وقتی ADX(14) > ۳۰ و صعودی است، روند اثبات شده. "
                      "اولین پولبکی که EMA۲۰ را لمس می‌کند بخر، با ورود بالای سقف کندل لمس‌کننده. "
                      "حد ضرر زیر کف پولبک؛ تریل زیر EMA یا حد سود در سقف سوئینگ قبلی.")
    rules_en = ["ADX(14) > 30 and was rising into the pullback", "Uptrend: +DI > -DI",
                "Setup bar: low touches/penetrates 20 EMA", "Trigger: next bar trades above setup bar high",
                "Stop: below setup bar low. Target: previous swing high / 2R"]
    rules_fa = ["ADX(14) > ۳۰ و قبل از پولبک صعودی بوده", "روند صعودی: +DI > -DI",
                "کندل ستاپ: کف، EMA۲۰ را لمس می‌کند", "تریگر: کندل بعد بالای سقف کندل ستاپ معامله شود",
                "حد ضرر: زیر کف کندل ستاپ. هدف: سقف سوئینگ قبلی / 2R"]
    pros_en = ["Only trades proven trends", "Precise, low-risk entry", "40 years of use by a market wizard"]
    cons_en = ["ADX>30 is rare — patience required", "Second/third pullbacks are weaker"]
    pros_fa = ["فقط در روندهای اثبات‌شده", "ورود دقیق و کم‌ریسک", "۴۰ سال استفاده توسط یک جادوگر بازار"]
    cons_fa = ["ADX>۳۰ کمیاب است — صبر لازم", "پولبک دوم/سوم ضعیف‌ترند"]

    def run(self, df):
        p = self.p
        adx, pdi, mdi = ta.adx(df, p["adx_n"])
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df)
        strong = (adx > p["adx_min"]) & (adx.shift(3) < adx.shift(1))
        touch_lo = (df.low.shift(1) <= e.shift(1)) & (df.close.shift(1) > e.shift(1) * 0.995)
        touch_hi = (df.high.shift(1) >= e.shift(1)) & (df.close.shift(1) < e.shift(1) * 1.005)
        # first pullback: previous 8 bars had no touch
        no_recent_lo = ~(df.low.shift(2).rolling(8).min() <= e.shift(2).rolling(8).max()).fillna(False)
        no_recent_hi = ~(df.high.shift(2).rolling(8).max() >= e.shift(2).rolling(8).min()).fillna(False)
        long = strong & (pdi > mdi) & touch_lo & (df.high > df.high.shift(1)) & (df.close > e)
        short = strong & (mdi > pdi) & touch_hi & (df.low < df.low.shift(1)) & (df.close < e)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.low.shift(1)[sig == 1] - 0.2 * a[sig == 1]
        stop[sig == -1] = df.high.shift(1)[sig == -1] + 0.2 * a[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"EMA20": e}, panels={"ADX": {"ADX": adx, "+DI": pdi, "-DI": mdi}})


class RaschkeAnti(Strategy):
    id = "anti"
    name_en = "Raschke 'Anti' (Stochastic hook with trend)"
    name_fa = "الگوی «آنتی» راشکی (قلاب استوکاستیک با روند)"
    category = "Momentum"
    author = "Linda Raschke — Street Smarts"
    difficulty = 3
    timeframes = "15m – 4h"
    params = {"k": 7, "d": 10, "slow": 4}
    description_en = ("Slow %D defines the trend, fast %K the pullback. When %K hooks back in the direction of %D "
                      "after a pullback, momentum is resuming — enter on the hook bar break.")
    description_fa = ("%D کند روند را تعیین می‌کند، %K سریع پولبک را. وقتی %K بعد از پولبک در جهت %D قلاب می‌زند، "
                      "مومنتوم دوباره شروع شده — در شکست کندل قلاب وارد شو.")
    rules_en = ["%D(10) rising for ≥3 bars (trend up)", "%K(7) fell for 2–4 bars (pullback) then turns up (hook)",
                "Enter on break of hook bar high; stop under pullback low; target 2R"]
    rules_fa = ["%D(10) حداقل ۳ کندل صعودی (روند)", "%K(7) ۲–۴ کندل نزولی (پولبک) بعد رو به بالا برمی‌گردد (قلاب)",
                "ورود در شکست سقف کندل قلاب؛ حد ضرر زیر کف پولبک؛ هدف 2R"]
    pros_en = ["Catches momentum resumption early"]
    cons_en = ["Needs a real trend; noisy otherwise"]
    pros_fa = ["ادامه‌ی مومنتوم را زود می‌گیرد"]
    cons_fa = ["روند واقعی لازم دارد؛ وگرنه پرنویز"]

    def run(self, df):
        p = self.p
        k, _ = ta.stochastic(df, p["k"], 3, p["slow"])
        d = k.rolling(p["d"]).mean()
        a = ta.atr(df)
        d_up = (d > d.shift(1)) & (d.shift(1) > d.shift(2)) & (d.shift(2) > d.shift(3))
        d_dn = (d < d.shift(1)) & (d.shift(1) < d.shift(2)) & (d.shift(2) < d.shift(3))
        k_pulled_dn = (k.shift(1) < k.shift(2)) & (k.shift(2) < k.shift(3))
        k_pulled_up = (k.shift(1) > k.shift(2)) & (k.shift(2) > k.shift(3))
        hook_up = k > k.shift(1)
        hook_dn = k < k.shift(1)
        long = d_up & k_pulled_dn & hook_up & (df.close > df.open)
        short = d_dn & k_pulled_up & hook_dn & (df.close < df.open)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.low.rolling(4).min()[sig == 1] - 0.2 * a[sig == 1]
        stop[sig == -1] = df.high.rolling(4).max()[sig == -1] + 0.2 * a[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, panels={"Stochastic": {"%K(7)": k, "%D(10)": d}})


class LarryWilliamsVolBreakout(Strategy):
    id = "lw_vol_breakout"
    name_en = "Larry Williams Volatility Breakout"
    name_fa = "شکست نوسانی لری ویلیامز"
    category = "Volatility"
    author = "Larry Williams (World Cup Trading Champion 1987, +11,376%)"
    difficulty = 2
    timeframes = "1d (also 4h)"
    params = {"k": 0.6, "range_n": 1, "ema_filter": 50}
    description_en = ("Today's open + k × yesterday's range = buy stop. A move that large from the open, early in the day, "
                      "statistically continues. Exit next open (original) or at ATR target. One of the most copied systems in history.")
    description_fa = ("اوپن امروز + k × رنج دیروز = حد خرید. حرکتی به این بزرگی از اوپن، از نظر آماری ادامه پیدا می‌کند. "
                      "خروج در اوپن بعدی (نسخه اصلی) یا هدف ATR. یکی از پرکپی‌ترین سیستم‌های تاریخ.")
    rules_en = ["Long: close > open + 0.6 × previous bar range, and price > EMA50",
                "Short: close < open - 0.6 × previous range, price < EMA50", "Stop: bar open. Target: 1.5× range"]
    rules_fa = ["خرید: بسته > اوپن + ۰.۶ × رنج کندل قبل و قیمت > EMA50",
                "فروش: بسته < اوپن − ۰.۶ × رنج قبل، قیمت < EMA50", "حد ضرر: اوپن کندل. هدف: ۱.۵ × رنج"]
    pros_en = ["Objective, very simple", "Captures expansion days"]
    cons_en = ["Whipsaws in low-vol chop", "Needs cheap costs"]
    pros_fa = ["عینی و بسیار ساده", "روزهای انبساط را می‌گیرد"]
    cons_fa = ["در رنج کم‌نوسان اره می‌شود", "کارمزد پایین لازم دارد"]

    def run(self, df):
        p = self.p
        rng = (df.high - df.low).rolling(p["range_n"]).mean().shift(1)
        e = ta.ema(df.close, p["ema_filter"])
        long = (df.close > df.open + p["k"] * rng) & (df.close > e)
        short = (df.close < df.open - p["k"] * rng) & (df.close < e)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.open[sig == 1]
        stop[sig == -1] = df.open[sig == -1]
        tgt[sig == 1] = df.close[sig == 1] + 1.5 * rng[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 1.5 * rng[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"EMA50": e})


class TripleRSI(Strategy):
    id = "triple_rsi"
    name_en = "Triple RSI (QuantifiedStrategies — 90% historical WR on S&P)"
    name_fa = "سه‌گانه RSI (کوانتیفاید — وین‌ریت تاریخی ۹۰٪ روی S&P)"
    category = "Mean-Reversion"
    author = "QuantifiedStrategies.com (Oddmund Grøtte)"
    difficulty = 2
    timeframes = "1d"
    params = {"rsi_n": 5, "below": 30, "prior_below": 60, "sma": 200, "exit_above": 50}
    description_en = ("Few trades, very high win rate on stock indices. Buys a 3-day RSI(5) slide below 30 inside a bull market. "
                      "Exit when RSI(5) crosses back above 50.")
    description_fa = ("معاملات کم، وین‌ریت بسیار بالا روی شاخص‌های سهام. سقوط ۳ روزه RSI(5) به زیر ۳۰ در بازار گاوی را می‌خرد. "
                      "خروج وقتی RSI(5) دوباره بالای ۵۰ برود.")
    rules_en = ["RSI(5) < 30", "RSI(5) down 3 days in a row", "RSI(5) was < 60 three days ago", "Close > SMA200",
                "Buy at close; sell when RSI(5) > 50"]
    rules_fa = ["RSI(5) < ۳۰", "RSI(5) سه روز متوالی نزولی", "RSI(5) سه روز قبل < ۶۰ بوده", "بسته > SMA200",
                "خرید در بسته شدن؛ فروش وقتی RSI(5) > ۵۰"]
    pros_en = ["~90% win rate historically on SPY", "Fully mechanical"]
    cons_en = ["Rare (few trades/yr)", "Indices/stocks only", "Long-only"]
    pros_fa = ["وین‌ریت تاریخی ~۹۰٪ روی SPY", "کاملاً مکانیکی"]
    cons_fa = ["کمیاب (چند معامله در سال)", "فقط شاخص/سهام", "فقط خرید"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, p["rsi_n"])
        s = ta.sma(df.close, p["sma"])
        a = ta.atr(df)
        long = (r < p["below"]) & (r < r.shift(1)) & (r.shift(1) < r.shift(2)) & (r.shift(2) < r.shift(3)) & (r.shift(3) < p["prior_below"]) & (df.close > s)
        long = long & ~long.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.close[sig == 1] - 3 * a[sig == 1]
        tgt[sig == 1] = df.close[sig == 1] + 2 * a[sig == 1]
        return StrategyResult(sig, stop, tgt, overlays={"SMA200": s}, panels={"RSI(5)": {"RSI": r}})


class IBSMeanReversion(Strategy):
    id = "ibs"
    name_en = "IBS + RSI Mean Reversion (Internal Bar Strength)"
    name_fa = "بازگشت به میانگین IBS + RSI (قدرت داخلی کندل)"
    category = "Mean-Reversion"
    author = "QuantifiedStrategies.com; widely used on S&P/Nasdaq"
    difficulty = 1
    timeframes = "1d"
    params = {"ibs_max": 0.25, "rsi_n": 21, "rsi_max": 45, "sma": 200}
    description_en = ("IBS = (close-low)/(high-low). A close near the day's low (IBS<0.25) in a bull market tends to bounce. "
                      "Classic exit: close > yesterday's close. Works on indices/stocks, NOT on commodities/forex.")
    description_fa = ("IBS = (بسته−کف)/(سقف−کف). بسته شدن نزدیک کف روز (IBS<۰.۲۵) در بازار گاوی معمولاً برمی‌گردد. "
                      "خروج کلاسیک: بسته > بسته دیروز. روی شاخص/سهام کار می‌کند، نه روی کالا/فارکس.")
    rules_en = ["IBS < 0.25", "RSI(21) < 45", "Close > SMA200", "Buy at close; exit when close > previous close (or IBS > 0.8)"]
    rules_fa = ["IBS < ۰.۲۵", "RSI(21) < ۴۵", "بسته > SMA200", "خرید در بسته شدن؛ خروج وقتی بسته > بسته قبلی (یا IBS > ۰.۸)"]
    pros_en = ["Very high win rate", "Short holding time"]
    cons_en = ["Small average gain", "Equity indices only"]
    pros_fa = ["وین‌ریت بسیار بالا", "زمان نگهداری کوتاه"]
    cons_fa = ["میانگین سود کوچک", "فقط شاخص سهام"]

    def run(self, df):
        p = self.p
        i = ibs(df)
        r = ta.rsi(df.close, p["rsi_n"])
        s = ta.sma(df.close, p["sma"])
        a = ta.atr(df)
        long = (i < p["ibs_max"]) & (r < p["rsi_max"]) & (df.close > s)
        long = long & ~long.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.close[sig == 1] - 2.5 * a[sig == 1]
        tgt[sig == 1] = df.high[sig == 1]  # yesterday's high ≈ close > prev close proxy
        return StrategyResult(sig, stop, tgt, overlays={"SMA200": s}, panels={"IBS": {"IBS": i}})


class TurnaroundTuesday(Strategy):
    id = "turnaround_tuesday"
    name_en = "Turnaround Tuesday (calendar anomaly)"
    name_fa = "سه‌شنبه‌ی برگشت (ناهنجاری تقویمی)"
    category = "Mean-Reversion"
    author = "Academic anomaly; quantified by QuantifiedStrategies"
    difficulty = 1
    timeframes = "1d (stocks/indices)"
    params = {"ibs_max": 0.5, "hold_bars": 4}
    description_en = ("Decades-old, still-working anomaly: when Monday closes down (and weak within its range), Tuesday and the "
                      "following days tend to be positive. Buy Monday close, exit when close > previous high or after 4 days. ~69% WR historically.")
    description_fa = ("ناهنجاری چند دهه‌ای که هنوز کار می‌کند: وقتی دوشنبه منفی و ضعیف بسته می‌شود، سه‌شنبه و روزهای بعد "
                      "معمولاً مثبت‌اند. خرید در بسته دوشنبه، خروج وقتی بسته > سقف قبلی یا بعد از ۴ روز. وین‌ریت تاریخی ~۶۹٪.")
    rules_en = ["Today is Monday", "Close < Friday close", "IBS < 0.5", "Buy at close; exit close > yesterday high OR 4 bars"]
    rules_fa = ["امروز دوشنبه است", "بسته < بسته جمعه", "IBS < ۰.۵", "خرید در بسته؛ خروج وقتی بسته > سقف دیروز یا ۴ کندل"]
    pros_en = ["Tiny market exposure", "Robust for decades"]
    cons_en = ["Only ~30 trades/yr", "Equities only"]
    pros_fa = ["حضور خیلی کم در بازار", "دهه‌ها مقاوم"]
    cons_fa = ["فقط ~۳۰ معامله در سال", "فقط سهام"]

    def run(self, df):
        p = self.p
        a = ta.atr(df)
        sig = pd.Series(0, index=df.index)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        if not isinstance(df.index, pd.DatetimeIndex):
            return StrategyResult(sig, stop, tgt)
        monday = pd.Series(df.index.dayofweek == 0, index=df.index)
        i = ibs(df)
        long = monday & (df.close < df.close.shift(1)) & (i < p["ibs_max"])
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        stop[sig == 1] = df.close[sig == 1] - 2.5 * a[sig == 1]
        tgt[sig == 1] = df.high[sig == 1]
        return StrategyResult(sig, stop, tgt, panels={"IBS": {"IBS": i}})


class NR7Breakout(Strategy):
    id = "nr7"
    name_en = "NR7 / Inside-Day Range Contraction Breakout"
    name_fa = "شکست NR7 (کوچک‌ترین رنج ۷ روزه)"
    category = "Volatility"
    author = "Toby Crabel — Day Trading with Short Term Price Patterns (1990)"
    difficulty = 2
    timeframes = "1d / 4h"
    params = {"n": 7, "ema": 50}
    description_en = ("The narrowest range of the last 7 bars = maximum compression. Volatility cycles from low to high, "
                      "so trade the break of the NR7 bar's high/low next bar in the trend direction.")
    description_fa = ("کوچک‌ترین رنج ۷ کندل اخیر = حداکثر فشردگی. نوسان از کم به زیاد چرخه دارد، "
                      "پس شکست سقف/کف کندل NR7 را در کندل بعد در جهت روند معامله کن.")
    rules_en = ["Bar range = min of last 7 ranges (NR7)", "Long: next bar closes above NR7 high, price > EMA50",
                "Stop: NR7 low. Target: 2.5R"]
    rules_fa = ["رنج کندل = کمترین ۷ رنج اخیر (NR7)", "خرید: کندل بعد بالای سقف NR7 بسته شود، قیمت > EMA50",
                "حد ضرر: کف NR7. هدف: 2.5R"]
    pros_en = ["Tight stop, big R:R", "Objective"]
    cons_en = ["False breaks", "Works best on daily"]
    pros_fa = ["حد ضرر کوچک، R:R بزرگ", "عینی"]
    cons_fa = ["شکست‌های جعلی", "روی روزانه بهتر است"]

    def run(self, df):
        p = self.p
        rng = df.high - df.low
        nr = rng.shift(1) <= rng.shift(1).rolling(p["n"]).min()
        e = ta.ema(df.close, p["ema"])
        ph, pl = df.high.shift(1), df.low.shift(1)
        long = nr & (df.close > ph) & (df.close > e)
        short = nr & (df.close < pl) & (df.close < e)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = pl[sig == 1]
        stop[sig == -1] = ph[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2.5 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2.5 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"EMA50": e})


class ICTSilverBullet(Strategy):
    id = "silver_bullet"
    name_en = "ICT Silver Bullet (time-window sweep → FVG)"
    name_fa = "گلوله نقره‌ای ICT (پنجره زمانی: سوییپ ← FVG)"
    category = "Smart-Money"
    author = "ICT — Michael Huddleston (2022 model)"
    difficulty = 5
    timeframes = "5m – 15m (intraday, UTC data)"
    params = {"windows_utc": "8,15,19", "lookback": 12, "bias_ema": 50}
    description_en = ("Time + price. Only inside three 1-hour windows (London 3-4am ET, NY AM 10-11am ET, NY PM 2-3pm ET) "
                      "look for: liquidity sweep of a recent high/low → displacement candle that creates a FVG → enter on FVG "
                      "retest with HTF bias. Stop beyond the sweep, target opposite liquidity / 2R+.")
    description_fa = ("زمان + قیمت. فقط داخل سه پنجره ۱ ساعته (لندن ۳-۴ صبح، نیویورک ۱۰-۱۱ صبح، نیویورک ۲-۳ عصر به وقت ET) "
                      "دنبال این باش: سوییپ نقدینگی سقف/کف اخیر ← کندل جابه‌جایی که FVG می‌سازد ← ورود در ریتست FVG با بایاس تایم بالا. "
                      "حد ضرر پشت سوییپ، هدف نقدینگی مقابل / 2R+.")
    rules_en = ["Bar time within a Silver Bullet window (UTC hours 8, 15, 19 ≈ ET 3-4, 10-11, 2-3)",
                "Sweep: low < lowest low of prior 12 bars within last 3 bars",
                "Displacement: strong bullish candle creating a bullish FVG", "Bias: price > EMA50",
                "Entry on FVG formation close; stop below sweep low; target 2.5R"]
    rules_fa = ["زمان کندل داخل پنجره گلوله نقره‌ای (ساعت UTC ۸، ۱۵، ۱۹)",
                "سوییپ: کف < پایین‌ترین کف ۱۲ کندل قبل، در ۳ کندل اخیر",
                "جابه‌جایی: کندل صعودی قوی که FVG صعودی می‌سازد", "بایاس: قیمت > EMA50",
                "ورود در بسته شدن کندل FVG؛ حد ضرر زیر کف سوییپ؛ هدف 2.5R"]
    pros_en = ["One hour of focus per session", "Very defined risk"]
    cons_en = ["Requires intraday data (15m or lower)", "Most windows produce no setup — that's the point"]
    pros_fa = ["فقط یک ساعت تمرکز در هر سشن", "ریسک کاملاً مشخص"]
    cons_fa = ["داده درون‌روزی (۱۵ دقیقه یا کمتر) لازم", "اکثر پنجره‌ها ستاپ ندارند — و همین نکته است"]

    def run(self, df):
        p = self.p
        a = ta.atr(df)
        e = ta.ema(df.close, p["bias_ema"])
        sig = pd.Series(0, index=df.index)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        if not isinstance(df.index, pd.DatetimeIndex):
            return StrategyResult(sig, stop, tgt)
        hours = {int(x) for x in str(p["windows_utc"]).split(",") if x.strip()}
        in_win = pd.Series(np.isin(df.index.hour, list(hours)), index=df.index)
        ll = df.low.rolling(p["lookback"]).min().shift(1)
        hh = df.high.rolling(p["lookback"]).max().shift(1)
        swept_lo = (df.low < ll).rolling(3).max().fillna(0).astype(bool)
        swept_hi = (df.high > hh).rolling(3).max().fillna(0).astype(bool)
        body = (df.close - df.open)
        bull_fvg = (df.low > df.high.shift(2)) & (body.shift(1) > a)
        bear_fvg = (df.high < df.low.shift(2)) & (body.shift(1) < -a)
        long = in_win & swept_lo & bull_fvg & (df.close > e)
        short = in_win & swept_hi & bear_fvg & (df.close < e)
        sig = self.make_signal(long, short)
        sw_lo = df.low.rolling(4).min()
        sw_hi = df.high.rolling(4).max()
        stop[sig == 1] = sw_lo[sig == 1] - 0.2 * a[sig == 1]
        stop[sig == -1] = sw_hi[sig == -1] + 0.2 * a[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2.5 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2.5 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"EMA50": e, "Liq High": hh, "Liq Low": ll})


class PowerOfThree(Strategy):
    id = "po3"
    name_en = "ICT Power of Three (AMD — Accumulation/Manipulation/Distribution)"
    name_fa = "قدرت سه ICT (انباشت / دستکاری / توزیع)"
    category = "Smart-Money"
    author = "ICT — daily/weekly candle model"
    difficulty = 4
    timeframes = "1h – 4h (uses daily open)"
    params = {"manip_atr": 0.5, "bias_ema": 100}
    description_en = ("Every daily candle: accumulate near the open, manipulate (Judas swing) against the true direction to "
                      "grab stops, then distribute in the real direction. Bullish day = price dips below daily open first, then "
                      "reclaims it. Enter on the reclaim, stop under the manipulation low.")
    description_fa = ("هر کندل روزانه: انباشت نزدیک اوپن، دستکاری (جوداس سوئینگ) خلاف جهت واقعی برای گرفتن استاپ‌ها، بعد توزیع "
                      "در جهت واقعی. روز صعودی = قیمت اول زیر اوپن روزانه می‌رود، بعد آن را پس می‌گیرد. در پس‌گیری وارد شو، "
                      "حد ضرر زیر کف دستکاری.")
    rules_en = ["Bias: price > EMA100 (bullish day expected)", "Manipulation: intraday low ≥ 0.5 ATR below the daily open",
                "Entry: first intraday close back above the daily open", "Stop: manipulation low; target: 2R / previous day high"]
    rules_fa = ["بایاس: قیمت > EMA100 (روز صعودی انتظار می‌رود)", "دستکاری: کف درون‌روزی حداقل ۰.۵ ATR زیر اوپن روزانه",
                "ورود: اولین بسته شدن درون‌روزی بالای اوپن روزانه", "حد ضرر: کف دستکاری؛ هدف: 2R / سقف روز قبل"]
    pros_en = ["Explains daily rhythm", "Excellent R:R"]
    cons_en = ["Needs intraday data", "Bias must be right"]
    pros_fa = ["ریتم روزانه را توضیح می‌دهد", "ریسک به ریوارد عالی"]
    cons_fa = ["داده درون‌روزی لازم", "بایاس باید درست باشد"]

    def run(self, df):
        p = self.p
        a = ta.atr(df)
        e = ta.ema(df.close, p["bias_ema"])
        sig = pd.Series(0, index=df.index)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        if not isinstance(df.index, pd.DatetimeIndex):
            return StrategyResult(sig, stop, tgt)
        day = df.index.normalize()
        d_open = df.open.groupby(day).transform("first")
        run_low = df.low.groupby(day).cummin()
        run_high = df.high.groupby(day).cummax()
        manip_dn = (d_open - run_low.shift(1)) >= p["manip_atr"] * a
        manip_up = (run_high.shift(1) - d_open) >= p["manip_atr"] * a
        same_day = pd.Series(day, index=df.index) == pd.Series(day, index=df.index).shift(1)
        reclaim_up = (df.close > d_open) & (df.close.shift(1) <= d_open) & same_day
        reclaim_dn = (df.close < d_open) & (df.close.shift(1) >= d_open) & same_day
        long = manip_dn & reclaim_up & (df.close > e)
        short = manip_up & reclaim_dn & (df.close < e)
        # first per day only
        long = long & ~long.groupby(day).cumsum().shift(1).fillna(0).astype(bool)
        short = short & ~short.groupby(day).cumsum().shift(1).fillna(0).astype(bool)
        sig = self.make_signal(long, short)
        stop[sig == 1] = run_low[sig == 1] - 0.1 * a[sig == 1]
        stop[sig == -1] = run_high[sig == -1] + 0.1 * a[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"Daily Open": d_open, "EMA100": e})


class FalseBreakout(Strategy):
    id = "false_breakout"
    name_en = "False Breakout Fade (Bull/Bear Trap)"
    name_fa = "معامله شکست جعلی (تله گاوی/خرسی)"
    category = "Price-Action"
    author = "Al Brooks (failed breakouts); 2025 study: 62% WR vs 54% for true breakouts"
    difficulty = 3
    timeframes = "15m – 1d"
    params = {"lookback": 20, "confirm_bars": 2}
    description_en = ("Research shows fading failed breakouts beats trading breakouts. Price closes above a 20-bar high, "
                      "then within 2 bars closes back below it — trapped longs must exit, fuelling the reversal.")
    description_fa = ("تحقیقات نشان می‌دهد معامله‌ی شکست‌های ناموفق بهتر از خود شکست است. قیمت بالای سقف ۲۰ کندل بسته می‌شود، "
                      "بعد طی ۲ کندل دوباره زیر آن بسته می‌شود — خریدارهای گیرافتاده باید خارج شوند و برگشت را تغذیه می‌کنند.")
    rules_en = ["Breakout: close > 20-bar high (bar i-1 or i-2)", "Failure: current close < that prior high",
                "Short at failure close; stop above breakout high; target 2R"]
    rules_fa = ["شکست: بسته > سقف ۲۰ کندل (کندل i-1 یا i-2)", "شکست ناموفق: بسته فعلی < آن سقف قبلی",
                "فروش در بسته ناموفق؛ حد ضرر بالای سقف شکست؛ هدف 2R"]
    pros_en = ["Higher WR than breakouts", "Trapped traders provide fuel"]
    cons_en = ["Real breakouts re-break — respect the stop"]
    pros_fa = ["وین‌ریت بالاتر از شکست‌ها", "معامله‌گران گیرافتاده سوخت می‌دهند"]
    cons_fa = ["شکست‌های واقعی دوباره می‌شکنند — به استاپ احترام بگذار"]

    def run(self, df):
        p = self.p
        a = ta.atr(df)
        hh = df.high.rolling(p["lookback"]).max().shift(1)
        ll = df.low.rolling(p["lookback"]).min().shift(1)
        broke_up = (df.close > hh)
        broke_dn = (df.close < ll)
        recent_up = broke_up.shift(1).fillna(False) | broke_up.shift(2).fillna(False)
        recent_dn = broke_dn.shift(1).fillna(False) | broke_dn.shift(2).fillna(False)
        lvl_up = hh.shift(1)
        lvl_dn = ll.shift(1)
        short = recent_up.astype(bool) & (df.close < lvl_up) & (df.close < df.open)
        long = recent_dn.astype(bool) & (df.close > lvl_dn) & (df.close > df.open)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == -1] = df.high.rolling(3).max()[sig == -1] + 0.2 * a[sig == -1]
        stop[sig == 1] = df.low.rolling(3).min()[sig == 1] - 0.2 * a[sig == 1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"20H": hh, "20L": ll})
