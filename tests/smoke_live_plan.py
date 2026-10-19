"""Opt-in AutoCAD 2025 synthetic integration. No drawing files are saved."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.live_plan.autocad import AutoCAD2025
from tools.live_plan.plan import build_plan
from tools.live_plan.qa import audit

def main():
    source=json.loads((ROOT/'examples/live-plan/source.synthetic.json').read_text())
    config=json.loads((ROOT/'examples/live-plan/config.synthetic.json').read_text())
    # Numeric geometry test, not a plot-preview/engineering attestation.
    config['sheet']=None
    plan=build_plan(source,config)
    client=AutoCAD2025();before=client.status();original_name=before['active']
    actual,job=client.draw(plan,work_dir=ROOT/'out'/'live-plan-smoke')
    result=audit(plan,actual)
    (job/'qa.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    if result['summary'].get('FAIL',0):
        raise AssertionError(f'Live readback failures; leave scratch for inspection: {job}')
    assert actual['save_requested'] is False and actual['saved'] is False and actual['drawing']==''
    # Close only this test's own document after successful readback, never user work.
    target=json.loads((job/'run.json').read_text())['target']
    client.application.Documents.Item(target).Close(False)
    if client.status()['active'] != original_name:
        restored=client.application.Documents.Item(original_name)
        restored.Activate()
    print(json.dumps({'status':'PASS','summary':result['summary'],
        'scope':'Synthetic source geometry, native dimension, fills/order and readback; no DWG saved',
        'visual_review':'UNVERIFIED','engineering_release':False}))

if __name__=='__main__':main()
