import unittest
import benchmark as m

class BenchmarkTests(unittest.TestCase):
    def test_all_adapters_bounded(self):
        for t in m.generate(3):
            for k in m.LAYERS:
                s=m.participant(t,k)
                self.assertLessEqual(s['evaluations'],100)
    def test_b5_b6_feedback_difference(self):
        t=m.generate(1)[2];t.update(c=1,f=2,deadline=7,blocked=[[2,3]])
        a=m.participant(t,'B5');b=m.participant(t,'B6')
        self.assertEqual(a['decision'],'FAILURE');self.assertEqual(b['decision'],'ACCEPT')
        self.assertTrue(m.valid(t,b['schedule']))
        self.assertEqual(len([x for x in b['trace'] if isinstance(x,dict) and 'round' in x]),2)
    def test_unresolved_premise(self):
        for t in (m.generate(1)[1],m.generate(1)[4]):
            self.assertEqual(m.oracle(t)['decision'],'DEFER')
            self.assertEqual(m.participant(t,'B6')['decision'],'DEFER')
    def test_nominal_oracle(self):
        t=m.generate(1)[0];t.update(c=1,f=2,deadline=5)
        self.assertEqual(m.oracle(t)['earliest'],5)
    def test_rejections(self):
        for i in (3,6):self.assertEqual(m.oracle(m.generate(1)[i])['decision'],'REJECT')
    def test_gate_rejects_overlap(self):
        t=m.generate(1)[0]
        self.assertFalse(m.valid(t,[0,t['c'],t['c'],t['c']]))
    def test_block_sampling_reproducible(self):
        self.assertEqual(m.generate(2),m.generate(2))
        self.assertNotEqual(m.generate(2,1),m.generate(2,2))
    def test_bootstrap_preserves_zero(self):self.assertEqual(m.bootstrap([0,0],n=100),[0,0])
    def test_budget_enforced(self):
        b=m.Budget(1);t=m.generate(1)[0];b.evaluate(t,[0,1,1,3],True)
        with self.assertRaises(RuntimeError):b.evaluate(t,[0,1,1,3],True)

if __name__=='__main__':unittest.main()
