import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from drawing_qa import validate_model
from build_set import SetBuilder

def fixture():
    segs=[]
    for x in range(0,10000,1000):
        segs.extend([[x,0,x+1000,0,'08','cut'],[x+1000,0,x+1000,6000,'08','cut'],
                     [x+1000,6000,x,6000,'08','cut'],[x,6000,x,0,'08','cut']])
    return {'units':'mm','bounds_mm':{'min':[0,0,0],'max':[10000,6000,4000]},
        'objects':[{'code':'08','name':'08 walls','persistent_id':100,'min':[0,0,0],'max':[10000,6000,3000]},
                   {'code':'04','name':'04 columns','persistent_id':101,'min':[0,0,0],'max':[10000,6000,3000],
                    'children':[{'name':'C1','min':[0,0,0],'max':[300,300,3000]},
                                {'name':'C2','min':[9700,5700,0],'max':[10000,6000,3000]}]}],
        'plans':[{'z':1500,'segs':segs}],
        'views':{k:{'segs':segs} for k in ['top','front','back','left','right']},'sections':[]}

class GeometryTests(unittest.TestCase):
    def setUp(self):self.m=fixture();self.p={'id':'SYNTHETIC','datum':{'confirmed':True}}
    def test_valid_geometry_is_not_engineering_release(self):
        r=validate_model(self.m,self.p)
        self.assertEqual(r['errors'],[])
        self.assertFalse(r['construction_release'])
        self.assertFalse(r['engineering_approval'])
    def test_nonfinite_rejected(self):
        self.m['plans'][0]['segs'][0][0]=float('nan')
        self.assertTrue(validate_model(self.m,self.p)['errors'])
    def test_reversed_bounds_rejected(self):
        self.m['objects'][0]['min'][0]=20000
        self.assertTrue(validate_model(self.m,self.p)['errors'])
    def test_duplicate_root_id_rejected(self):
        self.m['objects'][1]['persistent_id']=100
        self.assertTrue(validate_model(self.m,self.p)['errors'])
    def test_zero_length_rejected(self):
        self.m['plans'][0]['segs'].append([1,1,1,1,'08','cut'])
        self.assertTrue(validate_model(self.m,self.p)['errors'])
    def test_duplicate_segment_is_review_warning(self):
        self.m['plans'][0]['segs'].append(self.m['plans'][0]['segs'][0])
        self.assertTrue(any('duplicate' in w for w in validate_model(self.m,self.p)['warnings']))
    def test_non_mm_rejected(self):
        self.m['units']='in'
        self.assertTrue(validate_model(self.m,self.p)['errors'])
    def test_missing_datum_remains_pending(self):
        self.assertTrue(any('Datum' in w for w in validate_model(self.m,{})['warnings']))
    def test_grid_heads_outside_dimension_rows_even_when_rotated(self):
        for rotated in [False,True]:
            b=SetBuilder(self.m,{'id':'SYNTHETIC'},(0,0));b.rotate=rotated
            b.grids=([150,9850],[150,5850]);captured=[]
            b.grid_line=lambda a,z,*args:captured.append((a,z))
            b.grid_annot({},0,0,(0,0,10000,6000),100)
            # inverse tplan: grid endpoint margin must exceed both dimension rows
            inverse=lambda p:(-p[1],p[0]) if rotated else p
            a,z=map(inverse,captured[0])
            self.assertLess(a[1],-3500)
            self.assertGreater(z[1],9500)
    def test_build_cli_in_isolated_python(self):
        testroot=ROOT/'out'/'test-temp';testroot.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=testroot) as d:
            d=pathlib.Path(d);model=d/'model.json';project=d/'project.json';out=d/'set.lsp'
            model.write_text(json.dumps(self.m));project.write_text(json.dumps({'id':'SYNTHETIC','name':'Test','floors':[{'name':'G','cut':1500}]}))
            r=subprocess.run([sys.executable,'-I',str(ROOT/'tools/build_set.py'),str(model),str(project),str(out)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            meta=json.loads(pathlib.Path(str(out)+'.sheets.json').read_text(encoding='utf-8'))
            self.assertEqual(meta['readiness'],'PRE_DESIGN_ONLY')
            self.assertFalse(meta['source_qa']['construction_release'])
            bad=copy.deepcopy(self.m);bad['bounds_mm']['max'][0]=float('inf');model.write_text(json.dumps(bad));out.unlink()
            r=subprocess.run([sys.executable,'-I',str(ROOT/'tools/build_set.py'),str(model),str(project),str(out)],capture_output=True)
            self.assertNotEqual(r.returncode,0)
            self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
