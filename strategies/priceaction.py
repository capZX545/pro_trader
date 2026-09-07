import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta


class PinBar(Strategy):
    id = "pinbar"
    name_en = "Pin Bar at Key Level (Nial Fuller style)"
    name_fa = "پین بار در سطح کلیدی (سبک نایل فولر)"
    category = "Price-Action"
    author = "Nial Fuller / Martin Pring"
    difficulty = 2
    timeframes = "4h – 1d"
    params = {"wick_ratio": 0.66, "ema": 50, "lookback": 20}
    description_en = ("A long-wick rejection candle at a swing level in the direction of the trend. "
                      "The wick shows the market tried and failed to go there.")
    description_fa = ("کندل با سایه بلند که در سطح سوئینگ در جهت روند رد شده. "
                      "سایه نشان می‌دهد بازار تلاش کرد به آنجا برود و شکست خورد.")
    rules_en = ["Bullish pin: lower wick ≥ 66% of range, closes in top third, low is 20-bar low area, price > EMA50",
                "Bearish pin: mirror", "Stop beyond wick, target 2R"]
    rules_fa = ["پین صعودی: سایه پایین ≥ ۶۶٪ رنج، بسته شدن در یک‌سوم بالایی، کف نزدیک کف ۲۰ کندل، قیمت > EMA50",
                "پین نزولی: برعکس", "حد ضرر پشت سایه، هدف 2R"]
    pros_en = ["Clear, visual", "Excellent R:R"]
    cons_en = ["Context is everything — pin bars in mid-range fail"]
    pros_fa = ["واضح و بصری", "ریسک به ریوارد عالی"]
    cons_fa = ["زمینه همه‌چیز است — پین بار وسط رنج شکست می‌خورد"]

    def run(self, df):
        p = self.p
        rng = ta.candle_range(df)
        lw, uw = ta.lower_wick(df), ta.upper_wick(df)
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df)
        ll = df.low.rolling(p["lookback"]).min()
        hh = df.high.rolling(p["lookback"]).max()
        bull = (lw / rng >= p["wick_ratio"]) & (df.close > df.low + rng * 0.66) & (df.low <= ll.shift(1) * 1.002) & (df.close > e)
        bear = (uw / rng >= p["wick_ratio"]) & (df.close < df.high - rng * 0.66) & (df.high >= hh.shift(1) * 0.998) & (df.close < e)
        sig = self.make_signal(bull, bear)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.low[sig == 1] - 0.2 * a[sig == 1]
        stop[sig == -1] = df.high[sig == -1] + 0.2 * a[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"EMA50": e})


class EngulfingStrat(Strategy):
    id = "engulfing"
    name_en = "Engulfing Candle with Trend"
    name_fa = "کندل پوشا (انگالفینگ) در جهت روند"
    category = "Price-Action"
    author = "Steve Nison (Japanese Candlestick Charting)"
    difficulty = 1
    timeframes = "1h – 1d"
    params = {"ema": 50, "min_body_atr": 0.5}
    description_en = "A candle whose body fully engulfs the previous opposite candle, after a pullback, in trend direction."
    description_fa = "کندلی که بدنه‌اش بدنه کندل مخالف قبلی را کامل می‌پوشاند، بعد از پولبک، در جهت روند."
    rules_en = ["Bullish: prev red, current green, open ≤ prev close, close ≥ prev open, price > EMA50, body ≥ 0.5 ATR",
                "Bearish: mirror"]
    rules_fa = ["صعودی: قبلی قرمز، فعلی سبز، باز ≤ بسته قبلی، بسته ≥ باز قبلی، قیمت > EMA50، بدنه ≥ ۰.۵ ATR",
                "نزولی: برعکس"]
    pros_en = ["Very common, easy to spot"]
    cons_en = ["Too common — needs location filter"]
    pros_fa = ["بسیار رایج، شناسایی آسان"]
    cons_fa = ["بیش از حد رایج — نیاز به فیلتر مکان"]

    def run(self, df):
        p = self.p
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df)
        b = ta.body(df)
        po, pc = df.open.shift(1), df.close.shift(1)
        bull = (pc < po) & (df.close > df.open) & (df.open <= pc) & (df.close >= po) & (df.close > e) & (b > p["min_body_atr"] * a) & (df.low.shift(1) < e * 1.01)
        bear = (pc > po) & (df.close < df.open) & (df.open >= pc) & (df.close <= po) & (df.close < e) & (b > p["min_body_atr"] * a) & (df.high.shift(1) > e * 0.99)
        sig = self.make_signal(bull, bear)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df[["low"]].min(axis=1).rolling(2).min()[sig == 1] - 0.2 * a[sig == 1]
        stop[sig == -1] = df.high.rolling(2).max()[sig == -1] + 0.2 * a[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"EMA50": e})


class InsideBarBreakout(Strategy):
    id = "inside_bar"
    name_en = "Inside Bar Breakout"
    name_fa = "شکست اینساید بار"
    category = "Price-Action"
    author = "Classic; popularised by Nial Fuller"
    difficulty = 1
    timeframes = "4h – 1d"
    params = {"ema": 50}
    description_en = "Inside bar = compression. Trade the breakout of the mother bar in the trend direction."
    description_fa = "اینساید بار = فشردگی. شکست کندل مادر را در جهت روند معامله کن."
    rules_en = ["Inside bar: high < prev high and low > prev low", "Long: next candle closes above mother high (trend up)",
                "Stop: mother bar low"]
    rules_fa = ["اینساید بار: سقف < سقف قبلی و کف > کف قبلی", "خرید: کندل بعد بالای سقف مادر بسته شود (روند صعودی)",
                "حد ضرر: کف کندل مادر"]
    pros_en = ["Tight stops", "Simple"]
    cons_en = ["Fake breakouts"]
    pros_fa = ["حد ضرر کوچک", "ساده"]
    cons_fa = ["شکست‌های جعلی"]

    def run(self, df):
        e = ta.ema(df.close, self.p["ema"])
        ib = (df.high.shift(1) < df.high.shift(2)) & (df.low.shift(1) > df.low.shift(2))
        mh, ml = df.high.shift(2), df.low.shift(2)
        long = ib & (df.close > mh) & (df.close > e)
        short = ib & (df.close < ml) & (df.close < e)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = ml[sig == 1]
        stop[sig == -1] = mh[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"EMA50": e})


class SupportResistanceBreak(Strategy):
    id = "sr_breakout_retest"
    name_en = "S/R Breakout & Retest"
    name_fa = "شکست و پولبک به حمایت/مقاومت"
    category = "Price-Action"
    author = "Universal — core of classical technical analysis"
    difficulty = 3
    timeframes = "1h – 1d"
    params = {"swing": 5, "lookback": 100, "tolerance_atr": 0.5, "max_wait": 15}
    description_en = ("Identify swing-based S/R. When price breaks a level and comes back to retest it as new support "
                      "(role reversal) and holds, enter with stop under the level.")
    description_fa = ("حمایت/مقاومت را از سوئینگ‌ها شناسایی کن. وقتی قیمت سطح را می‌شکند و برای پولبک برمی‌گردد "
                      "(تغییر نقش) و آن را حفظ می‌کند، با حد ضرر زیر سطح وارد شو.")
    rules_en = ["Level: swing high/low touched ≥ 2 times", "Break: close beyond level",
                "Retest: within 15 bars price returns within 0.5 ATR of level and closes back in break direction"]
    rules_fa = ["سطح: سوئینگ که حداقل ۲ بار لمس شده", "شکست: بسته شدن فراتر از سطح",
                "پولبک: تا ۱۵ کندل قیمت به فاصله ۰.۵ ATR سطح برگردد و در جهت شکست بسته شود"]
    pros_en = ["Higher probability than raw breakouts", "Logical stop"]
    cons_en = ["Miss trades that don't retest"]
    pros_fa = ["احتمال بالاتر از شکست خام", "حد ضرر منطقی"]
    cons_fa = ["معاملاتی که پولبک نمی‌زنند از دست می‌رود"]

    def run(self, df):
        p = self.p
        sw = p["swing"]
        sh, sl = ta.swing_points(df, sw, sw)
        a = ta.atr(df)
        n = len(df)
        hi, lo, cl = df.high.values, df.low.values, df.close.values
        av = a.values
        long = np.zeros(n, dtype=bool)
        short = np.zeros(n, dtype=bool)
        stop = np.full(n, np.nan)
        tgt = np.full(n, np.nan)
        levels_out = []
        res_levels = []  # (price, created_idx)
        sup_levels = []
        broken_res = []  # (price, break_idx)
        broken_sup = []
        for i in range(sw * 2, n):
            # add new confirmed swing (confirmed sw bars later)
            j = i - sw
            if sh.values[j]:
                res_levels.append((hi[j], j))
            if sl.values[j]:
                sup_levels.append((lo[j], j))
            res_levels = [(px, k) for px, k in res_levels if i - k < p["lookback"]]
            sup_levels = [(px, k) for px, k in sup_levels if i - k < p["lookback"]]
            tol = p["tolerance_atr"] * av[i] if not np.isnan(av[i]) else 0
            # breaks
            for px, k in list(res_levels):
                if cl[i] > px + tol * 0.2 and cl[i - 1] <= px:
                    broken_res.append((px, i))
                    res_levels.remove((px, k))
            for px, k in list(sup_levels):
                if cl[i] < px - tol * 0.2 and cl[i - 1] >= px:
                    broken_sup.append((px, i))
                    sup_levels.remove((px, k))
            # retests
            for px, k in list(broken_res):
                if i - k > p["max_wait"] or cl[i] < px - tol:
                    broken_res.remove((px, k))
                    continue
                if i > k + 1 and lo[i] <= px + tol and cl[i] > px and cl[i] > df.open.values[i]:
                    long[i] = True
                    stop[i] = px - tol * 1.5
                    tgt[i] = cl[i] + 2.5 * (cl[i] - stop[i])
                    levels_out.append((px, "S/R", "#4caf50"))
                    broken_res.remove((px, k))
            for px, k in list(broken_sup):
                if i - k > p["max_wait"] or cl[i] > px + tol:
                    broken_sup.remove((px, k))
                    continue
                if i > k + 1 and hi[i] >= px - tol and cl[i] < px and cl[i] < df.open.values[i]:
                    short[i] = True
                    stop[i] = px + tol * 1.5
                    tgt[i] = cl[i] - 2.5 * (stop[i] - cl[i])
                    levels_out.append((px, "S/R", "#f44336"))
                    broken_sup.remove((px, k))
        sig = self.make_signal(pd.Series(long, index=df.index), pd.Series(short, index=df.index))
        return StrategyResult(sig, pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index), levels=levels_out[-12:])


class SupplyDemand(Strategy):
    id = "supply_demand"
    name_en = "Supply & Demand Zones (Rally-Base-Rally)"
    name_fa = "نواحی عرضه و تقاضا (RBR / DBD)"
    category = "Smart-Money"
    author = "Sam Seiden (Online Trading Academy)"
    difficulty = 4
    timeframes = "1h – 1d"
    params = {"base_max_bars": 3, "impulse_atr": 2.0, "zone_life": 150}
    description_en = ("Find a small 'base' (consolidation) followed by an explosive move — that base is where big orders sat. "
                      "When price returns to the fresh zone for the first time, trade the bounce.")
    description_fa = ("یک 'پایه' کوچک (تثبیت) پیدا کن که بعدش حرکت انفجاری آمده — آن پایه جایی است که سفارش‌های بزرگ بوده‌اند. "
                      "وقتی قیمت برای اولین بار به ناحیه تازه برمی‌گردد، برگشت را معامله کن.")
    rules_en = ["Demand zone: 1-3 small candles then a move ≥ 2 ATR up", "Zone = base low to base high",
                "Long: first return into zone with bullish close; stop below zone; target 3R", "Zone used once (fresh only)"]
    rules_fa = ["ناحیه تقاضا: ۱-۳ کندل کوچک و سپس حرکت ≥ ۲ ATR رو به بالا", "ناحیه = کف تا سقف پایه",
                "خرید: اولین بازگشت به ناحیه با بسته شدن صعودی؛ حد ضرر زیر ناحیه؛ هدف 3R", "هر ناحیه فقط یک‌بار (تازه)"]
    pros_en = ["Institutional logic", "Great R:R"]
    cons_en = ["Zone drawing is subjective", "Fresh zones can still fail"]
    pros_fa = ["منطق مؤسساتی", "ریسک به ریوارد عالی"]
    cons_fa = ["رسم ناحیه سلیقه‌ای است", "نواحی تازه هم می‌توانند شکست بخورند"]

    def run(self, df):
        p = self.p
        a = ta.atr(df)
        n = len(df)
        o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
        av = a.values
        long = np.zeros(n, dtype=bool)
        short = np.zeros(n, dtype=bool)
        stop = np.full(n, np.nan)
        tgt = np.full(n, np.nan)
        demand = []  # [lo, hi, created, fresh]
        supply = []
        zones_out = []
        for i in range(20, n):
            if np.isnan(av[i]):
                continue
            # detect impulse candle
            rng = h[i] - l[i]
            body = c[i] - o[i]
            if abs(body) >= p["impulse_atr"] * av[i] * 0.75 and rng >= p["impulse_atr"] * av[i]:
                # base = previous 1..base_max_bars small candles
                for k in range(1, p["base_max_bars"] + 1):
                    seg = slice(i - k, i)
                    if np.all(np.abs(c[seg] - o[seg]) < 0.5 * av[i]):
                        zlo, zhi = l[seg].min(), h[seg].max()
                        if zhi - zlo > 1.5 * av[i]:
                            continue
                        if body > 0:
                            demand.append([zlo, zhi, i, True])
                            zones_out.append((i - k, i, zlo, zhi, "#4caf50", "Demand"))
                        else:
                            supply.append([zlo, zhi, i, True])
                            zones_out.append((i - k, i, zlo, zhi, "#f44336", "Supply"))
                        break
            # retests
            for z in demand:
                if not z[3] or i - z[2] < 3 or i - z[2] > p["zone_life"]:
                    continue
                if c[i] < z[0]:  # broken
                    z[3] = False
                    continue
                if l[i] <= z[1] and c[i] > z[1] * 0.999 and c[i] > o[i]:
                    long[i] = True
                    stop[i] = z[0] - 0.3 * av[i]
                    tgt[i] = c[i] + 3 * (c[i] - stop[i])
                    z[3] = False
            for z in supply:
                if not z[3] or i - z[2] < 3 or i - z[2] > p["zone_life"]:
                    continue
                if c[i] > z[1]:
                    z[3] = False
                    continue
                if h[i] >= z[0] and c[i] < z[0] * 1.001 and c[i] < o[i]:
                    short[i] = True
                    stop[i] = z[1] + 0.3 * av[i]
                    tgt[i] = c[i] - 3 * (stop[i] - c[i])
                    z[3] = False
        sig = self.make_signal(pd.Series(long, index=df.index), pd.Series(short, index=df.index))
        return StrategyResult(sig, pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index), zones=zones_out[-20:])


class ICTFairValueGap(Strategy):
    id = "ict_fvg"
    name_en = "ICT Fair Value Gap (FVG) Entry"
    name_fa = "ورود در گپ ارزش منصفانه (ICT FVG)"
    category = "Smart-Money"
    author = "Michael J. Huddleston (ICT — Inner Circle Trader)"
    difficulty = 4
    timeframes = "5m – 4h"
    params = {"min_gap_atr": 0.3, "gap_life": 40, "bias_ema": 50}
    description_en = ("A 3-candle imbalance where candle 1 high < candle 3 low (bullish FVG). Price tends to return to fill "
                      "the gap; enter when it trades into the FVG in the direction of higher-timeframe bias.")
    description_fa = ("عدم تعادل ۳ کندلی که سقف کندل ۱ < کف کندل ۳ (FVG صعودی). قیمت تمایل دارد برگردد و گپ را پر کند؛ "
                      "وقتی وارد FVG شد، در جهت بایاس تایم بالاتر وارد شو.")
    rules_en = ["Bullish FVG: high[i-2] < low[i] with displacement candle in between", "Bias: price > EMA50",
                "Entry: price retraces into FVG and closes bullish", "Stop: below FVG low (or candle 1 low), target 2-3R"]
    rules_fa = ["FVG صعودی: سقف کندل i-2 < کف کندل i با کندل جابه‌جایی وسط", "بایاس: قیمت > EMA50",
                "ورود: قیمت به FVG برگردد و صعودی بسته شود", "حد ضرر: زیر کف FVG، هدف 2-3R"]
    pros_en = ["Precise entries", "Very popular in 2020s"]
    cons_en = ["Many FVGs — needs confluence (OB, liquidity, session time)"]
    pros_fa = ["ورودهای دقیق", "بسیار محبوب در دهه ۲۰۲۰"]
    cons_fa = ["FVG زیاد است — نیاز به هم‌راستایی (اوردربلاک، نقدینگی، سشن)"]

    def run(self, df):
        p = self.p
        a = ta.atr(df)
        e = ta.ema(df.close, p["bias_ema"])
        n = len(df)
        h, l, c, o = df.high.values, df.low.values, df.close.values, df.open.values
        av, ev = a.values, e.values
        long = np.zeros(n, dtype=bool)
        short = np.zeros(n, dtype=bool)
        stop = np.full(n, np.nan)
        tgt = np.full(n, np.nan)
        bull_gaps, bear_gaps, zones_out = [], [], []
        for i in range(3, n):
            if np.isnan(av[i]):
                continue
            # new FVGs formed at i (candles i-2, i-1, i)
            if l[i] > h[i - 2] and (l[i] - h[i - 2]) >= p["min_gap_atr"] * av[i] and abs(c[i - 1] - o[i - 1]) > av[i]:
                bull_gaps.append([h[i - 2], l[i], i, True])
                zones_out.append((i - 2, i + 5, h[i - 2], l[i], "#26a69a", "FVG+"))
            if h[i] < l[i - 2] and (l[i - 2] - h[i]) >= p["min_gap_atr"] * av[i] and abs(c[i - 1] - o[i - 1]) > av[i]:
                bear_gaps.append([h[i], l[i - 2], i, True])
                zones_out.append((i - 2, i + 5, h[i], l[i - 2], "#ef5350", "FVG-"))
            for g in bull_gaps:
                if not g[3] or i - g[2] > p["gap_life"] or i == g[2]:
                    continue
                if c[i] < g[0]:
                    g[3] = False
                    continue
                if l[i] <= g[1] and c[i] > g[0] and c[i] > o[i] and c[i] > ev[i]:
                    long[i] = True
                    stop[i] = g[0] - 0.5 * av[i]
                    tgt[i] = c[i] + 2.5 * (c[i] - stop[i])
                    g[3] = False
            for g in bear_gaps:
                if not g[3] or i - g[2] > p["gap_life"] or i == g[2]:
                    continue
                if c[i] > g[1]:
                    g[3] = False
                    continue
                if h[i] >= g[0] and c[i] < g[1] and c[i] < o[i] and c[i] < ev[i]:
                    short[i] = True
                    stop[i] = g[1] + 0.5 * av[i]
                    tgt[i] = c[i] - 2.5 * (stop[i] - c[i])
                    g[3] = False
        sig = self.make_signal(pd.Series(long, index=df.index), pd.Series(short, index=df.index))
        return StrategyResult(sig, pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index),
                              overlays={"EMA50": e}, zones=zones_out[-25:])


class ICTOrderBlock(Strategy):
    id = "ict_ob"
    name_en = "ICT Order Block + Break of Structure"
    name_fa = "اوردر بلاک ICT با شکست ساختار (BOS)"
    category = "Smart-Money"
    author = "ICT / Smart Money Concepts (SMC)"
    difficulty = 5
    timeframes = "15m – 4h"
    params = {"swing": 5, "ob_life": 60}
    description_en = ("The last opposite candle before an impulsive move that breaks structure (BOS) is an Order Block — "
                      "where institutions entered. Return to the OB = high-probability continuation entry.")
    description_fa = ("آخرین کندل مخالف قبل از حرکت ایمپالسیو که ساختار را می‌شکند (BOS) اوردر بلاک است — "
                      "جایی که مؤسسات وارد شده‌اند. بازگشت به OB = ورود ادامه‌دهنده با احتمال بالا.")
    rules_en = ["BOS up: close above last swing high", "Bullish OB: last bearish candle before the BOS leg",
                "Entry: price returns to OB (high of OB) and closes bullish", "Stop: OB low, target: 3R or next swing high"]
    rules_fa = ["BOS صعودی: بسته شدن بالای آخرین سقف سوئینگ", "OB صعودی: آخرین کندل نزولی قبل از لگ BOS",
                "ورود: قیمت به OB برگردد (سقف OB) و صعودی بسته شود", "حد ضرر: کف OB، هدف: 3R یا سقف سوئینگ بعدی"]
    pros_en = ["Excellent R:R (often 1:3+)", "Aligns with institutional flow"]
    cons_en = ["Steep learning curve", "Highly discretionary in practice"]
    pros_fa = ["ریسک به ریوارد عالی (اغلب ۱:۳+)", "هم‌راستا با جریان مؤسساتی"]
    cons_fa = ["منحنی یادگیری سخت", "در عمل بسیار سلیقه‌ای"]

    def run(self, df):
        p = self.p
        sw = p["swing"]
        sh, sl = ta.swing_points(df, sw, sw)
        a = ta.atr(df)
        n = len(df)
        h, l, c, o = df.high.values, df.low.values, df.close.values, df.open.values
        av = a.values
        long = np.zeros(n, dtype=bool)
        short = np.zeros(n, dtype=bool)
        stop = np.full(n, np.nan)
        tgt = np.full(n, np.nan)
        last_sh, last_sl = None, None
        bull_obs, bear_obs, zones_out = [], [], []
        for i in range(sw * 2 + 1, n):
            j = i - sw
            if sh.values[j]:
                last_sh = (h[j], j)
            if sl.values[j]:
                last_sl = (l[j], j)
            if np.isnan(av[i]):
                continue
            # BOS up
            if last_sh and c[i] > last_sh[0] and c[i - 1] <= last_sh[0]:
                # find last bearish candle between last swing low and now
                start = last_sl[1] if last_sl else max(0, i - 20)
                for k in range(i - 1, start - 1, -1):
                    if c[k] < o[k]:
                        bull_obs.append([l[k], h[k], i, True])
                        zones_out.append((k, i + 10, l[k], h[k], "#2196f3", "OB+"))
                        break
                last_sh = None
            if last_sl and c[i] < last_sl[0] and c[i - 1] >= last_sl[0]:
                start = last_sh[1] if last_sh else max(0, i - 20)
                for k in range(i - 1, start - 1, -1):
                    if c[k] > o[k]:
                        bear_obs.append([l[k], h[k], i, True])
                        zones_out.append((k, i + 10, l[k], h[k], "#ff9800", "OB-"))
                        break
                last_sl = None
            for ob in bull_obs:
                if not ob[3] or i - ob[2] > p["ob_life"] or i <= ob[2] + 1:
                    continue
                if c[i] < ob[0]:
                    ob[3] = False
                    continue
                if l[i] <= ob[1] and c[i] > ob[1] * 0.999 and c[i] > o[i]:
                    long[i] = True
                    stop[i] = ob[0] - 0.3 * av[i]
                    tgt[i] = c[i] + 3 * (c[i] - stop[i])
                    ob[3] = False
            for ob in bear_obs:
                if not ob[3] or i - ob[2] > p["ob_life"] or i <= ob[2] + 1:
                    continue
                if c[i] > ob[1]:
                    ob[3] = False
                    continue
                if h[i] >= ob[0] and c[i] < ob[0] * 1.001 and c[i] < o[i]:
                    short[i] = True
                    stop[i] = ob[1] + 0.3 * av[i]
                    tgt[i] = c[i] - 3 * (stop[i] - c[i])
                    ob[3] = False
        sig = self.make_signal(pd.Series(long, index=df.index), pd.Series(short, index=df.index))
        return StrategyResult(sig, pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index), zones=zones_out[-20:])


class LiquiditySweep(Strategy):
    id = "liquidity_sweep"
    name_en = "Liquidity Sweep / Stop Hunt Reversal"
    name_fa = "برگشت بعد از شکار نقدینگی (استاپ هانت)"
    category = "Smart-Money"
    author = "ICT 'Turtle Soup' / Linda Raschke"
    difficulty = 4
    timeframes = "15m – 4h"
    params = {"lookback": 20, "swing": 3}
    description_en = ("Price spikes beyond an obvious swing high/low (where retail stops sit), then closes back inside. "
                      "Smart money grabbed liquidity — trade the reversal.")
    description_fa = ("قیمت از سوئینگ واضح (جایی که استاپ‌های خرده‌فروش‌ها هست) رد می‌شود، بعد داخل بسته می‌شود. "
                      "پول هوشمند نقدینگی را جمع کرد — برگشت را معامله کن.")
    rules_en = ["Bullish sweep: low < lowest low of prior 20 bars, but close > that low (wick below)",
                "Confirm: close > open", "Stop: below the sweep wick, target: opposite side of range / 2.5R"]
    rules_fa = ["سوییپ صعودی: کف < پایین‌ترین کف ۲۰ کندل قبل، ولی بسته شدن بالای آن (سایه زیر)",
                "تأیید: بسته > باز", "حد ضرر: زیر سایه سوییپ، هدف: سمت دیگر رنج / 2.5R"]
    pros_en = ["Explains 'why did it stop me out then reverse?'", "Tight stop"]
    cons_en = ["Real breakouts look identical at first"]
    pros_fa = ["توضیح می‌دهد چرا استاپم خورد و برگشت", "حد ضرر کوچک"]
    cons_fa = ["شکست‌های واقعی در ابتدا یکسان به نظر می‌رسند"]

    def run(self, df):
        p = self.p
        a = ta.atr(df)
        ll = df.low.rolling(p["lookback"]).min().shift(1)
        hh = df.high.rolling(p["lookback"]).max().shift(1)
        bull = (df.low < ll) & (df.close > ll) & (df.close > df.open) & ((ll - df.low) > 0.15 * a)
        bear = (df.high > hh) & (df.close < hh) & (df.close < df.open) & ((df.high - hh) > 0.15 * a)
        sig = self.make_signal(bull, bear)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.low[sig == 1] - 0.2 * a[sig == 1]
        stop[sig == -1] = df.high[sig == -1] + 0.2 * a[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2.5 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2.5 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"Range High": hh, "Range Low": ll})


class BOSMarketStructure(Strategy):
    id = "market_structure"
    name_en = "Market Structure Shift (CHoCH) Trend Trading"
    name_fa = "تغییر ساختار بازار (CHoCH) — روندگیری ساختاری"
    category = "Smart-Money"
    author = "SMC community / Al Brooks (price action)"
    difficulty = 3
    timeframes = "1h – 1d"
    params = {"swing": 4}
    description_en = ("Track HH/HL vs LH/LL. A Change of Character (first break against the trend) plus a retest of the "
                      "broken swing = new trend entry.")
    description_fa = ("HH/HL در برابر LH/LL را دنبال کن. تغییر کاراکتر (اولین شکست خلاف روند) به‌علاوه پولبک به سوئینگ شکسته‌شده "
                      "= ورود به روند جدید.")
    rules_en = ["Downtrend = series of LH/LL", "CHoCH: close above last LH", "Entry: pullback to the broken LH and bullish close",
                "Stop below last swing low"]
    rules_fa = ["روند نزولی = سری LH/LL", "CHoCH: بسته شدن بالای آخرین LH", "ورود: پولبک به LH شکسته‌شده و بسته شدن صعودی",
                "حد ضرر زیر آخرین کف سوئینگ"]
    pros_en = ["Pure price, no indicators", "Early trend entries"]
    cons_en = ["Swing identification is parameter-sensitive"]
    pros_fa = ["قیمت خالص، بدون اندیکاتور", "ورود زودهنگام به روند"]
    cons_fa = ["شناسایی سوئینگ حساس به پارامتر است"]

    def run(self, df):
        sw = self.p["swing"]
        sh, sl = ta.swing_points(df, sw, sw)
        a = ta.atr(df)
        n = len(df)
        h, l, c, o = df.high.values, df.low.values, df.close.values, df.open.values
        av = a.values
        long = np.zeros(n, dtype=bool)
        short = np.zeros(n, dtype=bool)
        stop = np.full(n, np.nan)
        tgt = np.full(n, np.nan)
        highs, lows = [], []
        trend = 0
        pending = None  # ("long", level, sl_level, idx)
        for i in range(sw * 2 + 1, n):
            j = i - sw
            if sh.values[j]:
                highs.append((h[j], j))
            if sl.values[j]:
                lows.append((l[j], j))
            if len(highs) >= 2 and len(lows) >= 2:
                if highs[-1][0] > highs[-2][0] and lows[-1][0] > lows[-2][0]:
                    trend = 1
                elif highs[-1][0] < highs[-2][0] and lows[-1][0] < lows[-2][0]:
                    trend = -1
            if np.isnan(av[i]):
                continue
            if trend == -1 and highs and c[i] > highs[-1][0] and c[i - 1] <= highs[-1][0]:
                pending = ("long", highs[-1][0], lows[-1][0] if lows else l[i] - av[i], i)
                trend = 0
            if trend == 1 and lows and c[i] < lows[-1][0] and c[i - 1] >= lows[-1][0]:
                pending = ("short", lows[-1][0], highs[-1][0] if highs else h[i] + av[i], i)
                trend = 0
            if pending:
                side, lvl, slv, k = pending
                if i - k > 25:
                    pending = None
                elif side == "long" and i > k and l[i] <= lvl + 0.3 * av[i] and c[i] > lvl and c[i] > o[i]:
                    long[i] = True
                    stop[i] = min(slv, lvl - av[i])
                    tgt[i] = c[i] + 2.5 * (c[i] - stop[i])
                    pending = None
                elif side == "short" and i > k and h[i] >= lvl - 0.3 * av[i] and c[i] < lvl and c[i] < o[i]:
                    short[i] = True
                    stop[i] = max(slv, lvl + av[i])
                    tgt[i] = c[i] - 2.5 * (stop[i] - c[i])
                    pending = None
        sig = self.make_signal(pd.Series(long, index=df.index), pd.Series(short, index=df.index))
        return StrategyResult(sig, pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index))


class WyckoffSpring(Strategy):
    id = "wyckoff_spring"
    name_en = "Wyckoff Spring / Upthrust"
    name_fa = "اسپرینگ / آپ‌تراست وایکوف"
    category = "Smart-Money"
    author = "Richard D. Wyckoff (1930s)"
    difficulty = 4
    timeframes = "4h – 1d"
    params = {"range_bars": 40, "range_max_atr": 6.0}
    description_en = ("After a trading range (accumulation), a 'spring' dips below range support on low volume and "
                      "snaps back — the final shakeout before markup. Upthrust is the mirror in distribution.")
    description_fa = ("بعد از یک رنج معاملاتی (انباشت)، 'اسپرینگ' با حجم کم زیر حمایت رنج می‌رود و "
                      "سریع برمی‌گردد — آخرین تکان قبل از صعود. آپ‌تراست برعکس آن در توزیع است.")
    rules_en = ["Range: 40 bars with height < 6 ATR", "Spring: low breaks range low, close back inside, volume < average",
                "Long on spring bar close; stop below spring low; target range top then beyond"]
    rules_fa = ["رنج: ۴۰ کندل با ارتفاع < ۶ ATR", "اسپرینگ: کف زیر کف رنج، بسته شدن داخل، حجم < میانگین",
                "خرید در بسته شدن کندل اسپرینگ؛ حد ضرر زیر کف اسپرینگ؛ هدف سقف رنج و فراتر"]
    pros_en = ["Explains accumulation/distribution", "Great R:R"]
    cons_en = ["Rare setups", "Needs volume"]
    pros_fa = ["انباشت/توزیع را توضیح می‌دهد", "ریسک به ریوارد عالی"]
    cons_fa = ["ستاپ‌های کمیاب", "نیاز به حجم"]

    def run(self, df):
        p = self.p
        a = ta.atr(df)
        rb = p["range_bars"]
        hh = df.high.rolling(rb).max().shift(1)
        ll = df.low.rolling(rb).min().shift(1)
        in_range = (hh - ll) < p["range_max_atr"] * a
        vol_ok = df.volume < df.volume.rolling(20).mean() if df.volume.sum() > 0 else pd.Series(True, index=df.index)
        spring = in_range & (df.low < ll) & (df.close > ll) & (df.close > df.open) & vol_ok
        upthrust = in_range & (df.high > hh) & (df.close < hh) & (df.close < df.open) & vol_ok
        sig = self.make_signal(spring, upthrust)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.low[sig == 1] - 0.3 * a[sig == 1]
        stop[sig == -1] = df.high[sig == -1] + 0.3 * a[sig == -1]
        tgt[sig == 1] = hh[sig == 1]
        tgt[sig == -1] = ll[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"Range High": hh, "Range Low": ll})


class ThreeBarReversal(Strategy):
    id = "morning_evening_star"
    name_en = "Morning / Evening Star"
    name_fa = "ستاره صبحگاهی / شامگاهی"
    category = "Price-Action"
    author = "Steve Nison (Japanese candlesticks)"
    difficulty = 1
    timeframes = "4h – 1d"
    params = {"rsi_filter": True}
    description_en = "Three-candle reversal: big red, small indecision, big green closing above midpoint of candle 1."
    description_fa = "برگشت سه کندلی: قرمز بزرگ، کندل کوچک بلاتکلیف، سبز بزرگ که بالای نیمه کندل ۱ بسته می‌شود."
    rules_en = ["Morning star: candle1 bearish body > ATR·0.6, candle2 body < 0.3·ATR, candle3 bullish closes > mid of candle1",
                "Filter: RSI < 45 for morning star, > 55 for evening star"]
    rules_fa = ["ستاره صبحگاهی: کندل۱ نزولی بدنه > ۰.۶ATR، کندل۲ بدنه < ۰.۳ATR، کندل۳ صعودی بالای نیمه کندل۱",
                "فیلتر: RSI < ۴۵ برای صبحگاهی، > ۵۵ برای شامگاهی"]
    pros_en = ["Strong reversal pattern"]
    cons_en = ["Rare, must be at level"]
    pros_fa = ["الگوی برگشتی قوی"]
    cons_fa = ["کمیاب، باید در سطح باشد"]

    def run(self, df):
        a = ta.atr(df)
        r = ta.rsi(df.close)
        b = df.close - df.open
        b1, b2 = b.shift(2), b.shift(1)
        mid1 = (df.open.shift(2) + df.close.shift(2)) / 2
        bull = (b1 < -0.6 * a) & (b2.abs() < 0.3 * a) & (b > 0.6 * a) & (df.close > mid1)
        bear = (b1 > 0.6 * a) & (b2.abs() < 0.3 * a) & (b < -0.6 * a) & (df.close < mid1)
        if self.p["rsi_filter"]:
            bull &= r < 45
            bear &= r > 55
        sig = self.make_signal(bull, bear)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.low.rolling(3).min()[sig == 1] - 0.2 * a[sig == 1]
        stop[sig == -1] = df.high.rolling(3).max()[sig == -1] + 0.2 * a[sig == -1]
        risk = (df.close - stop).abs()
        tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]
        tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        return StrategyResult(sig, stop, tgt, panels={"RSI": {"RSI": r}})


class FibPullback(Strategy):
    id = "fib_pullback"
    name_en = "Fibonacci 0.5–0.618 Pullback (Golden Zone)"
    name_fa = "پولبک فیبوناچی ۰.۵–۰.۶۱۸ (ناحیه طلایی)"
    category = "Price-Action"
    author = "Classic; ICT 'OTE' variant"
    difficulty = 3
    timeframes = "1h – 1d"
    params = {"swing": 5, "lo": 0.5, "hi": 0.705, "ema": 100}
    description_en = ("After an impulse leg (swing low → swing high), wait for a retracement into the 50–70.5% zone and a "
                      "bullish rejection. Stop below the swing low, target the prior high and beyond.")
    description_fa = ("بعد از لگ ایمپالسیو (کف سوئینگ ← سقف سوئینگ)، منتظر اصلاح به ناحیه ۵۰–۷۰.۵٪ و رد شدن صعودی باش. "
                      "حد ضرر زیر کف سوئینگ، هدف سقف قبلی و فراتر.")
    rules_en = ["Trend: price > EMA100", "Leg: last swing low to last swing high", "Entry: low enters golden zone, close above zone bottom, green candle",
                "Stop: swing low, TP1: swing high, TP2: 1.272 extension"]
    rules_fa = ["روند: قیمت > EMA100", "لگ: آخرین کف سوئینگ تا آخرین سقف سوئینگ", "ورود: کف وارد ناحیه طلایی، بسته شدن بالای کف ناحیه، کندل سبز",
                "حد ضرر: کف سوئینگ، هدف۱: سقف سوئینگ، هدف۲: اکستنشن ۱.۲۷۲"]
    pros_en = ["Objective zone", "Excellent R:R"]
    cons_en = ["Which swing to use is subjective"]
    pros_fa = ["ناحیه عینی", "ریسک به ریوارد عالی"]
    cons_fa = ["انتخاب سوئینگ سلیقه‌ای است"]

    def run(self, df):
        p = self.p
        sw = p["swing"]
        sh, sl = ta.swing_points(df, sw, sw)
        e = ta.ema(df.close, p["ema"])
        a = ta.atr(df)
        n = len(df)
        h, l, c, o = df.high.values, df.low.values, df.close.values, df.open.values
        long = np.zeros(n, dtype=bool)
        short = np.zeros(n, dtype=bool)
        stop = np.full(n, np.nan)
        tgt = np.full(n, np.nan)
        last_lo = last_hi = None
        used = set()
        for i in range(sw * 2 + 1, n):
            j = i - sw
            if sl.values[j]:
                last_lo = (l[j], j)
            if sh.values[j]:
                last_hi = (h[j], j)
            if not last_lo or not last_hi:
                continue
            # bullish leg: low before high
            if last_lo[1] < last_hi[1] and c[i] > e.values[i] and (last_hi[0], last_lo[0]) not in used:
                rng = last_hi[0] - last_lo[0]
                z_hi = last_hi[0] - rng * p["lo"]
                z_lo = last_hi[0] - rng * p["hi"]
                if l[i] <= z_hi and c[i] > z_lo and c[i] > o[i] and i > last_hi[1] + sw:
                    long[i] = True
                    stop[i] = last_lo[0] - 0.2 * a.values[i]
                    tgt[i] = last_hi[0] + 0.272 * rng
                    used.add((last_hi[0], last_lo[0]))
            if last_hi[1] < last_lo[1] and c[i] < e.values[i] and (last_hi[0], last_lo[0]) not in used:
                rng = last_hi[0] - last_lo[0]
                z_lo = last_lo[0] + rng * p["lo"]
                z_hi = last_lo[0] + rng * p["hi"]
                if h[i] >= z_lo and c[i] < z_hi and c[i] < o[i] and i > last_lo[1] + sw:
                    short[i] = True
                    stop[i] = last_hi[0] + 0.2 * a.values[i]
                    tgt[i] = last_lo[0] - 0.272 * rng
                    used.add((last_hi[0], last_lo[0]))
        sig = self.make_signal(pd.Series(long, index=df.index), pd.Series(short, index=df.index))
        return StrategyResult(sig, pd.Series(stop, index=df.index), pd.Series(tgt, index=df.index), overlays={"EMA100": e})


class OpeningRangeBreakout(Strategy):
    id = "orb"
    name_en = "Opening Range Breakout (ORB)"
    name_fa = "شکست رنج ابتدای سشن (ORB)"
    category = "Price-Action"
    author = "Toby Crabel; popularised for stocks & indices"
    difficulty = 2
    timeframes = "5m – 1h (intraday)"
    params = {"range_bars": 2, "session_hour": 13}  # 13:30 UTC = NYSE open; adjust per market
    description_en = "Range of the first N bars after session open defines the day's battleground. Trade the first break."
    description_fa = "رنج N کندل اول بعد از باز شدن سشن، میدان نبرد روز را مشخص می‌کند. اولین شکست را معامله کن."
    rules_en = ["Range = high/low of first N bars after session open", "Long: close above range high", "Stop: range mid; target 2R"]
    rules_fa = ["رنج = سقف/کف N کندل اول بعد از باز شدن سشن", "خرید: بسته شدن بالای سقف رنج", "حد ضرر: وسط رنج؛ هدف 2R"]
    pros_en = ["Exploits opening volatility"]
    cons_en = ["Intraday data only; session timing must match market"]
    pros_fa = ["از نوسان ابتدای سشن استفاده می‌کند"]
    cons_fa = ["فقط داده روزانه؛ زمان سشن باید با بازار بخواند"]

    def run(self, df):
        p = self.p
        n = len(df)
        sig = pd.Series(0, index=df.index)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        if not isinstance(df.index, pd.DatetimeIndex) or n < 50:
            return StrategyResult(sig, stop, tgt)
        day = df.index.normalize()
        hours = df.index.hour
        grp = pd.Series(np.arange(n), index=df.index).groupby(day)
        rh = pd.Series(np.nan, index=df.index)
        rl = pd.Series(np.nan, index=df.index)
        for d, idxs in grp:
            idxs = idxs.values
            # session start = first bar at/after session_hour
            start = [k for k in idxs if hours[k] >= p["session_hour"]]
            if len(start) < p["range_bars"] + 1:
                continue
            s0 = start[0]
            rng = slice(s0, s0 + p["range_bars"])
            hh, ll = df.high.values[rng].max(), df.low.values[rng].min()
            done = False
            for k in range(s0 + p["range_bars"], idxs[-1] + 1):
                rh.iloc[k], rl.iloc[k] = hh, ll
                if done:
                    continue
                if df.close.values[k] > hh:
                    sig.iloc[k] = 1
                    stop.iloc[k] = (hh + ll) / 2
                    tgt.iloc[k] = df.close.values[k] + 2 * (df.close.values[k] - stop.iloc[k])
                    done = True
                elif df.close.values[k] < ll:
                    sig.iloc[k] = -1
                    stop.iloc[k] = (hh + ll) / 2
                    tgt.iloc[k] = df.close.values[k] - 2 * (stop.iloc[k] - df.close.values[k])
                    done = True
        return StrategyResult(sig, stop, tgt, overlays={"OR High": rh, "OR Low": rl})
