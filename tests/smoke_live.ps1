# Opt-in Windows/AutoCAD integration test. Uses only new unsaved scratch documents.
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$area=Join-Path $root 'out\smoke-live'
New-Item -ItemType Directory -Path $area -Force | Out-Null
$fixture=Join-Path $area 'fixture.lsp'
@'
(vl-load-com)
(setq sm (vla-get-ModelSpace (vla-get-ActiveDocument (vlax-get-acad-object))))
(vla-AddLine sm (vlax-3d-point 0 0 0) (vlax-3d-point 1000 0 0))
(vla-AddDimAligned sm (vlax-3d-point 0 0 0) (vlax-3d-point 1000 0 0) (vlax-3d-point 500 200 0))
(princ)
'@ | Set-Content -LiteralPath $fixture -Encoding ASCII
$app=[Runtime.InteropServices.Marshal]::GetActiveObject('AutoCAD.Application.25')
$original=$app.ActiveDocument
$before=@{}
foreach($d in $app.Documents){$before[$d.Name]=@($d.FullName,$d.ModelSpace.Count)}
$created=$null
try {
    $result=((& (Join-Path $root 'tools\run_live.ps1') -Lisp $fixture -NewDrawing -TimeoutSec 30) -join "`n") | ConvertFrom-Json
    $created=$app.Documents.Item($result.document)
    if($result.state -ne 'DRAWN_UNSAVED' -or $created.FullName -ne '' -or $created.ModelSpace.Count -ne 2){throw 'Live unsaved drawing failed'}
    if($created.GetVariable('INSUNITS') -ne 4){throw 'Wrong units'}
    $dim=@($created.ModelSpace | Where-Object {$_.ObjectName -eq 'AcDbAlignedDimension'})[0]
    if([Math]::Abs($dim.Measurement-1000) -gt 0.000001){throw 'Native dimension readback mismatch'}
    $rejected=$false
    try{& (Join-Path $root 'tools\run_live.ps1') -Lisp $fixture -DrawingName $created.Name | Out-Null}catch{$rejected=$true}
    if(!$rejected -or $created.ModelSpace.Count -ne 2){throw 'Nonempty drawing was not preserved'}
    foreach($d in $app.Documents){if($before.ContainsKey($d.Name)){if($d.FullName -ne $before[$d.Name][0] -or $d.ModelSpace.Count -ne $before[$d.Name][1]){throw 'Existing document changed'}}}
    Write-Output 'PASS: live draw, mm, native dimension, unsaved, duplicate prevention, original-document counts/path preservation'
} finally {
    # Only the document created by this test is closed, without saving.
    if($null -ne $created){$created.Close($false)}
    $original.Activate()
}
