from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from manufacturing_os.calculations import Scenario, estimate, sensitivity

ROOT = Path(__file__).resolve().parents[1]


class CalculationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'examples/serial-route.json').read_text())

    def result(self, data=None):
        return estimate(Scenario.from_dict(self.data if data is None else data))

    def test_hand_calculated_reference(self):
        result = self.result()
        # 72 / (.9 * .8) = 100 starts; finish receives 90 pieces.
        # Material $500; cut (100*.05+.5)*30=$165; finish (90/12)*20=$150.
        self.assertAlmostEqual(result['route_yield']['value'], .72)
        self.assertAlmostEqual(result['expected_starts']['value'], 100)
        self.assertAlmostEqual(result['expected_scrap']['value'], 28)
        self.assertAlmostEqual(result['total_cost']['value'], 815)
        self.assertAlmostEqual(result['unit_cost']['value'], 815/72)
        self.assertEqual(result['bottleneck_operation'], 'finish')
        self.assertAlmostEqual(result['expected_good_capacity']['value'], 76.8)
        self.assertTrue(result['capacity_feasible'])
        self.assertFalse(result['production_authorized'])
        self.assertEqual(result['validation_status'], 'UNVALIDATED_ESTIMATE')

    def test_unit_conversion_equivalence(self):
        other = deepcopy(self.data)
        other['operations'][0]['cycle_time'] = {'value': 180, 'unit': 's'}
        other['operations'][1]['cycle_time'] = {'value': 1/12, 'unit': 'h'}
        self.assertEqual(self.result()['operations'], self.result(other)['operations'])

    def test_capacity_constrained_ramp(self):
        self.data['target_good_units'] = 144
        result = self.result()
        self.assertFalse(result['capacity_feasible'])
        self.assertAlmostEqual(result['expected_good_capacity']['value'], 76.8)
        self.assertAlmostEqual(result['operations'][1]['utilization']['value'], 1.875)

    def test_parallel_machine_setup_and_availability(self):
        self.data['operations'][0].update(machines=2, availability=.5)
        result = self.result()
        self.assertAlmostEqual(result['operations'][0]['required_machine_time']['value'], 6)
        self.assertAlmostEqual(result['operations'][0]['available_machine_time']['value'], 8)
        self.assertAlmostEqual(result['operations'][0]['cost']['value'], 180)

    def test_setup_exceeds_horizon(self):
        self.data['operations'][0]['setup_time'] = {'value': 9, 'unit': 'h'}
        result = self.result()
        self.assertEqual(result['expected_good_capacity']['value'], 0)
        self.assertFalse(result['capacity_feasible'])

    def test_yield_degradation_sensitivity(self):
        lower = deepcopy(self.data)
        lower['revision'] = '2'
        lower['operations'][1]['yield_fraction'] = .5
        report = sensitivity(self.data, {'lower-yield': lower})
        self.assertGreater(report['variants']['lower-yield']['unit_cost_delta']['value'], 0)
        self.assertLess(report['variants']['lower-yield']['estimate']['expected_good_capacity']['value'], report['baseline']['expected_good_capacity']['value'])
        self.assertNotEqual(report['variants']['lower-yield']['estimate']['input_fingerprint'], report['baseline']['input_fingerprint'])

    def test_zero_rates_and_perfect_yield(self):
        for op in self.data['operations']:
            op['yield_fraction'] = 1
            op['machine_rate']['value'] = 0
            op['labor_rate']['value'] = 0
        result = self.result()
        self.assertEqual(result['expected_scrap']['value'], 0)
        self.assertEqual(result['unit_cost']['value'], 5)

    def test_invalid_scenarios(self):
        cases = []
        for key in self.data:
            bad = deepcopy(self.data)
            del bad[key]
            cases.append(bad)
        for field, values in [('yield_fraction', [0, -1, 1.1, True, float('nan')]),
                              ('availability', [0, 2, '1']), ('machines', [0, 1.5, True])]:
            for value in values:
                bad = deepcopy(self.data)
                bad['operations'][0][field] = value
                cases.append(bad)
        for key, value in [('cycle_time', {'value': 0, 'unit': 'h'}),
                           ('setup_time', {'value': -1, 'unit': 'h'}),
                           ('machine_rate', {'value': 20, 'unit': 'EUR/h'}),
                           ('cycle_time', {'value': 1, 'unit': 'day'})]:
            bad = deepcopy(self.data)
            bad['operations'][0][key] = value
            cases.append(bad)
        for key, value in [('target_good_units', True), ('target_good_units', 1.5),
                           ('operations', []), ('assumptions', []), ('currency', 'usd')]:
            cases.append({**deepcopy(self.data), key: value})
        bad = deepcopy(self.data)
        bad['operations'][1]['operation_id'] = 'cut'
        cases.append(bad)
        for index, case in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                Scenario.from_dict(case)

    def test_deterministic_and_input_not_mutated(self):
        before = deepcopy(self.data)
        self.assertEqual(self.result(), self.result())
        self.assertEqual(before, self.data)

    def test_cli(self):
        run = subprocess.run([sys.executable, '-m', 'manufacturing_os.calculations', 'examples/serial-route.json'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertAlmostEqual(json.loads(run.stdout)['total_cost']['value'], 815)
