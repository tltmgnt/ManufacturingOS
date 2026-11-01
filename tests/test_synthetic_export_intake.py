"""Intake regression checks: malformed exports and raw-to-derived traceability."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from examples.synthetic_export_intake import COLUMNS, parse_export, prepare_intake, run_intake
from manufacturing_os.study import run_study

RAW = (Path(__file__).resolve().parents[1] / "examples/synthetic-batch-export.csv").read_bytes()


def changed(**values):
    row = next(csv.DictReader(io.StringIO(RAW.decode())))
    row.update(values)
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerow(row)
    return target.getvalue().encode()


class ExportIntakeTests(unittest.TestCase):
    def test_raw_and_derived_sources_are_captured_separately(self):
        spec, provenance = prepare_intake(RAW)
        files = {row["evidence_id"]: base64.b64decode(row["content_base64"]) for row in spec["evidence_snapshot"]["files"]}
        self.assertEqual(files["E-EXPORT"], RAW)
        self.assertEqual(provenance["raw_sha256"], hashlib.sha256(RAW).hexdigest())
        self.assertEqual(provenance["derived_reference_sha256"], hashlib.sha256(files["E1"]).hexdigest())
        reference = json.loads(files["E1"])
        self.assertEqual(reference["reference_kind"], "synthetic")
        self.assertEqual(reference["metrics"]["full_batch_unit_cost"]["value"], 75)
        report = run_study(spec)
        self.assertEqual(report["observation_report"]["status"], "PASS")
        self.assertEqual({row["status"] for row in report["source_report"]["records"]}, {"HASH_MATCHED"})
        self.assertFalse(report["production_authorized"])

    def test_export_values_drive_comparison_rather_than_copied_reference(self):
        spec, _ = prepare_intake(changed(full_batch_total_cost_usd="220"))
        report = run_study(spec)
        self.assertEqual(report["observation_report"]["status"], "FAIL")
        self.assertEqual(report["review_state"], "REVISION_REQUIRED")
        cost = next(row for row in report["observation_report"]["checks"] if row["metric"] == "full_batch_total_cost")
        self.assertEqual(cost["residual"]["value"], 5)

    def test_context_and_real_record_labels_are_rejected(self):
        for values in ({"product_id": "different"}, {"facility_revision": "other"},
                       {"horizon_h": "6"}, {"data_kind": "declared_observations"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                prepare_intake(changed(**values))

    def test_inconsistent_or_undefined_counts_are_rejected(self):
        for values in ({"wip_at_horizon": "2"}, {"eventual_good_units": "2"},
                       {"batch_completion_time_h": "4"}, {"good_by_horizon": "-1"},
                       {"good_by_horizon": "2.0"},
                       {"good_by_horizon": "0", "scrapped_by_horizon": "3", "wip_at_horizon": "0",
                        "eventual_good_units": "0", "eventual_scrapped_units": "3", "batch_completion_time_h": "4"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                parse_export(changed(**values))

    def test_malformed_rows_headers_units_and_nonfinite_values_are_rejected(self):
        for raw in (RAW + RAW.splitlines(keepends=True)[1], RAW.replace(b"horizon_h", b"horizon_min"),
                    RAW.replace(b"data_kind,batch_id", b"data_kind,data_kind"),
                    RAW.replace(b",7,225", b",7,NaN"), RAW.rstrip() + b",extra\n",
                    RAW.replace(b",225", b","), b"x" * 65537):
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                parse_export(raw)

    def test_run_preserves_existing_output_and_bundled_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "intake"
            result = run_intake(output)
            self.assertEqual(result["bundle_status"], "VERIFIED_CONTENT")
            self.assertEqual((output / "source-export.csv").read_bytes(), RAW)
            before = (output / "study-report.json").read_bytes()
            with self.assertRaises(FileExistsError):
                run_intake(output)
            self.assertEqual((output / "study-report.json").read_bytes(), before)
            self.assertEqual((Path(__file__).resolve().parents[1] / "examples/synthetic-batch-export.csv").read_bytes(), RAW)
