from copy import deepcopy
from html import escape
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manufacturing_os.bundle import NOTE_NAMES,build_bundle,verify_bundle
from manufacturing_os.notes import add_note,assess_notes
from manufacturing_os.review import render_review
from manufacturing_os.study import run_study

ROOT=Path(__file__).resolve().parents[1]


class ReviewNotesTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/source-study.json').read_text())
        self.spec['uncertainty']['samples']=2
        self.report=run_study(self.spec)
        self.entry={'note_id':'N1','reviewer':'Synthetic reviewer','role':'quality',
                    'timestamp':'2026-11-01T00:00:00Z','disposition':'COMMENT',
                    'comment':'Review synthetic assumptions','finding_code':'UNVALIDATED_MODELS'}

    def test_exact_report_binding_and_approval_boundary(self):
        log=add_note(self.report,self.entry)
        summary=assess_notes(self.report,log)
        self.assertEqual(summary['state'],'NOTES_RECORDED')
        self.assertEqual(summary['roles_with_notes'],['quality'])
        self.assertFalse(summary['production_authorized'])
        self.assertEqual(summary['approval_state'],'PENDING_HUMAN_REVIEW')
        self.assertEqual(len(summary['roles_without_notes']),5)

    def test_stale_study_and_report_binding_rejected(self):
        log=add_note(self.report,self.entry)
        self.spec['revision']='new'
        with self.assertRaisesRegex(ValueError,'stale review notes'):
            assess_notes(run_study(self.spec),log)
        altered=deepcopy(log)
        altered['report_content_hash']='wrong'
        with self.assertRaisesRegex(ValueError,'stale review notes'):
            assess_notes(self.report,altered)

    def test_append_preserves_prior_log_and_readiness_does_not_erase_requests(self):
        self.entry['disposition']='REQUEST_REVISION'
        first=add_note(self.report,self.entry)
        saved=deepcopy(first)
        second={**self.entry,'note_id':'N2','disposition':'READY_FOR_FORMAL_REVIEW'}
        appended=add_note(self.report,second,first)
        self.assertEqual(first,saved)
        self.assertEqual(appended['revision'],2)
        summary=assess_notes(self.report,appended)
        self.assertEqual(summary['state'],'REQUESTED_CHANGES')
        self.assertEqual(summary['requested_revision_note_ids'],['N1'])
        self.assertFalse(summary['production_authorized'])

    def test_approval_and_unknown_role_finding_rejected(self):
        for field,value in [('disposition','APPROVED'),('role','admin'),('finding_code','missing'),('finding_code',[]),('reviewer',''),('comment','x'*10001)]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                add_note(self.report,{**self.entry,field:value})

    def test_utc_chronology_and_duplicate_ids(self):
        log=add_note(self.report,self.entry)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            add_note(self.report,self.entry,log)
        for stamp in ['2026-11-01','2026-11-01T00:00:00+01:00','2026-10-31T23:00:00Z']:
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):
                add_note(self.report,{**self.entry,'note_id':'N2','timestamp':stamp},log)

    def test_review_id_cannot_change_when_appending(self):
        log=add_note(self.report,self.entry,review_id='review-1')
        with self.assertRaisesRegex(ValueError,'cannot change review_id'):
            add_note(self.report,{**self.entry,'note_id':'N2'},log,review_id='review-2')

    def test_note_and_report_inputs_are_not_mutated(self):
        before=deepcopy((self.report,self.entry))
        first=add_note(self.report,self.entry)
        self.assertEqual(before,(self.report,self.entry))
        self.assertEqual(first,add_note(self.report,self.entry))
        self.assertEqual(assess_notes(self.report,first),assess_notes(self.report,json.loads(json.dumps(first))))

    def test_note_text_is_escaped_in_html(self):
        payload='<script>alert(1)</script><img src=x onerror=alert(1)>'
        self.entry['comment']=payload
        log=add_note(self.report,self.entry)
        rendered=render_review(self.report,log)
        self.assertIn(escape(payload,quote=True),rendered)
        self.assertNotIn(payload,rendered)
        self.assertIn('Names and roles are declared, not authenticated',rendered)

    def test_optional_notes_bundle_roundtrip(self):
        self.entry["disposition"]="REQUEST_REVISION"
        log=add_note(self.report,self.entry)
        result=verify_bundle(build_bundle(self.spec,notes=log))
        self.assertTrue(NOTE_NAMES<=set(result['verified_files']))
        self.assertEqual(result['notes_state'],'REQUESTED_CHANGES')
        self.assertFalse(result['production_authorized'])
        self.assertEqual(result['review_state'],self.report['review_state'])

    def test_stale_notes_rejected_by_html_and_bundle(self):
        log=add_note(self.report,self.entry)
        log['study_fingerprint']='stale'
        with self.assertRaises(ValueError):
            render_review(self.report,log)
        with self.assertRaises(ValueError):
            build_bundle(self.spec,notes=log)

    def test_missing_paired_notes_file_rejected(self):
        import io,zipfile
        log=add_note(self.report,self.entry)
        data=build_bundle(self.spec,notes=log)
        output=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as source,zipfile.ZipFile(output,'w') as target:
            for name in source.namelist():
                if name!='review-notes-assessment.json':
                    target.writestr(name,source.read(name))
        with self.assertRaisesRegex(ValueError,'note files must occur together'):
            verify_bundle(output.getvalue())

    def test_cli_append_check_and_output_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=root/'report.json'
            report.write_text(json.dumps(self.report))
            output=root/'notes.json'
            command=[sys.executable,'-m','manufacturing_os.cli','notes','add',str(report),'--note-id','N1','--reviewer','Synthetic reviewer','--role','quality','--timestamp',self.entry['timestamp'],'--comment','Needs revision','--disposition','REQUEST_REVISION','--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            original=output.read_text()
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(original,output.read_text())
            check=[sys.executable,'-m','manufacturing_os.cli','notes','check',str(report),str(output)]
            result=subprocess.run(check,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(result.stdout)['state'],'REQUESTED_CHANGES')
