from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from manufacturing_os.schemas import validate_contract
from manufacturing_os.study import preflight_study,run_study

ROOT=Path(__file__).resolve().parents[1]


class StudyPreflightTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/observation-study.json').read_text())
        self.spec['uncertainty']['samples']=2

    def test_all_study_features_validate_without_analysis(self):
        for name in ['integrated-study.json','evidence-study.json','source-study.json','downtime-study.json','cost-study.json','replication-study.json','observation-study.json']:
            spec=json.loads((ROOT/'examples'/name).read_text())
            result=preflight_study(spec)
            self.assertEqual(result['status'],'VALID')
            self.assertFalse(result['analysis_executed'])
            self.assertFalse(result['production_authorized'])
            self.assertEqual(result['scope'],'STUDY_INPUT_PREFLIGHT')
        self.assertEqual(preflight_study(self.spec)['observation_reference_status'],'REFERENCE_CONTRACT_VALID')

    def test_no_agents_simulation_sampling_estimation_or_reference_comparisons(self):
        with ExitStack() as stack:
            for name in ['manufacturing_os.study.simulate_batch','manufacturing_os.study.simulate',
                         'manufacturing_os.study.run_replications','manufacturing_os.study.estimate',
                         'manufacturing_os.study.validate_references','manufacturing_os.engine.Orchestrator.run',
                         'manufacturing_os.experiments.estimate','manufacturing_os.simulation.random.Random']:
                stack.enter_context(patch(name,side_effect=AssertionError('analysis must not run')))
            result=preflight_study(self.spec)
            reference=json.loads((ROOT/'examples/integrated-study.json').read_text())
            self.assertEqual(preflight_study(reference)['status'],'VALID')
        self.assertFalse(result['analysis_executed'])

    def test_stale_bindings_and_demand_mismatch_rejected(self):
        self.spec['binding']['input_fingerprint']='stale'
        with self.assertRaisesRegex(ValueError,'stale study binding'):
            preflight_study(self.spec)
        spec=json.loads((ROOT/'examples/integrated-study.json').read_text())
        spec['scenario']['target_good_units']+=1
        from manufacturing_os.study import binding
        spec['binding']=binding(spec['manufacturing_input'],spec['scenario'])
        with self.assertRaisesRegex(ValueError,'demand in piece'):
            preflight_study(spec)

    def test_late_uncertainty_errors_now_precede_simulation_execution(self):
        self.spec['uncertainty']['ranges']=[{'operation_id':'missing','parameter':'yield_fraction','low':.5,'high':.9}]
        with patch('manufacturing_os.study.simulate_batch',side_effect=AssertionError('must not simulate')):
            with self.assertRaisesRegex(ValueError,'unknown operation_id'):
                run_study(self.spec)

    def test_replication_and_simulation_settings_rejected_early(self):
        for field,value in [('seed',True),('batch_size',0),('include_costs','true')]:
            spec=deepcopy(self.spec)
            spec['simulation'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                preflight_study(spec)
        self.spec['replications']['runs']=1001
        with self.assertRaisesRegex(ValueError,'1 to 1000'):
            preflight_study(self.spec)

    def test_downtime_validation_and_budget_are_shared(self):
        self.spec['simulation']['downtime']=[{'operation_id':'missing','machine_id':0,'windows':[{'start':{'value':0,'unit':'h'},'end':{'value':1,'unit':'h'}}]}]
        with self.assertRaisesRegex(ValueError,'unknown downtime operation'):
            preflight_study(self.spec)

    def test_reference_contract_and_coverage_without_calculations(self):
        spec=json.loads((ROOT/'examples/integrated-study.json').read_text())
        spec['reference_suite']['cases'][0]['expected']['total_cost']['unit']='EUR'
        with self.assertRaisesRegex(ValueError,'reference unit'):
            preflight_study(spec)
        spec=json.loads((ROOT/'examples/integrated-study.json').read_text())
        spec['reference_suite']['cases']=spec['reference_suite']['cases'][1:]
        with self.assertRaisesRegex(ValueError,'does not cover'):
            preflight_study(spec)

    def test_observation_prerequisites_and_bad_tolerances_are_configuration_errors(self):
        spec=deepcopy(self.spec)
        del spec['replications']
        with self.assertRaisesRegex(ValueError,'require evidence_policy'):
            preflight_study(spec)
        self.spec['evidence_policy']['max_age']['value']=1
        self.spec['observation_checks']['tolerances']['full_batch_total_cost']['value']=-1
        with self.assertRaises(ValueError):
            preflight_study(self.spec)

    def test_evidence_gaps_are_visible_diagnostics_not_input_malformation(self):
        self.spec['evidence_policy']['max_age']['value']=1
        checked=preflight_study(self.spec)
        self.assertEqual(checked['status'],'VALID')
        self.assertEqual(checked['evidence_status'],'COVERAGE_GAPS')
        self.assertEqual(checked['observation_reference_status'],'REFERENCE_UNAVAILABLE')
        self.assertEqual(checked['combined_uncovered_requirements'],['R1'])
        self.assertFalse(checked['production_authorized'])

    def test_reference_numeric_agreement_is_not_evaluated(self):
        campaign=json.loads((ROOT/'examples/scenario-campaign.json').read_text())
        spec=campaign['cases'][2]['study']
        checked=preflight_study(spec)
        self.assertEqual(checked['observation_reference_status'],'REFERENCE_CONTRACT_VALID')
        self.assertEqual(run_study(spec)['observation_report']['status'],'FAIL')

    def test_immutable_deterministic_and_execution_outputs_unchanged(self):
        original=deepcopy(self.spec)
        before=run_study(self.spec)
        checked=preflight_study(self.spec)
        self.assertEqual(checked,validate_contract('study',self.spec))
        self.assertEqual(checked,preflight_study(self.spec))
        self.assertEqual(before,run_study(self.spec))
        self.assertEqual(original,self.spec)

    def test_cli_study_validation_and_invalid_configuration(self):
        command=[sys.executable,'-m','manufacturing_os.cli','schema','validate','study',str(ROOT/'examples/observation-study.json')]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(json.loads(result.stdout)['analysis_executed'])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'study.json'
            self.spec['uncertainty']['samples']=0
            path.write_text(json.dumps(self.spec))
            command[-1]=str(path)
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
        exported=subprocess.run([sys.executable,'-m','manufacturing_os.cli','schema','export','study'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(exported.returncode,2)
