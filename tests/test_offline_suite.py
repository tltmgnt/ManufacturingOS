"""A consolidated offline run must preserve evidence and expose incomplete/failed scope."""
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from examples.offline_suite import render_suite, run_suite


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs)["href"])


def component(status, fingerprint="a" * 64, repeat=False):
    result = {"status": status, "production_authorized": False, "empirical_calibration_complete": False, "live_integration_complete": False}
    result["source_fingerprints" if repeat else "source_fingerprint"] = [fingerprint, fingerprint] if repeat else fingerprint
    return result


class OfflineSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name) / "suite"
        cls.result = run_suite(cls.root)
    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_complete_suite_preserves_all_components_and_review_links(self):
        self.assertEqual(self.result["status"], "PASS")
        self.assertTrue(self.result["source_consistent"])
        parser = Links(); parser.feed((self.root / "index.html").read_text())
        self.assertEqual(len(parser.links), 7)
        self.assertTrue(all((self.root / name).is_file() for name in parser.links))
        self.assertTrue((self.root / "repeatability/first/rehearsal-manifest.json").is_file())
        self.assertTrue((self.root / "repeatability/second/rehearsal-manifest.json").is_file())
        self.assertTrue((self.root / "edges/edge-scorecard.json").is_file())
        self.assertTrue((self.root / "invariants/invariant-scorecard.json").is_file())
        self.assertFalse(self.result["actual_shadow_pilot_complete"])

    def test_completed_component_mismatch_is_visible_as_overall_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "suite"
            with patch("examples.offline_suite.run_repeatability", return_value=component("MISMATCH", repeat=True)), patch("examples.offline_suite.run_edges", return_value=component("PASS")), patch("examples.offline_suite.run_sweep", return_value=component("PASS")):
                result = run_suite(output)
            self.assertEqual(result["status"], "FAIL")
            self.assertIn('<span id="overall-result">FAIL</span>', (output / "index.html").read_text())
            self.assertEqual(json.loads((output / "run-status.json").read_text())["status"], "FAIL")

    def test_source_mismatch_cannot_pass_even_if_each_component_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "suite"
            with patch("examples.offline_suite.run_repeatability", return_value=component("REPEATABLE", repeat=True)), patch("examples.offline_suite.run_edges", return_value=component("PASS", "b" * 64)), patch("examples.offline_suite.run_sweep", return_value=component("PASS")):
                result = run_suite(output)
            self.assertFalse(result["source_consistent"])
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("DIFFERENT", (output / "index.html").read_text())

    def test_component_exception_does_not_publish_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "suite"
            with patch("examples.offline_suite.run_repeatability", side_effect=ValueError("fixture failed")):
                with self.assertRaises(ValueError):
                    run_suite(output)
            self.assertEqual(json.loads((output / "run-status.json").read_text()), {"status": "FAILED", "phase": "repeatability"})
            self.assertFalse((output / "offline-suite.json").exists())
            self.assertFalse((output / "index.html").exists())

    def test_component_cannot_claim_real_authorization(self):
        value = component("REPEATABLE", repeat=True); value["production_authorized"] = True
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "suite"
            with patch("examples.offline_suite.run_repeatability", return_value=value), patch("examples.offline_suite.run_edges", return_value=component("PASS")), patch("examples.offline_suite.run_sweep", return_value=component("PASS")):
                with self.assertRaisesRegex(RuntimeError, "real-world authorization"):
                    run_suite(output)
            self.assertFalse((output / "offline-suite.json").exists())

    def test_existing_output_is_preserved_before_component_execution(self):
        saved = (self.root / "offline-suite.json").read_bytes()
        with patch("examples.offline_suite.run_repeatability") as run:
            with self.assertRaises(FileExistsError):
                run_suite(self.root)
            run.assert_not_called()
        self.assertEqual((self.root / "offline-suite.json").read_bytes(), saved)

    def test_review_values_are_escaped(self):
        page = render_suite({"status": "PASS", "source_consistent": True, "components": [{"component": "<script>bad</script>", "software_check": "PASS", "observed_status": "PASS"}]})
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
