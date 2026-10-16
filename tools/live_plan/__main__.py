"""python -m tools.live_plan {prepare,draw,audit} ..."""
import argparse
import json
from pathlib import Path

from .plan import build_plan
from .qa import audit
from .render import render


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description='SketchUp geometry -> editable live AutoCAD 2025 + evidence-based QA')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','draw'):
        p=sub.add_parser(name);p.add_argument('source');p.add_argument('--config',required=True)
        p.add_argument('--work',required=True,help='Internal scratch directory, not final delivery')
        if name=='draw':p.add_argument('--output',required=True,help='New .dwg path; never overwrite')
    p=sub.add_parser('audit');p.add_argument('plan');p.add_argument('actual');p.add_argument('--output',required=True);p.add_argument('--visual-review')
    args=parser.parse_args()
    if args.command=='audit':
        result=audit(load(args.plan),load(args.actual),load(args.visual_review) if args.visual_review else None)
        write(args.output,result)
    else:
        plan=build_plan(load(args.source),load(args.config))
        if args.command=='prepare':
            work=Path(args.work).resolve()
            # Exercise the renderer and sheet fit during offline validation.
            render(plan,'NEW',work/'unused.dwg',work/'unused-actual.json',work/'unused-receipt.json','prepare-only')
            write(work/'plan.json',plan)
            print(f'Prepared {work / "plan.json"}; no CAD application modified')
            return 0
        from .autocad import AutoCAD2025
        actual,job=AutoCAD2025().draw(plan,args.output,args.work)
        result=audit(plan,actual);write(job/'qa.json',result)
        print(f'Editable drawing remains open in AutoCAD. Evidence: {job}')
    print(json.dumps(result['summary']))
    return 1 if result['summary'].get('FAIL') else 2 if result['summary'].get('UNVERIFIED') else 0


if __name__=='__main__':
    raise SystemExit(main())
