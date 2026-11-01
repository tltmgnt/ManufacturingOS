from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manufacturing_os.simulation import simulate_batch

ROOT = Path(__file__).resolve().parents[1]


class BatchSimulationTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT/'examples/finite-batch.json').read_text())
        self.spec['batch_size'] = 3
        scenario = self.spec['scenario']
        scenario['target_good_units'] = 3
        scenario['horizon'] = {'value': 5, 'unit': 'h'}
        for index, op in enumerate(scenario['operations']):
            op.update(cycle_time={'value': index+1, 'unit': 'h'},
                      setup_time={'value': 0, 'unit': 'h'}, machines=1,
                      availability=1, yield_fraction=1)

    def test_hand_schedule_and_horizon_boundary(self):
        result = simulate_batch(self.spec)
        self.assertEqual([row['finish_hours'] for row in result['operations'][0]['timeline']], [1,2,3])
        self.assertEqual([row['finish_hours'] for row in result['operations'][1]['timeline']], [3,5,7])
        self.assertEqual(result['good_by_horizon'], 2)
        self.assertEqual(result['wip_at_horizon'], 1)
        self.assertEqual(result['scrapped_by_horizon'], 0)
        self.assertFalse(result['target_met'])
        self.assertEqual(result['batch_completion_time']['value'], 7)
        self.assertEqual(result['operations'][1]['processing_at_horizon'], 1)
        self.assertEqual(result['operations'][1]['mean_full_batch_queue_wait']['value'], 1)
        self.assertEqual(result['operations'][0]['peak_queued_by_horizon'], 2)
        self.assertFalse(result['production_authorized'])

    def test_parallel_machines_and_tie_order(self):
        self.spec['scenario']['operations'][0]['machines'] = 2
        self.spec['scenario']['operations'][1]['machines'] = 2
        result = simulate_batch(self.spec)
        first = result['operations'][0]['timeline']
        self.assertEqual([row['machine_id'] for row in first], [0,1,0])
        self.assertEqual([row['finish_hours'] for row in first], [1,1,2])
        self.assertEqual([row['finish_hours'] for row in result['operations'][1]['timeline']], [3,3,5])
        self.assertEqual(result['good_by_horizon'], 3)
        self.assertTrue(result['target_met'])

    def test_setups_start_at_zero(self):
        for op in self.spec['scenario']['operations']:
            op['setup_time'] = {'value': 1, 'unit': 'h'}
        result = simulate_batch(self.spec)
        self.assertEqual([row['finish_hours'] for row in result['operations'][1]['timeline']], [4,6,8])
        self.assertAlmostEqual(result['operations'][0]['occupied_fraction_by_machine'][0]['value'], .8)

    def test_availability_time_stretch(self):
        self.spec['scenario']['operations'][0]['availability'] = .5
        result = simulate_batch(self.spec)
        self.assertEqual([row['finish_hours'] for row in result['operations'][0]['timeline']], [2,4,6])
        self.assertEqual([row['finish_hours'] for row in result['operations'][1]['timeline']], [4,6,8])

    def test_no_work_before_setup_finishes(self):
        self.spec['scenario']['operations'][0]['setup_time'] = {'value': 10, 'unit': 'h'}
        result = simulate_batch(self.spec)
        self.assertEqual(result['good_by_horizon'], 0)
        self.assertEqual(result['wip_at_horizon'], 3)
        self.assertEqual(result['operations'][0]['queued_at_horizon'], 3)
        self.assertEqual(result['operations'][0]['occupied_fraction_by_machine'][0]['value'], 1)
        self.assertEqual(result['operations'][1]['arrived_by_horizon'], 0)

    def test_scrap_removes_jobs_downstream(self):
        self.spec['scenario']['operations'][0]['yield_fraction'] = 1e-20
        result = simulate_batch(self.spec)
        self.assertEqual(result['eventual_good_units'], 0)
        self.assertEqual(result['scrapped_by_horizon'], 3)
        self.assertEqual(result['operations'][1]['timeline'], [])
        self.assertEqual(result['operations'][1]['mean_full_batch_queue_wait']['value'], 0)
        self.assertTrue(all(job['eventual_good_completion'] is None for job in result['jobs']))

    def test_future_scrap_is_wip_at_horizon(self):
        self.spec['scenario']['horizon'] = {'value': .5, 'unit': 'h'}
        self.spec['scenario']['operations'][0]['yield_fraction'] = 1e-20
        result = simulate_batch(self.spec)
        self.assertEqual(result['scrapped_by_horizon'], 0)
        self.assertEqual(result['wip_at_horizon'], 3)
        self.assertEqual(result['eventual_scrapped_units'], 3)
        self.assertTrue(all(job['state_at_horizon'] == 'WIP' for job in result['jobs']))

    def test_machine_nonoverlap_and_flow_conservation(self):
        spec = json.loads((ROOT/'examples/finite-batch.json').read_text())
        result = simulate_batch(spec)
        self.assertEqual(result['batch_size'], result['good_by_horizon']+result['scrapped_by_horizon']+result['wip_at_horizon'])
        self.assertEqual(result['batch_size'], result['eventual_good_units']+result['eventual_scrapped_units'])
        for op in result['operations']:
            prior = {}
            for row in op['timeline']:
                self.assertGreaterEqual(row['start_hours'], row['arrival_hours'])
                self.assertGreaterEqual(row['start_hours'], prior.get(row['machine_id'],0))
                self.assertGreater(row['finish_hours'], row['start_hours'])
                prior[row['machine_id']] = row['finish_hours']
            for utilization in op['occupied_fraction_by_machine']:
                self.assertGreaterEqual(utilization['value'],0)
                self.assertLessEqual(utilization['value'],1+1e-12)
        for first, second in zip(result['operations'],result['operations'][1:]):
            passed = {row['job_id']: row['finish_hours'] for row in first['timeline'] if row['quality_pass']}
            self.assertEqual(passed,{row['job_id']:row['arrival_hours'] for row in second['timeline']})

    def test_reproducibility_immutability_and_audit_reconstruction(self):
        before=deepcopy(self.spec)
        report=simulate_batch(self.spec)
        self.assertEqual(before,self.spec)
        self.assertEqual(report,simulate_batch(report['input']))
        changed=deepcopy(self.spec)
        changed['seed'] += 1
        self.assertNotEqual(report['input_fingerprint'],simulate_batch(changed)['input_fingerprint'])

    def test_time_units_equivalent(self):
        other=deepcopy(self.spec)
        other['scenario']['operations'][0]['cycle_time']={'value':60,'unit':'min'}
        self.assertEqual(simulate_batch(self.spec)['operations'],simulate_batch(other)['operations'])

    def test_invalid_input_and_resource_limits(self):
        cases=[]
        for key,value in [('batch_size',0),('batch_size',True),('batch_size',10001),('seed',-1),('seed',True),('schema_version','2')]:
            cases.append({**deepcopy(self.spec),key:value})
        bad=deepcopy(self.spec)
        bad['scenario']['operations'][0]['machines']=10001
        cases.append(bad)
        bad=deepcopy(self.spec)
        bad['batch_size']=10000
        bad['scenario']['operations']=[{**deepcopy(bad['scenario']['operations'][0]),'operation_id':str(i)} for i in range(11)]
        cases.append(bad)
        for index,case in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                simulate_batch(case)

    def test_cli_output_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'report.json'
            command=[sys.executable,'-m','manufacturing_os.simulation','examples/finite-batch.json','--output',str(output)]
            first=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            original=output.read_text()
            self.assertEqual(json.loads(original)['batch_size'],100)
            second=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(second.returncode,2)
            self.assertEqual(original,output.read_text())
