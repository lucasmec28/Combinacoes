"""Regressões dos critérios de geração solicitados para PY04."""
import unittest
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
from streamlit.testing.v1 import AppTest
from engine import (BANK, GAMMA, InputError, active_variable_group_count,
                    example_project, factor_record, generate, new_action)
from project_io import dump_project, load_project
from revisions import REVISIONS


class PY04EngineTests(unittest.TestCase):
    def project(self):
        p=example_project()
        p['families']=['ELUN','ELSR','ELSF','ELSQP']
        p['actions']=p['actions'][:3]  # 1 PP, 2 sobrecarga, 3 vento
        t=new_action(8)
        t.update(name='Temperatura',type='TEM',profile='TEM',origin='T8')
        p['actions'].append(t)
        return p

    def wind_rows(self,p,family='ELUN'):
        return [c for c in generate(p).combinations if c.family==family
                and any(d['case']==3 and d['role']=='Principal' for d in c.detail)]

    def test_wind_unit_permanents_excludes_other_q_but_keeps_temperature(self):
        for kind in ('TEM','TEQ'):
            p=self.project();p['actions'][-1]['type']=kind
            rows=self.wind_rows(p)
            favorable=[c for c in rows if dict(c.cases)[1]==D(1)]
            self.assertTrue(favorable)
            self.assertTrue(all(2 not in dict(c.cases) for c in favorable))
            self.assertTrue(any(8 in dict(c.cases) for c in favorable))
            self.assertTrue(any({2,3,8}<=dict(c.cases).keys() and dict(c.cases)[1]>1 for c in rows))

    def test_mixed_permanent_factors_do_not_trigger_filter(self):
        p=self.project();p['actions'][0]['g_effect']='favorable'
        cp=new_action(9);cp.update(name='CP',type='IND',origin='CP9',g_effect='unfavorable')
        p['actions'].append(cp)
        self.assertTrue(any({2,3,8,9}<=dict(c.cases).keys() and dict(c.cases)[1]==1
                            and dict(c.cases)[9]>1 for c in self.wind_rows(p)))
        cp['g_effect']='favorable'
        self.assertTrue(all(2 not in dict(c.cases) for c in self.wind_rows(p)))

    def test_no_direct_permanents_no_wind_filter(self):
        p=self.project();p['actions']=p['actions'][1:]
        self.assertTrue(any({2,3,8}<=dict(c.cases).keys() for c in self.wind_rows(p)))

    def test_els_and_other_principal_unchanged(self):
        p=self.project()
        for f in ('ELSR','ELSF'):
            self.assertTrue(any({2,3,8}<=dict(c.cases).keys() for c in self.wind_rows(p,f)))
        self.assertTrue(any(c.family=='ELUN' and dict(c.cases).get(1)==1
                            and {2,3,8}<=dict(c.cases).keys()
                            and any(d['case']==2 and d['role']=='Principal' for d in c.detail)
                            for c in generate(p).combinations))

    def test_special_and_construction_wind_filter(self):
        for f in ('ELUE','ELUC'):
            p=self.project();p['families']=[f]
            p['effective'][f]='psi0';p['effective_reason']='Condição do teste'
            p['actions'][2]['roles'][f]='primary'
            rows=self.wind_rows(p,f)
            self.assertTrue(any(8 in dict(c.cases) and dict(c.cases)[1]==1 for c in rows))
            self.assertTrue(all(2 not in dict(c.cases) for c in rows if dict(c.cases)[1]==1))
            self.assertTrue(any(2 in dict(c.cases) and dict(c.cases)[1]>1 for c in rows))

    def test_required_companion_conflict_does_not_force_absence(self):
        p=self.project();p['families']=['ELUN']
        p['actions'][0]['g_effect']='favorable'
        p['actions'][1].update(presence='required',primary=False,notes='')
        p['actions'][-1]['primary']=False
        with self.assertRaisesRegex(InputError,'nenhuma combinação válida'):
            generate(p)

    def test_other_principal_route_remains_after_wind_filter(self):
        p=self.project();p['families']=['ELUN'];p['actions']=p['actions'][:3]
        p['actions'][0]['g_effect']='favorable'
        q=p['actions'][1]
        q.update(type='CUSTOM',notes='',custom={'standard':p['standard'],'nature':'Q',
                 'gamma':['1.4',0,'1.2',0,1,0],'psi':[1,1,1],'source':'Critério de teste'})
        # Wind ψ0=0.6 means an allowed Q-led vector differs from the forbidden wind-led vector.
        rows=generate(p).combinations
        self.assertFalse(any(dict(c.cases).get(2)==D('1.4') and dict(c.cases).get(3)==D('1.4') for c in rows))
        self.assertTrue(any(dict(c.cases).get(2)==D('1.4') and dict(c.cases).get(3)==D('0.84') for c in rows))

    def grouped_winds(self):
        p=example_project();p['actions'].pop(1)
        p.update(q_mode='grouped',temperature_separate=None,families=['ELUN'])
        return p

    def test_four_winds_one_group_use_own_gamma_in_all_standards(self):
        for std in BANK['standards']:
            p=self.grouped_winds();p['standard']=std
            self.assertEqual(active_variable_group_count(p),1)
            self.assertEqual(factor_record(p,p['actions'][1])['gamma'][0],D('1.4'))
            rows=generate(p).combinations
            self.assertTrue(any(dict(c.cases).get(3)==D('1.4') for c in rows))
            self.assertFalse(any(coef==D('1.5') for c in rows for cid,coef in c.cases if cid>=3))

    def test_single_group_preserves_each_type_factor(self):
        p=self.project();p.update(q_mode='grouped',temperature_separate=False)
        for a in p['actions'][1:]:a.update(group=20,compatibility='compatible')
        self.assertEqual(active_variable_group_count(p),1)
        self.assertEqual([factor_record(p,a)['gamma'][0] for a in p['actions'][1:]],
                         [D('1.5'),D('1.4'),D('1.2')])

    def test_inactive_group_excluded_active_group_counts_even_when_absent(self):
        p=self.grouped_winds()
        q=example_project()['actions'][1];q.update(group=9,compatibility='exclusive',active=False)
        p['actions'].append(q)
        self.assertEqual(active_variable_group_count(p),1)
        self.assertEqual(factor_record(p,p['actions'][1])['gamma'][0],D('1.4'))
        q['active']=True;p['temperature_separate']=False
        self.assertEqual(active_variable_group_count(p),2)
        rows=generate(p).combinations
        wind_only=[c for c in rows if 3 in dict(c.cases) and 2 not in dict(c.cases)]
        self.assertTrue(wind_only)
        self.assertTrue(all(dict(c.cases)[3]==D('1.5') for c in wind_only))

    def test_grouped_factors_follow_each_standard_table(self):
        for std,key in [('NBR 8800:2024','Q agrupadas'),('NBR 14762:2010','Q agrupadas <=5'),('NBR 8681:2025','Q agrupadas')]:
            p=example_project();p.update(standard=std,q_mode='grouped',g_mode='grouped',temperature_separate=False,occupancy_band='<=5')
            fr=factor_record(p,p['actions'][2])
            self.assertEqual(fr['gamma'][0],D(str(GAMMA[(std,key)]['values'][0])))
            self.assertEqual(fr['source_gamma'],GAMMA[(std,key)]['source'])
            self.assertTrue(generate(p).combinations)

    def test_ungrouped_independent_and_linked_cases(self):
        p=self.grouped_winds();p['actions']=p['actions'][:2]
        a=p['actions'][1];a.update(group=None,compatibility=None)
        b=deepcopy(a);b['case']=7;p['actions'].append(b)
        self.assertEqual(active_variable_group_count(p),1)
        self.assertTrue(generate(p).combinations)
        b['origin']='OUTRA'
        self.assertEqual(active_variable_group_count(p),2)
        p['temperature_separate']=False
        self.assertEqual(factor_record(p,a)['gamma'][0],D('1.5'))

    def test_temperature_counts_but_can_keep_specific_gamma(self):
        p=self.project();p['actions'].pop(1)
        p.update(q_mode='grouped',temperature_separate=True)
        self.assertEqual(active_variable_group_count(p),2)
        self.assertEqual(factor_record(p,p['actions'][1])['gamma'][0],D('1.5'))
        self.assertEqual(factor_record(p,p['actions'][2])['gamma'][0],D('1.2'))

    def test_legacy_prefix_removed_notes_retained(self):
        p=example_project();p.update(prefix='ANTIGO_',app_version='PY03')
        p['actions'][0]['notes']='Registro anterior'
        loaded=load_project(dump_project(p))
        self.assertEqual(loaded['prefix'],'')
        self.assertEqual(loaded['actions'][0]['notes'],'Registro anterior')
        for source in (p,loaded):
            result=generate(source)
            self.assertTrue(all(c.name.startswith(c.family+'_') for c in result.combinations))
            self.assertEqual(result.wind_filtered,4)
            self.assertEqual(result.combinations[0].detail[0]['notes'],'Registro anterior')


class PY04InterfaceTests(unittest.TestCase):
    def test_removed_fields_revision_history_and_group_status(self):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
        next(b for b in at.button if b.label=='Carregar exemplo didático').click().run()
        self.assertFalse(at.exception)
        self.assertNotIn('Prefixo dos nomes',[x.label for x in at.text_input])
        self.assertNotIn('Observações',[x.label for x in at.text_area])
        self.assertIn('Histórico de revisões',[x.label for x in at.tabs])
        self.assertEqual(REVISIONS[0]['version'],'PY04')
        next(s for s in at.selectbox if s.label=='Variáveis (γQ)').set_value('grouped').run()
        self.assertTrue(any('2 grupo(s)' in x.value for x in at.caption))
        # Disable the ungrouped surcharge: only the wind group remains.
        next(s for s in at.selectbox if s.label=='Escolha uma ação para editar').set_value(1).run()
        next(b for b in at.button if b.label=='Editar ação').click().run()
        next(c for c in at.checkbox if c.label=='Ação ativa').uncheck().run()
        next(b for b in at.button if b.label=='Salvar ação').click().run()
        self.assertTrue(any('1 grupo(s)' in x.value for x in at.caption))
        next(b for b in at.button if b.label=='Gerar combinações').click().run()
        self.assertFalse(at.exception);self.assertFalse(at.error)
        self.assertIn('\t3\t1,4',at.code[0].value)


if __name__=='__main__':
    unittest.main()
