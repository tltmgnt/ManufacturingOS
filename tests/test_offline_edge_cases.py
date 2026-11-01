"""Hand-derived edge outcomes preserve counts, full-batch costs and undefined values."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from examples.offline_edge_cases import cases, metrics, run_edges
from manufacturing_os.simulation import simulate_batch


class OfflineEdgeCaseTests(unittest.TestCase):
    def test_all_hand_derived_cases_match_and_counts_reconcile(self):
        for name, spec, expected in cases():
            with self.subTest(case=name):
                report = simulate_batch(spec)
                self.assertEqual(metrics(report), expected)
                self.assertEqual(report["good_by_horizon"] + report["scrapped_by_horizon"] + report["wip_at_horizon"], spec["batch_size"])
                self.assertEqual(report["eventual_good_units"] + report["eventual_scrapped_units"], spec["batch_size"])
                self.assertFalse(report["production_authorized"])

    def test_seeded_zero_good_output_retains_undefined_unit_cost(self):
        for name, spec, _ in cases():
            if "scrap" in name:
                with self.subTest(case=name):
                    self.assertTrue(all(row["yield_fraction"] > 0 for row in spec["scenario"]["operations"]))
                    report = simulate_batch(spec)
                    self.assertEqual(report["eventual_good_units"], 0)
                    self.assertIsNone(report["cost_report"]["unit_cost"])
                    self.assertIn("undefined", report["cost_report"]["unit_cost_issue"])

    def test_upstream_scrap_does_not_charge_unperformed_downstream_processing(self):
        spec = next(spec for name, spec, _ in cases() if name == "seeded-upstream-scrap")
        report = simulate_batch(spec)
        self.assertEqual(report["cost_report"]["total_cost"]["value"], 105)
        self.assertEqual(report["cost_report"]["operations"][1]["processed_input"]["value"], 0)
        self.assertEqual(report["cost_report"]["operations"][1]["processing_time"]["value"], 0)

    def test_completed_target_misses_are_expected_software_outcomes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "edges"
            result = run_edges(output)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(sum(row["actual"]["target_met"] for row in result["cases"]), 1)
            self.assertTrue((output / "source-provenance.json").is_file())
            for row in result["cases"]:
                report = json.loads((output / row["case"] / "simulation-report.json").read_text())
                self.assertEqual(report, simulate_batch(report["input"]))
            saved = (output / "edge-scorecard.json").read_bytes()
            with self.assertRaises(FileExistsError):
                run_edges(output)
            self.assertEqual((output / "edge-scorecard.json").read_bytes(), saved)

    def test_wrong_expectation_is_retained_as_failure_not_false_success(self):
        definition = cases()[0]
        definition[2]["total_cost_usd"] = 999
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "edges"
            with patch("examples.offline_edge_cases.cases", return_value=[definition]):
                result = run_edges(output)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["cases"][0]["differences"], [{"metric": "total_cost_usd", "expected": 999, "actual": 225.0}])
