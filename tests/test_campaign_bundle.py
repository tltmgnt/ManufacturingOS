from copy import deepcopy
from html import escape
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from manufacturing_os.bundle import build_bundle,verify_bundle
from manufacturing_os.campaign import run_campaign
from manufacturing_os.campaign_bundle import build_campaign_bundle,verify_campaign_bundle
from manufacturing_os.campaign_review import render_campaign_review

ROOT=Path(__file__).resolve().parents[1]


def unpack(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name:archive.read(name) for name in archive.namelist()}


def repack(files,mode=None):
    target=io.BytesIO()
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():
            info=zipfile.ZipInfo(name)
            info.create_system=3
            info.external_attr=((mode if mode is not None else stat.S_IFREG)|0o644)<<16
            archive.writestr(info,data)
    return target.getvalue()


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
        self.tags=[]
        self.attributes=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)
        if tag=='a':
            self.links.append(dict(attrs)['href'])


class CampaignBundleTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/scenario-campaign.json').read_text())

    def test_bundle_roundtrip_preserves_blocked_studies(self):
        data=build_campaign_bundle(self.spec)
        result=verify_campaign_bundle(data)
        self.assertEqual(result['status'],'VERIFIED_CONTENT')
        self.assertEqual(result['campaign_status'],'PASS')
        self.assertEqual(result['revision_required_studies'],3)
        self.assertFalse(result['production_authorized'])
        files=unpack(data)
        self.assertIn('cases/004/study-review.html',files)
        self.assertIn(b'REVISION_REQUIRED',files['cases/004/study-review.html'])

    def test_every_html_link_resolves_to_an_archive_file(self):
        files=unpack(build_campaign_bundle(self.spec))
        parser=HTMLLinks()
        parser.feed(files['campaign-review.html'].decode())
        self.assertEqual(len(parser.links),8)
        self.assertTrue(all(link in files for link in parser.links))
        self.assertNotIn('script',parser.tags)
        self.assertNotIn('form',parser.tags)
        self.assertTrue(all(not link.startswith(('http:','https:','file:','/')) for link in parser.links))

    def test_untrusted_case_labels_are_inert_and_never_file_paths(self):
        payload='<script>alert(1)</script>../../escape'
        self.spec['cases'][0]['case_id']=payload
        files=unpack(build_campaign_bundle(self.spec))
        html=files['campaign-review.html'].decode()
        self.assertIn(escape(payload,quote=True),html)
        self.assertNotIn(payload,html)
        self.assertTrue(all('..' not in path and '<' not in path for path in files))
        self.assertIn('cases/001/study-review.html',files)

    def test_child_errors_remain_visible_and_do_not_fabricate_study(self):
        del self.spec['cases'][0]['study']['scenario']
        files=unpack(build_campaign_bundle(self.spec))
        self.assertIn('cases/001/error.json',files)
        self.assertNotIn('cases/001/study-report.json',files)
        result=verify_campaign_bundle(repack(files))
        self.assertEqual(result['campaign_status'],'FAIL')
        self.assertEqual(result['execution_errors'],1)
        self.assertIn(b'Execution error',files['campaign-review.html'])

    def test_report_tampering_is_rejected_by_renderer(self):
        report=run_campaign(self.spec)
        report['revision_required_studies']=0
        with self.assertRaisesRegex(ValueError,'differs from reconstruction'):
            render_campaign_review(report)

    def test_content_tampering_is_rejected(self):
        original=unpack(build_campaign_bundle(self.spec))
        for name in ['campaign-review.html','campaign-report.json','manifest.json','cases/001/study-review.html']:
            files=deepcopy(original)
            files[name]+=b'changed'
            with self.subTest(name=name),self.assertRaises(ValueError):
                verify_campaign_bundle(repack(files))

    def test_duplicate_unexpected_and_missing_paths_rejected(self):
        data=build_campaign_bundle(self.spec)
        files=unpack(data)
        for path in ['../outside','/absolute','cases/001/../../escape','unlisted.txt']:
            with self.subTest(path=path),self.assertRaises(ValueError):
                verify_campaign_bundle(repack({**files,path:b'extra'}))
        missing=deepcopy(files)
        del missing['cases/001/study-review.html']
        with self.assertRaisesRegex(ValueError,'file set differs'):
            verify_campaign_bundle(repack(missing))
        output=io.BytesIO(data)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(output,'a') as archive:
                archive.writestr('README.txt',b'duplicate')
        with self.assertRaisesRegex(ValueError,'duplicate'):
            verify_campaign_bundle(output.getvalue())

    def test_special_file_metadata_is_rejected_in_both_bundle_types(self):
        files=unpack(build_campaign_bundle(self.spec))
        study=json.loads((ROOT/'examples/integrated-study.json').read_text())
        study['uncertainty']['samples']=1
        study_files=unpack(build_bundle(study))
        for mode in [stat.S_IFLNK,stat.S_IFIFO,stat.S_IFCHR,stat.S_IFSOCK]:
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                verify_campaign_bundle(repack(files,mode))
            with self.assertRaises(ValueError):
                verify_bundle(repack(study_files,mode))

    def test_size_limits_and_invalid_archives(self):
        data=build_campaign_bundle(self.spec)
        with patch('manufacturing_os.campaign_bundle.MAX_ARCHIVE_BYTES',1):
            with self.assertRaises(ValueError):
                verify_campaign_bundle(data)
        with patch('manufacturing_os.campaign_bundle.MAX_CONTENT_BYTES',1):
            with self.assertRaises(ValueError):
                build_campaign_bundle(self.spec)
            with self.assertRaises(ValueError):
                verify_campaign_bundle(data)
        with self.assertRaises(zipfile.BadZipFile):
            verify_campaign_bundle(b'not a zip')

    def test_reproducible_zip_and_immutable_input(self):
        original=deepcopy(self.spec)
        first=build_campaign_bundle(self.spec)
        self.assertEqual(first,build_campaign_bundle(self.spec))
        self.assertEqual(original,self.spec)
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertTrue(all(entry.date_time==(1980,1,1,0,0,0) for entry in archive.infolist()))

    def test_manifest_hashes_match_every_content_file(self):
        import hashlib
        files=unpack(build_campaign_bundle(self.spec))
        manifest=json.loads(files['manifest.json'])
        self.assertEqual(set(manifest['files']),set(files)-{'manifest.json'})
        for name,record in manifest['files'].items():
            self.assertEqual(record['sha256'],hashlib.sha256(files[name]).hexdigest())
            self.assertEqual(record['size_bytes'],len(files[name]))

    def test_cli_preserves_output_and_keeps_campaign_status_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'campaign.zip'
            command=[sys.executable,'-m','manufacturing_os.cli','campaign-bundle','create',str(ROOT/'examples/scenario-campaign.json'),'--output',str(target)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['revision_required_studies'],3)
            original=target.read_bytes()
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(original,target.read_bytes())
            verify=[sys.executable,'-m','manufacturing_os.cli','campaign-bundle','verify',str(target)]
            result=subprocess.run(verify,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['campaign_status'],'PASS')
            target.write_bytes(b'bad')
            self.assertEqual(subprocess.run(verify,cwd=ROOT,capture_output=True).returncode,2)
