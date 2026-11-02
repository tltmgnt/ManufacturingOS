"""Portable archive checks reject hostile paths/metadata before temporary staging."""
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from examples.offline_suite import run_suite
from examples.offline_suite_bundle import create_archive, export_archive, verify_archive
from examples.offline_suite_integrity import MANIFEST


def archive_with(entries):
    output = io.BytesIO()
    with warnings.catch_warnings(), ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        warnings.simplefilter("ignore", UserWarning)
        for name, data, mode in entries:
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3; info.external_attr = mode << 16; info.compress_type = ZIP_DEFLATED
            archive.writestr(info, data)
    return output.getvalue()


class OfflineSuiteBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name) / "suite"
        run_suite(cls.root)
        cls.raw = create_archive(cls.root)
    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_roundtrip_is_verified_and_archive_bytes_are_repeatable(self):
        result = verify_archive(self.raw)
        self.assertEqual(result["status"], "VERIFIED_CONTENT")
        self.assertEqual(result["verified_study_bundles"], 16)
        self.assertEqual(result["verified_edge_cases"], 6)
        self.assertEqual(result["verified_invariant_cases"], 54)
        self.assertFalse(result["production_authorized"])
        self.assertEqual(create_archive(self.root), self.raw)

    def test_unsafe_duplicate_case_and_file_directory_collisions_fail_before_staging(self):
        mode = stat.S_IFREG | 0o644
        groups = [[(name, b"x", mode)] for name in ("../outside", "/absolute", "C:/drive", "a\\b", "CON", "aux .txt", "COM¹.txt", "a?.txt", "a\t.txt", "trailing.")]
        groups += [[("same", b"a", mode), ("same", b"b", mode)],
                   [("Same", b"a", mode), ("same", b"b", mode)],
                   [("a", b"a", mode), ("a/b", b"b", mode)],
                   [("é.txt", b"a", mode), ("e\u0301.txt", b"b", mode)]]
        for entries in groups:
            raw = archive_with(entries + [(MANIFEST, b"{}", mode)])
            with self.subTest(entries=entries), patch("examples.offline_suite_bundle.tempfile.TemporaryDirectory") as stage:
                with self.assertRaises(ValueError):
                    verify_archive(raw)
                stage.assert_not_called()

    def test_symlink_type_and_resource_limits_fail_before_staging(self):
        mode = stat.S_IFREG | 0o644
        raw = archive_with([(MANIFEST, b"{}", mode), ("link", b"target", stat.S_IFLNK | 0o777)])
        with patch("examples.offline_suite_bundle.tempfile.TemporaryDirectory") as stage:
            with self.assertRaisesRegex(ValueError, "regular files"):
                verify_archive(raw)
            stage.assert_not_called()
        raw = archive_with([(MANIFEST, b"{}", mode), ("large", b"12345", mode)])
        with patch("examples.offline_suite_bundle.MAX_FILE", 4), patch("examples.offline_suite_bundle.tempfile.TemporaryDirectory") as stage:
            with self.assertRaisesRegex(ValueError, "byte limit"):
                verify_archive(raw)
            stage.assert_not_called()

    def test_corrupted_member_cannot_pass_the_inner_suite_manifest(self):
        with ZipFile(io.BytesIO(self.raw)) as archive:
            entries = [(info.filename, archive.read(info) + (b"changed" if info.filename == "index.html" else b""), stat.S_IFREG | 0o644) for info in archive.infolist()]
        with self.assertRaisesRegex(ValueError, "differ from manifest"):
            verify_archive(archive_with(entries))

    def test_existing_output_and_inside_suite_destinations_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "existing.zip"; target.write_bytes(b"keep")
            with patch("examples.offline_suite_bundle.create_archive") as create:
                with self.assertRaises(FileExistsError):
                    export_archive(self.root, target)
                create.assert_not_called()
            self.assertEqual(target.read_bytes(), b"keep")
        with self.assertRaisesRegex(ValueError, "outside"):
            export_archive(self.root, self.root / "inside.zip")
        self.assertFalse((self.root / "inside.zip").exists())

    def test_invalid_archive_directory_is_rejected_without_staging(self):
        for raw in (b"not a zip", self.raw + b"trailing-data"):
            with self.subTest(raw=raw[:20]), patch("examples.offline_suite_bundle.tempfile.TemporaryDirectory") as stage:
                with self.assertRaises(ValueError):
                    verify_archive(raw)
                stage.assert_not_called()
