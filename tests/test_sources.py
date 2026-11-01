import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from manufacturing_os.bundle import build_bundle,verify_bundle
from manufacturing_os.compare import compare_studies
from manufacturing_os.models import ManufacturingInput
from manufacturing_os.review import render_review
from manufacturing_os.sources import verify_sources
from manufacturing_os.study import binding,run_study

ROOT=Path(__file__).resolve().parents[1]


class SourceContentTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'examples/source-input.json').read_text())
        self.snapshot=json.loads((ROOT/'examples/source-snapshot.json').read_text())
        self.spec=json.loads((ROOT/'examples/source-study.json').read_text())
        self.spec['uncertainty']['samples']=2

    def rebind(self):
        self.spec['binding']=binding(self.spec['manufacturing_input'],self.spec['scenario'])
        self.spec['evidence_snapshot']['input_fingerprint']=ManufacturingInput.from_dict(self.spec['manufacturing_input']).fingerprint

    def test_captured_bytes_match_declared_hash(self):
        result=verify_sources(self.data,self.snapshot)
        self.assertEqual(result['status'],'CAPTURED_CONTENT_COVERED')
        self.assertEqual(result['records'][0]['status'],'HASH_MATCHED')
        self.assertEqual(result['hash_matched_coverage'],{'R1':['E1']})
        self.assertFalse(result['production_authorized'])

    def test_changed_bytes_and_missing_capture_fail_coverage(self):
        self.snapshot['files'][0]['content_base64']=base64.b64encode(b'changed').decode()
        self.assertEqual(verify_sources(self.data,self.snapshot)['records'][0]['status'],'HASH_MISMATCH')
        self.snapshot['files']=[]
        result=verify_sources(self.data,self.snapshot)
        self.assertEqual(result['status'],'CONTENT_COVERAGE_GAPS')
        self.assertEqual(result['records'][0]['status'],'MISSING_CAPTURED_CONTENT')

    def test_empty_content_is_valid_binary_input(self):
        self.data['evidence'][0]['content_hash']=hashlib.sha256(b'').hexdigest()
        self.snapshot['input_fingerprint']=ManufacturingInput.from_dict(self.data).fingerprint
        self.snapshot['files'][0]['content_base64']=''
        result=verify_sources(self.data,self.snapshot)
        self.assertEqual(result['records'][0]['status'],'HASH_MATCHED')
        self.assertEqual(result['captured_total_bytes'],0)

    def test_missing_invalid_and_uppercase_hashes(self):
        for value,status in [(None,'MISSING_DECLARED_SHA256'),('bad','INVALID_DECLARED_SHA256'),
                             (self.data['evidence'][0]['content_hash'].upper(),'HASH_MATCHED')]:
            data=deepcopy(self.data)
            data['evidence'][0]['content_hash']=value
            snapshot=deepcopy(self.snapshot)
            snapshot['input_fingerprint']=ManufacturingInput.from_dict(data).fingerprint
            self.assertEqual(verify_sources(data,snapshot)['records'][0]['status'],status)

    def test_invalid_base64_unknown_and_duplicate_ids_rejected(self):
        for encoded in ['not base64!','Zh==','Zg==\n']:
            snapshot=deepcopy(self.snapshot)
            snapshot['files'][0]['content_base64']=encoded
            with self.subTest(value=encoded),self.assertRaises(ValueError):
                verify_sources(self.data,snapshot)
        duplicate=deepcopy(self.snapshot)
        duplicate['files']*=2
        with self.assertRaisesRegex(ValueError,'duplicate'):
            verify_sources(self.data,duplicate)
        self.snapshot['files'][0]['evidence_id']='unknown'
        with self.assertRaisesRegex(ValueError,'unknown'):
            verify_sources(self.data,self.snapshot)

    def test_stale_input_and_resource_limits(self):
        data=deepcopy(self.data)
        data['design_revision']='B'
        with self.assertRaisesRegex(ValueError,'stale source snapshot'):
            verify_sources(data,self.snapshot)
        with patch('manufacturing_os.sources.MAX_SOURCE_BYTES',1):
            with self.assertRaises(ValueError):
                verify_sources(self.data,self.snapshot)
        with patch('manufacturing_os.sources.MAX_SOURCE_FILES',0):
            with self.assertRaises(ValueError):
                verify_sources(self.data,self.snapshot)

    def test_combined_coverage_requires_same_record(self):
        second=deepcopy(self.spec['manufacturing_input']['evidence'][0])
        second.update(evidence_id='E2',captured_at='2020-01-01T00:00:00Z')
        self.spec['manufacturing_input']['evidence'].append(second)
        captured=deepcopy(self.spec['evidence_snapshot']['files'][0])
        captured['evidence_id']='E2'
        self.spec['evidence_snapshot']['files'].append(captured)
        self.spec['evidence_snapshot']['files'][0]['content_base64']=base64.b64encode(b'tampered').decode()
        self.rebind()
        result=run_study(self.spec)
        self.assertEqual(result['evidence_report']['eligible_coverage']['R1'],['E1'])
        self.assertEqual(result['source_report']['hash_matched_coverage']['R1'],['E2'])
        self.assertEqual(result['source_report']['combined_eligible_coverage']['R1'],[])
        self.assertEqual(result['review_state'],'REVISION_REQUIRED')

    def test_html_bundle_and_comparison_integration(self):
        after=run_study(self.spec)
        self.assertEqual(after['review_state'],'HUMAN_REVIEW')
        self.assertIn('HASH_MATCHED',render_review(after))
        self.assertEqual(verify_bundle(build_bundle(self.spec))['status'],'VERIFIED_CONTENT')
        before_spec=deepcopy(self.spec)
        del before_spec['evidence_snapshot']
        before=run_study(before_spec)
        self.assertNotIn('source_report',before)
        comparison=compare_studies(before,after)
        self.assertIn('EVIDENCE_SNAPSHOT_CHANGED',[row['code'] for row in comparison['context_changes']])

    def test_source_snapshot_requires_metadata_policy(self):
        del self.spec['evidence_policy']
        with self.assertRaisesRegex(ValueError,'requires evidence_policy'):
            run_study(self.spec)

    def test_deterministic_immutable_reconstructable(self):
        original=deepcopy((self.data,self.snapshot))
        first=verify_sources(self.data,self.snapshot)
        self.assertEqual(first,verify_sources(self.data,self.snapshot))
        self.assertEqual(original,(self.data,self.snapshot))
        report=run_study(self.spec)
        self.assertEqual(report,run_study(report['input']))

    def test_hash_match_does_not_override_metadata_failure(self):
        self.spec['evidence_policy']['max_age']['value']=1
        result=run_study(self.spec)
        self.assertEqual(result['source_report']['records'][0]['status'],'HASH_MATCHED')
        self.assertEqual(result['source_report']['combined_uncovered_requirements'],['R1'])
        self.assertEqual(result['review_state'],'REVISION_REQUIRED')

    def test_cli_exit_codes_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'snapshot.json'
            output=Path(directory)/'report.json'
            source.write_text(json.dumps(self.snapshot))
            command=[sys.executable,'-m','manufacturing_os.cli','sources',str(ROOT/'examples/source-input.json'),str(source),'--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            original=output.read_text()
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(original,output.read_text())
            self.snapshot['files']=[]
            source.write_text(json.dumps(self.snapshot))
            self.assertEqual(subprocess.run(command[:-2],cwd=ROOT,capture_output=True).returncode,1)
            source.write_text('{}')
            self.assertEqual(subprocess.run(command[:-2],cwd=ROOT,capture_output=True).returncode,2)
