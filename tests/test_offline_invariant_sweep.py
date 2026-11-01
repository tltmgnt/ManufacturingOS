"""Domain invariants detect broken conservation, accounting and seeded replay."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from examples.offline_invariant_sweep import check_invariants, run_sweep, sweep_cases
from manufacturing_os.simulation import simulate_batch


def reports(spec=None):
    if spec is None:
        spec = next(spec for _, spec in sweep_cases() if spec["seed"] == 42 and spec["batch_size"] == 3 and spec["scenario"]["operations"][1]["yield_fraction"] == 1 and spec["scenario"]["operations"][1]["machines"] == 1)
    report = simulate_batch(spec)
    extended_spec = deepcopy(spec)
    extended_spec["scenario"]["horizon"] = {"value": max(5, report["batch_completion_time"]["value"]) + 1, "unit": "h"}
    return report, simulate_batch(spec), simulate_batch(extended_spec)


class OfflineInvariantSweepTests(unittest.TestCase):
    def test_grid_is_bounded_unique_and_contains_both_machine_counts(self):
        definitions = list(sweep_cases())
        self.assertEqual(len(definitions), 54)
        self.assertEqual(len({name for name, _ in definitions}), 54)
        self.assertEqual({spec["scenario"]["operations"][1]["machines"] for _, spec in definitions}, {1, 2})
        self.assertTrue(all(0 < spec["scenario"]["operations"][1]["yield_fraction"] <= 1 for _, spec in definitions))

    def test_all_generated_cases_preserve_invariants_including_zero_good_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "sweep"
            result = run_sweep(output)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["simulation_count"], 162)
            self.assertTrue(any(row["zero_good_output"] for row in result["cases"]))
            self.assertTrue(any(not row["target_met"] for row in result["cases"]))
            saved = (output / "invariant-scorecard.json").read_bytes()
            with self.assertRaises(FileExistsError):
                run_sweep(output)
            self.assertEqual((output / "invariant-scorecard.json").read_bytes(), saved)

    def test_broken_count_conservation_is_detected(self):
        report, replay, extended = reports()
        report["wip_at_horizon"] += 1
        self.assertIn("Horizon counts do not reconcile to released starts", check_invariants(report, replay, extended))

    def test_wrong_cost_and_wrong_defined_unit_cost_are_detected(self):
        report, replay, extended = reports()
        report["cost_report"]["total_cost"]["value"] += 1
        issues = check_invariants(report, replay, extended)
        self.assertIn("Full-batch costs do not reconcile", issues)
        self.assertIn("Defined unit cost does not reconcile to total cost and final good output", issues)

    def test_replay_and_horizon_dependent_cost_changes_are_detected(self):
        report, replay, extended = reports()
        replay["target_met"] = not replay["target_met"]
        extended["cost_report"]["total_cost"]["value"] += 1
        issues = check_invariants(report, replay, extended)
        self.assertIn("Same-input replay changed the retained report", issues)
        self.assertIn("Extending the reporting horizon changed full-batch output: cost_report", issues)

    def test_non_extended_horizon_cannot_pass_as_an_extension(self):
        report, replay, extended = reports()
        extended["horizon"] = deepcopy(report["horizon"])
        self.assertIn("Extended horizon must exceed both the original horizon and batch completion", check_invariants(report, replay, extended))


    def test_zero_good_output_cannot_be_represented_as_zero_unit_cost(self):
        _, spec = next(sweep_cases())
        report, replay, extended = reports(spec)
        self.assertEqual(report["eventual_good_units"], 0)
        report["cost_report"]["unit_cost"] = {"value": 0, "unit": "USD/good_piece"}
        self.assertIn("Zero-good output must retain undefined unit cost with a diagnostic", check_invariants(report, replay, extended))
