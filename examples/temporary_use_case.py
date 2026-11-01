"""Run an explicitly synthetic bracket demo and a deliberate disagreement case.

From the repository root: python -m examples.temporary_use_case --output runs/demo
"""
import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from manufacturing_os.bundle import build_bundle, verify_bundle
from manufacturing_os.models import ManufacturingInput
from manufacturing_os.review import render_review
from manufacturing_os.study import binding, preflight_study, run_study


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def run_demo(output: Path) -> dict:
    root = Path(__file__).resolve().parent
    baseline = json.loads((root / "observation-study.json").read_text())
    disagreement = deepcopy(baseline)
    disagreement["revision"] = "synthetic-cost-disagreement-1"
    reference = json.loads((root / "observation-reference.json").read_text())
    # Deliberately author a NEW synthetic reference, never repair real evidence.
    reference["metrics"]["full_batch_total_cost"]["value"] = 220
    raw = encode(reference)
    disagreement["manufacturing_input"]["evidence"][0]["content_hash"] = hashlib.sha256(raw).hexdigest()
    disagreement["evidence_snapshot"]["files"][0]["content_base64"] = base64.b64encode(raw).decode()
    disagreement["evidence_snapshot"]["input_fingerprint"] = ManufacturingInput.from_dict(disagreement["manufacturing_input"]).fingerprint
    disagreement["binding"] = binding(disagreement["manufacturing_input"], disagreement["scenario"])

    # Refuse to mix this run with previous results or overwrite existing files.
    output.mkdir(parents=True, exist_ok=False)
    summary = {"scope": "SYNTHETIC_WORKFLOW_DEMO", "empirical_calibration_complete": False,
               "production_authorized": False, "cases": []}
    for name, spec, expected in [("baseline", baseline, "PASS"),
                                 ("cost-disagreement", disagreement, "FAIL")]:
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
                                 "cost_comparison": cost, "bundle_status": verification["status"]})
    (output / "summary.json").write_bytes(encode(summary))
    (output / "README.txt").write_text(
        "SYNTHETIC WORKFLOW DEMO — not facility data or empirical calibration.\n"
        "baseline: reference agreement; human review remains required.\n"
        "cost-disagreement: deliberately changed synthetic reference; expected FAIL, residual +5 USD.\n"
        "Each case contains an offline study-review.html and verified study-review.zip.\n"
        "Production authorization remains false in both cases.\n", encoding="utf-8")
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
