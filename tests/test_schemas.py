from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from manufacturing_os.schemas import CONTRACTS,get_schema,list_schemas,validate_contract

ROOT=Path(__file__).resolve().parents[1]


class SchemaContractTests(unittest.TestCase):
    def test_discovery_and_versioned_identifiers(self):
        metadata=list_schemas()
        self.assertEqual({row['name'] for row in metadata},{'input','scenario'})
        for row in metadata:
            schema=get_schema(row['name'])
            self.assertEqual(schema['$id'],row['schema_id'])
            self.assertEqual(schema['properties']['schema_version']['const'],'1.0')
            self.assertEqual(schema['$schema'],'https://json-schema.org/draft/2020-12/schema')
            self.assertFalse(schema['additionalProperties'])

    def test_local_references_resolve_inside_each_schema(self):
        for name in CONTRACTS:
            schema=get_schema(name)
            pending=[schema]
            while pending:
                value=pending.pop()
                if isinstance(value,dict):
                    if '$ref' in value:
                        self.assertTrue(value['$ref'].startswith('#/$defs/'))
                        self.assertIn(value['$ref'].split('/')[-1],schema['$defs'])
                    pending.extend(value.values())
                elif isinstance(value,list):
                    pending.extend(value)

    def test_core_examples_validate_with_runtime(self):
        for fixture in ['synthetic-cnc.json','evidence-input.json','source-input.json']:
            result=validate_contract('input',json.loads((ROOT/'examples'/fixture).read_text()))
            self.assertEqual(result['status'],'VALID')
            self.assertFalse(result['production_authorized'])
        result=validate_contract('scenario',json.loads((ROOT/'examples/serial-route.json').read_text()))
        self.assertEqual(result['scope'],'INPUT_CONTRACT_ONLY')

    def test_returns_fresh_documents_without_mutating_assets(self):
        schema=get_schema('input')
        schema['title']='changed'
        self.assertNotEqual(get_schema('input')['title'],'changed')
        with self.assertRaises(ValueError):
            get_schema('../outside')

    def test_runtime_preserves_duplicate_id_and_reference_checks(self):
        data=json.loads((ROOT/'examples/evidence-input.json').read_text())
        duplicate=deepcopy(data)
        duplicate['bom']*=2
        with self.assertRaisesRegex(ValueError,'duplicate BOM'):
            validate_contract('input',duplicate)
        data['evidence'][0]['claim_ids']=['missing']
        with self.assertRaisesRegex(ValueError,'unknown claim'):
            validate_contract('input',data)

    def test_runtime_enforces_currency_matching(self):
        data=json.loads((ROOT/'examples/serial-route.json').read_text())
        data['operations'][0]['machine_rate']['unit']='EUR/h'
        with self.assertRaisesRegex(ValueError,'expected unit USD/h'):
            validate_contract('scenario',data)

    def test_runtime_enforces_utc_timestamps(self):
        data=json.loads((ROOT/'examples/evidence-input.json').read_text())
        data['evidence'][0]['captured_at']='2026-11-01T00:00:00'
        with self.assertRaisesRegex(ValueError,'UTC'):
            validate_contract('input',data)

    def test_integer_types_and_constraint_issue_semantics(self):
        data=json.loads((ROOT/'examples/serial-route.json').read_text())
        data['target_good_units']=1.0
        with self.assertRaises(ValueError):
            validate_contract('scenario',data)
        package=json.loads((ROOT/'examples/synthetic-cnc.json').read_text())
        package['constraints'][0]['satisfied']=True
        with self.assertRaises(ValueError):
            validate_contract('input',package)

    def test_validation_runs_no_planning_or_analysis(self):
        data=json.loads((ROOT/'examples/synthetic-cnc.json').read_text())
        data['constraints'][0]['satisfied']=False
        with patch('manufacturing_os.engine.Orchestrator.run',side_effect=AssertionError('must not plan')):
            result=validate_contract('input',data)
        self.assertEqual(result['status'],'VALID')
        self.assertFalse(result['production_authorized'])

    def test_cli_export_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'input.schema.json'
            command=[sys.executable,'-m','manufacturing_os.cli','schema','export','input','--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            original=output.read_text()
            self.assertEqual(json.loads(original),get_schema('input'))
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(original,output.read_text())

    def test_cli_runtime_validation_and_invalid_data(self):
        good=subprocess.run([sys.executable,'-m','manufacturing_os.cli','schema','validate','scenario','examples/serial-route.json'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(good.returncode,0,good.stderr)
        self.assertEqual(json.loads(good.stdout)['validator'],'AUTHORITATIVE_RUNTIME')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'invalid.json'
            path.write_text('{"schema_version":"1.0","schema_version":"1.0"}')
            result=subprocess.run([sys.executable,'-m','manufacturing_os.cli','schema','validate','input',str(path)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('duplicate JSON key',result.stderr)

    def test_cli_discovery_and_unknown_contract(self):
        result=subprocess.run([sys.executable,'-m','manufacturing_os.cli','schema','list'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(json.loads(result.stdout)),2)
        result=subprocess.run([sys.executable,'-m','manufacturing_os.cli','schema','export','unknown'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
