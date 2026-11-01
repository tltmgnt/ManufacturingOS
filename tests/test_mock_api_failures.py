"""Failures must stop before intake/model work and never publish fake success."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from examples.mock_api_failures import CASES, run_failures
from examples.mock_enterprise_api import MockAPIRejected


class MockAPIFailureTests(unittest.TestCase):
    def test_all_real_transport_faults_stop_before_intake(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "failures"
            with patch("examples.mock_enterprise_api.run_intake_bytes") as intake:
                summary = run_failures(output)
                intake.assert_not_called()
            self.assertEqual(summary["status"], "EXPECTED_FAILURES_DETECTED")
            self.assertEqual(len(summary["cases"]), 9)
            for row in summary["cases"]:
                self.assertFalse(row["model_executed"])
                self.assertFalse((output / row["case"]).exists())
                self.assertEqual(len(row["request_audit"]), 1)
            self.assertEqual([row["request_audit"][0]["status"] for row in summary["cases"]], [401, 403, 429, 503, 200, 200, None, 200, None])
            self.assertFalse(summary["automatic_retries"])
            self.assertTrue((output / "index.html").is_file())

    def test_unexpected_source_acceptance_does_not_publish_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "failures"
            with patch("examples.mock_api_failures.run_api_rehearsal", return_value={}), self.assertRaisesRegex(RuntimeError, "unexpectedly"):
                run_failures(output)
            self.assertFalse((output / "failure-scorecard.json").exists())
            self.assertFalse((output / "index.html").exists())

    def test_unrelated_rejection_is_not_counted_as_expected_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "failures"
            error = MockAPIRejected("different error", [])
            with patch("examples.mock_api_failures.run_api_rehearsal", side_effect=error), self.assertRaisesRegex(RuntimeError, "not rejected as expected"):
                run_failures(output)
            self.assertFalse((output / "failure-scorecard.json").exists())

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            marker = output / "failure-scorecard.json"
            marker.write_text("existing")
            with self.assertRaises(FileExistsError):
                run_failures(output)
            self.assertEqual(marker.read_text(), "existing")

    def test_fault_audits_do_not_retain_ephemeral_credentials(self):
        token = "r" * 43
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "failures"
            with patch("examples.mock_enterprise_api.secrets.token_urlsafe", return_value=token):
                summary = run_failures(output)
            self.assertNotIn(token, json.dumps(summary))
            self.assertNotIn("x" + token[1:], json.dumps(summary))
            for path in output.iterdir():
                self.assertNotIn(token.encode(), path.read_bytes())
