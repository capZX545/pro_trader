"""
Phase 10 — deeper ports (built on core.quant2 / core.protections):
  • Chan (Algorithmic Trading ch.3) — Kalman-filter mean reversion: price regressed on its own smoothed "fair value"
    with a dynamic hedge ratio; trade forecast error e vs sqrt(Q) bands (single-asset version of Chan's EWA/EWC example).
  • Elder (Come Into My Trading Room) — Impulse system + SafeZone stop (the real SafeZone, not ATR).
  • Jesse — anchor-timeframe filter (4× base TF EMA slope) + base-TF pullback entry (Jesse docs "anchor timeframe").
  • O'Neil — base breakout with the actual SELL RULES (7-8% cut, 20-25% take, 50-DMA break on volume) as exit rules.
  • Davey — "robust" breakout template: simple parameters, protections ON (Freqtrade StoplossGuard/MaxDrawdown via bt_kwargs).
  • Freqtrade — canonical sample strategy (RSI<30 + TEMA crossing BB-mid + volume) + ROI table exits + trailing stop.
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta
from core import quant2 as Q


def _res(df, sig, atr_s, sl=1.5, tp=3.0, **kw):
    st, tg = Strategy.atr_stops(df, sig, atr_s, sl, tp)
    return StrategyResult(sig, st, tg, **kw)


class ChanKalmanMR(Strategy):
    id = "chan_kalman"
    name_en = "Chan — Kalman-filter mean reversion (dynamic beta bands)"
    name_fa = "چان — بازگشت به میانگین با فیلتر کالمن (باند بتای پویا)"
    category = "Mean-Reversion"
    author = "Ernie Chan — Algorithmic Trading ch.3 'Kalman filter as dynamic linear regression' (EWA/EWC example), single-asset form"
    difficulty = 4
    timeframes = "1h, 4h, 1d"
    params = {"fair_n": 50, "delta": 1e-5, "ve_mult": 1.0, "z_win": 100, "entry": 2.0, "sl_atr": 2.5, "tp_atr": 2.0}
    description_en = ("Chan replaces static regression with a Kalman filter: y = beta·x + alpha where beta/alpha follow a random walk. "
                      "Here x = 50-bar EMA fair value, y = close. Forecast error e normalised by its 100-bar std forms adaptive bands: long when "
                      "e crosses below −2·sqrt(Q), short when it crosses above +2·sqrt(Q), exit when e crosses zero. Beta drift tells you when the relation breaks.")
    description_fa = ("چان رگرسیون ایستا را با فیلتر کالمن جایگزین می‌کند: y = beta·x + alpha با beta/alpha گام‌تصادفی. اینجا x = EMA۵۰ (ارزش منصفانه) و y = قیمت. "
                      "خطای پیش‌بینی e نرمال‌شده با انحراف معیار ۱۰۰ کندلی‌اش باند تطبیقی می‌سازد: خرید وقتی e از −۲√Q پایین می‌رود، فروش وقتی از +۲√Q بالا می‌رود، خروج در عبور e از صفر.")
    rules_en = ["Kalman on log prices, state [beta, alpha], delta=1e-5, Ve = var(returns), z = e/σ₁₀₀(e)", "Long: e ↓ −2·√Q · Short: e ↑ +2·√Q", "Exit when e crosses 0 · stop 2.5 ATR"]
    rules_fa = ["کالمن روی لگاریتم قیمت، حالت [beta, alpha]، delta=1e-5، Ve=1e-4", "خرید: e از −۲√Q پایین برود · فروش: e از +۲√Q بالا برود", "خروج در عبور e از صفر · استاپ ۲.۵ ATR"]

    def run(self, df):
        p = self.p
        ly = np.log(df.close)
        x = np.log(ta.ema(df.close, p["fair_n"]).bfill())          # log space: Ve/delta are scale-free like Chan's ETF example
        # Chan fixes Ve=1e-3 for ETF prices; to stay scale-free across assets/timeframes we set Ve = ve_mult × var(log-returns)
        rv = float(ly.diff().iloc[:max(200, p["fair_n"] * 4)].var()) or 1e-6
        k = Q.kalman_hedge(ly.values, x.values, p["delta"], p["ve_mult"] * rv)
        e = pd.Series(k["e"].values, index=df.index)
        # sqrt(Q) is dominated by the state-noise term x²·Vw when x is a (log) price level, so we normalise the forecast error
        # by its own rolling std (Chan's practical variant in Machine Trading) — a scale-free z-score across assets.
        band = e.rolling(p["z_win"]).std().replace(0, np.nan)
        z = e / band
        warm = pd.Series(np.arange(len(df)) > p["fair_n"] * 2, index=df.index)
        long = self.cross_down(z, -p["entry"]) & warm                # enter on the crossing, not every bar beyond it
        short = self.cross_up(z, p["entry"]) & warm
        sig = self.make_signal(long, short)
        a = ta.atr(df)
        return _res(df, sig, a, p["sl_atr"], p["tp_atr"], overlays={"Kalman fair": np.exp(x)},
                    exit_long=self.cross_up(z, 0.0), exit_short=self.cross_down(z, 0.0),
                    panels={"Kalman z": {"z": z, "+entry": pd.Series(p["entry"], index=df.index),
                                            "-entry": pd.Series(-p["entry"], index=df.index)},
                            "beta": {"beta": pd.Series(k["beta"].values, index=df.index)}})


class ElderImpulseSafeZone(Strategy):
    id = "elder_impulse_safezone"
    name_en = "Elder — Impulse System + SafeZone stop"
    name_fa = "الدر — سیستم ایمپالس + استاپ SafeZone"
    category = "Trend"
    author = "Alexander Elder — Come Into My Trading Room (Impulse System ch.8; SafeZone stops ch.9)"
    difficulty = 3
    timeframes = "1h, 4h, 1d"
    params = {"ema": 13, "anchor": 5, "sz_lookback": 10, "sz_coef": 2.5, "tp_atr": 4.0}
    description_en = ("Elder's Impulse System: a bar is green when the 13-EMA AND the MACD-histogram both rise (buy permitted), red when both "
                      "fall (short permitted). Used as Elder intends — as a censorship system: the 5×-higher timeframe's colour forbids trading against it, "
                      "and the entry comes when the trading-timeframe impulse stops being red (long) / green (short). The stop is Elder's SafeZone: average downside penetration of the last 10 bars × 2.5, below the low — it adapts to 'market noise'.")
    description_fa = ("سیستم ایمپالس الدر: کندل سبز = EMA۱۳ و هیستوگرام MACD هر دو صعودی (اجازهٔ خرید)، قرمز = هر دو نزولی (اجازهٔ فروش). "
                      "به روش خود الدر یک سیستم سانسور است: رنگ تایم‌فریم ۵× بالاتر اجازهٔ معامله در خلافش را نمی‌دهد و ورود وقتی است که ایمپالس تایم معاملاتی از قرمز خارج شود (خرید) / از سبز خارج شود (فروش). استاپ = SafeZone الدر: میانگین نفوذ نزولی ۱۰ کندل × ۲.۵ زیر کف.")
    rules_en = ["Green = EMA13↑ & MACD-hist↑ ; Red = both ↓", "Long: anchor impulse not red & local impulse leaves red & close > EMA26", "SafeZone stop (10, 2.5) · exit when anchor impulse turns opposite"]
    rules_fa = ["سبز = EMA۱۳↑ و هیستوگرام↑ ؛ قرمز = هر دو ↓", "خرید: ایمپالس لنگر قرمز نباشد و ایمپالس محلی از قرمز خارج شود و بسته > EMA۲۶", "استاپ SafeZone (۱۰، ۲.۵) · خروج وقتی ایمپالس لنگر مخالف شود"]

    def run(self, df):
        p = self.p
        # Elder: the Impulse system is a CENSORSHIP system on the higher timeframe (Triple Screen): a red weekly bar
        # forbids longs, a green one forbids shorts. Entry on the trading timeframe when the local impulse stops being
        # red (long) / stops being green (short) — "buy when the bears lose their grip".
        imp = Q.impulse_system(df, p["ema"])
        n = len(df); idx = np.arange(n) // p["anchor"]
        agg = pd.DataFrame({"open": df.open.groupby(idx).first(), "high": df.high.groupby(idx).max(),
                            "low": df.low.groupby(idx).min(), "close": df.close.groupby(idx).last()})
        hi_imp = Q.impulse_system(agg, p["ema"])
        bias = pd.Series(hi_imp.reindex(idx).values, index=df.index).shift(p["anchor"]).fillna(0)  # completed anchor bars only
        long = (bias >= 0) & (imp.shift(1) == -1) & (imp != -1) & (df.close > ta.ema(df.close, p["ema"] * 2))
        short = (bias <= 0) & (imp.shift(1) == 1) & (imp != 1) & (df.close < ta.ema(df.close, p["ema"] * 2))
        sig = self.make_signal(long, short)
        a = ta.atr(df)
        sz_l = Q.safezone_stop(df, p["sz_lookback"], p["sz_coef"], 1)
        sz_s = Q.safezone_stop(df, p["sz_lookback"], p["sz_coef"], -1)
        stop = pd.Series(np.where(sig == 1, sz_l, np.where(sig == -1, sz_s, np.nan)), index=df.index)
        tgt = pd.Series(np.where(sig == 1, df.close + p["tp_atr"] * a, np.where(sig == -1, df.close - p["tp_atr"] * a, np.nan)), index=df.index)
        return StrategyResult(sig, stop, tgt, overlays={"EMA13": ta.ema(df.close, p["ema"]), "SafeZone L": sz_l},
                              exit_long=(bias == -1), exit_short=(bias == 1),
                              panels={"Impulse": {"impulse": imp, "anchor impulse": bias}})


class JesseAnchorPullback(Strategy):
    id = "jesse_anchor"
    name_en = "Bot: Jesse — anchor-timeframe trend + pullback"
    name_fa = "بات: Jesse — روند تایم‌فریم لنگر + پولبک"
    category = "Bot-Ported"
    author = "Jesse docs: 'anchor timeframe' (4× the trading timeframe decides the trend; entries on the trading timeframe)"
    difficulty = 2
    timeframes = "15m, 1h, 4h"
    params = {"factor": 4, "anchor_ema": 50, "pull_ema": 20, "rsi_n": 14, "sl_atr": 2.0, "tp_atr": 4.0}
    description_en = ("Jesse strategies typically read `self.candles` on an anchor timeframe (e.g. 4h when trading 1h) for bias. Bias = slope "
                      "of EMA50 on the 4×-resampled series (completed anchor candles only, no look-ahead). Entry on the base TF: pullback to EMA20 "
                      "(touch within 3 bars, close back above, RSI dipped below 50) in an up-bias (mirror for down), stop 2 ATR, target 4 ATR.")
    description_fa = ("استراتژی‌های Jesse معمولاً از تایم‌فریم لنگر (مثلاً ۴ ساعته وقتی ۱ ساعته معامله می‌کنید) برای جهت استفاده می‌کنند. جهت = شیب EMA۵۰ روی "
                      "سری ۴× بازنمونه‌شده (فقط کندل‌های کامل‌شده). ورود در تایم پایه: پولبک به EMA۲۰ (لمس ظرف ۳ کندل، بازگشت بالای آن، RSI زیر ۵۰ آمده) در جهت صعودی (برعکس برای نزولی).")
    rules_en = ["Bias: EMA50 slope on 4× anchor TF (completed candles)", "Long: bias↑ & touched EMA20 (≤3 bars) & close back above & RSI dipped <50", "Stop 2 ATR · target 4 ATR"]
    rules_fa = ["جهت: شیب EMA۵۰ در تایم‌فریم ۴× (کندل‌های کامل)", "خرید: جهت↑ و لمس EMA۲۰ (≤۳ کندل) و بازگشت بالای آن و RSI زیر ۵۰ آمده", "استاپ ۲ ATR · هدف ۴ ATR"]

    def run(self, df):
        p = self.p
        bias = Q.anchor_trend(df, p["factor"], p["anchor_ema"])
        e20 = ta.ema(df.close, p["pull_ema"])
        r = ta.rsi(df.close, p["rsi_n"])
        touched_l = (df.low <= e20).rolling(3).max().fillna(0) > 0   # pulled back into EMA20 within the last 3 bars
        touched_s = (df.high >= e20).rolling(3).max().fillna(0) > 0
        long = (bias > 0) & touched_l & (df.close > e20) & (df.close > df.close.shift(1)) & (r < 55) & (r.shift(1) < 50)
        short = (bias < 0) & touched_s & (df.close < e20) & (df.close < df.close.shift(1)) & (r > 45) & (r.shift(1) > 50)
        sig = self.make_signal(long, short)
        return _res(df, sig, ta.atr(df), p["sl_atr"], p["tp_atr"], overlays={"EMA20": e20},
                    panels={"Anchor bias": {"bias": bias}, "RSI": {"rsi": r}})


class ONeilSellRules(Strategy):
    id = "oneil_sell_rules"
    name_en = "O'Neil — breakout with the real sell rules (7-8% / 20-25% / 50-DMA)"
    name_fa = "اونیل — شکست با قوانین فروش واقعی (۷-۸٪ / ۲۰-۲۵٪ / MA۵۰)"
    category = "Trend"
    author = "William O'Neil — How to Make Money in Stocks, ch.10-11 (When to sell and cut losses / When to sell and take profits)"
    difficulty = 2
    timeframes = "1d"
    params = {"base_n": 40, "vol_mult": 1.4, "cut": 0.08, "take": 0.22, "hold_bars": 40}
    description_en = ("O'Neil's edge is in exits: buy a 40-bar base breakout on ≥1.4× volume with price above the 50- and 200-DMA; then "
                      "(1) cut every loss at 7-8% — no exceptions; (2) take profits at 20-25% unless the stock gained 20% within 3 weeks "
                      "(then hold 8 weeks); (3) sell on a close below the 50-DMA on heavy volume. Long-only, as in the book.")
    description_fa = ("مزیت اونیل در خروج‌هاست: خرید شکست پایهٔ ۴۰ کندلی با حجم ≥ ۱.۴× و قیمت بالای MA۵۰ و MA۲۰۰؛ سپس (۱) هر ضرر را در ۷-۸٪ ببند، بدون استثنا؛ "
                      "(۲) سود را در ۲۰-۲۵٪ بگیر مگر سهم ظرف ۳ هفته ۲۰٪ رشد کرده باشد (آنگاه ۸ هفته نگه دار)؛ (۳) بسته‌شدن زیر MA۵۰ با حجم سنگین = فروش. فقط خرید.")
    rules_en = ["Long: close > 40-bar high & vol ≥ 1.4×avg & close > MA50 > MA200", "Stop 8% below entry (hard) · target +22%", "Exit: close < MA50 on 1.5× volume"]
    rules_fa = ["خرید: بسته > سقف ۴۰ کندلی و حجم ≥ ۱.۴× و بسته > MA۵۰ > MA۲۰۰", "استاپ ۸٪ زیر ورود · هدف +۲۲٪", "خروج: بسته < MA۵۰ با حجم ۱.۵×"]
    bt_kwargs = {"allow_short": False, "max_bars": 60}

    def run(self, df):
        p = self.p
        hi = df.high.rolling(p["base_n"]).max().shift(1)
        va = df.volume.rolling(50).mean()
        m50, m200 = ta.sma(df.close, 50), ta.sma(df.close, 200)
        long = (df.close > hi) & (df.volume >= p["vol_mult"] * va) & (df.close > m50) & (m50 > m200)
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        stop = pd.Series(np.where(sig == 1, df.close * (1 - p["cut"]), np.nan), index=df.index)
        tgt = pd.Series(np.where(sig == 1, df.close * (1 + p["take"]), np.nan), index=df.index)
        exit_l = (df.close < m50) & (df.volume > 1.5 * va)
        return StrategyResult(sig, stop, tgt, overlays={"MA50": m50, "MA200": m200, "base high": hi}, exit_long=exit_l,
                              exit_short=pd.Series(False, index=df.index), bt_kwargs=dict(self.bt_kwargs))


class FreqtradeSample(Strategy):
    id = "freqtrade_sample"
    name_en = "Bot: Freqtrade — SampleStrategy (RSI+TEMA/BB) + minimal ROI + trailing"
    name_fa = "بات: Freqtrade — استراتژی نمونه (RSI+TEMA/BB) + ROI + تریلینگ"
    category = "Bot-Ported"
    author = "Freqtrade user_data/strategies/sample_strategy.py + docs (minimal_roi, trailing_stop, protections)"
    difficulty = 2
    timeframes = "5m, 15m, 1h"
    params = {"buy_rsi": 30, "sell_rsi": 70, "tema_n": 9, "bb_n": 20, "roi0": 0.04, "stoploss": 0.10}
    description_en = ("The strategy every Freqtrade user starts with: enter long when RSI crosses above 30, TEMA(9) ≤ Bollinger mid and TEMA rising, "
                      "volume > 0; enter short mirror (RSI crosses below 70, TEMA ≥ BB-mid, TEMA falling). Exit rule: RSI crosses 70 (30 for shorts). "
                      "minimal_roi 4% as target, stoploss −10%. Run it in the Lab with protections=True to see Freqtrade's StoplossGuard/MaxDrawdown.")
    description_fa = ("همان استراتژی که هر کاربر Freqtrade با آن شروع می‌کند: خرید وقتی RSI از ۳۰ بالا می‌رود، TEMA(۹) ≤ میانهٔ بولینگر و TEMA صعودی؛ فروش برعکس. "
                      "خروج: RSI از ۷۰ عبور کند. هدف minimal_roi ۴٪ و استاپ −۱۰٪. در آزمایشگاه با protections=True اثر StoplossGuard/MaxDrawdown را ببینید.")
    rules_en = ["Long: RSI ↑30 & TEMA ≤ BB-mid & TEMA rising & volume>0", "Short: RSI ↓70 & TEMA ≥ BB-mid & TEMA falling", "Exit: RSI ↑70 / ↓30 · ROI 4% · stop 10%"]
    rules_fa = ["خرید: RSI↑۳۰ و TEMA ≤ میانه BB و TEMA صعودی و حجم>۰", "فروش: RSI↓۷۰ و TEMA ≥ میانه BB و TEMA نزولی", "خروج: RSI↑۷۰ / ↓۳۰ · ROI ۴٪ · استاپ ۱۰٪"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close, 14)
        e1 = ta.ema(df.close, p["tema_n"]); e2 = ta.ema(e1, p["tema_n"]); e3 = ta.ema(e2, p["tema_n"])
        tema = 3 * e1 - 3 * e2 + e3
        mid = ta.sma(df.close, p["bb_n"])
        long = self.cross_up(r, p["buy_rsi"]) & (tema <= mid) & (tema > tema.shift(1)) & (df.volume > 0)
        short = self.cross_down(r, p["sell_rsi"]) & (tema >= mid) & (tema < tema.shift(1)) & (df.volume > 0)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.where(sig == 1, df.close * (1 - p["stoploss"]), np.where(sig == -1, df.close * (1 + p["stoploss"]), np.nan)), index=df.index)
        tgt = pd.Series(np.where(sig == 1, df.close * (1 + p["roi0"]), np.where(sig == -1, df.close * (1 - p["roi0"]), np.nan)), index=df.index)
        return StrategyResult(sig, stop, tgt, overlays={"TEMA": tema, "BB mid": mid}, panels={"RSI": {"rsi": r}},
                              exit_long=self.cross_up(r, p["sell_rsi"]), exit_short=self.cross_down(r, p["buy_rsi"]))


class DaveyRobustBreakout(Strategy):
    id = "davey_robust"
    name_en = "Davey — robust breakout template (few params, protections on)"
    name_fa = "دیوی — قالب شکست مقاوم (پارامتر کم، حفاظت فعال)"
    category = "Trend"
    author = "Kevin Davey — Building Winning Algorithmic Trading Systems (simple entry, ATR exits, MC/incubation; Freqtrade protections applied)"
    difficulty = 2
    timeframes = "4h, 1d"
    params = {"n": 40, "sl_atr": 3.0}
    description_en = ("Davey's advice: the fewer parameters the harder to over-fit. Entry = 40-bar Donchian breakout with close above/below; "
                      "exit = 3-ATR trailing style stop and 20-bar opposite channel. This strategy switches Freqtrade-style protections ON in the "
                      "backtester (Cooldown, StoplossGuard 4 stops/48 bars, MaxDrawdown 15%). Check it in Quant Lab → Incubation & Monkey test.")
    description_fa = ("توصیهٔ دیوی: پارامتر کمتر = بیش‌برازش سخت‌تر. ورود = شکست دانچین ۴۰ کندلی؛ خروج = استاپ ۳ ATR و کانال مخالف ۲۰ کندلی. "
                      "این استراتژی حفاظت‌های سبک Freqtrade را در بک‌تستر روشن می‌کند (Cooldown، StoplossGuard، MaxDrawdown ۱۵٪). در آزمایشگاه کوانت → Incubation و تست میمون ببینید.")
    rules_en = ["Long: close > 40-bar high · Short: close < 40-bar low", "Stop 3 ATR · exit on 20-bar opposite channel", "Protections: cooldown 2, 4 stops/48 → pause 12, DD>15% → pause 48"]
    rules_fa = ["خرید: بسته > سقف ۴۰ · فروش: بسته < کف ۴۰", "استاپ ۳ ATR · خروج با کانال مخالف ۲۰", "حفاظت: کول‌داون ۲، ۴ استاپ/۴۸ → توقف ۱۲، DD>۱۵٪ → توقف ۴۸"]
    bt_kwargs = {"max_bars": 200, "protections": True}

    def run(self, df):
        p = self.p
        hi, lo = df.high.rolling(p["n"]).max().shift(1), df.low.rolling(p["n"]).min().shift(1)
        h20, l20 = df.high.rolling(20).max().shift(1), df.low.rolling(20).min().shift(1)
        long = df.close > hi
        short = df.close < lo
        sig = self.make_signal(long, short)
        return _res(df, sig, ta.atr(df), p["sl_atr"], 99.0, overlays={"Donchian hi": hi, "Donchian lo": lo},
                    exit_long=df.close < l20, exit_short=df.close > h20, bt_kwargs=dict(self.bt_kwargs))
