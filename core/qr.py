"""Tiny dependency-free QR encoder (byte mode, EC level L, versions 1–10) — enough for a LAN URL. Returns a 0/1 matrix.
Based on the ISO 18004 algorithm (Reed-Solomon over GF(256), mask evaluation)."""
# ---- GF(256)
_EXP = [0] * 512; _LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x; _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _rs_gen(n):
    g = [1]
    for i in range(n):
        g = _poly_mul(g, [1, _EXP[i]])
    return g


def _poly_mul(a, b):
    r = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            if x and y:
                r[i + j] ^= _EXP[_LOG[x] + _LOG[y]]
    return r


def _rs_encode(data, n_ec):
    gen = _rs_gen(n_ec)
    res = list(data) + [0] * n_ec
    for i in range(len(data)):
        c = res[i]
        if c:
            for j in range(1, len(gen)):
                res[i + j] ^= _EXP[_LOG[gen[j]] + _LOG[c]]
    return res[len(data):]


# version → (total codewords, ec codewords per block, blocks) for level L
_VER = {1: (26, 7, 1), 2: (44, 10, 1), 3: (70, 15, 1), 4: (100, 20, 1), 5: (134, 26, 1), 6: (172, 18, 2), 7: (196, 20, 2), 8: (242, 24, 2),
        9: (292, 30, 2), 10: (346, 18, 4)}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}


def _bits(data):
    bits = []
    for v in range(1, 11):
        total, ecpb, blocks = _VER[v]
        cap = total - ecpb * blocks
        lbits = 8 if v < 10 else 16
        if 4 + lbits + 8 * len(data) <= cap * 8:
            ver = v; break
    else:
        raise ValueError("data too long for QR v10")
    def put(val, n):
        for i in range(n - 1, -1, -1):
            bits.append((val >> i) & 1)
    put(4, 4); put(len(data), lbits)
    for b in data:
        put(b, 8)
    total, ecpb, blocks = _VER[ver]; cap = total - ecpb * blocks
    put(0, min(4, cap * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    pads = [0xEC, 0x11]; k = 0
    while len(bits) < cap * 8:
        put(pads[k % 2], 8); k += 1
    cw = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    # split blocks (level L: all blocks same size except v10 which has 2+2 with sizes 68/69 — handle generic)
    n_short = blocks - (cap % blocks); short = cap // blocks
    dblocks = []; pos = 0
    for b in range(blocks):
        sz = short + (0 if b < n_short else 1)
        dblocks.append(cw[pos:pos + sz]); pos += sz
    eblocks = [_rs_encode(d, ecpb) for d in dblocks]
    out = []
    for i in range(max(len(d) for d in dblocks)):
        for d in dblocks:
            if i < len(d):
                out.append(d[i])
    for i in range(ecpb):
        for e in eblocks:
            out.append(e[i])
    ob = []
    for c in out:
        for i in range(7, -1, -1):
            ob.append((c >> i) & 1)
    return ver, ob


def matrix(text):
    data = text.encode("utf-8")
    ver, bits = _bits(data)
    n = 17 + 4 * ver
    M = [[None] * n for _ in range(n)]
    def finder(r, c):
        for i in range(-1, 8):
            for j in range(-1, 8):
                rr, cc = r + i, c + j
                if 0 <= rr < n and 0 <= cc < n:
                    M[rr][cc] = 1 if (0 <= i <= 6 and j in (0, 6)) or (0 <= j <= 6 and i in (0, 6)) or (2 <= i <= 4 and 2 <= j <= 4) else 0
    finder(0, 0); finder(0, n - 7); finder(n - 7, 0)
    for a in _ALIGN[ver]:
        for b in _ALIGN[ver]:
            if M[a][b] is None:
                for i in range(-2, 3):
                    for j in range(-2, 3):
                        M[a + i][b + j] = 1 if max(abs(i), abs(j)) != 1 else 0
    for i in range(8, n - 8):
        M[6][i] = M[i][6] = 1 - (i % 2)
    M[n - 8][8] = 1
    # reserve format areas
    for i in range(9):
        for (r, c) in ((8, i), (i, 8)):
            if M[r][c] is None:
                M[r][c] = 0
    for i in range(8):
        if M[8][n - 1 - i] is None: M[8][n - 1 - i] = 0
        if M[n - 1 - i][8] is None: M[n - 1 - i][8] = 0
    if ver >= 7:
        vinfo = {7: 0x07C94, 8: 0x085BC, 9: 0x09A99, 10: 0x0A4D3}[ver]
        for i in range(18):
            b = (vinfo >> i) & 1
            M[i // 3][n - 11 + i % 3] = b; M[n - 11 + i % 3][i // 3] = b
    # data placement
    fixed = [[M[r][c] is not None for c in range(n)] for r in range(n)]
    k = 0; col = n - 1; up = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(n - 1, -1, -1) if up else range(n)
        for r in rows:
            for c in (col, col - 1):
                if M[r][c] is None:
                    M[r][c] = bits[k] if k < len(bits) else 0; k += 1
        col -= 2; up = not up
    # masks
    masks = [lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0, lambda r, c: c % 3 == 0, lambda r, c: (r + c) % 3 == 0,
             lambda r, c: (r // 2 + c // 3) % 2 == 0, lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
             lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0, lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0]
    best = None
    for mi, mf in enumerate(masks):
        G = [[M[r][c] ^ (1 if (not fixed[r][c] and mf(r, c)) else 0) for c in range(n)] for r in range(n)]
        _format(G, mi, n)
        pen = _penalty(G, n)
        if best is None or pen < best[0]:
            best = (pen, G)
    return best[1]


def _format(G, mask, n):
    fmt = (1 << 3) | mask            # level L = 01
    v = fmt << 10
    g = 0x537
    for i in range(14, 9, -1):
        if v & (1 << i):
            v ^= g << (i - 10)
    bits = ((fmt << 10) | v) ^ 0x5412
    for i in range(15):
        b = (bits >> i) & 1
        # vertical strip (column 8)
        if i < 6: G[i][8] = b
        elif i < 8: G[i + 1][8] = b
        else: G[n - 15 + i][8] = b
        # horizontal strip (row 8)
        if i < 8: G[8][n - 1 - i] = b
        elif i < 9: G[8][15 - i] = b
        else: G[8][14 - i] = b


def _penalty(G, n):
    p = 0
    for lines in (G, list(map(list, zip(*G)))):
        for row in lines:
            run = 1
            for i in range(1, n):
                if row[i] == row[i - 1]:
                    run += 1
                else:
                    if run >= 5: p += run - 2
                    run = 1
            if run >= 5: p += run - 2
    for r in range(n - 1):
        for c in range(n - 1):
            if G[r][c] == G[r][c + 1] == G[r + 1][c] == G[r + 1][c + 1]:
                p += 3
    dark = sum(map(sum, G)); k = abs(dark * 100 // (n * n) - 50) // 5
    return p + k * 10


def qr_pixmap(text, size=132):
    from PyQt6 import QtGui, QtCore
    M = matrix(text); n = len(M); q = 2
    img = QtGui.QImage(n + 2 * q, n + 2 * q, QtGui.QImage.Format.Format_RGB32); img.fill(0xFFFFFF)
    for r in range(n):
        for c in range(n):
            if M[r][c]:
                img.setPixel(c + q, r + q, 0x000000)
    return QtGui.QPixmap.fromImage(img.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.FastTransformation))


def svg(text, scale=4):
    M = matrix(text); n = len(M)
    rects = "".join(f'<rect x="{(c + 2) * scale}" y="{(r + 2) * scale}" width="{scale}" height="{scale}"/>' for r in range(n) for c in range(n) if M[r][c])
    s = (n + 4) * scale
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}" width="{s}" height="{s}"><rect width="{s}" height="{s}" fill="#fff"/><g fill="#000">{rects}</g></svg>'
