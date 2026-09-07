"""
Chart-image understanding (Phase 11, "YOLO / OpenCV+PyTorch / Detectron2" category).

Design decision — why not ship a YOLO/Detectron2 model?
  Detectors trained on chart screenshots (the public YOLO-chart-pattern projects) reach ~60-75% mAP on their own
  synthetic sets and degrade badly on unseen themes. They also need torch + a 50-250 MB weight file. The far more
  robust approach used by serious chart-digitisers is the OpenCV one: *segment the candles, reconstruct the OHLC
  series, then run exact numeric pattern logic on it*. That is what this module does:

    image ──► plot-area & theme detection ──► candle colour clustering (any theme) ──► per-candle body/wick geometry
          ──► relative OHLC DataFrame ──► core.patterns (26 Nison candles + Bulkowski chart patterns), trend, S/R,
              indicators ──► annotated image + bilingual explanation.

  A YOLO-style *learned* detector is still available as an optional hook: if `torch` + `ultralytics` are installed
  and a weights file exists at data/models/chart_yolo.pt, its boxes are merged into the report (see `yolo_detect`).

  Self-test / "learning": `synthetic_chart()` renders random charts in several themes (TradingView dark/light,
  MetaTrader, Binance) from known OHLC; `self_test()` measures how accurately the extractor recovers them. The
  numbers are shown in the UI as a model card so nobody has to trust it blindly.
"""
import os
import numpy as np
import pandas as pd

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


# ------------------------------------------------------------------ helpers
def _load(path_or_array):
    if isinstance(path_or_array, np.ndarray):
        img = path_or_array
    else:
        img = cv2.imdecode(np.fromfile(path_or_array, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("cannot read image")
    h, w = img.shape[:2]
    scale = 1600 / max(h, w) if max(h, w) > 1600 else 1.0
    if max(h, w) < 900:                       # small screenshots / thumbnails: upscale so 1-px wicks survive morphology
        scale = 1200 / max(h, w)
    if scale != 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    # sensor / compression noise: estimate from Laplacian of a flat background; denoise only when needed
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    noise = float(np.median(np.abs(lap - np.median(lap)))) * 1.4826
    if noise > 6.0:
        img = cv2.bilateralFilter(img, 5, 40, 5)     # edge-preserving: keeps candle borders, kills grain
    return img


def _background(img):
    small = cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA).reshape(-1, 3)
    vals, counts = np.unique((small // 8) * 8, axis=0, return_counts=True)
    bg = vals[counts.argmax()].astype(int)
    return bg, float(bg.mean()) < 128  # colour, is_dark


def _plot_area(img, bg):
    """crop away axes/legend margins: keep the largest rectangle where 'ink' density is chart-like"""
    diff = np.abs(img.astype(int) - bg[None, None, :]).sum(2)
    ink = (diff > 60).astype(np.uint8)
    h, w = ink.shape
    col = ink.mean(0)
    row = ink.mean(1)
    # columns / rows that contain ink above a small threshold
    xs = np.where(col > 0.01)[0]
    ys = np.where(row > 0.01)[0]
    if len(xs) < 10 or len(ys) < 10:
        return 0, 0, w, h
    x0, x1 = int(xs[0]), int(xs[-1]) + 1
    y0, y1 = int(ys[0]), int(ys[-1]) + 1
    # trim a right-hand price axis: a block of columns with tiny density after the last dense block
    dense = col > np.percentile(col[x0:x1], 40) * 0.5
    right = x1
    for x in range(x1 - 1, x0 + (x1 - x0) // 2, -1):
        if dense[x]:
            right = x + 1
            break
    return x0, y0, right, y1


def _candle_colours(hsv, mask_fg):
    """rank hue peaks by how many SMALL VERTICAL blobs they form (candles), not by pixel mass (lines/menus win that).
    returns the two best hue peaks or None"""
    sat = hsv[..., 1] > 70
    val = hsv[..., 2] > 60
    m = mask_fg & sat & val
    hues = hsv[..., 0][m]
    if hues.size < 200:
        return None
    hist = np.bincount(hues, minlength=180).astype(float)
    k = np.ones(7) / 7
    hs = np.convolve(np.concatenate([hist[-3:], hist, hist[:3]]), k, mode="same")[3:-3]
    peaks = []
    for _ in range(6):
        p = int(hs.argmax())
        if hs[p] < 50:
            break
        peaks.append(p)
        idx = np.arange(p - 12, p + 13) % 180
        hs[idx] = 0
    if len(peaks) < 2:
        return None
    scores = []
    for p in peaks:
        mm = (m & (_hue_dist(hsv[..., 0], p) <= 12)).astype(np.uint8)
        num, lab, st, _ = cv2.connectedComponentsWithStats(mm, connectivity=8)
        if num <= 1:
            scores.append(0); continue
        w_, h_, a_ = st[1:, 2], st[1:, 3], st[1:, 4]
        cand = (h_ >= 5) & (w_ <= 40) & (w_ >= 2) & (h_ >= w_ * 1.5) & (a_ >= 5) & (w_ * h_ < 5000)
        # candles of one colour share a similar width → reward width consistency; line fragments (anti-aliased MA /
        # dotted indicators) are tiny (median h < 12 px) → weight by median height so they cannot win
        if cand.sum() >= 3:
            ws_ = w_[cand]; medw = np.median(ws_)
            ok_ = cand.copy(); ok_[cand] = np.abs(ws_ - medw) <= max(1, 0.5 * medw)
            # score = total candle-like ink height (tall bodies/wicks dominate; dotted/dashed indicator fragments are short)
            consistent = float(np.minimum(h_[ok_], 200).sum()) / 20.0
        else:
            consistent = 0
        scores.append(consistent)
    order = np.argsort(scores)[::-1]
    if scores[order[0]] < 5:
        return None
    best = [peaks[order[0]], peaks[order[1]]]
    # accept the 2nd hue only if it also forms a reasonable number of candle blobs; else caller uses gray/mono path
    if scores[order[1]] < max(3, 0.05 * scores[order[0]]):
        return [best[0], None]
    return best


def _hue_dist(h, p):
    d = np.abs(h.astype(int) - p)
    return np.minimum(d, 180 - d)


def _is_bull_hue(h):
    """green/teal/blue/white family = bullish; red/orange/magenta family = bearish (classic + TradingView + Binance)"""
    return 30 <= h <= 130


# ------------------------------------------------------------------ main extraction
def extract_candles(path_or_array, min_candles=8):
    """returns dict(df=OHLC DataFrame in pixel-price units (higher=higher price), boxes=list of candle geometry,
    crop=(x0,y0,x1,y1), theme=..., annotated=BGR image)"""
    if cv2 is None:
        raise RuntimeError("opencv not installed")
    img = _load(path_or_array)
    bg, dark = _background(img)
    x0, y0, x1, y1 = _plot_area(img, bg)
    crop = img[y0:y1, x0:x1]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    diff = np.abs(crop.astype(int) - bg[None, None, :]).sum(2)
    fg = diff > 45
    peaks = _candle_colours(hsv, fg)
    H = hsv[..., 0]

    def _blob_score(mm):
        """how many candle-like (narrow, taller-than-wide, width-consistent) blobs a binary mask forms"""
        num_, lab_, st_, _ = cv2.connectedComponentsWithStats(mm.astype(np.uint8), connectivity=8)
        if num_ <= 1:
            return 0
        w_, h_, a_ = st_[1:, 2], st_[1:, 3], st_[1:, 4]
        cand = (h_ >= 5) & (w_ <= 40) & (w_ >= 2) & (h_ >= w_ * 1.5) & (a_ >= 5) & (w_ * h_ < 5000)
        if cand.sum() < 3:
            return 0
        ws_ = w_[cand]; medw = np.median(ws_)
        ok_ = cand.copy(); ok_[cand] = np.abs(ws_ - medw) <= max(1, 0.5 * medw)
        return float(np.minimum(h_[ok_], 200).sum()) / 20.0
    S = hsv[..., 1]
    Vv = hsv[..., 2]
    hue_gray = False
    sat_fg = fg & (S > 60) & (Vv > 60)
    gray_fg = fg & (S <= 60) & ((Vv > 150) if dark else (Vv < 110))   # white-ish (dark theme) / black-ish (light theme)
    # decide the colour scheme from pixel mass: two saturated hues, one saturated + one gray (MetaTrader), or mono
    hist = np.bincount(H[sat_fg], minlength=180).astype(float) if sat_fg.any() else np.zeros(180)
    sat_mass = float(sat_fg.sum()); gray_mass = float(gray_fg.sum())
    if peaks is not None and peaks[1] is not None:
        pa, pb = peaks
    elif peaks is not None:
        pa, pb = peaks[0], None
    else:
        pa = int(hist.argmax()) if sat_mass else None; pb = None
    # two hues that are BOTH bullish-green (e.g. MetaTrader: green wicks + a green-ish grid) is not a real 2-colour
    # scheme; fall through to the "hue + gray" path where body fill decides direction
    if pb is not None and _is_bull_hue(pa) and _is_bull_hue(pb) and gray_mass > 0.2 * sat_mass:
        pb = None
    # MetaTrader-light / mono charts: black (or white) hollow+filled candles with coloured indicator lines. If the
    # gray class forms clearly more candle-like blobs than the best hue class, ignore the hues.
    gray_score = _blob_score(gray_fg) if gray_mass > 200 else 0
    hue_score = _blob_score(sat_fg & (_hue_dist(H, pa) <= 12)) if pa is not None else 0
    hue_score_b = _blob_score(sat_fg & (_hue_dist(H, pb) <= 12)) if pb is not None else 0
    if gray_score >= max(12, 1.5 * max(hue_score, hue_score_b)):
        pa, pb = None, None          # coloured classes are indicator lines/dots; candles are the gray class
    if pb is not None:
        da, db = _hue_dist(H, pa), _hue_dist(H, pb)
        ma = sat_fg & (da <= 12) & (da <= db)
        mb = sat_fg & (db <= 12) & (db < da)
        if _is_bull_hue(pa) and not _is_bull_hue(pb):
            bull, bear = ma, mb
        elif _is_bull_hue(pb) and not _is_bull_hue(pa):
            bull, bear = mb, ma
        else:
            bull, bear = (ma, mb) if abs(pa - 60) < abs(pb - 60) else (mb, ma)
        theme = f"two hues {pa}/{pb}"
    elif pa is not None and sat_mass > 200 and gray_mass > 0.2 * sat_mass:
        # MetaTrader style: one coloured class + one white/black class
        ma = sat_fg & (_hue_dist(H, pa) <= 12)
        if _is_bull_hue(pa):
            bull, bear = ma, gray_fg
        else:
            bull, bear = gray_fg, ma
        theme = f"hue {pa} + gray"
        hue_gray = True
    else:
        # monochrome: filled body = bear, hollow body = bull is handled later by body fill ratio
        m_all = fg & ((Vv > 150) if dark else (Vv < 110))
        bull = np.zeros_like(m_all); bear = m_all
        theme = "mono"
    mask = (bull | bear).astype(np.uint8)
    # remove long vertical lines that span (almost) the full height: cursor / crosshair / session separators
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, int(mask.shape[0] * 0.9)))
    vert = cv2.morphologyEx(mask, cv2.MORPH_OPEN, vk)
    mask = cv2.bitwise_and(mask, cv2.bitwise_not(vert))
    # remove long horizontal lines (grid, MA lines drawn in candle colours) – keep vertical structures
    kern = cv2.getStructuringElement(cv2.MORPH_RECT, (max(25, mask.shape[1] // 12), 1))
    horiz = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kern)
    mask = cv2.bitwise_and(mask, cv2.bitwise_not(horiz))
    bull = bull & mask.astype(bool)
    bear = bear & mask.astype(bool)
    # ---- connected components instead of full-column projection: robust to volume panes, menus, tags
    num, lab, stats, cent = cv2.connectedComponentsWithStats(mask, connectivity=8)
    comps = []
    for k in range(1, num):
        x, y, w_, h_, area = stats[k]
        if h_ < 2 or w_ > 60 or area < 2:
            continue
        comps.append(dict(x=int(x), y=int(y), w=int(w_), h=int(h_), area=int(area), k=k))
    if len(comps) < min_candles:
        raise ValueError("too few candle-like objects found")
    # text lines (legends, indicator titles, OHLC readouts): many tiny blobs whose TOP edges share the same row.
    # Candles never share a top row in numbers; drop every row band where ≥8 blobs share top±2 and blob height ≤ 20 px
    tops = np.array([c["y"] for c in comps]); hgt = np.array([c["h"] for c in comps])
    tv, tc = np.unique(tops // 3, return_counts=True)
    wid = np.array([c["w"] for c in comps])
    H_img = mask.shape[0]
    text_rows = set(int(t_) for t_, n_ in zip(tv, tc)
                    if n_ >= 8 and t_ * 3 < 0.12 * H_img and np.median(hgt[(tops // 3) == t_]) <= 14 and np.median(wid[(tops // 3) == t_]) <= 14)
    if text_rows:
        comps = [c for c in comps if (c["y"] // 3) not in text_rows]
        if len(comps) < min_candles:
            raise ValueError("only text-like objects found")
    # ---- pane selection (Phase 12, real screenshots): split the plot into horizontal bands separated by rows with
    # (almost) no candle-like components, then keep the band that looks most like a PRICE series: many blobs, their
    # vertical centres wander (volume bars are anchored to a baseline; text sits on one row), continuous in x.
    if len(comps) >= 2 * min_candles:
        Hm = mask.shape[0]
        occ = np.zeros(Hm + 1, int)
        for c in comps:
            occ[c["y"]:c["y"] + c["h"]] += 1
        empty = occ == 0
        # gaps of ≥ 12 px with nothing → band borders
        bands, start, run = [], 0, 0
        for yy in range(Hm):
            if empty[yy]:
                run += 1
                if run == 12:
                    if yy - 11 - start >= 20:
                        bands.append((start, yy - 11))
                    start = None
            else:
                if start is None:
                    start = yy
                run = 0
        if start is not None and Hm - start >= 20:
            bands.append((start, Hm))
        if len(bands) >= 2:
            best, best_score = None, -1
            for (b0, b1) in bands:
                inb = [c for c in comps if b0 <= c["y"] + c["h"] / 2 < b1]
                if len(inb) < min_candles:
                    continue
                cy = np.array([c["y"] + c["h"] / 2 for c in inb]); bt = np.array([c["y"] + c["h"] for c in inb]); tp = np.array([c["y"] for c in inb])
                wander = float(np.std(cy)) / max(b1 - b0, 1)                    # price: centres spread over the band
                base_share = float(np.bincount(bt // 3).max()) / len(inb)       # volume: bottoms share one row
                top_share = float(np.bincount(tp // 3).max()) / len(inb)        # text: tops share one row
                score = len(inb) * (0.2 + wander) * (1 - 0.8 * max(base_share, top_share)) * ((b1 - b0) / Hm) ** 0.5
                if score > best_score:
                    best, best_score = (b0, b1), score
            if best is not None:
                comps = [c for c in comps if best[0] <= c["y"] + c["h"] / 2 < best[1]]
    # the price pane = the horizontal band holding the most components whose bottom edge is NOT aligned (volume bars
    # all share one baseline → exclude any y-bottom shared by >25% of components)
    bottoms = np.array([c["y"] + c["h"] for c in comps])
    vals, cnts = np.unique(bottoms // 3, return_counts=True)
    baseline_bins = set(vals[cnts > max(3, 0.25 * len(comps))])
    comps = [c for c in comps if ((c["y"] + c["h"]) // 3) not in baseline_bins]
    if len(comps) < min_candles:
        raise ValueError("too few candles after removing baseline-aligned bars")
    # if a volume pane was present (baseline group found), it sits below the price pane: drop components that lie
    # entirely below the highest baseline row (volume bars grow upward from it)
    if baseline_bins:
        base_row = min(baseline_bins) * 3
        comps = [c for c in comps if c["y"] + c["h"] / 2 < base_row]
        if len(comps) < min_candles:
            raise ValueError("too few candles above the volume pane")
    # keep only the price series: legend/text blobs sit far from their x-neighbours vertically. For each blob compare
    # its centre-y with the median centre-y of the blobs in the nearest 6 x-slots; price candles are continuous.
    comps.sort(key=lambda c: c["x"])
    ys = np.array([c["y"] + c["h"] / 2 for c in comps]); hs_ = np.array([c["h"] for c in comps], float)
    if len(comps) > 12:
        keep = np.ones(len(comps), bool)
        medh = float(np.median(hs_))
        for i in range(len(comps)):
            lo_i, hi_i = max(0, i - 6), min(len(comps), i + 7)
            nb = np.r_[ys[lo_i:i], ys[i + 1:hi_i]]
            if nb.size and abs(ys[i] - np.median(nb)) > max(6 * medh, 0.25 * mask.shape[0]):
                keep[i] = False
        if keep.sum() >= min_candles:
            comps = [c for c, k in zip(comps, keep) if k]
    # merge components sharing the same x-slot (body + wick can be split by anti-aliasing) → one candle per slot
    comps.sort(key=lambda c: c["x"])
    widths = np.array([c["w"] for c in comps]); med_w = float(np.median(widths))
    segs = []
    for c in comps:
        cx = c["x"] + c["w"] / 2
        if segs and abs(cx - segs[-1]["cx"]) <= max(1.0, med_w * 0.6):
            s_ = segs[-1]
            s_["x0"] = min(s_["x0"], c["x"]); s_["x1"] = max(s_["x1"], c["x"] + c["w"])
            s_["top"] = min(s_["top"], c["y"]); s_["bot"] = max(s_["bot"], c["y"] + c["h"])
        else:
            segs.append(dict(cx=cx, x0=c["x"], x1=c["x"] + c["w"], top=c["y"], bot=c["y"] + c["h"]))
    # candles form ONE regularly spaced series: estimate the pitch from the most common centre-to-centre gap, then
    # keep slots whose offset from the grid is small (allows missing candles/gaps; rejects legends, menus, text)
    if len(segs) > min_candles:
        cxs = np.array([sg["cx"] for sg in segs])
        d = np.diff(cxs); d = d[(d > 0.5) & (d < 400)]
        if d.size >= 5:
            pitch = float(np.bincount(np.round(d).astype(int)).argmax())
            pitch = max(pitch, 1.0)
            # phase: choose the offset that maximises inliers
            best_in, best_phase = None, 0.0
            for ph in np.linspace(0, pitch, 8, endpoint=False):
                off = np.abs(((cxs - ph) / pitch) - np.round((cxs - ph) / pitch)) * pitch
                inl = off <= max(1.5, 0.25 * pitch)
                if best_in is None or inl.sum() > best_in.sum():
                    best_in, best_phase = inl, ph
            if best_in is not None and best_in.sum() >= min_candles:
                # additionally trim leading/trailing isolated inliers far from the main cluster
                idx = np.where(best_in)[0]
                gaps = np.diff(cxs[idx])
                keep = np.ones(len(idx), bool)
                for i_ in range(len(idx)):
                    left = gaps[i_ - 1] if i_ > 0 else np.inf
                    right = gaps[i_] if i_ < len(gaps) else np.inf
                    if min(left, right) > 8 * pitch:
                        keep[i_] = False
                segs = [segs[i] for i in idx[keep]]
    boxes = []
    for sg in segs:
        a, b = sg["x0"], sg["x1"]
        sub = mask[sg["top"]:sg["bot"], a:b]
        if sub.size == 0:
            continue
        width_rows = sub.sum(1)
        wmax = width_rows.max()
        body_rows = np.where(width_rows >= max(2, 0.6 * wmax))[0]
        top, bot = sg["top"], sg["bot"] - 1
        if body_rows.size == 0 or wmax <= 1:
            body_top, body_bot = top, bot
        else:
            body_top, body_bot = top + int(body_rows[0]), top + int(body_rows[-1])
        # colour vote on the BODY rows first (wicks may be drawn in one shared colour, e.g. MetaTrader green wicks
        # with white/black bodies); fall back to the whole candle when the body is degenerate (doji)
        bt, bb = body_top, body_bot + 1
        nb = int(bull[bt:bb, a:b].sum()); nr = int(bear[bt:bb, a:b].sum())
        if nb + nr < 3:
            nb = int(bull[top:bot + 1, a:b].sum()); nr = int(bear[top:bot + 1, a:b].sum())
        is_bull = nb >= nr
        conf_c = abs(nb - nr) / max(nb + nr, 1)
        if body_bot > body_top + 2 and (theme == "mono" or conf_c < 0.35 or (b - a) >= 4):
            inner = mask[body_top + 1:body_bot, a + 1:b - 1] if b - a > 2 else mask[body_top + 1:body_bot, a:b]
            fill = float(inner.mean()) if inner.size else 1.0
            if theme == "mono":
                is_bull = fill < 0.5
            elif hue_gray and (b - a) >= 4:
                # MetaTrader "hue + gray": the coloured class is usually the wick/outline colour for BOTH directions;
                # a filled gray body = one direction, hollow body = the other. Filled body colour decides:
                gray_in = float(gray_fg[body_top + 1:body_bot, a + 1:b - 1].mean()) if inner.size else 0.0
                if fill < 0.35:
                    is_bull = True                       # hollow = bull (MT default: bull candles are hollow/black on dark bg)
                elif gray_in > 0.5:
                    is_bull = not dark                   # filled white body on dark bg = bear (MT default); on light bg filled black = bear too
                    is_bull = False
            elif fill < 0.35 and (b - a) >= 4:
                # hollow body: an outlined candle. Hollow = bull on MT/TradingView-hollow style; if the outline colour
                # is a clear bear hue keep the colour vote
                is_bull = True if conf_c < 0.6 else is_bull
        boxes.append(dict(x0=a + x0, x1=b + x0, top=top + y0, bot=bot + y0, body_top=body_top + y0, body_bot=body_bot + y0,
                          bull=is_bull, conf=conf_c))
    if len(boxes) < min_candles:
        raise ValueError("too few candles after geometry filtering")
    # drop outliers in width (legend blobs, text) and in height (price-axis highlights, cursor lines, clipped candles)
    ws = np.array([bx["x1"] - bx["x0"] for bx in boxes])
    hs = np.array([bx["bot"] - bx["top"] for bx in boxes], float)
    med_h = np.median(hs)
    keep = (ws <= 2.5 * np.median(ws)) & (ws >= 1) & (hs <= 6 * med_h)
    # candles touching the top/bottom border of the plot area are clipped → mark & clamp (keep body if body is inside)
    for bx in boxes:
        bx["clipped"] = bx["top"] <= y0 + 1 or bx["bot"] >= y1 - 2
    boxes = [bx for bx, k in zip(boxes, keep) if k]
    # candle spacing should be regular: remove segments that break the dominant pitch badly (toolbars, text)
    if len(boxes) > 12:
        cx = np.array([(bx["x0"] + bx["x1"]) / 2 for bx in boxes])
        pitch = np.median(np.diff(cx))
        if pitch > 0:
            keep2 = np.ones(len(boxes), bool)
            for i in range(1, len(boxes)):
                if cx[i] - cx[i - 1] < 0.45 * pitch:  # two objects in one slot → keep the taller (real candle)
                    hi_, hj_ = boxes[i]["bot"] - boxes[i]["top"], boxes[i - 1]["bot"] - boxes[i - 1]["top"]
                    j = i if hi_ < hj_ else i - 1
                    keep2[j] = False
            boxes = [bx for bx, k in zip(boxes, keep2) if k]
    # outlier handling: (a) tall wick-lines that span >3× median (crosshair, clipped candles) → clamp range to the body
    # ± median wick; (b) tiny objects at the far right (price tags) → drop; a real candle is never < 15% of median height
    hh = np.array([b["bot"] - b["top"] for b in boxes], float)
    med = float(np.median(hh))
    wick = float(np.median([max(b["body_top"] - b["top"], b["bot"] - b["body_bot"]) for b in boxes]))
    n_dropped = 0
    cleaned = []
    for i, bx in enumerate(boxes):
        h = hh[i]
        if h > max(3 * med, med + 0.12 * (y1 - y0)):
            bx = dict(bx); bx["top"] = bx["body_top"] - int(wick); bx["bot"] = bx["body_bot"] + int(wick); bx["clipped"] = True
            n_dropped += 1
        elif h < 0.15 * med and i > len(boxes) - 6:
            continue
        cleaned.append(bx)
    boxes = cleaned
    # pixel → relative price: invert y; normalise so last close = 100
    rows = []
    for bx in boxes:
        hi, lo = -bx["top"], -bx["bot"]
        bt, bb = -bx["body_top"], -bx["body_bot"]
        o, c = (bb, bt) if bx["bull"] else (bt, bb)
        rows.append((o, hi, lo, c))
    arr = np.array(rows, float)
    base = arr[-1, 3]
    arr = arr - base + 100.0 * 0 + 0.0  # keep pixel units (calibration applied later)
    idx = pd.RangeIndex(len(arr))
    df = pd.DataFrame(arr, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 0.0
    ann = img.copy()
    for bx in boxes:
        col = (90, 200, 90) if bx["bull"] else (80, 80, 230)
        cv2.rectangle(ann, (bx["x0"], bx["body_top"]), (bx["x1"], bx["body_bot"]), col, 1)
        cx = (bx["x0"] + bx["x1"]) // 2
        cv2.line(ann, (cx, bx["top"]), (cx, bx["body_top"]), col, 1)
        cv2.line(ann, (cx, bx["body_bot"]), (cx, bx["bot"]), col, 1)
    cv2.rectangle(ann, (x0, y0), (x1 - 1, y1 - 1), (200, 200, 60), 1)
    return dict(df=df, boxes=boxes, crop=(x0, y0, x1, y1), theme=("dark" if dark else "light") + " · " + theme,
                annotated=ann, image=img, dropped_clipped=n_dropped)


def calibrate(df, px_top=None, price_top=None, px_bot=None, price_bot=None, img_h=None):
    """map pixel-units (negative y) to real prices using two user-given reference levels; else keep relative units
    scaled so that the last close = 100."""
    d = df.copy()
    cols = ["open", "high", "low", "close"]
    if px_top is not None and px_bot is not None and price_top and price_bot and px_top != px_bot:
        # pixel y (down positive) → our units are -y
        a = (price_top - price_bot) / ((-px_top) - (-px_bot))
        b = price_top - a * (-px_top)
        d[cols] = a * d[cols] + b
        d.attrs["units"] = "price"
    else:
        span = d["high"].max() - d["low"].min()
        last = d["close"].iloc[-1]
        d[cols] = 100 + (d[cols] - last) / max(span, 1e-9) * 20   # ~20% total range shown, relative
        d.attrs["units"] = "relative"
    return d


# ------------------------------------------------------------------ analysis on top of the extracted series
def analyse_chart(df, lang="en"):
    """run the numeric pattern library + structure analysis on the reconstructed OHLC"""
    from core import patterns as PT
    from core import indicators as ta
    out = {}
    n = len(df)
    c = df["close"]
    # trend by regression slope of closes (normalised) + EMA ordering
    x = np.arange(n)
    slope = np.polyfit(x, c.values, 1)[0] / max(c.abs().mean(), 1e-9) * n
    ema_f = c.ewm(span=max(3, n // 8), adjust=False).mean()
    ema_s = c.ewm(span=max(5, n // 3), adjust=False).mean()
    trend = "up" if slope > 0.03 and ema_f.iloc[-1] > ema_s.iloc[-1] else ("down" if slope < -0.03 and ema_f.iloc[-1] < ema_s.iloc[-1] else "range")
    out["trend"] = trend
    out["slope_pct"] = float(slope * 100)
    # volatility: avg range / price
    rng = (df["high"] - df["low"]).mean() / max(c.abs().mean(), 1e-9) * 100
    out["avg_range_pct"] = float(rng)
    # support / resistance from pivots (cluster)
    piv_hi, piv_lo = [], []
    L = max(2, min(5, n // 10))
    for i in range(L, n - L):
        if df["high"].iloc[i] == df["high"].iloc[i - L:i + L + 1].max():
            piv_hi.append(float(df["high"].iloc[i]))
        if df["low"].iloc[i] == df["low"].iloc[i - L:i + L + 1].min():
            piv_lo.append(float(df["low"].iloc[i]))
    tol = (df["high"].max() - df["low"].min()) * 0.02
    def cluster(vals):
        vals = sorted(vals); groups = []
        for v in vals:
            if groups and abs(v - groups[-1][-1]) <= tol:
                groups[-1].append(v)
            else:
                groups.append([v])
        return sorted([(float(np.mean(g)), len(g)) for g in groups], key=lambda t: -t[1])[:3]
    out["resistance"] = cluster(piv_hi); out["support"] = cluster(piv_lo)
    # candlestick patterns (last 5 bars) and chart patterns
    try:
        cs = PT.candlesticks(df)
        recent = []
        for name, ser in cs.items():
            hits = np.where(ser.values[-5:] != 0)[0]
            for h in hits:
                recent.append((name, int(ser.values[-5:][h]), n - 5 + int(h)))
        out["candles"] = recent
    except Exception as e:
        out["candles"] = []; out["candles_err"] = str(e)
    try:
        out["chart_patterns"] = PT.chart_patterns(df, lookback=n)
    except Exception as e:
        out["chart_patterns"] = []; out["patterns_err"] = str(e)
    # simple indicators
    try:
        out["rsi"] = float(ta.rsi(c, min(14, max(3, n // 4))).iloc[-1])
    except Exception:
        out["rsi"] = float("nan")
    # last-candle anatomy (Nison vocabulary)
    o, h, l, cl = df.iloc[-1][["open", "high", "low", "close"]]
    body = abs(cl - o); full = max(h - l, 1e-9)
    out["last_candle"] = dict(bull=bool(cl >= o), body_ratio=float(body / full), upper_wick=float((h - max(o, cl)) / full),
                              lower_wick=float((min(o, cl) - l) / full))
    out["n"] = n
    return out


def describe(out, lang="en"):
    """bilingual natural-language explanation of the analysis dict"""
    fa = lang == "fa"
    T = {
        "up": ("uptrend (higher highs/lows, fast EMA above slow)", "روند صعودی (سقف/کف بالاتر، EMA سریع بالای کند)"),
        "down": ("downtrend", "روند نزولی"),
        "range": ("sideways / range", "رنج / بدون روند"),
    }
    lines = []
    lines.append((f"Detected {out['n']} candles. Trend: {T[out['trend']][0]}; regression slope {out['slope_pct']:+.1f}% over the window; "
                  f"average candle range {out['avg_range_pct']:.2f}% of price.") if not fa else
                 (f"{out['n']} کندل شناسایی شد. روند: {T[out['trend']][1]}؛ شیب رگرسیون {out['slope_pct']:+.1f}٪ در کل پنجره؛ "
                  f"میانگین دامنهٔ هر کندل {out['avg_range_pct']:.2f}٪ قیمت."))
    lc = out["last_candle"]
    kind = ("bullish" if lc["bull"] else "bearish") if not fa else ("صعودی" if lc["bull"] else "نزولی")
    if lc["body_ratio"] < 0.1:
        shape = "doji (indecision)" if not fa else "دوجی (بلاتکلیفی)"
    elif lc["lower_wick"] > 0.6:
        shape = "hammer/pin-bar shape — rejection of lower prices" if not fa else "چکش/پین‌بار — رد قیمت‌های پایین"
    elif lc["upper_wick"] > 0.6:
        shape = "shooting-star shape — rejection of higher prices" if not fa else "ستارهٔ دنباله‌دار — رد قیمت‌های بالا"
    elif lc["body_ratio"] > 0.8:
        shape = "marubozu (strong conviction)" if not fa else "ماروبوزو (اقتدار کامل)"
    else:
        shape = "normal body" if not fa else "بدنهٔ معمولی"
    lines.append((f"Last candle: {kind}, body {lc['body_ratio'] * 100:.0f}% of range, upper wick {lc['upper_wick'] * 100:.0f}%, lower wick {lc['lower_wick'] * 100:.0f}% → {shape}.")
                 if not fa else f"آخرین کندل: {kind}، بدنه {lc['body_ratio'] * 100:.0f}٪ دامنه، سایهٔ بالا {lc['upper_wick'] * 100:.0f}٪، سایهٔ پایین {lc['lower_wick'] * 100:.0f}٪ → {shape}.")
    if out.get("candles"):
        names = ", ".join(f"{nm}({'+' if s > 0 else '-'})@{i}" for nm, s, i in out["candles"][:6])
        lines.append(("Candlestick patterns in the last 5 bars (Nison): " if not fa else "الگوهای کندلی ۵ کندل آخر (نیسون): ") + names)
    else:
        lines.append("No classic candlestick pattern in the last 5 bars." if not fa else "الگوی کندلی کلاسیکی در ۵ کندل آخر نیست.")
    cp = out.get("chart_patterns") or []
    if cp:
        names = ", ".join(str(p.get("name", p)) if isinstance(p, dict) else str(p) for p in cp[:4])
        lines.append(("Chart patterns (Bulkowski): " if not fa else "الگوهای نموداری (بالکوفسکی): ") + names)
    if out.get("resistance"):
        lines.append(("Resistance clusters (touches): " if not fa else "خوشه‌های مقاومت (تعداد برخورد): ") + ", ".join(f"{v:.2f}×{k}" for v, k in out["resistance"]))
    if out.get("support"):
        lines.append(("Support clusters (touches): " if not fa else "خوشه‌های حمایت (تعداد برخورد): ") + ", ".join(f"{v:.2f}×{k}" for v, k in out["support"]))
    if out.get("rsi") == out.get("rsi"):
        lines.append((f"RSI (short) {out['rsi']:.0f}." if not fa else f"RSI کوتاه {out['rsi']:.0f}."))
    lines.append(("Prices are relative pixel units unless you calibrate two axis levels; patterns are geometric and need volume/context confirmation."
                  if not fa else "قیمت‌ها نسبی (پیکسلی) هستند مگر دو سطح محور را کالیبره کنید؛ الگوها هندسی‌اند و به تأیید حجم/زمینه نیاز دارند."))
    return "\n".join(lines)


# ------------------------------------------------------------------ optional learned detector hook (YOLO)
def yolo_detect(path, weights=None):
    weights = weights or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "models", "chart_yolo.pt")
    if not os.path.exists(weights):
        return None
    try:
        from ultralytics import YOLO  # noqa
    except Exception:
        return None
    m = YOLO(weights)
    r = m(path, verbose=False)[0]
    return [dict(name=r.names[int(b.cls)], conf=float(b.conf), xyxy=[float(v) for v in b.xyxy[0]]) for b in r.boxes]


# ------------------------------------------------------------------ synthetic data + self-test ("learning")
THEMES = {
    "tradingview_dark": dict(bg="#131722", up="#26a69a", down="#ef5350", grid="#2a2e39", fill=True),
    "tradingview_light": dict(bg="#ffffff", up="#26a69a", down="#ef5350", grid="#e0e3eb", fill=True),
    "binance": dict(bg="#181a20", up="#0ecb81", down="#f6465d", grid="#2b3139", fill=True),
    "metatrader": dict(bg="#000000", up="#00ff00", down="#ffffff", grid="#333333", fill=False),
    "classic_light": dict(bg="#fafafa", up="#2e7d32", down="#c62828", grid="#dddddd", fill=True),
}


def synthetic_chart(n=60, theme="tradingview_dark", seed=0, size=(1000, 560), with_ma=True):
    """render a random OHLC chart to a BGR array; returns (image, df)"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rng = np.random.default_rng(seed)
    th = THEMES[theme]
    r = rng.normal(0.0005, 0.012, n)
    close = 100 * np.exp(np.cumsum(r))
    open_ = np.r_[100, close[:-1]] * (1 + rng.normal(0, 0.002, n))
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
    lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
    df = pd.DataFrame(dict(open=open_, high=hi, low=lo, close=close, volume=rng.integers(1, 100, n)))
    dpi = 100
    fig = plt.figure(figsize=(size[0] / dpi, size[1] / dpi), dpi=dpi, facecolor=th["bg"])
    ax = fig.add_axes([0.02, 0.05, 0.86, 0.9]); ax.set_facecolor(th["bg"])
    ax.grid(True, color=th["grid"], linewidth=0.6)
    w = 0.6
    for i in range(n):
        col = th["up"] if close[i] >= open_[i] else th["down"]
        ax.plot([i, i], [lo[i], hi[i]], color=col, linewidth=1)
        b0, b1 = min(open_[i], close[i]), max(open_[i], close[i])
        face = col if (th["fill"] or close[i] < open_[i]) else th["bg"]
        ax.add_patch(plt.Rectangle((i - w / 2, b0), w, max(b1 - b0, 1e-3), facecolor=face, edgecolor=col, linewidth=1))
    if with_ma:
        ma = pd.Series(close).rolling(10).mean()
        ax.plot(range(n), ma, color="#f0b90b", linewidth=1.2)
    ax.set_xlim(-1, n); ax.set_ylim(lo.min() * 0.995, hi.max() * 1.005)
    ax.yaxis.tick_right()
    ax.tick_params(colors="#888888", labelsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[..., :3][..., ::-1].copy()
    plt.close(fig)
    return buf, df


# Phase 12: robustness variants — what real screenshots look like (phone photos, compressed, watermarked, tiny)
VARIANTS = ("clean", "jpeg30", "scaled60", "noise", "blur", "watermark", "phone_photo")


def degrade(img, variant, seed=0):
    """apply a realistic degradation to a BGR chart image"""
    import cv2
    rng = np.random.default_rng(seed)
    out = img.copy()
    if variant == "jpeg30":
        ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 30]); out = cv2.imdecode(buf, 1)
    elif variant == "scaled60":
        h, w = out.shape[:2]; out = cv2.resize(out, (int(w * 0.6), int(h * 0.6)), interpolation=cv2.INTER_AREA)
    elif variant == "noise":
        out = np.clip(out.astype(np.int16) + rng.normal(0, 8, out.shape).astype(np.int16), 0, 255).astype(np.uint8)
    elif variant == "blur":
        out = cv2.GaussianBlur(out, (3, 3), 0)
    elif variant == "watermark":
        h, w = out.shape[:2]
        cv2.putText(out, "TradingView", (w // 3, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (128, 128, 128), 3, cv2.LINE_AA)
        cv2.putText(out, "BTCUSDT 1H", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA)
    elif variant == "phone_photo":
        # mild perspective + brightness gradient + JPEG
        h, w = out.shape[:2]
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[w * 0.02, h * 0.03], [w * 0.98, 0], [w, h * 0.98], [0, h]])
        out = cv2.warpPerspective(out, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=(40, 40, 40))
        grad = np.linspace(0.85, 1.1, w, dtype=np.float32)[None, :, None]
        out = np.clip(out.astype(np.float32) * grad, 0, 255).astype(np.uint8)
        ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 60]); out = cv2.imdecode(buf, 1)
    return out


def self_test(themes=None, n_per=3, n_candles=60, variants=("clean",)):
    """accuracy of the extractor on synthetic charts: candle-count error, direction accuracy, close correlation.
    variants: subset of VARIANTS — robustness to compression / scaling / noise / watermark / phone photo"""
    themes = themes or list(THEMES)
    rows = []
    for th in themes:
        for s in range(n_per):
          img0, truth = synthetic_chart(n_candles, th, seed=s)
          for var in variants:
            img = degrade(img0, var, seed=s) if var != "clean" else img0
            try:
                ex = extract_candles(img)
                got = ex["df"]
                # align by x-position: map each detected candle to the nearest truth slot
                cx = np.array([(b["x0"] + b["x1"]) / 2 for b in ex["boxes"]])
                slot_w = (cx.max() - cx.min()) / max(len(cx) - 1, 1) if len(cx) > 1 else 1
                pitch = np.median(np.diff(cx)) if len(cx) > 1 else slot_w
                idx = np.round((cx - cx[-1]) / pitch).astype(int) + (len(truth) - 1)
                ok_idx = (idx >= 0) & (idx < len(truth))
                g = got[ok_idx].reset_index(drop=True); t = truth.iloc[idx[ok_idx]].reset_index(drop=True)
                m = len(g)
                dir_acc = float(((g.close >= g.open) == (t.close >= t.open)).mean())
                corr = float(np.corrcoef(g.close, t.close)[0, 1]) if m > 3 else float("nan")
                rows.append(dict(theme=th, variant=var, seed=s, truth=len(truth), found=len(got), dir_acc=dir_acc, close_corr=corr, ok=True))
            except Exception as e:
                rows.append(dict(theme=th, variant=var, seed=s, truth=len(truth), found=0, dir_acc=0.0, close_corr=float("nan"), ok=False, err=str(e)))
    return pd.DataFrame(rows)


def robustness_report(n_per=2, n_candles=60):
    """per-variant summary → data/vision_robustness.json (Health/Vision page)"""
    df = self_test(n_per=n_per, n_candles=n_candles, variants=VARIANTS)
    g = df.groupby("variant").agg(found=("found", "mean"), truth=("truth", "mean"), dir_acc=("dir_acc", "mean"), close_corr=("close_corr", "mean"), ok=("ok", "mean"))
    g["count_err_pct"] = (g["found"] - g["truth"]).abs() / g["truth"] * 100
    out = g.round(3).reset_index().to_dict("records")
    try:
        import json, os
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "vision_robustness.json")
        json.dump(out, open(p, "w"), indent=1)
    except Exception:
        pass
    return out


# real-screenshot regression set (Phase 12): tests/real_charts/*.  Expected candle counts are approximate (hand count ±15 %)
REAL_EXPECT = {
    "mt_xauusd-h1-deriv-com-limited.png": (95, "MetaTrader dark, green wicks + white/hollow bodies, grid, MACD-EA text lines"),
    "mt_usdjpy-h1-instafinance-ltd.png": (105, "MetaTrader light, black hollow/filled candles, red MA, blue PSAR dots, CCI pane"),
    "mt_eurgbp-h1-instafinance-ltd.png": (105, "MetaTrader light, same style"),
    "tradingview-candlestick-chart-screenshot-2.png": (80, "TradingView dark, clean"),
    "tradingview-candlestick-chart-screenshot-3.png": (115, "TradingView dark, drawings"),
    "tradingview-candlestick-chart-screenshot-5.png": (55, "TradingView hourly TSLA, large"),
    "tradingview-btcusd-candlestick-chart-scr-1.png": (65, "TradingView light"),
    "tradingview-btcusd-candlestick-chart-scr-3.jpg": (70, "TradingView dark JPEG"),
    "binance-app-mobile-candlestick-chart-scr-2.jpg": (68, "Binance app phone screenshot"),
    "binance-app-mobile-candlestick-chart-scr-3.jpg": (55, "Binance app phone screenshot"),
    "binance-app-mobile-candlestick-chart-scr-4.jpg": (70, "Binance app phone screenshot"),
    # known-hard (kept to measure progress, not asserted): heavy annotations / tiny price pane
    "tradingview-candlestick-chart-screenshot-1.png": (None, "SMC-annotated chart with dozens of boxes and 3 colour classes"),
    "binance-app-mobile-candlestick-chart-scr-1.jpg": (None, "phone screenshot, price pane only ~150 px tall"),
}


def real_report():
    """run the extractor on the real screenshot set → list of dict(file, expected, found, ok, note)"""
    import os, glob, json
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "real_charts")
    out = []
    for f in sorted(glob.glob(os.path.join(root, "*"))):
        name = os.path.basename(f)
        exp, note = REAL_EXPECT.get(name, (None, ""))
        try:
            ex = extract_candles(f); n = len(ex["df"]); th = ex.get("theme")
        except Exception as e:
            n, th = 0, f"ERR {e}"
        ok = None if exp is None else abs(n - exp) <= 0.2 * exp
        out.append(dict(file=name, expected=exp, found=n, ok=ok, theme=th, note=note))
    try:
        p = os.path.join(os.path.dirname(root), "..", "data", "vision_real.json")
        json.dump(out, open(os.path.normpath(p), "w"), indent=1)
    except Exception:
        pass
    return out
