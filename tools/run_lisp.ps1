# run_lisp.ps1 - load a generated LISP into AutoCAD 2025 and wait for its done-flag file.
#   powershell -File run_lisp.ps1 -Lisp out\model\set.lsp [-NewDrawing] [-SaveAs out\model\Seathis.dwg] [-TimeoutSec 900]
# Retries COM calls rejected while AutoCAD is busy (RPC_E_CALL_REJECTED).
param([Parameter(Mandatory)][string]$Lisp, [switch]$NewDrawing, [string]$SaveAs, [int]$TimeoutSec = 900)

function Invoke-Retry([scriptblock]$Do, [int]$Tries = 60) {
    for ($i = 0; $i -lt $Tries; $i++) {
        try { return & $Do } catch {
            if ($_.Exception.Message -match '0x80010001|0x8001010A|busy|rejected') { Start-Sleep -Milliseconds 500 } else { throw } } }
    throw "AutoCAD stayed busy"
}

$Lisp = (Resolve-Path $Lisp).Path
$flag = "$Lisp.done"
Remove-Item $flag -ErrorAction SilentlyContinue
$acad = Invoke-Retry { [Runtime.InteropServices.Marshal]::GetActiveObject('AutoCAD.Application.25') }
if ($NewDrawing) {
    $doc = Invoke-Retry { $acad.Documents.Add() }
    Invoke-Retry { $doc.Activate() } | Out-Null
    Start-Sleep 2
}
$doc = Invoke-Retry { $acad.ActiveDocument }
$name = Invoke-Retry { $doc.Name }
Write-Output "drawing: $name"
$p = $Lisp.Replace('\', '/')
Invoke-Retry { $doc.SendCommand("(load `"$p`") ") } | Out-Null
$t = 0
while (-not (Test-Path $flag) -and $t -lt $TimeoutSec) { Start-Sleep 3; $t += 3 }
if (-not (Test-Path $flag)) { throw "LISP did not finish in $TimeoutSec s (check AutoCAD command line)" }
Write-Output "lisp done in ${t}s"
Invoke-Retry { $acad.ZoomExtents() } | Out-Null
if ($SaveAs) {
    $full = [IO.Path]::GetFullPath($SaveAs)
    Invoke-Retry { $doc.SaveAs($full) } | Out-Null
    Write-Output "saved: $full"
}
