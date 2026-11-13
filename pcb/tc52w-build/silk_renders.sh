#!/bin/bash
# silk_renders.sh : bottom-side renders of the plotted Gerbers (pcb/jlcpcb/gerber/ts52k-gerbers.zip), seen from below,
# with the orientation marks of silk.py ringed in yellow.  Output: docs/tc52w/silk/*.png
set -e
H=$(dirname $(realpath $0)); P=$(dirname $H); D=$(dirname $P)/docs/tc52w/silk
mkdir -p $D
T=$(mktemp -d)
unzip -q $P/jlcpcb/gerber/ts52k-gerbers.zip -d $T
# the marks silk.py adds are the board-level B.SilkS filled circles and the "+" / "-" texts
R=$(python3 - $P/ts52k.kicad_pcb <<'PY' 2>/dev/null
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
pts = [d.GetPosition() for d in b.GetDrawings() if d.GetLayer() == pcbnew.B_SilkS and
       ((d.GetClass() == 'PCB_SHAPE' and d.GetShapeStr() == 'Circle' and d.IsSolidFill()) or (d.GetClass() == 'PCB_TEXT' and d.GetText() in '+-'))]
print(';'.join(f'{mm(p.x):.2f},{mm(p.y):.2f}' for p in pts))
PY
)
V="python3 $H/gerber_view.py $T"
$V -5 39.5 310 84 $D/bottom-full.png --px 12 --bottom --rings "$R"
$V -5 39.5 310 84 $D/bottom-full-plain.png --px 12 --bottom
$V 14 44 16 20 $D/bottom-usb-charger.png --px 60 --bottom          # J1, D89-91, U9, Q1, J3
$V -5 82 18 24 $D/bottom-module-afe.png --px 45 --bottom           # U5, U6
$V -5 62 11 11 $D/bottom-sw1.png --px 60 --bottom                  # SW1
$V 68 101 13 16 $D/bottom-u7.png --px 50 --bottom                  # U7
$V 214.5 103 13 16 $D/bottom-u8.png --px 50 --bottom               # U8
rm -rf $T
