#!/usr/bin/env python3
"""NIVARA — a travel poster for a place that does not exist.

Draws a 1024x1024 PNG poster, procedurally, with the Python standard
library only (zlib + struct for the PNG encoder). No network, no
dependencies, fully deterministic: the same bytes come out every run.

Scene: a cliffside town above a sea of clouds at golden hour. The one
landmark is a slender white watchtower on the cliff edge, its windows
warm with light. The invented place's name, NIVARA, is set large across
the cloud sea in hand-designed block capitals.
"""

import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- canvas

# Sky gradient stops: (position 0..1, (r, g, b))
SKY_STOPS = [
    (0.00, (38, 20, 66)),     # deep dusk violet
    (0.30, (104, 44, 92)),    # mauve
    (0.50, (198, 96, 66)),    # burnt amber
    (0.66, (244, 164, 96)),   # golden peach
    (0.78, (255, 210, 148)),  # pale gold at the horizon
    (1.00, (255, 226, 178)),  # warm cream low down
]

CLOUD_LIGHT = (255, 222, 184)
CLOUD_MID = (244, 186, 148)
CLOUD_SHADOW = (198, 132, 118)
CLIFF = (46, 24, 58)
CLIFF_FAR = (74, 38, 76)
TOWER = (250, 238, 214)
TOWER_SHADE = (214, 186, 158)
WINDOW = (255, 196, 92)
NAME_FILL = (255, 250, 240)
NAME_OUTLINE = (40, 18, 52)


def _lerp(a, b, t):
    return int(a + (b - a) * t + 0.5)


def sky_color(y):
    t = y / (H - 1)
    for i in range(len(SKY_STOPS) - 1):
        t0, c0 = SKY_STOPS[i]
        t1, c1 = SKY_STOPS[i + 1]
        if t0 <= t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return (_lerp(c0[0], c1[0], f),
                    _lerp(c0[1], c1[1], f),
                    _lerp(c0[2], c1[2], f))
    return SKY_STOPS[-1][1]


class Canvas:
    def __init__(self):
        self.rows = [bytearray(W * 3) for _ in range(H)]

    def set(self, x, y, rgb):
        if 0 <= x < W and 0 <= y < H:
            row = self.rows[y]
            i = x * 3
            row[i] = rgb[0]
            row[i + 1] = rgb[1]
            row[i + 2] = rgb[2]

    def blend(self, x, y, rgb, alpha):
        """Alpha-blend rgb over the pixel at (x, y); alpha 0..1."""
        if 0 <= x < W and 0 <= y < H and alpha > 0.0:
            row = self.rows[y]
            i = x * 3
            a = alpha
            row[i] = int(rgb[0] * a + row[i] * (1 - a) + 0.5)
            row[i + 1] = int(rgb[1] * a + row[i + 1] * (1 - a) + 0.5)
            row[i + 2] = int(rgb[2] * a + row[i + 2] * (1 - a) + 0.5)

    def fill_sky(self):
        for y in range(H):
            c = sky_color(y)
            row = self.rows[y]
            row[0::3] = bytes([c[0]]) * W
            row[1::3] = bytes([c[1]]) * W
            row[2::3] = bytes([c[2]]) * W

    def disc(self, cx, cy, r, rgb, alpha=1.0):
        r2 = r * r
        for y in range(max(0, cy - r), min(H, cy + r + 1)):
            dy = y - cy
            dx = int((r2 - dy * dy) ** 0.5)
            for x in range(max(0, cx - dx), min(W, cx + dx + 1)):
                self.blend(x, y, rgb, alpha)

    def ellipse(self, cx, cy, rx, ry, rgb, alpha=1.0):
        for y in range(max(0, cy - ry), min(H, cy + ry + 1)):
            dy = (y - cy) / ry
            dx = int(rx * (1 - dy * dy) ** 0.5)
            for x in range(max(0, cx - dx), min(W, cx + dx + 1)):
                self.blend(x, y, rgb, alpha)

    def rect(self, x0, y0, x1, y1, rgb, alpha=1.0):
        for y in range(max(0, y0), min(H, y1 + 1)):
            for x in range(max(0, x0), min(W, x1 + 1)):
                self.blend(x, y, rgb, alpha)

    def polyfill(self, points, rgb):
        """Fill a polygon given as [(x, y), ...] via scanlines."""
        ys = [p[1] for p in points]
        for y in range(max(0, min(ys)), min(H, max(ys) + 1)):
            xs = []
            n = len(points)
            for i in range(n):
                x0, y0 = points[i]
                x1, y1 = points[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            if len(xs) >= 2:
                xs.sort()
                for x in range(max(0, int(xs[0])), min(W, int(xs[-1]) + 1)):
                    self.set(x, y, rgb)


# ---------------------------------------------------------------- letterforms

# Hand-designed 5x7 block capitals, drawn for this poster. "#" = ink.
FONT = {
    "N": [
        "#...#",
        "##..#",
        "##..#",
        "#.#.#",
        "#.#.#",
        "#..##",
        "#..##",
    ],
    "I": [
        "#####",
        "..#..",
        "..#..",
        "..#..",
        "..#..",
        "..#..",
        "#####",
    ],
    "V": [
        "#...#",
        "#...#",
        ".#.#.",
        ".#.#.",
        ".#.#.",
        "..#..",
        "..#..",
    ],
    "A": [
        ".###.",
        "#...#",
        "#...#",
        "#####",
        "#...#",
        "#...#",
        "#...#",
    ],
    "R": [
        "####.",
        "#...#",
        "#...#",
        "####.",
        "#.#..",
        "#..#.",
        "#...#",
    ],
}


def draw_text(canvas, text, cx, top, scale, fill, outline):
    """Draw text centred on cx, top edge at y=top, with an outline.

    Outline is painted first by stamping the glyphs shifted in eight
    directions, then the fill is stamped on top.
    """
    gw, gh = 5, 7
    gap = scale  # one cell of space between letters
    total = len(text) * (gw * scale + gap) - gap
    x = cx - total // 2
    # outline pass: 8 neighbours
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2),
                   (-2, -2), (2, -2), (-2, 2), (2, 2)):
        _stamp(canvas, text, x + dx, top + dy, scale, outline)
    # fill pass
    _stamp(canvas, text, x, top, scale, fill)


def _stamp(canvas, text, x0, y0, scale, rgb):
    x = x0
    for ch in text:
        glyph = FONT[ch]
        for gy, row in enumerate(glyph):
            for gx, cell in enumerate(row):
                if cell == "#":
                    canvas.rect(x + gx * scale, y0 + gy * scale,
                                x + (gx + 1) * scale - 1,
                                y0 + (gy + 1) * scale - 1, rgb)
        x += 5 * scale + scale


# ---------------------------------------------------------------- scene

def draw_poster():
    cv = Canvas()
    cv.fill_sky()

    # Sun low over the cloud sea, with a soft stepped halo.
    for r, a in [(170, 0.10), (140, 0.14), (110, 0.20), (88, 0.30)]:
        cv.disc(648, 470, r, (255, 218, 150), a)
    cv.disc(648, 470, 72, (255, 240, 205), 1.0)

    # Far ridge, hazy, behind the clouds.
    cv.polyfill([(0, 620), (120, 560), (260, 600), (420, 545),
                 (560, 595), (700, 560), (860, 600), (1024, 565),
                 (1024, 1024), (0, 1024)], CLIFF_FAR)

    # Sea of clouds: layered soft ellipses, light on top, shadow below.
    cloud_rows = [
        # (cx, cy, rx, ry, colour, alpha)
        (120, 640, 260, 70, CLOUD_LIGHT, 0.95),
        (420, 660, 320, 80, CLOUD_LIGHT, 0.95),
        (760, 650, 300, 75, CLOUD_LIGHT, 0.95),
        (980, 660, 240, 70, CLOUD_LIGHT, 0.95),
        (60, 720, 300, 90, CLOUD_MID, 0.95),
        (380, 740, 340, 95, CLOUD_MID, 0.95),
        (720, 730, 330, 90, CLOUD_MID, 0.95),
        (980, 740, 260, 85, CLOUD_MID, 0.95),
        (200, 830, 320, 100, CLOUD_LIGHT, 0.95),
        (560, 850, 360, 105, CLOUD_LIGHT, 0.95),
        (900, 840, 300, 100, CLOUD_LIGHT, 0.95),
        (40, 940, 320, 110, CLOUD_MID, 0.95),
        (420, 960, 360, 115, CLOUD_MID, 0.95),
        (800, 950, 340, 110, CLOUD_MID, 0.95),
    ]
    for cx, cy, rx, ry, col, a in cloud_rows:
        cv.ellipse(cx, cy, rx, ry, col, a)
    # Low cloud shadows to give the sea depth.
    for cx, cy, rx, ry in [(300, 700, 200, 34), (640, 690, 220, 32),
                           (880, 900, 220, 36), (180, 900, 200, 34),
                           (540, 990, 260, 40)]:
        cv.ellipse(cx, cy, rx, ry, CLOUD_SHADOW, 0.20)

    # Sunlight streak across the cloud sea.
    for i, (cx, cy, rx, ry) in enumerate([
            (648, 760, 130, 18), (648, 800, 180, 20), (648, 845, 230, 22)]):
        cv.ellipse(cx, cy, rx, ry, (255, 236, 190), 0.45 - i * 0.08)

    # Left foreground cliff, dark plum, jagged top edge.
    cv.polyfill([(0, 700), (60, 640), (130, 690), (210, 620),
                 (280, 680), (330, 650), (360, 760), (300, 1024),
                 (0, 1024)], CLIFF)
    # A few tiny lit windows along the left cliff hint at the town.
    for wx, wy in [(120, 668), (168, 690), (238, 648), (292, 676)]:
        cv.rect(wx, wy, wx + 7, wy + 9, WINDOW)
    # Right foreground cliff carrying the tower.
    cv.polyfill([(1024, 690), (960, 620), (900, 680), (830, 610),
                 (770, 660), (730, 700), (760, 1024), (1024, 1024)], CLIFF)

    # The watchtower of Nivara: slender white tower on the right cliff.
    # Tapered body, standing tall above the cliff edge.
    cv.polyfill([(812, 398), (856, 398), (848, 640), (820, 640)], TOWER)
    cv.polyfill([(838, 398), (856, 398), (848, 640), (838, 640)],
                TOWER_SHADE)
    # Gallery + pointed roof.
    cv.rect(800, 382, 868, 398, TOWER_SHADE)
    cv.polyfill([(800, 382), (868, 382), (834, 340)], (58, 28, 66))
    # Beacon light.
    cv.disc(834, 328, 26, (255, 210, 120), 0.35)
    cv.disc(834, 328, 12, (255, 226, 150), 1.0)
    # Warm windows down the tower.
    for wy in (420, 460, 500, 540, 580):
        cv.rect(828, wy, 840, wy + 18, WINDOW)

    # A few birds high over the clouds.
    for bx, by, s in [(300, 300, 14), (360, 330, 11), (250, 350, 9),
                      (520, 280, 12)]:
        cv.polyfill([(bx - s, by), (bx, by - s // 2), (bx + s, by),
                     (bx, by + s // 3)], (52, 26, 60))

    # The place name, large across the cloud sea.
    draw_text(cv, "NIVARA", 512, 742, 17, NAME_FILL, NAME_OUTLINE)

    return cv


# ---------------------------------------------------------------- PNG encoder

def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def encode_png(canvas):
    raw = bytearray()
    for row in canvas.rows:
        raw.append(0)  # filter: none
        raw += row
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    png = encode_png(draw_poster())
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    main()
