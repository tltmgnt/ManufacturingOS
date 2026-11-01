from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from manufacturing_os.experiments import percentile, simulate, validate_references

ROOT = Path(__file__).resolve().parents[1]


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT/'examples/uncertainty-experiment.json').read_text())
        self.suite = json.loads((ROOT/'examples/arithmetic-references.json').read_text())

    def test_reproducibility_and_immutable_input(self):
        before = deepcopy(self.spec)
        one = simulate(self.spec)
        self.assertEqual(one, simulate(self.spec))
        self.assertEqual(before, self.spec)
        changed = deepcopy(self.spec)
        changed['seed'] += 1
        self.assertNotEqual(one['samples'], simulate(changed)['samples'])
        self.assertEqual(one, simulate(one['input']))
        self.assertFalse(one['production_authorized'])

    def test_constant_ranges_match_baseline(self):
        self.spec['samples'] = 3
        self.spec['ranges'] = []
        result = simulate(self.spec)
        for metric, summary in result['summary'].items():
            for statistic, value in summary.items():
                self.assertAlmostEqual(value['value'], result['baseline'][metric]['value'])
        self.assertEqual(result['feasible_samples'], 3)
        self.assertEqual(result['bottleneck_counts'], {'finish': 3})

    def test_summary_reconstructs_from_samples(self):
        result = simulate(self.spec)
        self.assertEqual(sum(result['bottleneck_counts'].values()), 100)
        self.assertEqual(result['feasible_samples'], sum(s['capacity_feasible'] for s in result['samples']))
        for metric, summary in result['summary'].items():
            values = [s['metrics'][metric]['value'] for s in result['samples']]
            self.assertEqual(summary['p50']['value'], percentile(values, .5))
            self.assertLessEqual(summary['min']['value'], summary['p05']['value'])
            self.assertLessEqual(summary['p95']['value'], summary['max']['value'])
        for sample in result['samples']:
            for row in sample['sampled_parameters']:
                self.assertLessEqual(row['low'], row['value'])
                self.assertLessEqual(row['value'], row['high'])

    def test_range_order_does_not_change_samples(self):
        other = deepcopy(self.spec)
        other['ranges'].reverse()
        self.assertEqual(simulate(self.spec)['samples'], simulate(other)['samples'])

    def test_single_sample_quantiles(self):
        self.spec['samples'] = 1
        result = simulate(self.spec)
        for summary in result['summary'].values():
            self.assertEqual(summary['p05'], summary['p95'])

    def test_invalid_experiments(self):
        cases=[]
        for key, value in [('seed', True), ('seed', -1), ('samples', 0), ('samples', 10001), ('samples', 1.5), ('ranges', {})]:
            cases.append({**deepcopy(self.spec), key:value})
        for key, value in [('parameter','arbitrary'), ('operation_id','missing'), ('low', -1), ('high', .1), ('high', float('nan')), ('low',0), ('high',1.1)]:
            bad=deepcopy(self.spec)
            bad['ranges'][0][key]=value
            cases.append(bad)
        bad=deepcopy(self.spec)
        bad['ranges'].append(deepcopy(bad['ranges'][0]))
        cases.append(bad)
        for index, case in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                simulate(case)

    def test_reference_report_and_reconstruction(self):
        result=validate_references(self.suite)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['check_count'],12)
        self.assertEqual(result['passed_checks'],12)
        self.assertIsNone(result['reviewer'])
        self.assertFalse(result['production_authorized'])
        self.assertEqual(result,validate_references(result['input']))
        for case in result['cases']:
            for check in case['checks']:
                self.assertLessEqual(abs(check['residual']['value']),check['expected']['absolute_tolerance'])

    def test_reference_mismatch_is_failure(self):
        self.suite['cases'][0]['expected']['total_cost']['value']=800
        result=validate_references(self.suite)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['passed_checks'],11)
        check=next(c for c in result['cases'][0]['checks'] if c['metric']=='total_cost')
        self.assertAlmostEqual(check['residual']['value'],15)

    def test_invalid_reference_suites(self):
        cases=[]
        for key, value in [('cases',[]),('reference_type','real_facility')]:
            cases.append({**deepcopy(self.suite),key:value})
        for key,value in [('unit','EUR'),('absolute_tolerance',-1),('value',True)]:
            bad=deepcopy(self.suite)
            bad['cases'][0]['expected']['total_cost'][key]=value
            cases.append(bad)
        bad=deepcopy(self.suite)
        bad['cases'].append(deepcopy(bad['cases'][0]))
        cases.append(bad)
        for case in cases:
            with self.assertRaises(ValueError):
                validate_references(case)

    def test_cli_reports_exit_codes_and_no_overwrite(self):
        def run(*args):
            return subprocess.run([sys.executable,'-m','manufacturing_os.experiments',*map(str,args)],cwd=ROOT,capture_output=True,text=True)
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'report.json'
            result=run('validate','examples/arithmetic-references.json','--output',report)
            self.assertEqual(result.returncode,0,result.stderr)
            original=report.read_text()
            self.assertEqual(run('validate','examples/arithmetic-references.json','--output',report).returncode,2)
            self.assertEqual(original,report.read_text())
            self.suite['cases'][0]['expected']['total_cost']['value']=0
            fixture=Path(directory)/'bad-reference.json'
            fixture.write_text(json.dumps(self.suite))
            failed=run('validate',fixture)
            self.assertEqual(failed.returncode,1)
            self.assertEqual(json.loads(failed.stdout)['status'],'FAIL')
            self.assertEqual(run('simulate','examples/uncertainty-experiment.json').returncode,0)
