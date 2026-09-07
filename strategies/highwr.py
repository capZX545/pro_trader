"""
High-win-rate family — the strategies behind the published 70–80 % win-rate claims, implemented EXACTLY as their
authors define them (Connors/Alvarez "Short Term Trading Strategies That Work", quantifiedstrategies.com, Reddit
20-year constituent backtests). Their common DNA:
  • Daily bars on liquid stocks / indices / ETFs, long-only, above the 200-day SMA (bull regime)
  • Buy a short, sharp pullback (RSI(2) < 10, 7-day low, 3 down closes, IBS < 0.2 …)
  • Exit on a CONDITION (close > 5-SMA, RSI(2) > 65/70, first up close) — NOT a fixed target
  • NO tight stop (a tight stop is what turns a 75 % system into a 45 % one); only a wide disaster stop / time stop
Result: many small wins, few larger losses. Win rate 65–80 %, payoff ≈ 0.6–0.8, PF ≈ 1.3–1.6 — honest numbers.
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta


def _flat():
    return None


class _HighWR(Strategy):
    category = "High Win-Rate"
    timeframes = "1d (stocks / indices / BTC-ETH daily)"
    disaster_atr = 6.0          # very wide safety stop only
    bt_kwargs = {"max_bars": 10, "allow_short": False}   # Connors: time stop 10 bars, long-only

    def _pack(self, df, long, exit_rule, overlays=None, panels=None, short=None, exit_short=None):
        a = ta.atr(df)
        long = long & ~long.shift(1).fillna(False).astype(bool)
        if short is None:
            short = pd.Series(False, index=df.index)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.close[sig == 1] - self.disaster_atr * a[sig == 1]
        tgt[sig == 1] = df.close[sig == 1] + 30 * a[sig == 1]      # effectively no target: exit is rule-based
        stop[sig == -1] = df.close[sig == -1] + self.disaster_atr * a[sig == -1]
        tgt[sig == -1] = df.close[sig == -1] - 30 * a[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays=overlays or {}, panels=panels or {},
                              exit_long=exit_rule, exit_short=exit_short, bt_kwargs=dict(self.bt_kwargs))


class ConnorsRSI2Classic(_HighWR):
    id = "connors_rsi2_classic"
    name_en = "Connors RSI(2) Classic — 75–79% WR on SPY/S&P stocks (published)"
    name_fa = "کانرز RSI(2) کلاسیک — وین‌ریت ۷۵–۷۹٪ روی SPY/سهام S&P (منتشرشده)"
    author = "Larry Connors & Cesar Alvarez, 2008 — verified by quantifiedstrategies.com (76% WR), Reddit 20-yr constituents (68% WR, PF 1.59)"
    difficulty = 1
    params = {"rsi_buy": 10, "rsi_exit": 65, "sma_trend": 200, "sma_exit": 5}
    description_en = ("THE high-win-rate benchmark. Buy a stock above its 200-day SMA when RSI(2) < 10; exit when RSI(2) > 65 OR close > 5-SMA. "
                      "No target, no tight stop — that is exactly why the win rate is high (and the payoff below 1).")
    description_fa = ("معیار وین‌ریت بالا. سهم بالای SMA۲۰۰ روزانه را وقتی RSI(2) < ۱۰ بخر؛ وقتی RSI(2) > ۶۵ یا بسته > SMA۵ خارج شو. "
                      "بدون هدف، بدون استاپ تنگ — دقیقاً به همین دلیل وین‌ریت بالاست (و payoff زیر ۱).")
    rules_en = ["Close > SMA200", "RSI(2) < 10 (enter at next open)", "Exit: RSI(2) > 65 OR close > SMA5", "Disaster stop 6 ATR, time stop 10 bars"]
    rules_fa = ["بسته > SMA200", "RSI(2) < ۱۰ (ورود در باز شدن بعدی)", "خروج: RSI(2) > ۶۵ یا بسته > SMA5", "استاپ اضطراری ۶ ATR، استاپ زمانی ۱۰ کندل"]
    pros_en = ["Highest verified win rate of any public system", "Only ~18% time in market"]
    cons_en = ["Bear markets: WR drops < 60%", "Payoff < 1 — one crash trade erases several wins", "Stocks/indices only; weak on crypto intraday"]
    pros_fa = ["بالاترین وین‌ریت تأییدشده بین سیستم‌های عمومی", "فقط ~۱۸٪ زمان در بازار"]
    cons_fa = ["بازار خرسی: وین‌ریت < ۶۰٪", "payoff < ۱ — یک معاملهٔ سقوط چند برد را پاک می‌کند", "فقط سهام/شاخص؛ روی کریپتوی درون‌روزی ضعیف"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, 2)
        s200 = ta.sma(df.close, p["sma_trend"]); s5 = ta.sma(df.close, p["sma_exit"])
        long = (df.close > s200) & (r < p["rsi_buy"])
        exit_ = (r > p["rsi_exit"]) | (df.close > s5)
        return self._pack(df, long, exit_, overlays={"SMA200": s200, "SMA5": s5}, panels={"RSI(2)": {"RSI2": r}})


class CumulativeRSI2(_HighWR):
    id = "cum_rsi2"
    name_en = "Cumulative RSI(2) — 2-day sum < 35 (Connors)"
    name_fa = "RSI(2) تجمعی — مجموع ۲ روزه < ۳۵ (کانرز)"
    author = "Connors & Alvarez — 'Cumulative RSI' chapter; sustained-selling variant (68–75% WR)"
    difficulty = 1
    params = {"cum_n": 2, "cum_below": 35, "rsi_exit": 65}
    description_en = "Sum of the last 2 RSI(2) readings below 35 above SMA200 = sustained (not one-day) selling exhaustion; exit RSI(2) > 65."
    description_fa = "مجموع دو RSI(2) آخر زیر ۳۵ بالای SMA۲۰۰ = فرسودگی فروش پایدار (نه یک‌روزه)؛ خروج RSI(2) > ۶۵."
    rules_en = ["Close > SMA200", "RSI(2)[t] + RSI(2)[t-1] < 35", "Exit: RSI(2) > 65"]
    rules_fa = ["بسته > SMA200", "RSI(2)[t] + RSI(2)[t-1] < ۳۵", "خروج: RSI(2) > ۶۵"]
    pros_en = ["Fewer false dips than single-day RSI(2)"]; cons_en = ["Fewer trades"]
    pros_fa = ["دیپ‌های کاذب کمتر از RSI(2) تک‌روزه"]; cons_fa = ["معاملات کمتر"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, 2)
        cum = r.rolling(p["cum_n"]).sum()
        s200 = ta.sma(df.close, 200)
        long = (df.close > s200) & (cum < p["cum_below"])
        return self._pack(df, long, r > p["rsi_exit"], overlays={"SMA200": s200}, panels={"Cum RSI(2)": {"cum": cum}})


class Double7(_HighWR):
    id = "double7"
    name_en = "Connors Double 7 — 74% WR (Reddit 2024 backtest)"
    name_fa = "دابل ۷ کانرز — وین‌ریت ۷۴٪ (بک‌تست ردیت ۲۰۲۴)"
    author = "Connors 'Short Term Trading Strategies That Work' — r/Daytrading 2024: 74% WR, R:R 0.66, 18% time in market"
    difficulty = 1
    params = {"n": 7, "sma_trend": 200}
    description_en = "Above SMA200, buy when close is a 7-day low; sell when close is a 7-day high (or close > SMA5 variant)."
    description_fa = "بالای SMA۲۰۰، وقتی بسته کف ۷ روزه است بخر؛ وقتی بسته سقف ۷ روزه شد بفروش (یا نسخهٔ بسته > SMA۵)."
    rules_en = ["Close > SMA200", "Close = lowest close of 7 days", "Exit: close = highest close of 7 days OR close > SMA5"]
    rules_fa = ["بسته > SMA200", "بسته = پایین‌ترین بستهٔ ۷ روز", "خروج: بسته = بالاترین بستهٔ ۷ روز یا بسته > SMA5"]
    pros_en = ["Two rules, fully mechanical"]; cons_en = ["Doesn't beat buy&hold in raging bulls"]
    pros_fa = ["دو قانون، کاملاً مکانیکی"]; cons_fa = ["در گاوهای وحشی از خرید و نگهداری عقب می‌ماند"]

    def run(self, df):
        p = self.p
        s200 = ta.sma(df.close, p["sma_trend"]); s5 = ta.sma(df.close, 5)
        long = (df.close > s200) & (df.close <= df.close.rolling(p["n"]).min())
        exit_ = (df.close >= df.close.rolling(p["n"]).max()) | (df.close > s5)
        return self._pack(df, long, exit_, overlays={"SMA200": s200, "SMA5": s5})


class ThreeDayHighLow(_HighWR):
    id = "three_down_days"
    name_en = "3 Lower Lows + Lower Highs above SMA200 (Connors)"
    name_fa = "۳ کف پایین‌تر + سقف پایین‌تر بالای SMA۲۰۰ (کانرز)"
    author = "Connors '3 Day High/Low' — 70%+ WR on indices"
    difficulty = 1
    params = {"days": 3}
    description_en = "Three consecutive bars with lower highs AND lower lows, above SMA200 and below SMA5 → buy; exit close > SMA5."
    description_fa = "سه کندل متوالی با سقف و کف پایین‌تر، بالای SMA۲۰۰ و زیر SMA۵ ← خرید؛ خروج بسته > SMA۵."
    rules_en = ["Close > SMA200 and close < SMA5", "3 consecutive lower highs & lower lows", "Exit: close > SMA5"]
    rules_fa = ["بسته > SMA200 و بسته < SMA5", "۳ سقف و کف پایین‌تر متوالی", "خروج: بسته > SMA5"]
    pros_en = ["Pure price action, no oscillator"]; cons_en = ["Rare"]
    pros_fa = ["پرایس‌اکشن خالص"]; cons_fa = ["نادر"]

    def run(self, df):
        d = self.p["days"]
        s200 = ta.sma(df.close, 200); s5 = ta.sma(df.close, 5)
        lh = pd.Series(True, index=df.index); ll = pd.Series(True, index=df.index)
        for i in range(d):
            lh &= df.high.shift(i) < df.high.shift(i + 1)
            ll &= df.low.shift(i) < df.low.shift(i + 1)
        long = (df.close > s200) & (df.close < s5) & lh & ll
        return self._pack(df, long, df.close > s5, overlays={"SMA200": s200, "SMA5": s5})


class IBSLow(_HighWR):
    id = "ibs_low_hwr"
    name_en = "IBS < 0.2 + close < SMA5, exit IBS > 0.8 (quantifiedstrategies)"
    name_fa = "IBS < ۰.۲ + بسته < SMA۵، خروج IBS > ۰.۸"
    author = "quantifiedstrategies.com — Internal Bar Strength, 70–76% WR on S&P/Nasdaq ETFs"
    difficulty = 1
    params = {"ibs_buy": 0.2, "ibs_exit": 0.8}
    description_en = "Close in the bottom 20% of the day's range in an uptrend (above SMA200) → buy; exit when close is in top 20% of range."
    description_fa = "بسته در ۲۰٪ پایین دامنهٔ روز در روند صعودی (بالای SMA۲۰۰) ← خرید؛ خروج وقتی بسته در ۲۰٪ بالای دامنه باشد."
    rules_en = ["IBS = (close − low)/(high − low) < 0.2", "Close > SMA200", "Exit: IBS > 0.8 OR close > SMA5"]
    rules_fa = ["IBS = (بسته − کف)/(سقف − کف) < ۰.۲", "بسته > SMA200", "خروج: IBS > ۰.۸ یا بسته > SMA5"]
    pros_en = ["Works on ETFs, indices, large caps"]; cons_en = ["Useless on 24h crypto (no session close effect)"]
    pros_fa = ["روی ETF، شاخص، سهام بزرگ کار می‌کند"]; cons_fa = ["روی کریپتوی ۲۴ساعته بی‌فایده (اثر بسته شدن جلسه ندارد)"]

    def run(self, df):
        p = self.p
        ibs = ((df.close - df.low) / (df.high - df.low).replace(0, np.nan)).fillna(0.5)
        s200 = ta.sma(df.close, 200); s5 = ta.sma(df.close, 5)
        long = (df.close > s200) & (ibs < p["ibs_buy"])
        exit_ = (ibs > p["ibs_exit"]) | (df.close > s5)
        return self._pack(df, long, exit_, overlays={"SMA200": s200, "SMA5": s5}, panels={"IBS": {"IBS": ibs}})


class RSI2Dual(_HighWR):
    id = "rsi2_dual_trend"
    name_en = "RSI(2) + dual trend (SMA50 & SMA200) + 3-bar persistence — the 80%+ filter set"
    name_fa = "RSI(2) + روند دوگانه (SMA50 و SMA200) + ۳ کندل پایداری — مجموعه فیلتر ۸۰٪+"
    author = "quantifiedstrategies.com filter research: dual-trend +5–10% WR, 3-bar RSI(2)<10 persistence +10–15% WR"
    difficulty = 2
    params = {"rsi_below": 10, "persist": 2, "rsi_exit": 70}
    description_en = ("Stack every published filter that raises RSI(2)'s win rate: price above BOTH SMA50 and SMA200, RSI(2) below 10 for 2 "
                      "consecutive bars (capitulation), exit RSI(2) > 70. Very few, very high-probability trades.")
    description_fa = ("همهٔ فیلترهای منتشرشده که وین‌ریت RSI(2) را بالا می‌برند روی هم: قیمت بالای هر دو SMA۵۰ و SMA۲۰۰، RSI(2) زیر ۱۰ در ۲ کندل "
                      "متوالی (تسلیم)، خروج RSI(2) > ۷۰. معاملات خیلی کم، احتمال خیلی بالا.")
    rules_en = ["Close > SMA50 > SMA200", "RSI(2) < 10 on 2 consecutive bars", "Exit: RSI(2) > 70 OR close > SMA5"]
    rules_fa = ["بسته > SMA50 > SMA200", "RSI(2) < ۱۰ در ۲ کندل متوالی", "خروج: RSI(2) > ۷۰ یا بسته > SMA5"]
    pros_en = ["Highest expected win rate in the library"]; cons_en = ["Maybe 5–10 trades a year per symbol — needs a basket"]
    pros_fa = ["بالاترین وین‌ریت انتظاری کتابخانه"]; cons_fa = ["شاید ۵–۱۰ معامله در سال برای هر نماد — سبد لازم است"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, 2)
        s50, s200, s5 = ta.sma(df.close, 50), ta.sma(df.close, 200), ta.sma(df.close, 5)
        persist = (r < p["rsi_below"]).rolling(p["persist"]).sum() >= p["persist"]
        long = (df.close > s50) & (s50 > s200) & persist
        exit_ = (r > p["rsi_exit"]) | (df.close > s5)
        return self._pack(df, long, exit_, overlays={"SMA50": s50, "SMA200": s200, "SMA5": s5}, panels={"RSI(2)": {"RSI2": r}})


class BBLowerRSI2(_HighWR):
    id = "bb_rsi2_hwr"
    name_en = "Close < lower Bollinger(20,2) + RSI(2)<10, exit mid-band"
    name_fa = "بسته < باند پایین بولینگر + RSI(2)<۱۰، خروج باند میانی"
    author = "hyrotrader 2026 review: BB+RSI mean reversion 71% WR in ranging/mild-trend regimes"
    difficulty = 1
    params = {"rsi_below": 10}
    description_en = "Statistical stretch (below −2σ) plus 2-day exhaustion above SMA200; exit at the 20-SMA (mid band)."
    description_fa = "کشیدگی آماری (زیر −۲σ) به‌علاوهٔ فرسودگی ۲ روزه بالای SMA۲۰۰؛ خروج در SMA۲۰ (باند میانی)."
    rules_en = ["Close > SMA200", "Close < BB lower(20,2)", "RSI(2) < 10", "Exit: close > BB mid"]
    rules_fa = ["بسته > SMA200", "بسته < باند پایین (۲۰،۲)", "RSI(2) < ۱۰", "خروج: بسته > باند میانی"]
    pros_en = ["Two independent confirmations"]; cons_en = ["Crashes: band keeps expanding"]
    pros_fa = ["دو تأیید مستقل"]; cons_fa = ["در سقوط باند مدام باز می‌شود"]

    def run(self, df):
        r = ta.rsi(df.close, 2)
        u, m, l = ta.bollinger(df.close, 20, 2.0)
        s200 = ta.sma(df.close, 200)
        long = (df.close > s200) & (df.close < l) & (r < self.p["rsi_below"])
        return self._pack(df, long, df.close > m, overlays={"BB Up": u, "BB Mid": m, "BB Low": l, "SMA200": s200}, panels={"RSI(2)": {"RSI2": r}})


class HighWRPortfolio(_HighWR):
    id = "hwr_portfolio"
    name_en = "★ High-WR Composite (any of the Connors family fires, common exit)"
    name_fa = "★ ترکیب وین‌ریت بالا (هرکدام از خانوادهٔ کانرز فعال شود، خروج مشترک)"
    author = "ProTrader — union of the validated high-WR setups with the shared 'close > SMA5 or RSI(2) > 65' exit"
    difficulty = 2
    params = {}
    description_en = ("Fires when ANY of: RSI(2)<10, cumulative RSI(2)<35, 7-day low, IBS<0.2 with close<SMA5, 3 lower lows — all above SMA200. "
                      "One shared exit. Gives the family enough trades per symbol to be statistically meaningful.")
    description_fa = ("وقتی هرکدام از این‌ها فعال شود: RSI(2)<۱۰، RSI(2) تجمعی <۳۵، کف ۷ روزه، IBS<۰.۲ با بسته<SMA۵، ۳ کف پایین‌تر — همه بالای SMA۲۰۰. "
                      "یک خروج مشترک. به این خانواده تعداد معاملهٔ کافی برای معناداری آماری می‌دهد.")
    rules_en = ["Close > SMA200 AND close < SMA5", "Any Connors-family trigger", "Exit: close > SMA5 OR RSI(2) > 65"]
    rules_fa = ["بسته > SMA200 و بسته < SMA5", "هر تریگر خانوادهٔ کانرز", "خروج: بسته > SMA5 یا RSI(2) > ۶۵"]
    pros_en = ["Most trades of the family, same edge"]; cons_en = ["Still long-only, daily, bull-regime"]
    pros_fa = ["بیشترین معامله در خانواده، همان لبه"]; cons_fa = ["همچنان فقط خرید، روزانه، رژیم گاوی"]

    def run(self, df):
        r = ta.rsi(df.close, 2)
        s200, s5 = ta.sma(df.close, 200), ta.sma(df.close, 5)
        ibs = ((df.close - df.low) / (df.high - df.low).replace(0, np.nan)).fillna(0.5)
        ll3 = (df.low < df.low.shift(1)) & (df.low.shift(1) < df.low.shift(2)) & (df.low.shift(2) < df.low.shift(3))
        trig = (r < 10) | (r.rolling(2).sum() < 35) | (df.close <= df.close.rolling(7).min()) | (ibs < 0.2) | ll3
        long = (df.close > s200) & (df.close < s5) & trig
        exit_ = (df.close > s5) | (r > 65)
        return self._pack(df, long, exit_, overlays={"SMA200": s200, "SMA5": s5}, panels={"RSI(2)": {"RSI2": r}})
