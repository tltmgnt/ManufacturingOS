"""One-command synthetic pilot rehearsal; no actual pilot or approval is claimed."""
import argparse
from html import escape
import json
from pathlib import Path

from manufacturing_os._version import __version__
from .mock_enterprise_api import run_api_rehearsal
from .synthetic_calibration_rehearsal import run_rehearsal
from .synthetic_export_intake import run_intake
from .temporary_use_case import encode, run_demo


def render_index(summary):
    rows = "".join("<tr><th scope=\"row\">" + escape(row["check"]) + "</th><td>" +
                   escape(row["result"]) + "</td></tr>" for row in summary["software_checks"])
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ManufacturingOS — synthetic pilot rehearsal</title>
<style>body{font:16px/1.6 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#16263a;background:#f6f8fb}
a{color:#124e96}a:focus{outline:3px solid #946200}.notice{background:#fff0c2;border-left:5px solid #946200;padding:1rem}
table{border-collapse:collapse;width:100%;background:white}th,td{padding:.7rem;text-align:left;border-bottom:1px solid #ccd4df;overflow-wrap:anywhere}
th{width:70%}h1{line-height:1.2}li{margin:.5rem 0}</style></head><body>
<h1>Synthetic pilot rehearsal</h1>
<p class="notice"><strong>Software rehearsal only.</strong> No real facility data, live enterprise
integration or actual shadow pilot is evaluated. Empirical calibration is incomplete.
Production authorization remains false.</p>
<h2>Software checks</h2><table><thead><tr><th scope="col">Check</th><th scope="col">Result</th></tr></thead><tbody>
""" + rows + """</tbody></table>
<h2>Review the results</h2><ol>
<li><a href="planning/index.html">Planning cases</a>: reference agreement, cost discrepancy, target shortfall and assumed capacity remedy.</li>
<li><a href="intake/study-review.html">Read-only synthetic export intake</a> · <a href="intake/intake-provenance.json">Source provenance</a>.</li>
<li><a href="api/study-review.html">Read-only mock ERP/MES API</a> ·
<a href="api/transport-provenance.json">Transport provenance</a> ·
<a href="api/mock-request-audit.json">Request audit</a>.</li>
<li>Held-out evaluation: <a href="calibration/baseline/study-review.html">baseline</a> and
<a href="calibration/candidate/study-review.html">frozen candidate</a> ·
<a href="calibration/frozen-candidate.json">Fitting configuration</a> ·
<a href="calibration/rehearsal-summary.json">All residuals and limitations</a>.</li></ol>
<h2>Real-world milestones remain open</h2><ul>
<li>Authorized facility data, representative calibration and qualified acceptance.</li>
<li>Controlled read-only enterprise integration, identity/access controls and security review.</li>
<li>An actual shadow pilot with measured outcomes and qualified acceptance.</li></ul>
<p>A successful software run includes expected failures: the cost discrepancy and
shortfall must remain visible. A candidate matching a tiny synthetic held-out batch
does not establish generalization. Additional machine capacity is an assumption;
equipment purchase and added fixed costs are excluded.</p>
<p><a href="rehearsal-scorecard.json">Machine-readable scorecard</a> · <a href="run-status.json">Run status</a></p>
<p>Keep the whole directory together. Individual study bundles do not include every
fitting file; the calibration directory retains the full fitting/held-out record.</p>
</body></html>
"""


def run_pilot(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    phase = "planning"
    status = {"scope": "SYNTHETIC_PILOT_REHEARSAL", "status": "RUNNING", "phase": phase,
              "production_authorized": False, "empirical_calibration_complete": False}
    status_path = output / "run-status.json"
    status_path.write_bytes(encode(status))
    try:
        planning = run_demo(output / "planning")
        phase = "intake"
        status_path.write_bytes(encode({**status, "phase": phase}))
        intake = run_intake(output / "intake")
        phase = "api"
        status_path.write_bytes(encode({**status, "phase": phase}))
        api = run_api_rehearsal(output / "api")
        if api["status"] != "PASS" or api["request_count"] != 1 or api["live_integration_complete"]:
            raise RuntimeError("Mock API rehearsal did not preserve read-only synthetic scope")
        phase = "calibration"
        status_path.write_bytes(encode({**status, "phase": phase}))
        calibration = run_rehearsal(output / "calibration")
        expected = [("baseline", "PASS", True), ("cost-disagreement", "FAIL", True),
                    ("target-miss", "PASS", False), ("capacity-remedy", "PASS", True)]
        actual = [(row["case"], row["observation_status"], row["target_met"]) for row in planning["cases"]]
        if actual != expected or intake["observation_status"] != "PASS" or intake["bundle_status"] != "VERIFIED_CONTENT":
            raise RuntimeError("Component outcomes differ from the declared synthetic expectations")
        if [(row["case"], row["observation_status"]) for row in calibration["outcomes"]] != [("baseline", "FAIL"), ("candidate", "PASS")]:
            raise RuntimeError("Held-out comparison did not retain expected baseline/candidate outcomes")
        summary = {"scope": "SYNTHETIC_PILOT_REHEARSAL", "software_version": __version__,
                   "status": "SOFTWARE_REHEARSAL_PASSED", "production_authorized": False,
                   "empirical_calibration_complete": False, "actual_shadow_pilot_complete": False,
                   "live_integration_complete": False,
                   "software_checks": [{"check": name, "result": "PASS"} for name in
                       ["Four planning outcomes, including expected discrepancy and shortfall",
                        "Raw-to-derived synthetic CSV intake and verified bundle",
                        "Read-only loopback API transport with retained provenance",
                        "Separate fitting and held-out evaluation with frozen candidate",
                        "Baseline failure and candidate agreement retained without production authorization"]],
                   "planning": planning, "intake": intake, "api": api, "calibration": calibration}
        if any(result["production_authorized"] or result["empirical_calibration_complete"]
               for result in (planning, intake, api, calibration)):
            raise RuntimeError("A synthetic component incorrectly claimed real-world acceptance")
        phase = "summary"
        (output / "rehearsal-scorecard.json").write_bytes(encode(summary))
        (output / "index.html").write_text(render_index(summary), encoding="utf-8")
        status_path.write_bytes(encode({**status, "status": "COMPLETE", "phase": "complete"}))
        return summary
    except Exception:
        # Preserve partial outputs for diagnosis; never report an incomplete run as PASS.
        status_path.write_bytes(encode({**status, "status": "FAILED", "phase": phase}))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New rehearsal directory")
    args = parser.parse_args()
    try:
        summary = run_pilot(args.output)
    except Exception as exc:
        parser.exit(2, f"Synthetic pilot rehearsal error: {exc}\n")
    print(json.dumps({key: summary[key] for key in ("scope", "status", "software_version", "production_authorized",
                     "empirical_calibration_complete", "live_integration_complete", "actual_shadow_pilot_complete")}, indent=2))
    print(f"Open {args.output / 'index.html'} for the consolidated review.")


if __name__ == "__main__":
    main()
