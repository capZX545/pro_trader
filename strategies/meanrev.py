import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta


class RSIReversal(Strategy):
    id = "rsi_reversal"
    name_en = "RSI Oversold/Overbought + Trend Filter"
    name_fa = "RSI اشباع خرید/فروش با فیلتر روند"
    category = "Mean-Reversion"
    author = "J. Welles Wilder; refined by Larry Connors"
    difficulty = 1
    timeframes = "1h – 1d"
    params = {"n": 14, "ob": 70, "os": 30, "ema": 200}
    description_en = "Buy dips in an uptrend when RSI leaves oversold; sell rallies in a downtrend when RSI leaves overbought."
    description_fa = "در روند صعودی وقتی RSI از اشباع فروش خارج می‌شود بخر؛ در روند نزولی وقتی از اشباع خرید خارج می‌شود بفروش."
    rules_en = ["Long: RSI crosses back above 30 and price > EMA200", "Short: RSI crosses back below 70 and price < EMA200"]
    rules_fa = ["خرید: RSI دوباره بالای ۳۰ برگردد و قیمت بالای EMA200", "فروش: RSI دوباره زیر ۷۰ برگردد و قیمت زیر EMA200"]
    pros_en = ["High win rate in trends"]
    cons_en = ["Catching falling knives without filter"]
    pros_fa = ["وین‌ریت بالا در روند"]
    cons_fa = ["بدون فیلتر، چاقوی در حال سقوط را می‌گیرد"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, p["n"])
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df)
        long = self.cross_up(r, p["os"]) & (df.close > e)
        short = self.cross_down(r, p["ob"]) & (df.close < e)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 1.5, 2.0)
        return StrategyResult(sig, st, tp, overlays={"EMA200": e}, panels={"RSI": {"RSI": r}})


class RSI2Connors(Strategy):
    id = "rsi2"
    name_en = "Connors RSI(2) Pullback"
    name_fa = "پولبک RSI(2) لری کانرز"
    category = "Mean-Reversion"
    author = "Larry Connors & Cesar Alvarez"
    difficulty = 2
    timeframes = "1d"
    params = {"rsi_n": 2, "buy_below": 10, "sell_above": 90, "sma_trend": 200, "sma_exit": 5}
    description_en = ("Famous statistically-tested stock strategy: in a bull market (above 200 SMA) buy extreme short-term "
                      "oversold (RSI2<10), exit when price closes above 5 SMA. ~75% historical win rate on indices.")
    description_fa = ("استراتژی معروف آماری سهام: در بازار گاوی (بالای SMA200) در اشباع فروش شدید کوتاه‌مدت (RSI2<10) بخر، "
                      "وقتی قیمت بالای SMA5 بسته شد خارج شو. وین‌ریت تاریخی ~۷۵٪ روی شاخص‌ها.")
    rules_en = ["Long: close > SMA200 and RSI(2) < 10", "Exit: close > SMA5", "Short: close < SMA200 and RSI(2) > 90"]
    rules_fa = ["خرید: قیمت > SMA200 و RSI(2) < 10", "خروج: قیمت > SMA5", "فروش: قیمت < SMA200 و RSI(2) > 90"]
    pros_en = ["Very high win rate", "Fully quantified"]
    cons_en = ["Small wins, occasional large loss", "No hard stop in original"]
    pros_fa = ["وین‌ریت بسیار بالا", "کاملاً کمّی"]
    cons_fa = ["سودهای کوچک، گاهی ضرر بزرگ", "در نسخه اصلی حد ضرر سخت ندارد"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, p["rsi_n"])
        s200 = ta.sma(df.close, p["sma_trend"])
        s5 = ta.sma(df.close, p["sma_exit"])
        a = ta.atr(df)
        long = (df.close > s200) & (r < p["buy_below"]) & ~((df.close.shift(1) > s200.shift(1)) & (r.shift(1) < p["buy_below"]))
        short = (df.close < s200) & (r > p["sell_above"]) & ~((df.close.shift(1) < s200.shift(1)) & (r.shift(1) > p["sell_above"]))
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 3.0, 1.5)
        return StrategyResult(sig, st, tp, overlays={"SMA200": s200, "SMA5": s5}, panels={"RSI2": {"RSI(2)": r}})


class BollingerBounce(Strategy):
    id = "bb_bounce"
    name_en = "Bollinger Band Bounce (Range)"
    name_fa = "برگشت از باند بولینگر (رنج)"
    category = "Mean-Reversion"
    author = "John Bollinger"
    difficulty = 1
    timeframes = "15m – 4h"
    params = {"n": 20, "k": 2.0, "adx_max": 25}
    description_en = "In a ranging market (ADX<25) fade touches of the outer bands back toward the middle band."
    description_fa = "در بازار رنج (ADX<۲۵) لمس باندهای بیرونی را در جهت برگشت به باند میانی معامله کن."
    rules_en = ["Long: candle closes back inside after low < lower band, ADX < 25", "Short: mirror at upper band",
                "Target: middle band"]
    rules_fa = ["خرید: بعد از اینکه کف کندل زیر باند پایین رفت، کندل داخل باند بسته شود، ADX < ۲۵", "فروش: برعکس در باند بالا",
                "هدف: باند میانی"]
    pros_en = ["Great in sideways markets"]
    cons_en = ["Gets destroyed in breakouts — ADX filter is essential"]
    pros_fa = ["عالی در بازار خنثی"]
    cons_fa = ["در شکست‌ها نابود می‌شود — فیلتر ADX ضروری است"]

    def run(self, df):
        p = self.p
        u, m, l = ta.bollinger(df.close, p["n"], p["k"])
        adx, _, _ = ta.adx(df)
        rng = adx < p["adx_max"]
        long = (df.low.shift(1) < l.shift(1)) & (df.close > l) & (df.close > df.open) & rng
        short = (df.high.shift(1) > u.shift(1)) & (df.close < u) & (df.close < df.open) & rng
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.low.rolling(2).min()[sig == 1] * 0.998
        stop[sig == -1] = df.high.rolling(2).max()[sig == -1] * 1.002
        tgt[sig != 0] = m[sig != 0]
        return StrategyResult(sig, stop, tgt, overlays={"BB Upper": u, "BB Mid": m, "BB Lower": l})


class BollingerSqueeze(Strategy):
    id = "bb_squeeze"
    name_en = "TTM Squeeze (Bollinger inside Keltner)"
    name_fa = "اسکوئیز TTM (بولینگر داخل کلتنر)"
    category = "Volatility"
    author = "John Carter (Mastering the Trade)"
    difficulty = 3
    timeframes = "15m – 1d"
    params = {"n": 20, "bb_k": 2.0, "kc_mult": 1.5}
    description_en = ("Volatility compression precedes expansion. When BB squeezes inside KC and then releases, "
                      "trade the direction of momentum.")
    description_fa = ("فشردگی نوسان قبل از انبساط می‌آید. وقتی بولینگر داخل کلتنر فشرده و سپس آزاد می‌شود، "
                      "در جهت مومنتوم معامله کن.")
    rules_en = ["Squeeze on: BB upper < KC upper AND BB lower > KC lower", "Fire: squeeze turns off",
                "Direction: momentum histogram (close - midpoint of Donchian/SMA) sign"]
    rules_fa = ["اسکوئیز فعال: باند بالای BB < KC و باند پایین BB > KC", "شلیک: اسکوئیز خاموش شود",
                "جهت: علامت هیستوگرام مومنتوم"]
    pros_en = ["Catches explosive moves early"]
    cons_en = ["Direction can be wrong at release"]
    pros_fa = ["حرکات انفجاری را زود می‌گیرد"]
    cons_fa = ["جهت در لحظه آزادشدن ممکن است اشتباه باشد"]

    def run(self, df):
        p = self.p
        bu, bm, bl = ta.bollinger(df.close, p["n"], p["bb_k"])
        ku, km, kl = ta.keltner(df, p["n"], p["kc_mult"])
        a = ta.atr(df)
        sq = (bu < ku) & (bl > kl)
        hh, ll = ta.donchian(df, p["n"])
        mom = df.close - ((hh + ll) / 2 + ta.sma(df.close, p["n"])) / 2
        mom = mom.rolling(3).mean()
        fire = ~sq & sq.shift(1).fillna(False).astype(bool)
        long = fire & (mom > 0)
        short = fire & (mom < 0)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 1.5, 3.5)
        return StrategyResult(sig, st, tp, overlays={"BB Upper": bu, "BB Lower": bl, "KC Upper": ku, "KC Lower": kl},
                              panels={"Squeeze Momentum": {"Momentum": mom, "Squeeze": sq.astype(int) * mom.abs().max() * 0.3}})


class StochRSIStrat(Strategy):
    id = "stoch_rsi"
    name_en = "Stochastic RSI Cross in Trend"
    name_fa = "کراس استوکاستیک RSI در روند"
    category = "Momentum"
    author = "Tushar Chande & Stanley Kroll"
    difficulty = 2
    timeframes = "15m – 4h"
    params = {"n": 14, "k": 3, "d": 3, "ema": 100}
    description_en = "Buy K/D cross up below 20 in uptrend; sell K/D cross down above 80 in downtrend."
    description_fa = "در روند صعودی کراس K/D رو به بالا زیر ۲۰ بخر؛ در روند نزولی کراس رو به پایین بالای ۸۰ بفروش."
    rules_en = ["Long: %K crosses above %D, both < 20, price > EMA100", "Short: mirror above 80"]
    rules_fa = ["خرید: %K از بالای %D رد شود، هردو < ۲۰، قیمت > EMA100", "فروش: برعکس بالای ۸۰"]
    pros_en = ["Fast, precise timing"]
    cons_en = ["Very noisy without filter"]
    pros_fa = ["سریع و تایمینگ دقیق"]
    cons_fa = ["بدون فیلتر بسیار پرنویز"]

    def run(self, df):
        p = self.p
        k, d = ta.stoch_rsi(df.close, p["n"], p["k"], p["d"])
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df)
        long = self.cross_up(k, d) & (k < 25) & (df.close > e)
        short = self.cross_down(k, d) & (k > 75) & (df.close < e)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 1.5, 3.0)
        return StrategyResult(sig, st, tp, overlays={"EMA100": e}, panels={"StochRSI": {"%K": k, "%D": d}})


class RSIDivergence(Strategy):
    id = "rsi_div"
    name_en = "RSI Divergence (Regular)"
    name_fa = "واگرایی معمولی RSI"
    category = "Momentum"
    author = "Classic; taught by every price-action mentor"
    difficulty = 3
    timeframes = "1h – 1d"
    params = {"n": 14, "lookback": 30, "swing": 3}
    description_en = ("Price makes a lower low but RSI makes a higher low = bullish divergence (momentum fading). "
                      "One of the most reliable reversal signals when combined with S/R.")
    description_fa = ("قیمت کف پایین‌تر می‌زند ولی RSI کف بالاتر = واگرایی صعودی (مومنتوم در حال ضعیف شدن). "
                      "یکی از قابل‌اعتمادترین سیگنال‌های برگشتی وقتی با حمایت/مقاومت ترکیب شود.")
    rules_en = ["Bullish: new swing low in price lower than previous, RSI swing low higher than previous",
                "Bearish: mirror with swing highs", "Confirm with bullish/bearish candle close"]
    rules_fa = ["صعودی: کف جدید قیمت پایین‌تر از قبلی، کف RSI بالاتر از قبلی",
                "نزولی: برعکس با سقف‌ها", "تأیید با بسته شدن کندل صعودی/نزولی"]
    pros_en = ["Early reversal warning", "Excellent R:R"]
    cons_en = ["Divergences can extend a long time in strong trends"]
    pros_fa = ["هشدار زودهنگام برگشت", "ریسک به ریوارد عالی"]
    cons_fa = ["در روندهای قوی واگرایی می‌تواند مدت زیادی ادامه یابد"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, p["n"])
        a = ta.atr(df)
        sw = p["swing"]
        sh, sl = ta.swing_points(df, sw, sw)
        n = len(df)
        long = np.zeros(n, dtype=bool)
        short = np.zeros(n, dtype=bool)
        lows_idx = np.where(sl.values)[0]
        highs_idx = np.where(sh.values)[0]
        lo, hi, rv = df.low.values, df.high.values, r.values
        for j in range(1, len(lows_idx)):
            i2, i1 = lows_idx[j], lows_idx[j - 1]
            if i2 - i1 > p["lookback"]:
                continue
            if lo[i2] < lo[i1] and rv[i2] > rv[i1] and rv[i2] < 45:
                k = i2 + sw  # confirmed at swing right offset
                if k < n:
                    long[k] = True
        for j in range(1, len(highs_idx)):
            i2, i1 = highs_idx[j], highs_idx[j - 1]
            if i2 - i1 > p["lookback"]:
                continue
            if hi[i2] > hi[i1] and rv[i2] < rv[i1] and rv[i2] > 55:
                k = i2 + sw
                if k < n:
                    short[k] = True
        sig = self.make_signal(pd.Series(long, index=df.index), pd.Series(short, index=df.index))
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        ll = df.low.rolling(sw * 2 + 1).min()
        hh = df.high.rolling(sw * 2 + 1).max()
        stop[sig == 1] = ll[sig == 1] - 0.3 * a[sig == 1]
        stop[sig == -1] = hh[sig == -1] + 0.3 * a[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2.5 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2.5 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, panels={"RSI": {"RSI": r}})


class VWAPReversion(Strategy):
    id = "vwap"
    name_en = "VWAP Deviation Reversion (Intraday)"
    name_fa = "بازگشت به VWAP (روزانه)"
    category = "Mean-Reversion"
    author = "Institutional execution desks; popularised by Brian Shannon"
    difficulty = 2
    timeframes = "5m – 1h"
    params = {"dev_atr": 2.0}
    description_en = "Institutions execute around VWAP. When price stretches >2 ATR from VWAP, fade back toward it."
    description_fa = "مؤسسات حول VWAP اجرا می‌کنند. وقتی قیمت بیش از ۲ ATR از VWAP فاصله بگیرد، در جهت برگشت به آن معامله کن."
    rules_en = ["Long: close < VWAP - 2×ATR and bullish candle", "Short: close > VWAP + 2×ATR and bearish candle", "Target: VWAP"]
    rules_fa = ["خرید: قیمت < VWAP - ۲×ATR و کندل صعودی", "فروش: قیمت > VWAP + ۲×ATR و کندل نزولی", "هدف: VWAP"]
    pros_en = ["Institution-aligned reference"]
    cons_en = ["Intraday only; needs volume data"]
    pros_fa = ["مرجع هم‌راستا با مؤسسات"]
    cons_fa = ["فقط روزانه؛ به داده حجم نیاز دارد"]

    def run(self, df):
        v = ta.vwap(df)
        a = ta.atr(df)
        d = self.p["dev_atr"]
        long = (df.close < v - d * a) & (df.close > df.open)
        short = (df.close > v + d * a) & (df.close < df.open)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.close[sig == 1] - 1.5 * a[sig == 1]
        stop[sig == -1] = df.close[sig == -1] + 1.5 * a[sig == -1]
        tgt[sig != 0] = v[sig != 0]
        return StrategyResult(sig, stop, tgt, overlays={"VWAP": v})


class OBVDivergence(Strategy):
    id = "obv_trend"
    name_en = "OBV Breakout Confirmation"
    name_fa = "تأیید شکست با OBV"
    category = "Volume"
    author = "Joseph Granville"
    difficulty = 2
    timeframes = "1h – 1d"
    params = {"n": 20}
    description_en = "Only trade price breakouts that OBV also confirms with its own breakout — volume must agree."
    description_fa = "فقط شکست‌های قیمتی را معامله کن که OBV هم با شکست خودش تأیید کند — حجم باید موافق باشد."
    rules_en = ["Long: close > 20-bar high AND OBV > 20-bar OBV high", "Short: mirror"]
    rules_fa = ["خرید: قیمت > سقف ۲۰ کندل و OBV > سقف ۲۰ کندل OBV", "فروش: برعکس"]
    pros_en = ["Filters low-volume fake breakouts"]
    cons_en = ["Useless on forex (no real volume)"]
    pros_fa = ["شکست‌های جعلی کم‌حجم را فیلتر می‌کند"]
    cons_fa = ["روی فارکس بی‌فایده (حجم واقعی ندارد)"]

    def run(self, df):
        n = self.p["n"]
        o = ta.obv(df)
        a = ta.atr(df)
        hh, ll = ta.donchian(df, n)
        oh, ol = o.rolling(n).max(), o.rolling(n).min()
        long = (df.close > hh.shift(1)) & (o > oh.shift(1))
        short = (df.close < ll.shift(1)) & (o < ol.shift(1))
        long = long & ~long.shift(1).fillna(False).astype(bool)
        short = short & ~short.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        st, tp = self.atr_stops(df, sig, a, 2.0, 4.0)
        return StrategyResult(sig, st, tp, panels={"OBV": {"OBV": o}})


class MFIStrat(Strategy):
    id = "mfi"
    name_en = "Money Flow Index Extremes"
    name_fa = "اکسترمم‌های شاخص جریان پول (MFI)"
    category = "Volume"
    author = "Gene Quong & Avrum Soudack"
    difficulty = 1
    timeframes = "1h – 1d"
    params = {"n": 14, "ob": 80, "os": 20}
    description_en = "Volume-weighted RSI. Exits from <20 / >80 mark exhaustion of buying/selling pressure."
    description_fa = "RSI وزن‌دار با حجم. خروج از <۲۰ / >۸۰ نشانه اتمام فشار خرید/فروش است."
    rules_en = ["Long: MFI crosses above 20", "Short: MFI crosses below 80"]
    rules_fa = ["خرید: MFI بالای ۲۰ برگردد", "فروش: MFI زیر ۸۰ برگردد"]
    pros_en = ["Adds volume to momentum"]
    cons_en = ["Same weaknesses as RSI"]
    pros_fa = ["حجم را به مومنتوم اضافه می‌کند"]
    cons_fa = ["همان ضعف‌های RSI"]

    def run(self, df):
        m = ta.mfi(df, self.p["n"])
        a = ta.atr(df)
        sig = self.make_signal(self.cross_up(m, self.p["os"]), self.cross_down(m, self.p["ob"]))
        st, tp = self.atr_stops(df, sig, a, 1.5, 2.5)
        return StrategyResult(sig, st, tp, panels={"MFI": {"MFI": m}})
