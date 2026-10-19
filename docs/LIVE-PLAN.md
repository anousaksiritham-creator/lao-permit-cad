# Live plan + QA (v0.1)

## Update 2026-10-19: live unsaved by default

`draw` ບໍ່ບັງຄັບ `--output` ອີກແລ້ວ. ຖ້າບໍ່ລະບຸ output ຈະແຕ້ມໃນແຜ່ນໃໝ່ທີ່ຍັງບໍ່ save ໃນ AutoCAD:

```powershell
python -m tools.live_plan draw examples/live-plan/source.synthetic.json --config examples/live-plan/config.synthetic.json --work .live-runs
```

`--output new.dwg` ແມ່ນການຂໍ SaveAs ແບບ explicit; ຮັກສາການຫ້າມຂຽນທັບໄຟລ໌ເກົ່າ.
ສົ່ງຄຳສັ່ງ inline ຈາກ generated source ແທນ LOAD; ບໍ່ປ່ຽນ SECURELOAD ແລະບໍ່ເປີດ SCRIPT dialog.
ຜົນ QA ກວດ `save_policy` ໃນ unsaved mode; ບໍ່ໄດ້ຫຼຸດການກວດ source geometry, dimensions ຫຼື Draw Order.
ຫົວແກນຢູ່ນອກຈຸດ dimension ທີ່ໄກສຸດ. Dimension ໃຊ້ text 250 mm / arrow 150 mm ທີ່ model 1:1 ເປັນ drafting policy ສຳລັບກວດທີ່ 1:100, ບໍ່ແມ່ນຂໍ້ກຳນົດກົດໝາຍ.



ໂມດູນນີ້ເກັບຄວາມສາມາດຈາກວຽກແຕ້ມຈິງ: ດຶງ geometry ຈາກ SketchUp, ແຕ້ມ editable entities ໃນ **AutoCAD 2025 ໂດຍກົງ**, ແລະກວດ QA ຈາກ entities ທີ່ແຕ້ມແລ້ວ. ຜົນຫຼັກແມ່ນ drawing ທີ່ປາກົດໃນ AutoCAD; JSON/LISP ເປັນໄຟລ໌ພາຍໃນ.

ຮຸ່ນນີ້ເປັນ developer toolkit. ບໍ່ໄດ້ອ້າງວ່າທຸກໂມເດວຈະກາຍເປັນແບບກໍ່ສ້າງອັດຕະໂນມັດ. ມັນເປັນ workflow ຫຼັກສຳລັບ live geometry; pipeline `tools/build.ps1` ກໍໃຊ້ default ບໍ່ save ເຊັ່ນກັນ.

## ຕິດຕັ້ງ

- Python 3.10+; ການທົດສອບອອບລາຍບໍ່ຕ້ອງມີ CAD.
- ແຕ້ມຈິງ: Windows, AutoCAD 2025 ທີ່ເປີດຢູ່ ແລະມີ drawing ໜຶ່ງເປີດ, SketchUp 2025 ທີ່ເປີດໂມເດວທີ່ຕ້ອງການ.
- AutoCAD `LISPSYS=1` (ປ່ຽນຄ່ານີ້ແລ້ວຕ້ອງ restart AutoCAD); ໂມດູນບໍ່ປ່ຽນ/Restart ໃຫ້ເອງ.
- Font ຕ້ອງມີຢູ່ຈິງ. ຄ່າເລີ່ມຕົ້ນ `arial.ttf` ຈະຖືກຫາໃນ Windows Fonts. ສຳລັບປ້າຍລາວ ໃຫ້ກຳນົດ font ທີ່ຮອງຮັບພາສາລາວ ແລະກວດຮູບຕົວອັກສອນຈິງ.

```powershell
python -m pip install -r requirements-live.txt
python -m unittest discover -s tests -v
```

## ທົດສອບອອບລາຍ

```powershell
python -m tools.live_plan prepare examples/live-plan/source.synthetic.json --config examples/live-plan/config.synthetic.json --work .live-runs/prepared
```

ຄຳສັ່ງນີ້ກວດ units, source classification, ຮູບຕັດຝາ/ເສົາ, ການປັບຝາ, ຊ່ອງວ່າງ/ຮູຂອງ hatch ແລະການວາງ A3. ບໍ່ເປີດ ຫຼືແກ້ AutoCAD.

## ດຶງຈາກ SketchUp ທີ່ເປີດຢູ່

ອ່ານ model/session/units ຜ່ານ MCP ກ່ອນ, ແລ້ວໃນ Ruby Console:

```ruby
load 'C:/path/to/lao-permit-cad/tools/live_plan/semantic_extract.rb'
LaoPermitCad::SemanticExtract.export(
  path: 'C:/cad/scratch/source-001.json',
  cut_mm: 1500,
  expected_title: 'My model'
)
```

ການ `load` ບໍ່ເຮັດວຽກໃດຈົນກວ່າເອີ້ນ `export`. Export ອ່ານຜ່ານ SketchUp API; ບໍ່ແກ້ໂມເດວ ແລະບໍ່ຂຽນທັບ snapshot ເກົ່າ. ລະດັບຕັດແມ່ນ model Z ເປັນ mm. ເກັບ nested instance paths, hidden metadata, ຊື່, ພິກັດ world ແລະ revision context ໃນ path; ບໍ່ໃຊ້ bounding box ແທນເສັ້ນຈິງ.

ຂໍ້ຈຳກັດ: ພາກ below-cut ເປັນເສັ້ນຂອບຈິງທີ່ສາຍລົງພື້ນ; ຍັງບໍ່ເຮັດ hidden-line removal. ໜ້າທີ່ກົງກັບລະດັບຕັດພອດຈະມີຄຳເຕືອນ coplanar. ກວດພາບແລະເລືອກລະດັບຕັດທີ່ເໝາະສົມ.

## Config ທີ່ຢືນຢັນໄດ້

ເລີ່ມຈາກ `examples/live-plan/config.synthetic.json`. ຂໍ້ມູນຕົວຢ່າງແມ່ນສັງເຄາະ; ບໍ່ມີ geometry ຂອງໂຄງການຈິງ.

- `rules`: ordered regex ທຽບກັບຊື່ leaf group. `kind` ແມ່ນ `wall`, `column`, `door`, `glazing`, `access`, `fixture`, `floor`, `site`, `services`, `reference`. ກຸ່ມທີ່ບໍ່ກົງ rule ຈະເປັນ reference ແລະ QA UNVERIFIED.
- `exclude_source_ids`: ເລືອກ revision ທີ່ຈະບໍ່ນຳມາແຕ້ມ. Source ID ແມ່ນ path ຂອງ persistent IDs (`parent/child`), ຈຶ່ງບໍ່ປົນກັບ component instances ທີ່ໃຊ້ definition ຮ່ວມ.
- `wall_thickness_mm`: ບໍ່ໃສ່ = ຮັກສາຝາເດີມ. `100` ໃຊ້ໄດ້ເມື່ອຜູ້ໃຊ້ສັ່ງ. ຕ້ອງມີ `revision_evidence`; ຢ່າ classify ກະຈົກ, ເສົາ ຫຼືຝາຄອນກຣີດທາງລາດເປັນ masonry.
- `wall_axes`: `{ "source/path/id": 500 }` ປັບແນວກາງສະເພາະທີ່ອະນຸມັດ. `wall_ends`: `{ "id": [start_mm, end_mm] }` ປັບປາຍຕາມແນວຍາວ. ບໍ່ຄາດເດົາແນວເສົາໃຫ້ເອງ.
- ຝາປັບໄດ້ສະເພາະ axis-aligned rectangles ທີ່ກວດຂອບຕັດຈິງຄົບແລ້ວ. ຝາໂຄ້ງ/ຮູບຊັບຊ້ອນບໍ່ຖືກແທນດ້ວຍ box; ຖ້າຮັກສາຮູບເດີມຈະເກັບເສັ້ນ ແລະໝາຍ UNVERIFIED, ຖ້າຂໍປັບ thickness ຈະຢຸດໃຫ້ກວດ.
- `dimensions`: `p1`, `p2`, `position` ຈາກຈຸດທີ່ຢືນຢັນ. ຕ້ອງມີ `verified: true`, `evidence`. ບໍ່ຮັບ `value` ຫຼື `text_override` ເພື່ອປອມຄ່າ.
- `labels`: `text`, `position`, `verified`, `evidence`; ບໍ່ສ້າງຊື່ຫ້ອງເອງ.
- `grid`: `x`/`y` ເປັນລາຍການ `{ "value": 0, "label": "A" }`, ພ້ອມ `verified`/`evidence` ຢູ່ grid. ຕ້ອງກວດປ້າຍ/ແນວຈາກຕົ້ນສະບັບກ່ອນ; ບໍ່ເພີ່ມ grid ຖ້າບໍ່ມີຂໍ້ມູນ.
- `sheet`: v0.1 ຮອງຮັບ `{ "number": "A-101", "scale": 100 }`, A3 ແນວນອນ. ຖ້າບໍ່ພໍຈະຢຸດ ແທນທີ່ຈະຕັດແບບເງີຍໆ. ບໍ່ໃສ່ `sheet` ໄດ້ຖ້າຕ້ອງການ Model Space ເທົ່ານັ້ນ.

## ແຕ້ມໃນ AutoCAD

```powershell
python -m tools.live_plan draw C:/cad/scratch/source-001.json --config C:/cad/project/config.json --work .live-runs --output C:/cad/revisions/plan-R01.dwg
```

ຄຳສັ່ງນີ້ attach ສະເພາະ AutoCAD 2025 ທີ່ເປີດຢູ່. ອ່ານລາຍການ drawing/units ກ່ອນ, ສ້າງ drawing ໃໝ່ພຽງຄັ້ງດຽວ, ກວດວ່າ Model Space ວ່າງເປົ່າ, ແຕ້ມ entities, ຈັດ Draw Order, Save As ໄປຊື່ໃໝ່ ແລະ Zoom Extents. ບໍ່ເປີດ/ແກ້ແບບເກົ່າ. ຢ່າປ່ຽນ drawing ຫຼືໃຊ້ຄຳສັ່ງ CAD ລະຫວ່າງ batch.

ຂໍ້ມູນພາຍໃນ `.live-runs/<run-id>/`:

| ໄຟລ໌ | ເນື້ອໃນ |
|---|---|
| `before.json` | AutoCAD version, drawing names/paths, units/counts ກ່ອນແຕ້ມ |
| `plan.json` | source-derived geometry + approved revisions |
| `draw.lsp` | guarded batch ທີ່ສົ່ງພຽງຄັ້ງດຽວ |
| `run.json`, `receipt.json` | run identity, submission state, completion/error stage |
| `actual.json` | geometry, hatch area, dimensions/witnesses, layers, Draw Order, viewport ຈາກ CAD ຈິງ |
| `qa.json` | PASS/FAIL/UNVERIFIED ພ້ອມຫຼັກຖານ |

**Timeout ຫຼື COM ຕອບບໍ່ຊັດ:** ຢ່າສັ່ງແຕ້ມຊ້ຳ. ກວດ drawing ໃໝ່, receipt, actual snapshot ແລະ command line ກ່ອນ. ການອ່ານສະຖານະລອງໃໝ່ໄດ້, ການ mutate ບໍ່ລອງໃໝ່ອັດຕະໂນມັດ. ຖ້າຜິດພາດຫຼັງ Save As, drawing ໃໝ່ອາດບັນທຶກແລ້ວ; ກວດກ່ອນເຮັດຕໍ່.

## QA ແລະການກວດພາບ

```powershell
python -m tools.live_plan audit .live-runs/RUN/plan.json .live-runs/RUN/actual.json --output .live-runs/RUN/qa.json --visual-review C:/cad/scratch/review.json
```

`review.json` ແມ່ນຄຳຢືນຢັນຈາກຜູ້ທີ່ກວດພາບຈິງ; ຢ່າສ້າງພຽງເພື່ອໃຫ້ PASS:

```json
{
  "reviewed": true,
  "reviewer": "Actual reviewer",
  "notes": "Describe inspected junctions, defects fixed and remaining limits.",
  "views": {
    "model_extents": "C:/cad/scratch/extents.png",
    "junctions": "C:/cad/scratch/junctions.png",
    "openings": "C:/cad/scratch/openings.png",
    "layout": "C:/cad/scratch/layout.png",
    "plot_preview": "C:/cad/scratch/preview.png"
  }
}
```

QA ບໍ່ຮັບຮອງຮູບພາບຈາກການມີໄຟລ໌ຢ່າງດຽວ; ຄຳຢືນຢັນຕ້ອງມາຈາກການກວດຈິງ. ຖ້າບໍ່ມີ review ຈະເປັນ UNVERIFIED. Hinges/swings/usable clearance ຍັງເປັນ UNVERIFIED ໃນ v0.1 ເພາະ numeric geometry ບໍ່ພໍຢືນຢັນ. ບໍ່ໄດ້ຮັບຮອງວິສະວະກຳ ຫຼືກົດເກນກໍ່ສ້າງ.

Exit codes: `0` ບໍ່ມີ FAIL/UNVERIFIED, `1` FAIL ຫຼື runtime error, `2` ຍັງມີ UNVERIFIED. ດັ່ງນັ້ນ `draw` ອາດສຳເລັດໃນ AutoCAD ແລ້ວ ແຕ່ຄືນ `2` ຢ່າງຖືກຕ້ອງ; ບໍ່ຄວນແຕ້ມຊ້ຳ.

## ແຜນພັດທະນາຕໍ່

1. MCP wrapper ທີ່ເອີ້ນ API ນີ້ດ້ວຍ document identity ແບບເຂັ້ມງວດ.
2. Arbitrary polygon/curve cuts, non-orthogonal wall junctions, hidden-line projection.
3. Source-backed room/door schemas; usable-clearance checks ທີ່ແຍກຈາກຊ່ອງກໍ່.
4. Label collision solving, viewport sizing/other sheet scales, richer live QA readback.

ບໍ່ຕ້ອງ push DWG, SKP, geometry snapshots, QA screenshots, session tokens ຫຼື machine paths ເຂົ້າ GitHub. ໃຊ້ synthetic fixtures ໃນ tests/examples; ເກັບຂໍ້ມູນໂຄງການໄວ້ໃນ work directory ທີ່ ignore.
