"""merge_pdf.py - merge per-sheet PDFs in sheet order into one submission PDF with bookmarks.
python tools/merge_pdf.py <set.lsp.sheets.json> <pdf dir> <out.pdf>      (needs: pip install --user pypdf)
"""
import json
import logging
import os
import sys

from pypdf import PdfWriter

logging.getLogger("pypdf").setLevel(logging.CRITICAL)   # AutoCAD PDFs carry odd metadata keys

meta = json.load(open(sys.argv[1], encoding="utf-8"))
w = PdfWriter()
for s in meta["sheets"]:
    p = os.path.join(sys.argv[2], s["no"] + ".pdf")
    if os.path.exists(p):
        w.append(p, outline_item="%s  %s" % (s["no"], s["title"]))
w.write(sys.argv[3])
print("merged %d sheets -> %s" % (len(meta["sheets"]), sys.argv[3]))
