import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from manufacturing_os.capture import capture_sources
from manufacturing_os.sources import verify_sources

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name=='posix','secure source capture requires POSIX')
class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'examples/source-input.json').read_text())
        self.manifest=json.loads((ROOT/'examples/capture-manifest.json').read_text())
        self.raw=(ROOT/'examples/source-files/drawing.txt').read_bytes()

    def test_capture_matches_existing_snapshot_and_hash(self):
        result=capture_sources(self.data,self.manifest,ROOT/'examples/source-files')
        expected=json.loads((ROOT/'examples/source-snapshot.json').read_text())
        self.assertEqual(result,expected)
        self.assertEqual(verify_sources(self.data,result)['records'][0]['status'],'HASH_MATCHED')

    def test_nested_file_and_manifest_only_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'nested').mkdir()
            (root/'nested'/'selected.txt').write_bytes(self.raw)
            (root/'not-selected.txt').write_bytes(b'not captured')
            self.manifest['files'][0]['path']='nested/selected.txt'
            result=capture_sources(self.data,self.manifest,root)
            self.assertEqual(len(result['files']),1)
            self.assertEqual(base64.b64decode(result['files'][0]['content_base64']),self.raw)

    def test_absolute_traversal_and_noncanonical_paths_rejected(self):
        for path in ['/absolute','../escape','nested/../../escape','./drawing.txt','nested//drawing.txt','C:/file','nested\\file','.']:
            manifest=deepcopy(self.manifest)
            manifest['files'][0]['path']=path
            with self.subTest(path=path),self.assertRaises(ValueError):
                capture_sources(self.data,manifest,ROOT/'examples/source-files')

    def test_file_and_directory_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            actual=root/'real'
            actual.mkdir()
            (actual/'drawing.txt').write_bytes(self.raw)
            (root/'file-link').symlink_to(actual/'drawing.txt')
            (root/'dir-link').symlink_to(actual,target_is_directory=True)
            for path in ['file-link','dir-link/drawing.txt']:
                self.manifest['files'][0]['path']=path
                with self.subTest(path=path),self.assertRaises(OSError):
                    capture_sources(self.data,self.manifest,root)

    def test_nonregular_files_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'folder').mkdir()
            os.mkfifo(root/'pipe')
            for path in ['folder','pipe']:
                self.manifest['files'][0]['path']=path
                with self.subTest(path=path),self.assertRaisesRegex(ValueError,'regular file'):
                    capture_sources(self.data,self.manifest,root)

    def test_unknown_duplicate_ids_and_paths_rejected(self):
        unknown=deepcopy(self.manifest)
        unknown['files'][0]['evidence_id']='unknown'
        duplicate=deepcopy(self.manifest)
        duplicate['files']*=2
        for manifest in [unknown,duplicate]:
            with self.assertRaises(ValueError):
                capture_sources(self.data,manifest,ROOT/'examples/source-files')
        second=deepcopy(self.data['evidence'][0])
        second['evidence_id']='E2'
        self.data['evidence'].append(second)
        self.manifest['files'].append({'evidence_id':'E2','path':'drawing.txt'})
        with self.assertRaisesRegex(ValueError,'duplicate capture source path'):
            capture_sources(self.data,self.manifest,ROOT/'examples/source-files')

    def test_size_and_file_count_limits(self):
        with patch('manufacturing_os.capture.MAX_SOURCE_BYTES',1):
            with self.assertRaisesRegex(ValueError,'exceed'):
                capture_sources(self.data,self.manifest,ROOT/'examples/source-files')
        with patch('manufacturing_os.capture.MAX_SOURCE_FILES',0):
            with self.assertRaises(ValueError):
                capture_sources(self.data,self.manifest,ROOT/'examples/source-files')

    def test_source_change_during_read_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            path=root/'drawing.txt'
            path.write_bytes(self.raw)
            original=os.read
            changed=False
            def read_and_change(descriptor,size):
                nonlocal changed
                data=original(descriptor,size)
                if not changed:
                    with path.open('ab') as file:
                        file.write(b'changed during read')
                    changed=True
                return data
            with patch('manufacturing_os.capture.os.read',side_effect=read_and_change):
                with self.assertRaisesRegex(ValueError,'source changed during capture'):
                    capture_sources(self.data,self.manifest,root)

    def test_no_input_mutation_or_implicit_hash_update(self):
        self.data['evidence'][0]['content_hash']=None
        before=deepcopy((self.data,self.manifest))
        snapshot=capture_sources(self.data,self.manifest,ROOT/'examples/source-files')
        self.assertEqual(before,(self.data,self.manifest))
        self.assertEqual(verify_sources(self.data,snapshot)['records'][0]['status'],'MISSING_DECLARED_SHA256')
        self.assertEqual(snapshot,capture_sources(self.data,self.manifest,ROOT/'examples/source-files'))

    def test_missing_file_does_not_create_cli_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'snapshot.json'
            result=subprocess.run([sys.executable,'-m','manufacturing_os.cli','capture',str(ROOT/'examples/source-input.json'),str(ROOT/'examples/capture-manifest.json'),'--root',directory,'--output',str(output)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertFalse(output.exists())

    def test_cli_captures_preserves_output_and_returns_hash_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'drawing.txt').write_bytes(self.raw)
            source=root/'input.json'
            source.write_text(json.dumps(self.data))
            output=root/'snapshot.json'
            command=[sys.executable,'-m','manufacturing_os.cli','capture',str(source),str(ROOT/'examples/capture-manifest.json'),'--root',str(root),'--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            original=output.read_text()
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(original,output.read_text())
            (root/'drawing.txt').write_bytes(b'mismatched content')
            command[-1]=str(root/'mismatch.json')
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(result.stdout)['content_status'],'CONTENT_COVERAGE_GAPS')
            self.assertTrue((root/'mismatch.json').exists())

    def test_empty_manifest_produces_explicit_coverage_gap(self):
        self.manifest['files']=[]
        snapshot=capture_sources(self.data,self.manifest,ROOT/'examples/source-files')
        self.assertEqual(snapshot['files'],[])
        self.assertEqual(verify_sources(self.data,snapshot)['status'],'CONTENT_COVERAGE_GAPS')
