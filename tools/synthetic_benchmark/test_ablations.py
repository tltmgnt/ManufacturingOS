import unittest
import benchmark as m

class AblationTests(unittest.TestCase):
    def test_restore_layers_and_measure_ablation(self):
        original=m.LAYERS['B6'].copy()
        t=m.generate(1)[1]
        try:
            m.LAYERS['B6']=original-{'evidence'}
            self.assertNotEqual(m.participant(t,'B6')['decision'],'DEFER')
        finally:m.LAYERS['B6']=original
        self.assertEqual(m.participant(t,'B6')['decision'],'DEFER')

if __name__=='__main__':unittest.main()
