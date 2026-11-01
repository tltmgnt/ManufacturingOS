from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manufacturing_os.study import binding, run_study

ROOT=Path(__file__).resolve().parents[1]


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/integrated-study.json').read_text())
        self.spec['uncertainty']['samples']=5

    def rebind(self):
        self.spec['binding']=binding(self.spec['manufacturing_input'],self.spec['scenario'])

    def test_integrates_one_scenario_and_preserves_approval_boundary(self):
        result=run_study(self.spec)
        self.assertEqual(result['review_state'],'HUMAN_REVIEW')
        self.assertEqual(result['plan']['verification']['status'],'CONDITIONAL')
        self.assertFalse(result['production_authorized'])
        self.assertEqual(result['approval_state'],'PENDING_HUMAN_REVIEW')
        self.assertEqual(result['estimate']['input_fingerprint'],result['binding']['scenario_fingerprint'])
        self.assertEqual(result['uncertainty']['baseline'],result['estimate'])
        self.assertEqual(result['simulation']['input']['scenario'],self.spec['scenario'])
        self.assertEqual(result['reference_report']['passed_checks'],12)
        self.assertEqual(result['required_approvals'],result['plan']['required_approvals'])

    def test_stale_package_binding_rejected(self):
        self.spec['manufacturing_input']['design_revision']='B'
        with self.assertRaisesRegex(ValueError,'stale study binding'):
            run_study(self.spec)
        self.rebind()
        self.assertEqual(run_study(self.spec)['plan']['input_fingerprint'],self.spec['binding']['input_fingerprint'])

    def test_stale_scenario_binding_rejected(self):
        self.spec['scenario']['operations'][0]['cycle_time']['value']=4
        with self.assertRaisesRegex(ValueError,'stale study binding'):
            run_study(self.spec)

    def test_quantity_and_unit_mismatch_rejected(self):
        for demand in [{'value':73,'unit':'piece'},{'value':72,'unit':'piece/month'}]:
            spec=deepcopy(self.spec)
            spec['manufacturing_input']['demand']=demand
            spec['binding']=binding(spec['manufacturing_input'],spec['scenario'])
            with self.assertRaisesRegex(ValueError,'demand in piece'):
                run_study(spec)

    def test_hard_constraint_failure_survives_integration(self):
        self.spec['manufacturing_input']['constraints'][0]['satisfied']=False
        self.rebind()
        result=run_study(self.spec)
        self.assertEqual(result['review_state'],'REVISION_REQUIRED')
        self.assertIn('PLAN_VERIFICATION_FAILED',[f['code'] for f in result['findings']])
        self.assertEqual(result['plan']['verification']['conflicts'][0]['classification'],'hard')
        self.assertFalse(result['production_authorized'])

    def test_model_shortfalls_require_revision(self):
        self.spec['manufacturing_input']['demand']['value']=500
        self.spec['scenario']['target_good_units']=500
        self.spec['reference_suite']=None
        self.rebind()
        report=run_study(self.spec)
        codes={f['code'] for f in report['findings']}
        self.assertTrue({'ESTIMATED_CAPACITY_SHORTFALL','SIMULATED_TARGET_MISS'} <= codes)
        self.assertEqual(report['review_state'],'REVISION_REQUIRED')

    def test_missing_reference_stays_explicit(self):
        self.spec['reference_suite']=None
        report=run_study(self.spec)
        self.assertIsNone(report['reference_report'])
        self.assertIn('NO_REFERENCE_SUITE',[f['code'] for f in report['findings']])
        self.assertEqual(report['review_state'],'HUMAN_REVIEW')

    def test_unrelated_reference_suite_rejected(self):
        self.spec['reference_suite']['cases']=self.spec['reference_suite']['cases'][1:]
        with self.assertRaisesRegex(ValueError,'does not cover'):
            run_study(self.spec)

    def test_reference_failure_requires_revision(self):
        self.spec['reference_suite']['cases'][0]['expected']['total_cost']['value']=0
        report=run_study(self.spec)
        self.assertEqual(report['review_state'],'REVISION_REQUIRED')
        self.assertIn('REFERENCE_CHECK_FAILED',[f['code'] for f in report['findings']])

    def test_immutable_deterministic_reconstructable(self):
        original=deepcopy(self.spec)
        report=run_study(self.spec)
        self.assertEqual(original,self.spec)
        self.assertEqual(report,run_study(report['input']))

    def test_config_cannot_override_bound_scenario(self):
        self.spec['simulation']['scenario']={}
        with self.assertRaises(ValueError):
            run_study(self.spec)

    def test_cli_reports_success_failure_invalid_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'study.json'
            output=Path(directory)/'report.json'
            def run(*extra):
                return subprocess.run([sys.executable,'-m','manufacturing_os.study',str(source),*map(str,extra)],cwd=ROOT,capture_output=True,text=True)
            source.write_text(json.dumps(self.spec))
            result=run('--output',output)
            self.assertEqual(result.returncode,0,result.stderr)
            saved=output.read_text()
            self.assertEqual(run('--output',output).returncode,2)
            self.assertEqual(saved,output.read_text())
            self.spec['simulation']['batch_size']=1
            source.write_text(json.dumps(self.spec))
            result=run()
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(result.stdout)['review_state'],'REVISION_REQUIRED')
            self.spec['binding']['input_fingerprint']='stale'
            source.write_text(json.dumps(self.spec))
            self.assertEqual(run().returncode,2)
