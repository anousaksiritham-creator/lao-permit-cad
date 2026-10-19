# Validation notes — 2026-10-15

## ທົດສອບແລ້ວ

- Python 3.12 / Windows: **15 unit tests PASS** ແລະ synthetic `prepare` PASS.
- AutoCAD 2025 (`AutoCAD.Application.25`), `LISPSYS=1`: live synthetic drawing, save, readback and QA ສຳເລັດ.
- ທົດສອບຝາ 150 → 100 mm ໂດຍຍຶດແນວກາງ, ຕັດຝາຕາມເສົາ, associative solid hatches, native dimensions, native grid/circles/text, database Draw Order ແລະ A3 locked 1:100 viewport.
- ການທົດສອບ live ຄັ້ງສຸດທ້າຍ: **15 numeric/readback checks PASS; 2 UNVERIFIED** (visual-review attestation ແລະ hinge/swing/usable clearance), ບໍ່ມີ FAIL.
- ກວດພາບ Model Space ສັງເຄາະແລ້ວ; ບໍ່ໄດ້ສ້າງ attestation ວ່າໄດ້ກວດ layout/plot preview ຂອງ synthetic run ຄົບ. ຈຶ່ງຮັກສາ visual QA ເປັນ UNVERIFIED ຕາມຈິງ.
- ຈຳນວນ entities ຂອງ drawings ເດີມຖືກກວດກ່ອນ/ຫຼັງການທົດສອບ. ກັບໄປສະແດງ drawing ຂອງຜູ້ໃຊ້ຫຼັງຈົບ.

## ຈຸດທີ່ແກ້ຈາກ integration

- AutoCAD ຕ້ອງໄດ້ font file ທີ່ມີຢູ່ຈິງ; resolver ກວດ font ໃນ Windows Fonts ກ່ອນສ້າງ drawing.
- ແກ້ JSON quoting ຂອງ completion receipt. Receipt ມີ run ID ແລະ error stage ເພື່ອບໍ່ໃຫ້ແຕ້ມຊ້ຳຫຼັງຄຳຕອບບໍ່ຊັດ.
- ທົດສອບ response-loss ຂອງ document creation ແລະ command submission: mutate ພຽງຄັ້ງດຽວ.

## ຍັງບໍ່ທົດສອບຄົບ

- Ruby exporter ສະບັບ reusable ອີງຈາກ face/edge extraction ທີ່ໃຊ້ໃນວຽກຈິງ, ແຕ່ການເອີ້ນ version ທີ່ຈັດໃໝ່ຜ່ານ Ruby Console ໃນຮອບນີ້ຍັງຢືນຢັນ execution ບໍ່ໄດ້. ຕ້ອງທົດສອບໃນ SketchUp ກ່ອນໃຊ້ກັບງານໃໝ່.
- Hole subtraction ຜ່ານ pure-geometry unit tests; live smoke run ໃຊ້ເສົາທີ່ປາຍຝາ, ຍັງບໍ່ກວດ hatch inner loops ໃນ live CAD.
- ຍັງບໍ່ມີ validation ສຳລັບຮູບຕັດໂຄ້ງ, ຝາສະຫຼຽງ, ໂມເດວໃຫຍ່, fonts ລາວທຸກຊະນິດ ຫຼື engineering/code compliance.
- GitHub CI ເປັນ offline tests; ບໍ່ມີ AutoCAD/SketchUp ໃນ CI.

ໄຟລ໌ DWG, private geometry, screenshots, local session IDs ແລະ receipts ບໍ່ຖືກ commit. ທຸກ fixture ທີ່ຢູ່ໃນ repo ແມ່ນ synthetic.
