"""Traceability must detect source changes without claiming an unavailable Git state."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from examples.rehearsal_provenance import SOURCE_ROOT, capture_provenance, verify_source_unchanged
from examples.temporary_pilot import run_pilot


def source_tree(root):
    (root / "manufacturing_os").mkdir()
    (root / "examples").mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (root / "manufacturing_os/code.py").write_text("value = 1\n")
    (root / "examples/data.json").write_text('{"value":1}\n')


class RehearsalProvenanceTests(unittest.TestCase):
    def test_source_fingerprint_is_deterministic_and_detects_code_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_tree(root)
            first = capture_provenance(root)
            self.assertEqual(first["source_fingerprint"], capture_provenance(root)["source_fingerprint"])
            self.assertEqual(len(first["files"]), 3)
            verify_source_unchanged(first, root)
            (root / "manufacturing_os/code.py").write_text("value = 2\n")
            with self.assertRaisesRegex(ValueError, "source changed"):
                verify_source_unchanged(first, root)

    def test_missing_git_is_unknown_rather_than_clean(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_tree(root)
            with patch("examples.rehearsal_provenance.subprocess.run", side_effect=FileNotFoundError):
                provenance = capture_provenance(root)
            self.assertIsNone(provenance["git_commit"])
            self.assertIsNone(provenance["captured_source_roots_dirty"])
            self.assertTrue(provenance["source_fingerprint"])

    def test_documentation_is_outside_runtime_snapshot_but_json_is_included(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_tree(root)
            first = capture_provenance(root)
            (root / "examples/README.md").write_text("Documentation changed")
            verify_source_unchanged(first, root)
            (root / "examples/data.json").write_text('{"value":2}\n')
            with self.assertRaises(ValueError):
                verify_source_unchanged(first, root)

    def test_symlinks_and_excessive_source_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_tree(root)
            link = root / "examples/link.py"
            try:
                link.symlink_to(root / "manufacturing_os/code.py")
            except OSError:
                self.skipTest("Symlinks unavailable")
            with self.assertRaisesRegex(ValueError, "symlinks"):
                capture_provenance(root)
            link.unlink()
            with patch("examples.rehearsal_provenance.MAX_FILE_BYTES", 4), self.assertRaisesRegex(ValueError, "bounded"):
                capture_provenance(root)

    def test_changed_source_fails_run_before_success_is_published(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pilot"
            with patch("examples.temporary_pilot.verify_source_unchanged", side_effect=ValueError("source changed")):
                with self.assertRaisesRegex(ValueError, "source changed"):
                    run_pilot(output)
            status = json.loads((output / "run-status.json").read_text())
            self.assertEqual(status["status"], "FAILED")
            self.assertEqual(status["phase"], "source-verification")
            self.assertTrue((output / "source-provenance.json").is_file())
            self.assertFalse((output / "rehearsal-scorecard.json").exists())
            self.assertFalse((output / "index.html").exists())

    def test_output_inside_snapshot_roots_is_rejected_before_creation(self):
        output = SOURCE_ROOT / "examples/source-output-rejected-test"
        with self.assertRaisesRegex(ValueError, "outside"):
            run_pilot(output)
        self.assertFalse(output.exists())
