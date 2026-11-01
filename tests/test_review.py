from copy import deepcopy
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manufacturing_os.review import render_review
from manufacturing_os.study import binding, run_study

ROOT=Path(__file__).resolve().parents[1]


class ParsedHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags=[]
        self.attributes=[]
        self.values=[]
        self.identifiers=[]
        self.links=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)
        values=dict(attrs)
        if 'id' in values:
            self.identifiers.append(values['id'])
        if tag=='a':
            self.links.append(values.get('href',''))
    def handle_data(self,data):
        self.values.append(data)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/integrated-study.json').read_text())
        self.spec['uncertainty']['samples']=3

    def test_readable_values_units_and_references(self):
        output=render_review(run_study(self.spec))
        parsed=ParsedHTML()
        parsed.feed(output)
        content=' '.join(parsed.values)
        for label in ['HUMAN_REVIEW','USD/good_piece','815','72','Synthetic arithmetic only',
                      '12 / 12', 'WIP at horizon']:
            self.assertIn(label,content)
        self.assertIn('Production authorization: FALSE',content)
        self.assertIn('not confidence intervals',content)
        self.assertTrue(all(link.startswith('#') and link[1:] in parsed.identifiers for link in parsed.links))
        self.assertEqual(len(parsed.identifiers),len(set(parsed.identifiers)))
        self.assertNotIn('script',parsed.tags)
        self.assertNotIn('form',parsed.tags)
        self.assertNotIn('iframe',parsed.tags)

    def test_blocking_findings_precede_review_findings(self):
        self.spec['simulation']['batch_size']=1
        output=render_review(run_study(self.spec))
        self.assertIn('REVISION_REQUIRED',output)
        self.assertLess(output.index('BLOCKING: SIMULATED_TARGET_MISS'),output.index('REVIEW: UNVALIDATED_MODELS'))

    def test_altered_report_rejected(self):
        report=run_study(self.spec)
        for mutate in [lambda r:r.update(production_authorized=True),
                       lambda r:r['estimate']['unit_cost'].update(value=0),
                       lambda r:r['simulation'].update(good_by_horizon=1000),
                       lambda r:r.update(study_version='unknown')]:
            changed=deepcopy(report)
            mutate(changed)
            with self.assertRaisesRegex(ValueError,'differs from reconstruction'):
                render_review(changed)

    def test_stale_embedded_input_rejected(self):
        report=run_study(self.spec)
        report['input']['manufacturing_input']['design_revision']='B'
        with self.assertRaisesRegex(ValueError,'stale study binding'):
            render_review(report)

    def test_hostile_strings_remain_inert_text(self):
        payload='<script>alert("x")</script><img src=x onerror="alert(1)"> & "quoted"'
        self.spec['study_id']=payload
        self.spec['scenario']['source_reference']='javascript:alert(1)'+payload
        self.spec['manufacturing_input']['product_id']=payload
        self.spec['reference_suite']=None
        self.spec['binding']=binding(self.spec['manufacturing_input'],self.spec['scenario'])
        output=render_review(run_study(self.spec))
        self.assertIn(escape(payload,quote=True),output)
        parsed=ParsedHTML()
        parsed.feed(output)
        self.assertNotIn('script',parsed.tags)
        self.assertNotIn('img',parsed.tags)
        self.assertFalse(any(name.startswith('on') for name,value in parsed.attributes))
        self.assertTrue(all(link.startswith('#') for link in parsed.links))
        self.assertIn(payload,' '.join(parsed.values))

    def test_missing_references_evidence_and_ranges(self):
        self.spec['reference_suite']=None
        self.spec['uncertainty']['ranges']=[]
        output=render_review(run_study(self.spec))
        self.assertIn('No reference suite supplied.',output)
        self.assertIn('No input evidence records supplied.',output)

    def test_report_json_roundtrip_and_no_mutation(self):
        report=run_study(self.spec)
        before=deepcopy(report)
        self.assertEqual(render_review(report),render_review(json.loads(json.dumps(report))))
        self.assertEqual(before,report)

    def test_export_cli_refuses_overwrite_and_bad_report(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'report.json'
            output=Path(directory)/'review.html'
            source.write_text(json.dumps(run_study(self.spec)))
            command=[sys.executable,'-m','manufacturing_os.review',str(source),'--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            original=output.read_text()
            self.assertTrue(original.startswith('<!doctype html>'))
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertEqual(original,output.read_text())
            bad=Path(directory)/'bad.html'
            source.write_text('{}')
            command[-1]=str(bad)
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertFalse(bad.exists())
