"""Geometry checks, not engineering/code compliance. Standard library only."""
import math

def validate_model(model, project):
    errors, warnings = [], []
    def walk(value, path='model'):
        if isinstance(value, float) and not math.isfinite(value):
            errors.append(f'{path}: non-finite coordinate/value')
        elif isinstance(value, dict):
            for k,v in value.items(): walk(v, f'{path}.{k}')
        elif isinstance(value, list):
            for i,v in enumerate(value): walk(v, f'{path}[{i}]')
    walk(model)
    walk(project, 'project')
    if model.get('units', 'mm') != 'mm': errors.append('Model must explicitly use mm coordinates')
    if 'units' not in model: warnings.append('Legacy model: units not declared; bounds_mm contract only')
    def bounds(obj, label):
        lo,hi=obj.get('min'),obj.get('max')
        if not isinstance(lo,list) or not isinstance(hi,list) or len(lo)!=3 or len(hi)!=3:
            errors.append(f'{label}: expected XYZ min/max'); return
        if not all(type(x) in (int,float) for x in lo+hi):
            errors.append(f'{label}: bounds must be numeric'); return
        if any(a>b for a,b in zip(lo,hi)): errors.append(f'{label}: reversed bounds')
    bounds(model.get('bounds_mm',{}), 'model bounds')
    seen=set()
    for obj in model.get('objects',[]):
        bounds(obj, 'object '+str(obj.get('name')))
        pid=obj.get('persistent_id')
        if pid is not None:
            if pid in seen: errors.append(f'Duplicate root persistent ID: {pid}')
            seen.add(pid)
    if not model.get('plans'): errors.append('No extracted plan cuts')
    for plan in model.get('plans',[]):
        seen_segments=set();duplicates=zero=0
        for seg in plan.get('segs',[]):
            if len(seg)<4 or not all(type(v) in (int,float) for v in seg[:4]):
                errors.append('Invalid plan segment'); continue
            if not all(math.isfinite(x) for x in seg[:4]): continue
            a,b=tuple(seg[:2]),tuple(seg[2:4])
            if math.dist(a,b)<1e-6: zero+=1
            # Same geometry under different source codes can be intentional overlays.
            key=(tuple(sorted((a,b))),tuple(seg[4:]))
            if key in seen_segments: duplicates+=1
            seen_segments.add(key)
        if zero: errors.append(f'Plan {plan.get("z")}: {zero} zero-length segments')
        if duplicates: warnings.append(f'Plan {plan.get("z")}: {duplicates} exact duplicate segments; review')
    if not project.get('datum',{}).get('confirmed'):
        warnings.append('Datum/levels are not user-confirmed; do not certify reference elevations')
    warnings.append('Door/window Box bounds do not establish clear openings, hinges or swing direction')
    return {'errors':errors,'warnings':warnings,'readiness':'PRE_DESIGN_ONLY',
            'engineering_approval':False,'construction_release':False}
