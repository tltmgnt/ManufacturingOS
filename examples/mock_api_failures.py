"""Expected-failure rehearsal for a local mock API; no real integration acceptance."""
import argparse
from html import escape
import json
from pathlib import Path

from .mock_enterprise_api import MockAPIRejected, run_api_rehearsal
from .temporary_use_case import encode

CASES = {"invalid_credential": (401, "HTTP 401"), "insufficient_scope": (403, "HTTP 403"),
         "throttled": (429, "HTTP 429"), "unavailable": (503, "HTTP 503"),
         "stale_revision": (200, "source revision"), "hash_mismatch": (200, "ETag")}


def run_failures(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for name, (status, expected_error) in CASES.items():
        target = output / name
        try:
            run_api_rehearsal(target, failure=name)
        except MockAPIRejected as exc:
            if expected_error not in str(exc) or exc.audit != [{"method": "GET", "path": "/v1/batches/demo-batch-001/export", "status": status}]:
                raise RuntimeError("Source failure was not rejected as expected") from exc
            if target.exists():
                raise RuntimeError("Rejected source created a study output directory")
            results.append({"case": name, "software_check": "PASS", "source_result": "REJECTED_AS_EXPECTED",
                            "error": str(exc), "request_audit": exc.audit, "model_executed": False,
                            "production_authorized": False})
        else:
            raise RuntimeError("A deliberately failing source unexpectedly produced study outputs")
    summary = {"scope": "SYNTHETIC_API_FAILURE_REHEARSAL", "status": "EXPECTED_FAILURES_DETECTED",
               "cases": results, "automatic_retries": False, "live_integration_complete": False,
               "empirical_calibration_complete": False, "production_authorized": False}
    (output / "failure-scorecard.json").write_bytes(encode(summary))
    rows = "".join("<tr><th scope=\"row\">" + escape(row["case"]) + "</th><td>" + escape(row["error"]) +
                   "</td><td>Rejected before study</td></tr>" for row in results)
    (output / "index.html").write_text('''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mock API failure rehearsal</title>
<style>body{font:16px/1.6 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#16263a}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:.7rem;border-bottom:1px solid #ccd4df;overflow-wrap:anywhere}
@media(max-width:600px){table,thead,tbody,tr,th,td{display:block}thead{display:none}tr{border:1px solid #ccd4df;margin:1rem 0}}
</style></head><body><h1>Mock API failure rehearsal</h1>
<p>Synthetic local faults only. Each PASS means a deliberately bad source was rejected,
not that an integration or production plan was accepted.</p>
<table><thead><tr><th scope="col">Case</th><th scope="col">Observed error</th><th scope="col">Outcome</th></tr></thead><tbody>'''+rows+'''</tbody></table>
<p>Every case made one GET, performed no automatic retry and created no study output.
Invalid credentials simulate a rejected credential; no real identity-provider expiration or renewal is tested.</p>
<p><a href="failure-scorecard.json">Full failure scorecard and request audits</a></p>
</body></html>''', encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New rehearsal directory")
    args = parser.parse_args()
    try:
        result = run_failures(args.output)
    except Exception as exc:
        parser.exit(2, f"Mock API failure rehearsal error: {exc}\n")
    print(json.dumps({"scope": result["scope"], "status": result["status"], "cases": len(result["cases"])}))


if __name__ == "__main__":
    main()
