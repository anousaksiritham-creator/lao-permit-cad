# lao-permit-cad

ເຄື່ອງມື ແລະ ມາດຕະຖານ ສຳລັບແຕ້ມ **ແບບຂໍອະນຸຍາດປຸກສ້າງ** (Lao building-permit drawing set) ໃນ AutoCAD 2025,
ໂດຍຮຽນຈາກແບບອ້າງອີງ `ແບບ.dwg` (ເຮືອນ 2 ຊັ້ນ ບສລ, ຫຼັງຄາໂຄງເຫຼັກ). ໃຊ້ເພື່ອແຕ້ມແບບຈາກໄຟລ໌ SketchUp.

## ໂຄງສ້າງ
| Path | ເນື້ອໃນ |
|---|---|
| `docs/STANDARD.md` | ມາດຕະຖານ: ເລກແຜ່ນ, ມາດຕາສ່ວນ, ຟອນ, layer, ລະດັບ, ຄຳບັນຍາຍວັດສະດຸ |
| `docs/SKETCHUP-TO-CAD.md` | ຂັ້ນຕອນ SketchUp → AutoCAD |
| `skill/SKILL.md` | Claude Code skill (copy ໄປ `~/.claude/skills/lao-permit-drawing/`) |
| `tools/LaoPermitCad.psm1` | PowerShell module: ສ້າງແຜ່ນ, ໃສ່ກອບ A3, ຫົວຂໍ້, ລະດັບ, callout, import view |
| `tools/study_dwg.ps1` | ວິເຄາະ DWG ທີ່ເປີດຢູ່ → `study/` |
| `tools/su_export_views.rb` | SketchUp Ruby: export scene → 2D DWG (SketchUp Pro) |
| `tools/su_extract.rb` | SketchUp Ruby: ແຜນຜັງຕັດ + view projection + component → `out/<model>/model.json` |
| `tools/json2lsp.py` | `model.json` → AutoLISP ແຕ້ມທຸກ view ໃສ່ແຕ່ລະແຜ່ນ A3 |
| `docs/ROADMAP.md` | ເຕັກນິກທີ່ຕ້ອງພັດທະນາຕໍ່ |

## SketchUp → AutoCAD (ທົດສອບແລ້ວກັບ Seathis Office)
1. SketchUp Ruby Console: `load 'D:/ANS/Claude/CAD train AI/lao-permit-cad/tools/su_extract.rb'`
2. `python -I tools/json2lsp.py out/model/model.json out/model/views.lsp <X> <Y> 75 > out/model/sheets.json`
3. AutoCAD: `(load ".../views.lsp")`, ແລ້ວ `New-PermitSheet` + `Add-LevelMark` ຕາມ `sheets.json`
| `study/` | ຜົນວິເຄາະແບບອ້າງອີງ (layers, dimstyles, frames, hatches, blocks) |

## ເລີ່ມໃຊ້
```powershell
Import-Module .\tools\LaoPermitCad.psm1
Connect-Acad                     # ProgID AutoCAD.Application.25
$o = Get-NextSheetOrigin 84688 75
New-PermitSheet -No A202 -TitleLao 'ແຜນຜັງ ຊັ້ນ 1' -Scale 75 -X $o.X -Y $o.Y
```
Requires: Windows, AutoCAD 2025 running with the template drawing open (contains frame block `A$C2875ed45`,
symbol blocks, dimstyle `100`, layers). Optional: AutoCAD MCP server (`autocad_mcp.py`).
