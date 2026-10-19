# Compatibility entry point: live and unsaved by default. -Dwg is explicit export opt-in.
param([Parameter(Mandatory)][string]$Lisp,[string]$Dwg,[string]$SaveAs,
      [string]$DrawingName,[switch]$NewDrawing,[int]$TimeoutSec=300)
$ErrorActionPreference='Stop'
if($Dwg -and $SaveAs){throw 'Choose Dwg or SaveAs'}
$destination=if($SaveAs){$SaveAs}else{$Dwg}
& (Join-Path $PSScriptRoot 'run_live.ps1') -Lisp $Lisp -DrawingName $DrawingName -NewDrawing:$NewDrawing -SaveAs $destination -TimeoutSec $TimeoutSec
