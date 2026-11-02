"""Whole-run verification detects damage and cross-file inconsistencies."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from examples.rehearsal_integrity import MANIFEST, verify_rehearsal, write_manifest
from examples.temporary_pilot import run_pilot


class RehearsalIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.temporary.name) / "fixture"
        run_pilot(cls.fixture)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.copy_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.copy_directory.name) / "copy"
        shutil.copytree(self.fixture, self.root)
        self.addCleanup(self.copy_directory.cleanup)

    def test_complete_run_reconstructs_eight_bundles_and_fitting_provenance(self):
        result = verify_rehearsal(self.root)
        self.assertEqual(result["status"], "VERIFIED_CONTENT")
        self.assertEqual(result["verified_study_bundles"], 8)
        self.assertGreater(result["verified_files"], 50)
        self.assertFalse(result["production_authorized"])

    def test_changed_missing_and_extra_files_fail(self):
        path = self.root / "index.html"
        saved = path.read_bytes()
        path.write_bytes(saved + b"changed")
        with self.assertRaisesRegex(ValueError, "differ from the manifest") as error:
            verify_rehearsal(self.root)
        self.assertIn("index.html", str(error.exception))
        path.unlink()
        with self.assertRaises(ValueError):
            verify_rehearsal(self.root)
        path.write_bytes(saved)
        (self.root / "unlisted.txt").write_text("extra")
        with self.assertRaises(ValueError):
            verify_rehearsal(self.root)

    def test_unsafe_or_duplicate_manifest_paths_are_rejected(self):
        path = self.root / MANIFEST
        original = json.loads(path.read_text())
        for name in ("../outside", "/absolute", "a\\b", "a//b", "C:/drive"):
            manifest = json.loads(json.dumps(original))
            manifest["files"][0]["path"] = name
            path.write_text(json.dumps(manifest))
            with self.subTest(name=name), self.assertRaises(ValueError):
                verify_rehearsal(self.root)
        manifest = json.loads(json.dumps(original))
        manifest["files"].append(manifest["files"][0])
        path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            verify_rehearsal(self.root)

    def test_refreshed_hashes_do_not_hide_loose_report_disagreement(self):
        path = self.root / "planning/baseline/study-report.json"
        path.write_bytes(path.read_bytes() + b"\n")
        write_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "differs from its verified bundle"):
            verify_rehearsal(self.root)

    def test_refreshed_hashes_do_not_hide_fitting_record_changes(self):
        path = self.root / "calibration/fitting-records.csv"
        path.write_bytes(path.read_bytes().replace(b",finish,2", b",finish,3", 1))
        write_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "frozen candidate"):
            verify_rehearsal(self.root)

    def test_incomplete_run_cannot_receive_a_new_manifest(self):
        path = self.root / "run-status.json"
        status = json.loads(path.read_text())
        status["status"] = "FAILED"
        path.write_text(json.dumps(status))
        with self.assertRaisesRegex(ValueError, "completed"):
            write_manifest(self.root, replace=True)

    def test_symlinked_content_is_rejected(self):
        path = self.root / "index.html"
        path.unlink()
        try:
            path.symlink_to(self.fixture / "index.html")
        except OSError:
            self.skipTest("Symlinks unavailable")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            verify_rehearsal(self.root)

    def rewrite_json(self, name, mutate):
        path = self.root / name
        value = json.loads(path.read_text())
        mutate(value)
        path.write_text(json.dumps(value))

    def rewrite_component(self, name, file, mutate):
        self.rewrite_json(file, mutate)
        def update_scorecard(scorecard):
            mutate(scorecard[name])
        self.rewrite_json("rehearsal-scorecard.json", update_scorecard)
        write_manifest(self.root, replace=True)

    def test_combined_summary_must_match_its_component_summary(self):
        self.rewrite_json("rehearsal-scorecard.json", lambda value: value["planning"]["cases"][2].update(target_met=True))
        write_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "Combined planning scorecard"):
            verify_rehearsal(self.root)

    def test_matching_summary_edits_cannot_hide_a_reported_target_miss(self):
        self.rewrite_component("planning", "planning/summary.json", lambda value: value["cases"][2].update(target_met=True))
        with self.assertRaisesRegex(ValueError, "Planning outcomes"):
            verify_rehearsal(self.root)

    def test_calibration_residuals_must_match_the_verified_reports(self):
        self.rewrite_component("calibration", "calibration/rehearsal-summary.json", lambda value: value["outcomes"][0]["cost_residual"].update(value=0))
        with self.assertRaisesRegex(ValueError, "Held-out residual scorecard"):
            verify_rehearsal(self.root)

    def test_request_audit_cannot_claim_a_write_request(self):
        self.rewrite_json("api/mock-request-audit.json", lambda value: value["requests"][0].update(method="POST"))
        write_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "Read-only API audit"):
            verify_rehearsal(self.root)

    def test_transport_hash_must_match_retained_export(self):
        self.rewrite_json("api/transport-provenance.json", lambda value: value.update(sha256="0" * 64))
        self.rewrite_component("api", "api/api-rehearsal-summary.json", lambda value: value["transport"].update(sha256="0" * 64))
        with self.assertRaisesRegex(ValueError, "retained export bytes"):
            verify_rehearsal(self.root)

    def test_failure_scorecard_must_retain_no_model_execution(self):
        self.rewrite_component("api_failures", "api-failures/failure-scorecard.json", lambda value: value["cases"][0].update(model_executed=True))
        with self.assertRaisesRegex(ValueError, "expected rejection"):
            verify_rehearsal(self.root)

    def test_failed_software_check_cannot_coexist_with_overall_success(self):
        self.rewrite_json("rehearsal-scorecard.json", lambda value: value["software_checks"][0].update(result="FAIL"))
        write_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "software check results"):
            verify_rehearsal(self.root)

    def test_heldout_provenance_must_match_frozen_candidate(self):
        self.rewrite_json("calibration/heldout-provenance.json", lambda value: value.update(frozen_candidate_fingerprint="0" * 64))
        write_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "Held-out provenance"):
            verify_rehearsal(self.root)

    def test_loose_source_bytes_must_match_captured_evidence(self):
        path = self.root / "intake/source-export.csv"
        path.write_bytes(path.read_bytes().replace(b",7,225", b",7,220"))
        write_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "captured study evidence"):
            verify_rehearsal(self.root)


    def test_intake_provenance_cannot_grant_authorization(self):
        self.rewrite_json("intake/intake-provenance.json", lambda value: value.update(production_authorized=True))
        self.rewrite_json("rehearsal-scorecard.json", lambda value: value["intake"].update(production_authorized=True))
        write_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "Intake provenance claimed authorization"):
            verify_rehearsal(self.root)
