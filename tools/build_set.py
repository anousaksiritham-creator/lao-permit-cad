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
AREA = (1500.0, 5600.0, 40500.0, 28200.0)     # drawing area inside frame, frame units
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
    "A-ANNO-TABL": (7, 18, "Continuous"),
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
                key = (k["name"], round(w / 10) * 10, round(h / 10) * 10)
                if key not in types:
                    types[key] = "%s%d" % (prefix, len(types) + 1)
                res.append({"tag": types[key], "name": k["name"], "w": round(w), "h": round(h),
                            "sill": round(k["min"][2] - (self.levels[1][1] if len(self.levels) > 1 else 0)),
                            "x": (k["min"][0] + k["max"][0]) / 2, "y": (k["min"][1] + k["max"][1]) / 2})
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
    def pick_scale(self, w, h, allowed=(50, 75, 100, 200)):
        for sc in allowed:
            f = sc / 100.0
            if w <= (AREA[2] - AREA[0]) * f * 0.92 and h <= (AREA[3] - AREA[1]) * f * 0.85:
                return sc
        return allowed[-1]

    def new_sheet(self, no, title, scale):
        f = scale / 100.0
        x, y = self.cursor, self.oy
        self.cursor += FRAME_W * f + GAP
        attrs = {"PROJECT": self.p["name"], "LOCATION": self.p.get("location", ""), "OWNER": self.p.get("owner", ""),
                 "DESIGNER": self.p.get("designer", ""), "DATE": self.p.get("date", ""),
                 "TITLE": title, "SHEETNO": no, "SCALE": "1:%d" % scale}
        self.L.frame(x, y, f, attrs)
        sh = {"no": no, "title": title, "scale": scale, "x": x, "y": y, "w": FRAME_W * f, "h": FRAME_H * f}
        self.sheets.append(sh)
        return sh

    def place(self, sh, segs, cx=None, cy=None):
        """Centre geometry (sheet-independent coords) in the sheet's drawing area; returns offset."""
        f = sh["scale"] / 100.0
        x0, y0, x1, y1 = bbox(segs)
        acx = sh["x"] + (AREA[0] + AREA[2]) / 2 * f if cx is None else cx
        acy = sh["y"] + (AREA[1] + AREA[3]) / 2 * f + 300 * f if cy is None else cy
        dx, dy = acx - (x0 + x1) / 2, acy - (y0 + y1) / 2
        for a, b, c, d, lay in merge_collinear(segs):
            self.L.line(a + dx, b + dy, c + dx, d + dy, lay)
        return dx, dy

    def view_title(self, sh, x, y, title, scale):
        f = sh["scale"] / 100.0
        h = 4.0 * sh["scale"]
        self.L.text(x, y, h, title, "A-ANNO-TEXT", 2)
        self.L.line(x - 6000 * f, y - h * 0.9, x + 6000 * f, y - h * 0.9, "A-ANNO-TTLB")
        self.L.text(x, y - h * 1.3, h * 0.6, "ມາດຕາສ່ວນ 1:%d" % scale, "A-ANNO-TEXT", 2)

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
        nums = [str(i + 1) for i in range(len(gx))]
        lets = [chr(65 + i) for i in range(len(gy))]
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
        xs = sorted(set([mnx] + gx + [mxx]))
        ys = sorted(set([mny] + gy + [mxy]))
        # dimension chains along model X (below model min Y) and along model Y (left of model min X)
        for row, chain in enumerate((gx and [mnx] + gx + [mxx], [mnx, mxx])):
            if not chain:
                continue
            off = mny - 1500 - (row + 1) * step
            for a, b in zip(chain, chain[1:]):
                if b - a < 50:
                    continue
                self.dim_model((a, mny), (b, mny), (a, off), dx, dy, scale)
        for row, chain in enumerate((gy and [mny] + gy + [mxy], [mny, mxy])):
            if not chain:
                continue
            off = mnx - 1500 - (row + 1) * step
            for a, b in zip(chain, chain[1:]):
                if b - a < 50:
                    continue
                self.dim_model((mnx, a), (mnx, b), (off, a), dx, dy, scale)

    def dim_model(self, p1, p2, loc, dx, dy, scale):
        a, b, l = self.tplan(*p1), self.tplan(*p2), self.tplan(*loc)
        horiz = abs(b[0] - a[0]) >= abs(b[1] - a[1])
        self.L.dim(a[0] + dx, a[1] + dy, b[0] + dx, b[1] + dy, l[0] + dx, l[1] + dy, 0.0 if horiz else math.pi / 2, scale)

    def opening_tags(self, dx, dy, scale):
        for o in self.openings:
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
            if s["axis"] == "y":
                a, b = self.tplan(self.fp[0][0] - 2500, at), self.tplan(self.fp[1][0] + 2500, at)
            else:
                a, b = self.tplan(at, self.fp[0][1] - 2500), self.tplan(at, self.fp[1][1] + 2500)
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
    def plan_sheet(self, no, title, segs, extra=None, dims=True, tags=True, sections=True, scale=None, note=None):
        bb = bbox(segs)
        sc = scale or self.pick_scale(bb[2] - bb[0] + 30 * 75, bb[3] - bb[1] + 30 * 75)
        sh = self.new_sheet(no, title, sc)
        dx, dy = self.place(sh, segs)
        if extra:
            for a, b, c, d, lay in extra:
                self.L.line(a + dx, b + dy, c + dx, d + dy, lay)
        self.grid_annot(sh, dx, dy, bb, sc)
        if dims:
            self.plan_dims(dx, dy, sc)
        if tags:
            self.opening_tags(dx, dy, sc)
        if sections:
            self.section_marks(dx, dy, sc)
        self.north_arrow(sh)
        f = sc / 100.0
        self.view_title(sh, sh["x"] + 21000 * f, sh["y"] + 6900 * f, title, sc)
        if note:
            self.note(sh, note)
        return sh

    def elev_sheet(self, no, title, segs, levels=True):
        bb = bbox(segs)
        sc = self.pick_scale(bb[2] - bb[0] + 40 * 75, bb[3] - bb[1] + 20 * 75)
        sh = self.new_sheet(no, title, sc)
        # ground line
        g = [(bb[0] - 1500, 0, bb[2] + 1500, 0, "A-GRND")]
        dx, dy = self.place(sh, segs + g)
        if levels:
            self.levels_elev(dx, dy, bb[2] + 1500, sc)
        f = sc / 100.0
        self.view_title(sh, sh["x"] + 21000 * f, sh["y"] + 6900 * f, title, sc)
        return sh

    def cover(self, index):
        sc = 100
        sh = self.new_sheet("A101", "ໜ້າປົກ ແລະ ສາລະບານ", sc)
        x, y = sh["x"], sh["y"]
        self.L.text(x + 21000, y + 25500, 1200, self.p["name"], "A-ANNO-TEXT", 2)
        self.L.text(x + 21000, y + 23600, 700, self.p.get("subtitle", ""), "A-ANNO-TEXT", 2)
        self.L.text(x + 21000, y + 22300, 450, self.p.get("location", ""), "A-ANNO-TEXT", 2)
        cols = [("ເລກແຜ່ນ", 3500), ("ຊື່ແຜ່ນ", 13000), ("ມາດຕາສ່ວນ", 3500)]
        half = (len(index) + 1) // 2
        for k, part in enumerate((index[:half], index[half:])):
            if part:
                self.table(x + 1800 + k * 20000, y + 20500, cols, [[a, b, c] for a, b, c in part], 280)
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
        self.plan_sheet("A201", "ແຜນຜັງ ຊັ້ນ 1", self.plan_segs(plan["segs"], codes=None))
        self.plan_sheet("A202", "ແຜນຜັງ ບອກໄລຍະ ແລະ ປະຕູ-ປ່ອງຢ້ຽມ",
                        self.plan_segs(plan["segs"], codes=None, kinds={"cut"}) +
                        self.plan_segs(plan["segs"], codes={"03", "13", "10", "11"}, kinds={"beyond"}))
        self.plan_sheet("A203", "ແຜນຜັງ ຫຼັງຄາ", self.plan_segs(m["views"]["top"]["segs"]), tags=False, sections=False)
        # --- A3 elevations + sections
        names = {"front": ("A301", "ຮູບດ້ານໜ້າ"), "back": ("A302", "ຮູບດ້ານຫຼັງ"),
                 "left": ("A303", "ຮູບດ້ານຊ້າຍ"), "right": ("A304", "ຮູບດ້ານຂວາ")}
        for k, (no, t) in names.items():
            self.elev_sheet(no, t, self.elev_segs(m["views"][k]["segs"]))
        for i, s in enumerate(m.get("sections", [])):
            self.elev_sheet("A31%d" % (i + 1), "ຮູບຕັດ %s" % s["name"], self.elev_segs(s["segs"]))
        # --- A4 schedule
        self.schedule_sheet()
        # --- B structure
        found = next((p for p in m["plans"] if p["z"] < 300), None)
        if found:
            self.plan_sheet("B101", "ແຜນຜັງ ຮາກຖານ ແລະ ຄານຄໍດິນ",
                            self.plan_segs(found["segs"], codes={"00", "01", "02", "03", "04", "18"}),
                            tags=False, sections=False, note=self.p["engineer_note"])
        xr = m["views"].get("top_xray", {}).get("segs", [])
        if xr:
            self.plan_sheet("B201", "ແຜນຜັງ ໂຄງຫຼັງຄາ (ເສົາ, ຄານ, ແປ)",
                            self.plan_segs(xr, codes={"04", "05", "06"}), tags=False, sections=False,
                            note=self.p["engineer_note"])
            walls = self.plan_segs(plan["segs"], codes={"04", "08", "10", "11"}, kinds={"cut"})
            self.plan_sheet("E101", "ແຜນຜັງ ໄຟຟ້າ ແສງສະຫວ່າງ",
                            walls + self.plan_segs(xr, codes={"19"}), tags=False, sections=False,
                            note=self.p["engineer_note"])
            self.plan_sheet("P101", "ແຜນຜັງ ລະບົບນ້ຳ ແລະ ສຸຂະພັນ",
                            walls + self.plan_segs(xr, codes={"14", "15"}), tags=False, sections=False,
                            note=self.p["engineer_note"])
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

    def schedule_sheet(self):
        sh = self.new_sheet("A401", "ຕາຕະລາງ ປະຕູ ແລະ ປ່ອງຢ້ຽມ", 50)
        x, y = sh["x"] + 1500, sh["y"] + 13500
        agg = {}
        for o in self.openings:
            a = agg.setdefault(o["tag"], dict(o, n=0))
            a["n"] += 1
        rows = [[t, a["name"][:28], str(a["w"]), str(a["h"]), str(a["sill"]), str(a["n"])]
                for t, a in sorted(agg.items(), key=lambda kv: (kv[0][0], int(kv[0][1:])))]
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
    project.setdefault("done_flag", out + ".done")
    if os.path.exists(project["done_flag"]):
        os.remove(project["done_flag"])
    b = SetBuilder(model, project, (ox, oy))
    lsp = b.build()
    open(out, "w", encoding="ascii").write(lsp)
    meta = {"sheets": b.sheets, "rotate": b.rotate, "grids": b.grids, "levels": b.levels,
            "openings": len(b.openings), "done_flag": project["done_flag"]}
    json.dump(meta, open(out + ".sheets.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"sheets": [(s["no"], s["scale"]) for s in b.sheets], "grids": [len(g) for g in b.grids],
                      "openings": len(b.openings), "rotate": b.rotate, "lsp_kb": len(lsp) // 1024}, ensure_ascii=False))


if __name__ == "__main__":
    main()
