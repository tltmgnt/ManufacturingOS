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
        with self.assertRaisesRegex(ValueError, "differ from the manifest"):
            verify_rehearsal(self.root)
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
