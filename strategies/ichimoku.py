"""Ichimoku Kinko Hyo — the COMPLETE Hosoda system taught to the bot (Phase 17).

Learned from: Hosoda's three theories (time 時間論, wave 波動論, price 値幅観測論), Nicole Elliott "Ichimoku Charts",
Manesh Patel "Trading with Ichimoku Clouds", Karen Péloille, and 2025–26 crypto practitioner guides
(ChartingLens, indicator.trading, BingX). Every strategy below is one *named* Ichimoku signal with its
strength grading (strong / neutral / weak by location relative to the Kumo) so the bot can quote why it fires.

Shared engine: `ichimoku_full(df, t, k, s)` → dict with tenkan, kijun, span_a/span_b (displaced, as drawn),
future cloud (undisplaced, what the twist tells us about the next `k` bars), chikou free/obstructed flags,
cloud thickness, flat-kijun/flat-span-B flags, kihon-suchi time counts and N/V/E/NT price targets.
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta

KIHON_SUCHI = (9, 17, 26, 33, 42, 51, 65, 76, 83, 97, 101, 129, 172, 200, 257)      # Hosoda's basic numbers


def ichimoku_full(df, t=9, k=26, s=52, disp=None):
    disp = disp or k
    hi, lo, c = df.high, df.low, df.close
    tenkan = (hi.rolling(t).max() + lo.rolling(t).min()) / 2
    kijun = (hi.rolling(k).max() + lo.rolling(k).min()) / 2
    span_a_raw = (tenkan + kijun) / 2                                   # value that will be drawn `disp` bars ahead
    span_b_raw = (hi.rolling(s).max() + lo.rolling(s).min()) / 2
    span_a = span_a_raw.shift(disp)                                      # cloud under today's price (as drawn)
    span_b = span_b_raw.shift(disp)
    cloud_top = pd.concat([span_a, span_b], axis=1).max(axis=1)
    cloud_bot = pd.concat([span_a, span_b], axis=1).min(axis=1)
    thick = (cloud_top - cloud_bot)
    atr = ta.atr(df, 14)
    # Chikou (today's close vs price `disp` bars ago) — "free" when it is clear of the candles AND the cloud of that time
    past_hi = hi.shift(disp); past_lo = lo.shift(disp)
    past_top = cloud_top.shift(disp); past_bot = cloud_bot.shift(disp)
    chikou_bull = (c > past_hi) & (c > past_top.fillna(-np.inf))
    chikou_bear = (c < past_lo) & (c < past_bot.fillna(np.inf))
    # future cloud (what is drawn ahead of the last candle) = raw spans
    fut_bull = span_a_raw > span_b_raw
    twist_up = fut_bull & ~fut_bull.shift(1).fillna(False).astype(bool)
    twist_dn = ~fut_bull & fut_bull.shift(1).fillna(True).astype(bool)
    flat_kijun = kijun.diff().abs() < 1e-12
    flat_b = span_b_raw.diff().abs() < 1e-12
    return dict(tenkan=tenkan, kijun=kijun, span_a=span_a, span_b=span_b, span_a_raw=span_a_raw, span_b_raw=span_b_raw,
                cloud_top=cloud_top, cloud_bot=cloud_bot, thick=thick, thick_atr=thick / atr.replace(0, np.nan), atr=atr,
                chikou_bull=chikou_bull, chikou_bear=chikou_bear, fut_bull=fut_bull, twist_up=twist_up, twist_dn=twist_dn,
                flat_kijun=flat_kijun, flat_b=flat_b,
                above=c > cloud_top, below=c < cloud_bot, inside=(c <= cloud_top) & (c >= cloud_bot))


def wave_targets(df, lookback=200, left=5, right=5):
    """Hosoda price theory on the last N-wave (A→B→C): returns dict of N/V/E/NT targets and the wave points, or None."""
    seg = df.tail(lookback)
    sh, sl = ta.swing_points(seg, left, right)
    hi_idx, lo_idx = np.where(sh.values)[0], np.where(sl.values)[0]
    pts = sorted([(int(i), float(seg.high.iloc[i]), "H") for i in hi_idx] + [(int(i), float(seg.low.iloc[i]), "L") for i in lo_idx])
    # collapse consecutive same-type points (keep the extreme)
    clean = []
    for p in pts:
        if clean and clean[-1][2] == p[2]:
            if (p[2] == "H" and p[1] > clean[-1][1]) or (p[2] == "L" and p[1] < clean[-1][1]):
                clean[-1] = p
        else:
            clean.append(p)
    if len(clean) < 3:
        return None
    A, B, Cp = clean[-3], clean[-2], clean[-1]
    a, b, cc = A[1], B[1], Cp[1]
    up = A[2] == "L"                                           # A low → B high → C higher low = bullish N wave
    sgn = 1 if up else -1
    tg = {"N": cc + sgn * abs(b - a), "V": b + sgn * abs(b - cc), "E": b + sgn * abs(b - a), "NT": cc + sgn * abs(cc - a)}
    bars_since_c = len(seg) - 1 - Cp[0]
    return dict(A=a, B=b, C=cc, up=up, targets=tg, bars_since_C=bars_since_c,
                next_kihon=[n for n in KIHON_SUCHI if n >= bars_since_c][:2],
                idx=(int(len(df) - lookback + A[0]) if len(df) >= lookback else A[0], int(len(df) - len(seg) + B[0]), int(len(df) - len(seg) + Cp[0])))


def _result(df, ic, sig, stop_mode="kijun", rr=2.0, extra_over=None, levels=None):
    a = ic["atr"]; k = ic["kijun"]
    stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
    lo, sh = sig == 1, sig == -1
    if stop_mode == "kijun":
        stop[lo] = np.minimum(k[lo] - 0.5 * a[lo], df.close[lo] - 0.8 * a[lo])
        stop[sh] = np.maximum(k[sh] + 0.5 * a[sh], df.close[sh] + 0.8 * a[sh])
    elif stop_mode == "cloud":
        stop[lo] = np.minimum(ic["cloud_bot"][lo] - 0.3 * a[lo], df.close[lo] - 0.8 * a[lo])
        stop[sh] = np.maximum(ic["cloud_top"][sh] + 0.3 * a[sh], df.close[sh] + 0.8 * a[sh])
    else:
        stop[lo] = df.close[lo] - 1.5 * a[lo]; stop[sh] = df.close[sh] + 1.5 * a[sh]
    risk = (df.close - stop).abs()
    tgt[lo] = df.close[lo] + rr * risk[lo]; tgt[sh] = df.close[sh] - rr * risk[sh]
    over = {"Tenkan": ic["tenkan"], "Kijun": ic["kijun"], "Senkou A": ic["span_a"], "Senkou B": ic["span_b"], "Chikou": df.close.shift(-int(ic.get("disp", 26)))}
    if extra_over:
        over.update(extra_over)
    return StrategyResult(sig, stop, tgt, overlays=over, levels=levels or [])


class _Ichi(Strategy):
    category = "Trend"
    author = "Goichi Hosoda (Ichimoku Sanjin)"
    difficulty = 3
    params = {"tenkan": 9, "kijun": 26, "senkou": 52}

    def ic(self, df):
        p = self.p
        d = ichimoku_full(df, p["tenkan"], p["kijun"], p["senkou"])
        d["disp"] = p["kijun"]
        return d


class IchimokuPerfect(_Ichi):
    id = "ichimoku_perfect"
    name_en = "Ichimoku 'Perfect Order' (all 5 elements aligned)"
    name_fa = "ایچیموکو «ترتیب کامل» (هم‌راستایی هر ۵ عنصر)"
    timeframes = "1h – 1d"
    description_en = ("Sanyaku-kouten (three-role bullish): TK cross above the cloud + future cloud bullish + Chikou free. "
                      "Fires on the bar where the LAST missing element aligns, so it is later than a plain TK cross but far cleaner.")
    description_fa = ("سان‌یاکو کوتن (سه‌نقش صعودی): کراس TK بالای ابر + ابر آینده صعودی + چیکو آزاد. "
                      "روی کندلی فعال می‌شود که آخرین عنصر ناقص هم‌راستا شود؛ دیرتر از کراس ساده ولی بسیار تمیزتر.")
    rules_en = ["Price above Kumo", "Tenkan > Kijun", "Future cloud Span A > Span B", "Chikou above price & cloud 26 bars ago",
                "Entry when the alignment first becomes complete; stop under Kijun; target 2R"]
    rules_fa = ["قیمت بالای ابر", "تنکان > کیجون", "ابر آینده A > B", "چیکو بالای قیمت و ابر ۲۶ کندل قبل",
                "ورود در اولین کندل هم‌راستایی کامل؛ استاپ زیر کیجون؛ هدف 2R"]
    pros_en = ["Highest-quality Ichimoku signal", "Rare false positives in trends"]; cons_en = ["Late", "Long flat periods in ranges"]
    pros_fa = ["باکیفیت‌ترین سیگنال ایچیموکو", "خطای کم در روند"]; cons_fa = ["دیر", "در رنج مدت‌ها ساکت"]

    def run(self, df):
        ic = self.ic(df)
        bull = ic["above"] & (ic["tenkan"] > ic["kijun"]) & ic["fut_bull"] & ic["chikou_bull"]
        bear = ic["below"] & (ic["tenkan"] < ic["kijun"]) & ~ic["fut_bull"] & ic["chikou_bear"]
        long = bull & ~bull.shift(1).fillna(False).astype(bool)
        short = bear & ~bear.shift(1).fillna(False).astype(bool)
        return _result(df, ic, self.make_signal(long, short), "kijun", 2.0)


class IchimokuTKGraded(_Ichi):
    id = "ichimoku_tk_strong"
    name_en = "Ichimoku TK cross — strong grade only (above/below Kumo)"
    name_fa = "کراس تنکان/کیجون ایچیموکو — فقط درجهٔ قوی (بالا/پایین ابر)"
    timeframes = "15m – 4h"
    description_en = ("Hosoda grades a TK cross by location: strong when it happens on the trend side of the cloud, neutral inside, weak against it. "
                      "Only strong crosses with a thick enough cloud (≥ 0.5 ATR) and Chikou not obstructed are taken.")
    description_fa = ("هوسودا کراس TK را با مکان درجه‌بندی می‌کند: قوی در سمت روند ابر، خنثی داخل ابر، ضعیف مخالف آن. "
                      "فقط کراس‌های قوی با ابر به‌اندازهٔ کافی ضخیم (≥ ۰.۵ ATR) و چیکوی بدون مانع گرفته می‌شوند.")
    rules_en = ["Long: Tenkan crosses up Kijun while close > cloud top, cloud thickness ≥ 0.5 ATR, Chikou not below past price", "Short mirror", "Stop under Kijun, 2R"]
    rules_fa = ["خرید: کراس صعودی تنکان/کیجون وقتی close > سقف ابر، ضخامت ابر ≥ ۰.۵ ATR، چیکو زیر قیمت گذشته نباشد", "فروش برعکس", "استاپ زیر کیجون، 2R"]
    pros_en = ["Timely entry with quality filter"]; cons_en = ["Whipsaws when the cloud is thin"]
    pros_fa = ["ورود به‌موقع با فیلتر کیفیت"]; cons_fa = ["ویپساو وقتی ابر نازک است"]
    params = {"tenkan": 9, "kijun": 26, "senkou": 52, "min_thick_atr": 0.5}

    def run(self, df):
        ic = self.ic(df)
        thick_ok = ic["thick_atr"] >= self.p["min_thick_atr"]
        long = self.cross_up(ic["tenkan"], ic["kijun"]) & ic["above"] & thick_ok & ~ic["chikou_bear"]
        short = self.cross_down(ic["tenkan"], ic["kijun"]) & ic["below"] & thick_ok & ~ic["chikou_bull"]
        return _result(df, ic, self.make_signal(long, short), "kijun", 2.0)


class IchimokuKumoBreakout(_Ichi):
    id = "ichimoku_kumo_breakout"
    name_en = "Ichimoku Kumo breakout (close through the cloud)"
    name_fa = "شکست ابر ایچیموکو (بسته‌شدن آن‌سوی کومو)"
    timeframes = "1h – 1d"
    description_en = ("Trend declaration: a close exits the cloud after having been inside/on the other side. Stronger when the cloud ahead agrees "
                      "and Chikou also clears its own cloud. Stop back inside the far cloud edge.")
    description_fa = ("اعلام روند: بسته‌شدن قیمت بیرون ابر بعد از بودن داخل/سمت دیگر. قوی‌تر وقتی ابر پیش‌رو هم‌جهت باشد و چیکو هم ابر خودش را رد کند. استاپ داخل لبهٔ دور ابر.")
    rules_en = ["Long: close crosses above cloud top (was ≤ top on previous bar), future cloud bullish", "Short mirror", "Stop under cloud bottom − 0.3 ATR; target 2R"]
    rules_fa = ["خرید: close از سقف ابر عبور کند (کندل قبل ≤ سقف)، ابر آینده صعودی", "فروش برعکس", "استاپ زیر کف ابر − ۰.۳ ATR؛ هدف 2R"]
    pros_en = ["Catches new trends early"]; cons_en = ["False breaks through thin clouds"]
    pros_fa = ["روند تازه را زود می‌گیرد"]; cons_fa = ["شکست کاذب در ابر نازک"]

    def run(self, df):
        ic = self.ic(df)
        long = self.cross_up(df.close, ic["cloud_top"]) & ic["fut_bull"]
        short = self.cross_down(df.close, ic["cloud_bot"]) & ~ic["fut_bull"]
        return _result(df, ic, self.make_signal(long, short), "cloud", 2.0)


class IchimokuKijunBounce(_Ichi):
    id = "ichimoku_kijun_bounce"
    name_en = "Ichimoku Kijun-sen bounce (50 % equilibrium pullback)"
    name_fa = "برگشت از کیجون‌سن (پولبک ۵۰٪ تعادل)"
    timeframes = "15m – 4h"
    description_en = ("The Kijun is the 26-bar 50 % retracement drawn automatically. In an established trend (price above cloud, Tenkan > Kijun) a touch of the "
                      "Kijun followed by a close back above it is the classic 'buy the dip'. A flat Kijun attracts price — bounce entries near a flat Kijun are the best.")
    description_fa = ("کیجون همان اصلاح ۵۰٪ ۲۶ کندلی است که خودکار رسم می‌شود. در روند تثبیت‌شده (قیمت بالای ابر، تنکان > کیجون) لمس کیجون و بسته‌شدن دوباره بالای آن = خرید کلاسیک دیپ. کیجون صاف قیمت را جذب می‌کند.")
    rules_en = ["Trend: close above cloud & Tenkan > Kijun", "Low ≤ Kijun and close > Kijun (rejection)", "Stop under the bounce low − 0.3 ATR; target 2R", "Short mirror"]
    rules_fa = ["روند: close بالای ابر و تنکان > کیجون", "کف ≤ کیجون و close > کیجون (رد شدن)", "استاپ زیر کف برگشت − ۰.۳ ATR؛ هدف 2R", "فروش برعکس"]
    pros_en = ["Tight stops, trend-with entries"]; cons_en = ["Fails when the trend is ending"]
    pros_fa = ["استاپ کوچک، ورود در جهت روند"]; cons_fa = ["در پایان روند شکست می‌خورد"]

    def run(self, df):
        ic = self.ic(df); k = ic["kijun"]; a = ic["atr"]
        long = ic["above"] & (ic["tenkan"] > k) & (df.low <= k) & (df.close > k) & (df.low.shift(1) > k.shift(1))
        short = ic["below"] & (ic["tenkan"] < k) & (df.high >= k) & (df.close < k) & (df.high.shift(1) < k.shift(1))
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = df.low[sig == 1] - 0.3 * a[sig == 1]; stop[sig == -1] = df.high[sig == -1] + 0.3 * a[sig == -1]
        risk = (df.close - stop).abs(); tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]; tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        r = _result(df, ic, sig); r.stop, r.target = stop, tgt
        return r


class IchimokuKumoTwist(_Ichi):
    id = "ichimoku_kumo_twist"
    name_en = "Ichimoku Kumo twist + price confirmation"
    name_fa = "چرخش ابر (کومو توئیست) + تأیید قیمت"
    timeframes = "1h – 1d"
    description_en = ("The twist (Span A crossing Span B in the FUTURE cloud) is the only anticipatory Ichimoku signal. It is a warning, not an entry: "
                      "we enter when, within 26 bars after a twist, price closes on the twist's side of the current cloud with Tenkan > Kijun.")
    description_fa = ("چرخش (کراس اسپن A و B در ابر آینده) تنها سیگنال پیش‌نگر ایچیموکو است. هشدار است نه ورود: وقتی ظرف ۲۶ کندل بعد از چرخش، قیمت در سمت چرخش نسبت به ابر فعلی بسته شود و تنکان > کیجون باشد وارد می‌شویم.")
    rules_en = ["Bullish twist in future cloud in the last 26 bars", "Confirmation: close > cloud top & Tenkan > Kijun (first bar it holds)", "Stop under Kijun; 2R", "Short mirror"]
    rules_fa = ["چرخش صعودی در ابر آینده طی ۲۶ کندل اخیر", "تأیید: close > سقف ابر و تنکان > کیجون (اولین کندل)", "استاپ زیر کیجون؛ 2R", "فروش برعکس"]
    pros_en = ["Early regime-change detection"]; cons_en = ["Many twists in ranges"]
    pros_fa = ["تشخیص زودهنگام تغییر رژیم"]; cons_fa = ["چرخش‌های زیاد در رنج"]

    def run(self, df):
        ic = self.ic(df); k = self.p["kijun"]
        recent_up = ic["twist_up"].rolling(k).max().fillna(0).astype(bool)
        recent_dn = ic["twist_dn"].rolling(k).max().fillna(0).astype(bool)
        bull = recent_up & ic["above"] & (ic["tenkan"] > ic["kijun"])
        bear = recent_dn & ic["below"] & (ic["tenkan"] < ic["kijun"])
        long = bull & ~bull.shift(1).fillna(False).astype(bool)
        short = bear & ~bear.shift(1).fillna(False).astype(bool)
        return _result(df, ic, self.make_signal(long, short), "kijun", 2.0)


class IchimokuChikouBreak(_Ichi):
    id = "ichimoku_chikou_break"
    name_en = "Ichimoku Chikou-span breakout (lagging line clears price)"
    name_fa = "شکست چیکو اسپن (خط تأخیری از قیمت عبور می‌کند)"
    timeframes = "1h – 1d"
    description_en = ("Chikou = today's close plotted 26 bars back. When it breaks above the candles (and cloud) of 26 bars ago, momentum has decisively shifted. "
                      "Taken only when price is not below the cloud.")
    description_fa = ("چیکو = بستهٔ امروز که ۲۶ کندل عقب رسم می‌شود. وقتی از کندل‌ها (و ابر) ۲۶ کندل قبل بالا بزند، مومنتوم قاطعانه تغییر کرده. فقط وقتی قیمت زیر ابر نباشد.")
    rules_en = ["Long: Chikou turns 'free' bullish (close > high & cloud of 26 bars ago) and price ≥ cloud bottom", "Short mirror", "ATR stop 1.5, 2R"]
    rules_fa = ["خرید: چیکو «آزاد» صعودی می‌شود (close > سقف و ابر ۲۶ کندل قبل) و قیمت ≥ کف ابر", "فروش برعکس", "استاپ ۱.۵ ATR، 2R"]
    pros_en = ["Momentum confirmation independent of TK"]; cons_en = ["Lags at reversals"]
    pros_fa = ["تأیید مومنتوم مستقل از TK"]; cons_fa = ["در برگشت‌ها تأخیر دارد"]

    def run(self, df):
        ic = self.ic(df)
        cb, cs = ic["chikou_bull"], ic["chikou_bear"]
        long = cb & ~cb.shift(1).fillna(False).astype(bool) & ~ic["below"]
        short = cs & ~cs.shift(1).fillna(False).astype(bool) & ~ic["above"]
        return _result(df, ic, self.make_signal(long, short), "atr", 2.0)


class IchimokuEdgeToEdge(_Ichi):
    id = "ichimoku_edge_to_edge"
    name_en = "Ichimoku edge-to-edge Kumo trade"
    name_fa = "معاملهٔ لبه‌به‌لبهٔ ابر ایچیموکو"
    timeframes = "1h – 1d"
    description_en = ("When a candle closes INSIDE the cloud after entering from one edge, price tends to travel to the opposite edge. "
                      "Target = far edge (must be ≥ 1.2 ATR away), stop just outside the entry edge.")
    description_fa = ("وقتی کندلی بعد از ورود از یک لبه داخل ابر بسته می‌شود، قیمت معمولاً تا لبهٔ مقابل می‌رود. هدف = لبهٔ دور (باید ≥ ۱.۲ ATR فاصله داشته باشد)، استاپ کمی بیرون لبهٔ ورود.")
    rules_en = ["Long: close enters the cloud from below (prev close < bottom, now inside), far edge ≥ 1.2 ATR above", "Short mirror", "Target = opposite edge"]
    rules_fa = ["خرید: close از پایین وارد ابر شود (قبلی < کف، حالا داخل)، لبهٔ دور ≥ ۱.۲ ATR بالاتر", "فروش برعکس", "هدف = لبهٔ مقابل"]
    pros_en = ["Built-in target", "Works in transitions"]; cons_en = ["Thin clouds → skip"]
    pros_fa = ["هدف داخلی", "در گذارها کار می‌کند"]; cons_fa = ["ابر نازک → رد"]

    def run(self, df):
        ic = self.ic(df); a = ic["atr"]; top, bot = ic["cloud_top"], ic["cloud_bot"]
        long = ic["inside"] & (df.close.shift(1) < bot.shift(1)) & ((top - df.close) >= 1.2 * a)
        short = ic["inside"] & (df.close.shift(1) > top.shift(1)) & ((df.close - bot) >= 1.2 * a)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = bot[sig == 1] - 0.3 * a[sig == 1]; tgt[sig == 1] = top[sig == 1]
        stop[sig == -1] = top[sig == -1] + 0.3 * a[sig == -1]; tgt[sig == -1] = bot[sig == -1]
        r = _result(df, ic, sig); r.stop, r.target = stop, tgt
        return r


class IchimokuFlatKumo(_Ichi):
    id = "ichimoku_flat_kumo"
    name_en = "Ichimoku flat Span-B / Kijun magnet"
    name_fa = "آهن‌ربای اسپن-B / کیجون صاف"
    timeframes = "1h – 1d"
    description_en = ("A flat Senkou B (or Kijun) marks the exact 50 % of a long range: price is attracted to it and often reverses there. "
                      "Fade the approach: when price touches a flat Span B from above in an uptrend (above cloud earlier) and closes back up → long; mirror for shorts. "
                      "Also used as price TARGET when price moves toward a flat span.")
    description_fa = ("اسپن B (یا کیجون) صاف دقیقاً ۵۰٪ یک رنج بلند است: قیمت به آن جذب می‌شود و اغلب همان‌جا برمی‌گردد. برخورد به اسپن B صاف از بالا و بسته‌شدن دوباره بالای آن → خرید؛ برعکس برای فروش. همچنین به‌عنوان هدف قیمتی وقتی قیمت به سمت اسپن صاف می‌رود.")
    rules_en = ["Span B flat ≥ 5 bars", "Low touches Span B, close > Span B, and close was above cloud within last 10 bars", "Stop under Span B − 0.5 ATR, 2R", "Short mirror"]
    rules_fa = ["اسپن B حداقل ۵ کندل صاف", "کف اسپن B را لمس کند، close > اسپن B، و طی ۱۰ کندل اخیر بالای ابر بوده", "استاپ زیر اسپن B − ۰.۵ ATR، 2R", "فروش برعکس"]
    pros_en = ["Precise levels", "Explains 'why price stopped here'"]; cons_en = ["Rare"]
    pros_fa = ["سطوح دقیق", "توضیح «چرا قیمت اینجا ایستاد»"]; cons_fa = ["کم‌تعداد"]

    def run(self, df):
        ic = self.ic(df); a = ic["atr"]; sb = ic["span_b"]
        flat = (sb.diff().abs() < 1e-12).rolling(5).sum() >= 5
        was_above = ic["above"].rolling(10).max().fillna(0).astype(bool)
        was_below = ic["below"].rolling(10).max().fillna(0).astype(bool)
        long = flat & (df.low <= sb) & (df.close > sb) & was_above
        short = flat & (df.high >= sb) & (df.close < sb) & was_below
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = sb[sig == 1] - 0.5 * a[sig == 1]; stop[sig == -1] = sb[sig == -1] + 0.5 * a[sig == -1]
        risk = (df.close - stop).abs(); tgt[sig == 1] = df.close[sig == 1] + 2 * risk[sig == 1]; tgt[sig == -1] = df.close[sig == -1] - 2 * risk[sig == -1]
        r = _result(df, ic, sig); r.stop, r.target = stop, tgt
        return r


class IchimokuCrypto(_Ichi):
    id = "ichimoku_crypto_20_60_120"
    name_en = "Ichimoku crypto settings 20/60/120 (24/7 markets) — perfect order"
    name_fa = "ایچیموکو تنظیمات کریپتو ۲۰/۶۰/۱۲۰ (بازار ۲۴/۷) — ترتیب کامل"
    timeframes = "1h – 1d"
    params = {"tenkan": 20, "kijun": 60, "senkou": 120}
    description_en = ("Because crypto never closes, practitioners scale 9/26/52 (6-day week) to 10/30/60 or the doubled 20/60/120 for smoother, "
                      "less noisy clouds. Same 'perfect order' logic as ichimoku_perfect; compare the two on the same chart to see which the symbol respects.")
    description_fa = ("چون کریپتو تعطیل نمی‌شود، ۹/۲۶/۵۲ (هفتهٔ ۶ روزه) به ۱۰/۳۰/۶۰ یا ۲۰/۶۰/۱۲۰ مقیاس می‌شود تا ابر نرم‌تر و کم‌نویزتر باشد. همان منطق «ترتیب کامل»؛ هر دو را روی یک چارت مقایسه کنید.")
    rules_en = IchimokuPerfect.rules_en; rules_fa = IchimokuPerfect.rules_fa
    pros_en = ["Fewer false signals on volatile coins"]; cons_en = ["Slower"]
    pros_fa = ["سیگنال کاذب کمتر روی کوین‌های پرنوسان"]; cons_fa = ["کندتر"]
    run = IchimokuPerfect.run


class IchimokuMTF(_Ichi):
    id = "ichimoku_mtf"
    name_en = "Ichimoku multi-timeframe (HTF cloud bias + LTF TK/Kijun entry)"
    name_fa = "ایچیموکو چندتایم‌فریمی (جهت ابر تایم بالا + ورود TK/کیجون تایم پایین)"
    timeframes = "5m – 4h"
    description_en = ("Bias from the cloud of a timeframe ×4 higher (price above HTF cloud & HTF Tenkan>Kijun) and entries on this timeframe: "
                      "TK cross above cloud OR Kijun bounce. This is how most professional Ichimoku traders actually trade.")
    description_fa = ("جهت از ابر تایم‌فریم ۴ برابر بالاتر (قیمت بالای ابر HTF و تنکان>کیجون HTF) و ورود در همین تایم‌فریم: کراس TK بالای ابر یا برگشت کیجون. روش واقعی اکثر معامله‌گران حرفه‌ای ایچیموکو.")
    rules_en = ["HTF (×4) close above HTF cloud and HTF Tenkan > Kijun", "LTF: TK cross up above cloud, or Kijun bounce", "Stop under LTF Kijun; 2R", "Short mirror"]
    rules_fa = ["HTF (×۴): close بالای ابر HTF و تنکان > کیجون HTF", "LTF: کراس TK بالای ابر، یا برگشت کیجون", "استاپ زیر کیجون LTF؛ 2R", "فروش برعکس"]
    pros_en = ["Trades with the bigger tide"]; cons_en = ["Needs enough history for HTF"]
    pros_fa = ["هم‌جهت با موج بزرگ"]; cons_fa = ["به تاریخچهٔ کافی برای HTF نیاز دارد"]
    params = {"tenkan": 9, "kijun": 26, "senkou": 52, "htf_factor": 4}

    def run(self, df):
        ic = self.ic(df); f = int(self.p["htf_factor"])
        # HTF via bar aggregation (works for any index spacing)
        g = np.arange(len(df)) // f
        h = pd.DataFrame({"open": df.open.groupby(g).first(), "high": df.high.groupby(g).max(), "low": df.low.groupby(g).min(), "close": df.close.groupby(g).last()})
        hic = ichimoku_full(h, self.p["tenkan"], self.p["kijun"], self.p["senkou"])
        # only completed HTF bars are known → shift by one HTF bar, then broadcast
        hb = (hic["above"] & (hic["tenkan"] > hic["kijun"])).shift(1).fillna(False).astype(bool).values[g]
        hs = (hic["below"] & (hic["tenkan"] < hic["kijun"])).shift(1).fillna(False).astype(bool).values[g]
        hb = pd.Series(hb, index=df.index); hs = pd.Series(hs, index=df.index)
        k = ic["kijun"]
        tk_up = self.cross_up(ic["tenkan"], k) & ic["above"]
        tk_dn = self.cross_down(ic["tenkan"], k) & ic["below"]
        kb_up = ic["above"] & (df.low <= k) & (df.close > k) & (df.low.shift(1) > k.shift(1))
        kb_dn = ic["below"] & (df.high >= k) & (df.close < k) & (df.high.shift(1) < k.shift(1))
        long = hb & (tk_up | kb_up); short = hs & (tk_dn | kb_dn)
        return _result(df, ic, self.make_signal(long, short), "kijun", 2.0)


class IchimokuWaveTargets(_Ichi):
    id = "ichimoku_wave_targets"
    name_en = "Ichimoku N-wave price theory (N/V/E/NT targets + kihon-suchi timing)"
    name_fa = "نظریهٔ قیمت موج N ایچیموکو (اهداف N/V/E/NT + زمان‌بندی اعداد پایه)"
    timeframes = "1h – 1d"
    description_en = ("Hosoda's price theory: on the last A→B→C wave the targets are N = C+(B−A), V = B+(B−C), E = B+(B−A), NT = C+(C−A). "
                      "Entry = continuation trigger after C (close above the B-leg 50 % with Tenkan > Kijun, bullish case), target = N value, stop under C. "
                      "Kihon-suchi (9, 17, 26, 33, 42, 51, 65, 76…) counted from C mark the next 'henka-bi' (change days) — shown as levels/notes.")
    description_fa = ("نظریهٔ قیمت هوسودا: روی آخرین موج A→B→C اهداف N = C+(B−A)، V = B+(B−C)، E = B+(B−A)، NT = C+(C−A). "
                      "ورود = تریگر ادامه بعد از C (بسته‌شدن بالای ۵۰٪ پای B با تنکان > کیجون در حالت صعودی)، هدف = مقدار N، استاپ زیر C. "
                      "اعداد پایه (۹، ۱۷، ۲۶، ۳۳، ۴۲، ۵۱، ۶۵، ۷۶…) از C روزهای تغییر بعدی (هنکابی) را می‌دهند.")
    rules_en = ["Identify A,B,C swings (5/5 pivots)", "Long: bullish N wave, close > (B+C)/2 & Tenkan > Kijun, first bar", "Target N, stop under C − 0.3 ATR", "Short mirror"]
    rules_fa = ["سوئینگ‌های A,B,C (پیوت ۵/۵)", "خرید: موج N صعودی، close > (B+C)/2 و تنکان > کیجون، اولین کندل", "هدف N، استاپ زیر C − ۰.۳ ATR", "فروش برعکس"]
    pros_en = ["Objective targets", "Timing windows"]; cons_en = ["Pivot detection lags 5 bars"]
    pros_fa = ["اهداف عینی", "پنجره‌های زمانی"]; cons_fa = ["تشخیص پیوت ۵ کندل تأخیر دارد"]

    def run(self, df):
        ic = self.ic(df); a = ic["atr"]
        sh, sl = ta.swing_points(df, 5, 5)
        hi_idx, lo_idx = np.where(sh.values)[0], np.where(sl.values)[0]
        n = len(df)
        A = np.full(n, np.nan); B = np.full(n, np.nan); Cc = np.full(n, np.nan); up = np.zeros(n, bool)
        pts = sorted([(int(i) + 5, float(df.high.iloc[i]), 1) for i in hi_idx] + [(int(i) + 5, float(df.low.iloc[i]), 0) for i in lo_idx])   # known 5 bars after pivot
        clean = []
        for p in pts:
            if clean and clean[-1][2] == p[2]:
                if (p[2] == 1 and p[1] > clean[-1][1]) or (p[2] == 0 and p[1] < clean[-1][1]):
                    clean[-1] = p
            else:
                clean.append(p)
        for j in range(2, len(clean)):
            i0 = clean[j][0]; i1 = clean[j + 1][0] if j + 1 < len(clean) else n
            if i0 >= n:
                break
            A[i0:i1], B[i0:i1], Cc[i0:i1] = clean[j - 2][1], clean[j - 1][1], clean[j][1]
            up[i0:i1] = clean[j - 2][2] == 0
        A, B, Cc, up = (pd.Series(x, index=df.index) for x in (A, B, Cc, up))
        mid = (B + Cc) / 2
        bull = up & (df.close > mid) & (ic["tenkan"] > ic["kijun"]) & (df.close > Cc)
        bear = ~up & (df.close < mid) & (ic["tenkan"] < ic["kijun"]) & (df.close < Cc) & B.notna()
        long = bull & ~bull.shift(1).fillna(False).astype(bool)
        short = bear & ~bear.shift(1).fillna(False).astype(bool)
        sig = self.make_signal(long, short)
        stop = pd.Series(np.nan, index=df.index); tgt = pd.Series(np.nan, index=df.index)
        stop[sig == 1] = Cc[sig == 1] - 0.3 * a[sig == 1]; tgt[sig == 1] = Cc[sig == 1] + (B - A).abs()[sig == 1]
        stop[sig == -1] = Cc[sig == -1] + 0.3 * a[sig == -1]; tgt[sig == -1] = Cc[sig == -1] - (B - A).abs()[sig == -1]
        levels = []
        wt = wave_targets(df)
        if wt:
            for nm, v in wt["targets"].items():
                levels.append((float(v), f"{nm} target", "#f5c542"))
        r = _result(df, ic, sig, levels=levels); r.stop, r.target = stop, tgt
        return r


ICHIMOKU_STRATEGIES = [IchimokuPerfect, IchimokuTKGraded, IchimokuKumoBreakout, IchimokuKijunBounce, IchimokuKumoTwist,
                       IchimokuChikouBreak, IchimokuEdgeToEdge, IchimokuFlatKumo, IchimokuCrypto, IchimokuMTF, IchimokuWaveTargets]
