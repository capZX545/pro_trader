"""generate assets/icon.png / .ico / .icns (a simple candlestick glyph) so the build never depends on external art"""
import os
from PIL import Image, ImageDraw
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets"); os.makedirs(root, exist_ok=True)
png = os.path.join(root, "icon.png")
if not os.path.exists(png):
    s = 512; im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((16, 16, s - 16, s - 16), radius=96, fill=(19, 23, 34, 255))
    for i, (o, c, lo, hi, col) in enumerate([(300, 220, 330, 200, (38, 166, 154)), (220, 330, 350, 190, (239, 83, 80)), (330, 150, 360, 120, (38, 166, 154)),
                                              (150, 250, 280, 130, (239, 83, 80)), (250, 110, 270, 90, (38, 166, 154))]):
        x = 96 + i * 80
        d.line((x, hi, x, lo), fill=col, width=10)
        d.rectangle((x - 26, min(o, c), x + 26, max(o, c)), fill=col)
    im.save(png)
im = Image.open(png)
im.save(os.path.join(root, "icon.ico"), sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
try:
    im.save(os.path.join(root, "icon.icns"))
except Exception:
    pass
print("icons ok")
