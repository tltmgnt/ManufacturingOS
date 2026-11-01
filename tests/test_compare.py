from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manufacturing_os.compare import compare_studies, input_changes
from manufacturing_os.study import binding, run_study

ROOT=Path(__file__).resolve().parents[1]


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/integrated-study.json').read_text())
        self.spec['uncertainty']['samples']=3
        self.before=run_study(self.spec)

    def revise(self):
        after=deepcopy(self.spec)
        after['revision']='2'
        after['reference_suite']=None
        return after

    def bind(self,spec):
        spec['binding']=binding(spec['manufacturing_input'],spec['scenario'])
        return run_study(spec)

    def test_identical_reports_have_zero_deltas(self):
        result=compare_studies(self.before,self.before)
        self.assertEqual(result['input_changes'],[])
        self.assertEqual(result['context_changes'],[])
        self.assertEqual(result['changed_specialist_revisions'],[])
        self.assertTrue(all(row['delta']['value']==0 for row in result['estimates'].values()))
        self.assertFalse(result['production_authorized'])

    def test_capacity_change_matches_hand_difference(self):
        spec=self.revise()
        spec['scenario']['operations'][1]['machines']=2
        after=self.bind(spec)
        result=compare_studies(self.before,after)
        self.assertAlmostEqual(result['estimates']['expected_good_capacity']['delta']['value'],31.2)
        self.assertEqual(result['estimates']['expected_good_capacity']['delta']['unit'],'piece/horizon')
        self.assertIn('/scenario/operations/1/machines',[change['path'] for change in result['input_changes']])
        self.assertEqual(result['operations']['matched']['finish']['available_machine_time']['delta']['value'],8)

    def test_different_currency_no_cost_delta(self):
        spec=self.revise()
        spec['scenario']['currency']='EUR'
        spec['scenario']['material_cost_per_start']['unit']='EUR/piece'
        for op in spec['scenario']['operations']:
            for key in ['machine_rate','labor_rate']:
                op[key]['unit']='EUR/h'
        result=compare_studies(self.before,self.bind(spec))
        self.assertIsNone(result['estimates']['unit_cost']['delta'])
        self.assertEqual(result['estimates']['unit_cost']['comparison'],'INCOMPATIBLE_UNITS')
        self.assertIn('CURRENCY_CHANGED',[row['code'] for row in result['context_changes']])

    def test_changed_context_is_explicit(self):
        spec=self.revise()
        spec['manufacturing_input']['demand']['value']=80
        spec['scenario']['target_good_units']=80
        spec['scenario']['horizon']['value']=10
        spec['manufacturing_input']['facility']['revision']='2'
        spec['simulation']={'seed':1,'batch_size':120}
        spec['uncertainty']['seed']=2
        result=compare_studies(self.before,self.bind(spec))
        codes={row['code'] for row in result['context_changes']}
        self.assertTrue({'DEMAND_CHANGED','FACILITY_CHANGED','HORIZON_CHANGED','SIMULATION_CONFIG_CHANGED','UNCERTAINTY_CONFIG_CHANGED','REFERENCE_SUITE_CHANGED'}<=codes)

    def test_finding_added_and_no_longer_reported(self):
        spec=self.revise()
        spec['simulation']['batch_size']=1
        failed=self.bind(spec)
        introduced=compare_studies(self.before,failed)['findings']['introduced']
        self.assertIn('SIMULATED_TARGET_MISS',[f['code'] for f in introduced])
        removed=compare_studies(failed,self.before)['findings']['no_longer_reported']
        self.assertIn('SIMULATED_TARGET_MISS',[f['code'] for f in removed])

    def test_operations_matched_by_id_after_reordering(self):
        spec=self.revise()
        spec['scenario']['operations'].reverse()
        result=compare_studies(self.before,self.bind(spec))
        self.assertEqual(set(result['operations']['matched']),{'cut','finish'})
        self.assertEqual(result['operations']['added'],[])
        self.assertEqual(result['operations']['removed'],[])
        spec['scenario']['operations'][0]['operation_id']='polish'
        spec['uncertainty']['ranges']=[]
        result=compare_studies(self.before,self.bind(spec))
        self.assertEqual(result['operations']['added'],['polish'])
        self.assertEqual(result['operations']['removed'],['finish'])

    def test_changed_package_propagates_specialist_revisions(self):
        spec=self.revise()
        spec['manufacturing_input']['design_revision']='B'
        result=compare_studies(self.before,self.bind(spec))
        self.assertEqual(set(result['changed_specialist_revisions']),set(self.before['plan']['results']))

    def test_different_products_and_tampered_reports_rejected(self):
        spec=self.revise()
        spec['manufacturing_input']['product_id']='other-product'
        with self.assertRaisesRegex(ValueError,'same product_id'):
            compare_studies(self.before,self.bind(spec))
        tampered=deepcopy(self.before)
        tampered['estimate']['unit_cost']['value']=0
        with self.assertRaisesRegex(ValueError,'differs from reconstruction'):
            compare_studies(self.before,tampered)

    def test_json_pointer_and_absent_null_distinction(self):
        changes=input_changes({'a/b~':None,'removed':None},{'a/b~':1,'added':None})
        self.assertEqual(changes[0]['path'],'/a~1b~0')
        added=next(row for row in changes if row['path']=='/added')
        self.assertFalse(added['before_present'])
        self.assertTrue(added['after_present'])
        self.assertIsNone(added['after'])
        self.assertEqual(len(input_changes({'flag':True},{'flag':1})),1)

    def test_reproducibility_input_immutability_and_output_isolation(self):
        spec=self.revise()
        after=self.bind(spec)
        saved=deepcopy((self.before,after))
        report=compare_studies(self.before,after)
        self.assertEqual(saved,(self.before,after))
        reconstructed=compare_studies(run_study(report['sources']['before']['input']),run_study(report['sources']['after']['input']))
        self.assertEqual(report,reconstructed)
        report['plan_verification']['before']['status']='edited'
        self.assertEqual(self.before['plan']['verification']['status'],'CONDITIONAL')

    def test_cli_success_no_overwrite_and_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            before=Path(directory)/'before.json'
            after=Path(directory)/'after.json'
            output=Path(directory)/'comparison.json'
            before.write_text(json.dumps(self.before))
            after.write_text(json.dumps(self.bind(self.revise())))
            command=[sys.executable,'-m','manufacturing_os.compare',str(before),str(after),'--output',str(output)]
            first=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            original=output.read_text()
            self.assertEqual(json.loads(original)['product_id'],self.spec['manufacturing_input']['product_id'])
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(original,output.read_text())
            after.write_text('{}')
            command=command[:-2]
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
