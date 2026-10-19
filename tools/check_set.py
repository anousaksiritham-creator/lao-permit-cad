"""check_set.py - QA for a built set: sheet list, index, scales, fit, empty sheets, levels,
openings vs schedule, engineering-note presence. Exit code 1 when an error is found.

python -I check_set.py <set.lsp.sheets.json> <model.json> [qa.json]
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drawing_qa import validate_model

ALLOWED = {20, 25, 40, 50, 75, 100, 200}


def main():
    meta = json.load(open(sys.argv[1], encoding="utf-8"))
    model = json.load(open(sys.argv[2], encoding="utf-8"))
    out = sys.argv[3] if len(sys.argv) > 3 else None
    errors, warns, info = [], list(meta.get("warnings", [])), []
    source_qa = validate_model(model, {})
    errors.extend(source_qa['errors'])
    warns.extend(source_qa['warnings'])
    sheets = meta["sheets"]
    nos = [s["no"] for s in sheets]
    if len(nos) != len(set(nos)):
        errors.append("duplicate sheet numbers: %s" % sorted({n for n in nos if nos.count(n) > 1}))
    if not nos or nos[0] != "A101":
        errors.append("cover sheet A101 missing or not first")
    for s in sheets:
        if s["scale"] not in ALLOWED:
            errors.append("%s: unusual scale 1:%s" % (s["no"], s["scale"]))
        if s.get("kind") != "table" and s.get("lines", 0) < 20:
            errors.append("%s: almost empty (%d lines)" % (s["no"], s.get("lines", 0)))
    # sheets overlap each other?
    for a, b in zip(sheets, sheets[1:]):
        if a["x"] + a["w"] > b["x"] and abs(a["y"] - b["y"]) < 1:
            errors.append("%s overlaps %s" % (a["no"], b["no"]))
    # levels: increasing and unique names
    lv = meta.get("levels", [])
    vals = [v for _, v in lv]
    if vals != sorted(vals):
        warns.append("levels not increasing: %s" % lv)
    names = [n for n, _ in lv]
    if len(names) != len(set(names)):
        errors.append("duplicate level names: %s" % names)
    # openings vs model
    def big(k):   # same filter as build_set.find_openings (frames/mullions < 300 mm are parts, not openings)
        w = max(k["max"][0] - k["min"][0], k["max"][1] - k["min"][1])
        return w >= 300 and k["max"][2] - k["min"][2] >= 300
    kids = sum(1 for o in model["objects"] if o.get("code") in ("10", "11") for k in o.get("children", []) if big(k))
    info.append("openings tagged %d of %d door/window components" % (meta.get("openings", 0), kids))
    if kids and meta.get("openings", 0) < kids * 0.8:
        warns.append("only %d of %d door/window components tagged (small parts skipped?)" % (meta.get("openings", 0), kids))
    gx, gy = meta.get("grids", [[], []])
    if not gx and not gy:
        warns.append("no column grid found (expects columns as children of the '04' component)")
    info.append("grids %d x %d, sheets %d" % (len(gx), len(gy), len(sheets)))
    # sections present
    if not model.get("sections"):
        warns.append("no sections extracted")
    res = {"errors": errors, "warnings": warns, "info": info, "readiness": "PRE_DESIGN_ONLY", "engineering_approval": False, "construction_release": False}
    if out:
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.stdout.reconfigure(encoding="utf-8")
    for k in ("errors", "warnings", "info"):
        for m in res[k]:
            print("%-8s %s" % (k[:-1].upper(), m))
    print("QA: %d error(s), %d warning(s)" % (len(errors), len(warns)))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
