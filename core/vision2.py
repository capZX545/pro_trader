"""
Chart Vision — level 2 (Phase 11c). What YOLO / Detectron2 / OpenCV+PyTorch pipelines do for charts, ported to a
lightweight, fully-offline stack (OpenCV + scikit-learn):

  * overlays(img, ex)         → drawn trend-lines / horizontal levels (Hough) and smooth indicator curves (MAs) per hue
  * volume_pane(img, ex)      → volume bars under the price pane → fills df["volume"]
  * axis_digits(img, ex)      → OCR of the right price axis with a template k-NN (no tesseract) → auto price calibration
  * PatternDetector           → the "YOLO" part: an image classifier trained on thousands of synthetic labelled charts
                                 (HOG features + linear SVM), applied as a multi-scale sliding window over the price pane
                                 (grid proposals → class scores → non-max suppression). Weights cached in data/models/.
  * understand(path)          → one call: candles + overlays + volume + calibration + numeric patterns + image patterns

Why HOG+SVM instead of a CNN: no torch dependency, trains in ~1 minute on CPU, and chart patterns are *shape* classes,
which HOG captures well. If ultralytics is installed, core.vision.yolo_detect still runs alongside.
"""
import os
import pickle
import numpy as np
import pandas as pd

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

from core import vision as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(ROOT, "data", "models", "pattern_hog.pkl")

PATTERN_CLASSES = ["none", "uptrend", "downtrend", "range", "head_shoulders_top", "head_shoulders_bottom", "double_top",
                   "double_bottom", "triangle_asc", "triangle_desc", "triangle_sym", "wedge_rising", "wedge_falling",
                   "flag_bull", "flag_bear", "channel_up", "channel_down", "cup_handle", "rounding_bottom", "v_top", "v_bottom"]
CLASS_FA = {"none": "بدون الگو", "uptrend": "روند صعودی", "downtrend": "روند نزولی", "range": "رنج", "head_shoulders_top": "سر و شانه سقف",
            "head_shoulders_bottom": "سر و شانه کف", "double_top": "سقف دوقلو", "double_bottom": "کف دوقلو", "triangle_asc": "مثلث صعودی",
            "triangle_desc": "مثلث نزولی", "triangle_sym": "مثلث متقارن", "wedge_rising": "گوهٔ صعودی", "wedge_falling": "گوهٔ نزولی",
            "flag_bull": "پرچم صعودی", "flag_bear": "پرچم نزولی", "channel_up": "کانال صعودی", "channel_down": "کانال نزولی",
            "cup_handle": "فنجان و دسته", "rounding_bottom": "کف گرد", "v_top": "سقف V", "v_bottom": "کف V"}
CLASS_SIDE = {"uptrend": "bull", "downtrend": "bear", "head_shoulders_top": "bear", "head_shoulders_bottom": "bull", "double_top": "bear",
              "double_bottom": "bull", "triangle_asc": "bull", "triangle_desc": "bear", "wedge_rising": "bear", "wedge_falling": "bull",
              "flag_bull": "bull", "flag_bear": "bear", "channel_up": "bull", "channel_down": "bear", "cup_handle": "bull",
              "rounding_bottom": "bull", "v_top": "bear", "v_bottom": "bull"}


# =============================================================================== synthetic pattern generator
def _shape(kind, n, rng):
    """returns a 'skeleton' close path in [0,1] for the pattern class, before noise"""
    x = np.linspace(0, 1, n)
    if kind == "none":
        return np.cumsum(rng.normal(0, 1, n))
    if kind == "uptrend":
        return x * rng.uniform(2, 4) + np.sin(x * rng.uniform(6, 14)) * 0.25
    if kind == "downtrend":
        return -x * rng.uniform(2, 4) + np.sin(x * rng.uniform(6, 14)) * 0.25
    if kind == "range":
        return np.sin(x * rng.uniform(12, 25)) * 0.8
    if kind == "head_shoulders_top":
        return (np.exp(-((x - 0.2) / 0.07) ** 2) * 1.0 + np.exp(-((x - 0.5) / 0.08) ** 2) * 1.6 + np.exp(-((x - 0.8) / 0.07) ** 2) * 1.0) * rng.uniform(0.8, 1.2)
    if kind == "head_shoulders_bottom":
        return -_shape("head_shoulders_top", n, rng)
    if kind == "double_top":
        return np.exp(-((x - 0.3) / 0.09) ** 2) * 1.3 + np.exp(-((x - 0.7) / 0.09) ** 2) * 1.3 * rng.uniform(0.9, 1.05)
    if kind == "double_bottom":
        return -_shape("double_top", n, rng)
    if kind == "triangle_asc":
        return 1.0 - (1 - x) * np.abs(np.sin(x * rng.uniform(15, 25))) * 1.2
    if kind == "triangle_desc":
        return -_shape("triangle_asc", n, rng)
    if kind == "triangle_sym":
        return (1 - x) * np.sin(x * rng.uniform(15, 25)) * 1.2
    if kind == "wedge_rising":
        return x * 2.0 + (1 - x) * np.abs(np.sin(x * rng.uniform(15, 25))) * 1.0
    if kind == "wedge_falling":
        return -x * 2.0 - (1 - x) * np.abs(np.sin(x * rng.uniform(15, 25))) * 1.0
    if kind == "flag_bull":
        pole = np.clip(x / 0.35, 0, 1) * 3.0
        flag = np.where(x > 0.35, -(x - 0.35) * 1.2 + np.sin((x - 0.35) * 40) * 0.2, 0)
        return pole + flag
    if kind == "flag_bear":
        return -_shape("flag_bull", n, rng)
    if kind == "channel_up":
        return x * 2.0 + np.sin(x * rng.uniform(12, 20)) * 0.5
    if kind == "channel_down":
        return -x * 2.0 + np.sin(x * rng.uniform(12, 20)) * 0.5
    if kind == "cup_handle":
        cup = -np.sin(np.clip(x / 0.7, 0, 1) * np.pi) * 1.5
        handle = np.where(x > 0.7, -np.sin((x - 0.7) / 0.3 * np.pi) * 0.4, 0)
        return cup + handle
    if kind == "rounding_bottom":
        return -np.sin(x * np.pi) * 1.5
    if kind == "v_top":
        return -np.abs(x - 0.5) * 3
    if kind == "v_bottom":
        return np.abs(x - 0.5) * 3
    raise KeyError(kind)


def synth_pattern_df(kind, n=60, seed=0):
    rng = np.random.default_rng(seed)
    sk = _shape(kind, n, rng)
    sk = (sk - sk.mean()) / (sk.std() + 1e-9)
    # realistic: pattern amplitude vs noise ratio varies widely (real charts are noisy); 'none' = pure random walk
    noise_lvl = rng.uniform(0.15, 0.7) if kind != "none" else 1.0
    amp = rng.uniform(0.04, 0.10) if kind != "none" else 0.0
    walk = np.cumsum(rng.normal(0, 0.004 + 0.012 * noise_lvl, n)); walk -= np.linspace(0, walk[-1], n) * (0.0 if kind == "none" else 0.7)
    close = 100 * np.exp(amp * sk + walk * (1.0 if kind == "none" else 0.5))
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.002, n))
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    return pd.DataFrame(dict(open=open_, high=hi, low=lo, close=close, volume=rng.integers(1, 100, n)))


def render_df(df, theme="tradingview_dark", size=(320, 200), with_ma=False):
    """render a df with core.vision's matplotlib renderer (same look as synthetic_chart)"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    th = V.THEMES[theme]
    n = len(df); o, c, h, l = df.open.values, df.close.values, df.high.values, df.low.values
    dpi = 100
    fig = plt.figure(figsize=(size[0] / dpi, size[1] / dpi), dpi=dpi, facecolor=th["bg"])
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor(th["bg"]); ax.axis("off")
    w = 0.6
    for i in range(n):
        col = th["up"] if c[i] >= o[i] else th["down"]
        ax.plot([i, i], [l[i], h[i]], color=col, linewidth=1)
        b0, b1 = min(o[i], c[i]), max(o[i], c[i])
        face = col if (th["fill"] or c[i] < o[i]) else th["bg"]
        ax.add_patch(plt.Rectangle((i - w / 2, b0), w, max(b1 - b0, 1e-3), facecolor=face, edgecolor=col, linewidth=1))
    if with_ma:
        ax.plot(range(n), pd.Series(c).rolling(10).mean(), color="#f0b90b", linewidth=1.2)
    ax.set_xlim(-1, n); ax.set_ylim(l.min() * 0.998, h.max() * 1.002)
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[..., :3][..., ::-1].copy()
    plt.close(fig)
    return buf


# =============================================================================== HOG + SVM detector
def _hog_vec(img64, cell=8, bins=9):
    """numpy HOG (opencv-headless has no HOGDescriptor): 64×64 → 8×8 cells × 9 bins, L2-normalised 2×2 blocks + a
    coarse 8×8 intensity thumbnail (ink density), which helps distinguish flat 'range' from trending shapes."""
    g = img64.astype(np.float32) / 255.0
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]; gy[1:-1, :] = g[2:, :] - g[:-2, :]
    mag = np.hypot(gx, gy); ang = (np.degrees(np.arctan2(gy, gx)) % 180.0)
    nc = 64 // cell
    hist = np.zeros((nc, nc, bins), np.float32)
    b = (ang / (180.0 / bins)).astype(int) % bins
    for i in range(nc):
        for j in range(nc):
            sl = (slice(i * cell, (i + 1) * cell), slice(j * cell, (j + 1) * cell))
            hist[i, j] = np.bincount(b[sl].ravel(), weights=mag[sl].ravel(), minlength=bins)
    blocks = []
    for i in range(nc - 1):
        for j in range(nc - 1):
            v = hist[i:i + 2, j:j + 2].ravel()
            blocks.append(v / (np.linalg.norm(v) + 1e-6))
    thumb = cv2.resize(img64, (8, 8), interpolation=cv2.INTER_AREA).astype(np.float32).ravel() / 255.0
    return np.r_[np.concatenate(blocks), thumb]


def _prep(img_bgr):
    """chart crop → 64×64 'ink' image, theme-invariant (foreground = anything far from the background colour)"""
    bg, _ = V._background(img_bgr)
    diff = np.abs(img_bgr.astype(int) - bg[None, None, :]).sum(2)
    ink = np.clip(diff / 3.0, 0, 255).astype(np.uint8)
    return cv2.resize(ink, (64, 64), interpolation=cv2.INTER_AREA)


def features(img_bgr):
    return _hog_vec(_prep(img_bgr))


class PatternDetector:
    def __init__(self):
        self.clf = None; self.classes = PATTERN_CLASSES; self.meta = {}

    # ---- training (self-supervised from the generator; ~1 min CPU)
    def train(self, n_per_class=120, progress=None, seed=0):
        from sklearn.svm import LinearSVC
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.model_selection import train_test_split
        X, y = [], []
        themes = list(V.THEMES)
        rng = np.random.default_rng(seed)
        for ci, k in enumerate(self.classes):
            for j in range(n_per_class):
                df = synth_pattern_df(k, n=int(rng.integers(35, 90)), seed=seed * 100000 + ci * 1000 + j)
                img = render_df(df, theme=themes[j % len(themes)], with_ma=(j % 3 == 0))
                X.append(features(img)); y.append(ci)
            if progress:
                progress(int((ci + 1) / len(self.classes) * 90), f"rendering {k}")
        X = np.array(X); y = np.array(y)
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=0)
        clf = CalibratedClassifierCV(LinearSVC(C=0.5), cv=3)
        clf.fit(Xtr, ytr)
        acc = float((clf.predict(Xte) == yte).mean())
        # per-class recall for the model card
        pred = clf.predict(Xte)
        rec = {self.classes[c]: float((pred[yte == c] == c).mean()) for c in range(len(self.classes))}
        self.clf = clf; self.meta = dict(holdout_acc=acc, n_train=int(len(ytr)), n_test=int(len(yte)), recall=rec, n_per_class=n_per_class)
        if progress:
            progress(100, "done")
        return self.meta

    def save(self, path=MODEL_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(dict(clf=self.clf, classes=self.classes, meta=self.meta), f)

    @classmethod
    def load(cls, path=MODEL_PATH):
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            d = pickle.load(f)
        obj = cls(); obj.clf, obj.classes, obj.meta = d["clf"], d["classes"], d.get("meta", {})
        return obj

    @classmethod
    def get(cls, train_if_missing=True, progress=None):
        obj = cls.load()
        if obj is None and train_if_missing:
            obj = cls(); obj.train(progress=progress); obj.save()
        return obj

    # ---- inference
    def classify(self, img_bgr):
        p = self.clf.predict_proba(features(img_bgr)[None])[0]
        order = np.argsort(-p)
        return [(self.classes[i], float(p[i])) for i in order[:3]]

    def detect(self, df, boxes=None, scales=(1.0, 0.6, 0.4), stride_frac=0.25, min_conf=0.5, max_out=6):
        """YOLO-style multi-scale windows — but over the RECONSTRUCTED candles re-rendered cleanly, so the detector sees
        exactly the domain it was trained on (no toolbars, text, grids). Returns dict(i0, i1, box(px), name, conf)."""
        n = len(df)
        cands = []
        for s in scales:
            w = int(round(n * s))
            if w < 20:
                continue
            step = max(3, int(w * stride_frac))
            starts = list(range(0, max(1, n - w + 1), step))
            if starts[-1] != n - w:
                starts.append(n - w)
            for i0 in starts:
                sub = df.iloc[i0:i0 + w]
                p = self.clf.predict_proba(features(render_df(sub))[None])[0]
                ci = int(p.argmax())
                if self.classes[ci] != "none" and p[ci] >= min_conf:
                    cands.append(dict(i0=int(i0), i1=int(i0 + w - 1), name=self.classes[ci], conf=float(p[ci]), scale=s))
        cands.sort(key=lambda d: -d["conf"])
        out = []
        for c in cands:
            if all(_iou1d(c, o) <= 0.4 for o in out):
                out.append(c)
            if len(out) >= max_out:
                break
        for c in out:
            c["name_fa"] = CLASS_FA.get(c["name"], c["name"]); c["side"] = CLASS_SIDE.get(c["name"], "neutral")
            if boxes:
                bs = boxes[c["i0"]:c["i1"] + 1]
                c["box"] = (min(b["x0"] for b in bs), min(b["top"] for b in bs), max(b["x1"] for b in bs), max(b["bot"] for b in bs))
        return out


def _iou1d(a, b):
    inter = max(0, min(a["i1"], b["i1"]) - max(a["i0"], b["i0"]) + 1)
    union = (a["i1"] - a["i0"] + 1) + (b["i1"] - b["i0"] + 1) - inter
    return inter / union if union else 0.0


# =============================================================================== overlays: lines & indicator curves
def overlays(img, ex, min_len_frac=0.25):
    """Detect drawn lines (trend-lines, horizontal S/R) and smooth curves (moving averages) inside the plot area.
    Candle pixels are masked out first so only 'annotation ink' remains. Returns dict(lines=[...], curves=[...])."""
    x0, y0, x1, y1 = ex["crop"]
    if ex["boxes"]:  # limit to the price pane's vertical extent (± 8%) so axis ticks / toolbars are ignored
        ct, cb = min(b["top"] for b in ex["boxes"]), max(b["bot"] for b in ex["boxes"])
        pad = int(0.08 * (cb - ct)); y0, y1 = max(y0, ct - pad), min(y1, cb + pad)
    crop = img[y0:y1, x0:x1]
    bg, dark = V._background(img)
    diff = np.abs(crop.astype(int) - bg[None, None, :]).sum(2)
    fg = (diff > 45).astype(np.uint8)
    # mask candles (dilate their boxes a little)
    cm = np.zeros_like(fg)
    for b in ex["boxes"]:
        cv2.rectangle(cm, (b["x0"] - x0 - 1, b["top"] - y0 - 1), (b["x1"] - x0 + 1, b["bot"] - y0 + 1), 1, -1)
    rest = fg & (1 - cm)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    # ---- straight lines (Hough)
    edges = (rest * 255).astype(np.uint8)
    W = x1 - x0
    lines = []
    seg = cv2.HoughLinesP(edges, 1, np.pi / 360, threshold=40, minLineLength=int(W * min_len_frac), maxLineGap=12)
    if seg is not None:
        for s in np.asarray(seg).reshape(-1, 4):
            xa, ya, xb, yb = map(int, s)
            if xb < xa:
                xa, ya, xb, yb = xb, yb, xa, ya
            ang = np.degrees(np.arctan2(-(yb - ya), xb - xa))
            kind = "horizontal" if abs(ang) < 1.5 else ("vertical" if abs(abs(ang) - 90) < 1.5 else ("trendline_up" if ang > 0 else "trendline_down"))
            if kind == "vertical":
                continue
            # colour of the line
            ys_ = np.linspace(ya, yb, 20).astype(int); xs_ = np.linspace(xa, xb, 20).astype(int)
            hh = hsv[np.clip(ys_, 0, hsv.shape[0] - 1), np.clip(xs_, 0, hsv.shape[1] - 1)]
            lines.append(dict(kind=kind, x0=xa + x0, y0=ya + y0, x1=xb + x0, y1=yb + y0, angle=float(ang), length=float(np.hypot(xb - xa, yb - ya)),
                              hue=int(np.median(hh[:, 0])), sat=int(np.median(hh[:, 1]))))
    # merge near-duplicate lines (Hough returns many parallel fragments)
    lines.sort(key=lambda d: -d["length"])
    merged = []
    for ln in lines:
        dup = False
        for m in merged:
            if m["kind"] == ln["kind"] and abs(m["angle"] - ln["angle"]) < 2.0:
                # distance of ln midpoint from m's line
                mx, my = (ln["x0"] + ln["x1"]) / 2, (ln["y0"] + ln["y1"]) / 2
                dx, dy = m["x1"] - m["x0"], m["y1"] - m["y0"]
                dist = abs(dy * (mx - m["x0"]) - dx * (my - m["y0"])) / max(np.hypot(dx, dy), 1e-9)
                if dist < 6:
                    dup = True; break
        if not dup:
            merged.append(ln)
    lines = merged[:12]
    # ---- smooth curves: saturated ink not belonging to candle hues, grouped by hue, traced column-wise
    S, Hh, Vv = hsv[..., 1], hsv[..., 0], hsv[..., 2]
    sat = rest.astype(bool) & (S > 70) & (Vv > 70)
    curves = []
    if sat.sum() > 50:
        hist = np.bincount(Hh[sat], minlength=180).astype(float)
        hist = np.convolve(hist, np.ones(5) / 5, mode="same")
        used = np.zeros(180, bool)
        for _ in range(4):
            h_ = int(hist.argmax())
            if hist[h_] < 30:
                break
            band = V._hue_dist(Hh, h_) <= 8
            m = sat & band
            hist[max(0, h_ - 10):h_ + 10] = 0
            cols = np.where(m.any(0))[0]
            if cols.size < 0.3 * W:
                continue
            ys_ = np.full(W, np.nan)
            for cx in cols:
                yy = np.where(m[:, cx])[0]
                ys_[cx] = np.median(yy)
            s_ = pd.Series(ys_).interpolate(limit_direction="both")
            # smoothness: a moving average is smooth (small 2nd difference); text/labels are not
            d2 = np.nanmedian(np.abs(np.diff(s_.values, 2)))
            if d2 > 2.5:
                continue
            curves.append(dict(hue=h_, coverage=float(cols.size / W), y=(s_.values + y0).tolist(), smooth=float(d2)))
    return dict(lines=lines, curves=curves)


def describe_overlays(ov, ex, lang="en"):
    n = len(ex["df"]); out = []
    boxes = ex["boxes"]
    if not boxes:
        return out
    last_close_px = boxes[-1]["body_bot"] if boxes[-1]["bull"] else boxes[-1]["body_top"]
    for ln in ov["lines"]:
        if ln["kind"] == "horizontal":
            rel = "above" if ln["y0"] < last_close_px else "below"
            out.append((f"Horizontal level drawn {rel} price (y={ln['y0']})" if lang == "en" else f"سطح افقی کشیده‌شده {'بالای' if rel == 'above' else 'زیر'} قیمت (y={ln['y0']})"))
        else:
            up = ln["kind"] == "trendline_up"
            out.append((f"{'Rising' if up else 'Falling'} trend-line, {ln['angle']:+.1f}°, spanning {ln['length']:.0f}px" if lang == "en" else f"خط روند {'صعودی' if up else 'نزولی'}، {ln['angle']:+.1f}°، طول {ln['length']:.0f}px"))
    for cv_ in ov["curves"]:
        y = np.asarray(cv_["y"]); pos = "above" if y[-1] < last_close_px else "below"
        slope = "rising" if y[-1] < y[max(0, len(y) - 30)] else "falling"
        out.append((f"Indicator curve (hue {cv_['hue']}) is {slope} and price is {'above' if pos == 'below' else 'below'} it" if lang == "en" else
                    f"منحنی اندیکاتور (رنگ {cv_['hue']}) {'صعودی' if slope == 'rising' else 'نزولی'} است و قیمت {'بالای' if pos == 'below' else 'زیر'} آن قرار دارد"))
    return out


# =============================================================================== volume pane
def volume_pane(img, ex):
    """find bars below the price pane whose bottoms share one baseline; return per-candle volume (aligned by x) or None"""
    x0, y0, x1, y1 = ex["crop"]
    boxes = ex["boxes"]
    if not boxes:
        return None
    low_px = max(b["bot"] for b in boxes)
    if low_px >= img.shape[0] - 5:
        return None
    region = img[low_px + 2:, x0:x1]
    bg, _ = V._background(img)
    fg = (np.abs(region.astype(int) - bg[None, None, :]).sum(2) > 45).astype(np.uint8)
    num, lab, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
    comps = [s for s in stats[1:] if s[3] >= 2 and s[2] <= 60]
    if len(comps) < 8:
        return None
    bottoms = np.array([s[1] + s[3] for s in comps])
    vals, cnts = np.unique(bottoms // 3, return_counts=True)
    if cnts.max() < max(6, 0.4 * len(comps)):
        return None
    base = vals[cnts.argmax()]
    bars = [s for s in comps if (s[1] + s[3]) // 3 == base]
    vol = np.zeros(len(boxes))
    for i, b in enumerate(boxes):
        cx = (b["x0"] + b["x1"]) / 2 - x0
        for s in bars:
            if s[0] <= cx <= s[0] + s[2]:
                vol[i] = s[3]; break
    if (vol > 0).sum() < 0.5 * len(boxes):
        return None
    return vol


# =============================================================================== axis OCR (template k-NN)
_DIGIT_MODEL = None


def _digit_templates():
    """render 0-9 . , K M in several fonts/sizes → (X, y) for a k-NN; done once per process"""
    global _DIGIT_MODEL
    if _DIGIT_MODEL is not None:
        return _DIGIT_MODEL
    from sklearn.neighbors import KNeighborsClassifier
    chars = "0123456789.,"
    X, y = [], []
    fonts = [cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_DUPLEX, cv2.FONT_HERSHEY_PLAIN, cv2.FONT_HERSHEY_TRIPLEX]
    for ch in chars:
        for f in fonts:
            for scale in (0.5, 0.7, 0.9, 1.2):
                for th in (1, 2):
                    can = np.zeros((48, 40), np.uint8)
                    cv2.putText(can, ch, (6, 36), f, scale, 255, th, cv2.LINE_AA)
                    ys, xs = np.where(can > 60)
                    if xs.size == 0:
                        continue
                    g = can[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
                    X.append(_glyph_vec(g)); y.append(ch)
    try:
        from PIL import Image, ImageDraw, ImageFont
        import matplotlib.font_manager as fm
        for fp in list({fm.findfont("DejaVu Sans"), fm.findfont("DejaVu Sans Mono")}):
            for sz in (11, 13, 16, 20):
                font = ImageFont.truetype(fp, sz)
                for ch in chars:
                    im = Image.new("L", (40, 40), 0); ImageDraw.Draw(im).text((8, 6), ch, fill=255, font=font)
                    a = np.array(im); ys, xs = np.where(a > 60)
                    if xs.size == 0:
                        continue
                    X.append(_glyph_vec(a[ys.min():ys.max() + 1, xs.min():xs.max() + 1])); y.append(ch)
    except Exception:
        pass
    knn = KNeighborsClassifier(n_neighbors=3).fit(np.array(X), np.array(y))
    _DIGIT_MODEL = knn
    return knn


def _glyph_vec(g):
    h, w = g.shape
    aspect = w / max(h, 1)
    # '.' and ',' are tiny: encode size hints as extra features
    r = cv2.resize(g, (12, 16), interpolation=cv2.INTER_AREA).astype(float) / 255.0
    return np.r_[r.ravel(), aspect * 3, min(h, 40) / 40 * 3]


def axis_digits(img, ex, debug=False):
    """OCR the right-hand price axis without tesseract: locate the axis strip, upscale ×4, find text lines, split each
    line into glyphs (wide merged blobs are cut into equal-width digits), classify glyphs with the template k-NN, then
    keep the largest set of (y, value) pairs that lie on one straight line with negative slope (price axis)."""
    x0, y0, x1, y1 = ex["crop"]
    if ex["boxes"]:
        bx = ex["boxes"]; pitch = (bx[-1]["x1"] - bx[0]["x0"]) / max(len(bx) - 1, 1)
        ax0 = int(bx[-1]["x1"] + 2 * pitch)
    else:
        ax0 = x1
    ax0 = min(ax0, img.shape[1] - 12)
    strip = img[:, ax0:]
    bg, dark = V._background(img)
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    ink0 = (np.abs(strip.astype(int) - bg[None, None, :]).sum(2) > 60).astype(np.uint8)
    # find the text column: x-range where small components cluster (skip the highlighted tag boxes: wide & tall blobs)
    num, lab, stats, _ = cv2.connectedComponentsWithStats(ink0, connectivity=8)
    small = [s for s in stats[1:] if 4 <= s[3] <= 40 and s[2] <= 40 and s[4] >= 3]
    if len(small) < 6:
        return []
    # text column = the 60-px wide x-window holding the most small components (numbers stack vertically there;
    # toolbar icons are sparse and wider)
    xs = np.array([s[0] for s in small]); xe = np.array([s[0] + s[2] for s in small]); cxs = (xs + xe) / 2
    best, bx0 = -1, 0
    for start in range(0, strip.shape[1] - 30, 4):
        cnt = int(((cxs >= start) & (cxs < start + 60)).sum())
        if cnt > best:
            best, bx0 = cnt, start
    sel = [s for s, c in zip(small, cxs) if bx0 <= c < bx0 + 60]
    if len(sel) < 6:
        return []
    # grow the column: add components sitting on the same text rows within ±60 px (leading digits / decimals)
    rows = np.array([s[1] + s[3] / 2 for s in sel]); hm = float(np.median([s[3] for s in sel]))
    grown = [s for s in small if np.min(np.abs((s[1] + s[3] / 2) - rows)) <= hm * 0.6 and bx0 - 60 <= (s[0] + s[2] / 2) < bx0 + 120
             and abs(s[3] - hm) <= max(3, 0.5 * hm)]
    small = grown if len(grown) >= len(sel) else sel
    xs = np.array([s[0] for s in small]); xe = np.array([s[0] + s[2] for s in small])
    cx0, cx1 = int(np.percentile(xs, 5)), int(np.percentile(xe, 95)) + 2
    hmed = float(np.median([s[3] for s in small]))
    # text lines = y-bands where small comps sit
    ys = sorted(set(int(s[1] + s[3] / 2) for s in small))
    lines, cur = [], [ys[0]]
    for y in ys[1:]:
        if y - cur[-1] <= hmed * 0.8:
            cur.append(y)
        else:
            lines.append(cur); cur = [y]
    lines.append(cur)
    knn = _digit_templates()
    S = 4
    out = []
    for ln in lines:
        yc = int(np.mean(ln)); ya, yb = max(0, int(yc - hmed)), min(strip.shape[0], int(yc + hmed))
        row_c = [s for s in small if abs((s[1] + s[3] / 2) - yc) <= hmed * 0.8]
        if len(row_c) < 2:
            continue
        lx0 = max(0, min(s[0] for s in row_c) - 2); lx1 = max(s[0] + s[2] for s in row_c) + 2
        tile = gray[ya:yb, lx0:lx1]
        if tile.size == 0:
            continue
        tile = cv2.resize(tile, None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC)
        bw = (np.abs(tile.astype(int) - int(bg.mean())) > 60).astype(np.uint8)
        n2, lab2, st2, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
        comps = [s for s in st2[1:] if s[4] >= 2]
        if len([s for s in comps if s[3] >= 3 * S * 0.8]) < 2:
            continue
        # glyph height = median of tall comps; digit width ≈ 0.6 × height
        gh = float(np.median([s[3] for s in comps if s[3] >= hmed * S * 0.6])) if any(s[3] >= hmed * S * 0.6 for s in comps) else hmed * S
        dw = gh * 0.75
        glyphs = []
        for x, y, w, h, a in comps:
            if h < 0.45 * gh:                       # tiny → separator ('.' or ',')
                glyphs.append((x, "."))
                continue
            k = max(1, int(round(w / dw)))
            if k == 1:
                glyphs.append((x, bw[y:y + h, x:x + w]))
            else:                                    # merged digits: cut into k equal slices
                for j in range(k):
                    xa_, xb_ = x + int(j * w / k), x + int((j + 1) * w / k)
                    glyphs.append((xa_, bw[y:y + h, xa_:xb_]))
        glyphs.sort(key=lambda g: g[0])
        s_ = ""
        for _, g in glyphs:
            if isinstance(g, str):
                s_ += g; continue
            ys_, xs_ = np.where(g > 0)
            if xs_.size == 0:
                continue
            g = g[ys_.min():ys_.max() + 1, xs_.min():xs_.max() + 1] * 255
            if g.shape[1] <= 0.5 * g.shape[0] and g.mean() > 140:   # narrow solid bar → '1'
                s_ += "1"; continue
            pred = str(knn.predict(_glyph_vec(g)[None])[0])
            if pred in ".," and g.shape[0] >= 0.7 * gh:
                pred = "1"
            s_ += pred
        s_ = s_.replace(",", ".")
        # separators: a '.' followed by exactly 3 digits (and then more) is a thousands separator; the last one with
        # 1-2 trailing digits (or 3+ when it's the only one at the end) is the decimal point
        parts = s_.split(".")
        if len(parts) > 1:
            head = parts[0]; dec = ""
            for j, pt in enumerate(parts[1:], 1):
                if len(pt) == 3 and j < len(parts) - 1:
                    head += pt
                elif j == len(parts) - 1 and len(pt) in (1, 2):
                    dec = pt
                elif j == len(parts) - 1 and len(pt) == 5:      # "000.00" with the decimal point lost
                    head += pt[:3]; dec = pt[3:]
                else:
                    head += pt
            s_ = head + ("." + dec if dec else "")
        try:
            val = float(s_)
        except ValueError:
            continue
        if debug:
            print(yc, s_)
        out.append((float(yc), val))
    # RANSAC on a line with negative slope; ticks on TradingView-style axes are evenly spaced so residuals are tiny
    best = []
    if len(out) >= 3:
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                (ya_, va), (yb_, vb) = out[i], out[j]
                if yb_ == ya_ or vb == va:
                    continue
                k = (vb - va) / (yb_ - ya_)
                if k >= 0:
                    continue
                inl = [(yy, vv) for yy, vv in out if abs((va + k * (yy - ya_)) - vv) <= 0.01 * abs(vv) + 1e-9]
                if len(inl) > len(best):
                    best = inl
    return best if len(best) >= 3 else []


def auto_calibrate(df, ticks, boxes=None):
    """fit price = a + b*(-y_pixel) from OCR ticks; rebuild OHLC from the absolute pixel rows of the candle boxes"""
    if len(ticks) < 2:
        return df, None
    ys = np.array([t[0] for t in ticks]); vs = np.array([t[1] for t in ticks])
    b, a = np.polyfit(-ys, vs, 1)
    f = lambda y: a + b * (-np.asarray(y, float))
    out = df.copy()
    if boxes and len(boxes) == len(df):
        out["high"] = f([bx["top"] for bx in boxes]); out["low"] = f([bx["bot"] for bx in boxes])
        bt = f([bx["body_top"] for bx in boxes]); bb = f([bx["body_bot"] for bx in boxes])
        bull = np.array([bx["bull"] for bx in boxes])
        out["open"] = np.where(bull, bb, bt); out["close"] = np.where(bull, bt, bb)
    else:  # df is in relative pixel units (last close = 0) — only the scale can be applied
        for c in ("open", "high", "low", "close"):
            out[c] = df[c] * b
    resid = float(np.abs(f(ys) - vs).max() / max(np.abs(vs).mean(), 1e-9))
    return out, dict(a=float(a), b=float(b), n_ticks=int(len(ticks)), max_resid_pct=resid * 100)


# =============================================================================== one-call understanding
def understand(path, lang="en", detector=None, train_if_missing=True, progress=None):
    """full pipeline: candles → overlays → volume → OCR calibration → numeric analysis → image-pattern detection"""
    ex = V.extract_candles(path)
    img = ex["image"]
    df = ex["df"].copy()
    vol = volume_pane(img, ex)
    if vol is not None:
        df["volume"] = vol
    ticks = []
    cal = None
    try:
        ticks = axis_digits(img, ex)
        if len(ticks) >= 2:
            df, cal = auto_calibrate(df, ticks, ex["boxes"])
    except Exception:
        pass
    ov = overlays(img, ex)
    num = V.analyse_chart(df, lang=lang)
    det = detector or (PatternDetector.get(train_if_missing=train_if_missing, progress=progress))
    img_pats = det.detect(df, boxes=ex["boxes"]) if det is not None else []
    whole = det.classify(render_df(df)) if det is not None else []
    ann = ex["annotated"].copy()
    for ln in ov["lines"]:
        cv2.line(ann, (ln["x0"], ln["y0"]), (ln["x1"], ln["y1"]), (0, 220, 255), 2)
    for cv_ in ov["curves"]:
        pts = np.array([(ex["crop"][0] + i, int(y)) for i, y in enumerate(cv_["y"]) if np.isfinite(y)], np.int32)
        if len(pts) > 2:
            cv2.polylines(ann, [pts], False, (255, 200, 0), 1)
    for p in img_pats:
        bx = p["box"]; cv2.rectangle(ann, (bx[0], bx[1]), (bx[2], bx[3]), (255, 120, 255), 2)
        cv2.putText(ann, f"{p['name']} {p['conf']:.2f}", (bx[0] + 3, bx[1] + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 120, 255), 1, cv2.LINE_AA)
    return dict(ex=ex, df=df, volume=vol is not None, ticks=ticks, calibration=cal, overlays=ov, overlay_text=describe_overlays(ov, ex, lang),
                numeric=num, image_patterns=img_pats, whole_chart=whole, annotated=ann, detector_meta=(det.meta if det is not None else {}))
