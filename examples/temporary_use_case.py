"""Run an explicitly synthetic bracket demo with cost disagreement and target shortfall cases.

From the repository root: python -m examples.temporary_use_case --output runs/demo
"""
import argparse
import base64
from copy import deepcopy
import hashlib
from html import escape
import json
from pathlib import Path

from manufacturing_os.bundle import build_bundle, verify_bundle
from manufacturing_os.models import ManufacturingInput, digest
from manufacturing_os.review import render_review
from manufacturing_os.study import binding, preflight_study, run_study


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def render_summary(summary):
    """Offline landing page; case paths are fixed by the runner, values escaped."""
    paths = {"baseline": "baseline", "cost-disagreement": "cost-disagreement",
             "target-miss": "target-miss", "capacity-remedy": "capacity-remedy"}
    rows = []
    for case in summary["cases"]:
        path = paths[case["case"]]
        cost = case["cost_comparison"]
        values = [case["case"], case["observation_status"],
                  f'{case["good_by_horizon"]} / {case["target_good_units"]}',
                  "Met" if case["target_met"] else "MISSED",
                  f'{cost["model_mean"]["value"]:g} / {cost["observed"]["value"]:g}',
                  f'{cost["residual"]["value"]:+g}', case["review_state"]]
        labels = ["Case", "Reference", "Good / target at 5 h", "Target",
                  "Model / reference cost (USD)", "Cost residual (USD)", "Review state"]
        cells = "".join('<td data-label="' + escape(label, quote=True) + '"><span>' +
                        escape(str(value)) + '</span></td>' for label, value in zip(labels, values))
        rows.append("<tr>" + cells + f'<td data-label="Files"><span><a href="{path}/study-review.html">Review</a> · '
                    f'<a href="{path}/study-report.json">JSON</a> · '
                    f'<a href="{path}/study-review.zip">Bundle</a></span></td></tr>')
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Synthetic bracket demo — case comparison</title>
<style>
body {font-family:system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#16263a;background:#f6f8fb;line-height:1.5}
h1 {line-height:1.2} .notice {background:#fff0c2;border-left:5px solid #946200;padding:1rem}
.scroll {overflow-x:auto} table {border-collapse:collapse;width:100%;background:white}
th,td {padding:.8rem;text-align:left;border-bottom:1px solid #ccd4df;vertical-align:top}
th {background:#e6edf5} a {color:#124e96} a:focus {outline:3px solid #946200}
caption {text-align:left;font-weight:600;margin:1rem 0} small {color:#374c65}
@media (max-width: 1000px) {
 .scroll {overflow:visible} table,caption,tbody,tr {display:block}
 thead {position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
 tbody tr {margin:1rem 0;border:1px solid #ccd4df;border-radius:.4rem;overflow:hidden}
 td {display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:.8rem}
 td::before {content:attr(data-label);font-weight:600}
 td span {min-width:0;overflow-wrap:anywhere} td:first-child {background:#e6edf5}
 caption {width:auto} td:last-child {border-bottom:0}
}
</style></head><body>
<h1>Synthetic bracket demo</h1>
<p class="notice"><strong>Synthetic data only.</strong> Empirical calibration is incomplete.
Production authorization is false for every case. Software agreement does not approve a production plan.</p>
<p>Three brackets pass through cutting and finishing. Compare reference agreement,
cost disagreement, a production shortfall and an assumed capacity remedy at the five-hour deadline.</p>
<div class="scroll"><table><caption>Case outcomes · costs and residuals in USD</caption>
<thead><tr><th scope="col">Case</th><th scope="col">Reference</th><th scope="col">Good / target at 5 h</th>
<th scope="col">Target</th><th scope="col">Model / reference cost</th><th scope="col">Cost residual</th>
<th scope="col">Review state</th><th scope="col">Files</th></tr></thead><tbody>
""" + "\n".join(rows) + """
</tbody></table></div>
<h2>Interpret the outcomes</h2>
<ul><li>Baseline: agreement still requires human review.</li>
<li>Cost disagreement: the deliberately declared 220 USD reference differs from the 225 USD model by +5 USD.</li>
<li>Target miss: reference agreement coexists with a shortfall; only two of three requested brackets finish by hour five.</li>
<li>Capacity remedy: assuming a second identical finishing machine, all three finish by hour five.
The 225 USD processing cost excludes equipment purchase, installation and extra fixed costs;
resource availability and staffing are unverified.</li></ul>
<p>Each bundle has been checked for content consistency and reconstruction. This does not establish source authenticity or approval.</p>
<p><a href="summary.json">Machine-readable summary</a> · <a href="README.txt">Run notes</a></p>
<small>Offline review. Keep this page with its case directories so relative links work.</small>
</body></html>
"""


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
    remedy = deepcopy(target_miss)
    remedy["revision"] = "synthetic-capacity-remedy-1"
    remedy["scenario"]["revision"] = "capacity-remedy-1"
    remedy["scenario"]["operations"][1]["machines"] = 2
    remedy["scenario"]["assumptions"].append(
        "Synthetic capacity remedy assumes a second identical finishing machine and sufficient staffing; "
        "purchase, installation and additional fixed costs are excluded and resource availability is unverified.")
    remedy_reference = deepcopy(target_reference)
    remedy_reference["metrics"]["good_by_horizon"]["value"] = 3
    remedy_reference["metrics"]["wip_at_horizon"]["value"] = 0
    remedy_reference["metrics"]["batch_completion_time"]["value"] = 5
    remedy_reference["context"]["scenario_fingerprint"] = binding(
        remedy["manufacturing_input"], remedy["scenario"])["scenario_fingerprint"]
    bind_synthetic_reference(remedy, remedy_reference)


    # Refuse to mix this run with previous results or overwrite existing files.
    output.mkdir(parents=True, exist_ok=False)
    summary = {"scope": "SYNTHETIC_WORKFLOW_DEMO", "empirical_calibration_complete": False,
               "production_authorized": False, "cases": []}
    for name, spec, expected in [("baseline", baseline, "PASS"),
                                 ("cost-disagreement", disagreement, "FAIL"),
                                 ("target-miss", target_miss, "PASS"),
                                 ("capacity-remedy", remedy, "PASS")]:
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
        if name == "capacity-remedy" and (not simulation["target_met"] or
                simulation["good_by_horizon"] != 3 or simulation["wip_at_horizon"] != 0 or
                simulation["batch_completion_time"]["value"] != 5 or
                cost["model_mean"]["value"] != 225 or report["review_state"] != "HUMAN_REVIEW"):
            raise RuntimeError("Synthetic capacity remedy did not produce its hand-derived outcome")
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
                                 "batch_completion_time": simulation["batch_completion_time"],
                                 "finishing_machines": spec["scenario"]["operations"][1]["machines"],
                                 "cost_comparison": cost, "bundle_status": verification["status"]})
    (output / "summary.json").write_bytes(encode(summary))
    (output / "index.html").write_text(render_summary(summary), encoding="utf-8")
    (output / "README.txt").write_text(
        "SYNTHETIC WORKFLOW DEMO — not facility data or empirical calibration.\n"
        "baseline: reference agreement; human review remains required.\n"
        "cost-disagreement: deliberately changed synthetic reference; expected FAIL, residual +5 USD.\n"
        "target-miss: reference PASS but only 2 of 3 requested brackets by hour 5; revision required.\n"
        "capacity-remedy: assumes a second finishing machine; 3 of 3 by hour 5; capex/fixed additions excluded.\n"
        "Open index.html to compare all cases and follow links to their reviews.\n"
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
