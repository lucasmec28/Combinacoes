import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

class InterfaceTests(unittest.TestCase):
    def app(self):
        return AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20).run()
    def click(self,at,label):
        next(x for x in at.button if x.label==label).click().run()
        self.assertEqual(len(at.exception),0)
    def test_empty_validation(self):
        at=self.app();self.assertEqual(len(at.exception),0)
        self.click(at,'Gerar combinações')
        self.assertTrue(any('norma' in e.value for e in at.error))
        self.assertEqual(len(at.code),0)
    def test_example_generate_edit_stale_regenerate(self):
        at=self.app();self.click(at,'Carregar exemplo didático');self.click(at,'Gerar combinações')
        self.assertEqual(at.metric[0].value,'54');self.assertEqual(len(at.code),1)
        self.click(at,'Editar ação')
        next(x for x in at.text_input if x.label=='Nome do carregamento').set_value('PESO EDITADO').run()
        self.click(at,'Salvar ação')
        self.assertEqual(len(at.code),0)
        self.assertTrue(any('mudaram' in w.value for w in at.warning))
        self.click(at,'Gerar combinações');self.assertEqual(at.metric[0].value,'54')
    def test_filter_and_delete(self):
        at=self.app();self.click(at,'Carregar exemplo didático');self.click(at,'Gerar combinações')
        next(x for x in at.multiselect if x.label=='Famílias a copiar / baixar').set_value(['ELUN']).run()
        self.assertEqual(len(at.exception),0);self.assertEqual(len(at.code[0].value.splitlines()),28)
        self.click(at,'Excluir ação');self.assertEqual(len(at.code),0)
        self.assertEqual(len(at.session_state['project']['actions']),5)
    def test_type_change_exceptional(self):
        at=self.app();self.click(at,'Carregar exemplo didático');self.click(at,'Editar ação')
        next(x for x in at.selectbox if x.label=='Tipo de carregamento').set_value('EXC').run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(next(x for x in at.multiselect if x.label=='Participa das combinações').options,['ELU excepcional'])
    def test_duplicate_origin_and_case(self):
        at=self.app();self.click(at,'Carregar exemplo didático');self.click(at,'Duplicar ação')
        actions=at.session_state['project']['actions']
        self.assertEqual(len(actions),7);self.assertEqual(actions[-1]['case'],7)
        self.assertNotEqual(actions[-1]['origin'],actions[0]['origin'])

if __name__=='__main__':unittest.main()
