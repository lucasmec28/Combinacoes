import unittest
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
import json
from engine import *
from project_io import *

class EngineTests(unittest.TestCase):
    def setUp(self): self.p=example_project()
    def one_family(self,f='ELUN'):
        self.p['families']=[f]
        return self.p
    def test_reference_vectors_excel_vba(self):
        reference=json.loads(Path(__file__).with_name('reference_example.json').read_text())
        r=generate(self.p)
        for f,index in [('ELUN','1'),('ELSR','5'),('ELSF','6'),('ELSQP','7')]:
            actual={c.cases for c in r.combinations if c.family==f}
            expected={tuple(sorted((int(k),D(str(v))) for k,v in d.items())) for d in reference[index]}
            self.assertEqual(actual,expected)
    def test_example_counts(self):
        self.assertEqual(generate(self.p).counts,{'ELUN':28,'ELSR':14,'ELSF':10,'ELSQP':2})
    def test_winds_exclusive(self):
        for c in generate(self.p).combinations:
            self.assertLessEqual(len({i for i,v in c.cases}&{3,4,5,6}),1)
    def test_winds_compatible(self):
        for a in self.p['actions'][2:]:a['compatibility']='compatible'
        self.assertTrue(any({3,4,5,6}<=dict(c.cases).keys() for c in generate(self.one_family()).combinations))
    def test_physical_bundle(self):
        a=deepcopy(self.p['actions'][2]);a['case']=7;self.p['actions'].append(a)
        for c in generate(self.p).combinations:
            d=dict(c.cases);self.assertEqual(d.get(3),d.get(7))
    def test_conflicting_bundle(self):
        self.p['actions'][3]['origin']=self.p['actions'][2]['origin']
        self.p['actions'][3]['presence']='required'
        with self.assertRaises(InputError):generate(self.p)
    def test_exclusive_required_conflict(self):
        for a in self.p['actions'][2:]:a['presence']='required'
        with self.assertRaises(InputError):generate(self.one_family())
    def test_required_excludes_absence(self):
        self.p['actions'][1]['presence']='required'
        self.assertTrue(all(2 in dict(c.cases) for c in generate(self.p).combinations))
    def test_zero_psi_winds_absent_qp(self):
        self.assertTrue(all(not ({3,4,5,6}&dict(c.cases).keys()) for c in generate(self.one_family('ELSQP')).combinations))
    def test_no_principal_in_qp(self):
        for a in self.p['actions'][1:]:a['primary']=False
        self.assertEqual(generate(self.one_family('ELSQP')).counts['ELSQP'],2)
    def test_no_principal_normal_rejected(self):
        for a in self.p['actions'][1:]:a['primary']=False
        with self.assertRaises(InputError):generate(self.one_family())
    def test_favorable_restriction(self):
        self.p['actions'][0]['g_effect']='favorable'
        self.assertEqual(generate(self.one_family()).counts['ELUN'],14)
        self.assertTrue(all(dict(c.cases)[1]==1 for c in generate(self.p).combinations))
    def test_restrictions_require_reason(self):
        self.p['actions'][0].update(g_effect='favorable',notes='')
        with self.assertRaises(InputError):generate(self.p)
    def test_permanent_only(self):
        self.p['actions']=self.p['actions'][:1]
        self.assertEqual(generate(self.p).counts,{'ELUN':2,'ELSR':1,'ELSF':1,'ELSQP':1})
    def test_duplicate_case(self):
        self.p['actions'][1]['case']=1
        with self.assertRaises(InputError):generate(self.p)
    def test_group_relation_conflict(self):
        self.p['actions'][2]['compatibility']='compatible'
        with self.assertRaises(InputError):generate(self.p)
    def test_norm_specific_factors(self):
        a=self.p['actions'][0];a['type']='EQ'
        self.assertEqual(factor_record(self.p,a)['gamma'][0],D('1.25'))
        self.p['standard']='NBR 14762:2010'
        self.assertEqual(factor_record(self.p,a)['gamma'][0],D('1.5'))
    def test_no_cross_norm_fallback(self):
        self.p['standard']='NBR 14762:2010';self.p['actions'][0]['type']='MAD'
        with self.assertRaises(InputError):generate(self.p)
    def test_grouped_q_rule(self):
        self.p.update(standard='NBR 8681:2025',q_mode='grouped',temperature_separate=True)
        with self.assertRaises(InputError):generate(self.p)
    def test_grouped_permanent_moves_together(self):
        self.p['g_mode']='grouped'
        a=deepcopy(self.p['actions'][0]);a.update(case=7,origin='OTHER',type='IND');self.p['actions'].append(a)
        for c in generate(self.one_family()).combinations:self.assertEqual(dict(c.cases)[1],dict(c.cases)[7])
    def test_special_construction_exceptional(self):
        for family in ('ELUE','ELUC','ELUX'):
            p=example_project();p['families']=[family];p['effective'][family]='psi2';p['effective_reason']='Duração verificada no teste.'
            p['actions']=p['actions'][:3]
            for a in p['actions']:a['families']=[family]
            if family=='ELUX':
                e=new_action(9);e.update(name='Acidente',type='EXC',origin='E9',families=[family]);p['actions'].append(e)
            else:p['actions'][1]['roles'][family]='primary'
            r=generate(p)
            self.assertTrue(r.combinations)
            for c in r.combinations:
                d=dict(c.cases)
                self.assertNotIn(3,d) # wind psi2=0
                if family=='ELUX':self.assertEqual(d[9],D(1))
                else:self.assertIn(2,d)
    def test_effective_explicit(self):
        self.p['families']=['ELUE']
        with self.assertRaises(InputError):generate(self.p)
    def test_manual_factors_linked_to_norm(self):
        a=self.p['actions'][1]
        a.update(type='CUSTOM',custom={'standard':self.p['standard'],'nature':'Q','gamma':['1.7',0,'1.2',0,1,0],'psi':['0.6','0.4','0.2'],'source':'Teste manual'})
        self.assertTrue(any(dict(c.cases).get(2)==D('1.7') for c in generate(self.one_family()).combinations))
        self.p['standard']='NBR 8681:2025'
        with self.assertRaises(InputError):generate(self.p)
    def test_limits_no_partial_result(self):
        for key in ('limit','visit_limit'):
            p=deepcopy(self.p);p[key]=1
            with self.assertRaises(GenerationLimit):generate(p)
    def test_bank_version(self):
        self.p['bank_hash']='outdated'
        with self.assertRaises(InputError):generate(self.p)
    def test_output_plain_rectangle(self):
        text=robot_tsv(generate(self.p).combinations)
        lines=text.splitlines();self.assertEqual(len(lines),54)
        self.assertEqual(len({len(line.split('\t')) for line in lines}),1)
        self.assertTrue(lines[0].startswith('EX_ELUN_00001\t1\t1,25'))
        self.assertNotIn('Nome',text)
    def test_roundtrip_and_signature(self):
        p=load_project(dump_project(self.p));self.assertEqual(p,self.p)
        r=generate(p);self.assertEqual(r.signature,fingerprint(p))
        p['actions'][0]['name']='Alterado';self.assertNotEqual(r.signature,fingerprint(p))
    def test_import_incomplete_project(self):
        self.assertEqual(load_project(dump_project(new_project())),new_project())
    def test_invalid_imports(self):
        variants=[]
        for k,v in [('limit',50001),('standard','inventada'),('families',['x']),('temperature_separate','yes')]:
            p=deepcopy(self.p);p[k]=v;variants.append(p)
        for p in variants:
            with self.assertRaises(InputError):load_project(dump_project(p))
        with self.assertRaises(InputError):load_project(b'{malformed')
    def test_inactive_case(self):
        self.p['actions'][2]['active']=False
        self.assertTrue(all(3 not in dict(c.cases) for c in generate(self.p).combinations))
    def test_zero_and_decimal_format(self):
        self.assertEqual(number_text(D('0.000')), '0')
        self.assertEqual(number_text(D('1.2000')), '1,2')
    def test_csv_text_injection_escaped(self):
        self.p['actions'][0]['name']='=1+1'
        self.assertIn("'=1+1",audit_csv(generate(self.p).combinations).decode('utf-8-sig'))

if __name__=='__main__':unittest.main()
