"""Generate an internal AutoLISP batch for a new, explicitly identified drawing."""
from __future__ import annotations

import json
import math

from .geometry import point


def string(value):
    return json.dumps(str(value), ensure_ascii=False)


def number(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('Non-finite AutoLISP number')
    return repr(value)


def xyz(value):
    p = point(value)
    return "'(\u0020" + ' '.join(number(v) for v in (*p, 0)) + ')'


def poly(value):
    return "'(" + ' '.join('(' + ' '.join(number(v) for v in point(p)) + ')' for p in value) + ')'


HELPERS = r'''
(vl-load-com)
(defun lpc-live-json-string (s / out n)
 (setq out "\"")
 (foreach n (vl-string->list s)
  (setq out (strcat out (cond ((= n 34) "\\\"") ((= n 92) "\\\\")
   ((= n 10) "\\n") ((= n 13) "\\r") ((= n 9) "\\t") (T (chr n))))))
 (strcat out "\""))
(defun lpc-live-num (n) (vl-princ-to-string n))
(defun lpc-live-xyz-json (p) (strcat "[" (lpc-live-num (car p)) "," (lpc-live-num (cadr p)) "," (lpc-live-num (if (caddr p) (caddr p) 0.0)) "]"))
(defun lpc-live-bool (b) (if b "true" "false"))
(defun lpc-live-layer (name color weight / layers e)
 (setq layers (vla-get-Layers lpc-live-doc) e (vl-catch-all-apply 'vla-Item (list layers name)))
 (if (vl-catch-all-error-p e) (setq e (vla-Add layers name)))
 (vla-put-Color e color) (vla-put-Lineweight e weight) e)
(defun lpc-live-line (a b layer / e)
 (setq e (vla-AddLine lpc-live-ms (vlax-3d-point a) (vlax-3d-point b)))
 (vla-put-Layer e layer) e)
(defun lpc-live-poly (points layer / values array e)
 (setq values (apply 'append points) array (vlax-make-safearray vlax-vbDouble (cons 0 (1- (length values)))))
 (vlax-safearray-fill array values)
 (setq e (vla-AddLightWeightPolyline lpc-live-ms array))
 (vla-put-Closed e :vlax-true) (vla-put-Layer e layer) e)
(defun lpc-live-solid (outer holes outline fill / boundary h array inner)
 (setq boundary (lpc-live-poly outer outline) h (vla-AddHatch lpc-live-ms 0 "SOLID" :vlax-true))
 (setq array (vlax-make-safearray vlax-vbObject '(0 . 0)))
 (vlax-safearray-put-element array 0 boundary) (vla-AppendOuterLoop h array)
 (foreach points holes
  (setq inner (lpc-live-poly points outline))
  (vlax-safearray-put-element array 0 inner) (vla-AppendInnerLoop h array))
 (vla-put-Layer h fill) (vla-Evaluate h) h)
(defun lpc-live-text (text p height layer / e)
 (setq e (vla-AddText lpc-live-ms text (vlax-3d-point p) height))
 (vla-put-Layer e layer) (vla-put-StyleName e "LPC-LIVE-TEXT")
 (vla-put-Alignment e 10) (vla-put-TextAlignmentPoint e (vlax-3d-point p)) e)
(defun lpc-live-dim (a b p rotation / e)
 (setq e (vla-AddDimAligned lpc-live-ms (vlax-3d-point a) (vlax-3d-point b) (vlax-3d-point p)))
 (vla-put-Layer e "A-DIMS") (vla-put-TextStyle e "LPC-LIVE-TEXT")
 (vla-put-TextHeight e 240.0) (vla-put-ArrowheadSize e 110.0)
 (vla-put-ScaleFactor e 1.0) (vla-put-LinearScaleFactor e 1.0)
 (vla-put-TextGap e 70.0) (vla-put-ExtensionLineOffset e 80.0)
 (vla-put-ExtensionLineExtend e 120.0) (vla-put-PrimaryUnitsPrecision e 0)
 (vla-put-TextFill e :vlax-false) (vla-put-TextRotation e rotation)
 (vla-put-TextPosition e (vlax-3d-point p)) e)
(defun lpc-live-order (/ dict table layer ss objects i array)
 (setq dict (vla-GetExtensionDictionary lpc-live-ms)
  table (vl-catch-all-apply 'vla-Item (list dict "ACAD_SORTENTS")))
 (if (vl-catch-all-error-p table) (setq table (vla-AddObject dict "ACAD_SORTENTS" "AcDbSortentsTable")))
 (foreach layer '("A-WALL-POCHE" "A-WALL" "S-COLUMN-POCHE" "S-COLUMN")
  (setq ss (ssget "_X" (list (cons 8 layer) '(410 . "Model"))) objects nil i 0)
  (if ss (progn
   (repeat (sslength ss) (setq objects (cons (vlax-ename->vla-object (ssname ss i)) objects) i (1+ i)))
   (setq array (vlax-make-safearray vlax-vbObject (cons 0 (1- (length objects)))))
   (vlax-safearray-fill array objects) (vla-MoveToTop table array))))
 table)
(defun lpc-live-entity-json (e / typ base coordinates points pairs)
 (setq typ (vla-get-ObjectName e)
  base (strcat "{\"handle\":" (lpc-live-json-string (vla-get-Handle e))
   ",\"type\":" (lpc-live-json-string typ) ",\"layer\":" (lpc-live-json-string (vla-get-Layer e))))
 (cond
  ((= typ "AcDbLine")
   (setq base (strcat base ",\"a\":" (lpc-live-xyz-json (vlax-get e 'StartPoint)) ",\"b\":" (lpc-live-xyz-json (vlax-get e 'EndPoint)))))
  ((= typ "AcDbPolyline")
   (setq coordinates (vlax-get e 'Coordinates) points "" pairs "")
   (while coordinates
    (setq points (strcat points pairs "[" (lpc-live-num (car coordinates)) "," (lpc-live-num (cadr coordinates)) "]") pairs "," coordinates (cddr coordinates)))
   (setq base (strcat base ",\"points\":[" points "],\"closed\":" (lpc-live-bool (= :vlax-true (vla-get-Closed e))))))
  ((= typ "AcDbHatch") (setq base (strcat base ",\"area\":" (lpc-live-num (vla-get-Area e)))))
  ((= typ "AcDbAlignedDimension")
   (setq base (strcat base ",\"measurement\":" (lpc-live-num (vla-get-Measurement e))
    ",\"p1\":" (lpc-live-xyz-json (vlax-get e 'ExtLine1Point)) ",\"p2\":" (lpc-live-xyz-json (vlax-get e 'ExtLine2Point))
    ",\"height\":" (lpc-live-num (vla-get-TextHeight e)) ",\"scale\":" (lpc-live-num (vla-get-ScaleFactor e))
    ",\"linear_scale\":" (lpc-live-num (vla-get-LinearScaleFactor e)) ",\"override\":" (lpc-live-json-string (vla-get-TextOverride e)))))
  ((= typ "AcDbText") (setq base (strcat base ",\"text\":" (lpc-live-json-string (vla-get-TextString e)) ",\"height\":" (lpc-live-num (vla-get-Height e)) ",\"position\":" (lpc-live-xyz-json (vlax-get e 'TextAlignmentPoint)))))
  ((= typ "AcDbCircle") (setq base (strcat base ",\"centre\":" (lpc-live-xyz-json (vlax-get e 'Center)) ",\"radius\":" (lpc-live-num (vla-get-Radius e))))))
 (strcat base "}"))
(defun lpc-live-snapshot (path table / f comma e order layout vp)
 (setq f (open path "w" "utf8") comma "")
 (write-line (strcat "{\"run_id\":" (lpc-live-json-string lpc-live-run)
  ",\"drawing\":" (lpc-live-json-string (vla-get-FullName lpc-live-doc))
  ",\"units\":" (itoa (getvar "INSUNITS")) ",\"saved\":" (lpc-live-bool (= :vlax-true (vla-get-Saved lpc-live-doc)))
  ",\"entities\":[") f)
 (vlax-for e lpc-live-ms (write-line (strcat comma (lpc-live-entity-json e)) f) (setq comma ","))
 (write-line "],\"order\":[" f) (setq comma "")
 (vla-GetFullDrawOrder table 'order 0)
 (foreach e (vlax-safearray->list order) (write-line (strcat comma (lpc-live-json-string (vla-get-Handle e))) f) (setq comma ","))
 (write-line "],\"layers\":[" f) (setq comma "")
 (vlax-for e (vla-get-Layers lpc-live-doc)
  (write-line (strcat comma "{\"name\":" (lpc-live-json-string (vla-get-Name e))
   ",\"weight\":" (itoa (vla-get-Lineweight e)) ",\"linetype\":" (lpc-live-json-string (vla-get-Linetype e)) ",\"on\":" (lpc-live-bool (= :vlax-true (vla-get-LayerOn e))) "}") f) (setq comma ","))
 (write-line "],\"viewports\":[" f) (setq comma "")
 (if lpc-live-sheet (vlax-for vp (vla-get-Block lpc-live-sheet)
  (if (and (= (vla-get-ObjectName vp) "AcDbViewport") (/= (vla-get-Layer vp) "0"))
   (progn (write-line (strcat comma "{\"scale\":" (lpc-live-num (vla-get-CustomScale vp))
    ",\"locked\":" (lpc-live-bool (= :vlax-true (vla-get-DisplayLocked vp))) "}") f) (setq comma ",")))))
 (write-line "]}" f) (close f))
'''


def render(plan, drawing_name, output, snapshot_path, receipt_path, run_id):
    """The script refuses existing drawings, existing output files and nonempty models."""
    header = HELPERS
    points = [p for line in plan['lines'] for p in (line['a'],line['b'])]
    points += [p for s in plan['solids'] for p in s['outer']]
    points += [d['position'] for d in plan['dimensions']]
    points += [t['position'] for t in plan['labels']]
    if plan.get('grid'):
        g = plan['grid']
        points += [(float(g['x'][0]['value'])-1820, float(g['y'][0]['value'])-1820),
                   (float(g['x'][-1]['value'])+1820, float(g['y'][-1]['value'])+1820)]
    lo = [min(p[k] for p in points) for k in (0,1)]
    hi = [max(p[k] for p in points) for k in (0,1)]
    if plan.get('sheet') and (hi[0]-lo[0]+1000 > 39200 or hi[1]-lo[1]+1000 > 23400):
        raise ValueError('Plan does not fit A3 at 1:100; change the explicitly verified scope')
    body = [
        f'(setq lpc-live-run {string(run_id)} lpc-live-receipt {string(str(receipt_path).replace(chr(92), "/"))} lpc-live-stage "preflight")',
        '(setq lpc-live-doc (vla-get-ActiveDocument (vlax-get-acad-object)) lpc-live-ms (vla-get-ModelSpace lpc-live-doc) lpc-live-sheet nil)',
        '(setq lpc-live-old-error *error*)',
        '(defun *error* (msg / f) (setq f (open lpc-live-receipt "w" "utf8")) (if f (progn (write-line (strcat "{" (lpc-live-json-string "run_id") ":" (lpc-live-json-string lpc-live-run) "," (lpc-live-json-string "status") ":" (lpc-live-json-string "FAILED") "," (lpc-live-json-string "stage") ":" (lpc-live-json-string lpc-live-stage) "," (lpc-live-json-string "error") ":" (lpc-live-json-string msg) "}") f) (close f))) (setq *error* lpc-live-old-error) (princ msg) (princ))',
        f'(if (or (/= (getvar "DWGNAME") {string(drawing_name)}) (/= (vla-get-Count lpc-live-ms) 0)) (error "Wrong or nonempty target drawing"))',
        f'(if (findfile {string(str(output).replace(chr(92), "/"))}) (error "Output drawing already exists"))',
        '(setvar "TILEMODE" 1) (setvar "INSUNITS" 4) (setvar "MEASUREMENT" 1) (setvar "LWDISPLAY" 1)',
        '(setq lpc-live-stage "font" lpc-live-style (vla-Add (vla-get-TextStyles lpc-live-doc) "LPC-LIVE-TEXT"))',
        f'(vla-put-FontFile lpc-live-style {string(plan["font_file"])}) (vla-put-Height lpc-live-style 0.0)',
        f'(setq lpc-live-centre {xyz([(lo[0]+hi[0])/2, (lo[1]+hi[1])/2])})',
    ]
    weights = {'A-WALL':35,'S-COLUMN':35,'A-WALL-POCHE':25,'S-COLUMN-POCHE':25,'A-DIMS':18,'A-ROOMS':18,'A-DOOR':25,'A-GRID':9,'A-GRID-LABELS':18,'A-SHEET':18,'A-VPORT':9}
    all_layers = {l['layer'] for l in plan['lines']} | set(weights)
    for layer in sorted(all_layers):
        color = 2 if layer == 'S-COLUMN' else 1 if layer == 'S-COLUMN-POCHE' else 7
        body.append(f'(lpc-live-layer {string(layer)} {color} {weights.get(layer,13)})')
    body.append('(setq lpc-live-stage "geometry")')
    for line in plan['lines']:
        body.append(f'(lpc-live-line {xyz(line["a"])} {xyz(line["b"])} {string(line["layer"])})')
    for solid in plan['solids']:
        holes = "'(" + ' '.join(poly(h)[1:] for h in solid['holes']) + ')'
        body.append(f'(lpc-live-solid {poly(solid["outer"])} {holes} {string(solid["layer"])} {string(solid["layer"]+"-POCHE")})')
    for dim in plan['dimensions']:
        angle = math.atan2(dim['p2'][1]-dim['p1'][1], dim['p2'][0]-dim['p1'][0])
        if angle > math.pi/2: angle -= math.pi
        if angle < -math.pi/2: angle += math.pi
        body.append(f'(lpc-live-dim {xyz(dim["p1"])} {xyz(dim["p2"])} {xyz(dim["position"])} {number(angle)})')
    for label in plan['labels']:
        body.append(f'(lpc-live-text {string(label["text"])} {xyz(label["position"])} {number(label["height"])} {string(label["layer"])})')
    grid = plan.get('grid')
    if grid:
        x0, x1 = float(grid['x'][0]['value'])-1600, float(grid['x'][-1]['value'])+1600
        y0, y1 = float(grid['y'][0]['value'])-1600, float(grid['y'][-1]['value'])+1600
        body.extend(['(if (vl-catch-all-error-p (vl-catch-all-apply \'vla-Item (list (vla-get-Linetypes lpc-live-doc) "CENTER2"))) (vla-Load (vla-get-Linetypes lpc-live-doc) "CENTER2" "acadiso.lin"))',
                     '(vla-put-Linetype (vla-Item (vla-get-Layers lpc-live-doc) "A-GRID") "CENTER2")'])
        for axis in ('x','y'):
            for item in grid[axis]:
                v = float(item['value'])
                a,b = (([v,y0],[v,y1]) if axis=='x' else ([x0,v],[x1,v]))
                body.append(f'(vla-put-LinetypeScale (lpc-live-line {xyz(a)} {xyz(b)} "A-GRID") 25.0)')
                for p in (a,b):
                    body.append(f'(vla-put-Layer (vla-AddCircle lpc-live-ms (vlax-3d-point {xyz(p)}) 220.0) "A-GRID-LABELS")')
                    body.append(f'(lpc-live-text {string(item["label"])} {xyz(p)} 240.0 "A-GRID-LABELS")')
    if plan.get('sheet'):
        body.append('(setq lpc-live-stage "sheet")')
        body.extend(_sheet())
    body.extend([
        '(setq lpc-live-table (lpc-live-order))',
        '(setq lpc-live-stage "save")',
        '(setvar "TILEMODE" 1) (command "_.REGEN" "_.ZOOM" "_E")',
        f'(if (findfile {string(str(output).replace(chr(92), "/"))}) (error "Output drawing appeared; refusing overwrite"))',
        f'(vla-SaveAs lpc-live-doc {string(str(output).replace(chr(92), "/"))})',
        '(setq lpc-live-stage "actual-readback")',
        f'(lpc-live-snapshot {string(str(snapshot_path).replace(chr(92), "/"))} lpc-live-table)',
        '(setq lpc-live-f (open lpc-live-receipt "w" "utf8"))',
        '(write-line (strcat "{" (lpc-live-json-string "run_id") ":" (lpc-live-json-string lpc-live-run) "," (lpc-live-json-string "status") ":" (lpc-live-json-string "DONE") "}") lpc-live-f) (close lpc-live-f)',
        '(setq *error* lpc-live-old-error)',
        '(princ "LPC_LIVE_DONE") (princ)',
    ])
    # A single guarded expression stops the batch at the first failure.
    return header + '\n(progn\n' + '\n'.join(body) + '\n)\n'


def _sheet():
    return [
        '(setq lpc-live-sheet (vla-Add (vla-get-Layouts lpc-live-doc) "A-101"))',
        '(vla-put-ConfigName lpc-live-sheet "DWG To PDF.pc3") (vla-RefreshPlotDeviceInfo lpc-live-sheet)',
        '(vla-put-CanonicalMediaName lpc-live-sheet "ISO_full_bleed_A3_(420.00_x_297.00_MM)")',
        '(vla-put-PaperUnits lpc-live-sheet 1) (vla-put-PlotRotation lpc-live-sheet 0) (vla-put-PlotType lpc-live-sheet 5)',
        '(vla-put-UseStandardScale lpc-live-sheet :vlax-true) (vla-put-StandardScale lpc-live-sheet 16)',
        '(vla-put-StyleSheet lpc-live-sheet "monochrome.ctb") (vla-put-PlotWithPlotStyles lpc-live-sheet :vlax-true)',
        '(vla-put-PlotWithLineweights lpc-live-sheet :vlax-true)',
        '(vla-put-ActiveLayout lpc-live-doc lpc-live-sheet) (setvar "TILEMODE" 0)',
        '(setq lpc-live-paper (vla-get-PaperSpace lpc-live-doc) lpc-live-delete nil)',
        '(vlax-for e lpc-live-paper (if (and (= (vla-get-ObjectName e) "AcDbViewport") (> (cdr (assoc 69 (entget (vlax-vla-object->ename e)))) 1)) (setq lpc-live-delete (cons e lpc-live-delete))))',
        '(foreach e lpc-live-delete (vla-Delete e))',
        '(foreach pair \'(((10 10 0) (410 10 0)) ((410 10 0) (410 287 0)) ((410 287 0) (10 287 0)) ((10 287 0) (10 10 0)) ((10 43 0) (410 43 0))) (vla-put-Layer (vla-AddLine lpc-live-paper (vlax-3d-point (car pair)) (vlax-3d-point (cadr pair))) "A-SHEET"))',
        '(vla-put-Layer (vla-AddText lpc-live-paper "A-101 | MODEL PLAN | 1:100 @ A3 | DRAFT / QA REQUIRED" (vlax-3d-point \'(16 26 0)) 3.0) "A-SHEET")',
        '(vla-put-Plottable (vla-Item (vla-get-Layers lpc-live-doc) "A-VPORT") :vlax-false)',
        '(setq lpc-live-vp (vla-AddPViewport lpc-live-paper (vlax-3d-point \'(210 163 0)) 392.0 234.0))',
        '(vla-put-Layer lpc-live-vp "A-VPORT") (vla-put-Direction lpc-live-vp (vlax-3d-point \'(0 0 1)))',
        '(vla-put-Target lpc-live-vp (vlax-3d-point lpc-live-centre)) (vla-Display lpc-live-vp :vlax-true)',
        '(vla-put-CustomScale lpc-live-vp 0.01) (vla-put-DisplayLocked lpc-live-vp :vlax-true)',
    ]
