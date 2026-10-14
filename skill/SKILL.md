---
name: lao-permit-drawing
description: Draw, check or complete a Lao building-permit drawing set (ແບບຂໍອະນຸຍາດປຸກສ້າງ) in AutoCAD — sheet numbering, A3 title-block scaling, Lao annotation fonts/text, level marks, material callouts and the standard sheet list (architecture A, structure B, electrical E, plumbing P). Use whenever the user asks to draw, add, check or finish sheets/details for a house/building permit set, or mentions ແບບຂໍອະນຸຍາດ, ແຜນຜັງ, ຮູບຕັດ, ຮູບດ້ານ, ຮູບຂະຫຍາຍ in an AutoCAD context.
---

# Lao building-permit drawing set (AutoCAD)

Learned from the user's reference file `D:\ANS\Claude\ແບບ.dwg` (2-storey RC house, steel-truss roof). Copy its conventions; do not invent a new style.

## 1. Connecting
- MCP server `autocad` (tools `mcp__autocad__*`): status, list_layers, list_entities, draw_*, add_mtext, insert_block, send_command…
- For bulk reads (text dump, block counts, bounding boxes) use PowerShell COM. **ProgID must be versioned:** `[Runtime.InteropServices.Marshal]::GetActiveObject("AutoCAD.Application.25")` (the plain `AutoCAD.Application` fails with MK_E_UNAVAILABLE). Iterating 30k entities takes ~1–3 min; run with a long timeout.
- Read-only first. Draw new work on its own layer; never save over the user's file unless asked.

## 2. Units, scale and sheet layout (everything in Model space)
- INSUNITS = 4 (mm). Building drawn 1:1 in mm. LTSCALE = 1. Layouts are unused — all sheets are frames in Model space, plotted by window to **ISO A3 full-bleed 420×297**.
- Sheet frame = block `A$C2875ed45` (A3 frame + right-hand title strip, 43108 × 29700 at scale 1). **Frame block scale = sheet scale / 100**:
  - 1:100 → scale 1.0 (43108×29700) — also used for 1:200 site sheets and 1:20 detail sheets (see below)
  - 1:75 → scale 0.75 (32331×22275) — plans, elevations, sections, technical sheets
- Drawings at a scale different from the frame are inserted as **blocks scaled up/down** inside a frame: 1:200 site drawings = blocks at 0.5 in a scale-1 frame; 1:20 door/window details = blocks at 5 in a scale-1 frame; 1:40 stairs = 2.5.
- Sheets are laid out in rows, left→right in sheet-number order, spacing ≈ frame width + ~3–4 m gap (e.g. 1:75 row step 35 487 in X; 2nd row 28 231 lower).
- Drawing-title text on each sheet sits under the view: title (Lao) + sheet no. + scale, layer `SYM_DIM`, height 300 (1:75 frame) / 400 (1:100 frame).

## 3. Sheet index (from the "Drawing name / NO / Scale" table in the cover area)
Three title columns: **ແຜນແຕ້ມແບບສະຖາປັດ / Architect Drawing**, **ແຜນແຕ້ມແບບໂຄງສ້າງອາຄານ / Building Drawing**, **ແຜນແຕ້ມແບບການຈັດວາງລະບົບໄຟຟ້າ ແລະ ນໍ້າປະປາ / Electric & Plumbing Drawing**.

| No | Lao title | Scale |
|---|---|---|
| A101 | ໜ້າປົກ (cover) | – |
| A102 | ແຜນຜັງລວມ (site plan) | 1/200 |
| A103 | ແຜນຜັງຈັດສັນຕອນດິນ (land layout) | 1/200 |
| A104 | ແຜນຜັງຮ່ອງລະບາຍນ້ຳ (drainage) | 1/200 |
| A105 | ຮູບຕັດຕອນດິນ A-A & B-B (site sections) | 1/200 |
| A201–A203 | ແຜນຜັງຫຼັງຄາ, ແຜນຜັງຊັ້ນ 1, ແຜນຜັງຊັ້ນ 2 | 1/75 |
| A301–A304 | ຮູບດ້ານໜ້າ, ດ້ານຫຼັງ, ດ້ານຊ້າຍ, ດ້ານຂວາ | 1/75 |
| A311–A312 | ຮູບຕັດ A-A, ຮູບຕັດ B-B | 1/75 |
| A401–A402 | ແຜນຜັງບອກວັດສະດຸ,ປະຕູແລະປ່ອງຢ້ຽມ ຊັ້ນ 1/2 | 1/75 |
| A403–A404 | ແຜນຜັງບອກໄລຍະ ຊັ້ນ 1/2 (dimension plans) | 1/75 |
| A405–A406 | ແຜນຜັງບອກລະດັບພື້ນ ຊັ້ນ 1/2 (floor levels) | 1/75 |
| A407–A410 | ຮູບເຕັກນິກ ດ້ານໜ້າ/ຫຼັງ/ຊ້າຍ/ຂວາ | 1/75 |
| A501 | ຮູບຂະຫຍາຍ D1, D2 & D3 (doors) | 1/20 |
| A502–A503 | ຮູບຂະຫຍາຍ W1&W2, W3&W4 (windows) | 1/20 |
| A601 | ຮູບຂະຫຍາຍຂັ້ນໄດ (stairs) | 1/40 |
| B201 | ແຜນຜັງ ຮາກຖານ (foundation) | 1/75 |
| B202 | ແຜນຜັງ ຝາກັ້ນດິນ (retaining wall) | 1/75 |
| B203 | ແຜນຜັງ ຄານຄໍດິນ (ground beam) | 1/75 |
| B204 | ແຜນຜັງ ຄານ ຊັ້ນ 2 | 1/75 |
| B205 | ແຜນຜັງ ໂຄງຫຼັງຄາ (roof frame) | 1/75 |
| B301 | ຮູບຂະຫຍາຍ F1 (footing) | 1/20 |
| B401 | ຮູບຂະຫຍາຍເສົາ (columns) | 1/20 |
| B501 | ຮູບຂະຫຍາຍຄານຄໍດິນ | 1/25 |
| B502 | ຮູບຂະຫຍາຍຄານຊັ້ນ 2 ແລະ ຄານເອັນ | 1/25 |
| B601 | ຮູບຕັດການເສີມເຫຼັກແຜ່ນພື້ນ | 1/20 |
| B701 | ຮູບເຕັກນິກການເສີມເຫຼັກແຜ່ນພື້ນ | 1/100 |
| E301–E302 | ແຜນຜັງໄຟຟ້າ ຊັ້ນ 1/2 | 1/75 |
| E303–E304 | ແຜນຜັງພັດລົມດູດອາກາດ ຊັ້ນ 1/2 | 1/75 |
| P201–P202 | ແຜນຜັງນ້ຳໃຊ້ ຊັ້ນ 1/2 | 1/75 |
| P301 | ຮູບຂະຫຍາຍຂຸມອາຈົມ (septic tank) | 1/50 |
| P401 | ຮູບຂະຫຍາຍຮ່ອງລະບາຍນ້ຳ ແລະ ຂຸມພັກນ້ຳ | 1/20 |

Numbering rule: letter = discipline, first digit = drawing type (1 site, 2 plans, 3 elevations/sections, 4 technical/annotated plans, 5 details, 6 stairs/special), last two digits = sequence. Keep the index table and the per-sheet titles in sync.

**Status in the reference file (as studied):** placed sheets = A102–A105, A201–A203, A301–A304, A311–A312, A401–A410, A501–A503, A601. **Not drawn yet:** A101 cover, all B (structure), all E, all P sheets — they exist only in the index. When asked to "complete the set", these are the gaps.

## 4. Text and fonts
- Lao text: MText with inline font `{\fPhetsarath OT|b0|i0|c0|p2;…}` (titles) or **Saysettha OT** text style (level marks, callouts). Latin/numbers: Times New Roman (`{\fTimes New Roman|b0|i0|c0|p18;…}`). Dimension/callout numbers sometimes `Romantic`.
- Heights (model mm): sheet titles 300–400 (1:75/1:100 frames); index table 250, headers 300–380; level-mark text 210; material callouts 180–250; symbol legend 200 (Arial / Arial Narrow).
- Write in Lao with the conventional abbreviations: ບສລ = reinforced concrete, ຊັ້ນ = floor, ລະດັບ = level.

## 5. Levels (layer `A-FLOR-LEVL`, Saysettha OT, h 210, block `Level - SBIM_AN019_Level Head_Triangle…`)
Format `ລະດັບ<name> (+<mm>)`. Reference values for this house type:
- ລະດັບທຳມະຊາດ01 (±00) — natural ground
- ລະດັບຄໍດິນ ບສລ (+600) — ground beam / ground floor
- ລະດັບຄານພັກແຮງຂັ້ນໄດ (+2690) — stair landing beam
- ລະດັບຄານພື້ນຊັ້ນ 2 ບສລ (+4200) — 2nd-floor beam
- ລະດັບຄານຫຼັງຄາ (+7400) — roof beam
- ລະດັບໂຄງເຫຼັກທັກຊ໌ຕ່ໍາສຸດ/ສູງສຸດ (+7800 / +7950…+8350) — steel truss low/high
Floor finish marks on plans: `+550mm`, `+600mm` (layer `Dimention`).

## 6. Typical material callouts (sections, layer `Dimention`, leaders)
- ພື້ນ ບສລ ເບົາຫນາ 100mm ພ້ອມປູກາໂລ 600x600 mm (300x300 in wet rooms)
- ຖົມຊາຍຫົດນ້ຳຕຳແໜ້ນ — compacted sand fill
- ເພດານຢິບຊຳໂຄງຊີລາຍ — gypsum ceiling on C-line frame
- ເຫລັກສີຍົວ 100x50x3.2@1000mm (purlin/rafter), ເຫລັກຂ້າວ 30x30x3.0@1000mm (batten)
- ຫລັມຄາມມຸມດ້ວຍອາລູຊິ້ງ — roof ridge/hip flashing
- ອົກໄກ່ ບສລ 250x200mm (lintel/ring beam), ຄານ ບສລ 200x200mm
- ພັດລົມ ດູດອາກາດ ແບບຕິດເພດານ — ceiling exhaust fan

## 7. Layers and symbols
- Annotation layers (A-ANNO-*): TEXT, TITLEBLOCK, MATCHLINE, SYMBOL, CENTER, SECTION, ELEVATION, DOOR REF, WINDOW REF, WALL TYPE, DETAIL REF, GRID REF, REVISION, FLOOR TRANSITION; `A-ROOMNAME`, `A-FLOOR-STAIRS`, `A_GirdLine`, `SYM_DIM` (sheet titles/index), `SYM_TITLE`.
- Other: `wall`, `wall sec`, `colum`, `colum+beam section` (red), `BEAM`, `DOOR`, `Window(s)`, `furniture`/`FURN`, `Hatch*`, `centerline`, `Dimension`/`Dimention`, `LN_3`.
- Most geometry (~30k lines) is on layer `0` — exploded imports (SketchUp/Revit `ProfileEdges`/`SectionCutEdges`). New work should go on the proper named layer, not `0`.
- Symbol legend ("SYMBOLS REMARK") already exists in the cover area: blocks `GRID REF`, `ELEVATION MARK`, `WALL TYPE REF`, `bounpasong door type 140404`, `bounpasong wall type 140404`, `bounpasong cei-floor-height & type 140404`, level-head triangle, north arrow, graphic scale 0-1-2-4 m. Reuse these blocks via insert_block.
- Dimensions: dimstyle `100` with DIMSCALE 100 (1:100) or 175, text 1.5 → plots ~1.5 mm. For 1:75 use DIMSCALE 75.

## 7b. Drawing techniques found per sheet (deep study)
- Plans (A202/A203, A401–A406): walls = MLINE style `WALL100` (100 mm) on layer 0; columns on `colum+beam section` (red, lw 0.15); grid `A_GirdLine` + bubble block `ggf` (attr tag `12` = label) at scale 0.99; dims RotatedDimension 8–60 per plan; A401/402 add wall/door tags (`bounpasong wall type 140404` at ±75/±100, door type at 75); A405/406 use `bounpasong cei-floor-height & type 140404` at 75 + "+550mm/+600mm" text.
- Elevations A301–A304: 600–22 000 loose Lines on layer 0 = SketchUp/Revit 2D export; plus trees `gsa`, people `TR123`, car `CMD003`, ground polyline `Earth` (width 60).
- Technical elevations A407–A410: simplified elevation + level marks (block Level-Head ×5) + dims + wall/door tags.
- Sections A311/A312: hatches on `Hatch-3` (ANSI31 sc 8–10 for cut concrete, AR-B816C sc 0.4 brick, ANGLE sc 43), leaders on `Dimention`, section-mark block `S9` @0.9, beams/columns on `colum+beam section`, rebar outlines `0.6`.
- Detail sheets A501–A503, A601: whole detail is one block inserted at 5 (1:20) or 2.5 (1:40) inside a scale-1 frame.
- Dimstyle actually used: `100` (DIMSCALE 100, DIMTXT 1.5, ArchTick, Times New Roman) with per-dim scale 100/175.
- Reusable code & docs: repo folder `D:\ANS\Claude\CAD train AI\lao-permit-cad` (module `tools/LaoPermitCad.psm1`: Connect-Acad, New-PermitSheet, Get-NextSheetOrigin, Add-LevelMark, Add-Callout, Import-ViewDwg; `docs/SKETCHUP-TO-CAD.md` for drawing from a SketchUp model).

## 8. Workflow for adding a missing sheet
1. `status` → confirm `ແບບ.dwg` active, INSUNITS 4.
2. Find the next free slot in the right row; insert frame `A$C2875ed45` at the sheet scale factor (§2).
3. Draw on correct layers; at 1:1 for the frame's scale, or as a scaled block if the view scale differs.
4. Add the view title (Lao, Phetsarath OT) + sheet no. + scale under the view; annotate levels/materials using §5–6 wording.
5. Verify the sheet number and scale match the index table (§3); update the index if the title changed.
6. `zoom_extents`/zoom window to show the result. Don't save unless the user asks.

## 9. Known issues in the reference file
- Three block refs (`A$C9cdd5b41`, `A$Cae795bb4`, `A$C178ef4e7`, plus `rtgttyhrt`, `A$C39e104a2`, `A$C4bc875af`) have absurd extents (millions of mm) — stray geometry inside the block; they inflate EXTMAX. Mention before ZOOM E.
- Layer name typos (`Dimention`, `Hacth`, `Viwe`) are the user's existing names — reuse, don't "fix" silently.
- ROOF title says ເຫຼັກທັກຊ໌ top level both +7950 and +8350 on different sheets — flag inconsistencies like this when checking.
