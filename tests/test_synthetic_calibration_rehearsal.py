"""Guard fitting/held-out separation and reproducible synthetic residuals."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from examples.synthetic_calibration_rehearsal import evaluate_frozen, fit_candidate, run_rehearsal
from manufacturing_os.study import run_study

ROOT = Path(__file__).resolve().parents[1] / "examples"
FITTING = (ROOT / "synthetic-fitting-records.csv").read_bytes()
HELDOUT = (ROOT / "synthetic-batch-export.csv").read_bytes()


class CalibrationRehearsalTests(unittest.TestCase):
    def test_estimator_uses_fitting_data_not_heldout_observations(self):
        frozen = fit_candidate(FITTING)
        original = deepcopy(frozen)
        _, candidate, _, _ = evaluate_frozen(frozen, HELDOUT.replace(b",7,225", b",7,220"))
        report = run_study(candidate)
        self.assertEqual(frozen, original)
        self.assertEqual(frozen["parameter"]["value"], 2)
        self.assertEqual(report["observation_report"]["status"], "FAIL")
        cost = next(row for row in report["observation_report"]["checks"] if row["metric"] == "full_batch_total_cost")
        self.assertEqual(cost["residual"]["value"], 5)

    def test_overlap_is_rejected(self):
        frozen = fit_candidate(FITTING.replace(b"fit-batch-001", b"demo-batch-001"))
        with self.assertRaisesRegex(ValueError, "overlap"):
            evaluate_frozen(frozen, HELDOUT)

    def test_frozen_parameter_or_criteria_mutation_is_rejected(self):
        for key in ("parameter", "criteria"):
            frozen = fit_candidate(FITTING)
            if key == "parameter":
                frozen[key]["value"] = 1
            else:
                frozen[key]["absolute_tolerance"] = 100
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "changed"):
                evaluate_frozen(frozen, HELDOUT)

    def test_invalid_or_ambiguous_fitting_records_are_rejected(self):
        for raw in (FITTING.replace(b"fit-batch-002", b"fit-batch-001"),
                    FITTING.replace(b"synthetic", b"real", 1), FITTING.replace(b",finish,2", b",finish,NaN", 1),
                    FITTING.replace(b",finish,2", b",finish,0", 1),
                    FITTING.replace(b",finish,2", b",finish,1e308", 1),
                    FITTING.replace(b"cycle_time_h", b"cycle_time_min"),
                    b"\n".join(FITTING.splitlines()[:2]), b"x" * 65537):
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                fit_candidate(raw)

    def test_predeclared_baseline_and_candidate_show_expected_heldout_errors(self):
        frozen = fit_candidate(FITTING)
        baseline, candidate, _, heldout = evaluate_frozen(frozen, HELDOUT)
        before, after = run_study(baseline), run_study(candidate)
        self.assertEqual(before["observation_report"]["status"], "FAIL")
        self.assertEqual(after["observation_report"]["status"], "PASS")
        self.assertEqual(before["simulation"]["batch_completion_time"]["value"], 8.5)
        self.assertEqual(after["simulation"]["batch_completion_time"]["value"], 7)
        self.assertEqual(heldout["frozen_candidate_fingerprint"], frozen["frozen_fingerprint"])
        self.assertEqual(after["review_state"], "HUMAN_REVIEW")
        self.assertFalse(after["production_authorized"])

    def test_run_retains_full_provenance_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "rehearsal"
            summary = run_rehearsal(output)
            self.assertFalse(summary["empirical_calibration_complete"])
            self.assertEqual((output / "fitting-records.csv").read_bytes(), FITTING)
            self.assertEqual((output / "heldout-export.csv").read_bytes(), HELDOUT)
            saved = (output / "frozen-candidate.json").read_bytes()
            self.assertEqual(json.loads(saved)["fitting_count"], 3)
            with self.assertRaises(FileExistsError):
                run_rehearsal(output)
            self.assertEqual((output / "frozen-candidate.json").read_bytes(), saved)
