"""Read-only rehearsal of a single synthetic batch export; no enterprise connection."""
import argparse
import base64
from copy import deepcopy
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re

from manufacturing_os.bundle import build_bundle, verify_bundle
from manufacturing_os.models import ManufacturingInput, digest
from manufacturing_os.review import render_review
from manufacturing_os.study import binding, preflight_study, run_study
from .temporary_use_case import encode

COLUMNS = ("data_kind,batch_id,product_id,design_revision,facility_id,facility_revision,"
           "batch_size,horizon_h,good_by_horizon,scrapped_by_horizon,wip_at_horizon,"
           "eventual_good_units,eventual_scrapped_units,batch_completion_time_h,full_batch_total_cost_usd").split(",")
COUNTS = ("batch_size", "good_by_horizon", "scrapped_by_horizon", "wip_at_horizon",
          "eventual_good_units", "eventual_scrapped_units")


def parse_export(raw: bytes) -> dict:
    if len(raw) > 65536:
        raise ValueError("Synthetic export exceeds 64 KiB")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != COLUMNS:
        raise ValueError("Export requires the exact documented columns in order")
    rows = list(reader)
    if len(rows) != 1 or set(rows[0]) != set(COLUMNS) or any(value is None or not value.strip() for value in rows[0].values()):
        raise ValueError("Export requires exactly one complete batch row")
    row = rows[0]
    if row["data_kind"] != "synthetic":
        raise ValueError("This rehearsal accepts synthetic records only")
    for name in COUNTS:
        if not re.fullmatch(r"[0-9]{1,9}", row[name]):
            raise ValueError(f"{name} must be a nonnegative integer of at most nine digits")
        row[name] = int(row[name])
    for name in ("horizon_h", "batch_completion_time_h", "full_batch_total_cost_usd"):
        if not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", row[name]):
            raise ValueError(f"{name} requires a nonnegative decimal")
        row[name] = float(row[name])
        if not math.isfinite(row[name]):
            raise ValueError(f"{name} must be finite")
    if row["batch_size"] <= 0 or row["horizon_h"] <= 0 or row["batch_completion_time_h"] <= 0:
        raise ValueError("Batch size, horizon and completion time must be positive")
    if row["good_by_horizon"] + row["scrapped_by_horizon"] + row["wip_at_horizon"] != row["batch_size"]:
        raise ValueError("Horizon counts do not reconcile to batch starts")
    if row["eventual_good_units"] + row["eventual_scrapped_units"] != row["batch_size"]:
        raise ValueError("Final counts do not reconcile to batch starts")
    if row["good_by_horizon"] > row["eventual_good_units"] or row["scrapped_by_horizon"] > row["eventual_scrapped_units"]:
        raise ValueError("Horizon dispositions exceed final dispositions")
    if (row["batch_completion_time_h"] <= row["horizon_h"]) != (row["wip_at_horizon"] == 0):
        raise ValueError("Completion time and horizon WIP disagree")
    if row["eventual_good_units"] == 0:
        raise ValueError("This unit-cost rehearsal requires positive final good output")
    return row


def prepare_intake(raw: bytes) -> tuple[dict, dict]:
    row = parse_export(raw)
    root = Path(__file__).resolve().parent
    spec = json.loads((root / "observation-study.json").read_text())
    reference = json.loads((root / "observation-reference.json").read_text())
    for key in ("product_id", "design_revision", "facility_id", "facility_revision", "batch_size"):
        if row[key] != reference["context"][key]:
            raise ValueError(f"Export context mismatch: {key}")
    if row["horizon_h"] != reference["context"]["horizon"]["value"]:
        raise ValueError("Export context mismatch: horizon_h")
    # Derive every selected metric from CSV values, retaining original bytes separately.
    for key, measurement in reference["metrics"].items():
        source = {"batch_completion_time": "batch_completion_time_h", "full_batch_total_cost": "full_batch_total_cost_usd"}.get(key, key)
        measurement["value"] = (row["full_batch_total_cost_usd"] / row["eventual_good_units"]
                                if key == "full_batch_unit_cost" else row[source])
    spec["revision"] = "synthetic-export-intake-1"
    raw_hash = hashlib.sha256(raw).hexdigest()
    reference_raw = encode(reference)
    spec["manufacturing_input"]["evidence"][0].update(
        source_uri="synthetic://derived-batch-reference", content_hash=hashlib.sha256(reference_raw).hexdigest())
    spec["evidence_policy"]["sources"][0]["source_uri"] = "synthetic://derived-batch-reference"
    spec["evidence_snapshot"]["files"][0]["content_base64"] = base64.b64encode(reference_raw).decode()
    export_evidence = deepcopy(spec["manufacturing_input"]["evidence"][0])
    export_evidence.update(evidence_id="E-EXPORT", source_uri="synthetic://batch-export",
                           evidence_type="synthetic-batch-export", content_hash=raw_hash)
    spec["manufacturing_input"]["evidence"].append(export_evidence)
    spec["evidence_policy"]["sources"].append({key: export_evidence[key] for key in
                                              ("source_uri", "source_owner", "revision", "evidence_type")})
    spec["evidence_snapshot"]["files"].append({"evidence_id": "E-EXPORT", "content_base64": base64.b64encode(raw).decode()})
    spec["evidence_snapshot"]["input_fingerprint"] = ManufacturingInput.from_dict(spec["manufacturing_input"]).fingerprint
    spec["binding"] = binding(spec["manufacturing_input"], spec["scenario"])
    provenance = {"scope": "SYNTHETIC_EXPORT_INTAKE", "batch_id": row["batch_id"],
                  "raw_sha256": raw_hash, "derived_reference_sha256": hashlib.sha256(reference_raw).hexdigest(),
                  "reference_fingerprint": digest(reference), "observation_count": 1,
                  "transformation": "synthetic-batch-csv-to-reference-1", "production_authorized": False,
                  "empirical_calibration_complete": False}
    return spec, provenance


def run_intake(output: Path) -> dict:
    # Read only the bundled synthetic fixture; this command has no live-source selector.
    raw = (Path(__file__).resolve().parent / "synthetic-batch-export.csv").read_bytes()
    spec, provenance = prepare_intake(raw)
    preflight = preflight_study(spec)
    report = run_study(spec)
    if report["observation_report"]["status"] != "PASS" or report["production_authorized"]:
        raise RuntimeError("Synthetic export comparison produced an unexpected result")
    archive = build_bundle(spec)
    verification = verify_bundle(archive)
    output.mkdir(parents=True, exist_ok=False)
    for name, data in [("study-input.json", spec), ("intake-provenance.json", provenance),
                       ("preflight.json", preflight), ("study-report.json", report),
                       ("bundle-verification.json", verification)]:
        (output / name).write_bytes(encode(data))
    (output / "source-export.csv").write_bytes(raw)
    (output / "derived-reference.json").write_bytes(base64.b64decode(spec["evidence_snapshot"]["files"][0]["content_base64"]))
    (output / "study-review.html").write_text(render_review(report), encoding="utf-8")
    (output / "study-review.zip").write_bytes(archive)
    return {**provenance, "observation_status": report["observation_report"]["status"],
            "bundle_status": verification["status"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    try:
        print(json.dumps(run_intake(args.output), indent=2))
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, csv.Error) as exc:
        parser.exit(2, f"Synthetic intake error: {exc}\n")


if __name__ == "__main__":
    main()
