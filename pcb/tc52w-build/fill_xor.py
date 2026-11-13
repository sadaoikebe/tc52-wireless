#!/usr/bin/env python3
"""fill_xor.py A.kicad_pcb B.kicad_pcb : area (mm^2) of the XOR of the zone fills of two boards, per copper layer.
Zone fills are not bit-stable from one regeneration to the next (vertex order / extra collinear vertices), so the
Gerber text can change without any copper changing; this measures the copper that really differs."""
import sys
import pcbnew


def fills(path):
    b = pcbnew.LoadBoard(path)
    out = {}
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for L in z.GetLayerSet().CuStack():
            p = z.GetFilledPolysList(L)
            out.setdefault(L, pcbnew.SHAPE_POLY_SET()).Append(p)
    return b, out


ba, A = fills(sys.argv[1])
bb, B = fills(sys.argv[2])
worst = 0.0
for L in sorted(set(A) | set(B)):
    a = A.get(L, pcbnew.SHAPE_POLY_SET()); b = B.get(L, pcbnew.SHAPE_POLY_SET())
    a.Simplify(); b.Simplify()
    x = pcbnew.SHAPE_POLY_SET(a); x.BooleanSubtract(b)
    y = pcbnew.SHAPE_POLY_SET(b); y.BooleanSubtract(a)
    area = (x.Area() + y.Area()) / 1e12
    worst = max(worst, area)
    print(f'{ba.GetLayerName(L):8s} fill area {a.Area() / 1e12:10.3f} / {b.Area() / 1e12:10.3f} mm^2, XOR {area:.6f} mm^2')
print('max XOR', f'{worst:.6f}', 'mm^2')
