#!/usr/bin/env python3
"""gerber_view.py : rasterise KiCad Gerber layers (no external Gerber tool needed; Pillow only).

  python3 gerber_view.py DIR x0 y0 w h out.png [--px N] [--bottom] [--layers Edge_Cuts,B_Cu,B_Mask,B_Silkscreen]
                         [--rings "x,y;x,y;..."]   (yellow rings drawn around these board points, to find small marks)

Coordinates are board mm (KiCad y down); the Gerbers must be plotted with an absolute origin (as export.py does).
--bottom mirrors the image left/right, i.e. shows the board as seen from the bottom side, the way the bottom-side
silkscreen is read on the real board and in the fab's bottom preview.  Text on B.SilkS must read normally in that
view.  Colours: board green, copper (B.Cu) bronze, mask openings drawn as lighter copper, silkscreen white.
"""
import math
import os
import re
import sys
from PIL import Image, ImageDraw, ImageFont

ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
OPTS = sys.argv[1:]


def opt(name, default):
    if name in OPTS:
        return OPTS[OPTS.index(name) + 1]
    return default


DIR = ARGS[0]
X0, Y0, W, H = map(float, ARGS[1:5])
OUT = ARGS[5]
PX = float(opt('--px', 40))                      # pixels per mm
BOTTOM = '--bottom' in OPTS
LAYERS = opt('--layers', 'Edge_Cuts,B_Cu,B_Mask,B_Silkscreen').split(',')
SIZE = (int(W * PX), int(H * PX))


def to_px(x, y):
    """Gerber (mm, y up) -> image pixel"""
    bx, by = x, -y
    u = (bx - X0) * PX
    if BOTTOM:
        u = SIZE[0] - u
    return (u, (by - Y0) * PX)


def ev(expr, var):
    expr = expr.replace('x', '*').replace('X', '*')
    expr = re.sub(r'\$(\d+)', lambda m: repr(var.get(int(m.group(1)), 0.0)), expr)
    return float(eval(expr, {}, {}))


class Layer:
    def __init__(self):
        self.img = Image.new('L', SIZE, 0)
        self.d = ImageDraw.Draw(self.img)
        self.dark = True

    def col(self):
        return 255 if self.dark else 0

    def disc(self, x, y, dia):
        u, v = to_px(x, y)
        r = max(dia * PX / 2, 0.5)
        self.d.ellipse([u - r, v - r, u + r, v + r], fill=self.col())

    def poly(self, pts):
        if len(pts) >= 3:
            self.d.polygon([to_px(*p) for p in pts], fill=self.col())

    def seg(self, a, b, dia):
        if dia <= 0:
            return
        (x1, y1), (x2, y2) = a, b
        L = math.hypot(x2 - x1, y2 - y1)
        if L > 0:
            nx, ny = -(y2 - y1) / L * dia / 2, (x2 - x1) / L * dia / 2
            self.poly([(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)])
        self.disc(x1, y1, dia)
        self.disc(x2, y2, dia)


def arc_pts(a, b, c, cw):
    (x1, y1), (x2, y2), (cx, cy) = a, b, c
    r = math.hypot(x1 - cx, y1 - cy)
    t1, t2 = math.atan2(y1 - cy, x1 - cx), math.atan2(y2 - cy, x2 - cx)
    if cw:
        while t2 >= t1:
            t2 -= 2 * math.pi
    else:
        while t2 <= t1:
            t2 += 2 * math.pi
    if abs(x1 - x2) < 1e-9 and abs(y1 - y2) < 1e-9:
        t2 = t1 + (-2 * math.pi if cw else 2 * math.pi)
    n = max(8, int(abs(t2 - t1) * r * PX / 2))
    return [(cx + r * math.cos(t1 + (t2 - t1) * i / n), cy + r * math.sin(t1 + (t2 - t1) * i / n)) for i in range(1, n + 1)]


def render(path):
    s = open(path).read()
    lay = Layer()
    fs = 6
    macros, aps = {}, {}
    cur = None
    x = y = 0.0
    mode = 'G01'
    region = None
    for m in re.finditer(r'%(.*?)%|([^%*]*)\*', s, re.S):
        if m.group(1) is not None:
            blk = m.group(1).strip()
            if blk.startswith('FS'):
                fs = int(re.search(r'X\d(\d)', blk).group(1))
            elif blk.startswith('AM'):
                parts = [p.strip() for p in blk[2:].split('*') if p.strip()]
                macros[parts[0]] = [p for p in parts[1:] if not p.startswith('0 ')]
            elif blk.startswith('ADD'):
                mm_ = re.match(r'ADD(\d+)([A-Za-z_]+),?([^*]*)', blk)
                aps[int(mm_.group(1))] = (mm_.group(2), [float(v) for v in mm_.group(3).split('X') if v])
            elif blk.startswith('LP'):
                lay.dark = blk[2] == 'D'
            continue
        cmd = m.group(2).strip()
        if not cmd or cmd.startswith('G04'):
            continue
        if cmd in ('G01', 'G02', 'G03'):
            mode = cmd
            continue
        if cmd == 'G75':
            continue
        if cmd == 'G36':
            region = []
            continue
        if cmd == 'G37':
            lay.poly(region)
            region = None
            continue
        dm = re.match(r'^(G0[123])?(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?D0?([123]|\d\d+)$', cmd)
        if not dm:
            continue
        if dm.group(1):
            mode = dm.group(1)
        d = int(dm.group(6))
        if d >= 10:
            cur = d
            continue
        nx = int(dm.group(2)) / 10 ** fs if dm.group(2) else x
        ny = int(dm.group(3)) / 10 ** fs if dm.group(3) else y
        if d == 1:
            if mode == 'G01':
                pts = [(nx, ny)]
            else:
                ci = int(dm.group(4) or 0) / 10 ** fs
                cj = int(dm.group(5) or 0) / 10 ** fs
                pts = arc_pts((x, y), (nx, ny), (x + ci, y + cj), mode == 'G02')
            if region is not None:
                if not region:
                    region.append((x, y))
                region.extend(pts)
            else:
                t, p = aps[cur]
                dia = p[0] if t == 'C' else 0.0
                prev = (x, y)
                for q in pts:
                    lay.seg(prev, q, dia)
                    prev = q
        elif d == 2:
            if region is not None and region:
                lay.poly(region)
                region = []
        elif d == 3:
            flash(lay, aps[cur], macros, nx, ny)
        x, y = nx, ny
    return lay.img


def flash(lay, ap, macros, x, y):
    t, p = ap
    if t == 'C':
        lay.disc(x, y, p[0])
    elif t == 'R':
        w, h = p[0] / 2, p[1] / 2
        lay.poly([(x - w, y - h), (x + w, y - h), (x + w, y + h), (x - w, y + h)])
    elif t == 'O':
        w, h = p[0], p[1]
        if w > h:
            lay.seg((x - (w - h) / 2, y), (x + (w - h) / 2, y), h)
        else:
            lay.seg((x, y - (h - w) / 2), (x, y + (h - w) / 2), w)
    elif t in macros:
        var = {i + 1: v for i, v in enumerate(p)}
        for prim in macros[t]:
            f = [ev(v, var) for v in prim.split(',')]
            code = int(f[0])
            if code == 1:
                lay.disc(x + f[3], y + f[4], f[2])
            elif code == 4:
                n = int(f[2])
                lay.poly([(x + f[3 + 2 * i], y + f[4 + 2 * i]) for i in range(n + 1)])
            elif code == 20:
                (a, b), (c, e) = (f[3], f[4]), (f[5], f[6])
                L = math.hypot(c - a, e - b)
                if L:
                    nx_, ny_ = -(e - b) / L * f[2] / 2, (c - a) / L * f[2] / 2
                    lay.poly([(x + a + nx_, y + b + ny_), (x + c + nx_, y + e + ny_), (x + c - nx_, y + e - ny_), (x + a - nx_, y + b - ny_)])
            elif code == 21:
                w, h, cx, cy, rot = f[2], f[3], f[4], f[5], math.radians(f[6])
                pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
                lay.poly([(x + cx + u * math.cos(rot) - v * math.sin(rot), y + cy + u * math.sin(rot) + v * math.cos(rot)) for u, v in pts])


def find(layer):
    for n in os.listdir(DIR):
        if layer in n and not n.endswith('.gbrjob'):
            return os.path.join(DIR, n)
    raise SystemExit('no Gerber for ' + layer)


COLOURS = {'B_Cu': (184, 115, 51), 'F_Cu': (184, 115, 51), 'B_Mask': (222, 190, 120), 'F_Mask': (222, 190, 120),
           'B_Silkscreen': (255, 255, 255), 'F_Silkscreen': (255, 255, 255), 'Edge_Cuts': (240, 220, 0)}
base = Image.new('RGB', SIZE, (20, 80, 45))
for L in LAYERS:
    mask = render(find(L))
    col = COLOURS.get(L, (255, 0, 255))
    if L.endswith('_Cu'):
        col = (40, 110, 60)          # copper under mask: slightly lighter green, as on a real board
    base.paste(Image.new('RGB', SIZE, col), (0, 0), mask)
draw = ImageDraw.Draw(base)
for xy in filter(None, opt('--rings', '').split(';')):
    rx, ry = map(float, xy.split(','))
    u, v = to_px(rx, -ry)
    R = max(2.2 * PX, 14)
    for k in range(3):
        draw.ellipse([u - R - k, v - R - k, u + R + k, v + R + k], outline=(255, 220, 0))
try:
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
except OSError:
    font = ImageFont.load_default()
step = 1 if W <= 40 else (5 if W <= 160 else 10)
for i in range(int(math.ceil(X0 / step)), int((X0 + W) / step) + 1):
    u = (i * step - X0) * PX
    if BOTTOM:
        u = SIZE[0] - u
    draw.line([(u, 0), (u, 6)], fill=(200, 200, 200))
    draw.text((u + 2, 6), f'{i * step:g}', fill=(200, 200, 200), font=font)
for j in range(int(math.ceil(Y0 / step)), int((Y0 + H) / step) + 1):
    v = (j * step - Y0) * PX
    draw.line([(0, v), (6, v)], fill=(200, 200, 200))
    draw.text((8, v + 2), f'{j * step:g}', fill=(200, 200, 200), font=font)
draw.text((SIZE[0] - 330, SIZE[1] - 22), 'view from BOTTOM (mirrored x)' if BOTTOM else 'view from TOP (x as in KiCad)',
          fill=(255, 255, 0), font=font)
base.save(OUT)
print('wrote', OUT, SIZE)
