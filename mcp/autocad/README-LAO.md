# AutoCAD MCP 2025

ເຊີບເວີ Python ຊື່ `autocad`, ສື່ສານຜ່ານ stdio ແລະຄວບຄຸມ AutoCAD 2025 ຜ່ານ Windows COM (`AutoCAD.Application.25`). ເປັນເຄື່ອງມືເສີມ; pipeline `tools/build.ps1` ໃຊ້ງານໄດ້ຕາມເດີມ.

## ຕິດຕັ້ງ

ຕ້ອງມີ Windows, Python 3.10+ (ແນະນຳ 3.12), AutoCAD 2025 ແລະ MCP client ທີ່ຮອງຮັບ stdio. ແລ່ນຈາກໂຟນເດີຫຼັກຂອງ repository:

```powershell
py -3.12 -m venv mcp/autocad/.venv
& .\mcp\autocad\.venv\Scripts\python.exe -m pip install -r mcp/autocad/requirements.txt
$pythonPath = (Resolve-Path .\mcp\autocad\.venv\Scripts\python.exe).Path
$serverPath = (Resolve-Path .\mcp\autocad\autocad_mcp.py).Path
claude mcp add autocad --scope user -- $pythonPath $serverPath
```

ຖ້າມີ `autocad` ໃນ Claude ແລ້ວ, ກວດ `claude mcp get autocad` ກ່ອນ. ຖ້າຕ້ອງການປ່ຽນຈາກ server ເກົ່າມາໃຊ້ໄຟລ໌ໃນ repository ນີ້, ໃຊ້ `claude mcp remove autocad --scope user` ແລ້ວແລ່ນຄຳສັ່ງ add ຂ້າງເທິງ. ເປີດ session Claude ໃໝ່ຫຼັງປ່ຽນການຕັ້ງຄ່າ.

ສຳລັບ MCP client ອື່ນ: ກຳນົດ command ເປັນ absolute path ຂອງ Python ໃນ `.venv`, args ເປັນ absolute path ຂອງ `autocad_mcp.py`, transport ເປັນ stdio. ການດາວໂຫຼດ repository ບໍ່ໄດ້ລົງທະບຽນ server ໃນ client ອັດຕະໂນມັດ.

## ໃຊ້ງານ

ເປີດ AutoCAD 2025 ແລະແບບທີ່ຕ້ອງການ, ປິດ dialog ທີ່ຄ້າງ ແລ້ວເອີ້ນ tools ຜ່ານ client. ຫົວໜ່ວຍເປັນ drawing units; ກວດ `INSUNITS` ກ່ອນແຕ້ມ, ບໍ່ຄວນຖືວ່າທຸກແບບເປັນ mm.

ຖ້າ AutoCAD ບໍ່ເປີດ, server ຈະລອງເປີດ `C:\Program Files\Autodesk\AutoCAD 2025\acad.exe`. ຖ້າຕິດຕັ້ງຢູ່ບ່ອນອື່ນ, ປັບ `ACAD_EXE` ໃນ server. ບໍ່ fallback ໄປ AutoCAD 2018 ຫຼື version ອື່ນ.

ໝາຍເຫດ: `status` ແລະ tools ທີ່ອ່ານແບບອາດເປີດ AutoCAD ຫຼືສ້າງແບບໃໝ່ ຖ້າຍັງບໍ່ມີແບບເປີດ. `test_smoke.py` ສ້າງແບບໃໝ່ ແລະແຕ້ມຮູບທົດສອບ; ໃຊ້ເມື່ອຕ້ອງການທົດສອບການແຕ້ມເທົ່ານັ້ນ.

## Tools (25)

`status`, `new_drawing`, `open_drawing`, `save_drawing`, `zoom_extents`, `send_command`, `get_variable`, `set_variable`, `list_layers`, `create_layer`, `draw_line`, `draw_polyline`, `draw_rectangle`, `draw_circle`, `draw_arc`, `add_text`, `add_mtext`, `add_aligned_dimension`, `add_hatch`, `insert_block`, `list_entities`, `drawing_extents`, `erase_entities`, `move_entities`, `set_entity_props`.
