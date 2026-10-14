"""build_set.py - model.json (lpc_extract v2) + project.json -> one AutoLISP file that draws the
whole A3 sheet set in AutoCAD: own title block with attributes, layers, views, grids, dimensions,
door/window tags, levels, schedules, cover + index, B/E/P sheets.

python -I build_set.py <model.json> <project.json> <out.lsp> [originX originY]

Everything drawn carries XDATA  LPC = <project id>, and the LISP first erases the previous
build of the same project, so re-running is idempotent. Lao text is written as \\U+XXXX escapes
(ASCII-safe LISP). Writes <out>.sheets.json with the sheet list for plotting / QA.
"""
import json
import math
import os
import sys
from collections import defaultdict

# ---------------------------------------------------------------- constants
FRAME_W, FRAME_H = 42000.0, 29700.0           # A3 at 1:100 (frame scale 1)
AREA = (1500.0, 7000.0, 40500.0, 28200.0)     # drawing area inside frame (above the view title), frame units
GAP = 4000.0                                  # gap between sheets (model mm)
SCALES = [20, 25, 50, 75, 100, 200]
BLOCK = "LPC_A3_V1"

# code -> (cut layer, visible/beyond layer)
CODE_LAYERS = {
    "00": ("S-EXIST-CUT", "S-EXIST"), "00.1": ("A-DEMO", "A-DEMO"),
    "01": ("S-COLS-CUT", "S-FOUND"), "02": ("S-BEAM-CUT", "S-FOUND"), "18": ("S-REBAR", "S-REBAR"),
    "03": ("A-FLOR-CUT", "A-FLOR"), "13": ("A-FLOR-CUT", "A-FLOR"),
    "04": ("S-COLS-CUT", "S-COLS"), "05": ("S-BEAM-CUT", "S-BEAM"), "06": ("S-BEAM-CUT", "S-PURL"),
    "07": ("A-ROOF-CUT", "A-ROOF"), "08": ("A-WALL-CUT", "A-WALL"), "09": ("A-TRIM-CUT", "A-TRIM"),
    "10": ("A-DOOR", "A-DOOR"), "11": ("A-GLAZ", "A-GLAZ"), "12": ("A-CLNG", "A-CLNG"),
    "14": ("P-PIPE", "P-PIPE"), "15": ("P-SANR", "P-SANR"), "16": ("I-FURN", "I-FURN"),
    "19": ("E-LITE", "E-LITE"), "20": ("A-SIGN", "A-SIGN"),
}
# layer -> (colour, lineweight 1/100 mm, linetype)
LAYERS = {
    "A-WALL-CUT": (4, 50, "Continuous"), "A-WALL": (4, 25, "Continuous"),
    "S-COLS-CUT": (1, 50, "Continuous"), "S-COLS": (1, 25, "Continuous"),
    "S-BEAM-CUT": (1, 35, "Continuous"), "S-BEAM": (5, 25, "Continuous"), "S-PURL": (5, 13, "Continuous"),
    "S-FOUND": (6, 25, "Continuous"), "S-EXIST": (8, 18, "Continuous"), "S-EXIST-CUT": (8, 35, "Continuous"),
    "S-REBAR": (1, 13, "Continuous"), "A-DEMO": (8, 13, "HIDDEN"),
    "A-FLOR-CUT": (3, 35, "Continuous"), "A-FLOR": (8, 13, "Continuous"),
    "A-ROOF-CUT": (30, 35, "Continuous"), "A-ROOF": (30, 18, "Continuous"),
    "A-TRIM-CUT": (7, 35, "Continuous"), "A-TRIM": (7, 18, "Continuous"),
    "A-DOOR": (2, 18, "Continuous"), "A-GLAZ": (140, 18, "Continuous"), "A-CLNG": (8, 13, "Continuous"),
    "P-PIPE": (3, 25, "Continuous"), "P-SANR": (3, 18, "Continuous"), "I-FURN": (253, 9, "Continuous"),
    "E-LITE": (2, 25, "Continuous"), "A-SIGN": (6, 18, "Continuous"), "A-MISC": (8, 13, "Continuous"),
    "A-GRID": (8, 13, "CENTER"), "A-GRID-IDEN": (7, 18, "Continuous"), "A-DIMS": (8, 13, "Continuous"),
    "A-ANNO-TEXT": (7, 18, "Continuous"), "A-ANNO-TTLB": (7, 25, "Continuous"), "A-ANNO-SYMB": (1, 18, "Continuous"),
    "A-FLOR-LEVL": (51, 18, "Continuous"), "A-SECT-MARK": (1, 35, "DASHDOT"), "A-GRND": (32, 50, "Continuous"),
    "A-ANNO-TABL": (7, 18, "Continuous"), "S-BELOW-GRADE": (8, 13, "HIDDEN"), "A-HATCH": (8, 9, "Continuous"),
}


def lisp_str(s):
    """Python str -> LISP string literal; non-ASCII as \\U+XXXX (AutoCAD text escape)."""
    out = []
    for ch in str(s):
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif o < 128:
            out.append(ch)
        else:
            out.append("\\\\U+%04X" % o)
    return '"' + "".join(out) + '"'


def mtext(s):
    """Lao/plain text -> MText content (escape braces, keep \\P newlines given as '\n')."""
    return str(s).replace("{", "\\{").replace("}", "\\}").replace("\n", "\\P")


def fmt(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


# ---------------------------------------------------------------- geometry helpers
def merge_collinear(segs, tol=0.6):
    """Merge overlapping collinear segments per layer. segs: [(x1,y1,x2,y2,layer)]."""
    groups = defaultdict(list)
    out = []
    for x1, y1, x2, y2, lay in segs:
        dx, dy = x2 - x1, y2 - y1
        ln = math.hypot(dx, dy)
        if ln < 2:
            continue
        ang = math.atan2(dy, dx) % math.pi
        ux, uy = math.cos(ang), math.sin(ang)
        off = -uy * x1 + ux * y1
        key = (lay, round(ang, 4), round(off / tol))
        t1, t2 = ux * x1 + uy * y1, ux * x2 + uy * y2
        groups[key].append((min(t1, t2), max(t1, t2), ux, uy, off))
    for (lay, _, _), items in groups.items():
        items.sort()
        cur = None
        for t1, t2, ux, uy, off in items:
            if cur and t1 <= cur[1] + tol:
                cur[1] = max(cur[1], t2)
            else:
                if cur:
                    out.append(cur)
                cur = [t1, t2, ux, uy, off, lay]
        if cur:
            out.append(cur)
    res = []
    for t1, t2, ux, uy, off, lay in out:
        px, py = -uy * off, ux * off
        res.append((px + ux * t1, py + uy * t1, px + ux * t2, py + uy * t2, lay))
    return res


def closed_loops(segs, snap=1.0):
    """segs [(x1,y1,x2,y2)] -> list of closed polygons [(x,y),...] from components whose vertices
    all have degree 2 (unambiguous outlines). Used to hatch cut material."""
    key = lambda x, y: (round(x / snap), round(y / snap))
    adj = defaultdict(list)
    pos = {}
    for i, (x1, y1, x2, y2) in enumerate(segs):
        a, b = key(x1, y1), key(x2, y2)
        if a == b:
            continue
        adj[a].append(b)
        adj[b].append(a)
        pos[a], pos[b] = (x1, y1), (x2, y2)
    seen = set()
    loops = []
    for start in list(adj):
        if start in seen:
            continue
        # collect component
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            v = stack.pop()
            comp.append(v)
            for w in adj[v]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        if len(comp) < 3 or any(len(set(adj[v])) != 2 for v in comp):
            continue
        poly, prev, cur = [start], None, start
        while True:
            nxt = [w for w in set(adj[cur]) if w != prev]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            if cur == start:
                break
            poly.append(cur)
            if len(poly) > len(comp):
                break
        if len(poly) == len(comp):
            loops.append([pos[v] for v in poly])
    return loops


def poly_area(pts):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def bbox(segs):
    xs = [c for s in segs for c in (s[0], s[2])]
    ys = [c for s in segs for c in (s[1], s[3])]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 1, 1)


def cluster(vals, tol=150):
    vals = sorted(vals)
    groups = []
    for v in vals:
        if groups and v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


# ---------------------------------------------------------------- LISP writer
class Lisp:
    def __init__(self, proj):
        self.proj = proj
        self.lines = []

    def add(self, s):
        self.lines.append(s)

    def line(self, x1, y1, x2, y2, lay):
        self.add('(lpc-l "%s" %s %s %s %s)' % (lay, fmt(x1), fmt(y1), fmt(x2), fmt(y2)))

    def pline(self, pts, lay, closed=True, width=0):
        xy = " ".join("(list %s %s)" % (fmt(x), fmt(y)) for x, y in pts)
        self.add('(lpc-pl "%s" (list %s) %d %s)' % (lay, xy, 1 if closed else 0, fmt(width)))

    def text(self, x, y, h, s, lay="A-ANNO-TEXT", attach=1, width=0):
        self.add('(lpc-t "%s" %s %s %s %s %d %s)' % (lay, fmt(x), fmt(y), fmt(h), lisp_str(mtext(s)), attach, fmt(width)))

    def solid(self, pts, lay):
        p = [(fmt(x), fmt(y)) for x, y in pts]
        # SOLID vertex order is 1-2-4-3 (bow-tie otherwise)
        self.add("(entmake (list '(0 . \"SOLID\") (cons 8 \"%s\") (list 10 %s %s 0.0) (list 11 %s %s 0.0) "
                 "(list 12 %s %s 0.0) (list 13 %s %s 0.0) (lpc-xd)))" % ((lay,) + p[0] + p[1] + p[3] + p[2]))

    def hatch(self, pts, lay, pat, scale):
        xy = " ".join("(list %s %s)" % (fmt(x), fmt(y)) for x, y in pts)
        self.add('(vl-catch-all-apply (function lpc-h) (list "%s" "%s" %s (list %s)))' % (lay, pat, fmt(scale), xy))

    def circle(self, x, y, r, lay):
        self.add('(lpc-c "%s" %s %s %s)' % (lay, fmt(x), fmt(y), fmt(r)))

    def dim(self, x1, y1, x2, y2, lx, ly, rot, scale):
        self.add('(lpc-d %s %s %s %s %s %s %s %d)' % (fmt(x1), fmt(y1), fmt(x2), fmt(y2), fmt(lx), fmt(ly),
                                                       "%.6f" % rot, scale))

    def frame(self, x, y, f, attrs):
        kv = " ".join("(cons %s %s)" % (lisp_str(k), lisp_str(v)) for k, v in attrs.items())
        self.add('(lpc-frame %s %s %s (list %s))' % (fmt(x), fmt(y), "%.4f" % f, kv))


PRELUDE = r'''
(vl-load-com)
(setq lpc-doc (vla-get-ActiveDocument (vlax-get-acad-object)) lpc-ms (vla-get-ModelSpace lpc-doc))
(setq LPC-PROJ %(proj)s)
(regapp "LPC")
(setvar "CMDECHO" 0)
(defun lpc-xd () (list -3 (list "LPC" (cons 1000 LPC-PROJ))))
(defun lpc-x (obj / e) (setq e (vlax-vla-object->ename obj)) (entmod (append (entget e) (list (lpc-xd)))) obj)
(defun lpc-clean (/ ss i e x n)
  (setq n 0)
  (if (setq ss (ssget "_X" (list (list -3 (list "LPC")))))
    (repeat (setq i (sslength ss))
      (setq e (ssname ss (setq i (1- i))) x (cdr (assoc -3 (entget e (list "LPC")))))
      (if (= (cdr (assoc 1000 (cdr (car x)))) LPC-PROJ) (progn (entdel e) (setq n (1+ n))))))
  n)
(defun lpc-layer (nm col lw lt / l)
  (if (not (tblsearch "LTYPE" lt)) (vl-catch-all-apply 'vla-Load (list (vla-get-Linetypes lpc-doc) lt "acad.lin")))
  (setq l (vla-Add (vla-get-Layers lpc-doc) nm))
  (vla-put-Color l col) (vla-put-Lineweight l lw)
  (if (tblsearch "LTYPE" lt) (vla-put-Linetype l lt)))
(defun lpc-l (lay x1 y1 x2 y2)
  (entmake (list '(0 . "LINE") (cons 8 lay) (list 10 x1 y1 0.0) (list 11 x2 y2 0.0) (lpc-xd))))
(defun lpc-c (lay x y r)
  (entmake (list '(0 . "CIRCLE") (cons 8 lay) (list 10 x y 0.0) (cons 40 r) (lpc-xd))))
(defun lpc-pl (lay pts cl w)
  (entmake (append (list '(0 . "LWPOLYLINE") '(100 . "AcDbEntity") (cons 8 lay) '(100 . "AcDbPolyline")
                         (cons 90 (length pts)) (cons 70 cl) (cons 43 w))
                   (mapcar '(lambda (p) (list 10 (car p) (cadr p))) pts) (list (lpc-xd)))))
(defun lpc-t (lay x y h s at w)
  (entmake (list '(0 . "MTEXT") '(100 . "AcDbEntity") (cons 8 lay) '(100 . "AcDbMText")
                 (list 10 x y 0.0) (cons 40 h) (cons 41 w) (cons 71 at) (cons 7 "LPC_LAO") (cons 1 s) (lpc-xd))))
(defun lpc-d (x1 y1 x2 y2 lx ly rot sc / d)
  (setq d (vla-AddDimRotated lpc-ms (vlax-3d-point x1 y1 0) (vlax-3d-point x2 y2 0) (vlax-3d-point lx ly 0) rot))
  (vla-put-Layer d "A-DIMS") (vla-put-ScaleFactor d sc) (lpc-x d))
(defun lpc-h (lay pat sc pts / pl h arr)
  (lpc-pl lay pts 1 0)
  (setq pl (vlax-ename->vla-object (entlast)))
  (setq h (vla-AddHatch lpc-ms 1 pat :vlax-false))
  (setq arr (vlax-make-safearray vlax-vbObject '(0 . 0)))
  (vlax-safearray-put-element arr 0 pl)
  (vla-AppendOuterLoop h arr)
  (if (/= pat "SOLID") (vla-put-PatternScale h sc))
  (vla-put-Layer h lay) (vla-Evaluate h) (lpc-x h) (vla-Delete pl))
(defun lpc-frame (x y f attrs / b a v)
  (setq b (vla-InsertBlock lpc-ms (vlax-3d-point x y 0) "%(block)s" f f f 0))
  (vla-put-Layer b "A-ANNO-TTLB")
  (foreach a (vlax-invoke b 'GetAttributes)
    (if (setq v (assoc (vla-get-TagString a) attrs)) (vla-put-TextString a (cdr v))))
  (lpc-x b))
; ---- styles
(if (not (tblsearch "STYLE" "LPC_LAO"))
  (vla-SetFont (vla-Add (vla-get-TextStyles lpc-doc) "LPC_LAO") "Phetsarath OT" :vlax-false :vlax-false 0 0))
(if (not (tblsearch "STYLE" "LPC_ROM"))
  (vla-SetFont (vla-Add (vla-get-TextStyles lpc-doc) "LPC_ROM") "Arial" :vlax-false :vlax-false 0 0))
(setvar "DIMTXT" 2.0) (setvar "DIMASZ" 1.2) (setvar "DIMBLK" "_ARCHTICK") (setvar "DIMEXO" 1.5)
(setvar "DIMEXE" 1.25) (setvar "DIMGAP" 0.8) (setvar "DIMDEC" 0) (setvar "DIMTAD" 1) (setvar "DIMTIH" 0)
(setvar "DIMTOH" 0) (setvar "DIMTXSTY" "LPC_ROM") (setvar "DIMLUNIT" 2) (setvar "DIMCLRD" 8) (setvar "DIMCLRE" 8)
(if (not (tblsearch "DIMSTYLE" "LPC")) (vla-Add (vla-get-DimStyles lpc-doc) "LPC"))
(vla-CopyFrom (vla-Item (vla-get-DimStyles lpc-doc) "LPC") lpc-doc)
(vla-put-ActiveDimStyle lpc-doc (vla-Item (vla-get-DimStyles lpc-doc) "LPC"))
(setvar "LWDISPLAY" 1) (setvar "LTSCALE" 50) (setvar "PSLTSCALE" 0) (setvar "MSLTSCALE" 0)
'''


def title_block(L):
    """Define block LPC_A3_V1 once: A3 border + bottom title band with attributes (frame units)."""
    L.add('(if (not (tblsearch "BLOCK" "%s")) (progn' % BLOCK)
    L.add('(entmake (list \'(0 . "BLOCK") \'(2 . "%s") \'(70 . 2) \'(10 0.0 0.0 0.0)))' % BLOCK)

    def bl(x1, y1, x2, y2, w=0):
        L.add("(entmake (list '(0 . \"LWPOLYLINE\") '(100 . \"AcDbEntity\") '(8 . \"0\") '(100 . \"AcDbPolyline\") "
              "'(90 . 2) '(70 . 0) (cons 43 %s) '(10 %s %s) '(10 %s %s)))" % (fmt(w), fmt(x1), fmt(y1), fmt(x2), fmt(y2)))

    def rect(x1, y1, x2, y2, w):
        L.add("(entmake (list '(0 . \"LWPOLYLINE\") '(100 . \"AcDbEntity\") '(8 . \"0\") '(100 . \"AcDbPolyline\") "
              "'(90 . 4) '(70 . 1) (cons 43 %s) '(10 %s %s) '(10 %s %s) '(10 %s %s) '(10 %s %s)))"
              % (fmt(w), fmt(x1), fmt(y1), fmt(x2), fmt(y1), fmt(x2), fmt(y2), fmt(x1), fmt(y2)))

    def label(x, y, h, s):
        L.add("(entmake (list '(0 . \"TEXT\") '(8 . \"0\") (list 10 %s %s 0.0) (cons 40 %s) (cons 1 %s) "
              "'(7 . \"LPC_LAO\")))" % (fmt(x), fmt(y), fmt(h), lisp_str(s)))

    def attdef(tag, prompt, x, y, h, default=""):
        L.add("(entmake (list '(0 . \"ATTDEF\") '(8 . \"0\") (list 10 %s %s 0.0) (cons 40 %s) (cons 1 %s) "
              "(cons 3 %s) (cons 2 %s) '(70 . 0) '(7 . \"LPC_LAO\") '(72 . 1) (list 11 %s %s 0.0) '(74 . 2)))"
              % (fmt(x), fmt(y), fmt(h), lisp_str(default), lisp_str(prompt), lisp_str(tag), fmt(x), fmt(y)))

    rect(0, 0, FRAME_W, FRAME_H, 0)                 # trim line
    rect(1000, 1000, 41000, 28700, 60)              # border
    bl(1000, 5000, 41000, 5000, 40)                 # title band top
    for x in (9000, 21000, 33000, 37000):
        bl(x, 1000, x, 5000, 25)
    bl(1000, 3000, 9000, 3000, 0)
    bl(37000, 3000, 41000, 3000, 0)
    label(1200, 4550, 180, "ເຈົ້າຂອງ / OWNER")
    label(1200, 2550, 180, "ອອກແບບ / DESIGNED BY")
    label(9200, 4550, 180, "ໂຄງການ / PROJECT")
    label(21200, 4550, 180, "ຊື່ແຜ່ນ / DRAWING")
    label(33200, 4550, 180, "ເລກແຜ່ນ / NO.")
    label(37200, 4550, 180, "ມາດຕາສ່ວນ / SCALE")
    label(37200, 2550, 180, "ວັນທີ / DATE")
    attdef("OWNER", "Owner", 5000, 3700, 300)
    attdef("DESIGNER", "Designer", 5000, 1700, 300)
    attdef("PROJECT", "Project", 15000, 3500, 520)
    attdef("LOCATION", "Location", 15000, 1900, 300)
    attdef("TITLE", "Drawing title", 27000, 2800, 520)
    attdef("SHEETNO", "Sheet no", 35000, 2600, 650)
    attdef("SCALE", "Scale", 39000, 3700, 340)
    attdef("DATE", "Date", 39000, 1700, 300)
    L.add("(entmake '((0 . \"ENDBLK\")))))")


# ---------------------------------------------------------------- the set
class SetBuilder:
    def __init__(self, model, project, origin):
        self.m = model
        self.p = project
        self.ox, self.oy = origin
        self.L = Lisp(project["id"])
        self.sheets = []
        self.warnings = []
        self.cursor = self.ox
        objs = {o.get("code") or o["name"].split(" ")[0]: o for o in model["objects"]}
        self.objs = objs
        # building footprint from walls / floor, else whole bounds
        fp = [objs[c] for c in ("08", "13", "03") if c in objs]
        mn = [min(o["min"][i] for o in fp) for i in range(3)] if fp else model["bounds_mm"]["min"]
        mx = [max(o["max"][i] for o in fp) for i in range(3)] if fp else model["bounds_mm"]["max"]
        self.fp = (mn, mx)
        self.rotate = (mx[1] - mn[1]) > (mx[0] - mn[0])     # long side along sheet X
        # levels
        z = lambda c, k, i: objs[c][k][i] if c in objs else None
        self.levels = [("ລະດັບດິນທຳມະຊາດ", 0)]
        for name, val in (("ລະດັບພື້ນສຳເລັດ", z("13", "max", 2) or z("03", "max", 2)),
                          ("ລະດັບເພດານ", z("12", "min", 2)),
                          ("ລະດັບຫຼັງຄາສູງສຸດ", z("07", "max", 2))):
            if val is not None:
                self.levels.append((name, round(val)))
        floors = self.p.get("floors") or []
        if any("level" in fl for fl in floors):
            keep = [l for l in self.levels if l[0] in ("ລະດັບດິນທຳມະຊາດ", "ລະດັບຫຼັງຄາສູງສຸດ")]
            self.levels = sorted(keep + [("ລະດັບພື້ນ " + fl["name"], fl["level"]) for fl in floors if "level" in fl],
                                 key=lambda l: l[1])
        self.grids = self.find_grids()
        self.openings = self.find_openings()

    # ------------- semantic
    def find_grids(self):
        cols = self.objs.get("04", {}).get("children", [])
        xs, ys = [], []
        for c in cols:
            w, d = c["max"][0] - c["min"][0], c["max"][1] - c["min"][1]
            h = c["max"][2] - c["min"][2]
            if w <= 600 and d <= 600 and h > 1500:
                xs.append((c["min"][0] + c["max"][0]) / 2)
                ys.append((c["min"][1] + c["max"][1]) / 2)
        return cluster(xs), cluster(ys)

    def find_openings(self):
        res = []
        for code, prefix in (("10", "D"), ("11", "W")):
            kids = self.objs.get(code, {}).get("children", [])
            types = {}
            for k in kids:
                w = max(k["max"][0] - k["min"][0], k["max"][1] - k["min"][1])
                h = k["max"][2] - k["min"][2]
                if w < 300 or h < 300:
                    continue
                typ = k["name"].split(" ")[0].split("-")[0] or prefix
                key = (typ, round(w / 10) * 10, round(h / 10) * 10)
                if key not in types:
                    n = sum(1 for t in types if t[0] == typ) + 1
                    types[key] = "%s%d" % (typ, n)
                res.append({"tag": types[key], "name": k["name"], "w": round(w), "h": round(h),
                            "sill": (lambda v: 0 if abs(v) < 50 else v)(round(k["min"][2] - (self.levels[1][1] if len(self.levels) > 1 else 0))),
                            "x": (k["min"][0] + k["max"][0]) / 2, "y": (k["min"][1] + k["max"][1]) / 2,
                            "z0": k["min"][2], "z1": k["max"][2]})
        return res

    # ------------- transforms
    def tplan(self, x, y):
        return (y, -x) if self.rotate else (x, y)

    def plan_segs(self, segs, codes=None, kinds=None, force_layer=None):
        out = []
        for s in segs:
            code, kind = (s[4], s[5]) if len(s) > 5 else (s[4] if len(s) > 4 else "", "vis")
            if codes is not None and code not in codes:
                continue
            if kinds is not None and kind not in kinds:
                continue
            cut_l, vis_l = CODE_LAYERS.get(code, ("A-MISC", "A-MISC"))
            lay = force_layer or (cut_l if kind == "cut" else vis_l)
            a, b = self.tplan(s[0], s[1]), self.tplan(s[2], s[3])
            out.append((a[0], a[1], b[0], b[1], lay))
        return out

    def elev_segs(self, segs, codes=None):
        out = []
        for s in segs:
            code = s[4] if len(s) > 4 else ""
            kind = s[5] if len(s) > 5 else "vis"
            if codes is not None and code not in codes:
                continue
            cut_l, vis_l = CODE_LAYERS.get(code, ("A-MISC", "A-MISC"))
            out.append((s[0], s[1], s[2], s[3], cut_l if kind == "cut" else vis_l))
        return out

    # ------------- sheet placement
    def pick_scale(self, w, h, allowed=(50, 75, 100, 200), reserve=0.0):
        for sc in allowed:
            f = sc / 100.0
            if w <= (AREA[2] - AREA[0] - reserve) * f * 0.92 and h <= (AREA[3] - AREA[1]) * f * 0.85:
                return sc
        return allowed[-1]

    def new_sheet(self, no, title, scale, kind="view"):
        f = scale / 100.0
        x, y = self.cursor, self.oy
        self.cursor += FRAME_W * f + GAP
        attrs = {"PROJECT": self.p["name"], "LOCATION": self.p.get("location", ""), "OWNER": self.p.get("owner", ""),
                 "DESIGNER": self.p.get("designer", ""), "DATE": self.p.get("date", ""),
                 "TITLE": title, "SHEETNO": no, "SCALE": "1:%d" % scale}
        self.L.frame(x, y, f, attrs)
        sh = {"no": no, "title": title, "scale": scale, "x": x, "y": y, "w": FRAME_W * f, "h": FRAME_H * f, "lines": 0,
              "kind": kind}
        self.sheets.append(sh)
        return sh

    def place(self, sh, segs, cx=None, cy=None):
        """Centre geometry (sheet-independent coords) in the sheet's drawing area; returns offset."""
        f = sh["scale"] / 100.0
        x0, y0, x1, y1 = bbox(segs)
        acx = sh["x"] + (AREA[0] + AREA[2]) / 2 * f if cx is None else cx
        acy = sh["y"] + (AREA[1] + AREA[3]) / 2 * f + 300 * f if cy is None else cy
        dx, dy = acx - (x0 + x1) / 2, acy - (y0 + y1) / 2
        merged = merge_collinear(segs)
        for a, b, c, d, lay in merged:
            self.L.line(a + dx, b + dy, c + dx, d + dy, lay)
        self.check_fit(sh, x0 + dx, y0 + dy, x1 + dx, y1 + dy, len(merged))
        return dx, dy

    def check_fit(self, sh, x0, y0, x1, y1, n):
        f = sh["scale"] / 100.0
        sh["lines"] += n
        ax0, ay0 = sh["x"] + 1000 * f, sh["y"] + 5000 * f
        ax1, ay1 = sh["x"] + 41000 * f, sh["y"] + 28700 * f
        if x0 < ax0 or y0 < ay0 or x1 > ax1 or y1 > ay1:
            self.warnings.append("%s: view extends outside the border" % sh["no"])

    def view_title(self, sh, x, y, title, scale):
        f = sh["scale"] / 100.0
        h = 4.0 * sh["scale"]
        self.L.text(x, y + h * 0.4, h, title, "A-ANNO-TEXT", 8)          # bottom-centre on the line
        self.L.line(x - 6000 * f, y, x + 6000 * f, y, "A-ANNO-TTLB")
        self.L.text(x, y - h * 0.4, h * 0.6, "ມາດຕາສ່ວນ 1:%d" % scale, "A-ANNO-TEXT", 2)

    def note(self, sh, text):
        f = sh["scale"] / 100.0
        self.L.text(sh["x"] + 1700 * f, sh["y"] + 28000 * f, 2.2 * sh["scale"], text, "A-ANNO-TEXT", 1, 16000 * f)

    # ------------- annotation helpers
    def grid_annot(self, sh, dx, dy, segs_bb, scale):
        gx, gy = self.grids
        if not gx and not gy:
            return
        r = 4.5 * scale
        ext = 9 * scale
        x0, y0, x1, y1 = segs_bb
        long_y = (self.fp[1][1] - self.fp[0][1]) > (self.fp[1][0] - self.fp[0][0])
        nums = ([chr(65 + i) for i in range(len(gx))] if long_y else [str(i + 1) for i in range(len(gx))])
        lets = ([str(i + 1) for i in range(len(gy))] if long_y else [chr(65 + i) for i in range(len(gy))])
        # model x-grids -> after rotation they are horizontal lines; keep generic via tplan
        for v, lab in zip(gx, nums):
            a = self.tplan(v, self.fp[0][1] - 1500)
            b = self.tplan(v, self.fp[1][1] + 1500)
            self.grid_line(a, b, lab, dx, dy, r)
        for v, lab in zip(gy, lets):
            a = self.tplan(self.fp[0][0] - 1500, v)
            b = self.tplan(self.fp[1][0] + 1500, v)
            self.grid_line(a, b, lab, dx, dy, r)

    def grid_line(self, a, b, lab, dx, dy, r):
        ax, ay, bx, by = a[0] + dx, a[1] + dy, b[0] + dx, b[1] + dy
        self.L.line(ax, ay, bx, by, "A-GRID")
        ln = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / ln, (by - ay) / ln
        for px, py, sgn in ((ax, ay, -1), (bx, by, 1)):
            cx, cy = px + ux * r * sgn, py + uy * r * sgn
            self.L.circle(cx, cy, r, "A-GRID-IDEN")
            self.L.text(cx, cy, r * 1.0, lab, "A-GRID-IDEN", 5)

    def plan_dims(self, dx, dy, scale):
        gx, gy = self.grids
        (mnx, mny, _), (mxx, mxy, _) = self.fp
        step = 8 * scale
        base = 1500 + 12 * scale         # first dimension row sits outside the grid bubbles
        xs = sorted(set([mnx] + gx + [mxx]))
        ys = sorted(set([mny] + gy + [mxy]))
        # dimension chains along model X (below model min Y) and along model Y (left of model min X)
        for row, chain in enumerate((gx and [mnx] + gx + [mxx], [mnx, mxx])):
            if not chain:
                continue
            off = mny - base - row * step
            for a, b in zip(chain, chain[1:]):
                if b - a < 50:
                    continue
                self.dim_model((a, mny), (b, mny), (a, off), dx, dy, scale)
        for row, chain in enumerate((gy and [mny] + gy + [mxy], [mny, mxy])):
            if not chain:
                continue
            off = mnx - base - row * step
            for a, b in zip(chain, chain[1:]):
                if b - a < 50:
                    continue
                self.dim_model((mnx, a), (mnx, b), (off, a), dx, dy, scale)

    def dim_model(self, p1, p2, loc, dx, dy, scale):
        a, b, l = self.tplan(*p1), self.tplan(*p2), self.tplan(*loc)
        horiz = abs(b[0] - a[0]) >= abs(b[1] - a[1])
        self.L.dim(a[0] + dx, a[1] + dy, b[0] + dx, b[1] + dy, l[0] + dx, l[1] + dy, 0.0 if horiz else math.pi / 2, scale)

    def opening_tags(self, dx, dy, scale, z=None):
        for o in self.openings:
            if z is not None and not (o["z0"] - 1 < z < o["z1"] + 1):
                continue
            x, y = self.tplan(o["x"], o["y"])
            x, y = x + dx, y + dy
            r = 3.5 * scale
            if o["tag"].startswith("D"):
                self.L.circle(x, y, r, "A-ANNO-SYMB")
            else:
                self.L.pline([(x - r * 1.3, y - r * 0.8), (x + r * 1.3, y - r * 0.8), (x + r * 1.3, y + r * 0.8),
                              (x - r * 1.3, y + r * 0.8)], "A-ANNO-SYMB")
            self.L.text(x, y, 2.2 * scale, o["tag"], "A-ANNO-SYMB", 5)

    def section_marks(self, dx, dy, scale):
        for s in self.m.get("sections", []):
            at = s["at"]
            ext = 1500 + 27 * scale          # beyond grid bubbles and both dimension rows
            if s["axis"] == "y":
                a, b = self.tplan(self.fp[0][0] - ext, at), self.tplan(self.fp[1][0] + ext, at)
            else:
                a, b = self.tplan(at, self.fp[0][1] - ext), self.tplan(at, self.fp[1][1] + ext)
            ax, ay, bx, by = a[0] + dx, a[1] + dy, b[0] + dx, b[1] + dy
            self.L.line(ax, ay, bx, by, "A-SECT-MARK")
            lab = s["name"].split("-")[0]
            for px, py in ((ax, ay), (bx, by)):
                self.L.circle(px, py, 4 * scale, "A-ANNO-SYMB")
                self.L.text(px, py, 3 * scale, lab, "A-ANNO-SYMB", 5)

    def north_arrow(self, sh):
        f = sh["scale"] / 100.0
        cx, cy = sh["x"] + 38500 * f, sh["y"] + 25800 * f
        r = 1100 * f
        self.L.circle(cx, cy, r, "A-ANNO-SYMB")
        ang = math.pi if self.rotate else math.pi / 2       # model +Y
        tip = (cx + math.cos(ang) * r * 1.3, cy + math.sin(ang) * r * 1.3)
        l = (cx + math.cos(ang + 2.6) * r * 0.8, cy + math.sin(ang + 2.6) * r * 0.8)
        rr = (cx + math.cos(ang - 2.6) * r * 0.8, cy + math.sin(ang - 2.6) * r * 0.8)
        self.L.pline([tip, l, (cx, cy), rr], "A-ANNO-SYMB")
        self.L.text(tip[0] + math.cos(ang) * r * 0.5, tip[1] + math.sin(ang) * r * 0.5, 600 * f, "N", "A-ANNO-SYMB", 5)

    def levels_elev(self, dx, dy, xr, scale):
        for i, (name, z) in enumerate(self.levels):
            y = z + dy
            x = xr + dx + 1500
            L = self.L
            L.line(x, y, x + 9 * scale * 3, y, "A-FLOR-LEVL")
            t = 2.5 * scale
            L.pline([(x, y), (x + t * 0.6, y + t * 0.9), (x - t * 0.6, y + t * 0.9)], "A-FLOR-LEVL")
            sign = "±" if z == 0 else ("+" if z > 0 else "")
            yy = y + t * 1.6 if not (i == 0 and len(self.levels) > 1 and self.levels[1][1] - z < 12 * scale) else y - t * 0.6
            L.text(x + t, yy, t, "%s (%s%s)" % (name, sign, "0.00" if z == 0 else z), "A-FLOR-LEVL", 7 if yy > y else 1)

    def table(self, x, y, cols, rows, h, lay="A-ANNO-TABL"):
        """cols: [(header, width)], rows: [[cells]]; top-left at x,y."""
        rh = h * 2.2
        tw = sum(w for _, w in cols)
        n = len(rows) + 1
        for i in range(n + 1):
            self.L.line(x, y - i * rh, x + tw, y - i * rh, lay)
        cx = x
        for _, w in cols:
            self.L.line(cx, y, cx, y - n * rh, lay)
            cx += w
        self.L.line(cx, y, cx, y - n * rh, lay)
        for r, row in enumerate([[c for c, _ in cols]] + rows):
            cx = x
            for (c, w), val in zip(cols, row):
                self.L.text(cx + w / 2, y - r * rh - rh / 2, h, val, lay, 5)
                cx += w
        return y - n * rh

    # ------------- sheets
    def column_fill(self, dx, dy, codes, z):
        for c in codes:
            for k in self.objs.get(c, {}).get("children", []):
                (x0, y0, z0), (x1, y1, z1) = k["min"], k["max"]
                if not (z0 < z < z1) or max(x1 - x0, y1 - y0) > 800 or z1 - z0 < 300:
                    continue
                pts = [self.tplan(x0, y0), self.tplan(x1, y0), self.tplan(x1, y1), self.tplan(x0, y1)]
                self.L.solid([(px + dx, py + dy) for px, py in pts], "S-COLS-CUT")

    def plan_sheet(self, no, title, segs, extra=None, dims=True, tags=True, sections=True, scale=None, note=None,
                   reserve=0.0, fill=None, tag_z=None):
        """reserve: frame units kept free on the right (legend column)."""
        bb = bbox(segs)
        sc = scale or self.pick_scale(bb[2] - bb[0] + 30 * 75, bb[3] - bb[1] + 30 * 75, reserve=reserve)
        sh = self.new_sheet(no, title, sc)
        f = sc / 100.0
        dx, dy = self.place(sh, segs, cx=sh["x"] + (AREA[0] + AREA[2] - reserve) / 2 * f)
        if extra:
            for a, b, c, d, lay in extra:
                self.L.line(a + dx, b + dy, c + dx, d + dy, lay)
        if fill:
            self.column_fill(dx, dy, *fill)
        self.grid_annot(sh, dx, dy, bb, sc)
        if dims:
            self.plan_dims(dx, dy, sc)
        if tags:
            self.opening_tags(dx, dy, sc, tag_z)
        if sections:
            self.section_marks(dx, dy, sc)
        self.north_arrow(sh)
        f = sc / 100.0
        self.view_title(sh, (sh["x"] + (AREA[0] + AREA[2]) / 2 * f), sh["y"] + 6100 * f, title, sc)
        if note:
            self.note(sh, note)
        return sh

    def elev_grids(self, view, dx, dy, ybot, scale):
        gx, gy = self.grids
        long_y = (self.fp[1][1] - self.fp[0][1]) > (self.fp[1][0] - self.fp[0][0])
        labx = [chr(65 + i) for i in range(len(gx))] if long_y else [str(i + 1) for i in range(len(gx))]
        laby = [str(i + 1) for i in range(len(gy))] if long_y else [chr(65 + i) for i in range(len(gy))]
        if view in ("front", "A-A"):
            items = list(zip(gx, labx))
        elif view == "back":
            items = [(-v, l) for v, l in zip(gx, labx)]
        elif view in ("left", "B-B"):
            items = [(-v, l) for v, l in zip(gy, laby)]
        elif view == "right":
            items = list(zip(gy, laby))
        else:
            return
        r = 4.5 * scale
        for u, lab in items:
            x = u + dx
            self.L.line(x, ybot + dy + r * 2, x, ybot + dy + r * 2 + 1200, "A-GRID")
            self.L.circle(x, ybot + dy + r, r, "A-GRID-IDEN")
            self.L.text(x, ybot + dy + r, r, lab, "A-GRID-IDEN", 5)

    HATCH = {"01": "ANSI31", "02": "ANSI31", "03": "ANSI31", "13": "ANSI31", "00": "ANSI31",
             "08": "ANSI31", "04": "SOLID", "05": "SOLID", "06": "SOLID"}

    def section_hatch(self, raw, dx, dy, scale):
        by = defaultdict(list)
        for s in raw:
            if len(s) > 5 and s[5] == "cut" and s[4] in self.HATCH:
                by[s[4]].append(s[:4])
        n = 0
        for code, segs in by.items():
            for loop in closed_loops(segs):
                if poly_area(loop) < 400 or len(loop) > 200:
                    continue
                pat = self.HATCH[code]
                self.L.hatch([(x + dx, y + dy) for x, y in loop], "A-HATCH", pat, 0.6 * scale)
                n += 1
        return n

    def elev_sheet(self, no, title, segs, levels=True, view=None, raw=None):
        segs = [(a, b, c, d, "S-BELOW-GRADE" if max(b, d) < -20 else lay) for a, b, c, d, lay in segs
                if not (max(b, d) < -20 and lay in ("P-PIPE", "P-SANR"))]
        bb = bbox(segs)
        zone = 62.0          # level marks: paper mm right of the view
        sc = None
        for cand in (50, 75, 100, 200):
            if self.pick_scale(bb[2] - bb[0] + 1500 + zone * cand, bb[3] - bb[1] + 15 * cand, (cand,)) == cand and                bb[2] - bb[0] + 1500 + zone * cand <= (AREA[2] - AREA[0]) * cand / 100 * 0.92:
                sc = cand
                break
        sc = sc or 200
        sh = self.new_sheet(no, title, sc)
        # ground line + invisible extent for the level zone so the whole group is centred
        g = [(bb[0] - 1500, 0, bb[2] + 1500, 0, "A-GRND")]
        f = sc / 100.0
        x0, y0, x1, y1 = bbox(segs + g)
        x1z = x1 + zone * sc
        dx = sh["x"] + (AREA[0] + AREA[2]) / 2 * f - (x0 + x1z) / 2
        dy = sh["y"] + (AREA[1] + AREA[3]) / 2 * f + 300 * f - (y0 + y1) / 2
        merged = merge_collinear(segs + g)
        for a, b, c, d, lay in merged:
            self.L.line(a + dx, b + dy, c + dx, d + dy, lay)
        self.check_fit(sh, x0 + dx, y0 + dy, x1z + dx, y1 + dy, len(merged))
        if levels:
            self.levels_elev(dx, dy, bb[2] + 1000, sc)
        if view:
            self.elev_grids(view, dx, dy, y0 - 12 * sc, sc)
        if raw:
            sh["hatches"] = self.section_hatch(raw, dx, dy, sc)
        f = sc / 100.0
        self.view_title(sh, (sh["x"] + (AREA[0] + AREA[2]) / 2 * f), sh["y"] + 6100 * f, title, sc)
        return sh

    def cover(self, index):
        sc = 100
        sh = self.new_sheet("A101", "ໜ້າປົກ ແລະ ສາລະບານ", sc, kind="table")
        x, y = sh["x"], sh["y"]
        self.L.text(x + 21000, y + 25500, 1200, self.p["name"], "A-ANNO-TEXT", 2)
        self.L.text(x + 21000, y + 23600, 700, self.p.get("subtitle", ""), "A-ANNO-TEXT", 2)
        self.L.text(x + 21000, y + 22300, 450, self.p.get("location", ""), "A-ANNO-TEXT", 2)
        cols = [("ເລກແຜ່ນ", 2800), ("ຊື່ແຜ່ນ", 12800), ("ມາດຕາສ່ວນ", 2800)]
        half = (len(index) + 1) // 2
        for k, part in enumerate((index[:half], index[half:])):
            if part:
                self.table(x + 1800 + k * 19600, y + 20500, cols, [[a, b, c] for a, b, c in part], 280)
        return sh

    def build(self):
        m, L = self.m, self.L
        L.add(PRELUDE % {"proj": lisp_str(self.p["id"]), "block": BLOCK})
        L.add('(princ (strcat "\\nLPC: removed " (itoa (lpc-clean)) " old entities"))')
        for nm, (col, lw, lt) in LAYERS.items():
            L.add('(lpc-layer "%s" %d %d "%s")' % (nm, col, lw, lt))
        title_block(L)
        # cover first (index filled after other sheets are known): reserve slot
        cover_x = self.cursor
        self.cursor += FRAME_W + GAP
        sec = {s["name"]: s for s in m.get("sections", [])}
        plan = next((p for p in m["plans"] if 1000 <= p["z"] <= 2000), m["plans"][0])
        archi = None
        # --- A2 plans
        arch = {"03", "04", "05", "07", "08", "09", "10", "11", "12", "13", "15", "16", "19", "20"}
        floors = self.p.get("floors") or [{"name": "ຊັ້ນ 1", "cut": plan["z"]}]
        num = 201
        for fl in floors:
            pl = min(m["plans"], key=lambda p: abs(p["z"] - fl["cut"]))
            self.plan_sheet("A%d" % num, "ແຜນຜັງ " + fl["name"], self.plan_segs(pl["segs"], codes=arch),
                            fill=(["04", "08"], pl["z"]), tag_z=pl["z"])
            num += 1
        if len(floors) == 1:
            self.plan_sheet("A%d" % num, "ແຜນຜັງ ບອກໄລຍະ ແລະ ປະຕູ-ປ່ອງຢ້ຽມ",
                            self.plan_segs(plan["segs"], codes=arch, kinds={"cut"}) +
                            self.plan_segs(plan["segs"], codes={"03", "13", "10", "11"}, kinds={"beyond"}),
                            fill=(["04", "08"], plan["z"]), tag_z=plan["z"])
            num += 1
        roofc = {"03", "04", "05", "06", "07", "08", "09", "11", "13", "20"}
        self.plan_sheet("A%d" % num, "ແຜນຜັງ ຫຼັງຄາ", self.plan_segs(m["views"]["top"]["segs"], codes=roofc),
                        tags=False, sections=False)
        # --- A3 elevations + sections
        names = {"front": ("A301", "ຮູບດ້ານໜ້າ"), "back": ("A302", "ຮູບດ້ານຫຼັງ"),
                 "left": ("A303", "ຮູບດ້ານຊ້າຍ"), "right": ("A304", "ຮູບດ້ານຂວາ")}
        for k, (no, t) in names.items():
            self.elev_sheet(no, t, self.elev_segs(m["views"][k]["segs"]), view=k)
        for i, s in enumerate(m.get("sections", [])):
            self.elev_sheet("A31%d" % (i + 1), "ຮູບຕັດ %s" % s["name"], self.elev_segs(s["segs"]),
                            view=s["name"] if s.get("look", 1) > 0 else None, raw=s["segs"])
        # --- A4 schedule
        self.schedule_sheet()
        # --- B structure
        found = next((p for p in m["plans"] if p["z"] < 300), None)
        if found:
            self.plan_sheet("B101", "ແຜນຜັງ ຮາກຖານ ແລະ ຄານຄໍດິນ",
                            self.plan_segs(found["segs"], codes={"00", "01", "02", "03", "04", "18"}),
                            tags=False, sections=False, note=self.p["engineer_note"], fill=(["01", "04"], found["z"]))
        xr = m["views"].get("top_xray", {}).get("segs", [])
        if xr:
            self.plan_sheet("B201", "ແຜນຜັງ ໂຄງຫຼັງຄາ (ເສົາ, ຄານ, ແປ)",
                            self.plan_segs(xr, codes={"04", "05", "06"}), tags=False, sections=False,
                            note=self.p["engineer_note"])
            walls = self.plan_segs(plan["segs"], codes={"04", "08", "10", "11"}, kinds={"cut"})
            self.member_schedule()
            sh = self.plan_sheet("E101", "ແຜນຜັງ ໄຟຟ້າ ແສງສະຫວ່າງ",
                                 walls + self.plan_segs(xr, codes={"19"}), tags=False, sections=False,
                                 note=self.p["engineer_note"], reserve=11500)
            self.legend(sh, ["19"], "ສັນຍາລັກ / LEGEND")
            sh = self.plan_sheet("P101", "ແຜນຜັງ ລະບົບນ້ຳ ແລະ ສຸຂະພັນ",
                                 walls + self.plan_segs(xr, codes={"14", "15"}), tags=False, sections=False,
                                 note=self.p["engineer_note"], reserve=11500)
            self.legend(sh, ["14", "15"], "ສັນຍາລັກ / LEGEND")
        # --- cover with index (placed in the reserved slot)
        end = self.cursor
        self.cursor = cover_x
        index = [(s["no"], s["title"], "1:%d" % s["scale"]) for s in self.sheets]
        cov = self.cover([("A101", "ໜ້າປົກ ແລະ ສາລະບານ", "-")] + index)
        self.sheets.remove(cov)
        self.sheets.insert(0, cov)
        self.cursor = end
        L.add('(setvar "CMDECHO" 1)')
        L.add('(setq f (open %s "w")) (write-line "done" f) (close f)' % lisp_str(self.p["done_flag"].replace("\\", "/")))
        L.add('(princ "\\nLPC set built") (princ)')
        return "\n".join(L.lines)

    def legend(self, sh, codes, title):
        """Fixture legend from component children (type = name prefix before '-NN')."""
        f = sh["scale"] / 100.0
        agg = {}
        for c in codes:
            for k in self.objs.get(c, {}).get("children", []):
                typ = k["name"].split(" ")[0].split("-")[0]
                desc = k["name"].split(" ", 1)[1] if " " in k["name"] else k["name"]
                a = agg.setdefault(typ, [desc, 0])
                a[1] += 1
        if not agg:
            return
        rows = [[t, d[:30], str(n)] for t, (d, n) in sorted(agg.items())]
        x, y = sh["x"] + 29800 * f, sh["y"] + 24500 * f
        self.L.text(x, y + 500 * f, 2.6 * sh["scale"], title, "A-ANNO-TEXT", 7)
        self.table(x, y, [("ລະຫັດ", 1800 * f), ("ລາຍການ", 7200 * f), ("ຈຳນວນ", 1800 * f)], rows, 2.0 * sh["scale"])

    def member_schedule(self):
        rows = {}
        for c in ("00", "01", "02", "04", "05", "06", "18"):
            o = self.objs.get(c)
            if not o:
                continue
            for k in o.get("children", []):
                typ = k["name"].split(" ")[0].split("-")[0]
                desc = k["name"].split(" ", 1)[1] if " " in k["name"] else ""
                dims = sorted(round(k["max"][i] - k["min"][i]) for i in range(3))
                key = (c, typ)
                r = rows.setdefault(key, {"desc": desc, "n": 0, "sizes": set()})
                r["n"] += 1
                r["sizes"].add("%dx%d" % (dims[0], dims[1]))
                r["len"] = max(r.get("len", 0), dims[2])
        if not rows:
            return
        sh = self.new_sheet("B401", "ຕາຕະລາງ ອົງປະກອບໂຄງສ້າງ", 50, kind="table")
        data = [[t, r["desc"][:30], ", ".join(sorted(r["sizes"]))[:24], str(r["len"]), str(r["n"])]
                for (c, t), r in sorted(rows.items())]
        cols = [("ລະຫັດ", 1500), ("ລາຍການ", 6500), ("ໜ້າຕັດ bbox mm", 4200), ("ຍາວ/ສູງ mm", 2200), ("ຈຳນວນ", 1500)]
        half = (len(data) + 1) // 2 if len(data) > 26 else len(data)
        self.table(sh["x"] + 900, sh["y"] + 13400, cols, data[:half], 150)
        if data[half:]:
            self.table(sh["x"] + 900 + 16300, sh["y"] + 13400, cols, data[half:], 150)
        self.view_title(sh, sh["x"] + 10500, sh["y"] + 3050, "ຕາຕະລາງ ອົງປະກອບໂຄງສ້າງ", 50)
        self.note(sh, "ຂະໜາດຈາກ bounding box ຂອງ component (ບໍ່ແມ່ນຂະໜາດໜ້າຕັດອອກແບບ) — "
                      "ວິສະວະກອນຕ້ອງກຳນົດ ແລະ ຢັ້ງຢືນ ໜ້າຕັດ, ເຫຼັກເສີມ, ຊັ້ນຄອນກຣີດ")

    def schedule_sheet(self):
        sh = self.new_sheet("A401", "ຕາຕະລາງ ປະຕູ ແລະ ປ່ອງຢ້ຽມ", 50, kind="table")
        x, y = sh["x"] + 1500, sh["y"] + 13500
        agg = {}
        for o in self.openings:
            a = agg.setdefault(o["tag"], dict(o, n=0))
            a["n"] += 1
        rows = [[t, a["name"][:28], str(a["w"]), str(a["h"]), str(a["sill"]), str(a["n"])]
                for t, a in sorted(agg.items(), key=lambda kv: (kv[0].rstrip('0123456789'), int('0' + kv[0][len(kv[0].rstrip('0123456789')):])))]
        if not rows:
            rows = [["-", "ບໍ່ພົບ component ປະຕູ/ປ່ອງຢ້ຽມ", "", "", "", ""]]
        cols = [("ລະຫັດ", 1500), ("ຊື່ (SketchUp)", 6500), ("ກວ້າງ mm", 2000), ("ສູງ mm", 2000),
                ("ລະດັບລຸ່ມ mm", 2200), ("ຈຳນວນ", 1500)]
        self.table(x, y, cols, rows, 180)
        self.view_title(sh, sh["x"] + 10500, sh["y"] + 3450, "ຕາຕະລາງ ປະຕູ ແລະ ປ່ອງຢ້ຽມ", 50)
        self.note(sh, "ຂະໜາດອ່ານຈາກ bounding box ຂອງ component ໃນ SketchUp — ກວດກາໜ້າງານກ່ອນສັ່ງຜະລິດ")


def main():
    src, proj_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    ox = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    oy = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
    model = json.load(open(src, encoding="utf-8"))
    project = json.load(open(proj_path, encoding="utf-8"))
    project.setdefault("engineer_note", "ໝາຍເຫດ: ແຜ່ນນີ້ສ້າງຈາກໂມເດວ — ວິສະວະກອນຕ້ອງກວດກາ, ຄຳນວນ ແລະ ຢັ້ງຢືນກ່ອນນຳໃຊ້")
    project["done_flag"] = os.path.abspath(out + ".done")
    if os.path.exists(project["done_flag"]):
        os.remove(project["done_flag"])
    b = SetBuilder(model, project, (ox, oy))
    lsp = b.build()
    open(out, "w", encoding="ascii").write(lsp)
    meta = {"sheets": b.sheets, "warnings": b.warnings, "rotate": b.rotate, "grids": b.grids, "levels": b.levels,
            "openings": len(b.openings), "done_flag": project["done_flag"]}
    json.dump(meta, open(out + ".sheets.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"sheets": [(s["no"], s["scale"]) for s in b.sheets], "grids": [len(g) for g in b.grids],
                      "openings": len(b.openings), "rotate": b.rotate, "lsp_kb": len(lsp) // 1024}, ensure_ascii=False))


if __name__ == "__main__":
    main()
