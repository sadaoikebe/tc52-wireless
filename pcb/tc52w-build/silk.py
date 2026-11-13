"""Orientation marks on B.SilkS for every part whose orientation matters (all parts are on the back).

Why: JLCPCB's reading of bottom-side CPL angles is not settled in public documents (docs/tc52w-rotation-audit/,
~/tc52w-ordercheck-report.md), so the last checks are the order preview and the fab engineer's eye.  The library
footprints only carry a 0.6 mm triangle (ICs), a thin bracket (SOD-882D) or nothing (SW1); some of those are
clipped by the solder-mask opening of a neighbour.  This adds a filled dot (0.8 mm, 0.6 mm where 0.8 mm does not
fit) beside pin 1 / the cathode, and a larger "+" / "-" at the battery connector, each placed by a search:

  * clear of every B.Mask opening by 0.2 mm, so the mark is not clipped when the Gerber is plotted with the
    mask subtracted and does not touch a pad;
  * clear of the existing silkscreen (and of marks already placed) by 0.15 mm, of the board edge by 0.4 mm;
  * outside the body (B.Fab outline) of every part, its own included, so that it is still visible after assembly;
  * within 1.2 mm of the pad it marks;
  * the nearest pad of the whole board to the mark is the pin it marks, so it cannot be read as belonging to a
    neighbour or to another pin of the same part.

Only silkscreen is added; nothing else on the board is touched.  run() returns the list of marks for the log.
"""
import math
import pcbnew
from brd import MM, mm, V

ERR = MM(0.005)
MASK_CLR, SILK_CLR, EDGE_CLR = 0.2, 0.15, 0.4
SEARCH = 1.2                                    # mm from the pad edge, at most
STEP = 0.05

# (ref, pad, kind, why) -- kind: dot / plus / minus / end.  'end' is a dot for a two-pad part packed among others
# (the SOD-882D ESD diodes beside J1): it must lie beyond the marked pad's centre, seen along the line from the other
# pad (so it is at the cathode end, not beside the body), and the marked pad must be nearer than any other pad of
# the board by 0.2 mm (0.05 mm for the other kinds).  A strict on-axis spot does not exist for any of the three
# (the pair D89/D90 face each other cathode to cathode, D91's axis runs into D90's anode).
MARKS = [
    ('Q1', '1', 'dot', 'CPL +180 correction'),
    ('U6', '1', 'dot', 'CPL +180 correction'),
    ('U7', '1', 'dot', 'CPL +90 correction'),
    ('U8', '1', 'dot', 'CPL +90 correction'),
    ('D89', '1', 'end', 'cathode (pad 1)'),
    ('D90', '1', 'end', 'cathode (pad 1)'),
    ('D91', '1', 'end', 'cathode (pad 1)'),
    ('J1', 'A1', 'dot', 'pin A1'),
    ('J3', '1', 'plus', 'pin 1 = BAT+'),
    ('J3', '2', 'minus', 'pin 2 = GND'),
    ('SW1', '1', 'dot', 'pin-1 pair (90 deg would short the switch)'),
    ('U5', '1', 'dot', 'pin 1'),
    ('U9', '1', 'dot', 'pin 1'),
]


def poly_of(item, layer):
    p = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(p, layer, 0, ERR, pcbnew.ERROR_OUTSIDE)
    return p


def grown(p, d):
    q = pcbnew.SHAPE_POLY_SET(p)
    q.Inflate(MM(d), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    return q


def hits(a, b):
    if a.OutlineCount() == 0 or b.OutlineCount() == 0:
        return False
    q = pcbnew.SHAPE_POLY_SET(a)
    q.BooleanIntersection(b)
    return q.OutlineCount() > 0


def make(b, kind, x, y, r):
    if kind == 'dot':
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_CIRCLE)
        s.SetLayer(pcbnew.B_SilkS)
        s.SetFilled(True)
        s.SetWidth(MM(0.1))
        s.SetStart(V(x, y))
        s.SetEnd(V(x + r - 0.05, y))
        return s
    t = pcbnew.PCB_TEXT(b)
    t.SetText('+' if kind == 'plus' else '-')
    t.SetLayer(pcbnew.B_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(1.5), MM(1.5)))
    t.SetTextThickness(MM(0.25))
    t.SetMirrored(True)                          # back side: reads correctly when the board is seen from below
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    t.SetPosition(V(x, y))
    return t


class Obstacles:
    def __init__(self, b):
        self.b = b
        self.mask = pcbnew.SHAPE_POLY_SET()
        self.pads = []                           # (footprint ref, pad number, polygon)
        self.silk = pcbnew.SHAPE_POLY_SET()
        self.court = {}
        b.BuildCourtyardCaches() if hasattr(b, "BuildCourtyardCaches") else None
        self.body = {}
        for f in b.GetFootprints():
            ref = f.GetReference()
            for p in f.Pads():
                if p.IsOnLayer(pcbnew.B_Mask):
                    pp = poly_of(p, pcbnew.B_Mask)
                    self.mask.Append(pp)
                    self.pads.append((ref, p.GetNumber(), pp))
            for g in f.GraphicalItems():
                if g.GetLayer() == pcbnew.B_SilkS:
                    self.silk.Append(poly_of(g, pcbnew.B_SilkS))
                if g.GetLayer() == pcbnew.B_Mask:
                    self.mask.Append(poly_of(g, pcbnew.B_Mask))
            for t in f.GetFields():
                if t.IsVisible() and t.GetLayer() == pcbnew.B_SilkS:
                    self.silk.Append(poly_of(t, pcbnew.B_SilkS))
            if f.GetLayer() == pcbnew.B_Cu:
                c = f.GetCourtyard(pcbnew.B_CrtYd)
                self.court[ref] = pcbnew.SHAPE_POLY_SET(c)
                fab = [g for g in f.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetClass() == 'PCB_SHAPE']
                if fab:
                    bb = fab[0].GetBoundingBox()
                    for g in fab[1:]:
                        bb.Merge(g.GetBoundingBox())
                    q = pcbnew.SHAPE_POLY_SET()
                    q.NewOutline()
                    for x_, y_ in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()), (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
                        q.Append(x_, y_)
                    self.body[ref] = q
        for d in b.GetDrawings():
            if d.GetLayer() == pcbnew.B_SilkS:
                self.silk.Append(poly_of(d, pcbnew.B_SilkS))
            if d.GetLayer() == pcbnew.B_Mask:
                self.mask.Append(poly_of(d, pcbnew.B_Mask))
        self.edge = pcbnew.SHAPE_POLY_SET()
        b.GetBoardPolygonOutlines(self.edge, False)
        self.silk.Simplify()
        self.mask.Simplify()

    def local(self, ps, x, y, rad=SEARCH + 3):
        """the part of a poly set near (x, y) (keeps the boolean tests fast)"""
        box = pcbnew.SHAPE_POLY_SET()
        box.NewOutline()
        for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            box.Append(MM(x + dx * rad), MM(y + dy * rad))
        q = pcbnew.SHAPE_POLY_SET(ps)
        q.BooleanIntersection(box)
        return q


def pad_dist(pp, x, y):
    return math.sqrt(pp.SquaredDistance(V(x, y), False)) / 1e6


def place(b, ob, ref, pad, kind):
    axis = kind == 'end'
    kind = 'dot' if axis else kind
    margin = 0.2 if axis else 0.05
    f = b.FindFootprintByReference(ref)
    tp = [p for p in f.Pads() if p.GetNumber() == pad][0]
    px, py = mm(tp.GetPosition().x), mm(tp.GetPosition().y)
    mask = ob.local(ob.mask, px, py)
    silk = ob.local(ob.silk, px, py)
    pads = [(r, n, pp) for r, n, pp in ob.pads if pad_dist(pp, px, py) < SEARCH + 3]
    # the pad(s) with this number, plus any pad of the same part stacked on the same spot (J1: A1 and B12 share one land)
    tpos = [(mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in f.Pads() if p.GetNumber() == pad]
    same = {p.GetNumber() for p in f.Pads() if any(math.hypot(mm(p.GetPosition().x) - a, mm(p.GetPosition().y) - c) < 0.01 for a, c in tpos)}
    target = [pp for r, n, pp in pads if r == ref and n in same]
    bodies = [q for q in ob.body.values() if pad_dist(q, px, py) < SEARCH + 3]
    sizes = (0.4, 0.3) if kind == 'dot' else (None,)
    for r in sizes:
        best = None
        bb = tp.GetBoundingBox()                 # grid over the pad's box grown by SEARCH
        nx = int((mm(bb.GetWidth()) / 2 + SEARCH) / STEP) + 1
        ny = int((mm(bb.GetHeight()) / 2 + SEARCH) / STEP) + 1
        for i in range(-nx, nx + 1):
            for j in range(-ny, ny + 1):
                x, y = px + i * STEP, py + j * STEP
                dt = min(pad_dist(pp, x, y) for pp in target)
                if dt > SEARCH:
                    continue
                df = min([pad_dist(pp, x, y) for rr, nn, pp in pads if not (rr == ref and nn in same)] + [99])
                if axis:
                    (ax_, ay_), (bx_, by_) = tpos[0], [(mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in f.Pads() if p.GetNumber() != pad][0]
                    L = math.hypot(ax_ - bx_, ay_ - by_)
                    ux, uy = (ax_ - bx_) / L, (ay_ - by_) / L
                    if (x - ax_) * ux + (y - ay_) * uy <= 0:
                        continue                 # not beyond the marked pad
                if df <= dt + margin:
                    continue                     # some other pad is as near: the mark would be ambiguous
                score = dt + 0.5 * max(0.0, 1.0 - (df - dt))
                if best and score >= best[0]:
                    continue
                it = make(b, kind, x, y, r or 0)
                ip = poly_of(it, pcbnew.B_SilkS)
                if hits(grown(ip, MASK_CLR), mask) or hits(grown(ip, SILK_CLR), silk):
                    continue
                if any(hits(ip, q) for q in bodies):
                    continue
                out = grown(ip, EDGE_CLR)
                out.BooleanSubtract(ob.edge)
                if out.OutlineCount():
                    continue
                best = (score, x, y, dt, df)
        if best:
            s, x, y, dt, df = best
            it = make(b, kind, x, y, r or 0)
            b.Add(it)
            ob.silk.Append(poly_of(it, pcbnew.B_SilkS))
            return dict(ref=ref, pad=pad, kind=kind, x=round(x, 2), y=round(y, 2), size=(2 * r if r else 1.5),
                        gap=round(dt, 2), other=round(df, 2))
    return dict(ref=ref, pad=pad, kind=kind, x=None)


def run(bd):
    b = bd.b
    ob = Obstacles(b)
    done = []
    for ref, pad, kind, why in MARKS:
        m = place(b, ob, ref, pad, kind)
        m['kind'] = kind
        m['why'] = why
        done.append(m)
        if m['x'] is None:
            print(f'silk mark {ref}.{pad} {kind}: NO LEGAL SPOT')
        else:
            print(f"silk mark {ref}.{pad} {kind} {m['size']:g} mm at ({m['x']}, {m['y']}): {m['gap']} mm from the pad, next pad {m['other']} mm")
    return done
