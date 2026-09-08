"""Phase 19 — signal methods learned from masters who teach in OTHER languages, translated and made testable.

  • 缠论 Chan Lun (缠中说禅, Chinese): 中枢 (pivot zone) + 三类买卖点 (1st/2nd/3rd class buy/sell points) + 背驰 (divergence).
  • 酒田五法 Sakata Goho (本間宗久, Japanese): 三山/三川/三空/三兵/三法.
  • Александр Герчик (Russian): trade from strong LEVELS only; ложный пробой (false breakout) with ≥2 touches, tight stop
    ≤30 % of daily ATR, entry by limit at the level, target ≥3R; "паранормальный бар" (paranormal bar) rejection.
  • Stormer / Larry Williams setups (Portuguese, Brazil): 9.1 (EMA-9 turn), 9.2 (pullback candle), 9.3 (three-bar), Stormer's 8.1.
  • CPR (Central Pivot Range, India — Frank Ochoa via Indian traders): narrow-CPR trend day, virgin CPR magnet.
  • RTM / QM / FTR (Persian price-action school — "Read The Market"): Quasimodo, Flag-limit, Caps, Compression, FTR.
  • Dow / Wyckoff phase reading (Spanish school "método Wyckoff" — Rubén Villahermosa): Spring / Upthrust with test.

All rules were read in the source language, translated FA/EN and turned into deterministic OHLCV code. The measured success
rate (core/success.py) is shown next to each of them like every other signal — no promises, only numbers.
"""
import numpy as np
import pandas as pd
from .base import Strategy, StrategyResult
from core import indicators as ta
from core import indicators2 as t2


class _WM(Strategy):
    category = "World Masters"
    difficulty = 3
    timeframes = "15m – 1d"
    sl_mult, tp_mult = 1.5, 3.0

    def finish(self, df, long, short, overlays=None, panels=None, levels=None, stop=None, tgt=None, sl=None, tp=None):
        sig = self.make_signal(long, short)
        a = ta.atr(df)
        s2, t2_ = self.atr_stops(df, sig, a, sl or self.sl_mult, tp or self.tp_mult)
        if stop is not None:
            s2 = s2.where(stop.isna() | (sig == 0), stop)
        if tgt is not None:
            t2_ = t2_.where(tgt.isna() | (sig == 0), tgt)
        return StrategyResult(sig, s2, t2_, overlays=overlays or {}, panels=panels or {}, levels=levels or [])


# ---------------------------------------------------------------------------------------------- 缠论 Chan Lun
def _chan_segments(df, pct=2.5):
    """ZigZag strokes (笔) → list of (i0, i1, p0, p1). Uses % ZigZag as a practical stroke proxy; the % adapts to the
    timeframe's volatility (≈4× median ATR%) so a 'stroke' means the same thing on 5m and 1d."""
    try:
        atrp = float((ta.atr(df) / df.close).median()) * 100
        pct = float(np.clip(max(pct * 0.4, atrp * 4), 0.6, 8.0))
    except Exception:
        pass
    zz = t2.zigzag(df, pct)
    df.attrs["_chan_pct"] = pct
    piv = zz.dropna()
    pos = {ts: i for i, ts in enumerate(df.index)}
    pts = [(pos[ts], float(v)) for ts, v in piv.items()]
    return [(pts[k][0], pts[k + 1][0], pts[k][1], pts[k + 1][1]) for k in range(len(pts) - 1)]


def _confirm_bar(df, i, is_low, pct):
    """First bar after pivot i where the ZigZag reversal (pct %) is complete — the earliest moment the pivot is KNOWN (no look-ahead)."""
    h, l = df.high.values, df.low.values; n = len(df)
    if is_low:
        lvl = l[i] * (1 + pct / 100)
        for j in range(i + 1, min(i + 400, n)):
            if l[j] < l[i]:
                return None
            if h[j] >= lvl:
                return j
    else:
        lvl = h[i] * (1 - pct / 100)
        for j in range(i + 1, min(i + 400, n)):
            if h[j] > h[i]:
                return None
            if l[j] <= lvl:
                return j
    return None


def _chan_zhongshu(segs):
    """中枢 = overlap of three consecutive strokes: ZG = min(high of 3), ZD = max(low of 3). Returns list of (start_i, end_i, ZD, ZG)."""
    out = []
    for k in range(len(segs) - 2):
        a, b, c = segs[k], segs[k + 1], segs[k + 2]
        hi = min(max(a[2], a[3]), max(b[2], b[3]), max(c[2], c[3]))
        lo = max(min(a[2], a[3]), min(b[2], b[3]), min(c[2], c[3]))
        if hi > lo:
            out.append((a[0], c[1], lo, hi))
    return out


class ChanFirstBuy(_WM):
    id = "chan_buy1"; name_en = "Chan Lun 1st-class buy/sell point (背驰)"; name_fa = "چان‌لون: نقطهٔ خرید/فروش نوع اول (واگرایی 背驰)"
    author = "缠中说禅 (Chan Zhong Shuo Chan)"; params = {"zz_pct": 2.5}; difficulty = 4
    description_en = ("Chinese 'Chan theory': after a trend leaves its last pivot zone (中枢), the final stroke shows 背驰 — smaller MACD area/"
                      "momentum than the previous same-direction stroke. That exhaustion point is the 1st-class buy (下跌背驰) or sell (上涨背驰).")
    description_fa = ("نظریهٔ چینی «چان‌لون»: پس از خروج روند از آخرین ناحیهٔ محوری (中枢)، آخرین قلم حرکت 背驰 نشان می‌دهد — مساحت MACD/مومنتوم کمتر از "
                      "قلم هم‌جهت قبلی. آن نقطهٔ خستگی، خرید نوع اول (در ریزش) یا فروش نوع اول (در صعود) است.")
    rules_en = ["Build strokes (ZigZag), pivot zones = overlap of 3 strokes", "Price breaks below the last zone (ZD) with a new low",
                "MACD histogram area of this leg < 70 % of the previous down leg → 背驰", "Enter on close back above the low-bar high; stop under the low; target = zone ZG"]
    rules_fa = ["قلم‌ها (زیگزاگ) و ناحیهٔ محوری = هم‌پوشانی ۳ قلم", "قیمت زیر ZD آخرین ناحیه با کف جدید می‌شکند",
                "مساحت هیستوگرام MACD این پا < ۷۰٪ پای نزولی قبلی → 背驰", "ورود با بسته‌شدن بالای سقف کندلِ کف؛ استاپ زیر کف؛ هدف ZG ناحیه"]
    pros_en = ["Objective exhaustion definition", "Targets come from structure"]; pros_fa = ["تعریف عینی خستگی", "هدف از ساختار می‌آید"]
    cons_en = ["Stroke definition is a proxy (true 笔 needs inclusion handling)", "Counter-trend"]; cons_fa = ["تعریف قلم تقریبی است", "خلاف روند"]

    def run(self, df):
        n = len(df); long = pd.Series(False, index=df.index); short = long.copy()
        stop = pd.Series(np.nan, index=df.index); tgt = stop.copy()
        _, hist = ta.macd(df.close)[0], ta.macd(df.close)[2]
        h = hist.values
        segs = _chan_segments(df, self.p["zz_pct"]); zs = _chan_zhongshu(segs)
        if len(segs) < 4:
            return self.finish(df, long, short)
        for k in range(2, len(segs)):
            s = segs[k]; prev = segs[k - 2]
            down = s[3] < s[2]
            zone = [z for z in zs if z[1] <= s[0]]
            if not zone:
                continue
            zd, zg = zone[-1][2], zone[-1][3]
            area = abs(h[s[0]:s[1] + 1].sum()); parea = abs(h[prev[0]:prev[1] + 1].sum()) or 1e-9
            i = s[1]
            if i + 1 >= n:
                continue
            pct = df.attrs.get("_chan_pct", self.p["zz_pct"])
            if down and s[3] < zd and prev[3] < prev[2] and area < 0.7 * parea:
                j = _confirm_bar(df, i, True, pct)
                if j is not None and zg > df.close.iloc[j] * 1.002:
                    long.iloc[j] = True; stop.iloc[j] = df.low.iloc[i]; tgt.iloc[j] = zg
            if (not down) and s[3] > zg and prev[3] > prev[2] and area < 0.7 * parea:
                j = _confirm_bar(df, i, False, pct)
                if j is not None and zd < df.close.iloc[j] * 0.998:
                    short.iloc[j] = True; stop.iloc[j] = df.high.iloc[i]; tgt.iloc[j] = zd
        levels = [(z[3], "ZG") for z in zs[-2:]] + [(z[2], "ZD") for z in zs[-2:]]
        return self.finish(df, long, short, panels={"MACD hist": hist}, levels=levels, stop=stop, tgt=tgt)


class ChanThirdBuy(_WM):
    id = "chan_buy3"; name_en = "Chan Lun 3rd-class buy/sell (中枢 breakout + retest)"; name_fa = "چان‌لون: خرید/فروش نوع سوم (شکست ناحیهٔ محوری + پولبک)"
    author = "缠中说禅"; params = {"zz_pct": 2.5}; difficulty = 3
    description_en = ("A stroke leaves the pivot zone upward, the next pullback stroke holds ABOVE the zone top (ZG) → 3rd-class buy: the zone is finished "
                      "and the trend continues to build the next zone. Mirror for sells below ZD.")
    description_fa = ("یک قلم از ناحیهٔ محوری به بالا خارج می‌شود و قلم پولبک بعدی بالای سقف ناحیه (ZG) می‌ماند → خرید نوع سوم: ناحیه تمام شده و روند برای "
                      "ساخت ناحیهٔ بعدی ادامه می‌یابد. برای فروش زیر ZD برعکس.")
    rules_en = ["Zone = overlap of 3 strokes (ZD..ZG)", "Up-stroke closes above ZG", "Pullback stroke low > ZG", "Enter when price exceeds the pullback bar high; stop = ZG − 0.3 ATR; target = ZG + (ZG − ZD)"]
    rules_fa = ["ناحیه = هم‌پوشانی ۳ قلم (ZD تا ZG)", "قلم صعودی بالای ZG بسته می‌شود", "کف قلم پولبک > ZG", "ورود با عبور از سقف کندل پولبک؛ استاپ ZG − 0.3ATR؛ هدف ZG + عرض ناحیه"]
    pros_en = ["Trend-following; the cleanest Chan entry"]; pros_fa = ["هم‌جهت روند؛ تمیزترین ورود چان"]
    cons_en = ["Needs a clear zone; noisy in chop"]; cons_fa = ["نیاز به ناحیهٔ واضح؛ در رنج نویزی"]

    def run(self, df):
        n = len(df); long = pd.Series(False, index=df.index); short = long.copy()
        stop = pd.Series(np.nan, index=df.index); tgt = stop.copy(); a = ta.atr(df)
        segs = _chan_segments(df, self.p["zz_pct"]); zs = _chan_zhongshu(segs)
        h, l, c = df.high.values, df.low.values, df.close.values
        pct = df.attrs.get("_chan_pct", self.p["zz_pct"])
        for z in zs:
            zi = z[1]
            after = [s_ for s_ in segs if s_[0] >= zi][:1]
            if not after:
                continue
            out = after[0]; w = z[3] - z[2]
            if out[3] > out[2] and out[3] > z[3]:
                j0 = _confirm_bar(df, out[1], False, pct)          # pullback under way, known here
                if j0 is None:
                    continue
                for j in range(j0 + 1, min(j0 + 40, n)):
                    if l[j] < z[3]:
                        break                                       # fell back into the zone → not a 3rd buy
                    if c[j] > h[j - 3:j].max() and c[j] > c[j - 1] and z[3] + w > c[j] * 1.002:
                        long.iloc[j] = True; stop.iloc[j] = min(z[3], l[j0:j + 1].min()) - 0.3 * a.iloc[j]; tgt.iloc[j] = z[3] + w; break
            if out[3] < out[2] and out[3] < z[2]:
                j0 = _confirm_bar(df, out[1], True, pct)
                if j0 is None:
                    continue
                for j in range(j0 + 1, min(j0 + 40, n)):
                    if h[j] > z[2]:
                        break
                    if c[j] < l[j - 3:j].min() and c[j] < c[j - 1] and z[2] - w < c[j] * 0.998:
                        short.iloc[j] = True; stop.iloc[j] = max(z[2], h[j0:j + 1].max()) + 0.3 * a.iloc[j]; tgt.iloc[j] = z[2] - w; break
        levels = [(z[3], "ZG") for z in zs[-2:]] + [(z[2], "ZD") for z in zs[-2:]]
        return self.finish(df, long, short, levels=levels, stop=stop, tgt=tgt)


# ---------------------------------------------------------------------------------------------- 酒田五法 Sakata
class SakataSanpei(_WM):
    id = "sakata_sanpei"; name_en = "Sakata 三兵 three soldiers / crows (with 三法 filter)"; name_fa = "ساکاتا 三兵 سه سرباز/سه کلاغ (با فیلتر 三法)"
    author = "本間宗久 Honma Munehisa"; params = {"trend": 50}
    description_en = ("Edo-period rice-trader rules: 赤三兵 (three white soldiers) after a base = continuation up; 黒三兵 (three black crows) after a top = down. "
                      "Bodies must be progressive, closes near extremes, no long upper wicks (避ける: 先詰まり).")
    description_fa = ("قوانین معامله‌گر برنج دورهٔ ادو: 赤三兵 سه سرباز سفید پس از کف = ادامهٔ صعود؛ 黒三兵 سه کلاغ سیاه پس از سقف = نزول. بدنه‌ها پیش‌رونده، "
                      "بسته‌شدن نزدیک انتها، بدون سایهٔ بلند (先詰まり ممنوع).")
    rules_en = ["3 consecutive bullish bodies, each close > previous close and open inside previous body", "Upper wick < 30 % of body on all three",
                "Occurs after price was below SMA50 for ≥5 bars (base) — otherwise it is exhaustion", "Stop under the first soldier; target 2R"]
    rules_fa = ["۳ بدنهٔ صعودی پیاپی، هر بسته‌شدن بالاتر و باز شدن داخل بدنهٔ قبلی", "سایهٔ بالایی < ۳۰٪ بدنه در هر سه",
                "پس از ≥۵ کندل زیر SMA50 (کف) — وگرنه خستگی است", "استاپ زیر سرباز اول؛ هدف 2R"]
    pros_en = ["Oldest documented candle system"]; pros_fa = ["قدیمی‌ترین سیستم مستند کندلی"]
    cons_en = ["Late entry after 3 bars"]; cons_fa = ["ورود دیرهنگام پس از ۳ کندل"]

    def run(self, df):
        o, h, l, c = df.open, df.high, df.low, df.close
        body = (c - o).abs(); up = c > o; dn = c < o
        uw = h - np.maximum(o, c); lw = np.minimum(o, c) - l
        s = ta.sma(c, self.p["trend"])
        below = (c < s).rolling(8).sum().shift(3) >= 4
        above = (c > s).rolling(8).sum().shift(3) >= 4
        sold = up & up.shift(1) & up.shift(2) & (c > c.shift(1)) & (c.shift(1) > c.shift(2)) & (o > o.shift(1)) & (o < c.shift(1)) & (o.shift(1) < c.shift(2)) \
            & (uw < 0.5 * body) & (uw.shift(1) < 0.5 * body.shift(1)) & (uw.shift(2) < 0.5 * body.shift(2)) & (body > 0.25 * ta.atr(df))
        crow = dn & dn.shift(1) & dn.shift(2) & (c < c.shift(1)) & (c.shift(1) < c.shift(2)) & (o < o.shift(1)) & (o > c.shift(1)) & (o.shift(1) > c.shift(2)) \
            & (lw < 0.5 * body) & (lw.shift(1) < 0.5 * body.shift(1)) & (lw.shift(2) < 0.5 * body.shift(2)) & (body > 0.25 * ta.atr(df))
        long = sold & below.fillna(False); short = crow & above.fillna(False)
        stop = pd.Series(np.nan, index=df.index); stop[long] = l.shift(2)[long]; stop[short] = h.shift(2)[short]
        tgt = pd.Series(np.nan, index=df.index); tgt[long] = (c + 2 * (c - stop))[long]; tgt[short] = (c - 2 * (stop - c))[short]
        return self.finish(df, long, short, {"SMA50": s}, stop=stop, tgt=tgt)


class SakataSanku(_WM):
    id = "sakata_sanku"; name_en = "Sakata 三空 three gaps exhaustion"; name_fa = "ساکاتا 三空 سه گپ خستگی"
    author = "本間宗久"; params = {}; timeframes = "1d"
    description_en = ("三空踏み上げ: three consecutive up-gaps = over-heated, fade on the first bearish close; 三空叩き込み: three down-gaps at a bottom = buy the first bullish close. "
                      "Works on daily bars of gapping markets (stocks, indices); crypto rarely gaps.")
    description_fa = ("三空踏み上げ: سه گپ صعودی پیاپی = داغ‌شدگی، با اولین کندل نزولی معکوس بگیر؛ 三空叩き込み: سه گپ نزولی در کف = با اولین بسته‌شدن صعودی بخر. "
                      "برای کندل روزانهٔ بازارهای گپ‌دار (سهام/شاخص)؛ کریپتو کمتر گپ دارد.")
    rules_en = ["3 consecutive bars each opening beyond the previous high (or low)", "Entry: first opposite close after the 3rd gap", "Stop beyond the extreme; target = 2nd gap fill"]
    rules_fa = ["۳ کندل پیاپی که هر یک فراتر از سقف (یا کف) قبلی باز می‌شود", "ورود: اولین بسته‌شدن مخالف پس از گپ سوم", "استاپ فراتر از اکسترمم؛ هدف پرشدن گپ دوم"]
    pros_en = ["Very selective"]; pros_fa = ["بسیار گزینشی"]; cons_en = ["Rare in 24/7 markets"]; cons_fa = ["در بازار ۲۴/۷ نادر"]

    def run(self, df):
        o, h, l, c = df.open, df.high, df.low, df.close
        gu = o > h.shift(1); gd = o < l.shift(1)
        three_up = gu.shift(1) & gu.shift(2) & gu.shift(3); three_dn = gd.shift(1) & gd.shift(2) & gd.shift(3)
        short = three_up.fillna(False) & (c < o); long = three_dn.fillna(False) & (c > o)
        stop = pd.Series(np.nan, index=df.index); stop[short] = h.rolling(4).max()[short]; stop[long] = l.rolling(4).min()[long]
        tgt = pd.Series(np.nan, index=df.index); tgt[short] = h.shift(3)[short]; tgt[long] = l.shift(3)[long]
        return self.finish(df, long, short, stop=stop, tgt=tgt)


class SakataSanpo(_WM):
    id = "sakata_sanpo"; name_en = "Sakata 三法 rising/falling three methods"; name_fa = "ساکاتا 三法 سه‌روش صعودی/نزولی"
    author = "本間宗久"; params = {"trend": 50}
    description_en = "A big candle, then 2–4 small counter candles held inside its range, then a close beyond the big candle's extreme → trend resumes (休むも相場 'rest is also trading')."
    description_fa = "یک کندل بزرگ، سپس ۲ تا ۴ کندل کوچک مخالف داخل محدودهٔ آن، سپس بسته‌شدن فراتر از اکسترمم کندل بزرگ → ادامهٔ روند (休むも相場 «استراحت هم معامله است»)."
    rules_en = ["Big bar body ≥ 1.2 ATR in trend direction (close vs SMA50)", "Next 2–4 bars stay inside the big bar's high/low", "Breakout close beyond the big bar's extreme", "Stop = big bar midpoint; target = 1.5× big bar range"]
    rules_fa = ["بدنهٔ کندل بزرگ ≥ ۱.۲ATR هم‌جهت روند (نسبت به SMA50)", "۲ تا ۴ کندل بعدی داخل سقف/کف کندل بزرگ", "بسته‌شدن فراتر از اکسترمم کندل بزرگ", "استاپ وسط کندل بزرگ؛ هدف ۱.۵ برابر رنج آن"]
    pros_en = ["Continuation with defined risk"]; pros_fa = ["ادامه‌دهنده با ریسک مشخص"]; cons_en = ["Fails on range days"]; cons_fa = ["در روزهای رنج شکست می‌خورد"]

    def run(self, df):
        o, h, l, c = df.open, df.high, df.low, df.close; a = ta.atr(df); s = ta.sma(c, self.p["trend"])
        long = pd.Series(False, index=df.index); short = long.copy(); stop = pd.Series(np.nan, index=df.index); tgt = stop.copy()
        big_up = ((c - o) >= 1.2 * a) & (c > s); big_dn = ((o - c) >= 1.2 * a) & (c < s)
        for k in range(2, 5):
            inside = pd.Series(True, index=df.index)
            for j in range(1, k + 1):
                inside &= (h.shift(j) <= h.shift(k + 1)) & (l.shift(j) >= l.shift(k + 1))
            lu = big_up.shift(k + 1).fillna(False) & inside & (c > h.shift(k + 1))
            sd = big_dn.shift(k + 1).fillna(False) & inside & (c < l.shift(k + 1))
            long |= lu; short |= sd
            mid = (h.shift(k + 1) + l.shift(k + 1)) / 2; rng = h.shift(k + 1) - l.shift(k + 1)
            stop[lu] = mid[lu]; tgt[lu] = (c + 1.5 * rng)[lu]; stop[sd] = mid[sd]; tgt[sd] = (c - 1.5 * rng)[sd]
        return self.finish(df, long, short, {"SMA50": s}, stop=stop, tgt=tgt)


class SakataSanzan(_WM):
    id = "sakata_sanzan"; name_en = "Sakata 三山/三川 three mountains & rivers (triple top/bottom)"; name_fa = "ساکاتا 三山/三川 سه‌کوه و سه‌رود (سقف/کف سه‌قلو)"
    author = "本間宗久"; params = {"left": 5, "right": 5, "tol": 0.006}
    description_en = "Three swing highs within tolerance (中央 may be highest = 三尊 head & shoulders) then a close under the neckline = sell; mirror 三川 (逆三尊) = buy."
    description_fa = "سه سقف سوئینگ در تلورانس (وسطی می‌تواند بالاتر باشد = 三尊 سر و شانه) سپس بسته‌شدن زیر خط گردن = فروش؛ برعکس 三川 (逆三尊) = خرید."
    rules_en = ["3 swing highs (fractal 5/5) within 0.6 %", "Neckline = lowest low between them", "Entry on close through neckline; stop = middle peak; target = height projected"]
    rules_fa = ["۳ سقف سوئینگ (فراکتال ۵/۵) در ۰٫۶٪", "خط گردن = پایین‌ترین کف بین آن‌ها", "ورود با بسته‌شدن از خط گردن؛ استاپ قلهٔ وسط؛ هدف = ارتفاع الگو"]
    pros_en = ["Classic reversal, measurable target"]; pros_fa = ["برگشت کلاسیک با هدف قابل اندازه‌گیری"]; cons_en = ["Rare, needs patience"]; cons_fa = ["نادر، نیاز به صبر"]

    def run(self, df):
        sh, sl_ = ta.swing_points(df, self.p["left"], self.p["right"])
        n = len(df); h, l, c = df.high.values, df.low.values, df.close.values
        long = np.zeros(n, bool); short = np.zeros(n, bool); stop = np.full(n, np.nan); tgt = np.full(n, np.nan)
        hi_idx = np.where(sh.values)[0]; lo_idx = np.where(sl_.values)[0]; tol = self.p["tol"]; r = self.p["right"]
        for k in range(2, len(hi_idx)):
            i1, i2, i3 = hi_idx[k - 2], hi_idx[k - 1], hi_idx[k]
            if i3 - i1 > 120:
                continue
            p = [h[i1], h[i2], h[i3]]
            if (max(p) - min(p)) / max(p) > tol * 3 or not (abs(p[0] - p[2]) / p[2] <= tol):
                continue
            neck = l[i1:i3 + 1].min(); height = max(p) - neck
            for j in range(i3 + r, min(i3 + r + 30, n)):
                if c[j] < neck:
                    short[j] = True; stop[j] = h[i2]; tgt[j] = neck - height; break
                if h[j] > max(p):
                    break
        for k in range(2, len(lo_idx)):
            i1, i2, i3 = lo_idx[k - 2], lo_idx[k - 1], lo_idx[k]
            if i3 - i1 > 120:
                continue
            p = [l[i1], l[i2], l[i3]]
            if (max(p) - min(p)) / max(p) > tol * 3 or not (abs(p[0] - p[2]) / p[2] <= tol):
                continue
            neck = h[i1:i3 + 1].max(); height = neck - min(p)
            for j in range(i3 + r, min(i3 + r + 30, n)):
                if c[j] > neck:
                    long[j] = True; stop[j] = l[i2]; tgt[j] = neck + height; break
                if l[j] < min(p):
                    break
        idx = df.index
        return self.finish(df, pd.Series(long, idx), pd.Series(short, idx), stop=pd.Series(stop, idx), tgt=pd.Series(tgt, idx))


# ---------------------------------------------------------------------------------------------- Герчик (Russian)
def _strong_levels(df, lookback=200, touches=2, tol=0.0025):
    """Gerchik 'strong level': a swing extreme touched ≥N times (within tol) in the lookback. Nearest such level above /
    below the close for every bar. Vectorised over swing points (fast on 50k bars)."""
    h, l, c = df.high.values, df.low.values, df.close.values; n = len(df)
    res = np.full(n, np.nan); sup = np.full(n, np.nan)
    sh, sl_ = ta.swing_points(df, 3, 3)
    shi = np.where(sh.values)[0]; sli = np.where(sl_.values)[0]
    hv = h[shi]; lv = l[sli]
    for i in range(50, n):
        a0, a1 = np.searchsorted(shi, i - lookback), np.searchsorted(shi, i - 3)
        if a1 - a0 >= touches:
            cand = hv[a0:a1]; up = cand[cand > c[i]]
            if len(up):
                up = np.sort(up)
                cnt = np.array([(np.abs(cand - x) <= tol * x).sum() for x in up])
                ok = up[cnt >= touches]
                if len(ok):
                    res[i] = ok[0]
        b0, b1 = np.searchsorted(sli, i - lookback), np.searchsorted(sli, i - 3)
        if b1 - b0 >= touches:
            cand = lv[b0:b1]; dn = cand[cand < c[i]]
            if len(dn):
                dn = np.sort(dn)[::-1]
                cnt = np.array([(np.abs(cand - x) <= tol * x).sum() for x in dn])
                ok = dn[cnt >= touches]
                if len(ok):
                    sup[i] = ok[0]
    return pd.Series(res, df.index), pd.Series(sup, df.index)


class GerchikFalseBreak(_WM):
    id = "gerchik_false_break"; name_en = "Gerchik: false breakout of a strong level (ложный пробой)"; name_fa = "گرچیک: شکست کاذب سطح قوی (ложный пробой)"
    author = "Александр Герчик"; params = {"touches": 2, "atr_stop_frac": 0.3}; difficulty = 3
    description_en = ("Russian school: trade only from STRONG levels (≥2 touches, 'зеркальный' mirror levels best). Simple false breakout: a bar pierces the level and closes back "
                      "inside → limit entry at the level, stop ≤30 % of the DAILY ATR behind the extreme, take ≥3R. 'No false breakout — no trade'.")
    description_fa = ("مکتب روسی: فقط از سطوح قوی (≥۲ برخورد، سطوح آینه‌ای بهترین). شکست کاذب ساده: کندل سطح را سوراخ می‌کند و داخل بسته می‌شود → ورود لیمیت روی سطح، "
                      "استاپ ≤۳۰٪ ATR روزانه پشت اکسترمم، هدف ≥3R. «بدون شکست کاذب، معامله ممنوع».")
    rules_en = ["Level = swing extreme touched ≥2× within 0.25 % in the last 200 bars", "Bar pierces the level and closes back on the original side",
                "Entry next bar at the level; stop = pierce extreme (capped at 30 % of the 24-bar ATR sum)", "Target 3R; skip if 'запас хода' (room to next level) < 3R"]
    rules_fa = ["سطح = اکسترمم سوئینگ با ≥۲ برخورد در ۰٫۲۵٪ طی ۲۰۰ کندل", "کندل سطح را سوراخ کرده و در سمت اصلی بسته می‌شود",
                "ورود کندل بعد روی سطح؛ استاپ = اکسترمم سوراخ (حداکثر ۳۰٪ ATR روزانه)", "هدف 3R؛ اگر فضای حرکت تا سطح بعدی < 3R، رد کن"]
    pros_en = ["Tiny stop → big R", "Rules are explicit"]; pros_fa = ["استاپ کوچک → R بزرگ", "قوانین صریح"]
    cons_en = ["Many small stop-outs", "Level detection sensitive to tolerance"]; cons_fa = ["استاپ‌های کوچک زیاد", "حساس به تلورانس سطح"]

    def run(self, df):
        res, sup = _strong_levels(df, touches=self.p["touches"])
        h, l, c = df.high, df.low, df.close
        a = ta.atr(df); daily_atr = a * 5
        pierce_up = (h > res) & (c < res) & (c.shift(1) < res)
        pierce_dn = (l < sup) & (c > sup) & (c.shift(1) > sup)
        short = pierce_up.shift(1).fillna(False) & (h >= res.shift(1)) & (c < res.shift(1))
        long = pierce_dn.shift(1).fillna(False) & (l <= sup.shift(1)) & (c > sup.shift(1))
        stop = pd.Series(np.nan, index=df.index); tgt = stop.copy()
        cap = self.p["atr_stop_frac"] * daily_atr
        stop[short] = np.minimum(h.shift(1), res.shift(1) + cap)[short]; tgt[short] = (res.shift(1) - 3 * (stop - res.shift(1)))[short]
        stop[long] = np.maximum(l.shift(1), sup.shift(1) - cap)[long]; tgt[long] = (sup.shift(1) + 3 * (sup.shift(1) - stop))[long]
        room_ok_l = (res - c) >= 3 * (c - stop); room_ok_s = (c - sup) >= 3 * (stop - c)
        long &= room_ok_l.fillna(True); short &= room_ok_s.fillna(True)
        return self.finish(df, long, short, {"Gerchik R": res, "Gerchik S": sup}, stop=stop, tgt=tgt)


class GerchikParanormal(_WM):
    id = "gerchik_paranormal_bar"; name_en = "Gerchik: paranormal bar rejection at level"; name_fa = "گرچیک: کندل پارانرمال و ردشدن از سطح"
    author = "Александр Герчик"; params = {"mult": 2.5}
    description_en = ("'Паранормальный бар' — a bar ≥2.5× average range slamming into a strong level and closing off its extreme. The move is exhausted; trade the reaction back "
                      "with a stop behind the bar's extreme (capped) and target the bar's midpoint then origin.")
    description_fa = ("«کندل پارانرمال» — کندلی ≥۲٫۵ برابر رنج میانگین که به سطح قوی می‌کوبد و دور از اکسترممش بسته می‌شود. حرکت خسته شده؛ واکنش برگشتی را با استاپ پشت "
                      "اکسترمم کندل معامله کن؛ هدف وسط کندل سپس مبدأ آن.")
    rules_en = ["Range ≥ 2.5× ATR", "Extreme within 0.3 % of a strong level (or beyond and rejected)", "Close in the opposite third of the bar", "Entry next open; stop beyond extreme; target bar midpoint"]
    rules_fa = ["رنج ≥ ۲٫۵ATR", "اکسترمم در ۰٫۳٪ یک سطح قوی (یا فراتر و رد شده)", "بسته‌شدن در یک‌سوم مخالف کندل", "ورود اوپن بعدی؛ استاپ فراتر از اکسترمم؛ هدف وسط کندل"]
    pros_en = ["Captures climax reversals"]; pros_fa = ["برگشت‌های کلایمکس را می‌گیرد"]; cons_en = ["Rare; wide stop"]; cons_fa = ["نادر؛ استاپ پهن"]

    def run(self, df):
        res, sup = _strong_levels(df)
        h, l, c, o = df.high, df.low, df.close, df.open; a = ta.atr(df); rng = h - l
        big = rng >= self.p["mult"] * a
        near_r = ((h - res).abs() / res <= 0.003) | ((h > res) & (c < res)); near_s = ((l - sup).abs() / sup <= 0.003) | ((l < sup) & (c > sup))
        short = big & near_r.fillna(False) & (c < l + rng / 3); long = big & near_s.fillna(False) & (c > h - rng / 3)
        stop = pd.Series(np.nan, index=df.index); tgt = stop.copy()
        stop[short] = h[short]; tgt[short] = (l + rng / 2)[short] - (h - c)[short] * 0.5
        stop[long] = l[long]; tgt[long] = (l + rng / 2)[long] + (c - l)[long] * 0.5
        # the target is at least 1.5R
        tgt[short] = np.minimum(tgt[short], c[short] - 1.5 * (h - c)[short]); tgt[long] = np.maximum(tgt[long], c[long] + 1.5 * (c - l)[long])
        return self.finish(df, long, short, {"Gerchik R": res, "Gerchik S": sup}, stop=stop, tgt=tgt)


# ---------------------------------------------------------------------------------------------- Brazil: Larry Williams 9.x / Stormer
class LW91(_WM):
    id = "lw_setup_91"; name_en = "Larry Williams 9.1 — EMA-9 turn (Brazilian school)"; name_fa = "لری ویلیامز ۹٫۱ — چرخش EMA9 (مکتب برزیل)"
    author = "Larry Williams · Alexandre Wolwacz 'Stormer'"; params = {"n": 9}
    description_en = ("Setup 9.1 as taught in Brazil: when the 9-EMA turns from falling to rising, buy the break of that candle's high; stop under its low; trail by the EMA. "
                      "Sell mirror. Setup is cancelled if the EMA turns back before trigger.")
    description_fa = ("ستاپ ۹٫۱ به روش برزیلی: وقتی EMA9 از نزولی به صعودی برمی‌گردد، شکست سقف همان کندل را بخر؛ استاپ زیر کف؛ تریل با EMA. فروش برعکس. "
                      "اگر EMA قبل از تریگر برگردد، ستاپ باطل است.")
    rules_en = ["EMA9 slope flips up (ema > ema[1] after ema[1] < ema[2])", "Buy stop 1 tick above signal-candle high (valid next 2 bars)", "Stop = signal-candle low", "Target 2R, trailing under EMA9"]
    rules_fa = ["شیب EMA9 به بالا برمی‌گردد", "بای‌استاپ یک تیک بالای سقف کندل سیگنال (۲ کندل اعتبار)", "استاپ = کف کندل سیگنال", "هدف 2R، تریل زیر EMA9"]
    pros_en = ["Very early trend entry"]; pros_fa = ["ورود بسیار زودهنگام"]; cons_en = ["Whipsaws in ranges"]; cons_fa = ["در رنج ویپ‌ساو"]

    def run(self, df):
        e = ta.ema(df.close, self.p["n"]); h, l, c = df.high, df.low, df.close
        turn_up = (e > e.shift(1)) & (e.shift(1) < e.shift(2)); turn_dn = (e < e.shift(1)) & (e.shift(1) > e.shift(2))
        long = pd.Series(False, index=df.index); short = long.copy(); stop = pd.Series(np.nan, index=df.index); tgt = stop.copy()
        for k in (1, 2):
            lu = turn_up.shift(k).fillna(False) & (h > h.shift(k)) & (e > e.shift(1))
            sd = turn_dn.shift(k).fillna(False) & (l < l.shift(k)) & (e < e.shift(1))
            lu &= ~long; sd &= ~short
            long |= lu; short |= sd
            stop[lu] = l.shift(k)[lu]; tgt[lu] = (h.shift(k) + 2 * (h.shift(k) - l.shift(k)))[lu]
            stop[sd] = h.shift(k)[sd]; tgt[sd] = (l.shift(k) - 2 * (h.shift(k) - l.shift(k)))[sd]
        return self.finish(df, long, short, {"EMA9": e}, stop=stop, tgt=tgt)


class LW92(_WM):
    id = "lw_setup_92"; name_en = "Larry Williams 9.2 — first close against EMA-9 in trend"; name_fa = "لری ویلیامز ۹٫۲ — اولین بسته‌شدن مخالف EMA9 در روند"
    author = "Larry Williams · Stormer"; params = {"n": 9, "trend": 21}
    description_en = "In an up-trend (EMA9 rising, price > EMA21) the first candle that closes below the previous close is the pullback; buy the break of its high. Mirror for shorts."
    description_fa = "در روند صعودی (EMA9 صعودی، قیمت > EMA21) اولین کندلی که زیر بسته‌شدن قبلی بسته می‌شود پولبک است؛ شکست سقف آن را بخر. برعکس برای فروش."
    rules_en = ["EMA9 rising & close > EMA21", "Candle closes below prior close (first such candle)", "Buy break of its high within 2 bars; stop its low; target 2R"]
    rules_fa = ["EMA9 صعودی و close > EMA21", "کندل زیر بسته‌شدن قبلی بسته می‌شود (اولین کندل)", "شکست سقف آن طی ۲ کندل بخر؛ استاپ کف؛ هدف 2R"]
    pros_en = ["Buys pullbacks in trend"]; pros_fa = ["خرید پولبک در روند"]; cons_en = ["Shallow pullbacks fail at exhaustion"]; cons_fa = ["پولبک‌های کم‌عمق در خستگی می‌بازند"]

    def run(self, df):
        e9 = ta.ema(df.close, self.p["n"]); e21 = ta.ema(df.close, self.p["trend"]); h, l, c = df.high, df.low, df.close
        up = (e9 > e9.shift(1)) & (c > e21); dn = (e9 < e9.shift(1)) & (c < e21)
        pb_l = up & (c < c.shift(1)) & (c.shift(1) >= c.shift(2)); pb_s = dn & (c > c.shift(1)) & (c.shift(1) <= c.shift(2))
        long = pd.Series(False, index=df.index); short = long.copy(); stop = pd.Series(np.nan, index=df.index); tgt = stop.copy()
        for k in (1, 2):
            lu = pb_l.shift(k).fillna(False) & (h > h.shift(k)) & up & ~long; sd = pb_s.shift(k).fillna(False) & (l < l.shift(k)) & dn & ~short
            long |= lu; short |= sd
            stop[lu] = l.shift(k)[lu]; tgt[lu] = (h.shift(k) + 2 * (h.shift(k) - l.shift(k)))[lu]
            stop[sd] = h.shift(k)[sd]; tgt[sd] = (l.shift(k) - 2 * (h.shift(k) - l.shift(k)))[sd]
        return self.finish(df, long, short, {"EMA9": e9, "EMA21": e21}, stop=stop, tgt=tgt)


class Stormer81(_WM):
    id = "stormer_81"; name_en = "Stormer 8.1 — 2-bar low reversal with EMA-200 filter"; name_fa = "استورمر ۸٫۱ — برگشت کف دو کندلی با فیلتر EMA200"
    author = "Alexandre 'Stormer' Wolwacz"; params = {"trend": 200}
    description_en = ("Brazilian reversal setup: the current low is below the two previous lows AND the close is above the previous close, in the direction of the 200-MA slope. "
                      "Enter above the signal candle; stop at the projection of the previous candle (less whipsaw than the low); target 2× risk.")
    description_fa = ("ستاپ برگشتی برزیلی: کف فعلی زیر دو کف قبلی و بسته‌شدن بالای بسته‌شدن قبلی، هم‌جهت با شیب MA200. ورود بالای کندل سیگنال؛ استاپ در پروجکشن کندل قبلی "
                      "(کمتر از کف ویپ می‌شود)؛ هدف ۲ برابر ریسک.")
    rules_en = ["low < low[1] and low < low[2] and close > close[1]", "MA200 rising (price above) for longs", "Entry above signal high within 2 bars", "Stop = low − (prev range); target 2R"]
    rules_fa = ["low < low[1] و low < low[2] و close > close[1]", "MA200 صعودی (قیمت بالا) برای خرید", "ورود بالای سقف سیگنال طی ۲ کندل", "استاپ = کف − رنج قبلی؛ هدف 2R"]
    pros_en = ["Simple, popular on B3 stocks"]; pros_fa = ["ساده، محبوب در بورس برزیل"]; cons_en = ["Needs trend filter"]; cons_fa = ["نیاز به فیلتر روند"]

    def run(self, df):
        m = ta.sma(df.close, self.p["trend"]); h, l, c = df.high, df.low, df.close
        up = (m > m.shift(5)) & (c > m); dn = (m < m.shift(5)) & (c < m)
        sig_l = (l < l.shift(1)) & (l < l.shift(2)) & (c > c.shift(1)) & up
        sig_s = (h > h.shift(1)) & (h > h.shift(2)) & (c < c.shift(1)) & dn
        long = pd.Series(False, index=df.index); short = long.copy(); stop = pd.Series(np.nan, index=df.index); tgt = stop.copy()
        for k in (1, 2):
            lu = sig_l.shift(k).fillna(False) & (h > h.shift(k)) & ~long; sd = sig_s.shift(k).fillna(False) & (l < l.shift(k)) & ~short
            long |= lu; short |= sd
            pr = (h.shift(k + 1) - l.shift(k + 1))
            stop[lu] = (l.shift(k) - pr)[lu]; tgt[lu] = (h.shift(k) + 2 * (h.shift(k) - stop))[lu]
            stop[sd] = (h.shift(k) + pr)[sd]; tgt[sd] = (l.shift(k) - 2 * (stop - l.shift(k)))[sd]
        return self.finish(df, long, short, {"MA200": m}, stop=stop, tgt=tgt)


# ---------------------------------------------------------------------------------------------- India: CPR
def _cpr(df):
    """Central Pivot Range from previous DAY (resampled): pivot, BC, TC, width — forward-filled onto intraday bars."""
    try:
        d = df.resample("1D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    except Exception:
        d = df[["high", "low", "close"]]
    p = (d.high + d.low + d.close) / 3; bc = (d.high + d.low) / 2; tc = 2 * p - bc
    lo, hi = np.minimum(bc, tc), np.maximum(bc, tc)
    out = pd.DataFrame({"p": p, "cpr_lo": lo, "cpr_hi": hi, "width": (hi - lo) / p, "ph": d.high, "pl": d.low}).shift(1)
    out["width_med"] = out["width"].rolling(20).median()
    return out.reindex(df.index, method="ffill")


class CPRNarrow(_WM):
    id = "cpr_narrow_trend"; name_en = "CPR narrow-range trend day (Indian school)"; name_fa = "CPR رنج باریک = روز رونددار (مکتب هند)"
    author = "Frank Ochoa · Indian intraday community"; params = {"narrow": 0.5}; timeframes = "5m – 1h"
    description_en = ("Central Pivot Range = (pivot, BC, TC) from yesterday. A CPR narrower than 50 % of its 20-day median predicts a trend day: trade the first "
                      "15-min close outside the CPR in the direction of the break, stop the other CPR edge, target previous day's high/low then 2R.")
    description_fa = ("محدودهٔ محوری مرکزی (pivot، BC، TC) از دیروز. CPR باریک‌تر از ۵۰٪ میانهٔ ۲۰ روزه، روز رونددار را پیش‌بینی می‌کند: اولین بسته‌شدن بیرون CPR را "
                      "هم‌جهت شکست معامله کن، استاپ لبهٔ دیگر CPR، هدف سقف/کف دیروز سپس 2R.")
    rules_en = ["CPR width < 0.5 × 20-day median", "Close above TC (long) / below BC (short), first time today", "Stop = opposite CPR edge; target = prev day high/low (min 2R)"]
    rules_fa = ["عرض CPR < ۰٫۵ × میانهٔ ۲۰ روزه", "بسته‌شدن بالای TC (خرید) / زیر BC (فروش)، اولین بار امروز", "استاپ لبهٔ مخالف CPR؛ هدف سقف/کف دیروز (حداقل 2R)"]
    pros_en = ["Objective trend-day filter"]; pros_fa = ["فیلتر عینی روز رونددار"]; cons_en = ["Intraday only; needs daily session structure"]; cons_fa = ["فقط اینترادی؛ نیاز به ساختار روزانه"]

    def run(self, df):
        cp = _cpr(df); c = df.close
        narrow = cp.width < self.p["narrow"] * cp.width_med
        above = c > cp.cpr_hi; below = c < cp.cpr_lo
        day = pd.Series(df.index.normalize() if hasattr(df.index, "normalize") else np.arange(len(df)) // 24, index=df.index)
        first_up = above & ~above.shift(1).fillna(False) & (above.groupby(day).cumsum() == 1)
        first_dn = below & ~below.shift(1).fillna(False) & (below.groupby(day).cumsum() == 1)
        long = narrow & first_up; short = narrow & first_dn
        stop = pd.Series(np.nan, index=df.index); tgt = stop.copy()
        stop[long] = cp.cpr_lo[long]; tgt[long] = np.maximum(cp.ph, c + 2 * (c - cp.cpr_lo))[long]
        stop[short] = cp.cpr_hi[short]; tgt[short] = np.minimum(cp.pl, c - 2 * (cp.cpr_hi - c))[short]
        return self.finish(df, long, short, {"CPR top": cp.cpr_hi, "CPR bottom": cp.cpr_lo, "Pivot": cp.p}, stop=stop, tgt=tgt)


# ---------------------------------------------------------------------------------------------- Persian RTM school: QM / FTR / Flag-limit
class QuasimodoRTM(_WM):
    id = "rtm_quasimodo"; name_en = "RTM Quasimodo (QM) — head & shoulders with engulfed shoulder"; name_fa = "کوازیمودو RTM — سر و شانهٔ با شانهٔ بلعیده‌شده"
    author = "Read-The-Market school (IF Myfxbook) · Persian PA teachers"; params = {"left": 3, "right": 3}
    description_en = ("QM: higher-high then a lower-low that engulfs the previous low (structure break), price returns to the LEFT shoulder zone → sell. The left shoulder "
                      "(QML) is the entry; stop above the head; target the last low. Bullish mirror.")
    description_fa = ("QM: سقف بالاتر سپس کف پایین‌تر که کف قبلی را می‌بلعد (شکست ساختار)، قیمت به ناحیهٔ شانهٔ چپ برمی‌گردد → فروش. شانهٔ چپ (QML) نقطهٔ ورود؛ "
                      "استاپ بالای سر؛ هدف آخرین کف. برعکس برای خرید.")
    rules_en = ["Swings: L1 < H1(left shoulder) < H2(head) ; then L2 < L1 (engulf)", "Price returns to H1 zone (±0.25 ATR) within 40 bars", "Sell at H1; stop above H2; target L2"]
    rules_fa = ["سوئینگ‌ها: L1 < H1(شانهٔ چپ) < H2(سر)؛ سپس L2 < L1 (بلعیدن)", "بازگشت قیمت به ناحیهٔ H1 (±۰٫۲۵ATR) طی ۴۰ کندل", "فروش در H1؛ استاپ بالای H2؛ هدف L2"]
    pros_en = ["Excellent R:R at fresh QML"]; pros_fa = ["R:R عالی در QML تازه"]; cons_en = ["Subjective swing choice in the original; here fractal 3/3"]; cons_fa = ["انتخاب سوئینگ در نسخهٔ اصلی ذهنی است؛ اینجا فراکتال ۳/۳"]

    def run(self, df):
        sh, sl_ = ta.swing_points(df, self.p["left"], self.p["right"]); n = len(df)
        h, l, c = df.high.values, df.low.values, df.close.values; a = ta.atr(df).values
        long = np.zeros(n, bool); short = np.zeros(n, bool); stop = np.full(n, np.nan); tgt = np.full(n, np.nan)
        piv = sorted([(i, "H") for i in np.where(sh.values)[0]] + [(i, "L") for i in np.where(sl_.values)[0]])
        r = self.p["right"]
        for k in range(3, len(piv)):
            (i1, t1), (i2, t2_), (i3, t3), (i4, t4) = piv[k - 3:k + 1]
            # bearish QM: L1, H1, ... need H1 < H2 and L2 < L1 ; sequence H1(i1) L1(i2) H2(i3) L2(i4)
            if (t1, t2_, t3, t4) == ("H", "L", "H", "L") and h[i3] > h[i1] and l[i4] < l[i2]:
                qml = h[i1]
                for j in range(i4 + r, min(i4 + r + 40, n)):
                    if h[j] >= qml - 0.25 * a[j] and c[j] < qml + 0.25 * a[j] and h[j] < h[i3]:
                        short[j] = True; stop[j] = h[i3] + 0.1 * a[j]; tgt[j] = l[i4]; break
                    if c[j] > h[i3]:
                        break
            if (t1, t2_, t3, t4) == ("L", "H", "L", "H") and l[i3] < l[i1] and h[i4] > h[i2]:
                qml = l[i1]
                for j in range(i4 + r, min(i4 + r + 40, n)):
                    if l[j] <= qml + 0.25 * a[j] and c[j] > qml - 0.25 * a[j] and l[j] > l[i3]:
                        long[j] = True; stop[j] = l[i3] - 0.1 * a[j]; tgt[j] = h[i4]; break
                    if c[j] < l[i3]:
                        break
        idx = df.index
        return self.finish(df, pd.Series(long, idx), pd.Series(short, idx), stop=pd.Series(stop, idx), tgt=pd.Series(tgt, idx))


class FTRZone(_WM):
    id = "rtm_ftr"; name_en = "RTM FTR — Fail-To-Return zone retest"; name_fa = "FTR در RTM — بازگشت به ناحیهٔ Fail-To-Return"
    author = "RTM school · Persian PA"; params = {"lookback": 30}
    description_en = ("After price breaks a swing high with momentum, the last small pullback base BEFORE the break (the 'FTR' base) becomes demand: price returns to it, "
                      "fails to go back below → buy with stop under the base. Mirror for supply.")
    description_fa = ("پس از شکست مومنتومی سقف سوئینگ، آخرین پایهٔ پولبک کوچک پیش از شکست (پایهٔ FTR) تقاضا می‌شود: قیمت به آن برمی‌گردد و نمی‌تواند زیرش برود → "
                      "خرید با استاپ زیر پایه. برای عرضه برعکس.")
    rules_en = ["Break of 20-bar high with close > high + 0.5 ATR (momentum)", "Base = lowest low of the 3 bars before the breakout bar .. breakout open", "First return into base within 30 bars, close back above base top → long", "Stop base low − 0.2 ATR; target = breakout extreme + base height×2"]
    rules_fa = ["شکست سقف ۲۰ کندلی با بسته‌شدن > سقف + ۰٫۵ATR", "پایه = کف ۳ کندل قبل از کندل شکست تا اوپن شکست", "اولین بازگشت به پایه طی ۳۰ کندل و بسته‌شدن بالای سقف پایه → خرید", "استاپ کف پایه − ۰٫۲ATR؛ هدف اکسترمم شکست + ۲×ارتفاع پایه"]
    pros_en = ["Trades with momentum, tight stop"]; pros_fa = ["هم‌جهت مومنتوم، استاپ فشرده"]; cons_en = ["Zone may be skipped entirely"]; cons_fa = ["ناحیه ممکن است اصلاً لمس نشود"]

    def run(self, df):
        n = len(df); h, l, c, o = df.high.values, df.low.values, df.close.values, df.open.values; a = ta.atr(df).values
        hh = pd.Series(h).rolling(20).max().shift(1).values; ll = pd.Series(l).rolling(20).min().shift(1).values
        long = np.zeros(n, bool); short = np.zeros(n, bool); stop = np.full(n, np.nan); tgt = np.full(n, np.nan)
        i = 25
        while i < n - 2:
            if c[i] > hh[i] + 0.5 * a[i]:
                blo, bhi = l[i - 3:i].min(), max(o[i], h[i - 3:i].min()); ext = h[i]
                for j in range(i + 2, min(i + 2 + self.p["lookback"], n)):
                    ext = max(ext, h[j])
                    if l[j] <= bhi and c[j] > bhi and l[j] > blo - 0.2 * a[j]:
                        long[j] = True; stop[j] = blo - 0.2 * a[j]; tgt[j] = ext + 2 * (bhi - blo); i = j; break
                    if c[j] < blo:
                        i = j; break
            elif c[i] < ll[i] - 0.5 * a[i]:
                bhi, blo = h[i - 3:i].max(), min(o[i], l[i - 3:i].max()); ext = l[i]
                for j in range(i + 2, min(i + 2 + self.p["lookback"], n)):
                    ext = min(ext, l[j])
                    if h[j] >= blo and c[j] < blo and h[j] < bhi + 0.2 * a[j]:
                        short[j] = True; stop[j] = bhi + 0.2 * a[j]; tgt[j] = ext - 2 * (bhi - blo); i = j; break
                    if c[j] > bhi:
                        i = j; break
            i += 1
        idx = df.index
        return self.finish(df, pd.Series(long, idx), pd.Series(short, idx), stop=pd.Series(stop, idx), tgt=pd.Series(tgt, idx))


class CompressionRTM(_WM):
    id = "rtm_compression"; name_en = "RTM Compression into supply/demand"; name_fa = "کامپرشن RTM به سمت عرضه/تقاضا"
    author = "RTM school"; params = {"bars": 12}
    description_en = ("A grinding, overlapping climb (≥12 bars, small bodies, higher lows, no impulsive bar) INTO a fresh supply zone (last 50-bar swing high region) removes the demand "
                      "beneath: when price touches supply, sell with stop above the zone and target the compression origin. Mirror for demand.")
    description_fa = ("صعود فرسایشی و هم‌پوشان (≥۱۲ کندل، بدنه‌های کوچک، کف‌های بالاتر، بدون کندل ایمپالسیو) به سمت عرضهٔ تازه (ناحیهٔ سقف سوئینگ ۵۰ کندلی) تقاضای زیر را "
                      "پاک می‌کند: وقتی قیمت به عرضه می‌رسد، بفروش؛ استاپ بالای ناحیه؛ هدف مبدأ کامپرشن. برعکس برای تقاضا.")
    rules_en = ["Last N bars: mean |body| < 0.5 ATR, ≥70 % of lows higher than previous, net move > 1.5 ATR", "Touch of 50-bar swing high within 0.3 ATR", "Sell on first bearish close; stop = swing high + 0.3 ATR; target = compression start"]
    rules_fa = ["N کندل آخر: میانگین بدنه < ۰٫۵ATR، ≥۷۰٪ کف‌ها بالاتر، حرکت خالص > ۱٫۵ATR", "لمس سقف سوئینگ ۵۰ کندلی در ۰٫۳ATR", "فروش با اولین بسته‌شدن نزولی؛ استاپ سقف + ۰٫۳ATR؛ هدف شروع کامپرشن"]
    pros_en = ["Explains why 'support' fails after a grind"]; pros_fa = ["توضیح می‌دهد چرا حمایت پس از فرسایش می‌شکند"]; cons_en = ["Needs a real zone to hit"]; cons_fa = ["نیاز به ناحیهٔ واقعی"]

    def run(self, df):
        N = self.p["bars"]; h, l, c, o = df.high, df.low, df.close, df.open; a = ta.atr(df)
        body = (c - o).abs(); small = body.rolling(N).mean() < 0.5 * a
        hl_share = (l > l.shift(1)).astype(float).rolling(N).mean(); lh_share = (h < h.shift(1)).astype(float).rolling(N).mean()
        net_up = (c - c.shift(N)) > 1.5 * a; net_dn = (c.shift(N) - c) > 1.5 * a
        sup_hi = h.rolling(50).max().shift(N + 1); dem_lo = l.rolling(50).min().shift(N + 1)
        touch_s = (h >= sup_hi - 0.3 * a) & (c < sup_hi + 0.3 * a); touch_d = (l <= dem_lo + 0.3 * a) & (c > dem_lo - 0.3 * a)
        short = small & (hl_share >= 0.7) & net_up & touch_s & (c < o); long = small & (lh_share >= 0.7) & net_dn & touch_d & (c > o)
        stop = pd.Series(np.nan, index=df.index); tgt = stop.copy()
        stop[short] = (sup_hi + 0.3 * a)[short]; tgt[short] = l.shift(N)[short]; stop[long] = (dem_lo - 0.3 * a)[long]; tgt[long] = h.shift(N)[long]
        return self.finish(df, long, short, {"Supply": sup_hi, "Demand": dem_lo}, stop=stop, tgt=tgt)


# ---------------------------------------------------------------------------------------------- Spanish Wyckoff school: Spring/Upthrust with test
class WyckoffSpringTest(_WM):
    id = "wyckoff_spring_test"; name_en = "Wyckoff Spring + secondary test (método Wyckoff)"; name_fa = "اسپرینگ وایکوف + تست ثانویه (método Wyckoff)"
    author = "R. Wyckoff · Rubén Villahermosa (Spanish school)"; params = {"range": 40}
    description_en = ("Spring = a shake-out below the trading-range low (volume may spike) that recovers back inside; the TEST is a later dip on LOWER volume that holds above the "
                      "spring low. Buy the test's close; stop under spring; target range top (then 'jump across the creek'). Upthrust mirror.")
    description_fa = ("اسپرینگ = شیک‌اوت زیر کف رنج (شاید با حجم بالا) که به داخل برمی‌گردد؛ تست = افت بعدی با حجم کمتر که بالای کف اسپرینگ می‌ماند. با بسته‌شدن تست بخر؛ "
                      "استاپ زیر اسپرینگ؛ هدف سقف رنج. برعکس آپ‌تراست.")
    rules_en = ["Range = 40-bar high/low with width < 8 %", "Spring bar: low < range low, close back inside", "Test within 3–15 bars: low > spring low, volume < 70 % of spring volume, close up", "Stop spring low − 0.2 ATR; target range high"]
    rules_fa = ["رنج = سقف/کف ۴۰ کندلی با عرض < ۸٪", "کندل اسپرینگ: کف زیر کف رنج، بسته‌شدن داخل", "تست طی ۳ تا ۱۵ کندل: کف بالای کف اسپرینگ، حجم < ۷۰٪ حجم اسپرینگ، بسته‌شدن صعودی", "استاپ کف اسپرینگ − ۰٫۲ATR؛ هدف سقف رنج"]
    pros_en = ["Volume-confirmed accumulation"]; pros_fa = ["انباشت با تأیید حجم"]; cons_en = ["Needs volume data"]; cons_fa = ["نیاز به داده حجم"]

    def run(self, df):
        n = len(df); h, l, c, v = df.high.values, df.low.values, df.close.values, df.volume.values; a = ta.atr(df).values
        R = self.p["range"]
        long = np.zeros(n, bool); short = np.zeros(n, bool); stop = np.full(n, np.nan); tgt = np.full(n, np.nan)
        for i in range(R + 1, n - 3):
            rh, rl = h[i - R:i].max(), l[i - R:i].min()
            if (rh - rl) / rl > 0.08:
                continue
            if l[i] < rl and c[i] > rl:
                for j in range(i + 3, min(i + 16, n)):
                    if l[j] > l[i] and l[j] < rl + 0.5 * a[j] and v[j] < 0.7 * v[i] and c[j] > c[j - 1]:
                        long[j] = True; stop[j] = l[i] - 0.2 * a[j]; tgt[j] = rh; break
                    if c[j] < l[i]:
                        break
            if h[i] > rh and c[i] < rh:
                for j in range(i + 3, min(i + 16, n)):
                    if h[j] < h[i] and h[j] > rh - 0.5 * a[j] and v[j] < 0.7 * v[i] and c[j] < c[j - 1]:
                        short[j] = True; stop[j] = h[i] + 0.2 * a[j]; tgt[j] = rl; break
                    if c[j] > h[i]:
                        break
        idx = df.index
        return self.finish(df, pd.Series(long, idx), pd.Series(short, idx), stop=pd.Series(stop, idx), tgt=pd.Series(tgt, idx))


WORLD_STRATEGIES = [ChanFirstBuy, ChanThirdBuy, SakataSanpei, SakataSanku, SakataSanpo, SakataSanzan, GerchikFalseBreak, GerchikParanormal,
                    LW91, LW92, Stormer81, CPRNarrow, QuasimodoRTM, FTRZone, CompressionRTM, WyckoffSpringTest]
