"""Quick check: draws a test sheet in a new drawing. Run: python test_smoke.py"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import autocad_mcp as m

print(m.new_drawing())
print(m.status())
m.create_layer("MCP-TEST", 1)
print(m.draw_rectangle([0, 0], 6000, 4000, layer="MCP-TEST"))
print(m.draw_circle([3000, 2000], 800, layer="MCP-TEST", color=3))
print(m.draw_line([0, 0], [6000, 4000], layer="MCP-TEST"))
print(m.add_text("AutoCAD MCP OK", [500, 4300], 250))
print(m.add_aligned_dimension([0, 0], [6000, 0], [3000, -600]))
print(m.add_hatch([[4500, 200], [5800, 200], [5800, 1200], [4500, 1200]], "ANSI31", 50))
m.zoom_extents()
print(m.list_entities(limit=10)["total"], "entities")
