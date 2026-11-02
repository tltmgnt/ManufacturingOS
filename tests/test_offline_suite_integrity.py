"""A copied offline suite must preserve its files and reconstructed component results."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from examples.offline_suite import run_suite
from examples.offline_suite_integrity import MANIFEST, verify_suite, write_suite_manifest


class OfflineSuiteIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.temporary.name) / "suite"
        run_suite(cls.fixture)
    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()
    def setUp(self):
        self.working = tempfile.TemporaryDirectory()
        self.root = Path(self.working.name) / "copy"
        shutil.copytree(self.fixture, self.root)
        self.addCleanup(self.working.cleanup)
    def change(self, name, mutate):
        path = self.root / name
        value = json.loads(path.read_text()); mutate(value); path.write_text(json.dumps(value))

    def test_complete_copy_reconstructs_every_component(self):
        result = verify_suite(self.root)
        self.assertEqual(result["status"], "VERIFIED_CONTENT")
        self.assertEqual(result["verified_study_bundles"], 16)
        self.assertEqual(result["verified_edge_cases"], 6)
        self.assertEqual(result["verified_invariant_cases"], 54)
        self.assertGreater(result["verified_files"], 250)
        self.assertFalse(result["production_authorized"])

    def test_changed_missing_or_extra_files_fail_inventory(self):
        path = self.root / "index.html"; saved = path.read_bytes()
        path.write_bytes(saved + b"changed")
        with self.assertRaisesRegex(ValueError, "differ from manifest"):
            verify_suite(self.root)
        path.unlink()
        with self.assertRaises(ValueError):
            verify_suite(self.root)
        path.write_bytes(saved); (self.root / "extra.txt").write_text("extra")
        with self.assertRaises(ValueError):
            verify_suite(self.root)

    def test_refreshed_manifest_cannot_hide_edge_scorecard_changes(self):
        self.change("edges/edge-scorecard.json", lambda value: value["cases"][0]["actual"].update(target_met=False))
        write_suite_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "Edge scorecard"):
            verify_suite(self.root)

    def test_refreshed_manifest_cannot_hide_invariant_report_changes(self):
        path = next((self.root / "invariants").glob("*/simulation-report.json"))
        self.change(path.relative_to(self.root).as_posix(), lambda value: value.update(good_by_horizon=999))
        write_suite_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "Invariant base report"):
            verify_suite(self.root)

    def test_overview_must_match_its_scorecard(self):
        path = self.root / "index.html"; path.write_text(path.read_text() + "changed")
        write_suite_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "overview differs"):
            verify_suite(self.root)

    def test_repeatability_summary_must_match_actual_comparison(self):
        self.change("repeatability/repeatability.json", lambda value: value.update(compared_files=999))
        write_suite_manifest(self.root, replace=True)
        with self.assertRaisesRegex(ValueError, "Repeatability scorecard"):
            verify_suite(self.root)

    def test_unsafe_and_duplicate_manifest_paths_are_rejected(self):
        original = (self.root / MANIFEST).read_text()
        for mode in ("unsafe", "duplicate"):
            value = json.loads(original)
            if mode == "unsafe":
                value["files"][0]["path"] = "../outside"
            else:
                value["files"].append(value["files"][0])
            (self.root / MANIFEST).write_text(json.dumps(value))
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify_suite(self.root)

    def test_authorization_claim_cannot_receive_a_manifest(self):
        self.change("offline-suite.json", lambda value: value.update(production_authorized=True))
        with self.assertRaisesRegex(ValueError, "real-world authorization"):
            write_suite_manifest(self.root, replace=True)
