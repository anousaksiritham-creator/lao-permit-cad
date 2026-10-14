# LaoPermitCad.psm1 - helpers to build Lao building-permit sheets in AutoCAD 2025 via COM.
# Import-Module .\tools\LaoPermitCad.psm1 ; Connect-Acad ; New-PermitSheet -No A202 -TitleLao 'ແຜນຜັງ ຊັ້ນ 1' -Scale 75 -X 673356 -Y 84688

$script:FrameBlock = 'A$C2875ed45'   # A3 frame + title strip, 43108 x 29700 at scale 1 (= 1:100)
$script:FrameW = 43108; $script:FrameH = 29700

function Connect-Acad {
    # Plain 'AutoCAD.Application' fails (MK_E_UNAVAILABLE); use the versioned ProgID.
    $script:Acad = [Runtime.InteropServices.Marshal]::GetActiveObject('AutoCAD.Application.25')
    $script:Doc = $script:Acad.ActiveDocument
    $script:MS = $script:Doc.ModelSpace
    [pscustomobject]@{ Drawing = $script:Doc.FullName; Units = $script:Doc.GetVariable('INSUNITS'); Entities = $script:MS.Count }
}

function P([double]$x, [double]$y, [double]$z = 0) { , [double[]]@($x, $y, $z) }   # comma keeps double[] (no unroll)

function Use-Layer([string]$Name, [int]$Color = 7, [string]$Linetype = 'Continuous') {
    try { $l = $script:Doc.Layers.Item($Name) } catch { $l = $script:Doc.Layers.Add($Name); $l.color = $Color
        if ($Linetype -ne 'Continuous') { try { $l.Linetype = $Linetype } catch {} } }
    $l
}

# Frame scale factor for a sheet scale denominator (75 -> 0.75, 100 -> 1). Site 1:200 and
# detail 1:20/1:40 sheets use a scale-1 frame and insert the drawing as a scaled block.
function Get-FrameFactor([int]$Scale) { if ($Scale -in 75, 100) { $Scale / 100 } else { 1 } }

# Block factor for a view drawn 1:1 placed on a frame: viewScale 200 on 1:100 frame -> 0.5, 20 -> 5.
function Get-ViewFactor([int]$ViewScale) { $f = Get-FrameFactor $ViewScale; ($f * 100) / $ViewScale }

function Add-LaoMText([double]$X, [double]$Y, [string]$Text, [double]$Height = 300, [string]$Layer = 'SYM_DIM',
                      [string]$Font = 'Phetsarath OT', [double]$Width = 0) {
    $m = $script:MS.AddMText((P $X $Y), $Width, "{\f$Font|b0|i0|c0|p2;$Text}")
    $m.Height = $Height; $m.Layer = $Layer; $m
}

function New-PermitSheet {
    param([Parameter(Mandatory)][string]$No, [Parameter(Mandatory)][string]$TitleLao,
          [Parameter(Mandatory)][int]$Scale, [Parameter(Mandatory)][double]$X, [Parameter(Mandatory)][double]$Y)
    $f = Get-FrameFactor $Scale
    $fr = $script:MS.InsertBlock((P $X $Y), $script:FrameBlock, $f, $f, $f, 0)
    $fr.Layer = (Use-Layer 'A-ANNO-TITLEBLOCK' 2).Name
    # Title-strip fields, middle-centred; centres measured on reference sheets (frame scale 1 units)
    $h = if ($f -lt 1) { 300 } else { 400 }
    $fields = @(@((Add-LaoMText 0 0 $TitleLao $h), 30100, 3902),
                @($script:MS.AddMText((P 0 0), 0, $No), 39139, 3318),
                @($script:MS.AddMText((P 0 0), 0, "1/$Scale"), 39207, 1447))
    foreach ($fd in $fields) { $m = $fd[0]; $m.Height = $h; $m.Layer = 'SYM_DIM'
        $m.AttachmentPoint = 5   # acAttachmentPointMiddleCenter
        $m.InsertionPoint = (P ($X + $fd[1] * $f) ($Y + $fd[2] * $f)) }
    [pscustomobject]@{ No = $No; Frame = $fr.Handle; Origin = "$X,$Y"; Width = $script:FrameW * $f; Height = $script:FrameH * $f }
}

# Next free origin in a sheet row (rows: 1:100 at Y=84688/20801, 1:75 at Y=84688/56457).
function Get-NextSheetOrigin([double]$RowY, [int]$Scale) {
    $f = Get-FrameFactor $Scale; $maxX = 0
    for ($i = 0; $i -lt $script:MS.Count; $i++) { $e = $script:MS.Item($i)
        if ($e.ObjectName -eq 'AcDbBlockReference' -and $e.EffectiveName -eq $script:FrameBlock) {
            $p = $e.InsertionPoint; if ([math]::Abs($p[1] - $RowY) -lt 100) { $maxX = [math]::Max($maxX, $p[0] + $script:FrameW * $e.XScaleFactor) } } }
    $gap = if ($f -lt 1) { 3156 } else { 4000 }   # reference: 1:75 step 35487, 1:100 step 45987..47787
    [pscustomobject]@{ X = $maxX + $gap; Y = $RowY }
}

# Level mark text: 'ລະດັບຄໍດິນ ບສລ (+600)'. Places tick line + Saysettha text on A-FLOR-LEVL.
function Add-LevelMark([double]$X, [double]$Y, [string]$NameLao, [int]$LevelMm, [double]$Len = 3000, [switch]$Below) {
    $lay = (Use-Layer 'A-FLOR-LEVL' 51).Name
    $ln = $script:MS.AddLine((P $X $Y), (P ($X + $Len) $Y)); $ln.Layer = $lay
    $sign = if ($LevelMm -eq 0) { '±' } elseif ($LevelMm -gt 0) { '+' } else { '' }
    $txt = "$NameLao ($sign$(if($LevelMm -eq 0){'00'}else{$LevelMm}))"
    $ty = if ($Below) { $Y - 60 } else { $Y + 400 }   # Below: for marks closer than ~500 to the next one
    # Phetsarath OT inline: Saysettha OT only renders through a text style, not an inline \f code
    $t = $script:MS.AddMText((P ($X + 200) $ty), 0, "{\fPhetsarath OT|b0|i0|c0|p2;$txt}"); $t.Height = 210; $t.Layer = $lay
    $t
}

# Material callout with leader (layer Dimention, h 250).
function Add-Callout([double[]]$From, [double[]]$To, [string]$TextLao, [double]$Height = 250) {
    $t = $script:MS.AddMText((P ($To[0] + 100) ($To[1] + $Height)), 0, "{\fPhetsarath OT|b0|i0|c0|p2;$TextLao}")
    $t.Height = $Height; $t.Layer = 'Dimention'
    $pts = [double[]]@($From[0], $From[1], 0, $To[0], $To[1], 0)
    $ld = $script:MS.AddLeader($pts, $t, 2); $ld.Layer = 'Dimention'   # 2 = acLineWithArrow, attached to the MText
    $t
}

# Insert a DWG/DXF exported from SketchUp (2D view, mm, 1:1) as a block at a scale factor.
function Import-ViewDwg([string]$Path, [double]$X, [double]$Y, [double]$Factor = 1) {
    $b = $script:MS.InsertBlock((P $X $Y), $Path, $Factor, $Factor, $Factor, 0); $b
}

function Zoom-Window([double]$X0, [double]$Y0, [double]$X1, [double]$Y1) { $script:Acad.ZoomWindow((P $X0 $Y0), (P $X1 $Y1)) }

Export-ModuleMember -Function Connect-Acad, Use-Layer, Get-FrameFactor, Get-ViewFactor, Add-LaoMText, New-PermitSheet,
    Get-NextSheetOrigin, Add-LevelMark, Add-Callout, Import-ViewDwg, Zoom-Window
