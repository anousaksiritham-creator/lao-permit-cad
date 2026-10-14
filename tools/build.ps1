# build.ps1 - one command: SketchUp model -> complete A3 sheet set in AutoCAD (+ QA, PNG, PDF).
#   powershell -File tools\build.ps1 -Project projects\seathis\project.json [-SkipExtract] [-Pdf] [-NoPng]
# Needs: SketchUp open with the model + HTML MCP v2 bridge started (unless -SkipExtract),
#        AutoCAD 2025 running. Output folder: out\<model name>\
param([Parameter(Mandatory)][string]$Project, [switch]$SkipExtract, [switch]$Pdf, [switch]$NoPng)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$node = 'C:\Users\This notebook\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$proj = Get-Content $Project -Raw -Encoding UTF8 | ConvertFrom-Json
$sw = [Diagnostics.Stopwatch]::StartNew()

# 1. extract (bridge command lpc_extract) -> out\<model>\model.json
if (-not $SkipExtract) {
    $ex = if ($proj.extract) { $proj.extract | ConvertTo-Json -Compress } else { '{}' }
    $exFile = Join-Path $env:TEMP 'lpc_extract_args.json'
    [IO.File]::WriteAllText($exFile, $ex)
    $log = & $node (Join-Path $PSScriptRoot 'lpc_bridge.mjs') extract $exFile     # file path: PS 5.1 mangles quotes
    $log | Write-Output
    if ($LASTEXITCODE -ne 0) { throw 'extraction failed' }
    $status = ($log | Select-Object -Last 1) | ConvertFrom-Json
    $model = $status.path
} else {
    $model = Join-Path $root ("out\{0}\model.json" -f $proj.model_dir)
}
$outDir = Split-Path $model -Parent
Write-Output "model: $model"

# 2. LISP
$lsp = Join-Path $outDir 'set.lsp'
& python -I (Join-Path $PSScriptRoot 'build_set.py') $model (Resolve-Path $Project).Path $lsp 0 0
if ($LASTEXITCODE -ne 0) { throw 'build_set failed' }

# 3. draw + save
$dwgName = if ($proj.dwg_name) { $proj.dwg_name } else { 'set.dwg' }
$dwg = Join-Path $outDir $dwgName
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'run_lisp.ps1') -Lisp $lsp -Dwg $dwg
if ($LASTEXITCODE -ne 0) { throw 'AutoCAD build failed' }

# 4. QA
& python -I (Join-Path $PSScriptRoot 'check_set.py') "$lsp.sheets.json" $model (Join-Path $outDir 'qa.json')
$qaFail = $LASTEXITCODE -ne 0

# 5. previews / PDF
if (-not $NoPng) { & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'plot_pdf.ps1') -Sheets "$lsp.sheets.json" -OutDir (Join-Path $outDir 'png') -Png | Out-Null }
if ($Pdf) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'plot_pdf.ps1') -Sheets "$lsp.sheets.json" -OutDir (Join-Path $outDir 'pdf')
    # merged submission PDF (python without -I so the user-site pypdf is found)
    & python (Join-Path $PSScriptRoot 'merge_pdf.py') "$lsp.sheets.json" (Join-Path $outDir 'pdf') ([IO.Path]::ChangeExtension($dwg, $null).TrimEnd('.') + '_set.pdf')
}
Write-Output ("done in {0:N0}s  dwg: {1}" -f $sw.Elapsed.TotalSeconds, $dwg)
if ($qaFail) { exit 1 }
