# Deep study of a permit DWG open in AutoCAD 2025. Usage: powershell -File study_dwg.ps1 <outDir>
param([string]$Out = "$PSScriptRoot\..\study")
$acad = [Runtime.InteropServices.Marshal]::GetActiveObject("AutoCAD.Application.25")
$doc = $acad.ActiveDocument; $ms = $doc.ModelSpace
New-Item -ItemType Directory -Force $Out | Out-Null
function W($name, $lines) { $lines | Out-File (Join-Path $Out $name) -Encoding utf8 }

# Layers with full props
W layers.tsv (@("name`tcolor`tlinetype`tlineweight`tplot") + ($doc.Layers | % { "$($_.Name)`t$($_.color)`t$($_.Linetype)`t$($_.Lineweight)`t$($_.Plottable)" }))
# Dimension styles: activate each and read key vars
$cur = $doc.ActiveDimStyle
$dl = @("name`tDIMSCALE`tDIMTXT`tDIMASZ`tDIMTXSTY`tDIMBLK`tDIMEXO`tDIMEXE`tDIMDEC`tDIMLFAC")
foreach ($s in $doc.DimStyles) { try { $doc.ActiveDimStyle = $s
  $v = 'DIMSCALE','DIMTXT','DIMASZ','DIMTXSTY','DIMBLK','DIMEXO','DIMEXE','DIMDEC','DIMLFAC' | % { $doc.GetVariable($_) }
  $dl += "$($s.Name)`t" + ($v -join "`t") } catch {} }
$doc.ActiveDimStyle = $cur; W dimstyles.tsv $dl

# Frames (title block A$C2875ed45) + per-frame contents
$frames = @(); $all = @()
for ($i = 0; $i -lt $ms.Count; $i++) { $e = $ms.Item($i)
  try { $mn=$null;$mx=$null; $e.GetBoundingBox([ref]$mn,[ref]$mx) } catch { continue }
  $o = [pscustomobject]@{ t=$e.ObjectName; l=$e.Layer; x0=$mn[0]; y0=$mn[1]; x1=$mx[0]; y1=$mx[1]; e=$e }
  $all += $o
  if ($o.t -eq 'AcDbBlockReference' -and $e.EffectiveName -eq 'A$C2875ed45') { $frames += $o } }
$fl = @(); $k = 0
foreach ($f in ($frames | Sort-Object { -[math]::Round($_.y0/1000) }, x0)) { $k++
  $in = $all | ? { $_.x0 -ge $f.x0 -and $_.x1 -le $f.x1 -and $_.y0 -ge $f.y0 -and $_.y1 -le $f.y1 -and $_.e -ne $f.e }
  $txt = ($in | ? { $_.t -in 'AcDbText','AcDbMText' } | % { ($_.e.TextString.Replace('\P',' ') -replace '\\[A-Za-z][^;\\]*;|[{}]','').Trim() }) -join ' / '
  $att = ''; if ($f.e.HasAttributes) { $att = ($f.e.GetAttributes() | % { "$($_.TagString)=$($_.TextString)" }) -join '; ' }
  $lay = ($in | Group-Object l | Sort-Object Count -Desc | Select -First 8 | % { "$($_.Name):$($_.Count)" }) -join ','
  $typ = ($in | Group-Object t | Sort-Object Count -Desc | % { "$($_.Name -replace 'AcDb',''):$($_.Count)" }) -join ','
  $blk = ($in | ? { $_.t -eq 'AcDbBlockReference' } | % { "$($_.e.EffectiveName)@$([math]::Round($_.e.XScaleFactor,2))" } | Group-Object | % { "$($_.Name)x$($_.Count)" }) -join ','
  $fl += "## Frame $k  scale=$([math]::Round($f.e.XScaleFactor,2))  origin=$([math]::Round($f.x0)),$([math]::Round($f.y0))  size=$([math]::Round($f.x1-$f.x0))x$([math]::Round($f.y1-$f.y0))"
  $fl += "attrs: $att"; $fl += "text: $txt"; $fl += "layers: $lay"; $fl += "types: $typ"; $fl += "blocks: $blk"; $fl += "" }
W frames.md $fl

# Hatches, mlines, leaders, dims
W hatches.tsv ($all | ? t -eq 'AcDbHatch' | % { "$($_.l)`t$($_.e.PatternName)`t$($_.e.PatternScale)`t$($_.e.PatternAngle)" } | Group-Object | % { "$($_.Name)`t$($_.Count)" })
W mlines.tsv ($all | ? t -eq 'AcDbMline' | % { "$($_.l)`t$($_.e.StyleName)`t$($_.e.MLineScale)" } | Group-Object | % { "$($_.Name)`t$($_.Count)" })
W dims.tsv ($all | ? { $_.t -like '*Dimension' } | % { "$($_.l)`t$($_.e.StyleName)`t$($_.e.ScaleFactor)`t$([math]::Round($_.e.Measurement))" } | Group-Object | Sort-Object Count -Desc | % { "$($_.Name)`t$($_.Count)" })
W polylines.tsv ($all | ? t -eq 'AcDbPolyline' | % { "$($_.l)`tw=$($_.e.ConstantWidth)`tclosed=$($_.e.Closed)" } | Group-Object | Sort-Object Count -Desc | % { "$($_.Name)`t$($_.Count)" })
# Block definitions: name, entity count, attribute tags
W blockdefs.tsv ($doc.Blocks | ? { -not $_.IsLayout -and -not $_.IsXRef } | % { $b=$_; $tags = @(); foreach($x in $b){ if($x.ObjectName -eq 'AcDbAttributeDefinition'){ $tags += $x.TagString } }; "$($b.Name)`t$($b.Count)`t$($tags -join ',')" })
"frames=$($frames.Count) entities=$($all.Count)"

