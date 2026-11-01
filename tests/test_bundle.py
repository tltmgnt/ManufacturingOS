from copy import deepcopy
import hashlib
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

from manufacturing_os.bundle import BASE_NAMES, OPTIONAL_NAMES, build_bundle, verify_bundle
from manufacturing_os.study import run_study

ROOT=Path(__file__).resolve().parents[1]


def unpack(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name:archive.read(name) for name in archive.namelist()}


def pack(files):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():
            archive.writestr(name,data)
    return buffer.getvalue()


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/integrated-study.json').read_text())
        self.spec['uncertainty']['samples']=3

    def test_complete_bundle_roundtrip(self):
        data=build_bundle(self.spec)
        files=unpack(data)
        self.assertEqual(set(files),BASE_NAMES)
        result=verify_bundle(data)
        self.assertEqual(result['status'],'VERIFIED_CONTENT')
        self.assertFalse(result['production_authorized'])
        self.assertIn(b'Production authorization: FALSE',files['study-review.html'])
        manifest=json.loads(files['manifest.json'])
        for name,record in manifest['files'].items():
            self.assertEqual(record['sha256'],hashlib.sha256(files[name]).hexdigest())
            self.assertEqual(record['size_bytes'],len(files[name]))

    def test_bundle_with_revision_comparison(self):
        previous=run_study(self.spec)
        revised=deepcopy(self.spec)
        revised['revision']='2'
        revised['simulation']['batch_size']=110
        data=build_bundle(revised,previous)
        self.assertEqual(set(unpack(data)),BASE_NAMES|OPTIONAL_NAMES)
        self.assertEqual(verify_bundle(data)['study_revision'],'2')
        self.assertEqual(json.loads(unpack(data)['comparison.json'])['sources']['before']['study_revision'],'1')

    def test_reproducible_zip_and_immutable_input(self):
        before=deepcopy(self.spec)
        first=build_bundle(self.spec)
        self.assertEqual(first,build_bundle(self.spec))
        self.assertEqual(before,self.spec)
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertTrue(all(row.date_time==(1980,1,1,0,0,0) for row in archive.infolist()))

    def test_altered_report_rejected_even_with_updated_manifest(self):
        files=unpack(build_bundle(self.spec))
        report=json.loads(files['study-report.json'])
        report['production_authorized']=True
        files['study-report.json']=json.dumps(report).encode()
        manifest=json.loads(files['manifest.json'])
        manifest['files']['study-report.json']={'sha256':hashlib.sha256(files['study-report.json']).hexdigest(),'size_bytes':len(files['study-report.json'])}
        files['manifest.json']=json.dumps(manifest).encode()
        with self.assertRaisesRegex(ValueError,'differs from reconstruction'):
            verify_bundle(pack(files))

    def test_altered_html_and_manifest_rejected(self):
        original=unpack(build_bundle(self.spec))
        for name in ['study-review.html','manifest.json','README.txt']:
            files=deepcopy(original)
            files[name]+=b'changed'
            with self.subTest(name=name),self.assertRaises(ValueError):
                verify_bundle(pack(files))

    def test_unexpected_path_and_missing_file_rejected(self):
        files=unpack(build_bundle(self.spec))
        for name in ['../outside.txt','/absolute.txt','folder/','unlisted.txt']:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'bundle paths'):
                verify_bundle(pack({**files,name:b'extra'}))
        del files['study-report.json']
        with self.assertRaisesRegex(ValueError,'bundle paths'):
            verify_bundle(pack(files))

    def test_duplicate_paths_rejected(self):
        data=build_bundle(self.spec)
        output=io.BytesIO(data)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(output,'a') as archive:
                archive.writestr('README.txt',b'duplicate')
        with self.assertRaisesRegex(ValueError,'duplicate'):
            verify_bundle(output.getvalue())

    def test_optional_files_must_be_paired(self):
        files=unpack(build_bundle(self.spec))
        files['comparison.json']=b'{}'
        with self.assertRaisesRegex(ValueError,'occur together'):
            verify_bundle(pack(files))

    def test_symlink_rejected_without_extraction(self):
        files=unpack(build_bundle(self.spec))
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as archive:
            for name,data in files.items():
                info=zipfile.ZipInfo(name)
                info.create_system=3
                info.external_attr=(stat.S_IFLNK|0o777)<<16 if name=='README.txt' else (stat.S_IFREG|0o644)<<16
                archive.writestr(info,data)
        with self.assertRaisesRegex(ValueError,'symbolic links'):
            verify_bundle(output.getvalue())

    def test_resource_limits_and_invalid_zip(self):
        data=build_bundle(self.spec)
        with patch('manufacturing_os.bundle.MAX_ARCHIVE_BYTES',10):
            with self.assertRaisesRegex(ValueError,'compressed bundle'):
                verify_bundle(data)
        with patch('manufacturing_os.bundle.MAX_CONTENT_BYTES',10):
            with self.assertRaisesRegex(ValueError,'bundle contents'):
                verify_bundle(data)
            with self.assertRaisesRegex(ValueError,'bundle contents'):
                build_bundle(self.spec)
        with self.assertRaises(zipfile.BadZipFile):
            verify_bundle(b'invalid zip')

    def test_revision_required_study_can_be_bundled(self):
        self.spec['simulation']['batch_size']=1
        result=verify_bundle(build_bundle(self.spec))
        self.assertEqual(result['review_state'],'REVISION_REQUIRED')
        self.assertFalse(result['production_authorized'])

    def test_cli_create_verify_preserve_output_and_bad_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'study.json'
            target=Path(directory)/'bundle.zip'
            source.write_text(json.dumps(self.spec))
            create=[sys.executable,'-m','manufacturing_os.bundle','create',str(source),'--output',str(target)]
            result=subprocess.run(create,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            original=target.read_bytes()
            self.assertEqual(subprocess.run(create,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(original,target.read_bytes())
            verify=[sys.executable,'-m','manufacturing_os.bundle','verify',str(target)]
            result=subprocess.run(verify,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'VERIFIED_CONTENT')
            target.write_bytes(b'bad')
            self.assertEqual(subprocess.run(verify,cwd=ROOT,capture_output=True).returncode,2)
