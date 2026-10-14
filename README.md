# lao-permit-cad

ເຄື່ອງມືແຕ້ມ **ແບບຂໍອະນຸຍາດປຸກສ້າງ / Shop drawing** ຈາກໂມເດວ SketchUp ລົງ AutoCAD 2025 ອັດຕະໂນມັດ —
1 ຄຳສັ່ງ ໄດ້ຊຸດແບບ A3 ຄົບ (DWG + PDF) ພ້ອມ QA.

## ຕິດຕັ້ງຄັ້ງທຳອິດ (ເຄື່ອງໃໝ່)
1. ຕິດຕັ້ງ extension HTML MCP v2 ໃນ SketchUp 2025.
2. ເພີ່ມຄຳສັ່ງ `lpc_extract` ໃສ່ extension: `powershell -File extension\install.ps1`
   (copy `tools\lpc_extract.rb` + patch `main.rb`, ສຳຮອງເປັນ `main.rb.pre-lpc.bak`), ແລ້ວ restart SketchUp.
3. `pip install --user pypdf` (ລວມ PDF).

## ໃຊ້ງານ (1 ຄຳສັ່ງ)
ກ່ອນ: ເປີດ SketchUp + ໂມເດວ, **Extensions > HTML MCP v2 > Start bridge**; ເປີດ AutoCAD 2025.
```powershell
powershell -File tools\build.ps1 -Project projects\seathis\project.json -Pdf
```
ຜົນ: `out\<model>\` → `<name>.dwg`, `<name>_set.pdf` (ລວມທຸກແຜ່ນ), `pdf\*.pdf`, `png\*.png` (ພາບກວດ), `qa.json`.

ຂັ້ນຕອນພາຍໃນ: `lpc_extract` (SketchUp, ~40 ວິ) → `build_set.py` (AutoLISP) → `run_lisp.ps1` (AutoCAD, ລຶບຂອງເກົ່າຂອງໂຄງການແລ້ວແຕ້ມໃໝ່)
→ `check_set.py` (QA) → `plot_pdf.ps1` (PNG/PDF) → `merge_pdf.py`.

## ຊຸດແບບທີ່ໄດ້ (ຕົວຢ່າງ Seathis Office — 16 ແຜ່ນ)
| ແຜ່ນ | ເນື້ອໃນ |
|---|---|
| A101 | ໜ້າປົກ + ສາລະບານ (ສ້າງເອງ) |
| A201–A203 | ແຜນຜັງ, ແຜນຜັງບອກໄລຍະ/ປະຕູ-ປ່ອງຢ້ຽມ, ແຜນຜັງຫຼັງຄາ — grid, dimension 2 ແຖວ, tag, ຖົມດຳເສົາທີ່ຖືກຕັດ, ເຄື່ອງໝາຍຮູບຕັດ, ທິດເໜືອ |
| A301–A304 | ຮູບດ້ານ 4 ດ້ານ — hidden-line, ລະດັບ, grid, ສ່ວນໃຕ້ດິນເປັນເສັ້ນປະ |
| A311–A312 | ຮູບຕັດ A-A, B-B (ຕັດຈິງ + ເສັ້ນທາງຫຼັງ) |
| A401 | ຕາຕະລາງປະຕູ-ປ່ອງຢ້ຽມ |
| B101, B201, B401 | ຮາກຖານ/ຄານຄອດິນ, ໂຄງຫຼັງຄາ, ຕາຕະລາງອົງປະກອບໂຄງສ້າງ |
| E101, P101 | ໄຟຟ້າແສງສະຫວ່າງ, ນ້ຳ-ສຸຂະພັນ + legend |
> ແຜ່ນ B/E/P ມີໝາຍເຫດ: ວິສະວະກອນຕ້ອງກວດກາ ແລະ ຢັ້ງຢືນ.

## ໂຄງສ້າງ repo
| Path | ເນື້ອໃນ |
|---|---|
| `tools/build.ps1` | ຄຳສັ່ງດຽວ ທັງ pipeline |
| `extension/` | patch `main.rb` ຂອງ HTML MCP v2 (ຄຳສັ່ງ `lpc_extract`) + `install.ps1` |
| `tools/lpc_extract.rb` | Extractor v2 (ຕິດຕັ້ງໃນ extension HTML MCP v2 ເປັນຄຳສັ່ງ `lpc_extract`) |
| `tools/lpc_bridge.mjs` | ສັ່ງ extract ຜ່ານ bridge port 32124, ລໍ status |
| `tools/build_set.py` | model.json + project.json → AutoLISP ທັງຊຸດ (ກອບ `LPC_A3_V1` ມີ attribute) |
| `tools/run_lisp.ps1`, `plot_pdf.ps1`, `check_set.py`, `merge_pdf.py` | ແຕ້ມ, plot, QA, ລວມ PDF |
| `tools/su_extract.rb` | ສຳຮອງ: ແລ່ນ extractor ຈາກ Ruby Console |
| `tools/LaoPermitCad.psm1`, `json2lsp.py`, `study_dwg.ps1` | ເຄື່ອງມືຮຸ່ນທຳອິດ / ວິເຄາະແບບອ້າງອີງ |
| `projects/<name>/project.json` | ຂໍ້ມູນໂຄງການ (ຊື່, ສະຖານທີ່, ເຈົ້າຂອງ, ຜູ້ອອກແບບ, ລະດັບຕັດ) |
| `docs/MODEL-CONVENTION.md` | **ກົດການຕັ້ງຊື່ໂມເດວ SketchUp** |
| `docs/STANDARD.md`, `SKETCHUP-TO-CAD.md`, `ROADMAP.md` | ມາດຕະຖານ, ຂັ້ນຕອນ, ແຜນພັດທະນາ |
| `skill/SKILL.md` | Claude Code skill `lao-permit-drawing` |

## project.json
```json
{ "id": "SEATHIS_OFFICE", "name": "ຫ້ອງການ SEATHIS", "subtitle": "ແບບກໍ່ສ້າງ / Shop Drawing",
  "location": "...", "owner": "...", "designer": "...", "date": "2026-10-15",
  "model_dir": "model", "dwg_name": "Seathis_Office.dwg",
  "extract": { "cuts": [1500, 100, 4300], "skip": ["17 "], "hidden": true, "sections": "auto" } }
```
`cuts`: ລະດັບຕັດແຜນຜັງ (mm) — ອັນທຳອິດ 1000–2000 = ແຜນຜັງສະຖາປັດ, < 300 = ຮາກຖານ.

## ຕ້ອງການ
Windows, AutoCAD 2025, SketchUp 2025 + extension HTML MCP v2 (ມີ `lpc_extract.rb`), Python 3 (+ `pip install --user pypdf` ສຳລັບລວມ PDF), Node (codex runtime).
