"""Run the complete synthetic offline suite without real-system access."""
import argparse
from html import escape
import json
from pathlib import Path

from manufacturing_os._version import __version__
from .offline_edge_cases import run_edges
from .offline_invariant_sweep import run_sweep
from .offline_repeatability import run_repeatability
from .rehearsal_provenance import SOURCE_ROOT
from .temporary_use_case import encode


def render_suite(result):
    rows = "".join('<tr><th scope="row">' + escape(row["component"]) + '</th><td data-label="Check"><span>' +
                   escape(row["software_check"]) + '</span></td><td data-label="Observed result"><span>' + escape(row["observed_status"]) + '</span></td></tr>'
                   for row in result["components"])
    overall = '<p><strong>Overall software result: <span id="overall-result">' + escape(result["status"]) + '</span></strong></p>'
    overall += '<p>Captured sources: ' + ('consistent' if result["source_consistent"] else 'DIFFERENT — inspect the scorecard') + '</p>'
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>ManufacturingOS — offline synthetic suite</title>
<style>body{font:16px/1.6 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#16263a;background:#f6f8fb}
h1{line-height:1.2}.notice{background:#fff0c2;border-left:5px solid #946200;padding:1rem}
table{border-collapse:collapse;table-layout:fixed;width:100%;background:white}th,td{padding:.7rem;text-align:left;border-bottom:1px solid #ccd4df;overflow-wrap:anywhere}
a{color:#124e96}a:focus{outline:3px solid #946200}li{margin:.6rem 0}
@media(max-width:600px){table,tbody,tr{display:block}thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
tbody tr{margin:1rem 0;border:1px solid #ccd4df;border-radius:.4rem;overflow:hidden}
tbody th{display:block;background:#e6edf5}tbody td{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:.8rem}
tbody td::before{content:attr(data-label);font-weight:600}td span{min-width:0;overflow-wrap:anywhere}td:last-child{border-bottom:0}}
</style></head><body>
<h1>Offline synthetic suite</h1><p class="notice"><strong>No real-system reads.</strong>
Only bundled synthetic fixtures and a loopback mock API are used. Real calibration,
enterprise acceptance and an actual shadow pilot remain open. Production authorization is false.</p>
<h2>Software checks</h2>'''+overall+'''<table><thead><tr><th scope="col">Component</th><th scope="col">Check</th><th scope="col">Observed result</th></tr></thead><tbody>'''+rows+'''</tbody></table>
<h2>Review the evidence</h2><ol>
<li>Complete pilot rehearsal: <a href="repeatability/first/index.html">first run</a> and
<a href="repeatability/second/index.html">second run</a> · <a href="repeatability/repeatability.json">72-file repeatability comparison</a>.</li>
<li><a href="edges/edge-scorecard.json">Six hand-derived scheduling/cost edge cases</a>, including target misses and undefined unit costs.</li>
<li><a href="invariants/invariant-scorecard.json">54-configuration invariant sweep</a> with 162 simulations.</li></ol>
<p>Each pilot run includes planning alternatives, CSV/mock API intake, rejected source/transport
faults, separate fitting/held-out evaluation and reconstructed bundles. The edge cases and
invariant sweep are bounded software checks, not empirical accuracy or probability estimates.</p>
<p><a href="offline-suite.json">Suite scorecard and source fingerprints</a> · <a href="run-status.json">Run status</a></p>
<p>Keep the entire directory tree together. Expected target misses or source rejections can
coexist with software PASS. Inspect component results and limitations before interpreting outcomes.</p>
</body></html>'''


def run_suite(output: Path):
    if any(output.resolve().is_relative_to((SOURCE_ROOT / name).resolve()) for name in ("examples", "manufacturing_os")):
        raise ValueError("Output must be outside captured source directories")
    output.mkdir(parents=True, exist_ok=False)
    phase = "repeatability"
    status_file = output / "run-status.json"
    status_file.write_bytes(encode({"status": "RUNNING", "phase": phase}))
    try:
        repeatability = run_repeatability(output / "repeatability")
        phase = "edges"
        status_file.write_bytes(encode({"status": "RUNNING", "phase": phase}))
        edges = run_edges(output / "edges")
        phase = "invariants"
        status_file.write_bytes(encode({"status": "RUNNING", "phase": phase}))
        invariants = run_sweep(output / "invariants")
        phase = "validation"
        if any(value.get(key) is not False for value in (repeatability, edges, invariants)
               for key in ("production_authorized", "empirical_calibration_complete", "live_integration_complete")):
            raise RuntimeError("A synthetic component claimed real-world authorization or completion")
        components = [{"component": name, "observed_status": value["status"],
                       "software_check": "PASS" if value["status"] == expected else "FAIL"}
                      for name, value, expected in [("Repeatability", repeatability, "REPEATABLE"),
                                                    ("Edge cases", edges, "PASS"), ("Invariant sweep", invariants, "PASS")]]
        fingerprints = [*repeatability["source_fingerprints"], edges["source_fingerprint"], invariants["source_fingerprint"]]
        source_consistent = len(set(fingerprints)) == 1
        result = {"scope": "OFFLINE_SYNTHETIC_SUITE", "software_version": __version__,
                  "status": "PASS" if source_consistent and all(row["software_check"] == "PASS" for row in components) else "FAIL",
                  "components": components, "source_consistent": source_consistent, "source_fingerprints": fingerprints,
                  "production_authorized": False, "live_integration_complete": False,
                  "empirical_calibration_complete": False, "actual_shadow_pilot_complete": False,
                  "limitations": ["Fully synthetic software coverage only; no real system or facility data is accessed.",
                                  "Individual pilot directories retain their own verifiable manifests and fitting/source provenance.",
                                  "Repeatability and bounded invariants do not establish measured accuracy or production acceptance."]}
        phase = "summary"
        (output / "offline-suite.json").write_bytes(encode(result))
        (output / "index.html").write_text(render_suite(result), encoding="utf-8")
        status_file.write_bytes(encode({"status": "COMPLETE" if result["status"] == "PASS" else "FAIL", "phase": "complete"}))
        return result
    except Exception:
        status_file.write_bytes(encode({"status": "FAILED", "phase": phase}))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New offline-suite directory")
    args = parser.parse_args()
    try:
        result = run_suite(args.output)
    except Exception as exc:
        parser.exit(2, f"Offline suite error: {exc}\n")
    print(json.dumps({"scope": result["scope"], "status": result["status"], "source_consistent": result["source_consistent"]}))
    print(f"Open {args.output / 'index.html'} for the complete offline review.")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
