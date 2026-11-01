from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manufacturing_os.bundle import build_bundle,verify_bundle
from manufacturing_os.compare import compare_studies
from manufacturing_os.evidence import assess_evidence
from manufacturing_os.review import render_review
from manufacturing_os.study import binding,run_study

ROOT=Path(__file__).resolve().parents[1]


class EvidencePolicyTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'examples/evidence-input.json').read_text())
        self.policy=json.loads((ROOT/'examples/evidence-policy.json').read_text())
        self.spec=json.loads((ROOT/'examples/evidence-study.json').read_text())
        self.spec['uncertainty']['samples']=2

    def test_pinned_fresh_record_covers_requirement(self):
        result=assess_evidence(self.data,self.policy)
        self.assertEqual(result['status'],'METADATA_CHECKS_PASSED')
        self.assertEqual(result['eligible_coverage'],{'R1':['E1']})
        self.assertEqual(result['records'][0]['age'],{'value':17.0,'unit':'day'})
        self.assertFalse(result['production_authorized'])

    def test_age_boundary_is_inclusive(self):
        self.policy['max_age']['value']=17
        self.assertEqual(assess_evidence(self.data,self.policy)['status'],'METADATA_CHECKS_PASSED')
        self.policy['max_age']['value']=16.999
        result=assess_evidence(self.data,self.policy)
        self.assertEqual(result['status'],'COVERAGE_GAPS')
        self.assertIn('STALE_EVIDENCE',result['records'][0]['issues'])

    def test_future_capture_is_ineligible(self):
        self.data['evidence'][0]['captured_at']='2026-11-02T00:00:00Z'
        result=assess_evidence(self.data,self.policy)
        self.assertIn('FUTURE_CAPTURE_TIMESTAMP',result['records'][0]['issues'])
        self.assertEqual(result['uncovered_requirements'],['R1'])
        self.assertEqual(result['records'][0]['age']['value'],-1)

    def test_source_identity_and_revision_are_exact(self):
        for field,value,code in [('source_uri','synthetic://other','UNPINNED_SOURCE'),
                                 ('source_owner','other','SOURCE_OWNER_MISMATCH'),
                                 ('revision','B','SOURCE_REVISION_MISMATCH'),
                                 ('evidence_type','other','EVIDENCE_TYPE_MISMATCH')]:
            data=deepcopy(self.data)
            data['evidence'][0][field]=value
            result=assess_evidence(data,self.policy)
            self.assertIn(code,result['records'][0]['issues'])
            self.assertEqual(result['status'],'COVERAGE_GAPS')

    def test_declared_hash_is_format_checked_not_verified(self):
        self.policy['require_declared_sha256']=True
        self.assertIn('MISSING_DECLARED_SHA256',assess_evidence(self.data,self.policy)['records'][0]['issues'])
        self.data['evidence'][0]['content_hash']='not-a-hash'
        self.assertIn('INVALID_DECLARED_SHA256',assess_evidence(self.data,self.policy)['records'][0]['issues'])
        self.data['evidence'][0]['content_hash']='A'*64
        result=assess_evidence(self.data,self.policy)
        self.assertEqual(result['status'],'METADATA_CHECKS_PASSED')
        self.assertEqual(result['records'][0]['declared_hash_status'],'DECLARED_NOT_VERIFIED')

    def test_excluded_record_does_not_hide_eligible_coverage(self):
        bad=deepcopy(self.data['evidence'][0])
        bad.update(evidence_id='E2',revision='old')
        self.data['evidence'].append(bad)
        result=assess_evidence(self.data,self.policy)
        self.assertEqual(result['status'],'COVERED_WITH_EXCLUSIONS')
        self.assertEqual(result['eligible_coverage']['R1'],['E1'])
        self.assertEqual(result['ineligible_record_count'],1)

    def test_empty_evidence_and_partial_coverage(self):
        self.data['requirements'].append({'requirement_id':'R2','description':'Another requirement'})
        self.assertEqual(assess_evidence(self.data,self.policy)['uncovered_requirements'],['R2'])
        self.data['evidence']=[]
        self.assertEqual(assess_evidence(self.data,self.policy)['uncovered_requirements'],['R1','R2'])

    def test_invalid_policies_rejected(self):
        cases=[]
        for key,value in [('as_of','2026-11-01'),('as_of','2026-11-01T00:00:00+01:00'),
                          ('require_declared_sha256',1),('sources',[]),('schema_version','2'),
                          ('max_age',{'value':-1,'unit':'day'}),('max_age',{'value':30,'unit':'h'})]:
            cases.append({**deepcopy(self.policy),key:value})
        duplicate=deepcopy(self.policy)
        duplicate['sources']*=2
        cases.append(duplicate)
        for index,policy in enumerate(cases):
            with self.subTest(case=index),self.assertRaises(ValueError):
                assess_evidence(self.data,policy)

    def test_deterministic_and_immutable(self):
        before=deepcopy((self.data,self.policy))
        first=assess_evidence(self.data,self.policy)
        self.assertEqual(first,assess_evidence(self.data,self.policy))
        self.assertEqual(before,(self.data,self.policy))

    def test_study_gaps_require_revision_without_changing_original_plan(self):
        self.spec['evidence_policy']['max_age']['value']=1
        result=run_study(self.spec)
        self.assertEqual(result['review_state'],'REVISION_REQUIRED')
        self.assertEqual(result['plan']['verification']['status'],'CONDITIONAL')
        self.assertIn('EVIDENCE_COVERAGE_GAPS',[row['code'] for row in result['findings']])
        self.assertIn('STALE_EVIDENCE',render_review(result))
        self.assertEqual(verify_bundle(build_bundle(self.spec))['review_state'],'REVISION_REQUIRED')

    def test_opt_in_preserves_old_output_and_comparison_flags_policy(self):
        original=json.loads((ROOT/'examples/integrated-study.json').read_text())
        original['uncertainty']['samples']=2
        before=run_study(original)
        self.assertNotIn('evidence_report',before)
        after=run_study(self.spec)
        self.assertIn('EVIDENCE_POLICY_CHANGED',[item['code'] for item in compare_studies(before,after)['context_changes']])
        self.assertIn('Evidence metadata policy: METADATA_CHECKS_PASSED',render_review(after))
        self.assertFalse(after['production_authorized'])

    def test_cli_gap_exit_and_output_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'report.json'
            policy=Path(directory)/'policy.json'
            policy.write_text(json.dumps(self.policy))
            command=[sys.executable,'-m','manufacturing_os.cli','evidence',str(ROOT/'examples/evidence-input.json'),str(policy),'--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            original=output.read_text()
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(original,output.read_text())
            self.policy['max_age']['value']=1
            policy.write_text(json.dumps(self.policy))
            result=subprocess.run(command[:-2],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'COVERAGE_GAPS')
