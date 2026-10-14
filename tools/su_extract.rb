# su_extract.rb - run the extractor from SketchUp's Ruby Console (manual fallback).
#   load 'D:/ANS/Claude/CAD train AI/lao-permit-cad/tools/su_extract.rb'
# Options before loading: $LPC_ARGS = { 'cuts' => [1500], 'skip' => ['17 '], 'hidden' => true }
# Normally Claude runs the same code through the HTML MCP v2 bridge command `lpc_extract`.
load File.join(__dir__, 'lpc_extract.rb')
r = LaoPermitExtract.run($LPC_ARGS || {})
puts "LPC export OK: #{r.inspect}"
r
