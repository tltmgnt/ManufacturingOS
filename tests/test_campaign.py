from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from manufacturing_os.campaign import run_campaign
from manufacturing_os.models import ManufacturingInput,digest
from manufacturing_os.study import binding

ROOT=Path(__file__).resolve().parents[1]


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/scenario-campaign.json').read_text())

    def test_expected_failures_can_match_without_becoming_ready(self):
        report=run_campaign(self.spec)
        self.assertEqual(report['status'],'PASS')
        self.assertEqual(report['passed_cases'],4)
        self.assertEqual(report['revision_required_studies'],3)
        self.assertEqual(report['scope'],'SOFTWARE_EXPECTATION_CHECKS')
        self.assertFalse(report['production_authorized'])
        self.assertEqual(report['approval_state'],'PENDING_HUMAN_REVIEW')
        self.assertTrue(all(case['study_report']['production_authorized'] is False for case in report['cases']))

    def test_expectation_mismatch_fails_with_actual_and_expected(self):
        self.spec['cases'][0]['expected_review_state']='REVISION_REQUIRED'
        report=run_campaign(self.spec)
        self.assertEqual(report['status'],'FAIL')
        self.assertEqual(report['passed_cases'],3)
        self.assertEqual(report['failed_cases'],1)
        self.assertEqual(report['execution_errors'],0)
        mismatch=report['cases'][0]['mismatches'][0]
        self.assertEqual(mismatch,{'field':'review_state','expected':'REVISION_REQUIRED','actual':'HUMAN_REVIEW'})

    def test_blocking_codes_must_match_exactly(self):
        self.spec['cases'][1]['expected_blocking_codes']=[]
        report=run_campaign(self.spec)
        case=report['cases'][1]
        self.assertEqual(case['status'],'FAIL')
        self.assertEqual(case['actual']['blocking_codes'],['SIMULATED_TARGET_MISS'])
        self.assertIsNone(case['actual']['observation_status'])

    def test_child_error_fails_case_and_later_cases_continue(self):
        del self.spec['cases'][0]['study']['scenario']
        report=run_campaign(self.spec)
        self.assertEqual(report['execution_errors'],1)
        self.assertEqual(report['status'],'FAIL')
        self.assertEqual(report['cases'][0]['execution_status'],'ERROR')
        self.assertIsNone(report['cases'][0]['study_report'])
        self.assertIsNotNone(report['cases'][0]['error']['message'])
        self.assertEqual(report['cases'][3]['execution_status'],'COMPLETED')
        self.assertEqual(report['cases'][3]['status'],'PASS')

    def test_invalid_campaign_structure_and_expectations(self):
        cases=[]
        for key,value in [('cases',[]),('schema_version','2'),('campaign_id','')]:
            cases.append({**deepcopy(self.spec),key:value})
        for key,value in [('expected_review_state','APPROVED'),('expected_observation_status','unknown'),
                          ('expected_blocking_codes',['same','same'])]:
            bad=deepcopy(self.spec)
            bad['cases'][0][key]=value
            cases.append(bad)
        duplicate=deepcopy(self.spec)
        duplicate['cases'][1]['case_id']=duplicate['cases'][0]['case_id']
        cases.append(duplicate)
        for index,case in enumerate(cases):
            with self.subTest(case=index),self.assertRaises(ValueError):
                run_campaign(case)

    def test_aggregate_work_rejected_before_running_children(self):
        with patch('manufacturing_os.campaign.MAX_WORK',1),patch('manufacturing_os.campaign.run_study',side_effect=AssertionError('must not execute')):
            with self.assertRaisesRegex(ValueError,'aggregate'):
                run_campaign(self.spec)
        with patch('manufacturing_os.campaign.MAX_UNCERTAINTY_SAMPLES',1):
            with self.assertRaisesRegex(ValueError,'aggregate'):
                run_campaign(self.spec)

    def test_case_and_byte_limits(self):
        with patch('manufacturing_os.campaign.MAX_CASES',1):
            with self.assertRaises(ValueError):
                run_campaign(self.spec)
        with patch('manufacturing_os.campaign.MAX_INPUT_BYTES',1):
            with self.assertRaisesRegex(ValueError,'input exceeds'):
                run_campaign(self.spec)
        with patch('manufacturing_os.campaign.MAX_REPORT_BYTES',1):
            with self.assertRaisesRegex(ValueError,'report exceeds'):
                run_campaign(self.spec)

    def test_determinism_input_immutability_and_full_reconstruction(self):
        original=deepcopy(self.spec)
        report=run_campaign(self.spec)
        self.assertEqual(original,self.spec)
        self.assertEqual(report,run_campaign(report['input']))
        for case in report['cases']:
            self.assertEqual(case['study_report_hash'],digest(case['study_report']))

    def test_study_and_reference_states_remain_visible(self):
        cases=run_campaign(self.spec)['cases']
        self.assertEqual(cases[0]['actual']['observation_status'],'PASS')
        self.assertEqual(cases[2]['actual']['observation_status'],'FAIL')
        self.assertEqual(cases[3]['actual']['observation_status'],'REFERENCE_UNAVAILABLE')
        self.assertEqual(cases[3]['study_report']['observation_report']['status'],'REFERENCE_UNAVAILABLE')

    def test_embedded_sources_do_not_trigger_file_reads(self):
        self.spec['cases']=self.spec['cases'][:1]
        study=self.spec['cases'][0]['study']
        study['manufacturing_input']['evidence'][0]['source_uri']='file:///not-a-selected-file'
        study['evidence_policy']['sources'][0]['source_uri']='file:///not-a-selected-file'
        study['evidence_snapshot']['input_fingerprint']=ManufacturingInput.from_dict(study['manufacturing_input']).fingerprint
        study['binding']=binding(study['manufacturing_input'],study['scenario'])
        with patch('builtins.open',side_effect=AssertionError('unexpected filesystem read')):
            report=run_campaign(self.spec)
        self.assertEqual(report['status'],'PASS')

    def test_child_error_can_never_be_configured_as_a_pass(self):
        self.spec['cases']=self.spec['cases'][:1]
        self.spec['cases'][0]['study']['uncertainty']['samples']=0
        self.spec['cases'][0]['expected_review_state']='REVISION_REQUIRED'
        report=run_campaign(self.spec)
        self.assertEqual(report['cases'][0]['status'],'FAIL')
        self.assertEqual(report['cases'][0]['execution_status'],'ERROR')
        self.assertEqual(report['passed_cases'],0)

    def test_cli_summary_preserves_output_and_failure_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'campaign.json'
            output=root/'report.json'
            source.write_text(json.dumps(self.spec))
            command=[sys.executable,'-m','manufacturing_os.cli','campaign',str(source),'--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['revision_required_studies'],3)
            original=output.read_bytes()
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(original,output.read_bytes())
            self.spec['cases'][0]['expected_review_state']='REVISION_REQUIRED'
            source.write_text(json.dumps(self.spec))
            result=subprocess.run(command[:-2],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'FAIL')
            source.write_text('{}')
            self.assertEqual(subprocess.run(command[:-2],cwd=ROOT,capture_output=True).returncode,2)
