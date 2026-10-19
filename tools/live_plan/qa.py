"""QA compares native CAD readback with the prepared source-derived plan."""
from __future__ import annotations

from collections import Counter
import math
from pathlib import Path

from .geometry import area
from .render import grid_limits


def _p(value):
    return tuple(round(float(v),3) for v in value[:2])


def _line(layer,a,b):
    return (layer,tuple(sorted((_p(a),_p(b)))))


def _polygon(layer, points):
    points = tuple(_p(p) for p in points)
    rotations = [points[i:]+points[:i] for i in range(len(points))]
    reverse = tuple(reversed(points))
    rotations += [reverse[i:]+reverse[:i] for i in range(len(reverse))]
    return layer,min(rotations)


def audit(plan, actual, visual_review=None):
    checks=[]
    def check(name, condition, detail):
        checks.append({'check':name,'status':'PASS' if condition else 'FAIL','evidence':detail})
    entities = actual.get('entities',[])
    check('units',actual.get('units')==4,'INSUNITS must be 4 (mm)')
    if actual.get('save_requested') is False:
        check('save_policy',actual.get('drawing') == '' and actual.get('saved') is False,'Live mode: drawing must remain unsaved with no disk path')
    else:
        check('saved',actual.get('saved') is True,'Explicit save mode: readback follows saving the new DWG')
    expected=Counter(_line(l['layer'],l['a'],l['b']) for l in plan['lines'])
    measured=Counter(_line(e['layer'],e['a'],e['b']) for e in entities if e['type']=='AcDbLine' and e['layer']!='A-GRID')
    check('source_lines',expected==measured,{'expected':sum(expected.values()),'actual':sum(measured.values()),'missing':sum((expected-measured).values()),'extra':sum((measured-expected).values())})
    expected_poly=Counter(_polygon(s['layer'],p) for s in plan['solids'] for p in [s['outer'],*s['holes']])
    actual_poly=Counter(_polygon(e['layer'],e['points']) for e in entities if e['type']=='AcDbPolyline' and e.get('closed'))
    check('solid_boundaries',expected_poly==actual_poly,'Actual closed polylines must match source/revised outlines and holes')
    for layer,expected_area in plan['expected_fill_area'].items():
        total=sum(e['area'] for e in entities if e['type']=='AcDbHatch' and e['layer']==layer+'-POCHE')
        check('hatch_area:'+layer,math.isclose(total,expected_area,rel_tol=1e-7,abs_tol=.01),{'expected_mm2':expected_area,'actual_mm2':total})
    expected_dim=Counter((tuple(sorted((_p(d['p1']),_p(d['p2'])))),round(d['expected_mm'],3)) for d in plan['dimensions'])
    actual_dim=Counter((tuple(sorted((_p(e['p1']),_p(e['p2'])))),round(e['measurement'],3)) for e in entities if e['type']=='AcDbAlignedDimension')
    check('dimensions_and_witnesses',expected_dim==actual_dim,'Coordinates and actual measurements, not overridden text')
    dim_entities=[e for e in entities if e['type']=='AcDbAlignedDimension']
    check('dimension_style',all(e['height']>=200 and e['scale']==1 and e['linear_scale']==1 and not e['override'] for e in dim_entities),'Native dimension text >=2 mm at 1:100; scale factors 1; no overrides')
    order=actual.get('order',[]);pos={h:i for i,h in enumerate(order)}
    buckets={layer:[e['handle'] for e in entities if e['layer']==layer] for layer in ['A-WALL-POCHE','A-WALL','S-COLUMN-POCHE','S-COLUMN']}
    complete=len(pos)==len(entities) and all(e['handle'] in pos for e in entities)
    ranked=[v for v in buckets.values() if v]
    rest=[e['handle'] for e in entities if e['layer'] not in buckets]
    if rest:ranked.insert(0,rest)
    good=complete and all(max(pos[h] for h in lo)<min(pos[h] for h in hi) for lo,hi in zip(ranked,ranked[1:]))
    check('draw_order',good,'Other < wall fills < wall outlines < column fills < column outlines')
    check('planar_lines',all(abs(e['a'][2])<.001 and abs(e['b'][2])<.001 for e in entities if e['type']=='AcDbLine'),'All line endpoints Z=0')
    expected_labels=Counter((t['text'],_p(t['position'])) for t in plan.get('labels',[]))
    actual_labels=Counter((e['text'],_p(e.get('position',[]))) for e in entities if e['type']=='AcDbText' and e['layer']=='A-ROOMS')
    check('labels',expected_labels==actual_labels,'Confirmed label text and actual alignment points')
    grid=plan.get('grid')
    if grid:
        x0,y0,x1,y1=grid_limits(plan)
        axes=[];labels=[];circles=[]
        for direction in ('x','y'):
            for item in grid[direction]:
                v=float(item['value']);a,b=([v,y0],[v,y1]) if direction=='x' else ([x0,v],[x1,v])
                axes.append(_line('A-GRID',a,b))
                for p in (a,b):labels.append((str(item['label']),_p(p)));circles.append((_p(p),220))
        measured_axes=[_line(e['layer'],e['a'],e['b']) for e in entities if e['type']=='AcDbLine' and e['layer']=='A-GRID']
        measured_labels=[(e['text'],_p(e.get('position',[]))) for e in entities if e['type']=='AcDbText' and e['layer']=='A-GRID-LABELS']
        measured_circles=[(_p(e['centre']),round(e['radius'],3)) for e in entities if e['type']=='AcDbCircle' and e['layer']=='A-GRID-LABELS']
        check('grid',Counter(axes)==Counter(measured_axes) and Counter(labels)==Counter(measured_labels) and Counter(circles)==Counter(measured_circles),'Native axes, label text/positions and bubble centres/radii match confirmed inputs')
    used={e['layer'] for e in entities}
    expected_weights={'A-WALL':35,'S-COLUMN':35,'A-WALL-POCHE':25,'S-COLUMN-POCHE':25,'A-DIMS':18,'A-ROOMS':18,'A-GRID':9,'A-GRID-LABELS':18}
    layer_map={l['name']:l for l in actual.get('layers',[])}
    check('layer_weights_visibility',all(n in layer_map and layer_map[n]['weight']==w and layer_map[n]['on'] for n,w in expected_weights.items() if n in used),'Configured cut/column/annotation weights, and intended used layers on')
    if grid:check('grid_linetype',layer_map.get('A-GRID',{}).get('linetype')=='CENTER2','Actual layer linetype CENTER2')
    if plan.get('sheet'):
        vps=actual.get('viewports',[])
        check('viewport',len(vps)==1 and math.isclose(vps[0]['scale'],.01) and vps[0]['locked'],'One locked 1:100 viewport')
    checks.extend(plan.get('issues',[]))
    required={'model_extents','junctions','openings'}
    if plan.get('sheet'):required.update(('layout','plot_preview'))
    review=visual_review or {}
    views=review.get('views',{})
    attested=review.get('reviewed') is True and bool(review.get('reviewer')) and bool(review.get('notes'))
    evidence_ok=required<=set(views) and all(Path(views[k]).is_file() for k in required)
    checks.append({'check':'visual_review','status':'PASS' if attested and evidence_ok else 'UNVERIFIED',
                   'evidence':review if attested and evidence_ok else 'Requires an explicit reviewer attestation and inspected model/junction/opening images; layout/plot preview too when a sheet exists. File existence alone does not establish visual correctness.'})
    # Geometry cannot establish these design facts, regardless of numeric checks.
    checks.append({'check':'hinges_swings_usable_clearance','status':'UNVERIFIED','evidence':'Not inferred from geometry; confirm source design information separately.'})
    summary=dict(Counter(c['status'] for c in checks))
    return {'drawing':actual.get('drawing'),'summary':summary,'checks':checks,
            'scope':'Drafting QA only; no engineering, accessibility or construction-release certification.',
            'approved_source_differences':plan.get('approved_revision')}
