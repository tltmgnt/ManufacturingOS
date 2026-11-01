"""Synthetic fitting/held-out rehearsal, never empirical facility calibration."""
import argparse
import base64
from copy import deepcopy
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics

from manufacturing_os.bundle import build_bundle, verify_bundle
from manufacturing_os.models import digest
from manufacturing_os.review import render_review
from manufacturing_os.study import binding, run_study
from .synthetic_export_intake import parse_export, prepare_intake
from .temporary_use_case import bind_synthetic_reference, encode

METRICS = {"good_by_horizon", "wip_at_horizon", "eventual_good_units",
           "batch_completion_time", "full_batch_total_cost", "full_batch_unit_cost"}


def fit_candidate(raw: bytes) -> dict:
    """Estimate one parameter using fitting bytes alone, with fixed toy criteria."""
    if len(raw) > 65536:
        raise ValueError("Fitting data exceeds 64 KiB")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames != ["data_kind", "batch_id", "operation_id", "cycle_time_h"]:
        raise ValueError("Unexpected fitting columns")
    rows = list(reader)
    if not 2 <= len(rows) <= 100:
        raise ValueError("Rehearsal requires 2–100 distinct fitting batches")
    ids, samples = set(), []
    for row in rows:
        if set(row) != set(reader.fieldnames) or any(value is None for value in row.values()):
            raise ValueError("Incomplete fitting row")
        if row["data_kind"] != "synthetic" or row["operation_id"] != "finish":
            raise ValueError("Only synthetic finish-operation fitting records are supported")
        batch_id = row["batch_id"]
        if not batch_id.strip() or batch_id in ids:
            raise ValueError("Fitting batch IDs must be nonempty and unique")
        value = float(row["cycle_time_h"])
        if not math.isfinite(value) or not 0 < value <= 1_000_000:
            raise ValueError("Cycle times must be finite positive hours no greater than 1,000,000")
        ids.add(batch_id)
        samples.append(value)
    frozen = {"schema_version": "1.0", "scope": "SYNTHETIC_CALIBRATION_REHEARSAL",
              "fitting_source_sha256": hashlib.sha256(raw).hexdigest(),
              "fitting_batch_ids": sorted(ids), "fitting_count": len(samples),
              "method": "Arithmetic mean of one finish cycle-time measurement per fitting batch",
              "parameter": {"operation_id": "finish", "name": "cycle_time", "value": statistics.fmean(samples), "unit": "h"},
              "criteria": {"metrics": sorted(METRICS), "absolute_tolerance": 1e-9,
                           "require_all_defined": True, "reference_kind": "synthetic"},
              "empirical_calibration_complete": False, "production_authorized": False}
    frozen["frozen_fingerprint"] = digest(frozen)
    return frozen


def evaluate_frozen(frozen: dict, heldout_raw: bytes) -> tuple[dict, dict, dict, dict]:
    saved = deepcopy(frozen)
    fingerprint = saved.pop("frozen_fingerprint")
    if digest(saved) != fingerprint:
        raise ValueError("Frozen candidate changed after fitting")
    heldout = parse_export(heldout_raw)
    if heldout["batch_id"] in frozen["fitting_batch_ids"]:
        raise ValueError("Fitting and held-out batch IDs overlap")
    candidate, provenance = prepare_intake(heldout_raw)
    reference = json.loads(base64.b64decode(candidate["evidence_snapshot"]["files"][0]["content_base64"]))
    if set(reference["metrics"]) != set(frozen["criteria"]["metrics"]):
        raise ValueError("Held-out metrics differ from frozen criteria")
    cases = []
    for name, cycle_time in [("baseline", 2.5), ("candidate", frozen["parameter"]["value"])]:
        spec = deepcopy(candidate)
        spec["revision"] = "synthetic-heldout-" + name + "-1"
        spec["scenario"]["revision"] = spec["revision"]
        spec["scenario"]["operations"][1]["cycle_time"]["value"] = cycle_time
        spec["scenario"]["assumptions"].append("Synthetic fitting/held-out rehearsal only; not facility calibration.")
        for tolerance in spec["observation_checks"]["tolerances"].values():
            tolerance["value"] = frozen["criteria"]["absolute_tolerance"]
        bound_reference = deepcopy(reference)
        bound_reference["context"]["scenario_fingerprint"] = binding(
            spec["manufacturing_input"], spec["scenario"])["scenario_fingerprint"]
        bind_synthetic_reference(spec, bound_reference)
        cases.append(spec)
    return cases[0], cases[1], provenance, {"batch_id": heldout["batch_id"],
        "source_sha256": hashlib.sha256(heldout_raw).hexdigest(), "frozen_candidate_fingerprint": fingerprint}


def run_rehearsal(output: Path) -> dict:
    root = Path(__file__).resolve().parent
    fitting_raw = (root / "synthetic-fitting-records.csv").read_bytes()
    frozen = fit_candidate(fitting_raw)
    # Candidate and criteria exist before the held-out file is read.
    heldout_raw = (root / "synthetic-batch-export.csv").read_bytes()
    baseline, candidate, provenance, heldout = evaluate_frozen(frozen, heldout_raw)
    output.mkdir(parents=True, exist_ok=False)
    (output / "fitting-records.csv").write_bytes(fitting_raw)
    (output / "heldout-export.csv").write_bytes(heldout_raw)
    (output / "frozen-candidate.json").write_bytes(encode(frozen))
    (output / "heldout-provenance.json").write_bytes(encode({**provenance, **heldout}))
    outcomes = []
    for name, spec in [("baseline", baseline), ("candidate", candidate)]:
        report = run_study(spec)
        checks = report["observation_report"]
        cost = next(row for row in checks["checks"] if row["metric"] == "full_batch_total_cost")
        if checks["status"] != ("FAIL" if name == "baseline" else "PASS") or report["production_authorized"]:
            raise RuntimeError("Unexpected synthetic held-out outcome")
        directory = output / name
        directory.mkdir()
        archive = build_bundle(spec)
        verify_bundle(archive)
        (directory / "study-input.json").write_bytes(encode(spec))
        (directory / "study-report.json").write_bytes(encode(report))
        (directory / "study-review.html").write_text(render_review(report), encoding="utf-8")
        (directory / "study-review.zip").write_bytes(archive)
        outcomes.append({"case": name, "observation_status": checks["status"], "cost_residual": cost["residual"],
                         "review_state": report["review_state"], "checks": checks["checks"]})
    result = {"scope": "SYNTHETIC_CALIBRATION_REHEARSAL", "frozen_candidate_fingerprint": frozen["frozen_fingerprint"],
              "heldout_batch_id": heldout["batch_id"], "outcomes": outcomes,
              "empirical_calibration_complete": False, "production_authorized": False,
              "limitations": ["Synthetic records and preselected toy criteria only; no statistical generalization claim.",
                              "One parameter fitted, three fitting batches and one held-out batch; no real facility evidence.",
                              "Candidate fingerprint checks consistency, not an authenticated timestamp or approval.",
                              "Individual study bundles preserve held-out evidence; retain the entire run directory for fitting provenance."]}
    (output / "rehearsal-summary.json").write_bytes(encode(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New run directory")
    args = parser.parse_args()
    try:
        print(json.dumps(run_rehearsal(args.output), indent=2))
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, csv.Error) as exc:
        parser.exit(2, f"Synthetic calibration rehearsal error: {exc}\n")


if __name__ == "__main__":
    main()
