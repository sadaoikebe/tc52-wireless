#!/usr/bin/env python3
"""gerber_objects.py A B : compare two Gerber (or Excellon-free) files as unordered multisets of drawn objects.

Each flash becomes (polarity, aperture definition, x, y); each stroke (polarity, aperture definition, mode, start,
end, centre offset); each region (polarity, its contour, rotated to start at its smallest vertex).  D-code numbers,
statement order and comments (dates) are ignored, so a board that was regenerated with its items in another order
compares equal when, and only when, the same geometry is plotted.  Prints counts and the objects that differ."""
import collections
import re
import sys


def objects(path):
    s = open(path).read()
    aps, out = {}, collections.Counter()
    cur = None; x = y = 0; mode = 'G01'; pol = 'D'; region = None
    for m in re.finditer(r'%(.*?)%|([^%*]*)\*', s, re.S):
        if m.group(1) is not None:
            blk = m.group(1).strip()
            a = re.match(r'ADD(\d+)(.*)', blk)
            if a:
                aps[int(a.group(1))] = a.group(2)
            elif blk.startswith('LP'):
                pol = blk[2]
            continue
        c = m.group(2).strip()
        if not c or c.startswith('G04'):
            continue
        if c in ('G01', 'G02', 'G03'):
            mode = c; continue
        if c == 'G36':
            region = []; continue
        if c == 'G37':
            if region:
                k = region.index(min(region)); out[('R', pol, tuple(region[k:] + region[:k]))] += 1
            region = None; continue
        d = re.match(r'^(G0[123])?(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?D0?(\d+)$', c)
        if not d:
            continue
        if d.group(1):
            mode = d.group(1)
        n = int(d.group(6))
        if n >= 10:
            cur = n; continue
        nx = int(d.group(2)) if d.group(2) else x
        ny = int(d.group(3)) if d.group(3) else y
        if n == 1:
            if region is not None:
                if not region:
                    region.append((x, y))
                region.append((nx, ny, mode, d.group(4), d.group(5)) if mode != 'G01' else (nx, ny))
            else:
                a, b = (x, y), (nx, ny)
                key = (mode, d.group(4), d.group(5), a, b) if mode != 'G01' else (mode, None, None) + tuple(sorted((a, b)))
                out[('S', pol, aps[cur]) + key] += 1
        elif n == 2 and region:
            k = region.index(min(region)); out[('R', pol, tuple(region[k:] + region[:k]))] += 1
            region = []
        elif n == 3:
            out[('F', pol, aps[cur], nx, ny)] += 1
        x, y = nx, ny
    return out


A, B = objects(sys.argv[1]), objects(sys.argv[2])
only_a, only_b = A - B, B - A
print(f'{sys.argv[1]}: {sum(A.values())} objects; {sys.argv[2]}: {sum(B.values())}; only in first {sum(only_a.values())}, only in second {sum(only_b.values())}')
for k, v in list(only_a.items())[:8]:
    print('  -', v, str(k)[:160])
for k, v in list(only_b.items())[:8]:
    print('  +', v, str(k)[:160])
sys.exit(1 if only_a or only_b else 0)
