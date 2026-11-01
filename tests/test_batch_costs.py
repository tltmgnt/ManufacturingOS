from copy import deepcopy
import json
from pathlib import Path
import unittest

from manufacturing_os.bundle import build_bundle,verify_bundle
from manufacturing_os.compare import compare_studies
from manufacturing_os.review import render_review
from manufacturing_os.simulation import simulate_batch
from manufacturing_os.study import binding,run_study

ROOT=Path(__file__).resolve().parents[1]


class BatchCostTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/finite-batch.json').read_text())
        self.spec['batch_size']=3
        self.spec['include_costs']=True
        self.spec['scenario']['horizon']={'value':5,'unit':'h'}
        self.spec['scenario']['target_good_units']=3
        for index,op in enumerate(self.spec['scenario']['operations']):
            op.update(cycle_time={'value':index+1,'unit':'h'},setup_time={'value':0,'unit':'h'},availability=1,yield_fraction=1,machines=1)

    def test_hand_calculated_full_batch_cost(self):
        report=simulate_batch(self.spec)
        costs=report['cost_report']
        # Material 3*5=15; cut 3h*(20+10)=90; finish 6h*(15+5)=120.
        self.assertEqual(costs['material_cost']['value'],15)
        self.assertEqual(costs['machine_cost']['value'],150)
        self.assertEqual(costs['labor_cost']['value'],60)
        self.assertEqual(costs['total_cost']['value'],225)
        self.assertEqual(costs['unit_cost'],{'value':75.0,'unit':'USD/good_piece'})
        self.assertEqual(costs['scope'],'FULL_SIMULATED_BATCH')
        self.assertFalse(costs['production_authorized'])

    def test_unit_cost_uses_eventual_good_not_horizon_good(self):
        report=simulate_batch(self.spec)
        self.assertEqual(report['good_by_horizon'],2)
        self.assertEqual(report['eventual_good_units'],3)
        self.assertEqual(report['cost_report']['unit_cost']['value'],75)
        self.assertEqual(report['cost_report']['eventual_good_output']['value'],3)

    def test_planned_setups_charge_each_machine(self):
        self.spec['scenario']['operations'][0]['setup_time']={'value':1,'unit':'h'}
        self.spec['scenario']['operations'][0]['machines']=2
        costs=simulate_batch(self.spec)['cost_report']
        self.assertEqual(costs['operations'][0]['planned_setup_time']['value'],2)
        self.assertEqual(costs['total_cost']['value'],285)

    def test_scrap_limits_downstream_processing_but_keeps_planned_setup(self):
        self.spec['scenario']['operations'][0]['yield_fraction']=1e-20
        self.spec['scenario']['operations'][1]['setup_time']={'value':1,'unit':'h'}
        costs=simulate_batch(self.spec)['cost_report']
        self.assertEqual(costs['operations'][1]['processed_input']['value'],0)
        self.assertEqual(costs['operations'][1]['total_cost']['value'],20)
        self.assertEqual(costs['total_cost']['value'],125)
        self.assertIsNone(costs['unit_cost'])
        self.assertIn('undefined',costs['unit_cost_issue'])

    def test_downtime_and_availability_do_not_charge_idle_elapsed_time(self):
        original=simulate_batch(self.spec)['cost_report']
        self.spec['downtime']=[{'operation_id':'finish','machine_id':0,'windows':[{'start':{'value':0,'unit':'h'},'end':{'value':10,'unit':'h'}}]}]
        self.assertEqual(simulate_batch(self.spec)['cost_report'],original)
        del self.spec['downtime']
        self.spec['scenario']['operations'][0]['availability']=.5
        self.assertEqual(simulate_batch(self.spec)['cost_report'],original)

    def test_zero_rates_and_material_allow_zero_cost(self):
        self.spec['scenario']['material_cost_per_start']['value']=0
        for op in self.spec['scenario']['operations']:
            op['machine_rate']['value']=0
            op['labor_rate']['value']=0
        self.assertEqual(simulate_batch(self.spec)['cost_report']['unit_cost']['value'],0)

    def test_opt_in_boolean_and_disabled_behavior(self):
        for value in [1,'true',None]:
            self.spec['include_costs']=value
            with self.assertRaises(ValueError):
                simulate_batch(self.spec)
        self.spec['include_costs']=False
        disabled=simulate_batch(self.spec)
        self.assertNotIn('cost_report',disabled)
        self.assertNotIn('normalized_downtime',disabled)
        del self.spec['include_costs']
        self.assertEqual(disabled['jobs'],simulate_batch(self.spec)['jobs'])

    def study_spec(self):
        spec=json.loads((ROOT/'examples/source-study.json').read_text())
        spec['uncertainty']['samples']=2
        spec['simulation']['include_costs']=True
        spec['reference_suite']=None
        return spec

    def test_study_html_and_bundle_include_scope(self):
        spec=self.study_spec()
        report=run_study(spec)
        self.assertIn('FULL_BATCH_COST_SCOPE',[row['code'] for row in report['findings']])
        self.assertIn('Full simulated batch cost estimates',render_review(report))
        self.assertEqual(verify_bundle(build_bundle(spec))['status'],'VERIFIED_CONTENT')

    def test_no_good_output_html_and_comparison_remain_undefined(self):
        spec=self.study_spec()
        before=run_study(spec)
        spec['scenario']['operations'][1]['yield_fraction']=1e-20
        spec['binding']=binding(spec['manufacturing_input'],spec['scenario'])
        after=run_study(spec)
        self.assertIsNone(after['simulation']['cost_report']['unit_cost'])
        self.assertIn('SIMULATED_UNIT_COST_UNDEFINED',[row['code'] for row in after['findings']])
        self.assertIn('Undefined:',render_review(after))
        delta=compare_studies(before,after)['finite_batch_costs']['metrics']['unit_cost']
        self.assertIsNone(delta['delta'])
        self.assertEqual(delta['comparison'],'UNDEFINED_INPUT')

    def test_comparison_reports_missing_costing_without_zero_fill(self):
        spec=self.study_spec()
        after=run_study(spec)
        del spec['simulation']['include_costs']
        comparison=compare_studies(run_study(spec),after)['finite_batch_costs']
        self.assertFalse(comparison['before_available'])
        self.assertEqual(comparison['metrics'],{})
        self.assertIsNotNone(comparison['issue'])

    def test_comparison_cost_units_must_match(self):
        spec=self.study_spec()
        before=run_study(spec)
        spec['scenario']['currency']='EUR'
        spec['scenario']['material_cost_per_start']['unit']='EUR/piece'
        for op in spec['scenario']['operations']:
            for key in ['machine_rate','labor_rate']:
                op[key]['unit']='EUR/h'
        spec['binding']=binding(spec['manufacturing_input'],spec['scenario'])
        delta=compare_studies(before,run_study(spec))['finite_batch_costs']['metrics']['total_cost']
        self.assertIsNone(delta['delta'])
        self.assertEqual(delta['comparison'],'INCOMPATIBLE_UNITS')

    def test_deterministic_and_immutable(self):
        original=deepcopy(self.spec)
        self.assertEqual(simulate_batch(self.spec),simulate_batch(self.spec))
        self.assertEqual(original,self.spec)
