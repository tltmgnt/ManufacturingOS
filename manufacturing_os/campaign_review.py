"""Self-contained HTML campaign overview with fixed local case links."""
from html import escape
import json

from .campaign import reconstruct_campaign
from .models import digest

EXPORT_VERSION = "campaign-review-1.0"


def text(value: object) -> str:
    return escape(str(value),quote=True)


def render_campaign_review(report: dict) -> str:
    reconstruct_campaign(report)
    rows,details = [],[]
    for index,case in enumerate(report["cases"],1):
        prefix = f"cases/{index:03d}/"
        actual = case["actual"] or {}
        if case["study_report"] is None:
            links = f"<a href='{prefix}error.json'>Execution error</a>"
        else:
            links = f"<a href='{prefix}study-review.html'>Study review</a> · <a href='{prefix}study-report.json'>JSON</a>"
        rows.append("<tr>"+"".join(f"<td>{value}</td>" for value in [
            text(case["case_id"]),text(case["status"]),text(case["execution_status"]),
            text(case["expected"]["review_state"]),text(actual.get("review_state","Unavailable")),
            text(actual.get("observation_status") or "Not configured"),links])+"</tr>")
        mismatch = json.dumps(case["mismatches"],indent=2,sort_keys=True)
        error = json.dumps(case["error"],indent=2,sort_keys=True) if case["error"] else "No execution error."
        details.append(f"<details><summary>{text(case['case_id'])} — {text(case['status'])}: expectations and findings</summary>"
                       f"<p>Expected blocking codes: {text(', '.join(case['expected']['blocking_codes']) or 'None')}.</p>"
                       f"<p>Actual blocking codes: {text(', '.join(actual.get('blocking_codes',[])) or 'None / unavailable')}.</p>"
                       f"<pre>{text(mismatch)}</pre><pre>{text(error)}</pre></details>")
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width, initial-scale=1'>
<meta http-equiv=Content-Security-Policy content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>ManufacturingOS campaign review</title><style>
:root{{font-family:system-ui,sans-serif;line-height:1.5;color:#18313e;background:#edf2f5}}*{{box-sizing:border-box}}body{{max-width:1200px;margin:auto;padding:28px}}header,section{{background:white;border:1px solid #cddae1;border-radius:10px;padding:24px;margin:0 0 20px}}h1{{font-size:1.8rem;margin:5px 0;overflow-wrap:anywhere}}h2{{font-size:1.25rem}}.eyebrow{{color:#536773;text-transform:uppercase;font-size:.8rem;letter-spacing:.07em}}.notice{{padding:14px;background:#fff5df;border-left:5px solid #a96800}}.status{{font-size:1.1rem;font-weight:750}}table{{border-collapse:collapse;width:100%;font-size:.9rem}}caption{{font-weight:700;text-align:left;padding:12px 0}}th,td{{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #d7e0e5;overflow-wrap:anywhere}}th{{background:#edf3f6}}.table-wrap{{overflow-x:auto}}a{{color:#075d86}}a:focus-visible,summary:focus-visible{{outline:3px solid #a96800;outline-offset:3px}}details{{padding:12px 0;border-bottom:1px solid #dae2e7}}summary{{cursor:pointer;font-weight:650;overflow-wrap:anywhere}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f7;padding:12px;font-size:.8rem}}footer{{color:#536773;font-size:.85rem}}@media(max-width:650px){{body{{padding:10px}}header,section{{padding:16px}}h1{{font-size:1.5rem}}}}@media print{{body{{background:white;padding:0;max-width:none}}header,section{{border:0;padding:8px 0}}tr{{break-inside:avoid}}h2{{break-after:avoid}}.table-wrap{{overflow:visible}}}}
</style></head><body><header><p class=eyebrow>ManufacturingOS · software scenario campaign</p><h1>{text(report['campaign_id'])}</h1>
<p class=status>Expectation result: {text(report['status'])}</p><p>{text(report['passed_cases'])} / {text(report['case_count'])} cases matched; {text(report['failed_cases'])} failed; {text(report['execution_errors'])} execution errors.</p>
<p class=notice>{text(report['revision_required_studies'])} completed studies require revision. Campaign PASS means software expectations matched, including intentionally blocked studies. Production authorization: FALSE. Formal approvals remain pending.</p></header>
<main><section><h2>Case overview</h2><div class=table-wrap><table><caption>Expected behavior versus actual study state</caption><thead><tr><th scope=col>Case</th><th scope=col>Expectation result</th><th scope=col>Execution</th><th scope=col>Expected review state</th><th scope=col>Actual review state</th><th scope=col>Observation checks</th><th scope=col>Local reports</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
<section><h2>Expectation details</h2>{''.join(details)}</section><section><h2>Scope and provenance</h2><ul>{''.join('<li>'+text(value)+'</li>' for value in report['limitations'])}</ul>
<p>Campaign revision: {text(report['campaign_revision'])}; runner: {text(report['campaign_version'])}; exporter: {text(EXPORT_VERSION)}.</p>
<pre>Campaign fingerprint: {text(report['campaign_fingerprint'])}\nReport content hash: {text(digest(report))}</pre>
<p>Keep campaign-report.json and manifest.json for exact data and content checks. Local links point only to indexed files in this bundle. Content reconstruction is not a signature or source authentication.</p></section></main>
<footer>Offline review only · {text(EXPORT_VERSION)} · No approval actions.</footer></body></html>\n"""
