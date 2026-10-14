# SketchUp → AutoCAD permit set (ຂັ້ນຕອນແຕ້ມແບບຈາກ SketchUp)

The reference set was built this way: elevations A301–A304 are 600–22 000 exploded lines on layer `0`
(2D hidden-line exports from SketchUp); plans use MLINE `WALL100` walls drawn over the exported outline.

## 1. Prepare the SketchUp model
- Units mm, building origin at grid A/1, ground floor ±0 at Z = 600 (ລະດັບຄໍດິນ +600 above natural ground ±00).
- Tags (layers) for: walls, columns, doors, windows, roof, furniture, site.
- Create one **scene per sheet view**, named `<sheetNo> <Lao title>`:
  | Scene | Camera | Notes |
  |---|---|---|
  | A102 ແຜນຜັງລວມ | Top, parallel | site + roof outline |
  | A201 ແຜນຜັງ ຫຼັງຄາ | Top | |
  | A202 / A203 ແຜນຜັງ ຊັ້ນ 1 / 2 | Top + section plane at +1.2 m above floor | |
  | A301–A304 ຮູບດ້ານ ໜ້າ/ຫຼັງ/ຊ້າຍ/ຂວາ | Front/Back/Left/Right, parallel | furniture hidden |
  | A311 / A312 ຮູບຕັດ A-A / B-B | section plane on, parallel | |
- Camera > Parallel Projection for every scene.

## 2. Export 2D views
- Run `tools/su_export_views.rb` in the SketchUp Ruby console → `cad_views/<sheet>.dwg`.
- Manual fallback: File > Export > 2D Graphic > `.dwg`, Options: Full scale 1:1, mm, edges only.

## 3. Place views on sheets in AutoCAD
```powershell
Import-Module .\tools\LaoPermitCad.psm1
Connect-Acad
$o = Get-NextSheetOrigin 84688 75                        # next free 1:75 slot in the top row
New-PermitSheet -No A202 -TitleLao 'ແຜນຜັງ ຊັ້ນ 1' -Scale 75 -X $o.X -Y $o.Y
Import-ViewDwg 'D:\proj\cad_views\A202.dwg' ($o.X + 3000) ($o.Y + 4000) (Get-ViewFactor 75)   # = 1
```
Geometry is always 1:1 mm; the **frame** is scaled (0.75 for 1:75, 1 for 1:100). View factor =
frame factor × 100 / view scale: `Get-ViewFactor 75` = 1, `200` = 0.5, `20` = 5, `40` = 2.5.

## 4. Annotate (after import)
1. Grid lines `A_GirdLine` + bubbles `ggf` (attr = grid label).
2. Walls: MLINE style `WALL100` (100 mm), columns hatched on `colum+beam section`.
3. Dimensions (`RotatedDimension`, dimstyle `100`, DIMSCALE = sheet scale).
4. Door/window/wall tags: `bounpasong door type 140404`, `bounpasong wall type 140404` (insert scale = sheet scale), window tags `A$C1078655e`.
5. Levels: `Add-LevelMark` + block `Level - SBIM_AN019_Level Head_Triangle…`.
6. Section callouts: `Add-Callout` with standard wording (see STANDARD.md §6).
7. Hatches: section cut ANSI31 sc 8–10, brick AR-B816C sc 0.4, ground ANGLE sc 43 — layer `Hatch-3`.
8. Check sheet no./title/scale vs index table on the cover (A101).
