"""Run an explicitly synthetic bracket demo with cost disagreement and target shortfall cases.

From the repository root: python -m examples.temporary_use_case --output runs/demo
"""
import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from manufacturing_os.bundle import build_bundle, verify_bundle
from manufacturing_os.models import ManufacturingInput, digest
from manufacturing_os.review import render_review
from manufacturing_os.study import binding, preflight_study, run_study


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def bind_synthetic_reference(spec, reference):
    """Bind newly authored synthetic bytes; never use this to repair real evidence."""
    raw = encode(reference)
    spec["manufacturing_input"]["evidence"][0]["content_hash"] = hashlib.sha256(raw).hexdigest()
    spec["evidence_snapshot"]["files"][0]["content_base64"] = base64.b64encode(raw).decode()
    spec["evidence_snapshot"]["input_fingerprint"] = ManufacturingInput.from_dict(spec["manufacturing_input"]).fingerprint
    spec["binding"] = binding(spec["manufacturing_input"], spec["scenario"])


def run_demo(output: Path) -> dict:
    root = Path(__file__).resolve().parent
    baseline = json.loads((root / "observation-study.json").read_text())
    disagreement = deepcopy(baseline)
    disagreement["revision"] = "synthetic-cost-disagreement-1"
    reference = json.loads((root / "observation-reference.json").read_text())
    # Deliberately author a NEW synthetic reference, never repair real evidence.
    reference["metrics"]["full_batch_total_cost"]["value"] = 220
    bind_synthetic_reference(disagreement, reference)
    target_miss = deepcopy(baseline)
    target_miss["revision"] = "synthetic-target-miss-1"
    target_miss["scenario"]["target_good_units"] = 3
    target_miss["manufacturing_input"]["demand"]["value"] = 3
    target_reference = json.loads((root / "observation-reference.json").read_text())
    # Counts and costs are unchanged: only the requested output increases.
    target_reference["context"]["scenario_fingerprint"] = binding(
        target_miss["manufacturing_input"], target_miss["scenario"])["scenario_fingerprint"]
    target_reference["context"]["simulation_config_fingerprint"] = digest(target_miss["simulation"])
    bind_synthetic_reference(target_miss, target_reference)

    # Refuse to mix this run with previous results or overwrite existing files.
    output.mkdir(parents=True, exist_ok=False)
    summary = {"scope": "SYNTHETIC_WORKFLOW_DEMO", "empirical_calibration_complete": False,
               "production_authorized": False, "cases": []}
    for name, spec, expected in [("baseline", baseline, "PASS"),
                                 ("cost-disagreement", disagreement, "FAIL"),
                                 ("target-miss", target_miss, "PASS")]:
        directory = output / name
        directory.mkdir()
        preflight = preflight_study(spec)
        report = run_study(spec)
        checks = report["observation_report"]
        cost = next(row for row in checks["checks"] if row["metric"] == "full_batch_total_cost")
        if checks["status"] != expected or report["production_authorized"]:
            raise RuntimeError("Synthetic case produced an unexpected result")
        if name == "cost-disagreement" and (cost["residual"]["value"] != 5 or report["review_state"] != "REVISION_REQUIRED"):
            raise RuntimeError("Synthetic disagreement was not retained for review")
        simulation = report["simulation"]
        if name == "target-miss" and (simulation["target_met"] or
                simulation["good_by_horizon"] != 2 or simulation["target_good_units"] != 3 or
                report["review_state"] != "REVISION_REQUIRED" or
                "SIMULATED_TARGET_MISS" not in {row["code"] for row in report["findings"]}):
            raise RuntimeError("Reference agreement hid the synthetic production shortfall")
        archive = build_bundle(spec)
        verification = verify_bundle(archive)
        for filename, value in [("study-input.json", spec), ("preflight.json", preflight),
                                ("study-report.json", report), ("observation-checks.json", checks),
                                ("bundle-verification.json", verification)]:
            (directory / filename).write_bytes(encode(value))
        (directory / "study-review.html").write_text(render_review(report), encoding="utf-8")
        (directory / "study-review.zip").write_bytes(archive)
        summary["cases"].append({"case": name, "reference_kind": checks["reference_kind"],
                                 "observation_status": checks["status"], "review_state": report["review_state"],
                                 "target_good_units": simulation["target_good_units"],
                                 "good_by_horizon": simulation["good_by_horizon"],
                                 "target_met": simulation["target_met"],
                                 "cost_comparison": cost, "bundle_status": verification["status"]})
    (output / "summary.json").write_bytes(encode(summary))
    (output / "README.txt").write_text(
        "SYNTHETIC WORKFLOW DEMO — not facility data or empirical calibration.\n"
        "baseline: reference agreement; human review remains required.\n"
        "cost-disagreement: deliberately changed synthetic reference; expected FAIL, residual +5 USD.\n"
        "target-miss: reference PASS but only 2 of 3 requested brackets by hour 5; revision required.\n"
        "Each case contains an offline study-review.html and verified study-review.zip.\n"
        "Production authorization remains false in all cases.\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Synthetic bracket workflow demo; no real-data calibration")
    parser.add_argument("--output", type=Path, required=True, help="New output directory; existing paths rejected")
    args = parser.parse_args()
    try:
        summary = run_demo(args.output)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        parser.exit(2, f"Synthetic demo error: {exc}\n")
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
