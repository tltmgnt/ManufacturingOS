import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manufacturing_os import __version__
from manufacturing_os.cli import COMMANDS

ROOT=Path(__file__).resolve().parents[1]


class UnifiedCLITests(unittest.TestCase):
    def run_cli(self,*args):
        return subprocess.run([sys.executable,'-m','manufacturing_os.cli',*map(str,args)],cwd=ROOT,capture_output=True,text=True)

    def test_version_and_top_help(self):
        self.assertEqual(self.run_cli('--version').stdout.strip(),f'manufacturing-os {__version__}')
        result=self.run_cli()
        self.assertEqual(result.returncode,0)
        for command in COMMANDS:
            self.assertIn(command,result.stdout)

    def test_every_component_help_is_forwarded(self):
        for command in COMMANDS:
            with self.subTest(command=command):
                result=self.run_cli(command,'--help')
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('usage:',result.stdout)
                self.assertNotIn('Commands:',result.stdout)

    def test_bad_command_and_bad_child_arguments(self):
        self.assertEqual(self.run_cli('unknown').returncode,2)
        self.assertEqual(self.run_cli('study','--unexpected').returncode,2)

    def test_estimate_matches_component(self):
        result=self.run_cli('estimate','examples/serial-route.json')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertAlmostEqual(json.loads(result.stdout)['total_cost']['value'],815)

    def test_plan_legacy_module_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            result=self.run_cli('plan','examples/synthetic-cnc.json','--output-dir',directory)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['verification'],'CONDITIONAL')
            legacy=subprocess.run([sys.executable,'-m','manufacturing_os','examples/synthetic-cnc.json','--output-dir',directory],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(legacy.returncode,0,legacy.stderr)

    def test_revision_required_exit_code_survives_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            spec=json.loads((ROOT/'examples/integrated-study.json').read_text())
            spec['uncertainty']['samples']=1
            spec['simulation']['batch_size']=1
            source=Path(directory)/'study.json'
            source.write_text(json.dumps(spec))
            result=self.run_cli('study',source)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertEqual(json.loads(result.stdout)['review_state'],'REVISION_REQUIRED')

    def test_bundle_subcommands_forward_options(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'bundle.zip'
            result=self.run_cli('bundle','create','examples/integrated-study.json','--output',output)
            self.assertEqual(result.returncode,0,result.stderr)
            result=self.run_cli('bundle','verify',output)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'VERIFIED_CONTENT')
