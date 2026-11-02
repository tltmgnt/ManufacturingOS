"""Handoff metadata is not external evidence, identity verification or acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from examples.pilot_readiness import assess

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = json.loads((ROOT / "examples/pilot-readiness.json").read_text())


def complete_index():
    value = deepcopy(TEMPLATE)
    for item in value["milestones"]:
        item["owner_reference"] = "synthetic://unverified-owner"
        for row in item["evidence"]:
            row.update(reference="https://example.invalid/" + row["requirement_id"], revision="fixture-1", sha256="0" * 64)
    return value


class PilotReadinessTests(unittest.TestCase):
    def test_unfilled_template_reports_all_three_owners_and_fifteen_records(self):
        report = assess(deepcopy(TEMPLATE))
        self.assertEqual(report["status"], "MISSING_DECLARED_METADATA")
        self.assertEqual(report["missing_owners"], 3)
        self.assertEqual(report["missing_evidence_records"], 15)
        self.assertEqual(report["metadata_complete_milestones"], 0)

    def test_complete_declarations_never_fetch_sources_or_close_milestones(self):
        value = complete_index()
        value["milestones"][0]["evidence"][0]["reference"] = "file:///must-not-be-opened"
        with patch("urllib.request.urlopen", side_effect=AssertionError("No source fetch allowed")) as fetch:
            report = assess(value)
            fetch.assert_not_called()
        self.assertEqual(report["status"], "DECLARED_METADATA_COMPLETE_NOT_VERIFIED")
        self.assertEqual(report["metadata_complete_milestones"], 3)
        for key in ("external_sources_accessed", "source_hashes_verified", "identities_authenticated", "milestone_closure_assessed", "production_authorized"):
            self.assertFalse(report[key])
        self.assertTrue(all(row["closure_assessed"] is False for row in report["milestones"]))

    def test_partial_record_reports_exact_missing_fields(self):
        value = deepcopy(TEMPLATE)
        value["milestones"][0]["evidence"][0]["reference"] = "controlled-record-id"
        report = assess(value)
        self.assertEqual(report["milestones"][0]["evidence_checks"][0]["missing_fields"], ["revision", "sha256"])
        value["milestones"][0]["evidence"] = []
        self.assertEqual(assess(value)["missing_evidence_records"], 15)

    def test_missing_owner_still_blocks_metadata_completeness(self):
        value = complete_index()
        for item in value["milestones"]:
            item["owner_reference"] = None
        report = assess(value)
        self.assertEqual(report["missing_evidence_records"], 0)
        self.assertEqual(report["missing_owners"], 3)
        self.assertEqual(report["metadata_complete_milestones"], 0)

    def test_duplicate_unknown_and_malformed_records_are_rejected(self):
        values = []
        value = deepcopy(TEMPLATE); value["milestones"][1]["milestone_id"] = "M1"; values.append(value)
        value = deepcopy(TEMPLATE); value["milestones"].pop(); values.append(value)
        value = deepcopy(TEMPLATE); value["milestones"][0]["evidence"][1]["requirement_id"] = "data_authority"; values.append(value)
        value = deepcopy(TEMPLATE); value["milestones"][0]["evidence"][0]["requirement_id"] = "unknown"; values.append(value)
        value = deepcopy(TEMPLATE); value["milestones"][0]["evidence"][0]["sha256"] = "not-a-hash"; values.append(value)
        value = deepcopy(TEMPLATE); value["milestones"][0]["owner_reference"] = " "; values.append(value)
        value = deepcopy(TEMPLATE); value["production_authorized"] = True; values.append(value)
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                assess(value)

    def test_report_records_do_not_mutate_the_input_index(self):
        value = complete_index(); before = deepcopy(value)
        report = assess(value)
        report["milestones"][0]["evidence_checks"][0]["record"]["reference"] = "changed"
        self.assertEqual(value, before)

    def test_cli_exit_codes_and_output_preservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); index = root / "index.json"; output = root / "report.json"
            index.write_text(json.dumps(TEMPLATE))
            command = [sys.executable, "-m", "examples.pilot_readiness", str(index), "--output", str(output)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            saved = output.read_bytes()
            self.assertEqual(subprocess.run(command, cwd=ROOT, capture_output=True).returncode, 2)
            self.assertEqual(output.read_bytes(), saved)
            output.unlink(); index.write_text(json.dumps(complete_index()))
            self.assertEqual(subprocess.run(command, cwd=ROOT, capture_output=True).returncode, 0)
            output.unlink(); index.write_text('{"schema_version":"1.0","schema_version":"1.0"}')
            self.assertEqual(subprocess.run(command, cwd=ROOT, capture_output=True).returncode, 2)
            self.assertFalse(output.exists())
