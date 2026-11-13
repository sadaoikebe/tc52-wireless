#!/usr/bin/env python3
"""board_digest.py board.kicad_pcb [out.txt] : order-independent dump of a board (no UUIDs), one item per line,
grouped by kind, so that two builds can be compared with diff.  Silkscreen items are listed under 'silk'."""
import sys
import pcbnew
mm = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
SILK = (pcbnew.B_SilkS, pcbnew.F_SilkS)
out = []
r = lambda v: f'{mm(v):.4f}'
P = lambda p: f'({r(p.x)},{r(p.y)})'


def shape(g):
    s = f'{g.GetLayerName()} {g.GetClass()}'
    if g.GetClass() == 'PCB_SHAPE':
        s += f' {g.GetShapeStr()} {P(g.GetStart())} {P(g.GetEnd())} w={r(g.GetWidth())} fill={g.IsSolidFill()}'
        if g.GetShapeStr() == 'Polygon':
            o = g.GetPolyShape().Outline(0)
            s += ' ' + ' '.join(P(o.CPoint(i)) for i in range(o.PointCount()))
    else:
        s += f' {g.GetText()!r} {P(g.GetPosition())} size={r(g.GetTextSize().x)} th={r(g.GetTextThickness())} mir={g.IsMirrored()} ang={g.GetTextAngleDegrees()} vis={g.IsVisible()}'
    return s


for f in b.GetFootprints():
    ref = f.GetReference()
    out.append(f'fp {ref} {f.GetFPIDAsString()} {P(f.GetPosition())} rot={f.GetOrientationDegrees()} {f.GetLayerName()} val={f.GetValue()} dnp={f.IsDNP()} bom={f.IsExcludedFromBOM()} pos={f.IsExcludedFromPosFiles()}')
    for p in f.Pads():
        out.append(f'pad {ref}.{p.GetNumber()} {P(p.GetPosition())} net={p.GetNetname()} size={P(p.GetSize(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu))} ang={p.GetOrientationDegrees()} layers={p.GetLayerSet().FmtHex()}')
    for t in f.GetFields():
        out.append(('silk ' if t.GetLayer() in SILK else 'field ') + f'{ref} {t.GetName()} {shape(t)}')
    for g in f.GraphicalItems():
        out.append(('silk ' if g.GetLayer() in SILK else 'fpgfx ') + f'{ref} {shape(g)}')
for t in b.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        out.append(f'via {P(t.GetPosition())} {t.GetNetname()} d={r(t.GetWidth(pcbnew.F_Cu))} drill={r(t.GetDrill())}')
    else:
        out.append(f'track {t.GetLayerName()} {P(t.GetStart())} {P(t.GetEnd())} w={r(t.GetWidth())} {t.GetNetname()}')
for z in b.Zones():
    o = z.Outline()
    pts = ' '.join(P(o.CVertex(i)) for i in range(o.TotalVertices()))
    out.append(f'zone {z.GetLayerSet().FmtHex()} {z.GetNetname()} {z.GetZoneName()} rule={z.GetIsRuleArea()} prio={z.GetAssignedPriority()} {pts}')
for d in b.GetDrawings():
    out.append(('silk ' if d.GetLayer() in SILK else 'drawing ') + 'board ' + shape(d))
out.sort()
txt = '\n'.join(out) + '\n'
if len(sys.argv) > 2:
    open(sys.argv[2], 'w').write(txt)
else:
    sys.stdout.write(txt)
