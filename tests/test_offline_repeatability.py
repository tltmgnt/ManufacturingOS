"""Repeatability distinguishes verified drift, invalid output and failed reruns."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from examples.offline_repeatability import compare_runs, run_repeatability
from examples.rehearsal_integrity import write_manifest


class OfflineRepeatabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name) / "repeat"
        cls.result = run_repeatability(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_two_real_synthetic_runs_are_byte_repeatable(self):
        self.assertEqual(self.result["status"], "REPEATABLE")
        self.assertEqual(self.result["compared_files"], 72)
        self.assertEqual(self.result["differences"], [])
        self.assertEqual(len(set(self.result["source_fingerprints"])), 1)
        self.assertFalse(self.result["live_integration_complete"])
        self.assertFalse(self.result["empirical_calibration_complete"])

    def test_verified_environment_drift_is_reported_as_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / "changed"
            shutil.copytree(self.root / "second", copy)
            path = copy / "source-provenance.json"
            provenance = json.loads(path.read_text())
            provenance["machine"] = "different-synthetic-environment"
            path.write_text(json.dumps(provenance))
            write_manifest(copy, replace=True)
            result = compare_runs(self.root / "first", copy)
            self.assertEqual(result["status"], "MISMATCH")
            self.assertIn("source-provenance.json", [row["path"] for row in result["differences"]])

    def test_invalid_run_is_rejected_before_comparison(self):
        with self.assertRaisesRegex(ValueError, "two distinct"):
            compare_runs(self.root / "first", self.root / "first")
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / "damaged"
            shutil.copytree(self.root / "second", copy)
            (copy / "planning/baseline/study-report.json").unlink()
            with self.assertRaises(ValueError):
                compare_runs(self.root / "first", copy)

    def test_second_run_failure_cannot_publish_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "repeat"
            with patch("examples.offline_repeatability.run_pilot", side_effect=[{}, ValueError("second run failed")]):
                with self.assertRaisesRegex(ValueError, "second run failed"):
                    run_repeatability(output)
            status = json.loads((output / "run-status.json").read_text())
            self.assertEqual(status, {"status": "FAILED", "phase": "second-run"})
            self.assertFalse((output / "repeatability.json").exists())

    def test_existing_output_is_preserved_without_starting_a_run(self):
        with patch("examples.offline_repeatability.run_pilot") as run:
            before = (self.root / "repeatability.json").read_bytes()
            with self.assertRaises(FileExistsError):
                run_repeatability(self.root)
            run.assert_not_called()
            self.assertEqual((self.root / "repeatability.json").read_bytes(), before)
