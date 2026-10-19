# ແຕ້ມໃນ AutoCAD ໂດຍກົງ

ຄ່າປົກກະຕິ: ແຕ້ມໃນ AutoCAD ທີ່ເປີດຢູ່, ບໍ່ save DWG/DXF/PDF ແລະບໍ່ plot ອັດຕະໂນມັດ. JSON, generated LISP ແລະ run journal ເປັນຂໍ້ມູນພາຍໃນ `out/`, ບໍ່ແມ່ນຜົນສົ່ງມອບແບບ ແລະບໍ່ຕ້ອງ commit.

```powershell
powershell -NoProfile -File tools\build.ps1 -Project projects\seathis\project.json
# ຫຼືໃຊ້ extraction ທີ່ກວດແລ້ວ
powershell -NoProfile -File tools\build.ps1 -Project projects\seathis\project.json -SkipExtract
```

ຕ້ອງເປີດ AutoCAD ກ່ອນ. ຖ້າ active drawing ມີວັດຖຸ ຫຼືເຄີຍ save, ລະບົບຈະໃຊ້ແຜ່ນໃໝ່ທີ່ຍັງບໍ່ save ໃນ app ດຽວກັນ. `-DrawingName` ໃຊ້ໄດ້ສະເພາະແຜ່ນວ່າງທີ່ຍັງບໍ່ save. ບໍ່ລຶບວັດຖຸເດີມເມື່ອຮັນຊ້ຳ. ການແກ້ວັດຖຸໃນແຜ່ນທີ່ມີງານແລ້ວຍັງຕ້ອງມີ adapter ທີ່ກວດ baseline ແລະອະນຸມັດການແກ້ເປັນລາຍຈຸດ.

## ຕົວແຕ້ມ

`tools/run_live.ps1` ໃຊ້ COM ກັບ AutoCAD 2025 ແລະສົ່ງຄຳສັ່ງ inline ພຽງຄັ້ງດຽວ. ບໍ່ເປີດ SCRIPT file dialog, ບໍ່ປ່ຽນ SECURELOAD. ໃຊ້ nonce ຕໍ່ແຜ່ນ ແລະ completion marker ຕໍ່ run; ຄືນຄ່າ FILEDIA/CMDDIA/OSMODE/CMDECHO ຫຼັງການຮັນສຳເລັດ ຫຼື error ທີ່ຈັບໄດ້.

COM reads ທີ່ busy ສາມາດ retry ໄດ້. ຄຳສັ່ງແຕ້ມ/ສ້າງແຜ່ນ/SaveAs ບໍ່ retry. ຖ້າ timeout ຫຼື submission error, ກວດ `out/runs/<id>/live-run.json` ແລະແຜ່ນໃນ AutoCAD ກ່ອນ; ຫ້າມຮັນຊ້ຳອັດຕະໂນມັດ. ບາງ COM calls ອາດບລັອກກ່ອນເຂົ້າການຈັບເວລາ; TimeoutSec ບໍ່ແມ່ນຕົວຂ້າ process.

ບໍ່ສົ່ງ LISP ທີ່ບໍ່ໄດ້ກວດ. ຕົວກັ້ນຄຳສັ່ງ save ເປັນການກວດປ້ອງກັນຜິດພາດ, ບໍ່ແມ່ນ sandbox ສຳລັບ code ທີ່ບໍ່ໜ້າເຊື່ອຖື.

## ການສົ່ງອອກແມ່ນ opt-in

`build.ps1 -ExportDwg` ຈຶ່ງ save DWG; `-Png` ແລະ `-Pdf` ຈຶ່ງ plot. `run_lisp.ps1 -Dwg` ຍັງຮອງຮັບເປັນ alias ຂອງ SaveAs ແຕ່ບໍ່ເປີດ/ຂຽນທັບໄຟລ໌ເກົ່າ. ຜູ້ໃຊ້ສາມາດ save ເອງໃນ AutoCAD ເມື່ອພ້ອມ.

## ການກວດ

```powershell
python -m unittest discover -s tests -v
# ທົດສອບໃນ AutoCAD ຈິງດ້ວຍແຜ່ນຈຳລອງທີ່ປິດໂດຍບໍ່ save
powershell -NoProfile -File tests\smoke_live.ps1
```

QA ຈະແລ່ນກ່ອນສົ່ງແບບເຂົ້າ AutoCAD. ກວດ non-finite values, bounds ກັບດ້ານ, root IDs ຊ້ຳ, ເສັ້ນສູນ ແລະຫົວໜ່ວຍ; ຂໍ້ມູນ datum ທີ່ບໍ່ຢືນຢັນຈະຄົງ pending. ກວດຫົວແກນຢູ່ນອກຂະໜາດທັງສອງທິດຂອງ view.

**ຂອບເຂດ:** ເປັນ pre-design/drafting QA. ບໍ່ໄດ້ຢືນຢັນກົດໝາຍອາຄານ, ຄຳນວນໂຄງສ້າງ ຫຼືອະນຸຍາດກໍ່ສ້າງ. ຄ່າຈາກແບບຕົວຢ່າງຕ້ອງບໍ່ນຳໄປເປັນ engineering input ຂອງໂຄງການໃໝ່ໂດຍອັດຕະໂນມັດ.
