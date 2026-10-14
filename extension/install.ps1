# install.ps1 - add the lao-permit-cad extraction command to the HTML MCP v2 SketchUp extension.
#   powershell -File extension\install.ps1
# 1. copies tools\lpc_extract.rb into the extension folder (Plugins\sketchup_html_mcp_v2)
# 2. applies main.rb.lpc.patch (adds bridge command `lpc_extract` + require_relative 'lpc_extract') once,
#    keeping a backup main.rb.pre-lpc.bak
# Then restart SketchUp (or load lpc_extract.rb from the Ruby Console) and Start bridge.
$plug = Join-Path $env:APPDATA 'SketchUp\SketchUp 2025\SketchUp\Plugins\sketchup_html_mcp_v2'
if (-not (Test-Path $plug)) { throw "HTML MCP v2 extension not found: $plug" }
$repo = Split-Path $PSScriptRoot -Parent
Copy-Item (Join-Path $repo 'tools\lpc_extract.rb') $plug -Force
$main = Join-Path $plug 'main.rb'
if ((Get-Content $main -Raw) -match "when 'lpc_extract'") { 'main.rb already has lpc_extract'; return }
Copy-Item $main (Join-Path $plug 'main.rb.pre-lpc.bak') -Force
Push-Location $plug
& git apply --ignore-whitespace (Join-Path $PSScriptRoot 'main.rb.lpc.patch')
$ok = $LASTEXITCODE -eq 0
Pop-Location
if (-not $ok) { throw 'patch failed - apply extension\main.rb.lpc.patch by hand' }
'installed: lpc_extract command + lpc_extract.rb'
