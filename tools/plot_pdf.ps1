# plot_pdf.ps1 - plot every sheet listed in <set>.lsp.sheets.json to A3 PDF (DWG To PDF.pc3,
# ISO full bleed A3, exact scale 1:<sheet scale>, monochrome.ctb, lineweights on).
#   powershell -File plot_pdf.ps1 -Sheets out\model\set.lsp.sheets.json -OutDir out\model\pdf
# Plots the ACTIVE drawing's model space by window = sheet frame.
# -Png: raster preview instead (PublishToWeb PNG.pc3, largest ~A3-ratio media, fit to page) for visual QA.
#  -Only A201,A301 limits the sheets.
param([Parameter(Mandatory)][string]$Sheets, [Parameter(Mandatory)][string]$OutDir, [switch]$Png, [string[]]$Only)

function Invoke-Retry([scriptblock]$Do, [int]$Tries = 120) {
    for ($i = 0; $i -lt $Tries; $i++) {
        try { return & $Do } catch {
            if ($_.Exception.Message -match '0x80010001|0x8001010A|busy|rejected') { Start-Sleep -Milliseconds 500 } else { throw } } }
    throw 'AutoCAD stayed busy'
}

if ($Only) { $Only = $Only -join "," -split "," }
$meta = Get-Content $Sheets -Raw -Encoding UTF8 | ConvertFrom-Json
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$acad = Invoke-Retry { [Runtime.InteropServices.Marshal]::GetActiveObject('AutoCAD.Application.25') }
$doc = Invoke-Retry { $acad.ActiveDocument }
Invoke-Retry { $doc.SetVariable('BACKGROUNDPLOT', 0) } | Out-Null
$lay = Invoke-Retry { $doc.ModelSpace.Layout }
if ($Png) {
    Invoke-Retry { $lay.ConfigName = 'PublishToWeb PNG.pc3'; $lay.RefreshPlotDeviceInfo() } | Out-Null
    $media = Invoke-Retry { $lay.GetCanonicalMediaNames() } | ForEach-Object {
        if ($_ -match '\(([\d.]+)_x_([\d.]+)_Pixels\)') { [pscustomobject]@{ n = $_; w = [double]$Matches[1]; h = [double]$Matches[2] } } } |
        Where-Object { $_.w -gt $_.h -and [math]::Abs($_.w / $_.h - 1.414) -lt 0.2 } | Sort-Object w -Descending | Select-Object -First 1
    Invoke-Retry { $lay.CanonicalMediaName = $media.n } | Out-Null
    "media: $($media.n)"
} else {
    Invoke-Retry { $lay.ConfigName = 'DWG To PDF.pc3'; $lay.RefreshPlotDeviceInfo() } | Out-Null
    Invoke-Retry { $lay.CanonicalMediaName = 'ISO_full_bleed_A3_(420.00_x_297.00_MM)' } | Out-Null
}
if (-not $Png) { Invoke-Retry { $lay.PaperUnits = 1 } | Out-Null }   # raster devices use pixels
Invoke-Retry { $lay.PlotRotation = 0; $lay.CenterPlot = $true
    $lay.StyleSheet = 'monochrome.ctb'; $lay.PlotWithPlotStyles = $true; $lay.PlotWithLineweights = $true } | Out-Null
$done = @()
$ext = if ($Png) { 'png' } else { 'pdf' }
foreach ($s in $meta.sheets) {
    if ($Only -and $Only -notcontains $s.no) { continue }
    $ll = [double[]]@($s.x, $s.y); $ur = [double[]]@(($s.x + $s.w), ($s.y + $s.h))
    Invoke-Retry { $lay.SetWindowToPlot($ll, $ur); $lay.PlotType = 4 } | Out-Null      # acWindow
    if ($Png) { Invoke-Retry { $lay.UseStandardScale = $true; $lay.StandardScale = 0 } | Out-Null }   # fit
    else { Invoke-Retry { $lay.UseStandardScale = $false; $lay.SetCustomScale(1, [double]$s.scale) } | Out-Null }
    $pdf = Join-Path $OutDir ("{0}.{1}" -f $s.no, $ext)
    Remove-Item $pdf -ErrorAction SilentlyContinue
    $ok = Invoke-Retry { $doc.Plot.PlotToFile($pdf) }
    $done += "{0} {1}" -f $s.no, $(if (Test-Path $pdf) { 'ok' } else { "FAILED ($ok)" })
}
$done
