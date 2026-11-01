import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from manufacturing_os.bundle import build_bundle,verify_bundle
from manufacturing_os.jsonio import loads,read_json
from manufacturing_os.notes import add_note
from manufacturing_os.study import run_study

ROOT=Path(__file__).resolve().parents[1]


class StrictJSONTests(unittest.TestCase):
    def test_duplicate_keys_rejected_at_every_nesting_level(self):
        for raw in ['{"a":1,"a":1}','{"outer":{"x":1,"x":2}}','[{"unit":"h","unit":"min"}]']:
            with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,'duplicate JSON key'):
                loads(raw)

    def test_nonfinite_tokens_and_float_overflow_rejected(self):
        for value in ['NaN','Infinity','-Infinity','1e400','-1e400']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                loads('{"value":'+value+'}')
        self.assertEqual(loads('{"label":"NaN","value":1.5}'),{'label':'NaN','value':1.5})

    def test_utf8_unicode_and_optional_bom(self):
        source='{"unit":"µm","value":2.5}'
        expected={'unit':'µm','value':2.5}
        self.assertEqual(loads(source),expected)
        self.assertEqual(loads(source.encode()),expected)
        self.assertEqual(loads(b'\xef\xbb\xbf'+source.encode()),expected)
        with self.assertRaises(ValueError):
            loads(source.encode('utf-16'))

    def test_text_and_file_byte_limits(self):
        self.assertEqual(loads(b'{}',max_bytes=2),{})
        with self.assertRaisesRegex(ValueError,'byte limit'):
            loads(b'{}',max_bytes=1)
        for limit in [0,-1,True,1.5]:
            with self.assertRaises(ValueError):
                loads('{}',max_bytes=limit)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.json'
            path.write_bytes(b'{}')
            self.assertEqual(read_json(path,max_bytes=2),{})
            with self.assertRaisesRegex(ValueError,'byte limit'):
                read_json(path,max_bytes=1)

    def test_nonregular_inputs_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'regular file'):
                read_json(directory)
            if os.name=='posix':
                fifo=Path(directory)/'fifo.json'
                os.mkfifo(fifo)
                with self.assertRaisesRegex(ValueError,'regular file'):
                    read_json(fifo)

    def test_changed_file_detected_using_open_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.json'
            path.write_text('{}')
            original=os.fstat
            changed=False
            def fstat_and_change(descriptor):
                nonlocal changed
                info=original(descriptor)
                if not changed:
                    with path.open('a') as file:
                        file.write(' ')
                    changed=True
                return info
            with patch('manufacturing_os.jsonio.os.fstat',side_effect=fstat_and_change):
                with self.assertRaisesRegex(ValueError,'changed during read'):
                    read_json(path)

    @unittest.skipUnless(os.name=='posix','symlink fixture needs POSIX')
    def test_explicitly_selected_regular_symlink_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'target.json'
            target.write_text('{"selected":true}')
            link=Path(directory)/'selected.json'
            link.symlink_to(target)
            self.assertEqual(read_json(link),{'selected':True})

    def test_nested_shapes_and_normal_float_behavior_preserved(self):
        value={'nested':[None,True,False,0,-1,1e-20,{'label':'quoted " text','units':'USD/h'}]}
        encoded=json.dumps(value)
        self.assertEqual(loads(encoded),json.loads(encoded))
        self.assertEqual(loads(encoded.encode()),value)
        self.assertIsInstance(loads('['*128+'0'+']'*128),list)
        with self.assertRaisesRegex(ValueError,'128 container levels'):
            loads('['*129+'0'+']'*129)

    def test_invalid_payload_types_and_malformed_text(self):
        for index,value in enumerate([None,{},[],b'{',b'\xff','{unquoted:1}','['*2000+'0'+']'*2000]):
            with self.subTest(case=index),self.assertRaises(ValueError):
                loads(value)

    def test_cli_config_routes_reject_identical_duplicate_fields(self):
        definitions=[
            ('plan','synthetic-cnc.json'),('estimate','serial-route.json'),
            ('experiment','uncertainty-experiment.json'),('simulate','finite-batch.json'),
            ('study','integrated-study.json'),('evidence','evidence-input.json'),
            ('sources','source-input.json'),('capture','source-input.json'),
            ('replicate','replication-experiment.json'),('campaign','scenario-campaign.json'),
            ('bundle','integrated-study.json'),('campaign-bundle','scenario-campaign.json')]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for command,fixture in definitions:
                path=root/(command+'.json')
                data=json.loads((ROOT/'examples'/fixture).read_text())
                path.write_text('{"schema_version":"1.0",'+json.dumps(data)[1:])
                args=[command]
                if command=='experiment':args+=['simulate']
                if command in ['bundle','campaign-bundle']:args+=['create']
                args+=[str(path)]
                if command=='evidence':args+=[str(ROOT/'examples/evidence-policy.json')]
                if command=='sources':args+=[str(ROOT/'examples/source-snapshot.json')]
                if command=='capture':args+=[str(ROOT/'examples/capture-manifest.json'),'--root',str(ROOT/'examples/source-files')]
                if command in ['study','bundle','campaign-bundle','capture']:args+=['--output',str(root/(command+'.output'))]
                if command=='plan':args+=['--output-dir',str(root/'plan-output')]
                with self.subTest(command=command):
                    result=subprocess.run([sys.executable,'-m','manufacturing_os.cli',*args],cwd=ROOT,capture_output=True,text=True)
                    self.assertEqual(result.returncode,2,result.stderr)
                    self.assertIn('duplicate JSON key',result.stderr)
                    self.assertFalse((root/(command+'.output')).exists())

    def test_cli_report_routes_reject_duplicates_before_reconstruction(self):
        spec=json.loads((ROOT/'examples/observation-study.json').read_text())
        spec['uncertainty']['samples']=1
        report=run_study(spec)
        note=add_note(report,{'note_id':'test','reviewer':'Synthetic reviewer','role':'quality','timestamp':'2026-11-01T00:00:00Z',
                             'disposition':'COMMENT','comment':'Synthetic annotation','finding_code':None})
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            valid=root/'valid.json'
            invalid=root/'duplicate.json'
            notes=root/'notes.json'
            valid.write_text(json.dumps(report))
            invalid.write_text('{"schema_version":"1.0",'+json.dumps(report)[1:])
            notes.write_text(json.dumps(note))
            commands=[['review',str(invalid),'--output',str(root/'review.html')],
                      ['compare',str(invalid),str(valid)],['observations',str(invalid)],
                      ['notes','check',str(invalid),str(notes)]]
            for args in commands:
                with self.subTest(command=args[0]):
                    result=subprocess.run([sys.executable,'-m','manufacturing_os.cli',*args],cwd=ROOT,capture_output=True,text=True)
                    self.assertEqual(result.returncode,2,result.stderr)
                    self.assertIn('duplicate JSON key',result.stderr)
            self.assertFalse((root/'review.html').exists())

    def test_archive_input_parser_rejects_duplicates(self):
        spec=json.loads((ROOT/'examples/integrated-study.json').read_text())
        spec['uncertainty']['samples']=1
        data=build_bundle(spec)
        target=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as source,zipfile.ZipFile(target,'w') as output:
            for name in source.namelist():
                content=source.read(name)
                if name=='study-input.json':
                    content=b'{"schema_version":"1.0",'+content[1:]
                output.writestr(name,content)
        with self.assertRaisesRegex(ValueError,'duplicate JSON key'):
            verify_bundle(target.getvalue())
