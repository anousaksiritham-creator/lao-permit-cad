"""Explicit source classification and revision preparation; no architectural guessing."""
from __future__ import annotations

from collections import defaultdict
import math
import re

from .geometry import EPS, merge_lines, point, verified_rectangle, revise_rect, reconcile_junctions, regions, area

LAYERS = {
    'wall': 'A-WALL', 'column': 'S-COLUMN', 'door': 'A-DOOR',
    'glazing': 'A-GLAZING', 'access': 'A-ACCESS', 'fixture': 'A-FIXTURES',
    'floor': 'A-FLOOR', 'site': 'L-SITE', 'services': 'M-SERVICES',
    'reference': 'A-REFERENCE',
}


def confirmed(item):
    if item.get('verified') is not True or not str(item.get('evidence', '')).strip():
        raise ValueError('Annotations require verified=true and nonempty evidence')


def build_plan(snapshot, config):
    if snapshot.get('units') != 'mm':
        raise ValueError('Snapshot must declare units="mm"; units are never guessed')
    segments = snapshot.get('segments', [])
    if not segments or len(segments) > 500_000:
        raise ValueError('Expected 1..500000 actual source segments')
    if config.get('expected_model') and snapshot.get('title') != config['expected_model']:
        raise ValueError('Wrong source model')
    rules = []
    for rule in config.get('rules', []):
        if rule['kind'] not in LAYERS or len(rule['pattern']) > 200:
            raise ValueError('Invalid classification rule')
        rules.append((re.compile(rule['pattern']), rule['kind']))
    if not rules:
        raise ValueError('Provide ordered source-name classification rules')
    excluded = {str(v) for v in config.get('exclude_source_ids', [])}
    groups = defaultdict(list)
    kinds, names, issues = {}, {}, []
    for seg in segments:
        point(seg['a']); point(seg['b'])
        if seg.get('kind') not in ('cut', 'below', 'grid'):
            raise ValueError('Unsupported segment kind')
        path = seg.get('path', [])
        leaf = path[-1] if path else {'id': seg.get('source_id', '__root__'), 'name': 'root geometry'}
        oid = str(seg.get('source_id') or '/'.join(str(p['id']) for p in path) or leaf['id'])
        name = leaf.get('name', '')
        if oid in excluded:
            continue
        if oid not in kinds:
            match = next((kind for pattern, kind in rules if pattern.search(name)), None)
            kinds[oid], names[oid] = match or 'reference', name
            if match is None:
                issues.append({'check': 'classification', 'status': 'UNVERIFIED', 'source_id': oid, 'name': name})
        groups[oid].append(seg)
    lines, walls, original, columns, column_rects = [], [], [], [], []
    wall_ids = []
    thickness = config.get('wall_thickness_mm')
    overrides = {str(k): v for k, v in config.get('wall_axes', {}).items()}
    ends = {str(k): v for k, v in config.get('wall_ends', {}).items()}
    if (thickness is not None or overrides or ends) and not config.get('revision_evidence'):
        raise ValueError('Wall revisions require explicit revision_evidence')
    if thickness is not None:
        thickness = float(thickness)
        if not math.isfinite(thickness) or thickness <= 0:
            raise ValueError('Invalid wall thickness')
    for oid, segs in groups.items():
        kind = kinds[oid]
        if kind in ('wall', 'column'):
            cuts = [s for s in segs if s['kind'] == 'cut']
            try:
                rect = verified_rectangle(cuts)
            except ValueError as error:
                if kind == 'wall' and (thickness is not None or oid in overrides or oid in ends):
                    raise ValueError(f'Cannot revise unsupported wall cut {oid}: {error}') from error
                issues.append({'check': f'{kind}_solid', 'status': 'UNVERIFIED', 'source_id': oid, 'reason': str(error)})
                lines.extend({'a': s['a'], 'b': s['b'], 'layer': LAYERS[kind]} for s in cuts)
                continue
            if kind == 'wall':
                original.append(rect)
                walls.append(revise_rect(rect, thickness or min(rect[2]-rect[0], rect[3]-rect[1]), overrides.get(oid)))
                wall_ids.append(oid)
            else:
                if rect not in column_rects:
                    column_rects.append(rect)
                    columns.extend(dict(r, layer='S-COLUMN') for r in regions([rect]))
        else:
            lines.extend({'a': s['a'], 'b': s['b'], 'layer': LAYERS[kind]} for s in segs)
    walls = reconcile_junctions(original, walls)
    if (set(overrides) | set(ends)) - set(wall_ids):
        raise ValueError('Wall revision refers to an unknown or excluded source ID')
    for i, oid in enumerate(wall_ids):
        if oid in ends:
            lo, hi = map(float, ends[oid])
            if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi:
                raise ValueError('Invalid explicit wall endpoints')
            axis = 1 if original[i][2]-original[i][0] < original[i][3]-original[i][1] else 0
            walls[i][axis], walls[i][axis+2] = lo, hi
    if thickness is not None:
        for i, a in enumerate(walls):
            for b in walls[i+1:]:
                vertical = a[2]-a[0] < a[3]-a[1]
                if vertical != (b[2]-b[0] < b[3]-b[1]):
                    continue
                overlap = min(a[2],b[2])-max(a[0],b[0]) > EPS and min(a[3],b[3])-max(a[1],b[1]) > EPS
                axis = 0 if vertical else 1
                offset = abs((a[axis]+a[axis+2])-(b[axis]+b[axis+2]))/2
                if overlap and offset > EPS:
                    raise ValueError('Overlapping parallel wall revisions: select source IDs or approve axes explicitly')
    solids = [dict(r, layer='A-WALL') for r in regions(walls, column_rects)] + columns
    dimensions = []
    for item in config.get('dimensions', []):
        confirmed(item)
        if 'value' in item or 'text_override' in item:
            raise ValueError('Numeric dimension overrides are forbidden')
        p1, p2, pos = point(item['p1']), point(item['p2']), point(item['position'])
        if math.dist(p1, p2) <= EPS:
            raise ValueError('Zero-length dimension')
        dimensions.append(dict(p1=p1, p2=p2, position=pos, expected_mm=math.dist(p1,p2)))
    labels = []
    for item in config.get('labels', []):
        confirmed(item)
        if not item.get('text') or len(item['text']) > 500 or any(ord(c)<32 for c in item['text']):
            raise ValueError('Invalid label')
        labels.append({'text': item['text'], 'position': point(item['position']), 'layer': 'A-ROOMS', 'height': 200})
    grid = config.get('grid')
    if grid:
        confirmed(grid)
        for key in ('x', 'y'):
            if not grid.get(key) or len(grid[key]) > 100:
                raise ValueError('Invalid grid')
            values = [float(a['value']) for a in grid[key]]
            if not all(math.isfinite(v) for v in values) or values != sorted(set(values)):
                raise ValueError('Grid axes must be finite, unique and ascending')
            if any(not str(a.get('label', '')) or any(ord(c)<32 for c in str(a['label'])) for a in grid[key]):
                raise ValueError('Missing verified grid label')
    sheet = config.get('sheet')
    if sheet and (sheet.get('scale') != 100 or sheet.get('number') != 'A-101'):
        raise ValueError('v0.1 sheet support is explicitly A-101 / A3 / 1:100')
    plan = {'version': 1, 'units': 'mm', 'source': {k: snapshot.get(k) for k in ('title','path','model_session','sketchup_version','cut_mm','captured_at')},
            'lines': merge_lines(lines), 'solids': solids, 'dimensions': dimensions,
            'labels': labels, 'grid': grid, 'sheet': sheet,
            'issues': issues, 'hidden_source_groups': len(snapshot.get('hidden', [])),
            'approved_revision': {'evidence': config.get('revision_evidence'), 'wall_thickness_mm': thickness, 'wall_axes': overrides, 'wall_ends': ends, 'excluded_source_ids': sorted(excluded)},
            'font_file': config.get('font_file', 'arial.ttf')}
    if not plan['lines'] and not plan['solids']:
        raise ValueError('Empty drawing plan')
    plan['expected_fill_area'] = {layer: sum(abs(area(s['outer']))-sum(abs(area(h)) for h in s['holes']) for s in solids if s['layer']==layer) for layer in ('A-WALL','S-COLUMN')}
    return plan
