"""
Ported from the remaining open-source bots + the reading list (Phase 9).

Bots (default / flagship strategies re-implemented from their docs & source):
  • Jesse         — example "SMA crossover + ATR trailing" & its Trend-following template (long/short, risk-based sizing)
  • OctoBot       — default "DailyTradingMode" evaluator mix: RSI + MACD + Bollinger + candle-pattern vote (weighted)
  • Superalgos    — "Weak-Hands-Buster"/"Masters" default: LRC (linear-regression channel) + Bollinger squeeze breakouts
  • Hummingbot    — Pure-Market-Making → here: Avellaneda–Stoikov style mean-reversion inside a fair-value band
                    (signals when price deviates > k·σ from micro-VWAP fair value; not real quoting)
  • Blackbird/ArbitrageBot — spread-arbitrage logic → cross-asset spread z-score (BTC vs ETH pairs) via core.quant
  • Gekko         — default MACD & DEMA strategies (with its "persistence" thresholds)
  • Zenbot        — trend_ema (default), rsi & ta_macd strategies
  • Binance-trading-bot (chrisleekr) — grid-style "buy dip / sell grid" with trailing thresholds
  • MagiBot / 3Commas / Bitsgap / Pionex — DCA (safety orders) bot and Grid bot as signal strategies
  • TensorTrade / Freqtrade-FreqAI — RL/ML → handled in core.ml (meta-labelling); here a "regime-adaptive ensemble" wrapper

Books:
  • Elder  — Impulse System + Triple Screen already exist; here: Force-Index 2-day (Come Into My Trading Room) and
             SafeZone stop system.
  • O'Neil — CANSLIM technical part (RS line new high + base breakout + 50-day above 200 + volume 50%↑, 7-8% stop)
  • Murphy — Multi-confirmation: trend (MA) + momentum (ROC) + volume (OBV) + breadth-free "3-step" rule
  • Nison  — Candle reversal at Bollinger/Support with trend filter (uses core.patterns)
  • Bulkowski — top-ranked patterns (H&S, double bottom, flags) with his measure rule (uses core.patterns)
  • Chan   — Mean-reversion on stationary series: Bollinger-z on log price only when ADF passes & half-life short;
             Momentum-on-non-stationary otherwise (regime chosen by Hurst)
  • Davey  — Any strategy can be "incubated" with quant.davey_incubation (Lab).
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta
from core import indicators2 as I2


def _res(df, sig, atr_s, sl=1.5, tp=3.0, **kw):
    st, tg = Strategy.atr_stops(df, sig, atr_s, sl, tp)
    return StrategyResult(sig, st, tg, **kw)


# ============================================================ Jesse
class JesseTrendATR(Strategy):
    id = "jesse_trend_atr"
    name_en = "Bot: Jesse — Trend template (EMA cross + ATR trail)"
    name_fa = "بات: Jesse — قالب روندی (کراس EMA + تریل ATR)"
    category = "Bot-Ported"
    author = "Jesse (jesse.trade) docs/examples — 'Trend following' template, risk-based position sizing"
    difficulty = 2
    timeframes = "4h, 1d"
    params = {"fast": 21, "slow": 55, "trend": 200, "atr_sl": 2.5, "atr_tp": 5.0, "chop_max": 60}
    description_en = ("Jesse's canonical example: long when EMA21 crosses EMA55 above EMA200 (mirror for shorts), ATR-based stop, "
                      "position sized by risk %. Filters chop with Choppiness Index < 60 like Jesse's 'anchor timeframe' idea.")
    description_fa = ("مثال کلاسیک Jesse: خرید وقتی EMA۲۱ از EMA۵۵ بالای EMA۲۰۰ بالا می‌رود (فروش برعکس)، استاپ ATR، اندازهٔ پوزیشن با ٪ریسک. "
                      "با Choppiness < ۶۰ بازار رنج را فیلتر می‌کند.")
    rules_en = ["Long: EMA21 ↑ EMA55 & close > EMA200 & CHOP < 60", "Short: mirror", "Stop 2.5 ATR · target 5 ATR · exit on opposite cross"]
    rules_fa = ["خرید: EMA۲۱ از EMA۵۵ بالا برود و قیمت > EMA۲۰۰ و CHOP < ۶۰", "فروش: برعکس", "استاپ ۲.۵ ATR · هدف ۵ ATR · خروج با کراس مخالف"]

    def run(self, df):
        p = self.p
        f, s, tr = ta.ema(df.close, p["fast"]), ta.ema(df.close, p["slow"]), ta.ema(df.close, p["trend"])
        ch = I2.choppiness(df)
        a = ta.atr(df)
        long = self.cross_up(f, s) & (df.close > tr) & (ch < p["chop_max"])
        short = self.cross_down(f, s) & (df.close < tr) & (ch < p["chop_max"])
        sig = self.make_signal(long, short)
        return _res(df, sig, a, p["atr_sl"], p["atr_tp"], overlays={"EMA21": f, "EMA55": s, "EMA200": tr},
                    exit_long=self.cross_down(f, s), exit_short=self.cross_up(f, s), panels={"CHOP": {"chop": ch}})


# ============================================================ OctoBot
class OctoBotDailyMix(Strategy):
    id = "octobot_daily"
    name_en = "Bot: OctoBot — Daily evaluator vote (RSI+MACD+BB+candles)"
    name_fa = "بات: OctoBot — رأی‌گیری ارزیاب‌ها (RSI+MACD+BB+کندل)"
    category = "Bot-Ported"
    author = "OctoBot default 'DailyTradingMode' + TA evaluators (RSI, MACD, Bollinger, candle patterns) — weighted average in [-1, 1]"
    difficulty = 2
    timeframes = "1h, 4h, 1d"
    params = {"threshold": 0.45, "sl_atr": 2.0, "tp_atr": 4.0}
    description_en = ("OctoBot doesn't trade one indicator: each evaluator emits a score in [-1,1] (RSI extreme, MACD histogram turn, "
                      "Bollinger position, candle reversal) and the trading mode acts when the average crosses ±0.45. Re-implemented faithfully.")
    description_fa = ("OctoBot با یک اندیکاتور معامله نمی‌کند: هر ارزیاب عددی در [−۱,۱] می‌دهد (RSI، چرخش هیستوگرام MACD، موقعیت در بولینگر، "
                      "کندل برگشتی) و وقتی میانگین از ±۰.۴۵ رد شد اقدام می‌کند. وفادارانه بازسازی شده.")
    rules_en = ["score = mean(RSI, MACD, BB, candle) each in [-1,1]", "Long when score crosses above +0.45; short below −0.45"]
    rules_fa = ["امتیاز = میانگین(RSI, MACD, BB, کندل) هرکدام در [−۱,۱]", "خرید وقتی امتیاز از +۰.۴۵ بالا رفت؛ فروش زیر −۰.۴۵"]

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close)
        e_rsi = ((50 - r) / 50).clip(-1, 1)                          # oversold → +1
        m, sgl, hist = ta.macd(df.close)
        e_macd = np.sign(hist.diff()).fillna(0) * (hist.abs() / hist.abs().rolling(50).mean().replace(0, np.nan)).clip(0, 1).fillna(0)
        mid, up, lo = ta.bollinger(df.close)
        pb = ((df.close - lo) / (up - lo).replace(0, np.nan)).clip(0, 1)
        e_bb = (1 - 2 * pb).fillna(0)
        body = df.close - df.open
        rngv = (df.high - df.low).replace(0, np.nan)
        e_cdl = ((body / rngv).clip(-1, 1)).fillna(0) * 0.5 + np.where(
            (df.low < df.low.shift(1)) & (df.close > df.open) & (body.abs() > (df.high - df.low) * 0.6), 0.5, 0) - np.where(
            (df.high > df.high.shift(1)) & (df.close < df.open) & (body.abs() > (df.high - df.low) * 0.6), 0.5, 0)
        score = (e_rsi + e_macd + e_bb + pd.Series(e_cdl, index=df.index)) / 4
        long = self.cross_up(score, p["threshold"])
        short = self.cross_down(score, -p["threshold"])
        sig = self.make_signal(long, short)
        return _res(df, sig, ta.atr(df), p["sl_atr"], p["tp_atr"], panels={"OctoBot score": {"score": score, "+thr": pd.Series(p["threshold"], index=df.index), "-thr": pd.Series(-p["threshold"], index=df.index)}})


# ============================================================ Superalgos
class SuperalgosLRC(Strategy):
    id = "superalgos_lrc"
    name_en = "Bot: Superalgos — LRC channel + BB-squeeze breakout"
    name_fa = "بات: Superalgos — کانال رگرسیون خطی + شکست فشردگی بولینگر"
    category = "Bot-Ported"
    author = "Superalgos 'Masters' & 'Weak-Hands-Buster' default strategies (LRC 15/30/60 + Bollinger channel/sub-channel)"
    difficulty = 3
    timeframes = "1h, 4h"
    params = {"lrc": 60, "bb": 20, "squeeze_pct": 0.35, "sl_atr": 2.0, "tp_atr": 4.0}
    description_en = ("Superalgos' shipped strategies key off the Linear-Regression Channel slope (the '15/30/60' LRC) and Bollinger "
                      "channel state: enter with the LRC direction when bands were squeezed (width below 35th percentile) and price breaks the band.")
    description_fa = ("استراتژی‌های پیش‌فرض Superalgos روی شیب کانال رگرسیون خطی و حالت کانال بولینگر کار می‌کنند: در جهت LRC وقتی باندها فشرده بودند "
                      "(پهنای کمتر از صدک ۳۵) و قیمت باند را شکست وارد شو.")
    rules_en = ["LRC slope > 0 and BB width was squeezed → long on close > upper band", "mirror for short", "ATR stops"]
    rules_fa = ["شیب LRC مثبت و باند فشرده → خرید با بسته شدن بالای باند بالا", "فروش برعکس", "استاپ ATR"]

    def run(self, df):
        p = self.p
        _lrc = I2.lin_reg_channel(df.close, p["lrc"]); mid_l, up_l, lo_l = _lrc[0], _lrc[1], _lrc[2]
        slope = mid_l.diff(3)
        mid, up, lo = ta.bollinger(df.close, p["bb"])
        width = (up - lo) / mid
        sq = width < width.rolling(120).quantile(p["squeeze_pct"])
        long = (slope > 0) & sq.shift(1).fillna(False) & self.cross_up(df.close, up)
        short = (slope < 0) & sq.shift(1).fillna(False) & self.cross_down(df.close, lo)
        sig = self.make_signal(long, short)
        return _res(df, sig, ta.atr(df), p["sl_atr"], p["tp_atr"], overlays={"LRC mid": mid_l, "LRC up": up_l, "LRC lo": lo_l, "BB up": up, "BB lo": lo})


# ============================================================ Hummingbot (market-making logic as a signal)
class HummingbotFairValue(Strategy):
    id = "hummingbot_fv"
    name_en = "Bot: Hummingbot — fair-value band reversion (Avellaneda–Stoikov)"
    name_fa = "بات: Hummingbot — بازگشت به ارزش منصفانه (اَولانِدا–استویکوف)"
    category = "Bot-Ported"
    author = "Hummingbot pure_market_making / avellaneda_market_making → reservation price & optimal spread logic"
    difficulty = 4
    timeframes = "5m, 15m, 1h"
    params = {"vwap_n": 48, "k_sigma": 2.0, "inv_skew": 0.0, "sl_atr": 1.5, "tp_atr": 1.0, "max_bars": 24}
    description_en = ("A market maker quotes around a reservation price r = mid − q·γ·σ² and profits when price returns. As a directional "
                      "signal: fair value = rolling VWAP; when price is > k·σ below fair value, buy (you'd be the bid getting hit); above → sell. "
                      "Time-stopped fast, like an MM inventory that must be flattened. Volume-less markets (forex feed) get no signals.")
    description_fa = ("مارکت‌میکر حول قیمت رزرو r = mid − q·γ·σ² سفارش می‌گذارد و از بازگشت قیمت سود می‌برد. به‌صورت سیگنال جهت‌دار: ارزش منصفانه = VWAP غلتان؛ "
                      "وقتی قیمت بیش از k·σ زیر آن است بخر، بالای آن بفروش. با حد زمانی کوتاه، مثل موجودی MM که باید صفر شود.")
    rules_en = ["fair = rolling VWAP(48), σ = std of (close − fair)", "Long: close < fair − 2σ ; Short: close > fair + 2σ", "Exit at fair (target) · time stop 24 bars"]
    rules_fa = ["ارزش منصفانه = VWAP غلتان ۴۸، σ = انحراف (قیمت − ارزش)", "خرید: قیمت < ارزش − ۲σ ؛ فروش: قیمت > ارزش + ۲σ", "خروج در ارزش منصفانه · حد زمانی ۲۴ کندل"]
    bt_kwargs = {"max_bars": 24}

    def run(self, df):
        p = self.p
        if df.volume.fillna(0).sum() == 0:
            z = pd.Series(0.0, index=df.index)
            return StrategyResult(pd.Series(0, index=df.index), bt_kwargs=self.bt_kwargs)
        pv = (df.close * df.volume).rolling(p["vwap_n"]).sum()
        fair = pv / df.volume.rolling(p["vwap_n"]).sum().replace(0, np.nan)
        dev = df.close - fair
        sig_ = dev.rolling(p["vwap_n"] * 2).std()
        z = dev / sig_.replace(0, np.nan)
        long = self.cross_down(z, -p["k_sigma"])
        short = self.cross_up(z, p["k_sigma"])
        sig = self.make_signal(long, short)
        a = ta.atr(df)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.close[sig == 1] - p["sl_atr"] * a[sig == 1]; tgt[sig == 1] = fair[sig == 1]
        stop[sig == -1] = df.close[sig == -1] + p["sl_atr"] * a[sig == -1]; tgt[sig == -1] = fair[sig == -1]
        return StrategyResult(sig, stop, tgt, overlays={"fair value": fair, "+2σ": fair + p["k_sigma"] * sig_, "−2σ": fair - p["k_sigma"] * sig_},
                              panels={"z": {"z": z}}, bt_kwargs=self.bt_kwargs)


# ============================================================ Gekko
class GekkoMACD(Strategy):
    id = "gekko_macd"
    name_en = "Bot: Gekko — MACD with persistence"
    name_fa = "بات: Gekko — MACD با پایداری"
    category = "Bot-Ported"
    author = "Gekko (askmike) strategies/MACD.js — thresholds up/down + persistence"
    difficulty = 1
    timeframes = "1h, 4h"
    params = {"short": 10, "long": 21, "signal": 9, "up": 0.025, "down": -0.025, "persistence": 1, "sl_atr": 2.0, "tp_atr": 4.0}
    description_en = ("Gekko's default MACD: signal only after the MACD histogram (normalised by price %) stays beyond the threshold for "
                      "`persistence` candles — avoiding the whipsaw of raw crosses.")
    description_fa = ("MACD پیش‌فرض Gekko: سیگنال فقط وقتی هیستوگرام (نرمال‌شده به درصد قیمت) به مدت `persistence` کندل فراتر از آستانه بماند — "
                      "برای پرهیز از نوسان کراس‌های خام.")
    rules_en = ["hist% = MACD hist / close × 100", "long after hist% > up for N bars; short after < down for N bars"]
    rules_fa = ["hist% = هیستوگرام / قیمت × ۱۰۰", "خرید بعد از N کندل hist% > up؛ فروش بعد از N کندل < down"]

    def run(self, df):
        p = self.p
        m, s, h = ta.macd(df.close, p["short"], p["long"], p["signal"])
        hp = h / df.close * 100
        n = p["persistence"] + 1
        up = (hp > p["up"]).rolling(n).sum() == n
        dn = (hp < p["down"]).rolling(n).sum() == n
        long = up & ~up.shift(1).fillna(False).astype(bool)
        short = dn & ~dn.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        return _res(df, sig, ta.atr(df), p["sl_atr"], p["tp_atr"], panels={"MACD%": {"hist%": hp}})


class GekkoDEMA(Strategy):
    id = "gekko_dema"
    name_en = "Bot: Gekko — DEMA trend"
    name_fa = "بات: Gekko — روند DEMA"
    category = "Bot-Ported"
    author = "Gekko strategies/DEMA.js — price vs DEMA(?) with up/down thresholds"
    difficulty = 1
    timeframes = "1h, 4h, 1d"
    params = {"n": 21, "up": 0.025, "down": -0.025, "sl_atr": 2.0, "tp_atr": 4.0}
    description_en = "Gekko DEMA: diff% = (DEMA − SMA)/SMA·100; long when diff% > up threshold, short when < down. Long/short flips only."
    description_fa = "DEMA گکو: diff% = (DEMA − SMA)/SMA·۱۰۰؛ خرید وقتی diff% > up، فروش وقتی < down."
    rules_en = ["diff% > +0.025 → long", "diff% < −0.025 → short"]
    rules_fa = ["diff% > +۰.۰۲۵ → خرید", "diff% < −۰.۰۲۵ → فروش"]

    def run(self, df):
        p = self.p
        d = I2.dema(df.close, p["n"]); s = ta.sma(df.close, p["n"])
        diff = (d - s) / s * 100
        long = self.cross_up(diff, p["up"]); short = self.cross_down(diff, p["down"])
        sig = self.make_signal(long, short)
        return _res(df, sig, ta.atr(df), p["sl_atr"], p["tp_atr"], overlays={"DEMA": d, "SMA": s})


# ============================================================ Zenbot
class ZenbotTrendEMA(Strategy):
    id = "zenbot_trend_ema"
    name_en = "Bot: Zenbot — trend_ema (default)"
    name_fa = "بات: Zenbot — trend_ema (پیش‌فرض)"
    category = "Bot-Ported"
    author = "Zenbot (DeviaVir) extensions/strategies/trend_ema — EMA rate-of-change with neutral_rate & oversold RSI"
    difficulty = 1
    timeframes = "15m, 1h, 4h"
    params = {"ema": 26, "neutral_rate": 0.06, "oversold_rsi": 10, "sl_atr": 2.0, "tp_atr": 4.0}
    description_en = ("Zenbot's default: compute EMA(26) slope % per bar ('trend_ema_rate'); above +neutral_rate → buy, below −neutral_rate "
                      "→ sell; plus an oversold-RSI dip buy. The `neutral_rate` dead-zone is what stops it churning.")
    description_fa = ("پیش‌فرض Zenbot: شیب درصدی EMA(۲۶) در هر کندل؛ بالای +neutral_rate خرید، زیر −neutral_rate فروش؛ به‌علاوه خرید در RSI اشباع فروش. "
                      "ناحیهٔ خنثی جلوی نوسان‌گیری بیهوده را می‌گیرد.")
    rules_en = ["rate% = ΔEMA/EMA·100", "rate% crosses above +0.06 → long; below −0.06 → short", "RSI(14) < 10 → long"]
    rules_fa = ["rate% = ΔEMA/EMA·۱۰۰", "rate% از +۰.۰۶ بالا رفت → خرید؛ زیر −۰.۰۶ → فروش", "RSI < ۱۰ → خرید"]

    def run(self, df):
        p = self.p
        e = ta.ema(df.close, p["ema"])
        rate = e.pct_change() * 100
        r = ta.rsi(df.close)
        long = self.cross_up(rate, p["neutral_rate"]) | self.cross_down(r, p["oversold_rsi"])
        short = self.cross_down(rate, -p["neutral_rate"])
        sig = self.make_signal(long, short)
        return _res(df, sig, ta.atr(df), p["sl_atr"], p["tp_atr"], overlays={"EMA26": e}, panels={"rate%": {"rate": rate}})


# ============================================================ Grid / DCA (3Commas, Pionex, Bitsgap, MagiBot, chrisleekr)
class GridBotSignal(Strategy):
    id = "grid_bot"
    name_en = "Bot: Grid (Pionex / Bitsgap / 3Commas) — range grid as signals"
    name_fa = "بات: گرید (Pionex / Bitsgap / 3Commas) — شبکهٔ رنج به‌صورت سیگنال"
    category = "Bot-Ported"
    author = "Grid-bot logic: N levels between range low/high (Donchian 100), buy at lower levels, sell at upper; disabled when trend breaks the range"
    difficulty = 2
    timeframes = "15m, 1h, 4h"
    params = {"range_n": 100, "levels": 8, "adx_max": 22, "max_bars": 60}
    description_en = ("Grid bots profit in ranges and bleed in trends. Faithful signal version: range = Donchian(100); price crossing DOWN through "
                      "a grid line = buy (target: next line up, stop: 2 lines down); crossing UP through an upper line = sell. Only when ADX < 22. "
                      "Shows exactly where a grid bot would have made/lost money.")
    description_fa = ("گرید‌بات در رنج سود می‌کند و در روند خون‌ریزی. نسخهٔ سیگنالی: رنج = دانچیان(۱۰۰)؛ عبور قیمت به پایین از خط شبکه = خرید (هدف: خط بعدی، "
                      "استاپ: دو خط پایین‌تر)؛ عبور به بالا از خط بالایی = فروش. فقط وقتی ADX < ۲۲.")
    rules_en = ["grid = 8 equal levels inside Donchian(100)", "buy on cross below a level in lower half; sell on cross above a level in upper half", "ADX < 22 only · time stop 60"]
    rules_fa = ["شبکه = ۸ سطح مساوی داخل دانچیان(۱۰۰)", "خرید با عبور به پایین از سطح در نیمهٔ پایین؛ فروش با عبور به بالا از سطح در نیمهٔ بالا", "فقط ADX < ۲۲ · حد زمانی ۶۰"]
    bt_kwargs = {"max_bars": 60}

    def run(self, df):
        p = self.p
        hi = df.high.rolling(p["range_n"]).max().shift(1); lo = df.low.rolling(p["range_n"]).min().shift(1)
        step = (hi - lo) / p["levels"]
        adx, _, _ = ta.adx(df)
        pos = ((df.close - lo) / step)            # fractional grid position
        prev = pos.shift(1)
        lvl_now = np.floor(pos); lvl_prev = np.floor(prev)
        crossed_down = (lvl_now < lvl_prev) & (pos < p["levels"] / 2)
        crossed_up = (lvl_now > lvl_prev) & (pos > p["levels"] / 2)
        ok = adx < p["adx_max"]
        sig = self.make_signal(crossed_down & ok, crossed_up & ok)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        L = sig == 1; S = sig == -1
        stop[L] = df.close[L] - 2 * step[L]; tgt[L] = lo[L] + (lvl_now[L] + 1) * step[L]
        stop[S] = df.close[S] + 2 * step[S]; tgt[S] = lo[S] + (lvl_now[S]) * step[S]
        return StrategyResult(sig, stop, tgt, overlays={"range hi": hi, "range lo": lo}, panels={"grid pos": {"level": pos}}, bt_kwargs=self.bt_kwargs)


class DCABotSignal(Strategy):
    id = "dca_bot"
    name_en = "Bot: DCA / safety-orders (3Commas, MagiBot) — as signals"
    name_fa = "بات: DCA / سفارش‌های ایمنی (3Commas، MagiBot) — به‌صورت سیگنال"
    category = "Bot-Ported"
    author = "3Commas DCA bot defaults: base order on signal, safety orders every −2.5% (scale 1.05), take-profit +1.5% from average"
    difficulty = 2
    timeframes = "1h, 4h"
    params = {"so_step": 2.5, "max_so": 5, "tp": 1.5, "rsi_entry": 30, "max_bars": 120}
    description_en = ("The most-sold bot type. Base order on RSI<30 dip; up to 5 safety orders every −2.5% (each 1.05× bigger); exits when price "
                      "returns +1.5% above the AVERAGE entry. Re-created as one trade with the equivalent averaged entry/stop, so the backtester "
                      "reveals the hidden risk: the stop (all SOs filled + one more step) is ~15% below the first entry.")
    description_fa = ("پرفروش‌ترین نوع بات. سفارش پایه در RSI<۳۰؛ تا ۵ سفارش ایمنی هر −۲.۵٪ (هرکدام ۱.۰۵ برابر)؛ خروج وقتی قیمت +۱.۵٪ بالای میانگین ورود برگردد. "
                      "به‌صورت یک معامله با ورود/استاپ میانگین بازسازی شده تا بک‌تستر ریسک پنهان را نشان دهد: استاپ ~۱۵٪ زیر ورود اول است.")
    rules_en = ["Entry: RSI(14) < 30 & close > EMA200 (3Commas 'RSI' signal + trend filter)", "Average entry ≈ first − 6.3% (SO ladder); target avg + 1.5%", "Stop = last SO − 2.5%"]
    rules_fa = ["ورود: RSI < ۳۰ و قیمت > EMA۲۰۰", "میانگین ورود ≈ ورود اول − ۶.۳٪؛ هدف میانگین + ۱.۵٪", "استاپ = آخرین SO − ۲.۵٪"]
    bt_kwargs = {"max_bars": 120, "allow_short": False}

    def run(self, df):
        p = self.p
        r = ta.rsi(df.close); e = ta.ema(df.close, 200)
        long = self.cross_down(r, p["rsi_entry"]) & (df.close > e)
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        # ladder maths
        sizes = np.array([1.0] + [1.05 ** k for k in range(1, p["max_so"] + 1)])
        offs = np.array([0.0] + [-p["so_step"] * k for k in range(1, p["max_so"] + 1)]) / 100
        avg_off = float((sizes * offs).sum() / sizes.sum())          # ≈ −6.3%
        stop_off = offs[-1] - p["so_step"] / 100
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        L = sig == 1
        stop[L] = df.close[L] * (1 + stop_off)
        tgt[L] = df.close[L] * (1 + avg_off) * (1 + p["tp"] / 100)
        return StrategyResult(sig, stop, tgt, overlays={"EMA200": e}, panels={"RSI": {"rsi": r}}, bt_kwargs=self.bt_kwargs)


# ============================================================ Books
class ElderForceIndex2(Strategy):
    id = "elder_force2"
    name_en = "Elder — 2-day Force Index pullback in EMA trend (Come Into My Trading Room)"
    name_fa = "الدر — پولبک Force Index دوروزه در روند EMA"
    category = "Masters' Indicators"
    author = "Dr. Alexander Elder — Come Into My Trading Room ch.5 & The New Trading for a Living"
    difficulty = 2
    timeframes = "1d, 4h"
    params = {"ema": 22, "fi": 2, "sl_atr": 2.0, "tp_atr": 4.0}
    description_en = ("Elder's favourite entry: when the 22-day EMA rises, buy when the 2-day Force Index dips below zero (a pullback with "
                      "weak selling pressure); mirror for shorts. Stop under the recent low via SafeZone-like ATR stop.")
    description_fa = ("ورود محبوب الدر: وقتی EMA ۲۲روزه صعودی است، هنگامی که Force Index دوروزه زیر صفر رفت بخر (پولبک با فشار فروش ضعیف)؛ برعکس برای فروش.")
    rules_en = ["EMA22 slope > 0 and FI(2) crosses below 0 → long", "EMA22 slope < 0 and FI(2) crosses above 0 → short"]
    rules_fa = ["شیب EMA۲۲ مثبت و FI(۲) زیر صفر رفت → خرید", "شیب EMA۲۲ منفی و FI(۲) بالای صفر رفت → فروش"]

    def run(self, df):
        p = self.p
        e = ta.ema(df.close, p["ema"]); fi = I2.force_index(df, p["fi"])
        long = (e.diff() > 0) & self.cross_down(fi, 0)
        short = (e.diff() < 0) & self.cross_up(fi, 0)
        sig = self.make_signal(long, short)
        return _res(df, sig, ta.atr(df), p["sl_atr"], p["tp_atr"], overlays={"EMA22": e}, panels={"Force Index 2": {"FI": fi}})


class ONeilCANSLIM(Strategy):
    id = "oneil_canslim"
    name_en = "O'Neil — CAN SLIM technical checklist + pivot breakout"
    name_fa = "اونیل — چک‌لیست تکنیکال CAN SLIM + شکست پیوت"
    category = "Masters' Indicators"
    author = "William J. O'Neil — How to Make Money in Stocks (L = leader via RS line; M = market direction; base breakout on 40-50% volume)"
    difficulty = 3
    timeframes = "1d"
    params = {"base_n": 35, "vol_mult": 1.4, "stop_pct": 7.0, "rs_n": 126}
    description_en = ("The technical half of CAN SLIM: price within 15% of 52-week high, above rising 50 & 200-day MAs, RS-line (price/SPY proxy = "
                      "price/its own 126-day mean) at a new high, breakout from a ≥7-week base on volume ≥ 140% of average. Sell at −7% (his cardinal rule) "
                      "or after 20–25% gain unless it ran 20% in < 3 weeks.")
    description_fa = ("نیمهٔ تکنیکال CAN SLIM: قیمت در ۱۵٪ سقف ۵۲هفته، بالای MA ۵۰ و ۲۰۰ صعودی، خط قدرت نسبی در سقف جدید، شکست پایهٔ ≥۷ هفته با حجم ≥۱۴۰٪ میانگین. "
                      "فروش در −۷٪ (قانون طلایی او) یا بعد از ۲۰–۲۵٪ سود.")
    rules_en = ["close > SMA50 > SMA200, both rising; close ≥ 0.85 × 52w high", "RS proxy at 126-day high", "close > max(high, 35 bars) and volume ≥ 1.4× avg", "stop −7%, target +22%"]
    rules_fa = ["قیمت > SMA۵۰ > SMA۲۰۰ و هر دو صعودی؛ قیمت ≥ ۰.۸۵ × سقف ۵۲هفته", "قدرت نسبی در سقف ۱۲۶روزه", "شکست سقف ۳۵ کندلی با حجم ≥ ۱.۴ برابر", "استاپ −۷٪، هدف +۲۲٪"]
    bt_kwargs = {"allow_short": False, "max_bars": 120}

    def run(self, df):
        p = self.p
        c = df.close
        s50, s200 = ta.sma(c, 50), ta.sma(c, 200)
        hi52 = c.rolling(252).max()
        rs = c / c.rolling(p["rs_n"]).mean()
        rs_new_high = rs >= rs.rolling(p["rs_n"]).max()
        base_hi = df.high.rolling(p["base_n"]).max().shift(1)
        vol_ok = df.volume > p["vol_mult"] * df.volume.rolling(50).mean() if df.volume.fillna(0).sum() > 0 else pd.Series(True, index=df.index)
        cond = (c > s50) & (s50 > s200) & (s50.diff(10) > 0) & (s200.diff(20) > 0) & (c >= 0.85 * hi52) & rs_new_high & (c > base_hi) & vol_ok
        long = cond & ~cond.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, pd.Series(False, index=df.index))
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = c[sig == 1] * (1 - p["stop_pct"] / 100); tgt[sig == 1] = c[sig == 1] * 1.22
        return StrategyResult(sig, stop, tgt, overlays={"SMA50": s50, "SMA200": s200, "base high": base_hi}, panels={"RS line": {"rs": rs}}, bt_kwargs=self.bt_kwargs)


class MurphyConfirmation(Strategy):
    id = "murphy_confirm"
    name_en = "Murphy — trend + momentum + volume confirmation"
    name_fa = "مورفی — تأیید سه‌گانهٔ روند + مومنتوم + حجم"
    category = "Trend"
    author = "John J. Murphy — Technical Analysis of the Financial Markets (ch. 4 trend, 10 oscillators, 7 volume/OBV; 'volume must confirm the trend')"
    difficulty = 2
    timeframes = "1d, 4h"
    params = {"ma": 50, "roc": 10, "obv_ma": 20, "sl_atr": 2.0, "tp_atr": 4.0}
    description_en = ("Murphy's core teaching is confirmation across dimensions: price above a rising 50 MA (trend), ROC crossing zero (momentum) "
                      "and OBV above its own MA (volume confirming). Enter only when all three agree; exit when trend breaks.")
    description_fa = ("آموزهٔ اصلی مورفی تأیید چندبعدی است: قیمت بالای MA۵۰ صعودی (روند)، عبور ROC از صفر (مومنتوم) و OBV بالای میانگین خودش (حجم تأییدکننده). فقط با توافق هر سه وارد شو.")
    rules_en = ["close > SMA50 & SMA50 rising", "ROC(10) crosses above 0", "OBV > SMA(OBV,20)", "mirror for short"]
    rules_fa = ["قیمت > SMA۵۰ صعودی", "ROC(۱۰) از صفر بالا برود", "OBV > میانگین ۲۰ خودش", "فروش برعکس"]

    def run(self, df):
        p = self.p
        m = ta.sma(df.close, p["ma"]); roc = ta.roc(df.close, p["roc"]); obv = ta.obv(df); om = ta.sma(obv, p["obv_ma"])
        vol_ok = df.volume.fillna(0).sum() > 0
        long = (df.close > m) & (m.diff(5) > 0) & self.cross_up(roc, 0) & ((obv > om) if vol_ok else True)
        short = (df.close < m) & (m.diff(5) < 0) & self.cross_down(roc, 0) & ((obv < om) if vol_ok else True)
        sig = self.make_signal(long, short)
        return _res(df, sig, ta.atr(df), p["sl_atr"], p["tp_atr"], overlays={"SMA50": m}, panels={"ROC": {"roc": roc}, "OBV": {"obv": obv, "obv ma": om}},
                    exit_long=self.cross_down(df.close, m), exit_short=self.cross_up(df.close, m))


class NisonCandleReversal(Strategy):
    id = "nison_candles"
    name_en = "Nison — candle reversal at Bollinger band with trend filter"
    name_fa = "نیسون — برگشت کندلی روی باند بولینگر با فیلتر روند"
    category = "Price-Action"
    author = "Steve Nison — Japanese Candlestick Charting Techniques; pattern set & 'needs a prior trend + support' rule; ranking from Bulkowski's candle stats"
    difficulty = 2
    timeframes = "4h, 1d"
    params = {"min_rev": 60, "sl_atr": 1.5, "tp_atr": 3.0}
    description_en = ("Nison insists a candle pattern only matters at support/resistance after a move. Implementation: a bullish reversal candle "
                      "(engulfing, hammer, piercing, morning star… with Bulkowski reversal-rate ≥ 60%) whose low touched the lower Bollinger band; "
                      "mirror at the upper band. 24 Nison patterns from core.patterns.")
    description_fa = ("نیسون تأکید دارد الگوی کندلی فقط روی حمایت/مقاومت و بعد از یک حرکت معنی دارد. پیاده‌سازی: کندل برگشتی صعودی (پوشا، چکش، نفوذی، ستارهٔ صبح… با نرخ برگشت بالکوفسکی ≥۶۰٪) "
                      "که کف آن باند پایین بولینگر را لمس کرده؛ برعکس در باند بالا. ۲۴ الگوی نیسون از core.patterns.")
    rules_en = ["bullish Nison pattern (rev-rate ≥ 60%) & low ≤ lower BB → long", "bearish pattern & high ≥ upper BB → short", "stop beyond pattern extreme (1.5 ATR)"]
    rules_fa = ["الگوی صعودی نیسون (نرخ ≥۶۰٪) و کف ≤ باند پایین → خرید", "الگوی نزولی و سقف ≥ باند بالا → فروش", "استاپ فراتر از اکسترمم الگو"]

    def run(self, df):
        from core.patterns import candlesticks
        p = self.p
        mid, up, lo = ta.bollinger(df.close)
        sig = pd.Series(0, index=df.index)
        for c in candlesticks(df):
            if c["stats"]["reversal_rate"] < p["min_rev"]:
                continue
            i = c["i_end"]
            if c["side"] == 1 and df.low.values[c["i_start"]:i + 1].min() <= lo.values[i]:
                sig.iloc[i] = 1
            elif c["side"] == -1 and df.high.values[c["i_start"]:i + 1].max() >= up.values[i]:
                sig.iloc[i] = -1
        return _res(df, sig, ta.atr(df), p["sl_atr"], p["tp_atr"], overlays={"BB up": up, "BB lo": lo})


class BulkowskiTopPatterns(Strategy):
    id = "bulkowski_patterns"
    name_en = "Bulkowski — top-ranked chart patterns with measure rule"
    name_fa = "بالکوفسکی — الگوهای نموداری برتر با قانون اندازه‌گیری"
    category = "Price-Action"
    author = "Thomas N. Bulkowski — Encyclopedia of Chart Patterns (H&S, double/triple bottoms, flags, cup-handle; break-even failure & measure rule)"
    difficulty = 3
    timeframes = "1d, 4h"
    params = {"max_fail": 10, "lookback": 250}
    description_en = ("Trades only patterns Bulkowski ranks with ≤10% break-even failure (H&S top/bottom, Adam&Adam double bottom, triple bottom, "
                      "bull flag, cup-handle, rounding bottom…). Entry on the confirmed breakout of the neckline/rim, target by his measure rule "
                      "(pattern height), stop at half height. Pattern stats are shown in the Academy.")
    description_fa = ("فقط الگوهایی را معامله می‌کند که بالکوفسکی با نرخ شکست ≤۱۰٪ رتبه‌بندی کرده (سر و شانه، کف دوقلوی Adam&Adam، کف سه‌قلو، پرچم صعودی، فنجان‌ودسته…). "
                      "ورود با شکست تأییدشدهٔ خط گردن، هدف با قانون اندازه‌گیری (ارتفاع الگو)، استاپ نصف ارتفاع.")
    rules_en = ["detect patterns (core.patterns.chart_patterns) on rolling window", "enter on first close beyond breakout level", "target = level ± height, stop = level ∓ height/2"]
    rules_fa = ["تشخیص الگو روی پنجرهٔ غلتان", "ورود با اولین کلوز فراتر از سطح شکست", "هدف = سطح ± ارتفاع، استاپ = سطح ∓ نصف ارتفاع"]

    def run(self, df):
        from core.patterns import chart_patterns
        p = self.p
        n = len(df)
        sig = pd.Series(0, index=df.index); stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        step = 10 if n > 3000 else 5
        armed = {}   # name -> (side, level, target, stop, expires)
        c = df.close.values
        for i in range(p["lookback"], n):
            if i % step == 0:
                for pt in chart_patterns(df.iloc[:i + 1], lookback=min(p["lookback"], 150) if n > 3000 else p["lookback"]):
                    if pt["stats"]["fail"] <= p["max_fail"] and not pt["confirmed"] and pt["i_end"] >= i - 30:
                        armed[pt["name"]] = (pt["side"], pt["level"], pt["target"], pt["stop"], i + 40)
            for name, (side, lvl, tg, sp, exp) in list(armed.items()):
                if i > exp:
                    armed.pop(name); continue
                if (side == 1 and c[i] > lvl) or (side == -1 and c[i] < lvl):
                    sig.iloc[i] = side; stop.iloc[i] = sp; tgt.iloc[i] = tg
                    armed.pop(name)
        return StrategyResult(sig, stop, tgt)


class ChanStatArb(Strategy):
    id = "chan_statarb"
    name_en = "Chan — regime-aware mean reversion / momentum (ADF · Hurst · half-life)"
    name_fa = "چان — بازگشت به میانگین / مومنتوم آگاه از رژیم (ADF · هرست · نیمه‌عمر)"
    category = "Mean-Reversion"
    author = "Ernie Chan — Algorithmic Trading ch.2–3 (stationarity tests, half-life, Bollinger-z) & ch.6 (momentum when H>0.5)"
    difficulty = 4
    timeframes = "1h, 4h, 1d"
    params = {"win": 250, "z_in": 2.0, "z_out": 0.0, "sl_atr": 2.5, "tp_atr": 2.0}
    description_en = ("Chan's discipline: never assume a series mean-reverts — test it. Every 50 bars: Hurst & ADF on log price of the last 250 bars. "
                      "If H<0.45 and ADF passes → trade Bollinger z-score reversion with look-back = half-life; if H>0.55 → trade 250-bar momentum "
                      "breakouts instead; in between → flat. Stop loss is what Chan warns most about for MR: ATR-based.")
    description_fa = ("انضباط چان: هرگز فرض نکن سری به میانگین برمی‌گردد — تستش کن. هر ۵۰ کندل: هرست و ADF روی لگاریتم قیمت ۲۵۰ کندل اخیر. "
                      "اگر H<۰.۴۵ و ADF قبول → بازگشت z-score با پنجره = نیمه‌عمر؛ اگر H>۰.۵۵ → شکست مومنتوم؛ بین این دو → بی‌معامله.")
    rules_en = ["regime test every 50 bars (Hurst, ADF, half-life)", "MR regime: z < −2 long, z > +2 short, exit at z = 0", "Momentum regime: 50-bar breakout in direction of 250-bar return"]
    rules_fa = ["تست رژیم هر ۵۰ کندل", "رژیم MR: z < −۲ خرید، z > +۲ فروش، خروج در z = ۰", "رژیم مومنتوم: شکست ۵۰ کندلی در جهت بازده ۲۵۰ کندلی"]

    def run(self, df):
        from core.quant import hurst, adf_test, half_life
        p = self.p
        lp = np.log(df.close)
        n = len(df)
        sig = pd.Series(0, index=df.index)
        exit_l = pd.Series(False, index=df.index); exit_s = pd.Series(False, index=df.index)
        regime = pd.Series(0.0, index=df.index)
        mode, hl = 0, 30
        for i in range(p["win"], n):
            if i % 50 == 0:
                seg = lp.values[i - p["win"]:i]
                H = hurst(seg); a = adf_test(seg)
                if H < 0.45 and a["stationary"]:
                    mode = 1; h = half_life(seg); hl = int(min(100, max(5, h if np.isfinite(h) else 30)))
                elif H > 0.55:
                    mode = 2
                else:
                    mode = 0
            regime.iloc[i] = mode
        z = pd.Series(np.nan, index=df.index)
        for i in range(p["win"], n):
            w = hl
            seg = lp.values[i - w + 1:i + 1]
            sd = seg.std()
            z.iloc[i] = (lp.values[i] - seg.mean()) / sd if sd > 0 else 0
        mr = regime == 1; mo = regime == 2
        long = (mr & self.cross_down(z, -p["z_in"])) | (mo & (df.close > df.high.rolling(50).max().shift(1)) & (lp.diff(p["win"]) > 0))
        short = (mr & self.cross_up(z, p["z_in"])) | (mo & (df.close < df.low.rolling(50).min().shift(1)) & (lp.diff(p["win"]) < 0))
        s = self.make_signal(long, short)
        exit_l[mr & self.cross_up(z, p["z_out"])] = True; exit_s[mr & self.cross_down(z, p["z_out"])] = True
        return _res(df, s, ta.atr(df), p["sl_atr"], p["tp_atr"], panels={"z (Chan)": {"z": z}, "regime 1=MR 2=MOM": {"regime": regime}}, exit_long=exit_l, exit_short=exit_s)


class RegimeAdaptiveEnsemble(Strategy):
    id = "regime_ensemble"
    name_en = "AI-style: regime-adaptive ensemble (TensorTrade/FreqAI idea, no black box)"
    name_fa = "به سبک AI: آنسامبل تطبیقی با رژیم (ایدهٔ TensorTrade/FreqAI، بدون جعبهٔ سیاه)"
    category = "Ensemble"
    author = "TensorTrade / Freqtrade-FreqAI concept: an agent that picks the action per market state; here the 'agent' is the Playbook grade table (transparent)"
    difficulty = 3
    timeframes = "1h, 4h, 1d"
    params = {"k": 3}
    description_en = ("RL bots (TensorTrade) learn a policy state→action. Our transparent version: state = (regime trend/range, volatility high/low); "
                      "policy = the top-k playbook strategies for this timeframe & asset whose category fits the regime (trend followers in trends, "
                      "mean-reversion in ranges); action = majority vote of their fresh signals. Uses data/playbook.json — the bot's own learned table.")
    description_fa = ("بات‌های RL سیاست حالت→عمل یاد می‌گیرند. نسخهٔ شفاف ما: حالت = (رژیم روند/رنج، نوسان بالا/پایین)؛ سیاست = k استراتژی برتر کتاب راهنما برای این تایم‌فریم/دارایی "
                      "که دسته‌شان با رژیم می‌خواند؛ عمل = رأی اکثریت سیگنال‌های تازه‌شان. از جدول یادگرفتهٔ خودِ ربات استفاده می‌کند.")
    rules_en = ["regime: ADX>25 & CHOP<55 = trend, else range", "trend → Trend/Bot/Masters strategies; range → Mean-Reversion/High-WR", "signal = majority of top-k fresh signals"]
    rules_fa = ["رژیم: ADX>۲۵ و CHOP<۵۵ = روند، وگرنه رنج", "روند → استراتژی‌های روندی؛ رنج → بازگشت به میانگین", "سیگنال = اکثریت k سیگنال تازه"]

    def run(self, df):
        import strategies as S
        from core import playbook as PB
        p = self.p
        sym, tf = df.attrs.get("symbol", "BTC/USDT"), df.attrs.get("tf", "1d")
        adx, _, _ = ta.adx(df); ch = I2.choppiness(df)
        trend = (adx > 25) & (ch < 55)
        cands = [sid for sid, _, _ in PB.best_for(tf, sym, k=12)] or ["ema_cross", "rsi2", "supertrend", "bb_bounce"]
        votes = pd.Series(0.0, index=df.index)
        used = 0
        for sid in cands:
            cls = S.REGISTRY.get(sid)
            if not cls or cls.id == self.id or cls.category == "Ensemble":
                continue   # never nest meta-strategies (ensemble ↔ regime_ensemble recursion)
            try:
                s = cls().run(df).signal.fillna(0)
            except Exception:
                continue
            is_trend = cls.category in ("Trend", "Bot-Ported", "Masters' Indicators", "Momentum", "Smart-Money", "Price-Action")
            mask = trend if is_trend else ~trend
            votes += s.where(mask, 0)
            used += 1
            if used >= p["k"] * 2:
                break
        thr = max(1, p["k"] // 2 + 1) if used else 99
        sig = pd.Series(0, index=df.index); sig[votes >= thr] = 1; sig[votes <= -thr] = -1
        sig = sig.where(sig != sig.shift(1), 0)
        return _res(df, sig, ta.atr(df), 2.0, 4.0, panels={"votes": {"votes": votes}})
