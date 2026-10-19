import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.live_plan.geometry import verified_rectangle, revise_rect, reconcile_junctions, regions, area, merge_lines
from tools.live_plan.plan import build_plan
from tools.live_plan.render import render
from tools.live_plan.qa import audit
from tools.live_plan.autocad import AutoCAD2025, UncertainMutation

ROOT=Path(__file__).resolve().parents[1]


def rectangle(x0,y0,x1,y1):
    p=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    return [{'a':a,'b':b} for a,b in zip(p,p[1:]+p[:1])]


def load_example():
    return (json.loads((ROOT/'examples/live-plan/source.synthetic.json').read_text()),
            json.loads((ROOT/'examples/live-plan/config.synthetic.json').read_text()))


def balanced_lisp(code):
    """Check reader structure including escaped strings and comments."""
    depth=0;quoted=False;escaped=False;comment=False
    for ch in code:
        if comment:
            if ch=='\n':comment=False
            continue
        if quoted:
            if escaped:escaped=False
            elif ch=='\\':escaped=True
            elif ch=='"':quoted=False
        elif ch==';':comment=True
        elif ch=='"':quoted=True
        elif ch=='(':depth+=1
        elif ch==')':
            depth-=1
            if depth<0:raise AssertionError('Unmatched closing parenthesis')
    if quoted or depth:raise AssertionError(f'Unclosed reader structure: {depth}, string={quoted}')


class GeometryTests(unittest.TestCase):
    def test_rejects_bbox_substitution_and_missing_sides(self):
        with self.assertRaises(ValueError):verified_rectangle(rectangle(0,0,10,10)[:-1])
        with self.assertRaises(ValueError):verified_rectangle([{'a':[0,0],'b':[10,0]},{'a':[10,0],'b':[5,10]},{'a':[5,10],'b':[0,0]}])
        hole=rectangle(0,0,10,10)+rectangle(2,2,8,8)
        with self.assertRaises(ValueError):verified_rectangle(hole)

    def test_accepts_split_actual_sides(self):
        edges=rectangle(0,0,10,10)[1:]+[{'a':[0,0],'b':[4,0]},{'a':[4,0],'b':[10,0]}]
        edges+=list(reversed(edges))
        self.assertEqual(verified_rectangle(edges),[0,0,10,10])

    def test_junctions_preserve_axis_and_existing_gaps(self):
        self.assertEqual(revise_rect([0,0,150,2000],100),[25,0,125,2000])
        old=[[0,0,150,2000],[150,1850,2000,2000]]
        revised=[revise_rect(r,100) for r in old]
        result=reconcile_junctions(old,revised)
        self.assertEqual(result[1][0],125)
        separate=[[0,0,150,2000],[200,1850,2000,2000]]
        self.assertEqual(reconcile_junctions(separate,[revise_rect(r,100) for r in separate])[1][0],200)

    def test_union_column_subtraction_and_holes(self):
        r=regions([[0,0,1000,100]],[[450,-50,550,150]])
        self.assertEqual(len(r),2)
        self.assertEqual(sum(area(p['outer']) for p in r),90000)
        r=regions([[0,0,1000,1000]],[[400,400,600,600]])
        self.assertEqual(len(r),1);self.assertEqual(len(r[0]['holes']),1)
        self.assertEqual(area(r[0]['outer'])+area(r[0]['holes'][0]),960000)

    def test_point_contacts_do_not_merge_components(self):
        r=regions([[0,0,10,10],[10,10,20,20]])
        self.assertEqual(len(r),2)
        self.assertEqual(sum(area(p['outer']) for p in r),200)

    def test_short_valid_edges_and_layer_separation(self):
        r=merge_lines([{'a':[0,0],'b':[.01,0],'layer':'a'},
                       {'a':[.01,0],'b':[1,0],'layer':'a'},
                       {'a':[0,0],'b':[1,0],'layer':'b'}])
        self.assertEqual(len(r),2)
        for p in [float('nan'),float('inf')]:
            with self.assertRaises(ValueError):merge_lines([{'a':[p,0],'b':[1,0],'layer':'a'}])


class PipelineTests(unittest.TestCase):
    def test_no_unit_or_annotation_guesses(self):
        source,config=load_example();source.pop('units')
        with self.assertRaises(ValueError):build_plan(source,config)
        source,config=load_example();config['dimensions'][0]['verified']=False
        with self.assertRaises(ValueError):build_plan(source,config)
        source,config=load_example();config['dimensions'][0]['value']=10000
        with self.assertRaises(ValueError):build_plan(source,config)

    def test_reused_component_leaf_ids_stay_separate(self):
        source,config=load_example();ss=[]
        for root,shift in [(10,0),(20,10000)]:
            for edge in rectangle(0,0,100,1000):
                ss.append(dict(edge,a=[edge['a'][0]+shift,edge['a'][1]],b=[edge['b'][0]+shift,edge['b'][1]],kind='cut',path=[{'id':root,'name':'Instance'},{'id':1,'name':'Wall_N'}]))
        source['segments']=ss;config.pop('sheet');config.pop('grid');config['dimensions']=[];config['labels']=[]
        plan=build_plan(source,config)
        self.assertEqual(len(plan['solids']),2)

    def test_sheet_fit_and_lisp_structure(self):
        source,config=load_example();plan=build_plan(source,config)
        code=render(plan,'Drawing99.dwg',Path('new.dwg'),Path('actual.json'),Path('receipt.json'),'test-run')
        balanced_lisp(code)
        self.assertIn('PrimaryUnitsPrecision',code)
        self.assertNotIn('vla-put-TextPrecision',code)
        self.assertIn('Wrong or nonempty target drawing',code)
        self.assertIn('refusing overwrite',code)
        plan['lines'].append({'a':[0,0],'b':[100000,0],'layer':'reference'})
        with self.assertRaises(ValueError):render(plan,'new','out.dwg','actual','receipt','test')

    def test_columns_are_subtracted_from_wall_fill(self):
        source,config=load_example();plan=build_plan(source,config)
        self.assertEqual(plan['expected_fill_area']['A-WALL'],585000)
        self.assertEqual(plan['expected_fill_area']['S-COLUMN'],45000)

    def test_existing_output_refused_without_touching_cad(self):
        class Forbidden:
            def __getattr__(self,name):raise AssertionError('CAD must not be touched')
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            p=Path(temp)/'existing.dwg';p.write_bytes(b'preserve')
            with self.assertRaises(ValueError):AutoCAD2025(Forbidden()).draw({},p,Path(temp)/'work')
            self.assertEqual(p.read_bytes(),b'preserve')

    def test_malformed_readback_fails_and_missing_review_is_unverified(self):
        source,config=load_example();plan=build_plan(source,config)
        report=audit(plan,{'units':1,'saved':False,'entities':[],'order':[]})
        self.assertGreater(report['summary'].get('FAIL',0),0)
        self.assertGreater(report['summary'].get('UNVERIFIED',0),0)
        self.assertNotEqual(next(c for c in report['checks'] if c['check']=='visual_review')['status'],'PASS')

    def test_add_response_loss_does_not_create_a_second_document(self):
        class Doc:
            Name='DrawingMock.dwg';FullName=''
            class ModelSpace:Count=0
            def GetVariable(self,name):return 4
        class App:
            Version='25-test'
            ActiveDocument=None
        app=App()
        class Docs:
            Count=0;calls=0
            def Add(self):
                self.calls+=1;self.Count=1;app.ActiveDocument=Doc()
                raise RuntimeError('Response lost after creation')
            def Item(self,index):return app.ActiveDocument
        app.Documents=Docs();client=AutoCAD2025(app)
        before=client.status();doc=client.new_empty(before)
        self.assertEqual(doc.Name,'DrawingMock.dwg');self.assertEqual(app.Documents.calls,1)

    def test_command_response_loss_is_never_resubmitted(self):
        class Doc:
            Name='DrawingMock.dwg';calls=0
            def GetVariable(self,name):return 1
            def SendCommand(self,command):
                self.calls+=1
                raise RuntimeError('Response lost after queueing command')
        class App:ActiveDocument=Doc()
        class Client(AutoCAD2025):
            def status(self):return {'documents':[],'active':'DrawingMock.dwg'}
            def new_empty(self,before):return self.application.ActiveDocument
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            font=Path(temp)/'test.ttf';font.write_bytes(b'fake font; no real CAD is called')
            source,config=load_example();plan=build_plan(source,config);plan['font_file']=str(font)
            app=App()
            with self.assertRaises(UncertainMutation):Client(app).draw(plan,Path(temp)/'new.dwg',Path(temp)/'work')
            self.assertEqual(app.ActiveDocument.calls,1)

    def test_dimension_text_overrides_and_wrong_witnesses_fail(self):
        plan={'lines':[],'solids':[],'expected_fill_area':{},'dimensions':[{'p1':[0,0],'p2':[3000,0],'expected_mm':3000}], 'issues':[]}
        entity={'handle':'D','type':'AcDbAlignedDimension','layer':'A-DIMS','p1':[0,0,0],'p2':[3000,0,0],'measurement':3000,'height':240,'scale':1,'linear_scale':1,'override':'3000'}
        actual={'drawing':'synthetic','units':4,'saved':True,'entities':[entity],'order':['D']}
        report=audit(plan,actual)
        self.assertEqual(next(c['status'] for c in report['checks'] if c['check']=='dimension_style'),'FAIL')
        entity['override']='';entity['p2']=[3100,0,0]
        report=audit(plan,actual)
        self.assertEqual(next(c['status'] for c in report['checks'] if c['check']=='dimensions_and_witnesses'),'FAIL')


if __name__=='__main__':unittest.main()
