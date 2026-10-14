# Roadmap — ເຕັກນິກການແຕ້ມທີ່ຕ້ອງພັດທະນາຕໍ່

## ສະຖານະປັດຈຸບັນ (2026-10-14)
- ✅ AutoCAD 2025 ↔ PowerShell COM (`AutoCAD.Application.25`) + AutoCAD MCP
- ✅ SketchUp 2025 → `su_extract.rb` → `model.json` (ແຜນຜັງຕັດ, 5 view projection, ລາຍການ component, PNG)
- ✅ `json2lsp.py` → AutoLISP entmake (48k ເສັ້ນ ~4 ນາທີ), ຈັດກາງແຜ່ນ, ໝຸນແຜນຜັງທີ່ຍາວ
- ✅ ກອບ A3 + ຫົວຂໍ້/ເລກແຜ່ນ/scale ກົງກັບແບບອ້າງອີງ (±1 mm), ລະດັບ, callout
- ✅ ທົດສອບກັບ Seathis Office (6 ແຜ່ນ SD-101…SD-204)

## ບັນຫາທີ່ຮູ້ແລ້ວ
1. ຮູບດ້ານບໍ່ມີ hidden-line removal → ເຫັນທາງໃນທະລຸ. ແກ້ຊົ່ວຄາວ: ກອງຕາມ component code (`keep` ໃນ json2lsp.py).
2. ແຜນຜັງມີແຕ່ເສັ້ນຕັດ (cut) — ຍັງບໍ່ມີເສັ້ນທີ່ເຫັນຢູ່ລຸ່ມ (ພື້ນ, ເຟີນີເຈີ, ສຸຂະພັນ).
3. ກອບ `A$C2875ed45` ມີຊື່ໂຄງການເກົ່າຝັງໃນ block → ຕ້ອງເຮັດກອບແບບມີ attribute.
4. Saysettha OT ໃຊ້ inline `\f` ບໍ່ໄດ້ → ໃຊ້ Phetsarath OT ຫຼື text style.
5. `SendCommand` ແບບ async; COM ອາດ RPC_E_CALL_REJECTED ເມື່ອ AutoCAD ຫຍຸ້ງ → ຕ້ອງມີ retry.
6. ເສັ້ນທັງໝົດຢູ່ layer ດຽວຕໍ່ view → ຕ້ອງແຍກ layer ຕາມ component (ຝາ, ປະຕູ, ...).

## ແຜນພັດທະນາ (ລຽງຕາມຄວາມສຳຄັນ)
- [ ] **Hidden-line**: z-buffer/occlusion ໃນ Ruby (ray test `model.raytest` ຈາກກາງເສັ້ນໄປຫາຜູ້ເບິ່ງ) ຫຼື export 2D DWG ຂອງ SketchUp Pro.
- [ ] **Layer ຕາມ component**: map code → layer (08→`wall`, 10→`DOOR`, 11→`Window`, 04→`colum`, 07→`ROOF`), ສີ/lineweight ຕາມ STANDARD.
- [ ] **ແຜນຜັງຄົບ**: cut (ໜາ) + projection ລຸ່ມ cut (ບາງ) + hatch ເສົາ/ຝາທີ່ຖືກຕັດ (ANSI31).
- [ ] **ກອບແບບ attribute**: ຊື່ໂຄງການ, ສະຖານທີ່, ວັນທີ, ຜູ້ອອກແບບ, ເລກແຜ່ນ, scale.
- [ ] **Dimension ອັດຕະໂນມັດ**: grid ເສົາ (A/B…, 1/2…), ໄລຍະລວມ, ໄລຍະເສົາ ຈາກ component 04.
- [ ] **Grid line + bubble** (`ggf`) ຈາກຕຳແໜ່ງເສົາ.
- [ ] **ຮູບຕັດ A-A / B-B**: cut ແນວຕັ້ງ (intersect plane XZ/YZ) + projection ທາງຫຼັງ.
- [ ] **Tag ປະຕູ/ປ່ອງຢ້ຽມ** + ຕາຕະລາງ (schedule) ຈາກ component 10/11.
- [ ] **ລະດັບອັດຕະໂນມັດ** ຈາກ bounds ຂອງ component (ພື້ນ, ເພດານ, ຫຼັງຄາ).
- [ ] **ແຜ່ນໂຄງສ້າງ B** (ຮາກຖານ, ຄານ, ເສົາ) ຈາກ component 01/02/04/05/18.
- [ ] **ແຜ່ນ E / P** ຈາກ component 14/15/19.
- [ ] Batch: 1 ຄຳສັ່ງ = SketchUp → JSON → DWG ທັງຊຸດ (ໃຊ້ bridge HTML MCP v2 ເມື່ອເພີ່ມ `run_ruby`).
