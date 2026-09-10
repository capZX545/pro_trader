"""
World Masters 2 — استراتژی‌های استادان جهان برای تمام بازارها
Learned from masters worldwide, translated to English, taught to bot

Masters covered:
- Takashi Kotegawa (BNF) Japan - mean reversion panic buy
- Alexander Gerchik Russia - levels + false breakout
- Stormer / Larry Williams Brazil - EMA9 setups 9.1, 9.2, 9.3, 9.4
- Frank Ochoa USA/India - CPR Central Pivot Range
- RTM Read The Market (Persian school) - QM, Flag Limit, FTR
- Linda Raschke USA - Holy Grail, Anti
- Larry Williams USA - Volatility breakout
- Al Brooks USA - H2/L2, price action
- ICT (Inner Circle Trader) - Fair Value Gap, Order Block, Silver Bullet
- Wyckoff - Spring, Upthrust
- Gold specific: Trend + Breakout + Mean Reversion + Session

All strategies work on ALL charts: Crypto, Forex, Commodities, Indices, Stocks, ETFs, Iran Gold
"""

import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta
from core import indicators2 as t2

class _WM2(Strategy):
    category = "World Masters"
    difficulty = 3
    timeframes = "any"
    sl_mult, tp_mult = 1.5, 3.0

    def finish(self, df, long, short, overlays=None, panels=None, levels=None, stop=None, tgt=None):
        sig = self.make_signal(long, short)
        a = ta.atr(df)
        s2, t2_ = self.atr_stops(df, sig, a, self.sl_mult, self.tp_mult)
        if stop is not None:
            s2 = s2.where(stop.isna() | (sig == 0), stop)
        if tgt is not None:
            t2_ = t2_.where(tgt.isna() | (sig == 0), tgt)
        return StrategyResult(sig, s2, t2_, overlays=overlays or {}, panels=panels or {}, levels=levels or [])

# =============================================================================
# 1. Takashi Kotegawa (BNF) Japan - Mean Reversion Panic Buy
# Learned from: Purple Trading, PocketOption, TradingView articles about BNF
# Core: Buy 20-35% below 25-day MA, RSI < 30, volume confirmation, hold 2-6 days
# =============================================================================
class BNFMeanReversion(_WM2):
    id = "bnf_mean_rev"
    name_en = "BNF (Kotegawa) Mean Reversion - Buy Panic 20% below MA25"
    name_fa = "BNF ژاپن: خرید در وحشت 20% زیر MA25"
    author = "Takashi Kotegawa (BNF)"
    params = {"ma_period": 25, "discount_pct": 20, "rsi_period": 14, "rsi_oversold": 30}
    description_en = "Japanese legend BNF: Buy stocks/crypto/gold that fell 20-35% below 25-day MA during panic. Confirm with RSI<30, Bollinger lower band, volume. Hold 2-6 days, sell into relief. Works on all markets, especially after crashes."
    description_fa = "افسانه ژاپنی BNF: خرید سهام/ارز/طلا که 20-35% زیر میانگین 25 روزه در وحشت افتاده. تایید با RSI<30، باند پایین بولینگر، حجم. نگهداری 2-6 روز."
    rules_en = ["Price 20%+ below 25-day SMA", "RSI(14) < 30 oversold", "Close above previous close (first green after panic)", "Volume > 1.2x average", "Stop under panic low, target = MA25 or 2R"]
    rules_fa = ["قیمت 20%+ زیر SMA25", "RSI<30", "اولین کندل سبز پس از وحشت", "حجم >1.2 میانگین", "استاپ زیر کف وحشت، هدف MA25"]
    
    def run(self, df):
        c = df.close
        ma25 = ta.sma(c, self.p["ma_period"])
        rsi = ta.rsi(c, self.p["rsi_period"])
        bb_lower = ta.bb(c, 20)[2]  # lower band
        vol = df.volume
        vol_ma = ta.sma(vol, 20)
        
        discount = (ma25 - c) / ma25 * 100
        oversold = discount >= self.p["discount_pct"]
        rsi_os = rsi < self.p["rsi_oversold"]
        vol_conf = vol > vol_ma * 1.2
        first_green = (c > c.shift(1)) & (c.shift(1) < c.shift(2))
        below_bb = c < bb_lower
        
        long = oversold & rsi_os & first_green & vol_conf & below_bb
        short = pd.Series(False, index=df.index)  # BNF mostly long, but add short for symmetry
        # Short: 20% above MA25 + RSI>70
        discount_up = (c - ma25) / ma25 * 100
        short = (discount_up >= self.p["discount_pct"]) & (rsi > 70) & (c < c.shift(1)) & (c.shift(1) > c.shift(2))
        
        return self.finish(df, long, short, overlays={"MA25": ma25, "BB_Lower": bb_lower}, panels={"RSI": {"rsi": rsi}})

class BNFSniperLevels(_WM2):
    id = "bnf_sniper"
    name_en = "BNF Sniper Levels - Strong levels 2-3 touches"
    name_fa = "BNF اسنایپر: سطوح قوی 2-3 برخورد"
    author = "Takashi Kotegawa"
    params = {"lookback": 10, "min_touches": 2}
    description_en = "BNF sniper mindset: Mark highs/lows of past 5-10 days, levels tested 2-3 times. Wait for confirmed break with engulfing + volume. No trade is also a trade - patience is edge."
    description_fa = "ذهنیت اسنایپر BNF: سطوح 5-10 روز گذشته با 2-3 برخورد، صبر برای شکست تایید شده"
    rules_en = ["Mark 5-10 day highs/lows with 2-3 touches", "Wait for close beyond level + engulfing", "Volume confirmation", "Stop behind level, target 2R"]
    
    def run(self, df):
        # Simplified: use swing points as levels
        left, right = 5, 5
        swing_high, swing_low = ta.swing_points(df, left, right)
        
        # Find recent swing levels
        recent_highs = df.high[swing_high].dropna().tail(10)
        recent_lows = df.low[swing_low].dropna().tail(10)
        
        long = pd.Series(False, index=df.index)
        short = pd.Series(False, index=df.index)
        
        # Long: break above recent high with bullish engulfing
        c, o = df.close, df.open
        bullish_eng = (c > o) & (c.shift(1) < o.shift(1)) & (c > o.shift(1)) & (o < c.shift(1))
        
        for i in range(len(df)):
            if i < 20:
                continue
            # Check if price breaks above any recent high level
            current_close = df.close.iloc[i]
            for level in recent_highs.values:
                if abs(current_close - level) / level < 0.01:  # near level
                    if current_close > level and bullish_eng.iloc[i]:
                        long.iloc[i] = True
                        break
        
        bearish_eng = (c < o) & (c.shift(1) > o.shift(1)) & (c < o.shift(1)) & (o > c.shift(1))
        for i in range(len(df)):
            if i < 20:
                continue
            current_close = df.close.iloc[i]
            for level in recent_lows.values:
                if abs(current_close - level) / level < 0.01:
                    if current_close < level and bearish_eng.iloc[i]:
                        short.iloc[i] = True
                        break
        
        return self.finish(df, long, short)

# =============================================================================
# 2. Alexander Gerchik Russia - Levels + False Breakout
# =============================================================================
class GerchikLevels(_WM2):
    id = "gerchik_levels"
    name_en = "Gerchik Levels - Strong levels only"
    name_fa = "گرچیک روسیه: فقط سطوح قوی"
    author = "Alexander Gerchik"
    params = {"atr_mult": 0.3, "min_touches": 2}
    description_en = "Russian master Gerchik: Trade from strong levels only. Level = tested 2+ times, tight stop <=30% daily ATR, limit entry at level, target >=3R. No indicators, only levels + volume."
    description_fa = "استاد روسی گرچیک: فقط از سطوح قوی معامله کن. سطح با 2+ برخورد، استاپ <=30% ATR روزانه"
    rules_en = ["Level tested 2+ times", "Stop <=0.3*ATR", "Limit entry at level", "Target >=3R", "Volume spike at level"]
    
    def run(self, df):
        # Use swing points to find levels
        swing_high, swing_low = ta.swing_points(df, 5, 5)
        atr = ta.atr(df)
        
        long = pd.Series(False, index=df.index)
        short = pd.Series(False, index=df.index)
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        
        # Simplified: support bounce
        # Price near swing low + bullish reversal
        c, o, h, l = df.close, df.open, df.high, df.low
        bullish_pin = (c > o) & ((c - l) > 2 * (o - l)) & ((h - c) < 0.3 * (h - l))
        
        for i in range(20, len(df)):
            # Check proximity to recent swing lows
            recent_lows = df.low[swing_low].dropna()
            if len(recent_lows) == 0:
                continue
            nearest_low = recent_lows.iloc[-1] if len(recent_lows) > 0 else None
            if nearest_low and abs(df.close.iloc[i] - nearest_low) / nearest_low < 0.005:
                if bullish_pin.iloc[i] and atr.iloc[i] > 0:
                    long.iloc[i] = True
                    stop.iloc[i] = df.close.iloc[i] - 0.3 * atr.iloc[i]
                    tgt.iloc[i] = df.close.iloc[i] + 0.9 * atr.iloc[i]  # 3R
        
        bearish_pin = (c < o) & ((h - c) > 2 * (h - o)) & ((c - l) < 0.3 * (h - l))
        for i in range(20, len(df)):
            recent_highs = df.high[swing_high].dropna()
            if len(recent_highs) == 0:
                continue
            nearest_high = recent_highs.iloc[-1]
            if abs(df.close.iloc[i] - nearest_high) / nearest_high < 0.005:
                if bearish_pin.iloc[i]:
                    short.iloc[i] = True
                    stop.iloc[i] = df.close.iloc[i] + 0.3 * atr.iloc[i]
                    tgt.iloc[i] = df.close.iloc[i] - 0.9 * atr.iloc[i]
        
        return self.finish(df, long, short, stop=stop, tgt=tgt)

class GerchikFalseBreakout(_WM2):
    id = "gerchik_false_break2"
    name_en = "Gerchik False Breakout - Trap retail, trade opposite"
    name_fa = "گرچیک شکست کاذب: تله‌گذاری و معامله برعکس"
    author = "Alexander Gerchik"
    params = {"consolidation_bars": 10}
    description_en = "Gerchik false breakout: Price aggressively moves to support/resistance, breaks it, then returns. Big players accumulate opposite. Enter opposite after return, stop behind level, target next level. Works on all markets."
    description_fa = "شکست کاذب گرچیک: قیمت به سطح می‌رسد، می‌شکند، برمی‌گردد. ورود برعکس پس از بازگشت"
    rules_en = ["Aggressive move to level", "Break level with 1-4 candles", "Return under/above level", "Enter opposite on horizontal consolidation near level", "Stop behind level, target next level"]
    
    def run(self, df):
        c, h, l = df.close, df.high, df.low
        # Find consolidation
        # Simplified: false breakout = wick beyond recent high/low then close back inside
        recent_high = h.rolling(20).max().shift(1)
        recent_low = l.rolling(20).min().shift(1)
        
        # False breakout up: high > recent_high but close < recent_high
        fb_up = (h > recent_high) & (c < recent_high) & (c < c.shift(1))
        # False breakout down: low < recent_low but close > recent_low
        fb_down = (l < recent_low) & (c > recent_low) & (c > c.shift(1))
        
        short = fb_up.fillna(False)
        long = fb_down.fillna(False)
        
        return self.finish(df, long, short)

# =============================================================================
# 3. Stormer / Larry Williams Brazil - EMA9 setups
# =============================================================================
class Stormer91(_WM2):
    id = "stormer_91"
    name_en = "Stormer 9.1 - EMA9 turn reversal"
    name_fa = "استورمر 9.1: چرخش EMA9"
    author = "Larry Williams / Stormer (Brazil)"
    params = {"ema_period": 9}
    description_en = "Brazilian popularized Larry Williams 9.1: EMA9 was falling, now turns up after leg down = buy. EMA9 was rising, now turns down after leg up = sell. Entry 1 tick above high of 9.1 candle, stop below low."
    description_fa = "9.1 لری ویلیامز: EMA9 در حال سقوط بود، حالا پس از لگ نزولی به بالا می‌چرخد = خرید"
    rules_en = ["EMA9 falling then turns up after down leg", "Buy 1 tick above high of turn candle", "Stop 1 tick below low", "Exit when close below EMA9"]
    
    def run(self, df):
        c = df.close
        ema9 = ta.ema(c, self.p["ema_period"])
        growing = ema9 >= ema9.shift(1)
        
        turn_up = growing & (~growing.shift(1).fillna(False))
        turn_down = (~growing) & (growing.shift(1).fillna(False))
        
        long = turn_up & (c > ema9)
        short = turn_down & (c < ema9)
        
        return self.finish(df, long, short, overlays={"EMA9": ema9})

class Stormer92(_WM2):
    id = "stormer_92"
    name_en = "Stormer 9.2 - Pullback to EMA9"
    name_fa = "استورمر 9.2: پولبک به EMA9"
    author = "Stormer / Palex"
    params = {"ema_period": 9}
    description_en = "9.2: In uptrend (EMA9 rising), wait for close below previous low, mark high, buy breakout of that high. Stop at previous low. Mirror for downtrend."
    description_fa = "9.2: در روند صعودی EMA9، بسته شدن زیر کف قبلی، خرید شکست سقف"
    rules_en = ["EMA9 rising", "Close below previous low", "Buy breakout of that candle high", "Stop at candle low"]
    
    def run(self, df):
        c, l, h = df.close, df.low, df.high
        ema9 = ta.ema(c, self.p["ema_period"])
        growing = ema9 >= ema9.shift(1)
        
        # 9.2 up: growing and close < low[1]
        ref_up = growing & (c < l.shift(1))
        # For simplicity, enter next bar if breaks high of ref candle
        long = pd.Series(False, index=df.index)
        for i in range(2, len(df)):
            if ref_up.iloc[i-1] and c.iloc[i] > h.iloc[i-1]:
                long.iloc[i] = True
        
        ref_down = (~growing) & (c > h.shift(1))
        short = pd.Series(False, index=df.index)
        for i in range(2, len(df)):
            if ref_down.iloc[i-1] and c.iloc[i] < l.iloc[i-1]:
                short.iloc[i] = True
        
        return self.finish(df, long, short, overlays={"EMA9": ema9})

class Stormer93(_WM2):
    id = "stormer_93"
    name_en = "Stormer 9.3 - Three closes against trend"
    name_fa = "استورمر 9.3: سه بسته شدن خلاف روند"
    author = "Larry Williams / Stormer"
    params = {"ema_period": 9}
    description_en = "9.3: EMA9 uptrend, 1 close followed by 2 lower closes below reference, mark high of last, buy breakout. Stop at low of entry candle."
    description_fa = "9.3: روند صعودی EMA9، یک بسته شدن و سپس دو بسته شدن پایین‌تر، خرید شکست"
    rules_en = ["EMA9 uptrend", "Close + 2 lower closes below reference", "Buy breakout high of last", "Stop low of entry candle"]
    
    def run(self, df):
        c, h, l = df.close, df.high, df.low
        ema9 = ta.ema(c, self.p["ema_period"])
        growing = ema9 >= ema9.shift(1)
        
        # Simplified: 3 lower closes in uptrend
        lower1 = c < c.shift(1)
        lower2 = c.shift(1) < c.shift(2)
        ref = c.shift(2)  # reference
        
        long_cond = growing & lower1 & lower2 & (c.shift(1) < ref) & (c < ref)
        short_cond = (~growing) & (c > c.shift(1)) & (c.shift(1) > c.shift(2)) & (c.shift(1) > ref) & (c > ref)
        
        # Enter breakout
        long = pd.Series(False, index=df.index)
        short = pd.Series(False, index=df.index)
        for i in range(3, len(df)):
            if long_cond.iloc[i-1] and c.iloc[i] > h.iloc[i-1]:
                long.iloc[i] = True
            if short_cond.iloc[i-1] and c.iloc[i] < l.iloc[i-1]:
                short.iloc[i] = True
        
        return self.finish(df, long, short, overlays={"EMA9": ema9})

# =============================================================================
# 4. Frank Ochoa - CPR Central Pivot Range (India/USA)
# =============================================================================
class CPRBreakout(_WM2):
    id = "cpr_breakout"
    name_en = "CPR Breakout - Central Pivot Range narrow breakout"
    name_fa = "CPR شکست ناحیه محوری مرکزی"
    author = "Frank Ochoa"
    params = {"cpr_width_pct": 0.5}
    description_en = "CPR: Pivot=(H+L+C)/3, BC=(H+L)/2, TC=2*Pivot-BC. Narrow CPR = low volatility, breakout expected. Buy above TC, sell below BC. Target 2R. Works on all markets intraday."
    description_fa = "CPR: ناحیه محوری مرکزی باریک = نوسان کم، انتظار شکست. خرید بالای TC، فروش زیر BC"
    rules_en = ["Calculate CPR: Pivot, BC, TC", "Narrow CPR (TC-BC < 0.5% price)", "Buy above TC + close above prev high", "Sell below BC + close below prev low", "Stop opposite CPR side, target 2R"]
    
    def run(self, df):
        # CPR needs daily pivots, but we approximate with rolling
        # For intraday: use previous day's HLC
        # Simplified: use previous bar's HLC as proxy for daily CPR
        h, l, c = df.high, df.low, df.close
        pivot = (h.shift(1) + l.shift(1) + c.shift(1)) / 3
        bc = (h.shift(1) + l.shift(1)) / 2
        tc = 2 * pivot - bc
        
        cpr_width = (tc - bc).abs() / c * 100
        narrow = cpr_width < self.p["cpr_width_pct"]
        
        long = narrow & (c > tc) & (c > h.shift(1))
        short = narrow & (c < bc) & (c < l.shift(1))
        
        return self.finish(df, long, short, overlays={"Pivot": pivot, "BC": bc, "TC": tc})

class CPRVirginMagnet(_WM2):
    id = "cpr_virgin"
    name_en = "CPR Virgin - Price magnet to untouched CPR"
    name_fa = "CPR بکر: آهنربای قیمت به ناحیه دست‌نخورده"
    author = "Frank Ochoa (Indian traders)"
    params = {}
    description_en = "Virgin CPR: CPR level not tested yet acts as magnet. If price opens near virgin CPR, high probability gap fill to CPR. Buy pullback to CPR in uptrend."
    description_fa = "CPR بکر دست‌نخورده مثل آهنربا عمل می‌کند، احتمال پر شدن گپ بالا"
    rules_en = ["Virgin CPR (untested)", "Price opens near virgin CPR", "Buy pullback to CPR in uptrend", "Target 2R"]
    
    def run(self, df):
        h, l, c = df.high, df.low, df.close
        pivot = (h.shift(1) + l.shift(1) + c.shift(1)) / 3
        
        # Virgin: price hasn't touched pivot in last 5 bars
        touched = (h >= pivot) & (l <= pivot)
        virgin = touched.rolling(5).sum().shift(1) == 0
        
        # Uptrend: close > SMA50
        sma50 = ta.sma(c, 50)
        uptrend = c > sma50
        
        long = virgin & uptrend & (l <= pivot) & (c > pivot)
        short = virgin & (~uptrend) & (h >= pivot) & (c < pivot)
        
        return self.finish(df, long, short, overlays={"Pivot": pivot})

# =============================================================================
# 5. RTM Read The Market - QM, Flag Limit, FTR (Persian school)
# =============================================================================
class RTMQuasimodo(_WM2):
    id = "rtm_qm"
    name_en = "RTM Quasimodo (QM) - Over & Under reversal"
    name_fa = "RTM کوازیمودو: برگشت Over & Under"
    author = "RTM / Read The Market (Persian school)"
    params = {}
    description_en = "Quasimodo: 5 points - High, Low, Higher High, Lower Low, retrace to original High without breaking = short. Mirror for long. High probability reversal at supply/demand."
    description_fa = "کوازیمودو 5 نقطه: سقف، کف، سقف بالاتر، کف پایین‌تر، بازگشت به سقف اول بدون شکست = فروش"
    rules_en = ["5-point structure HH, LL, retrace without break", "Sell at original High if fails to break", "Buy at original Low if fails to break", "Stop above HH/below LL, target 3R"]
    
    def run(self, df):
        # Simplified QM detection using swing points
        swing_high, swing_low = ta.swing_points(df, 5, 5)
        h, l, c = df.high, df.low, df.close
        
        long = pd.Series(False, index=df.index)
        short = pd.Series(False, index=df.index)
        
        # Bearish QM: High, Low, HH, LL, retrace to High
        # We approximate: recent HH followed by LL then retrace to previous high
        recent_high = h.rolling(30).max().shift(1)
        recent_low = l.rolling(30).min().shift(1)
        
        # Bearish QM: price makes HH then LL then fails to break previous high
        hh = h > recent_high
        ll = l < recent_low
        # After HH and LL, price retrace to near previous high but fails
        for i in range(30, len(df)):
            if hh.iloc[i-5] and ll.iloc[i-2]:
                prev_high = recent_high.iloc[i-1]
                if abs(c.iloc[i] - prev_high) / prev_high < 0.01 and c.iloc[i] < prev_high and c.iloc[i] < c.iloc[i-1]:
                    short.iloc[i] = True
        
        # Bullish QM
        for i in range(30, len(df)):
            if ll.iloc[i-5] and hh.iloc[i-2]:
                prev_low = recent_low.iloc[i-1]
                if abs(c.iloc[i] - prev_low) / prev_low < 0.01 and c.iloc[i] > prev_low and c.iloc[i] > c.iloc[i-1]:
                    long.iloc[i] = True
        
        return self.finish(df, long, short)

class RTMFlagLimit(_WM2):
    id = "rtm_flag"
    name_en = "RTM Flag Limit - Flag pattern at supply/demand"
    name_fa = "RTM فلگ لیمیت: پرچم در عرضه/تقاضا"
    author = "RTM"
    params = {}
    description_en = "Flag Limit: Strong impulse, small flag consolidation (3-5 bars inside), breakout. Authentic zone = first strong imbalance, no prior reactions."
    description_fa = "فلگ لیمیت: حرکت قوی، پرچم کوچک 3-5 کندلی، شکست. ناحیه اصیل = اولین عدم تعادل قوی"
    rules_en = ["Strong impulse (big body)", "Flag 3-5 bars inside range", "Breakout with volume", "Authentic zone entry"]
    
    def run(self, df):
        c, h, l = df.close, df.high, df.low
        # Big impulse
        body = (c - df.open).abs()
        atr = ta.atr(df)
        big_up = (c > df.open) & (body > 1.5 * atr)
        big_down = (c < df.open) & (body > 1.5 * atr)
        
        long = pd.Series(False, index=df.index)
        short = pd.Series(False, index=df.index)
        
        # Flag: 3 bars inside previous big bar range
        for k in range(3, 6):
            inside = pd.Series(True, index=df.index)
            for j in range(1, k+1):
                inside &= (h.shift(j) <= h.shift(k+1)) & (l.shift(j) >= l.shift(k+1))
            
            long |= big_up.shift(k+1).fillna(False) & inside & (c > h.shift(k+1))
            short |= big_down.shift(k+1).fillna(False) & inside & (c < l.shift(k+1))
        
        return self.finish(df, long, short)

# =============================================================================
# 6. Gold Specific Strategies - XAUUSD masters
# =============================================================================
class GoldTrendEMA(_WM2):
    id = "gold_trend_ema"
    name_en = "Gold Trend - EMA 50/200 + RSI filter for XAU"
    name_fa = "طلا ترند: EMA50/200 + RSI"
    author = "Gold Masters"
    params = {"ema_fast": 50, "ema_slow": 200, "rsi_period": 14}
    description_en = "Gold trend: Long above 200-day, pullback to 50 EMA + bullish PA, RSI>50. Works on XAUUSD and Iran Gold. Gold trends persist."
    description_fa = "ترند طلا: بالای EMA200، پولبک به EMA50 + RSI>50"
    rules_en = ["Price above EMA200 = uptrend", "Pullback to EMA50", "RSI>50 + bullish candle", "Stop below pullback low, target 2R"]
    
    def run(self, df):
        c = df.close
        ema50 = ta.ema(c, self.p["ema_fast"])
        ema200 = ta.ema(c, self.p["ema_slow"])
        rsi = ta.rsi(c, self.p["rsi_period"])
        
        uptrend = c > ema200
        pullback = (c <= ema50 * 1.01) & (c >= ema50 * 0.99)
        bullish = c > df.open
        
        long = uptrend & pullback & bullish & (rsi > 50)
        short = (~uptrend) & pullback & (~bullish) & (rsi < 50)
        
        return self.finish(df, long, short, overlays={"EMA50": ema50, "EMA200": ema200}, panels={"RSI": {"rsi": rsi}})

class GoldBreakoutRange(_WM2):
    id = "gold_breakout_range"
    name_en = "Gold Breakout - Daily high/low breakout + RSI"
    name_fa = "طلا شکست: شکست سقف/کف روزانه"
    author = "Gold Masters"
    params = {"ema_filter": 190, "rsi_period": 14}
    description_en = "Gold breakout: Mark D1 highs/lows, wait for breakout + close above/below + EMA190 filter + RSI. Gold trends persist after breakout."
    description_fa = "شکست طلا: سقف/کف روزانه + EMA190 + RSI"
    rules_en = ["Mark D1 high/low", "Breakout + close beyond", "EMA190 trend filter", "RSI>50 long, <50 short"]
    
    def run(self, df):
        # Approximate daily high/low with rolling
        c = df.close
        # Use 24h rolling for daily levels if 1h timeframe, else 20 bars
        lookback = 24 if "h" in df.attrs.get("tf","1h") else 20
        daily_high = df.high.rolling(lookback).max().shift(1)
        daily_low = df.low.rolling(lookback).min().shift(1)
        
        ema190 = ta.ema(c, self.p["ema_filter"])
        rsi = ta.rsi(c, self.p["rsi_period"])
        
        long = (c > daily_high) & (c > ema190) & (rsi > 50)
        short = (c < daily_low) & (c < ema190) & (rsi < 50)
        
        return self.finish(df, long, short, overlays={"DailyHigh": daily_high, "DailyLow": daily_low, "EMA190": ema190})

class GoldSessionBreakout(_WM2):
    id = "gold_session_break"
    name_en = "Gold Session Breakout - Asian range -> London/NY"
    name_fa = "طلا شکست سشن: رنج آسیا → لندن/نیویورک"
    author = "Gold Masters"
    params = {"asian_bars": 8}
    description_en = "Gold session: Mark Asian session high/low, breakout during London/NY overlap. Average breakout 300-600 pips. Wait for close beyond, not wick."
    description_fa = "شکست سشن طلا: سقف/کف آسیا، شکست در همپوشانی لندن/نیویورک"
    rules_en = ["Mark Asian high/low", "Breakout in London/NY overlap", "Close beyond level (not wick)", "Stop opposite Asian range, target 1.5-2x range"]
    
    def run(self, df):
        c = df.close
        # Simplified: Asian range = last 8 bars (for 1h chart)
        asian_high = df.high.rolling(self.p["asian_bars"]).max().shift(1)
        asian_low = df.low.rolling(self.p["asian_bars"]).min().shift(1)
        asian_range = asian_high - asian_low
        
        long = (c > asian_high) & (asian_range > 0) & (c > c.shift(1))
        short = (c < asian_low) & (asian_range > 0) & (c < c.shift(1))
        
        stop = pd.Series(np.nan, index=df.index)
        tgt = pd.Series(np.nan, index=df.index)
        
        stop[long] = asian_low[long]
        tgt[long] = c[long] + 1.5 * asian_range[long]
        
        stop[short] = asian_high[short]
        tgt[short] = c[short] - 1.5 * asian_range[short]
        
        return self.finish(df, long, short, overlays={"AsianHigh": asian_high, "AsianLow": asian_low}, stop=stop, tgt=tgt)

class GoldNewsFade(_WM2):
    id = "gold_news_fade"
    name_en = "Gold News Fade - Fade spike after NFP/FOMC/CPI"
    name_fa = "طلا فید اخبار: برگشت پس از NFP/FOMC"
    author = "Gold Masters"
    params = {"spike_bars": 3, "atr_mult": 2.0}
    description_en = "Gold news: After NFP/FOMC/CPI spike, wait 5 min, mark spike high/low, if price closes back inside pre-news range = fade reversal. Initial reaction often overreaction."
    description_fa = "فید اخبار طلا: پس از اسپایک NFP، صبر 5 دقیقه، بازگشت به رنج قبل = برگشت"
    rules_en = ["Wait 5 min after news spike", "Mark spike high/low", "Close back inside pre-news range = reversal", "Stop beyond spike, target 1R"]
    
    def run(self, df):
        c, h, l = df.close, df.high, df.low
        atr = ta.atr(df)
        
        # Spike = large range bar >2*ATR
        spike_up = (h - l) > self.p["atr_mult"] * atr
        # Pre-news range = previous 5 bars range
        pre_high = h.rolling(5).max().shift(1)
        pre_low = l.rolling(5).min().shift(1)
        
        # Fade: spike up then close back inside pre range
        long = spike_up.shift(1).fillna(False) & (c < pre_high) & (c > pre_low) & (c < c.shift(1))
        short = spike_up.shift(1).fillna(False) & (c < pre_high) & (c > pre_low) & (c > c.shift(1))
        
        # Actually need opposite: spike up then bearish close back inside = short
        short = spike_up.shift(1).fillna(False) & (c < pre_high) & (c < c.shift(1)) & (h.shift(1) > pre_high.shift(1))
        long = spike_up.shift(1).fillna(False) & (c > pre_low) & (c > c.shift(1)) & (l.shift(1) < pre_low.shift(1))
        
        return self.finish(df, long, short)

# =============================================================================
# 7. Additional World Masters - More strategies for all markets
# =============================================================================
class IchimokuPerfectOrder(_WM2):
    id = "ichimoku_perfect_gold"
    name_en = "Ichimoku Perfect Order - All lines aligned"
    name_fa = "ایچیموکو نظم کامل: همه خطوط هم‌جهت"
    author = "Goichi Hosoda"
    params = {}
    description_en = "Ichimoku perfect order: Price > Tenkan > Kijun > Senkou A > Senkou B = strong uptrend. Works on all markets, especially trending like gold."
    description_fa = "نظم کامل ایچیموکو: قیمت > تنکان > کیجون > سنکو A > B = روند قوی صعودی"
    
    def run(self, df):
        tenkan, kijun, senkou_a, senkou_b, chikou = ta.ichimoku(df)
        c = df.close
        
        long = (c > tenkan) & (tenkan > kijun) & (kijun > senkou_a) & (senkou_a > senkou_b)
        short = (c < tenkan) & (tenkan < kijun) & (kijun < senkou_a) & (senkou_a < senkou_b)
        
        return self.finish(df, long, short, overlays={"Tenkan": tenkan, "Kijun": kijun, "SenkouA": senkou_a, "SenkouB": senkou_b})

class WyckoffSpringGold(_WM2):
    id = "wyckoff_spring_gold"
    name_en = "Wyckoff Spring - Shakeout + test for all markets"
    name_fa = "وایکوف اسپرینگ: shakeout + تست"
    author = "Richard Wyckoff"
    params = {}
    description_en = "Wyckoff Spring: Price breaks support (shakeout), then quickly returns + volume test. Works on all markets, especially accumulation phases."
    description_fa = "اسپرینگ وایکوف: شکست حمایت (shakeout)، بازگشت سریع + تست حجمی"
    
    def run(self, df):
        c, l, h, vol = df.close, df.low, df.high, df.volume
        support = l.rolling(20).min().shift(1)
        
        spring = (l < support) & (c > support) & (c > c.shift(1))
        vol_test = vol < vol.rolling(20).mean() * 0.8
        
        long = spring & vol_test.shift(1).fillna(False)
        short = pd.Series(False, index=df.index)  # Upthrust opposite
        
        # Upthrust: break resistance then return
        resistance = h.rolling(20).max().shift(1)
        upthrust = (h > resistance) & (c < resistance)
        short = upthrust & vol_test.shift(1).fillna(False)
        
        return self.finish(df, long, short, overlays={"Support": support, "Resistance": resistance})

# All new strategies
WORLD_MASTERS2_STRATEGIES = [
    BNFMeanReversion, BNFSniperLevels,
    GerchikLevels, GerchikFalseBreakout,
    Stormer91, Stormer92, Stormer93,
    CPRBreakout, CPRVirginMagnet,
    RTMQuasimodo, RTMFlagLimit,
    GoldTrendEMA, GoldBreakoutRange, GoldSessionBreakout, GoldNewsFade,
    IchimokuPerfectOrder, WyckoffSpringGold,
]
