"""
Chart & candlestick pattern engine — Bulkowski (Encyclopedia of Chart Patterns), Nison (Japanese Candlestick
Charting Techniques), Murphy (Technical Analysis of the Financial Markets).

Each detector returns a list of dict(name, name_fa, side, i_start, i_end, level, target, stop, stats) where `stats`
are Bulkowski's published bull-market figures (break-even failure rate %, average rise/decline %) so the UI can
show what the pattern has historically done — not what folklore says.
"""
import numpy as np
import pandas as pd
from core.indicators import swing_points, atr

# Bulkowski (2nd/3rd ed., bull market): failure rate %, avg move %, rank (lower better)
BULK = {
    "double_bottom_adam_adam": dict(fail=5, move=35, rank=8, fa="کف دوقلو (Adam & Adam)"),
    "double_top_adam_adam": dict(fail=8, move=-19, rank=10, fa="سقف دوقلو (Adam & Adam)"),
    "head_shoulders_top": dict(fail=4, move=-22, rank=1, fa="سر و شانهٔ سقف"),
    "head_shoulders_bottom": dict(fail=3, move=38, rank=7, fa="سر و شانهٔ کف"),
    "ascending_triangle": dict(fail=13, move=35, rank=17, fa="مثلث صعودی"),
    "descending_triangle": dict(fail=16, move=-16, rank=10, fa="مثلث نزولی"),
    "symmetrical_triangle": dict(fail=9, move=31, rank=16, fa="مثلث متقارن"),
    "rectangle_top": dict(fail=9, move=39, rank=9, fa="مستطیل (شکست رو به بالا)"),
    "rectangle_bottom": dict(fail=13, move=-14, rank=12, fa="مستطیل (شکست رو به پایین)"),
    "bull_flag": dict(fail=4, move=23, rank=3, fa="پرچم صعودی (تند)"),
    "bear_flag": dict(fail=6, move=-17, rank=9, fa="پرچم نزولی (تند)"),
    "cup_handle": dict(fail=5, move=34, rank=13, fa="فنجان و دسته"),
    "triple_bottom": dict(fail=4, move=37, rank=4, fa="کف سه‌قلو"),
    "triple_top": dict(fail=10, move=-19, rank=13, fa="سقف سه‌قلو"),
    "rounding_bottom": dict(fail=5, move=43, rank=5, fa="کف گرد"),
    "wedge_falling": dict(fail=11, move=32, rank=21, fa="کنج نزولی (شکست بالا)"),
    "wedge_rising": dict(fail=8, move=-14, rank=20, fa="کنج صعودی (شکست پایین)"),
}
# Nison candlesticks with Bulkowski's candle-performance ranking (reversal rate %)
CANDLES = {
    "hammer": dict(side=1, rev=60, fa="چکش"), "hanging_man": dict(side=-1, rev=59, fa="مرد آویزان"),
    "inverted_hammer": dict(side=1, rev=65, fa="چکش وارونه"), "shooting_star": dict(side=-1, rev=59, fa="ستارهٔ دنباله‌دار"),
    "bullish_engulfing": dict(side=1, rev=63, fa="پوشای صعودی"), "bearish_engulfing": dict(side=-1, rev=79, fa="پوشای نزولی"),
    "piercing": dict(side=1, rev=64, fa="نفوذی"), "dark_cloud": dict(side=-1, rev=60, fa="ابر سیاه"),
    "morning_star": dict(side=1, rev=78, fa="ستارهٔ صبحگاهی"), "evening_star": dict(side=-1, rev=72, fa="ستارهٔ شامگاهی"),
    "three_white_soldiers": dict(side=1, rev=82, fa="سه سرباز سفید"), "three_black_crows": dict(side=-1, rev=78, fa="سه کلاغ سیاه"),
    "bullish_harami": dict(side=1, rev=53, fa="هارامی صعودی"), "bearish_harami": dict(side=-1, rev=53, fa="هارامی نزولی"),
    "doji_dragonfly": dict(side=1, rev=50, fa="دوجی سنجاقک"), "doji_gravestone": dict(side=-1, rev=51, fa="دوجی سنگ‌قبر"),
    "tweezer_bottom": dict(side=1, rev=56, fa="انبرک کف"), "tweezer_top": dict(side=-1, rev=56, fa="انبرک سقف"),
    "abandoned_baby_bull": dict(side=1, rev=70, fa="نوزاد رهاشده (صعودی)"), "abandoned_baby_bear": dict(side=-1, rev=69, fa="نوزاد رهاشده (نزولی)"),
    "three_inside_up": dict(side=1, rev=65, fa="سه درونی صعودی"), "three_inside_down": dict(side=-1, rev=65, fa="سه درونی نزولی"),
    "rising_three": dict(side=1, rev=74, fa="سه‌گانهٔ صعودی (ادامه)"), "falling_three": dict(side=-1, rev=71, fa="سه‌گانهٔ نزولی (ادامه)"),
    "marubozu_bull": dict(side=1, rev=56, fa="ماروبوزو سفید"), "marubozu_bear": dict(side=-1, rev=56, fa="ماروبوزو سیاه"),
}


# ---------------------------------------------------------------- candlesticks (Nison rules, trend-qualified)
def candlesticks(df, trend_len=10):
    o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
    n = len(df)
    body = np.abs(c - o); rng = (h - l) + 1e-12
    up_w = h - np.maximum(o, c); lo_w = np.minimum(o, c) - l
    avg_body = pd.Series(body).rolling(20).mean().bfill().values
    sma = pd.Series(c).rolling(trend_len).mean().values
    out = []

    def add(i, key, i0=None):
        m = CANDLES[key]
        out.append(dict(name=key, name_fa=m["fa"], side=m["side"], i_start=i0 if i0 is not None else i, i_end=i,
                        stats=dict(reversal_rate=m["rev"]), kind="candle"))
    for i in range(2, n):
        down = c[i - 1] < sma[i - 1] if not np.isnan(sma[i - 1]) else False   # prior trend (Nison: pattern needs a trend)
        up = not down
        small = body[i] <= 0.3 * rng[i]
        # single-bar
        if small and lo_w[i] >= 2 * body[i] and up_w[i] <= 0.1 * rng[i]:
            add(i, "hammer" if down else "hanging_man")
        if small and up_w[i] >= 2 * body[i] and lo_w[i] <= 0.1 * rng[i]:
            add(i, "inverted_hammer" if down else "shooting_star")
        if body[i] <= 0.05 * rng[i]:
            if lo_w[i] > 0.7 * rng[i]:
                add(i, "doji_dragonfly")
            elif up_w[i] > 0.7 * rng[i]:
                add(i, "doji_gravestone")
        if body[i] >= 0.95 * rng[i] and body[i] > avg_body[i]:
            add(i, "marubozu_bull" if c[i] > o[i] else "marubozu_bear")
        # two-bar
        if c[i] > o[i] and c[i - 1] < o[i - 1] and o[i] <= c[i - 1] and c[i] >= o[i - 1] and body[i] > body[i - 1] and down:
            add(i, "bullish_engulfing", i - 1)
        if c[i] < o[i] and c[i - 1] > o[i - 1] and o[i] >= c[i - 1] and c[i] <= o[i - 1] and body[i] > body[i - 1] and up:
            add(i, "bearish_engulfing", i - 1)
        if down and c[i - 1] < o[i - 1] and o[i] < l[i - 1] and c[i] > (o[i - 1] + c[i - 1]) / 2 and c[i] < o[i - 1]:
            add(i, "piercing", i - 1)
        if up and c[i - 1] > o[i - 1] and o[i] > h[i - 1] and c[i] < (o[i - 1] + c[i - 1]) / 2 and c[i] > o[i - 1]:
            add(i, "dark_cloud", i - 1)
        if body[i - 1] > avg_body[i - 1] and body[i] < 0.5 * body[i - 1] and max(o[i], c[i]) < max(o[i - 1], c[i - 1]) and min(o[i], c[i]) > min(o[i - 1], c[i - 1]):
            if c[i - 1] < o[i - 1] and down:
                add(i, "bullish_harami", i - 1)
            elif c[i - 1] > o[i - 1] and up:
                add(i, "bearish_harami", i - 1)
        if down and abs(l[i] - l[i - 1]) <= 0.1 * rng[i] and c[i - 1] < o[i - 1] and c[i] > o[i]:
            add(i, "tweezer_bottom", i - 1)
        if up and abs(h[i] - h[i - 1]) <= 0.1 * rng[i] and c[i - 1] > o[i - 1] and c[i] < o[i]:
            add(i, "tweezer_top", i - 1)
        # three-bar
        if i >= 2:
            b0, b1, b2 = body[i - 2], body[i - 1], body[i]
            if down and c[i - 2] < o[i - 2] and b0 > avg_body[i] and b1 < 0.3 * b0 and c[i] > o[i] and c[i] > (o[i - 2] + c[i - 2]) / 2:
                gap = h[i - 1] < l[i - 2] and h[i - 1] < l[i]
                add(i, "abandoned_baby_bull" if gap else "morning_star", i - 2)
            if up and c[i - 2] > o[i - 2] and b0 > avg_body[i] and b1 < 0.3 * b0 and c[i] < o[i] and c[i] < (o[i - 2] + c[i - 2]) / 2:
                gap = l[i - 1] > h[i - 2] and l[i - 1] > h[i]
                add(i, "abandoned_baby_bear" if gap else "evening_star", i - 2)
            if all(c[j] > o[j] for j in (i - 2, i - 1, i)) and c[i] > c[i - 1] > c[i - 2] and all(up_w[j] < 0.3 * body[j] for j in (i - 2, i - 1, i)) and all(body[j] > avg_body[j] * 0.8 for j in (i - 2, i - 1, i)):
                add(i, "three_white_soldiers", i - 2)
            if all(c[j] < o[j] for j in (i - 2, i - 1, i)) and c[i] < c[i - 1] < c[i - 2] and all(lo_w[j] < 0.3 * body[j] for j in (i - 2, i - 1, i)) and all(body[j] > avg_body[j] * 0.8 for j in (i - 2, i - 1, i)):
                add(i, "three_black_crows", i - 2)
            if down and c[i - 2] < o[i - 2] and b1 < 0.5 * b0 and max(o[i - 1], c[i - 1]) < o[i - 2] and min(o[i - 1], c[i - 1]) > c[i - 2] and c[i] > o[i - 2]:
                add(i, "three_inside_up", i - 2)
            if up and c[i - 2] > o[i - 2] and b1 < 0.5 * b0 and max(o[i - 1], c[i - 1]) < c[i - 2] and min(o[i - 1], c[i - 1]) > o[i - 2] and c[i] < o[i - 2]:
                add(i, "three_inside_down", i - 2)
        # five-bar continuation (rising / falling three methods)
        if i >= 4:
            if c[i - 4] > o[i - 4] and body[i - 4] > avg_body[i] and all(body[j] < 0.5 * body[i - 4] and l[j] > l[i - 4] and h[j] < h[i - 4] for j in (i - 3, i - 2, i - 1)) and c[i] > h[i - 4]:
                add(i, "rising_three", i - 4)
            if c[i - 4] < o[i - 4] and body[i - 4] > avg_body[i] and all(body[j] < 0.5 * body[i - 4] and l[j] > l[i - 4] and h[j] < h[i - 4] for j in (i - 3, i - 2, i - 1)) and c[i] < l[i - 4]:
                add(i, "falling_three", i - 4)
    return out


# ---------------------------------------------------------------- chart patterns (Bulkowski identification rules)
def _pivots(df, left=5, right=5):
    hi, lo = swing_points(df, left, right) if swing_points.__code__.co_argcount >= 3 else swing_points(df)
    H = [(i, df.high.values[i]) for i in np.where(hi.values)[0]]
    L = [(i, df.low.values[i]) for i in np.where(lo.values)[0]]
    return H, L


def chart_patterns(df, tol=0.03, min_sep=8, lookback=300):
    """Detect classic patterns on the last `lookback` bars. Levels are the breakout line; target = Bulkowski's
    measure rule (pattern height projected), stop = opposite side of pattern."""
    d = df.tail(lookback)
    off = len(df) - len(d)
    H, L = _pivots(d)
    c = d.close.values; h = d.high.values; l = d.low.values
    n = len(d)
    out = []
    a = atr(d).bfill().values

    def add(name, side, i0, i1, level, height):
        m = BULK[name]
        out.append(dict(name=name, name_fa=m["fa"], side=side, i_start=i0 + off, i_end=i1 + off, level=float(level),
                        target=float(level + side * height), stop=float(level - side * height * 0.5),
                        stats=dict(fail=m["fail"], avg_move=m["move"], rank=m["rank"]), kind="chart",
                        confirmed=bool((c[-1] > level) if side == 1 else (c[-1] < level))))
    # double / triple bottoms & tops
    for pts, side, name2, name3 in ((L, 1, "double_bottom_adam_adam", "triple_bottom"), (H, -1, "double_top_adam_adam", "triple_top")):
        for k in range(1, len(pts)):
            (i0, p0), (i1, p1) = pts[k - 1], pts[k]
            if i1 - i0 < min_sep or abs(p1 - p0) / p0 > tol:
                continue
            mid = h[i0:i1].max() if side == 1 else l[i0:i1].min()
            height = abs(mid - (p0 + p1) / 2)
            if height < 1.5 * a[i1]:
                continue
            if k >= 2 and abs(pts[k - 2][1] - p0) / p0 <= tol and i0 - pts[k - 2][0] >= min_sep:
                add(name3, side, pts[k - 2][0], i1, mid, height)
            else:
                add(name2, side, i0, i1, mid, height)
    # head & shoulders
    for pts, side, name in ((H, -1, "head_shoulders_top"), (L, 1, "head_shoulders_bottom")):
        for k in range(2, len(pts)):
            (i0, s1), (i1, hd), (i2, s2) = pts[k - 2], pts[k - 1], pts[k]
            higher = (hd > s1 and hd > s2) if side == -1 else (hd < s1 and hd < s2)
            if not higher or abs(s1 - s2) / s1 > tol * 1.5:
                continue
            neck = (l[i0:i1].min() + l[i1:i2].min()) / 2 if side == -1 else (h[i0:i1].max() + h[i1:i2].max()) / 2
            add(name, side, i0, i2, neck, abs(hd - neck))
    # triangles / rectangles / wedges via linear fits of last 3 highs & lows
    if len(H) >= 3 and len(L) >= 3:
        hh = H[-3:]; ll = L[-3:]
        sh = np.polyfit([i for i, _ in hh], [p for _, p in hh], 1)[0] / c[-1]
        sl = np.polyfit([i for i, _ in ll], [p for _, p in ll], 1)[0] / c[-1]
        i0 = min(hh[0][0], ll[0][0]); i1 = n - 1
        height = hh[0][1] - ll[0][1]
        flat = 0.0005
        if abs(sh) < flat and sl > flat:
            add("ascending_triangle", 1, i0, i1, hh[-1][1], height)
        elif abs(sl) < flat and sh < -flat:
            add("descending_triangle", -1, i0, i1, ll[-1][1], height)
        elif sh < -flat and sl > flat:
            add("symmetrical_triangle", 1 if c[-1] > (hh[-1][1] + ll[-1][1]) / 2 else -1, i0, i1, hh[-1][1] if c[-1] > (hh[-1][1] + ll[-1][1]) / 2 else ll[-1][1], height)
        elif abs(sh) < flat and abs(sl) < flat and height > 2 * a[-1]:
            add("rectangle_top" if c[-1] > (hh[-1][1] + ll[-1][1]) / 2 else "rectangle_bottom", 1 if c[-1] > (hh[-1][1] + ll[-1][1]) / 2 else -1, i0, i1,
                hh[-1][1] if c[-1] > (hh[-1][1] + ll[-1][1]) / 2 else ll[-1][1], height)
        elif sh < -flat and sl < -flat and sl < sh:
            add("wedge_falling", 1, i0, i1, hh[-1][1], height)
        elif sh > flat and sl > flat and sh < sl:
            add("wedge_rising", -1, i0, i1, ll[-1][1], height)
    # flags: sharp pole then tight counter-drift
    if n > 40:
        pole = (c[-15] - c[-35]) / c[-35]
        drift = (c[-1] - c[-15]) / c[-15]
        rng15 = (h[-15:].max() - l[-15:].min()) / c[-1]
        if pole > 0.10 and -0.06 < drift < 0.01 and rng15 < 0.08:
            add("bull_flag", 1, n - 35, n - 1, h[-15:].max(), c[-15] - c[-35])
        if pole < -0.10 and -0.01 < drift < 0.06 and rng15 < 0.08:
            add("bear_flag", -1, n - 35, n - 1, l[-15:].min(), c[-35] - c[-15])
    # cup & handle (O'Neil/Bulkowski): U-shape 30-120 bars, rims within 5%, handle < 1/3 depth
    for span in (40, 60, 90, 120):
        if n < span + 15:
            continue
        seg = c[-(span + 15):-15]
        rim_l, rim_r = seg[:5].max(), seg[-5:].max()
        bottom = seg.min()
        if abs(rim_l - rim_r) / rim_r < 0.05 and (rim_r - bottom) / rim_r > 0.12 and np.argmin(seg) > len(seg) * 0.3 and np.argmin(seg) < len(seg) * 0.7:
            handle = c[-15:]
            if handle.min() > rim_r - (rim_r - bottom) / 3 and handle.max() <= rim_r * 1.01:
                add("cup_handle", 1, n - span - 15, n - 1, rim_r, rim_r - bottom)
                break
    # dedupe by name keep latest
    seen = {}
    for p in out:
        seen[p["name"]] = p
    return sorted(seen.values(), key=lambda p: -p["i_end"])


def summarize(df, recent=3):
    """Everything that is currently 'live': candles in the last `recent` bars + chart patterns still near breakout."""
    n = len(df)
    cs = [p for p in candlesticks(df) if p["i_end"] >= n - recent]
    ch = chart_patterns(df)
    px = df.close.iloc[-1]
    ch = [p for p in ch if abs(p["level"] - px) / px < 0.08]
    return cs, ch
