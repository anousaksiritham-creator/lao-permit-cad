# Live drawing only by default. Read retries are allowed; mutations are never retried.
param([Parameter(Mandatory)][string]$Lisp, [string]$DrawingName,
      [switch]$NewDrawing, [string]$SaveAs, [int]$TimeoutSec=300)
$ErrorActionPreference='Stop'
if ($DrawingName -and $NewDrawing) { throw 'Choose DrawingName or NewDrawing' }
if ($TimeoutSec -lt 1) { throw 'TimeoutSec must be positive' }
function Read-Acad([scriptblock]$Read) {
    for ($i=0; $i -lt 20; $i++) {
        try { return & $Read } catch {
            if ($_.Exception.Message -notmatch '0x80010001|0x8001010A|rejected|busy') { throw }
            Start-Sleep -Milliseconds 250
        }
    }
    throw 'AutoCAD busy; read failed'
}
function Lisp-String([string]$Value) { '"'+$Value.Replace('\','/').Replace('"','\"')+'"' }
$source=(Resolve-Path -LiteralPath $Lisp).Path
$body=[IO.File]::ReadAllText($source)
if ($body -match '(?i)\b(?:vla-saveas|vla-save|saveas|qsave|dxfout)\b') {
    throw 'LISP contains drawing-file writes; live source must not save/export. Use explicit runner SaveAs instead.'
}
$run=[Guid]::NewGuid().ToString('N')
$runDir=Join-Path (Split-Path $PSScriptRoot -Parent) ('out\runs\'+$run)
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
$journalPath=Join-Path $runDir 'live-run.json'
$completion=Join-Path $runDir 'completion.txt'
$acad=$null
foreach ($progid in @('AutoCAD.Application.25','AutoCAD.Application')) {
    try { $acad=[Runtime.InteropServices.Marshal]::GetActiveObject($progid); break } catch {}
}
if ($null -eq $acad) { throw 'Open AutoCAD first; this runner never launches it' }
$original=Read-Acad { $acad.ActiveDocument }
if ((Read-Acad { $original.GetVariable('CMDACTIVE') }) -ne 0) { throw 'Finish the current AutoCAD command first' }
if ($DrawingName) {
    $doc=Read-Acad { $acad.Documents.Item($DrawingName) }
} elseif ($NewDrawing -or (Read-Acad { $original.ModelSpace.Count }) -ne 0 -or (Read-Acad { $original.FullName })) {
    $doc=$acad.Documents.Add() # mutation, once
} else { $doc=$original }
if ((Read-Acad { $doc.ModelSpace.Count }) -ne 0 -or (Read-Acad { $doc.PaperSpace.Count }) -ne 0 -or (Read-Acad { $doc.FullName })) {
    throw 'Generation requires an empty unsaved drawing; existing drawings are preserved'
}
$doc.Activate()
$name=Read-Acad { $doc.Name }
$doc.SetVariable('USERS3',$run)
$journal=[ordered]@{run_id=$run;document=$name;source_sha256=(Get-FileHash -LiteralPath $source).Hash;
    state='PREPARED';save_requested=[bool]$SaveAs;source=$source;completion=$completion;
    warning='On timeout/COM error inspect the target; do not automatically resubmit'}
function Write-Journal { $journal | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $journalPath -Encoding UTF8 }
Write-Journal
$guard=Lisp-String $run
$flag=Lisp-String $completion
# No LOAD, SCRIPT dialogs or SECURELOAD changes. Forms come from reviewed generated LISP.
$command=@"
(progn
 (vl-load-com)
 (if (/= (getvar "USERS3") $guard) (exit))
 (setq lpc-run-vars (mapcar '(lambda (k) (cons k (getvar k))) '("FILEDIA" "CMDDIA" "CMDECHO" "OSMODE")))
 (setvar "FILEDIA" 0) (setvar "CMDDIA" 0) (setvar "OSMODE" 0) (setvar "INSUNITS" 4) (setvar "MEASUREMENT" 1)
 (setvar "DIMLFAC" 1.0)
 (setq lpc-run-result (vl-catch-all-apply '(lambda ()
 $body
 ) nil))
 (foreach pair lpc-run-vars (setvar (car pair) (cdr pair)))
 (setq lpc-run-file (open $flag "w"))
 (write-line (if (vl-catch-all-error-p lpc-run-result) (strcat "ERROR: " (vl-catch-all-error-message lpc-run-result)) "COMPLETE") lpc-run-file)
 (close lpc-run-file)
 (princ))
"@
$journal.state='SUBMITTED_OR_UNKNOWN'; Write-Journal
try { $doc.SendCommand($command+"`n") } catch {
    $journal.error=$_.Exception.Message; Write-Journal
    throw 'Submission result unknown. Do not retry; inspect target and live-run.json'
}
$timer=[Diagnostics.Stopwatch]::StartNew()
while (-not (Test-Path -LiteralPath $completion) -and $timer.Elapsed.TotalSeconds -lt $TimeoutSec) { Start-Sleep -Milliseconds 250 }
if (-not (Test-Path -LiteralPath $completion)) {
    $journal.state='TIMEOUT_UNKNOWN'; Write-Journal
    throw "No completion marker. Inspect $name; no retry or save performed"
}
$message=[IO.File]::ReadAllText($completion).Trim()
if ($message -ne 'COMPLETE') { $journal.state='FAILED_PARTIAL'; $journal.error=$message; Write-Journal; throw $message }
$journal.entity_count=Read-Acad { $doc.ModelSpace.Count }
$journal.units_code=Read-Acad { $doc.GetVariable('INSUNITS') }
if ($journal.entity_count -eq 0 -or $journal.units_code -ne 4) { $journal.state='FAILED_READBACK'; Write-Journal; throw 'Readback failed' }
$journal.state='DRAWN_UNSAVED'
if ($SaveAs) {
    $destination=[IO.Path]::GetFullPath($SaveAs)
    if (Test-Path -LiteralPath $destination) { Write-Journal; throw 'Refusing to overwrite existing file' }
    $doc.SaveAs($destination) # opt-in, once
    $journal.state='DRAWN_AND_SAVED'; $journal.saved_path=$destination
}
Write-Journal
$journal | ConvertTo-Json -Depth 8
