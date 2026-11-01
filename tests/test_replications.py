from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from manufacturing_os.bundle import build_bundle,verify_bundle
from manufacturing_os.compare import compare_studies
from manufacturing_os.models import digest
from manufacturing_os.replications import replay_replication,run_replications
from manufacturing_os.review import render_review
from manufacturing_os.study import run_study

ROOT=Path(__file__).resolve().parents[1]


class ReplicationTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/replication-experiment.json').read_text())
        self.spec['runs']=4

    def test_seeded_reproducibility_and_input_immutability(self):
        original=deepcopy(self.spec)
        first=run_replications(self.spec)
        self.assertEqual(first,run_replications(self.spec))
        self.assertEqual(original,self.spec)
        self.assertEqual([row['seed'] for row in first['outcomes']],[42,43,44,45])
        self.assertFalse(first['production_authorized'])

    def test_replay_recovers_full_report_and_consistency_hash(self):
        result=run_replications(self.spec)
        for row in result['outcomes']:
            replay=replay_replication(self.spec,row['run_index'])
            self.assertEqual(row['simulation_report_hash'],digest(replay))
            self.assertEqual(row['simulation_input_fingerprint'],replay['input_fingerprint'])
            self.assertEqual(row['metrics']['good_by_horizon']['value'],replay['good_by_horizon'])
            self.assertEqual(replay['good_by_horizon']+replay['scrapped_by_horizon']+replay['wip_at_horizon'],100)

    def test_summaries_reconstruct_and_target_counts_match(self):
        report=run_replications(self.spec)
        self.assertEqual(report['target_met_runs'],sum(row['target_met'] for row in report['outcomes']))
        self.assertEqual(report['target_met_runs']+report['target_missed_runs'],4)
        for key,summary in report['summary'].items():
            values=[row['metrics'][key]['value'] for row in report['outcomes'] if row['metrics'][key] is not None]
            self.assertEqual(summary['defined_runs'],len(values))
            self.assertEqual(summary['undefined_runs'],4-len(values))
            if values:
                self.assertAlmostEqual(summary['statistics']['mean']['value'],sum(values)/len(values))
                self.assertEqual(summary['statistics']['min']['value'],min(values))
                self.assertEqual(summary['statistics']['max']['value'],max(values))

    def test_perfect_yield_runs_have_equal_metrics(self):
        self.spec['simulation'].pop('downtime')
        for op in self.spec['simulation']['scenario']['operations']:
            op['yield_fraction']=1
        rows=run_replications(self.spec)['outcomes']
        self.assertTrue(all(row['metrics']==rows[0]['metrics'] for row in rows))

    def test_no_good_output_preserves_undefined_unit_cost(self):
        self.spec['simulation']['scenario']['operations'][0]['yield_fraction']=1e-20
        report=run_replications(self.spec)
        summary=report['summary']['full_batch_unit_cost']
        self.assertEqual(summary['defined_runs'],0)
        self.assertEqual(summary['undefined_runs'],4)
        self.assertIsNone(summary['statistics'])
        self.assertIsNotNone(summary['issue'])
        self.assertTrue(all(row['metrics']['full_batch_unit_cost'] is None for row in report['outcomes']))

    def test_cost_metrics_are_absent_when_disabled(self):
        self.spec['simulation']['include_costs']=False
        report=run_replications(self.spec)
        self.assertNotIn('full_batch_unit_cost',report['summary'])
        self.assertNotIn('full_batch_total_cost',report['summary'])

    def test_seed_wrap_and_single_run_quantiles(self):
        self.spec['simulation']['seed']=2**32-1
        self.spec['runs']=3
        self.assertEqual([row['seed'] for row in run_replications(self.spec)['outcomes']],[2**32-1,0,1])
        self.spec['runs']=1
        summary=run_replications(self.spec)['summary']['good_by_horizon']['statistics']
        self.assertEqual(summary['min'],summary['p05'])
        self.assertEqual(summary['p05'],summary['p95'])

    def test_invalid_run_counts_seeds_and_replay_indexes(self):
        for value in [0,1001,True,1.5]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                run_replications({**self.spec,'runs':value})
        for value in [-1,2**32,True]:
            spec=deepcopy(self.spec)
            spec['simulation']['seed']=value
            with self.assertRaises(ValueError):
                run_replications(spec)
        for value in [-1,4,True]:
            with self.assertRaises(ValueError):
                replay_replication(self.spec,value)

    def test_aggregate_work_limits_before_simulating(self):
        with patch('manufacturing_os.replications.MAX_WORK',1):
            with self.assertRaisesRegex(ValueError,'aggregate scheduling'):
                run_replications(self.spec)
        spec=deepcopy(self.spec)
        spec['runs']=1000
        spec['simulation']['batch_size']=10000
        with self.assertRaises(ValueError):
            run_replications(spec)

    def test_study_html_bundle_and_comparison_integration(self):
        spec=json.loads((ROOT/'examples/replication-study.json').read_text())
        spec['uncertainty']['samples']=2
        spec['replications']['runs']=3
        after=run_study(spec)
        self.assertIn('REPLICATION_SCOPE',[row['code'] for row in after['findings']])
        self.assertIn('Seeded finite-batch replications',render_review(after))
        self.assertEqual(verify_bundle(build_bundle(spec))['review_state'],after['review_state'])
        del spec['replications']
        before=run_study(spec)
        self.assertNotIn('replication_report',before)
        comparison=compare_studies(before,after)
        self.assertIn('REPLICATION_CONFIG_CHANGED',[row['code'] for row in comparison['context_changes']])

    def test_study_replications_share_exact_template(self):
        spec=json.loads((ROOT/'examples/replication-study.json').read_text())
        spec['uncertainty']['samples']=1
        spec['replications']['runs']=1
        report=run_study(spec)
        replay=replay_replication(report['replication_report']['input'],0)
        self.assertEqual(replay,report['simulation'])
        self.assertEqual(report,run_study(report['input']))

    def test_cli_output_replay_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'experiment.json'
            source.write_text(json.dumps(self.spec))
            output=root/'report.json'
            command=[sys.executable,'-m','manufacturing_os.cli','replicate',str(source),'--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            saved=output.read_text()
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,2)
            self.assertEqual(saved,output.read_text())
            replay=subprocess.run(command[:-2]+['--replay','0'],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(replay.returncode,0,replay.stderr)
            self.assertIn('operations',json.loads(replay.stdout))
