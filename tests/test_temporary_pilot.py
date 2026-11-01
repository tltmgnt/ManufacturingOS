"""Combined rehearsal preserves provenance and distinguishes incomplete runs."""
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from examples.temporary_pilot import render_index, run_pilot


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs)["href"])


class TemporaryPilotTests(unittest.TestCase):
    def test_complete_review_links_and_full_provenance_are_retained(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pilot"
            summary = run_pilot(output)
            self.assertEqual(summary["status"], "SOFTWARE_REHEARSAL_PASSED")
            for key in ("production_authorized", "empirical_calibration_complete", "live_integration_complete", "actual_shadow_pilot_complete"):
                self.assertFalse(summary[key])
            self.assertEqual(json.loads((output / "run-status.json").read_text())["status"], "COMPLETE")
            parser = Links()
            parser.feed((output / "index.html").read_text())
            self.assertEqual(len(parser.links), 12)
            self.assertTrue(all((output / path).is_file() for path in parser.links))
            self.assertTrue((output / "calibration/fitting-records.csv").is_file())
            self.assertTrue((output / "calibration/frozen-candidate.json").is_file())
            self.assertTrue((output / "intake/source-export.csv").is_file())

    def test_component_failure_does_not_publish_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "pilot"
            with patch("examples.temporary_pilot.run_intake", side_effect=ValueError("fixture failure")):
                with self.assertRaisesRegex(ValueError, "fixture failure"):
                    run_pilot(output)
            self.assertEqual(json.loads((output / "run-status.json").read_text())["status"], "FAILED")
            self.assertEqual(json.loads((output / "run-status.json").read_text())["phase"], "intake")
            self.assertFalse((output / "rehearsal-scorecard.json").exists())
            self.assertFalse((output / "index.html").exists())
            self.assertTrue((output / "planning/summary.json").exists())

    def test_existing_directory_is_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            marker = output / "run-status.json"
            marker.write_text("existing")
            with self.assertRaises(FileExistsError):
                run_pilot(output)
            self.assertEqual(marker.read_text(), "existing")

    def test_summary_values_are_escaped(self):
        page = render_index({"software_checks": [{"check": "<script>alert(1)</script>", "result": "PASS"}]})
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
