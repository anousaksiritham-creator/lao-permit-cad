# run_lisp.ps1 - load a generated LISP into AutoCAD 2025 and wait for its done-flag file.
#   powershell -File run_lisp.ps1 -Lisp out\model\set.lsp -Dwg out\model\Seathis_Office.dwg
# -Dwg: activates that drawing if open, opens it if it exists, otherwise starts a new drawing and
#       saves it there. Without -Dwg the active drawing is used (and saved only with -SaveAs).
# Retries COM calls rejected while AutoCAD is busy (RPC_E_CALL_REJECTED).
param([Parameter(Mandatory)][string]$Lisp, [string]$Dwg, [string]$SaveAs, [switch]$NewDrawing, [int]$TimeoutSec = 900)

function Invoke-Retry([scriptblock]$Do, [int]$Tries = 120) {
    for ($i = 0; $i -lt $Tries; $i++) {
        try { return & $Do } catch {
            if ($_.Exception.Message -match '0x80010001|0x8001010A|busy|rejected') { Start-Sleep -Milliseconds 500 } else { throw } } }
    throw "AutoCAD stayed busy"
}

$Lisp = (Resolve-Path $Lisp).Path
$flag = "$Lisp.done"
Remove-Item $flag -ErrorAction SilentlyContinue
$acad = Invoke-Retry { [Runtime.InteropServices.Marshal]::GetActiveObject('AutoCAD.Application.25') }
$doc = $null
if ($Dwg) {
    $full = [IO.Path]::GetFullPath($Dwg)
    $SaveAs = $full
    foreach ($d in (Invoke-Retry { $acad.Documents })) { if ((Invoke-Retry { $d.FullName }) -eq $full) { $doc = $d } }
    if (-not $doc -and (Test-Path $full)) { $doc = Invoke-Retry { $acad.Documents.Open($full) } }
    if (-not $doc) { $doc = Invoke-Retry { $acad.Documents.Add() } }
    Invoke-Retry { $doc.Activate() } | Out-Null
    Start-Sleep 1
} elseif ($NewDrawing) {
    $doc = Invoke-Retry { $acad.Documents.Add() }
    Invoke-Retry { $doc.Activate() } | Out-Null
    Start-Sleep 1
}
$doc = Invoke-Retry { $acad.ActiveDocument }
Write-Output ("drawing: " + (Invoke-Retry { $doc.Name }))
$p = $Lisp.Replace('\', '/')
Invoke-Retry { $doc.SendCommand("(load `"$p`") ") } | Out-Null
$t = 0
while (-not (Test-Path $flag) -and $t -lt $TimeoutSec) { Start-Sleep 2; $t += 2 }
if (-not (Test-Path $flag)) { throw "LISP did not finish in $TimeoutSec s (see AutoCAD command line / LOGFILEMODE log)" }
Write-Output "lisp done in ${t}s"
Invoke-Retry { $acad.ZoomExtents() } | Out-Null
if ($SaveAs) {
    $full = [IO.Path]::GetFullPath($SaveAs)
    if ((Invoke-Retry { $doc.FullName }) -eq $full) { Invoke-Retry { $doc.Save() } | Out-Null }
    else { Invoke-Retry { $doc.SaveAs($full) } | Out-Null }
    Write-Output "saved: $full"
}
