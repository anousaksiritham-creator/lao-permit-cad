"""json2lsp.py - turn su_extract.rb model.json into an AutoLISP file that draws each view
centred in its own A3 sheet slot (geometry 1:1 mm, frame scale = sheet scale / 100).

python -I json2lsp.py <model.json> <out.lsp> <originX> <originY> [scale=75] [step=35487]
Prints a JSON sheet list (no, view, origin) for LaoPermitCad.psm1 to add frames/titles.
"""
import json
import sys

# Drawing area inside the A3 frame at scale 1 (frame 43108 x 29700, title band at bottom)
AREA = (1000, 5000, 41000, 28700)

# (sheet no, view key, layer, colour)
SHEETS = [
    ("SD-101", "plan", "SD-PLAN-CUT", 4),
    ("SD-102", "top", "SD-ROOF", 7),
    ("SD-201", "front", "SD-ELEV", 7),
    ("SD-202", "back", "SD-ELEV", 7),
    ("SD-203", "left", "SD-ELEV", 7),
    ("SD-204", "right", "SD-ELEV", 7),
]


def bbox(segs):
    xs = [c for s in segs for c in (s[0], s[2])]
    ys = [c for s in segs for c in (s[1], s[3])]
    return min(xs), min(ys), max(xs), max(ys)


def main():
    src, out, ox, oy = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    scale = int(sys.argv[5]) if len(sys.argv) > 5 else 75
    step = float(sys.argv[6]) if len(sys.argv) > 6 else 35487
    f = scale / 100 if scale in (75, 100) else 1
    d = json.load(open(src, encoding="utf-8"))
    # Component codes (su_extract.rb 5th seg field) kept per view; interior items would show through walls
    keep = {"top": {"07", "09", "20"},
            "elev": {"03", "04", "05", "07", "08", "09", "10", "11", "20"}}
    rotated = []
    views = {k: v["segs"] for k, v in d["views"].items()}
    for k in views:
        allowed = keep["top"] if k == "top" else keep["elev"]
        if views[k] and len(views[k][0]) > 4:
            views[k] = [s[:4] for s in views[k] if s[4] in allowed]
    views["plan"] = d["plans"][0]["segs"]
    # Plans of long buildings: rotate 90 deg so the long side runs along the sheet
    for k in ("plan", "top"):
        x0, y0, x1, y1 = bbox(views[k])
        if (y1 - y0) > (x1 - x0):
            views[k] = [[s[1], -s[0], s[3], -s[2]] for s in views[k]]
            rotated.append(k)

    lines = ["(defun lpc-l (lay x1 y1 x2 y2) (entmake (list '(0 . \"LINE\") (cons 8 lay) (list 10 x1 y1 0.0) (list 11 x2 y2 0.0))))",
             "(setvar \"CMDECHO\" 0)"]
    for _, _, lay, col in SHEETS:
        lines.append(f'(if (not (tblsearch "LAYER" "{lay}")) (command "_.-LAYER" "_M" "{lay}" "_C" "{col}" "" ""))')
    report = []
    for i, (no, key, lay, _) in enumerate(SHEETS):
        segs = views[key]
        sx, sy = ox + i * step, oy
        x0, y0, x1, y1 = bbox(segs)
        cx = sx + (AREA[0] + AREA[2]) / 2 * f
        cy = sy + (AREA[1] + AREA[3]) / 2 * f
        dx, dy = cx - (x0 + x1) / 2, cy - (y0 + y1) / 2
        fits = (x1 - x0) <= (AREA[2] - AREA[0]) * f and (y1 - y0) <= (AREA[3] - AREA[1]) * f
        for s in segs:
            lines.append(f'(lpc-l "{lay}" {s[0]+dx:.1f} {s[1]+dy:.1f} {s[2]+dx:.1f} {s[3]+dy:.1f})')
        report.append({"no": no, "view": key, "x": sx, "y": sy, "segs": len(segs),
                       "size": [round(x1 - x0), round(y1 - y0)], "fits": fits,
                       "offset": [round(dx, 1), round(dy, 1)], "rotated": key in rotated})
    lines.append('(setvar "CMDECHO" 1)(princ "\\nLPC views drawn")(princ)')
    open(out, "w", encoding="ascii").write("\n".join(lines))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
