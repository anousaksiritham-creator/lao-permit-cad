"""AutoCAD MCP server (COM automation, target: AutoCAD 2025 on Windows).

Run:  python autocad_mcp.py   (stdio transport)
AutoCAD 2025 should be open; if not, the server launches its executable and connects via COM.
Units: drawing units (usually mm). Points are [x, y] or [x, y, z].
"""
import time
import functools

import pythoncom
import win32com.client
try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

mcp = FastMCP("autocad")

PROG_IDS = ["AutoCAD.Application.25"]  # AutoCAD 2025 only
ACAD_EXE = r"C:\Program Files\Autodesk\AutoCAD 2025\acad.exe"
_acad = None


def _retry(fn):
    """AutoCAD rejects COM calls while busy (RPC_E_CALL_REJECTED) - retry a few times."""
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        last = None
        for _ in range(10):
            try:
                return fn(*a, **kw)
            except pythoncom.com_error as e:
                last = e
                if e.hresult in (-2147418111, -2147417846):  # call rejected / busy
                    time.sleep(0.5)
                    continue
                raise
        raise last
    return wrapper


def acad():
    global _acad
    pythoncom.CoInitialize()
    if _acad is not None:
        try:
            _acad.Name
            return _acad
        except Exception:
            _acad = None
    for pid in PROG_IDS:
        try:
            _acad = win32com.client.GetActiveObject(pid)
            break
        except Exception:
            continue
    if _acad is None:
        # COM CreateInstance is unreliable for AutoCAD; launch the exe and wait for it to register
        import subprocess
        subprocess.Popen([ACAD_EXE, "/nologo"])
        for _ in range(120):
            time.sleep(2)
            try:
                _acad = win32com.client.GetActiveObject(PROG_IDS[0])
                _acad.Documents.Count
                break
            except Exception:
                _acad = None
        if _acad is None:
            raise RuntimeError("AutoCAD 2025 did not start. Open AutoCAD 2025 manually, close any dialogs, and retry.")
    return _acad


def doc():
    a = acad()
    if a.Documents.Count == 0:
        a.Documents.Add()
    return a.ActiveDocument


def ms():
    return doc().ModelSpace


def pt(p):
    p = list(map(float, p)) + [0.0] * (3 - len(p))
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, p[:3])


def flat2d(points):
    vals = []
    for p in points:
        vals += [float(p[0]), float(p[1])]
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, vals)


def _apply(ent, layer=None, color=None):
    if layer:
        _ensure_layer(layer)
        ent.Layer = layer
    if color is not None:
        ent.Color = int(color)
    ent.Update()
    return {"handle": ent.Handle, "type": ent.ObjectName, "layer": ent.Layer}


def _ensure_layer(name, color=None):
    layers = doc().Layers
    try:
        lay = layers.Item(name)
    except Exception:
        lay = layers.Add(name)
    if color is not None:
        lay.Color = int(color)
    return lay


# ---------------------------------------------------------------- documents

@mcp.tool()
@_retry
def status() -> dict:
    """Connect to AutoCAD and report version, open drawings and the active drawing."""
    a = acad()
    d = doc()
    return {
        "version": a.Version,
        "active": d.FullName or d.Name,
        "documents": [a.Documents.Item(i).Name for i in range(a.Documents.Count)],
        "insunits": d.GetVariable("INSUNITS"),
        "modelspace_entities": d.ModelSpace.Count,
    }


@mcp.tool()
@_retry
def new_drawing(template: str = "") -> str:
    """Create a new drawing (optional .dwt template path) and make it active."""
    d = acad().Documents.Add(template) if template else acad().Documents.Add()
    return d.Name


@mcp.tool()
@_retry
def open_drawing(path: str) -> str:
    """Open a .dwg/.dxf file and make it active."""
    return acad().Documents.Open(path).FullName


@mcp.tool()
@_retry
def save_drawing(path: str = "") -> str:
    """Save the active drawing. With a path (.dwg) it does Save As."""
    d = doc()
    if path:
        d.SaveAs(path)
    else:
        d.Save()
    return d.FullName


@mcp.tool()
@_retry
def zoom_extents() -> str:
    """Zoom to the extents of the drawing."""
    acad().ZoomExtents()
    return "ok"


@mcp.tool()
@_retry
def send_command(command: str) -> str:
    """Send a raw command string to the AutoCAD command line, e.g. "_.ZOOM _E ".
    End with a space or \\n to press Enter. Runs asynchronously."""
    if not command.endswith((" ", "\n")):
        command += "\n"
    doc().SendCommand(command)
    return "sent"


@mcp.tool()
@_retry
def get_variable(name: str) -> str:
    """Read a system variable (e.g. INSUNITS, LTSCALE, DIMSCALE)."""
    return str(doc().GetVariable(name))


@mcp.tool()
@_retry
def set_variable(name: str, value: str) -> str:
    """Set a system variable. Value is converted to int/float when possible."""
    v: object = value
    for conv in (int, float):
        try:
            v = conv(value)
            break
        except ValueError:
            pass
    doc().SetVariable(name, v)
    return str(doc().GetVariable(name))


# ------------------------------------------------------------------- layers

@mcp.tool()
@_retry
def list_layers() -> list:
    """List layers with color, on/off, frozen, locked."""
    out = []
    for lay in doc().Layers:
        out.append({"name": lay.Name, "color": lay.Color, "on": lay.LayerOn,
                    "frozen": lay.Freeze, "locked": lay.Lock})
    return out


@mcp.tool()
@_retry
def create_layer(name: str, color: int = 7, make_current: bool = False) -> str:
    """Create (or update) a layer. color = ACI index (1 red, 2 yellow, 3 green, 4 cyan, 5 blue, 6 magenta, 7 white)."""
    lay = _ensure_layer(name, color)
    if make_current:
        doc().ActiveLayer = lay
    return lay.Name


# ----------------------------------------------------------------- drawing

@mcp.tool()
@_retry
def draw_line(start: list[float], end: list[float], layer: str = "", color: int | None = None) -> dict:
    """Draw a line from start [x,y(,z)] to end."""
    return _apply(ms().AddLine(pt(start), pt(end)), layer, color)


@mcp.tool()
@_retry
def draw_polyline(points: list[list[float]], closed: bool = False, layer: str = "",
                  color: int | None = None, width: float = 0.0) -> dict:
    """Draw a 2D lightweight polyline through points [[x,y], ...]."""
    pl = ms().AddLightWeightPolyline(flat2d(points))
    pl.Closed = closed
    if width:
        pl.ConstantWidth = float(width)
    return _apply(pl, layer, color)


@mcp.tool()
@_retry
def draw_rectangle(corner: list[float], width: float, height: float, layer: str = "",
                   color: int | None = None) -> dict:
    """Draw a closed rectangle from lower-left corner [x,y] with width and height."""
    x, y = float(corner[0]), float(corner[1])
    return draw_polyline([[x, y], [x + width, y], [x + width, y + height], [x, y + height]],
                         True, layer, color)


@mcp.tool()
@_retry
def draw_circle(center: list[float], radius: float, layer: str = "", color: int | None = None) -> dict:
    """Draw a circle."""
    return _apply(ms().AddCircle(pt(center), float(radius)), layer, color)


@mcp.tool()
@_retry
def draw_arc(center: list[float], radius: float, start_angle_deg: float, end_angle_deg: float,
             layer: str = "", color: int | None = None) -> dict:
    """Draw an arc counter-clockwise from start to end angle (degrees)."""
    import math
    arc = ms().AddArc(pt(center), float(radius), math.radians(start_angle_deg), math.radians(end_angle_deg))
    return _apply(arc, layer, color)


@mcp.tool()
@_retry
def add_text(text: str, position: list[float], height: float = 2.5, rotation_deg: float = 0.0,
             layer: str = "", color: int | None = None) -> dict:
    """Add single-line text at position (insertion point, lower-left)."""
    import math
    t = ms().AddText(text, pt(position), float(height))
    t.Rotation = math.radians(rotation_deg)
    return _apply(t, layer, color)


@mcp.tool()
@_retry
def add_mtext(text: str, position: list[float], width: float, height: float = 2.5,
              layer: str = "", color: int | None = None) -> dict:
    """Add multiline text (top-left at position). Supports Unicode such as Lao if the style font supports it."""
    t = ms().AddMText(pt(position), float(width), text)
    t.Height = float(height)
    return _apply(t, layer, color)


@mcp.tool()
@_retry
def add_aligned_dimension(p1: list[float], p2: list[float], text_position: list[float],
                          layer: str = "", color: int | None = None) -> dict:
    """Add an aligned dimension between p1 and p2; text_position sets the dimension line location."""
    return _apply(ms().AddDimAligned(pt(p1), pt(p2), pt(text_position)), layer, color)


@mcp.tool()
@_retry
def add_hatch(boundary_points: list[list[float]], pattern: str = "ANSI31", scale: float = 1.0,
              layer: str = "", color: int | None = None) -> dict:
    """Hatch a closed polygon boundary [[x,y], ...] with a pattern (ANSI31, SOLID, AR-CONC, ...)."""
    pl = ms().AddLightWeightPolyline(flat2d(boundary_points))
    pl.Closed = True
    h = ms().AddHatch(0, pattern, True)
    h.AppendOuterLoop(win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [pl]))
    h.PatternScale = float(scale)
    h.Evaluate()
    pl.Delete()
    return _apply(h, layer, color)


@mcp.tool()
@_retry
def insert_block(name_or_path: str, position: list[float], scale: float = 1.0,
                 rotation_deg: float = 0.0, layer: str = "") -> dict:
    """Insert a block by name (existing in drawing) or from a .dwg file path."""
    import math
    br = ms().InsertBlock(pt(position), name_or_path, scale, scale, scale, math.radians(rotation_deg))
    return _apply(br, layer)


# ------------------------------------------------------------- inspection

@mcp.tool()
@_retry
def list_entities(layer: str = "", entity_type: str = "", limit: int = 200) -> dict:
    """List model-space entities (handle, type, layer, bounding box). Filter by layer and/or type (e.g. AcDbLine)."""
    items, total = [], 0
    for e in ms():
        if layer and e.Layer.lower() != layer.lower():
            continue
        if entity_type and entity_type.lower() not in e.ObjectName.lower():
            continue
        total += 1
        if len(items) >= limit:
            continue
        rec = {"handle": e.Handle, "type": e.ObjectName, "layer": e.Layer}
        try:
            lo, hi = e.GetBoundingBox()
            rec["bbox"] = [[round(v, 3) for v in lo[:2]], [round(v, 3) for v in hi[:2]]]
        except Exception:
            pass
        if hasattr(e, "TextString"):
            try:
                rec["text"] = e.TextString
            except Exception:
                pass
        items.append(rec)
    return {"total": total, "returned": len(items), "entities": items}


@mcp.tool()
@_retry
def drawing_extents() -> dict:
    """Return EXTMIN/EXTMAX of the drawing."""
    d = doc()
    return {"min": list(d.GetVariable("EXTMIN")), "max": list(d.GetVariable("EXTMAX"))}


# ------------------------------------------------------------------ edit

@mcp.tool()
@_retry
def erase_entities(handles: list[str]) -> dict:
    """Delete entities by handle."""
    d, done, missing = doc(), [], []
    for h in handles:
        try:
            d.HandleToObject(h).Delete()
            done.append(h)
        except Exception:
            missing.append(h)
    return {"erased": done, "not_found": missing}


@mcp.tool()
@_retry
def move_entities(handles: list[str], from_point: list[float], to_point: list[float]) -> int:
    """Move entities by handle from one point to another."""
    d = doc()
    for h in handles:
        d.HandleToObject(h).Move(pt(from_point), pt(to_point))
    return len(handles)


@mcp.tool()
@_retry
def set_entity_props(handle: str, layer: str = "", color: int | None = None) -> dict:
    """Change layer and/or color of an entity."""
    return _apply(doc().HandleToObject(handle), layer, color)


if __name__ == "__main__":
    mcp.run()
