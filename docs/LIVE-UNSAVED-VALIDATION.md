# Validation — 2026-10-19

## Changes verified

- Default live workflows do not create/save DWG, DXF, PDF or PNG drawing deliverables. Internal JSON/LISP receipts remain ignored scratch data.
- `tools/live_plan` supports `output=None`; CLI `--output` is explicit save opt-in. Readback QA validates the chosen save policy rather than requiring a saved file in live mode.
- Generated source is submitted inline. No SCRIPT file-selection dialog, LOAD trust changes, or SECURELOAD changes.
- The compatibility PowerShell pipeline checks QA before mutation, uses empty unsaved targets, refuses existing-file overwrite and does not delete previous project entities.
- Mutation submission is never retried; journals distinguish uncertain, partial, unsaved and explicitly saved results.
- Grid heads extend beyond outer dimension positions, including rotated views in the legacy builder.
- Native dimensions have explicit text/arrow sizes. Numeric values and witness points remain independent of displayed text; unresolved hinges/clear openings remain UNVERIFIED.

## Evidence and limits

- Python 3.12 / Windows: 28 offline unit tests pass, including the upstream live-plan tests and new validation/default-save/grid-placement tests.
- Offline synthetic `python -m tools.live_plan prepare ...` passes.
- AutoCAD 2025 / Windows PowerShell: `tests/smoke_live.ps1` passed direct unsaved drawing, native 1000 mm dimension readback, mm units, nonempty-target refusal and prior-document counts/path preservation. Its own scratch drawing was closed without saving.
- AutoCAD 2025 / pywin32: `tests/smoke_live_plan.py` passed with 14 numeric/readback checks PASS, 2 UNVERIFIED, 0 FAIL. It draws actual synthetic source-derived geometry and verifies native dimensions, hatch areas and Draw Order without saving a DWG. Its own successful scratch drawing was closed without saving.
- These are numeric/database tests, not a claim of complete model/layout/Plot Preview visual review. Visual review and hinge/swing/usable clearance remain UNVERIFIED.
- The changed legacy Ruby extractor metadata has not been reinstalled or executed inside SketchUp during this update. Exporter installation/restart and live extraction compatibility need their own check.
- Full legacy A3 multi-sheet generation has offline CLI coverage; the new legacy dispatcher has live primitive coverage. A full generated legacy sheet set was not retested live in this update.
- No building-code, structural, accessibility, permit or construction-release certification is implied.

Only synthetic fixtures and reusable code/documentation are committed. No project drawing, screenshot, model geometry, credentials, source session IDs or runtime receipts are included.
