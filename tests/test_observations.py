import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manufacturing_os.bundle import build_bundle,verify_bundle
from manufacturing_os.compare import compare_studies
from manufacturing_os.models import ManufacturingInput,digest
from manufacturing_os.review import render_review
from manufacturing_os.study import binding,run_study

ROOT=Path(__file__).resolve().parents[1]


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/observation-study.json').read_text())
        self.spec['uncertainty']['samples']=2
        self.reference=json.loads((ROOT/'examples/observation-reference.json').read_text())

    def capture_reference(self,reference=None,sync_context=False):
        reference=deepcopy(self.reference if reference is None else reference)
        if sync_context:
            reference['context']['scenario_fingerprint']=binding(self.spec['manufacturing_input'],self.spec['scenario'])['scenario_fingerprint']
            reference['context']['simulation_config_fingerprint']=digest(self.spec['simulation'])
        raw=(json.dumps(reference,indent=2,sort_keys=True)+'\n').encode()
        self.spec['manufacturing_input']['evidence'][0]['content_hash']=hashlib.sha256(raw).hexdigest()
        self.spec['evidence_snapshot']['files'][0]['content_base64']=base64.b64encode(raw).decode()
        self.spec['evidence_snapshot']['input_fingerprint']=ManufacturingInput.from_dict(self.spec['manufacturing_input']).fingerprint
        self.spec['binding']=binding(self.spec['manufacturing_input'],self.spec['scenario'])

    def test_independent_hand_reference_passes_six_checks(self):
        report=run_study(self.spec)
        result=report['observation_report']
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['reference_kind'],'synthetic')
        self.assertEqual(result['observation_count'],1)
        self.assertEqual(len(result['checks']),6)
        cost=next(row for row in result['checks'] if row['metric']=='full_batch_total_cost')
        self.assertEqual(cost['observed']['value'],225)
        self.assertEqual(cost['model_mean']['value'],225)
        self.assertEqual(cost['residual']['value'],0)
        self.assertFalse(report['production_authorized'])
        self.assertEqual(report['review_state'],'HUMAN_REVIEW')

    def test_reference_pass_never_overrides_simulated_target_miss(self):
        self.spec['scenario']['target_good_units']=3
        self.spec['manufacturing_input']['demand']['value']=3
        self.capture_reference(sync_context=True)
        report=run_study(self.spec)
        self.assertEqual(report['observation_report']['status'],'PASS')
        self.assertEqual(report['review_state'],'REVISION_REQUIRED')
        self.assertIn('SIMULATED_TARGET_MISS',[row['code'] for row in report['findings']])

    def test_disagreement_requires_revision_and_retains_residual(self):
        self.reference['metrics']['full_batch_total_cost']['value']=220
        self.capture_reference()
        report=run_study(self.spec)
        self.assertEqual(report['review_state'],'REVISION_REQUIRED')
        self.assertEqual(report['observation_report']['status'],'FAIL')
        row=next(row for row in report['observation_report']['checks'] if row['metric']=='full_batch_total_cost')
        self.assertEqual(row['residual'],{'value':5.0,'unit':'USD'})

    def test_context_mismatch_never_computes_comparison(self):
        for key,value in [('product_id','other'),('facility_revision','other'),('scenario_fingerprint','other'),
                          ('simulation_config_fingerprint','other'),('batch_size',4),('horizon',{'value':6,'unit':'h'})]:
            reference=deepcopy(self.reference)
            reference['context'][key]=value
            self.capture_reference(reference)
            result=run_study(self.spec)['observation_report']
            self.assertEqual(result['status'],'CONTEXT_MISMATCH')
            self.assertEqual(result['checks'],[])
            self.assertTrue(any(key in issue for issue in result['issues']))

    def test_hash_mismatch_makes_selected_reference_unavailable(self):
        self.spec['evidence_snapshot']['files'][0]['content_base64']=base64.b64encode(b'changed bytes').decode()
        result=run_study(self.spec)['observation_report']
        self.assertEqual(result['status'],'REFERENCE_UNAVAILABLE')
        self.assertEqual(result['checks'],[])

    def test_stale_metadata_blocks_selected_reference_even_with_matching_hash(self):
        self.spec['evidence_policy']['max_age']['value']=1
        report=run_study(self.spec)
        self.assertEqual(report['source_report']['records'][0]['status'],'HASH_MATCHED')
        self.assertEqual(report['observation_report']['status'],'REFERENCE_UNAVAILABLE')
        self.assertEqual(report['review_state'],'REVISION_REQUIRED')

    def test_invalid_reference_units_counts_and_tolerances(self):
        bad=deepcopy(self.reference)
        bad['metrics']['full_batch_total_cost']['unit']='EUR'
        self.capture_reference(bad)
        with self.assertRaises(ValueError):
            run_study(self.spec)
        bad=deepcopy(self.reference)
        bad['observation_count']=True
        self.capture_reference(bad)
        with self.assertRaises(ValueError):
            run_study(self.spec)
        self.capture_reference()
        self.spec['observation_checks']['tolerances']['full_batch_total_cost']['value']=-1
        with self.assertRaises(ValueError):
            run_study(self.spec)
        self.spec['observation_checks']['tolerances']['full_batch_total_cost']['value']=1e-9
        raw=json.dumps(self.reference).replace('"value": 225','"value": 220, "value": 225').encode()
        self.spec['manufacturing_input']['evidence'][0]['content_hash']=hashlib.sha256(raw).hexdigest()
        self.spec['evidence_snapshot']['files'][0]['content_base64']=base64.b64encode(raw).decode()
        self.spec['evidence_snapshot']['input_fingerprint']=ManufacturingInput.from_dict(self.spec['manufacturing_input']).fingerprint
        self.spec['binding']=binding(self.spec['manufacturing_input'],self.spec['scenario'])
        with self.assertRaisesRegex(ValueError,'duplicate JSON key'):
            run_study(self.spec)

    def test_prerequisites_and_unknown_evidence_rejected(self):
        for key in ['replications','evidence_snapshot','evidence_policy']:
            spec=deepcopy(self.spec)
            del spec[key]
            with self.assertRaises(ValueError):
                run_study(spec)
        self.spec['observation_checks']['evidence_id']='unknown'
        with self.assertRaises(ValueError):
            run_study(self.spec)

    def test_undefined_model_unit_cost_is_not_a_conditional_mean_pass(self):
        self.spec['scenario']['operations'][1]['yield_fraction']=1e-20
        self.capture_reference(sync_context=True)
        result=run_study(self.spec)['observation_report']
        row=next(row for row in result['checks'] if row['metric']=='full_batch_unit_cost')
        self.assertEqual(row['status'],'FAIL')
        self.assertIsNone(row['model_mean'])
        self.assertIsNone(row['residual'])
        self.assertIn('undefined',row['issue'])

    def test_unavailable_cost_metric_fails_explicitly(self):
        self.spec['simulation']['include_costs']=False
        self.capture_reference(sync_context=True)
        result=run_study(self.spec)['observation_report']
        row=next(row for row in result['checks'] if row['metric']=='full_batch_total_cost')
        self.assertEqual(row['status'],'FAIL')
        self.assertIn('unavailable',row['issue'])

    def test_absolute_tolerance_boundary(self):
        self.reference['metrics']['full_batch_total_cost']['value']=220
        self.capture_reference()
        self.spec['observation_checks']['tolerances']['full_batch_total_cost']['value']=5
        self.assertEqual(run_study(self.spec)['observation_report']['status'],'PASS')

    def test_html_bundle_comparison_and_reconstruction(self):
        original=deepcopy(self.spec)
        report=run_study(self.spec)
        self.assertEqual(original,self.spec)
        self.assertEqual(report,run_study(report['input']))
        self.assertIn('Captured observation reference: PASS',render_review(report))
        self.assertEqual(verify_bundle(build_bundle(self.spec))['review_state'],'HUMAN_REVIEW')
        before=deepcopy(self.spec)
        del before['observation_checks']
        previous=run_study(before)
        self.assertNotIn('observation_report',previous)
        comparison=compare_studies(previous,report)
        self.assertIn('OBSERVATION_CHECKS_CHANGED',[row['code'] for row in comparison['context_changes']])

    def test_cli_success_failure_and_output_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'report.json'
            output=root/'checks.json'
            source.write_text(json.dumps(run_study(self.spec)))
            command=[sys.executable,'-m','manufacturing_os.cli','observations',str(source),'--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            original=output.read_text()
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(original,output.read_text())
            self.reference['metrics']['good_by_horizon']['value']=0
            self.capture_reference()
            source.write_text(json.dumps(run_study(self.spec)))
            self.assertEqual(subprocess.run(command[:-2],cwd=ROOT,capture_output=True).returncode,1)
