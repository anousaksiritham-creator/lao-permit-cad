"""Pure geometry helpers. No CAD application or third-party dependencies."""
from __future__ import annotations

from collections import defaultdict
import math

EPS = 1e-5


def point(value):
    if len(value) not in (2, 3):
        raise ValueError("A point must have two or three coordinates")
    result = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("Non-finite geometry")
    return result[:2]


def area(poly):
    return sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(poly, poly[1:] + poly[:1])) / 2


def inside(p, poly):
    x, y = p
    hit = False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                hit = not hit
    return hit


def verified_rectangle(segments):
    """Accept actual four-sided cut geometry only, never an arbitrary object's box.

    Triangulation split points and duplicate reversed edges are supported. A hole,
    diagonal, missing side, or non-rectangular shape is rejected.
    """
    edges = {(tuple(round(v, 5) for v in point(s["a"])),
              tuple(round(v, 5) for v in point(s["b"]))) for s in segments}
    edges = {tuple(sorted(e)) for e in edges if e[0] != e[1]}
    if not edges:
        raise ValueError("No cut edges")
    pts = {p for e in edges for p in e}
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    if x1 - x0 <= EPS or y1 - y0 <= EPS:
        raise ValueError("Degenerate cut")
    intervals = defaultdict(list)
    for a, b in edges:
        if abs(a[0] - b[0]) < EPS and a[0] in (x0, x1):
            intervals[("v", a[0])].append(sorted((a[1], b[1])))
        elif abs(a[1] - b[1]) < EPS and a[1] in (y0, y1):
            intervals[("h", a[1])].append(sorted((a[0], b[0])))
        else:
            raise ValueError("Cut is not a simple axis-aligned rectangle")
    for side, start, end in [(('v', x0), y0, y1), (('v', x1), y0, y1),
                              (('h', y0), x0, x1), (('h', y1), x0, x1)]:
        runs = sorted(intervals[side])
        cursor = start
        for lo, hi in runs:
            if lo > cursor + EPS:
                raise ValueError("Incomplete rectangle boundary")
            cursor = max(cursor, hi)
        if cursor < end - EPS:
            raise ValueError("Incomplete rectangle boundary")
    return [x0, y0, x1, y1]


def revise_rect(rect, thickness, axis=None):
    x0, y0, x1, y1 = rect
    if not math.isfinite(thickness) or thickness <= 0:
        raise ValueError("Wall thickness must be positive and finite")
    if x1 - x0 < y1 - y0:
        centre = (x0 + x1) / 2 if axis is None else float(axis)
        result = [centre - thickness / 2, y0, centre + thickness / 2, y1]
    else:
        centre = (y0 + y1) / 2 if axis is None else float(axis)
        result = [x0, centre - thickness / 2, x1, centre + thickness / 2]
    if not all(math.isfinite(v) for v in result):
        raise ValueError("Non-finite wall revision")
    return result


def reconcile_junctions(original, revised):
    """Map existing perpendicular end attachments to the revised wall faces.

    No snapping across previously open gaps, no axis guesses, and no collapsing
    overlapping parallel walls: those require explicit source selection.
    """
    out = [r[:] for r in revised]
    for i, (old, new) in enumerate(zip(original, revised)):
        vertical = old[2] - old[0] < old[3] - old[1]
        along, cross = (1, 0) if vertical else (0, 1)
        centre = (old[cross] + old[cross + 2]) / 2
        for end in (along, along + 2):
            candidates = []
            for j, other in enumerate(original):
                if i == j or vertical == (other[2] - other[0] < other[3] - other[1]):
                    continue
                if (other[cross] - EPS <= centre <= other[cross + 2] + EPS and
                        other[along] - EPS <= old[end] <= other[along + 2] + EPS):
                    t = (old[end] - other[along]) / (other[along + 2] - other[along])
                    candidates.append(revised[j][along] + t * (revised[j][along + 2] - revised[j][along]))
            if candidates:
                if max(candidates) - min(candidates) > EPS:
                    raise ValueError("Ambiguous wall junction; select the intended source revision")
                out[i][end] = candidates[0]
        if out[i][0] >= out[i][2] or out[i][1] >= out[i][3]:
            raise ValueError("Wall collapsed at revised junction")
    return out


def regions(walls, columns=()):
    """Exact orthogonal rectangle union minus column rectangles, including holes."""
    if not walls:
        return []
    for r in [*walls, *columns]:
        if len(r) != 4 or not all(math.isfinite(v) for v in r) or r[0] >= r[2] or r[1] >= r[3]:
            raise ValueError("Invalid rectangle")
    xs = sorted({v for r in [*walls, *columns] for v in (r[0], r[2])})
    ys = sorted({v for r in [*walls, *columns] for v in (r[1], r[3])})
    if len(xs) * len(ys) > 500_000:
        raise ValueError("Rectangle grid too large; split the plan into explicit batches")
    edges = set()
    def contained(x, y, rs):
        return any(r[0] < x < r[2] and r[1] < y < r[3] for r in rs)
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            x, y = (x0 + x1) / 2, (y0 + y1) / 2
            if not contained(x, y, walls) or contained(x, y, columns):
                continue
            p = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            for a, b in zip(p, p[1:] + p[:1]):
                if (b, a) in edges:
                    edges.remove((b, a))
                else:
                    edges.add((a, b))
    loops = []
    while edges:
        first = min(edges)
        edges.remove(first)
        start, current = first
        previous, poly = start, [start]
        while current != start:
            poly.append(current)
            candidates = [e for e in edges if e[0] == current]
            if not candidates:
                raise ValueError("Unclosed Boolean boundary")
            incoming = (current[0] - previous[0], current[1] - previous[1])
            def turn(e):
                v = (e[1][0] - current[0], e[1][1] - current[1])
                return math.atan2(incoming[0] * v[1] - incoming[1] * v[0],
                                  incoming[0] * v[0] + incoming[1] * v[1])
            edge = max(candidates, key=turn)
            edges.remove(edge)
            previous, current = current, edge[1]
        clean = []
        for i, p in enumerate(poly):
            before, after = poly[i - 1], poly[(i + 1) % len(poly)]
            if abs((p[0] - before[0]) * (after[1] - p[1]) -
                   (p[1] - before[1]) * (after[0] - p[0])) > EPS:
                clean.append(p)
        if abs(area(clean)) > EPS:
            loops.append(clean)
    result = [{"outer": p, "holes": []} for p in loops if area(p) > 0]
    for hole in (p for p in loops if area(p) < 0):
        owners = [r for r in result if inside(hole[0], r["outer"])]
        if not owners:
            raise ValueError("Orphan inner boundary")
        min(owners, key=lambda r: abs(area(r["outer"])))['holes'].append(hole)
    return result


def merge_lines(lines, precision=5):
    """Union collinear segments per layer without discarding short valid lines."""
    groups = defaultdict(list)
    for line in lines:
        a, b = point(line['a']), point(line['b'])
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length <= EPS:
            continue
        ux, uy = dx / length, dy / length
        if ux < -EPS or (abs(ux) < EPS and uy < 0):
            ux, uy = -ux, -uy
        off = -uy * a[0] + ux * a[1]
        key = (line['layer'], round(ux, 8), round(uy, 8), round(off, precision))
        groups[key].append(sorted((ux * a[0] + uy * a[1], ux * b[0] + uy * b[1])))
    out = []
    for (layer, ux, uy, off), spans in sorted(groups.items()):
        spans.sort()
        lo, hi = spans[0]
        def emit(lo, hi):
            out.append({'layer': layer, 'a': [ux * lo - uy * off, uy * lo + ux * off],
                        'b': [ux * hi - uy * off, uy * hi + ux * off]})
        for a, b in spans[1:]:
            if a > hi + EPS:
                emit(lo, hi)
                lo, hi = a, b
            else:
                hi = max(hi, b)
        emit(lo, hi)
    return out
