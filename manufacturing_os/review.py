"""Offline, escaped HTML summaries of reproducible study reports."""
from html import escape
import json
from pathlib import Path
from typing import Any

from .models import digest
from .notes import assess_notes
from .study import reconstruct_report

EXPORT_VERSION = "html-review-1.0"


def text(value: Any) -> str:
    return escape(str(value), quote=True)


def measurement(value: dict) -> str:
    return f"{text(format(value['value'], '.6g'))} <span class=unit>{text(value['unit'])}</span>"


def table(caption: str, headers: list[str], rows: list[list[str]]) -> str:
    # Callers provide escaped cells; table labels are escaped here.
    heading = "".join(f"<th scope=col>{text(label)}</th>" for label in headers)
    body = "".join("<tr>"+"".join(f"<td>{cell}</td>" for cell in row)+"</tr>" for row in rows)
    return f"<div class=table-wrap><table><caption>{text(caption)}</caption><thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div>"


def render_review(report: dict, notes: dict | None = None) -> str:
    reconstruct_report(report)
    package = report["input"]["manufacturing_input"]
    scenario = report["input"]["scenario"]
    estimate, batch, uncertainty = report["estimate"], report["simulation"], report["uncertainty"]
    findings = sorted(report["findings"], key=lambda finding: finding["severity"] != "BLOCKING")
    findings_html = "".join(
        f"<li class={'blocking' if f['severity']=='BLOCKING' else 'review'}><strong>{text(f['severity'])}: {text(f['code'])}</strong>"
        f"<p>{text(f['message'])} <span class=unit>Component: {text(f['component'])}</span></p></li>"
        for f in findings)
    summary = table("Study identity", ["Field", "Value"], [
        ["Study / revision", text(report["study_id"])+" / "+text(report["study_revision"])],
        ["Product / design revision", text(package["product_id"])+" / "+text(package["design_revision"])],
        ["Package / revision", text(package["package_id"])+" / "+text(package["revision"])],
        ["Facility / revision", text(package["facility"]["facility_id"])+" / "+text(package["facility"]["revision"])],
        ["Demand", measurement(package["demand"])],
        ["Scenario / revision", text(scenario["scenario_id"])+" / "+text(scenario["revision"])],
        ["Source reference", text(scenario["source_reference"])],
    ])
    estimates = table("Steady-state model estimates", ["Metric", "Value"], [
        ["Unit cost", measurement(estimate["unit_cost"])], ["Total cost", measurement(estimate["total_cost"])],
        ["Expected starts", measurement(estimate["expected_starts"])], ["Expected scrap", measurement(estimate["expected_scrap"])],
        ["Route yield", measurement(estimate["route_yield"])],
        ["Good-output capacity", measurement(estimate["expected_good_capacity"])],
        ["Bottleneck operation", text(estimate["bottleneck_operation"])],
        ["Capacity feasible under model assumptions", text(estimate["capacity_feasible"])],
    ])
    capacity = table("Operation capacity estimates", ["Operation", "Required hours", "Available hours", "Utilization", "Good capacity"], [
        [text(row["operation_id"]),measurement(row["required_machine_time"]),measurement(row["available_machine_time"]),
         measurement(row["utilization"]),measurement(row["expected_good_capacity"])] for row in estimate["operations"]])
    batch_summary = table("Finite-batch outcomes at the reporting horizon", ["Metric", "Value"], [
        ["Reporting horizon",measurement(batch["horizon"])], ["Released batch",text(batch["batch_size"])+" piece"],
        ["Good by horizon",text(batch["good_by_horizon"])+" piece"],
        ["Scrapped by horizon",text(batch["scrapped_by_horizon"])+" piece"],
        ["WIP at horizon",text(batch["wip_at_horizon"])+" piece"],
        ["Target met in this seeded run",text(batch["target_met"])],
        ["Eventual batch completion (may exceed horizon)",measurement(batch["batch_completion_time"])],
    ])
    calendar_html = ""
    if "normalized_downtime" in batch:
        calendar_html = "<p>Scheduled windows affect this finite-batch simulation; steady-state cost/capacity and uncertainty estimates exclude these windows.</p>"+table("Scheduled downtime (half-open intervals)", ["Operation", "Machine", "Start", "End"], [
            [text(row["operation_id"]), text(row["machine_id"]), measurement(row["start"]), measurement(row["end"])] for row in batch["normalized_downtime"]])
    queues = table("Finite-batch queue summary", ["Operation", "Queued at horizon", "Processing at horizon", "Peak queue", "Full-batch mean wait"], [
        [text(row["operation_id"]),text(row["queued_at_horizon"]),text(row["processing_at_horizon"]),
         text(row["peak_queued_by_horizon"]),measurement(row["mean_full_batch_queue_wait"])] for row in batch["operations"]])
    range_rows = []
    operation_inputs = {op["operation_id"]: op for op in scenario["operations"]}
    for row in report["input"]["uncertainty"]["ranges"]:
        field = operation_inputs[row["operation_id"]][row["parameter"]]
        unit = field["unit"] if isinstance(field, dict) else "fraction"
        range_rows.append([text(row["operation_id"]), text(row["parameter"]),
                           text(row["low"]), text(row["high"]), text(unit)])
    ranges = table("Assumed independent uniform ranges", ["Operation", "Parameter", "Low", "High", "Unit"], range_rows)
    sampled = table("Sampled model output summaries", ["Metric", "P05", "Median", "P95", "Mean"], [
        [text(metric),measurement(row["p05"]),measurement(row["p50"]),measurement(row["p95"]),measurement(row["mean"])]
        for metric,row in sorted(uncertainty["summary"].items())])
    reference = report["reference_report"]
    if reference is None:
        reference_html = "<p>No reference suite supplied.</p>"
    else:
        reference_html = f"<p>{text(reference['status'])}: {text(reference['passed_checks'])} / {text(reference['check_count'])} checks passed. Synthetic arithmetic only.</p>"
        for case in reference["cases"]:
            reference_html += f"<h3>{text(case['case_id'])} — {text(case['status'])}</h3><p>{text(case['objective'])}</p><p>Reference: {text(case['source_reference'])}, revision {text(case['reference_revision'])}.</p>"
            reference_html += table("Reference residuals", ["Metric", "Expected", "Actual", "Residual", "Absolute tolerance", "Result"], [
                [text(check["metric"]),measurement(check["expected"]),measurement(check["actual"]),measurement(check["residual"]),
                 text(check["expected"]["absolute_tolerance"]),text(check["status"])] for check in case["checks"]])
    plan = report["plan"]
    specialist = table("Mock specialist results", ["Agent", "Status", "Open issues"], [
        [text(aid),text(result["status"]),"<br>".join(text(issue) for issue in result["open_issues"])] for aid,result in sorted(plan["results"].items())])
    plan_findings = "<ul>"+"".join(f"<li>{text(value)}</li>" for value in plan["verification"]["findings"])+"</ul>"
    conflicts = "<pre>"+text(json.dumps(plan["verification"]["conflicts"],indent=2))+"</pre>" if plan["verification"]["conflicts"] else "<p>No recorded hard-constraint conflicts.</p>"
    evidence = table("Input evidence registry", ["ID", "Source", "Owner", "Revision", "Captured (UTC)", "Claims"], [
        [text(row["evidence_id"]),text(row["source_uri"]),text(row["source_owner"]),text(row["revision"]),text(row["captured_at"]),text(", ".join(row["claim_ids"]))]
        for row in package["evidence"]]) if package["evidence"] else "<p>No input evidence records supplied.</p>"
    policy_html = ""
    if "evidence_report" in report:
        policy_result = report["evidence_report"]
        policy = policy_result["policy"]
        policy_html = f"<h3>Evidence metadata policy: {text(policy_result['status'])}</h3><p>Policy {text(policy_result['policy_id'])}, revision {text(policy_result['policy_revision'])}; as of {text(policy['as_of'])}; maximum capture age {measurement(policy['max_age'])}.</p>"
        policy_html += table("Evidence policy records", ["Evidence", "Capture age", "Metadata eligible", "Issues", "Declared hash"], [
            [text(row["evidence_id"]), measurement(row["age"]), text(row["metadata_eligible"]), text(", ".join(row["issues"]) or "None"), text(row["declared_hash_status"])]
            for row in policy_result["records"]])
        policy_html += table("Eligible requirement coverage", ["Requirement", "Evidence IDs"], [
            [text(claim), text(", ".join(refs) or "UNCOVERED")] for claim, refs in sorted(policy_result["eligible_coverage"].items())])
        policy_html += "<ul>"+"".join(f"<li>{text(item)}</li>" for item in policy_result["limitations"])+"</ul>"
    if "source_report" in report:
        sources = report["source_report"]
        policy_html += f"<h3>Captured source content: {text(sources['status'])}</h3><p>Snapshot {text(sources['snapshot_id'])}, revision {text(sources['snapshot_revision'])}; {text(sources['captured_total_bytes'])} captured bytes.</p>"
        policy_html += table("Captured content verification", ["Evidence", "Status", "Bytes", "Declared SHA-256", "Captured SHA-256"], [
            [text(row["evidence_id"]), text(row["status"]), text(row["captured_size_bytes"]), text(row["declared_sha256"]), text(row["captured_sha256"])] for row in sources["records"]])
        policy_html += table("Combined metadata and content coverage", ["Requirement", "Evidence IDs"], [
            [text(claim), text(", ".join(refs) or "UNCOVERED")] for claim,refs in sorted(sources["combined_eligible_coverage"].items())])
        policy_html += "<ul>"+"".join(f"<li>{text(item)}</li>" for item in sources["limitations"])+"</ul>"
    assumptions = ""
    for title, values in [("Estimate",estimate["assumptions"]),("Finite-batch simulation",batch["assumptions"]),("Uncertainty exploration",uncertainty["limitations"])]:
        assumptions += f"<h3>{text(title)}</h3><ul>"+"".join(f"<li>{text(value)}</li>" for value in values)+"</ul>"
    versions = table("Versions and content provenance", ["Field", "Value"], [
        ["Exporter version",text(EXPORT_VERSION)], ["Study version",text(report["study_version"])],
        ["Calculation model",text(estimate["model_version"])], ["Simulator",text(batch["simulator_version"])],
        ["Experiment",text(uncertainty["experiment_version"])], ["Study fingerprint",text(report["study_fingerprint"])],
        ["Report content hash",text(digest(report))], ["Bound input fingerprint",text(report["binding"]["input_fingerprint"])],
        ["Bound scenario fingerprint",text(report["binding"]["scenario_fingerprint"])],
    ])
    approvals = "<ul>"+"".join(f"<li>{text(role)} — pending human review</li>" for role in report["required_approvals"])+"</ul>"
    notes_html = ""
    if notes is not None:
        assessment = assess_notes(report, notes)
        notes_html = f"<section><h2>Reviewer feedback: {text(assessment['state'])}</h2><p>Names and roles are declared, not authenticated. Notes do not grant approval.</p>"
        notes_html += table("Revision-bound reviewer notes", ["ID", "Reviewer / role", "UTC timestamp", "Disposition", "Finding", "Comment"], [
            [text(entry["note_id"]), text(entry["reviewer"])+" / "+text(entry["role"]), text(entry["timestamp"]), text(entry["disposition"]), text(entry["finding_code"] or "Study-wide"), text(entry["comment"])] for entry in notes["entries"]])
        notes_html += "<ul>"+"".join(f"<li>{text(value)}</li>" for value in assessment["limitations"])+"</ul></section>"
    body = f"""<header><p class=eyebrow>ManufacturingOS · advisory study</p><h1>{text(report['study_id'])}</h1>
<p class=state>{text(report['review_state'])}</p><p class=notice>Production authorization: FALSE. All approvals remain pending. Models are unvalidated; real facility calibration is outstanding.</p></header>
<nav aria-label='Report sections'><a href='#findings'>Findings</a><a href='#estimates'>Estimates</a><a href='#batch'>Finite batch</a><a href='#uncertainty'>Uncertainty</a><a href='#references'>References</a><a href='#plan'>Plan</a><a href='#provenance'>Provenance</a></nav>
<main><section id=findings><h2>Review findings</h2><ul class=findings>{findings_html}</ul>{summary}</section>{notes_html}
<section id=estimates><h2>Capacity and cost estimates</h2><p>Expected-value steady-state model; fractional starts are intentional. Costs are estimates in the declared currency.</p>{estimates}{capacity}</section>
<section id=batch><h2>Finite-batch simulation</h2><p>Seed {text(report['input']['simulation']['seed'])}. This is one seeded outcome. Queue waits and eventual completion include events beyond the horizon.</p>{batch_summary}{calendar_html}{queues}</section>
<section id=uncertainty><h2>Uncertainty exploration</h2><p>{text(uncertainty['sample_count'])} samples; seed {text(report['input']['uncertainty']['seed'])}. {text(uncertainty['feasible_samples'])} sampled scenarios fit steady-state capacity. This fraction is not a calibrated manufacturing risk probability. Percentiles describe sampled model outputs, not confidence intervals.</p>{ranges}{sampled}</section>
<section id=references><h2>Synthetic reference checks</h2>{reference_html}</section>
<section id=plan><h2>Original plan verification: {text(plan['verification']['status'])}</h2>{plan_findings}<h3>Conflicts</h3>{conflicts}{specialist}<h3>Required approval roles</h3>{approvals}</section>
<section><h2>Evidence and assumptions</h2>{evidence}{policy_html}{assumptions}</section>
<section id=provenance><h2>Provenance</h2><p>Report content was reconstructed from the saved study input and matched before rendering. This is a reproducibility check, not a signature, human approval, or proof that source claims are true. Retain the source JSON for full timelines and per-sample audit records.</p>{versions}
<details><summary>Exact study input</summary><pre>{text(json.dumps(report['input'],indent=2,sort_keys=True))}</pre></details></section></main>
<footer>ManufacturingOS · {text(EXPORT_VERSION)} · Offline review summary. No approval actions are available.</footer>"""
    return """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width, initial-scale=1'>
<meta http-equiv=Content-Security-Policy content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>ManufacturingOS study review</title><style>
:root{font-family:system-ui,sans-serif;color:#172c39;background:#eef2f4;line-height:1.5}*{box-sizing:border-box}body{max-width:1160px;margin:auto;padding:32px}header,section{background:white;border:1px solid #d2dce1;border-radius:10px;padding:28px;margin-bottom:22px}h1{font-size:2rem;margin:4px 0;overflow-wrap:anywhere}h2{font-size:1.35rem;margin-top:0}h3{font-size:1.05rem}.eyebrow,.unit,footer{color:#526570}.eyebrow{text-transform:uppercase;letter-spacing:.08em;font-size:.8rem}.state{font-size:1.1rem;font-weight:750}.notice{border-left:5px solid #b66a00;background:#fff5e5;padding:14px}nav{display:flex;gap:18px;flex-wrap:wrap;margin:0 0 22px}a{color:#075a80}a:focus-visible,summary:focus-visible{outline:3px solid #b66a00;outline-offset:4px}.findings{list-style:none;padding:0}.findings li{border-left:4px solid #b66a00;background:#fff8ec;padding:12px 16px;margin-bottom:12px}.findings .blocking{border-color:#b62929;background:#fff0f0}.findings p{margin:4px 0}table{width:100%;border-collapse:collapse;font-size:.92rem;margin:16px 0 24px}caption{text-align:left;font-weight:700;margin-bottom:8px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #d8e0e5;padding:10px;overflow-wrap:anywhere}th{background:#edf3f6}tr:nth-child(even){background:#f7f9fa}.table-wrap{overflow-x:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.8rem;background:#f2f5f7;padding:16px}summary{cursor:pointer}footer{font-size:.85rem;padding:6px 0 30px}section{scroll-margin-top:16px}@media(max-width:650px){body{padding:12px}header,section{padding:16px}th,td{padding:7px}h1{font-size:1.6rem}}@media print{body{max-width:none;padding:0;background:white;font-size:10pt}header,section{border:0;border-radius:0;padding:8px 0}nav,details{display:none}table{font-size:8pt}tr,li{break-inside:avoid}h2,h3{break-after:avoid}.table-wrap{overflow:visible}footer{padding:8px 0}}
</style></head><body>"""+body+"</body></html>\n"


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Export a reconstructed study report as offline HTML")
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="Create a new HTML file; existing files are rejected")
    parser.add_argument("--notes", type=Path, help="Optional reviewer notes bound to this exact report")
    args = parser.parse_args(argv)
    try:
        output = render_review(json.loads(args.report.read_text(encoding="utf-8")),
                               json.loads(args.notes.read_text(encoding="utf-8")) if args.notes else None)
        with args.output.open("x", encoding="utf-8") as file:
            file.write(output)
    except (ValueError, TypeError, KeyError, OSError, OverflowError, ZeroDivisionError) as exc:
        print(f"Review export error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
