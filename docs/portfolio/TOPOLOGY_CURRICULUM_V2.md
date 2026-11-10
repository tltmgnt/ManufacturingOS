# Topology compatibility and curriculum v2 — ManufacturingOS

Version 2 adapts the explicit-molecular-graph teaching pattern to this repository's actual role. This is documentation and a learning/decision framework; it introduces no mathematical engine, runtime dependency or operational permission.

## Repository decision

| Question | Repository-specific answer |
| --- | --- |
| Architectural role | application |
| Minimum useful mathematics | Directed process/dependency graphs and finite-state failure models |
| Relationships to preserve | Manufacturing steps, mock integration states and rejection evidence |
| Concrete operation / capstone | Trace the mock API failure rehearsal for stale_revision and hash_mismatch; explain why a rejected mock response is useful evidence |
| Necessity and scope boundary | A local mock does not establish facility calibration, enterprise acceptance or equipment safety |

The decision is a source-based recommendation, not measured proof that a new specialty improves this repository. Start with the existing implementation and compare any proposed abstraction against a simpler alternative.

## Six-criterion compatibility scorecard

Complete one scorecard per proposed candidate and per concrete operation. Leave unmeasured entries unknown. Scores are human judgments from 0 (no fit) to 5 (strong evidenced fit); unknown is not zero. Do not sum an incomplete card. A total out of 30 is a heuristic, not adoption approval, and feasibility or necessity can veto a high total.

| Criterion | Score | Required evidence |
| --- | --- | --- |
| Structural compatibility | Not yet scored | Map the repository objects and the relationships above without losing direction, labels, units or missingness. |
| Transformation support | Not yet scored | Demonstrate the capstone operation on accepted and rejected inputs. |
| Invariant preservation | Not yet scored | State the property preserved and supply a counterexample or perturbation. |
| Computational feasibility | Not yet scored | Measure size, time and memory on bounded fixtures; record limits. |
| Integration compatibility | Not yet scored | Verify existing schemas, APIs and neighboring contracts remain compatible. |
| Mathematical necessity | Not yet scored | Compare with directed process/dependency graphs and finite-state failure models and explain the additional capability, if any. |

## Curriculum

Prerequisites: basic programming, sets, functions and graph vocabulary. Work in six competency-gated sessions, approximately 60–90 minutes each; empirical evaluation is a separate research activity.

| Session | Learning objective | Exercise | Completion evidence |
| --- | --- | --- | --- |
| 1. Model | Identify manufacturing steps, mock integration states and rejection evidence. | Draw a minimal valid example and one excluded relationship. | Annotated object/relation inventory with explicit assumptions. |
| 2. Contract | Distinguish schema validity from substantive correctness. | Trace validation and propose malformed, missing and boundary inputs. | Input-to-rejection table grounded in current source. |
| 3. Operation | Explain directed process/dependency graphs and finite-state failure models. | Trace the mock API failure rehearsal for stale_revision and hash_mismatch; explain why a rejected mock response is useful evidence. | Hand trace compared with existing software, or a clearly labeled specification when no runtime exists. |
| 4. Preservation | State what a transformation must preserve. | Rename identifiers, reorder records, then alter one meaningful relation; predict each effect under the actual contract. | Separate invariant, expected change and unsupported transformation. |
| 5. Comparison | Justify mathematical necessity and cost. | Complete the six-criterion card for the existing approach and one proposed alternative; record unknowns honestly. | Evidence-backed recommendation with baseline and explicit veto conditions. |
| 6. Reproduction | Communicate the bounded result. | Reproduce the capstone using existing offline fixtures and record software version, inputs, outputs and limitations. | Reviewable notebook or report distinguishing computation, replay, independent evaluation and authorization. |

## Source-linked reading laboratory

The table is a guided selection of source lines, not an assertion that the whole repository is covered. Line numbers refer to the inspected source blob `e1ad479bd85b157fc29d758992ee45849e195e3c` in [examples/mock_api_failures.py](../../examples/mock_api_failures.py). Recheck anchors after source changes.

| Line | Statement | Learning check |
| --- | --- | --- |
| [1](../../examples/mock_api_failures.py#L1) | `"""Expected-failure rehearsal for a local mock API; no real integration acceptance."""` | Explain the stated scope and identify a claim the implementation does not establish. |
| [2](../../examples/mock_api_failures.py#L2) | `import argparse` | Identify the dependency and explain which operation needs it. |
| [3](../../examples/mock_api_failures.py#L3) | `from html import escape` | Identify the dependency and explain which operation needs it. |
| [4](../../examples/mock_api_failures.py#L4) | `import json` | Identify the dependency and explain which operation needs it. |
| [5](../../examples/mock_api_failures.py#L5) | `from pathlib import Path` | Identify the dependency and explain which operation needs it. |
| [7](../../examples/mock_api_failures.py#L7) | `from .mock_enterprise_api import MockAPIRejected, run_api_rehearsal` | Identify the dependency and explain which operation needs it. |
| [8](../../examples/mock_api_failures.py#L8) | `from .temporary_use_case import encode` | Identify the dependency and explain which operation needs it. |
| [10](../../examples/mock_api_failures.py#L10) | `CASES = {"invalid_credential": (401, "HTTP 401"), "insufficient_scope": (403, "HTTP 403"),` | Explain the statement, track its state change and predict its effect on the worked example. |
| [11](../../examples/mock_api_failures.py#L11) | `"throttled": (429, "HTTP 429"), "unavailable": (503, "HTTP 503"),` | Explain the statement, track its state change and predict its effect on the worked example. |
| [12](../../examples/mock_api_failures.py#L12) | `"stale_revision": (200, "source revision"), "hash_mismatch": (200, "ETag"), "timeout": (None, "timed out"),` | Explain the exact bytes bound by the digest and why hashing does not authenticate the source. |
| [13](../../examples/mock_api_failures.py#L13) | `"truncated": (200, "byte count"), "connection_closed": (None, "closed before response")}` | Explain the statement, track its state change and predict its effect on the worked example. |
| [16](../../examples/mock_api_failures.py#L16) | `def run_failures(output: Path) -> dict:` | State the input/output contract and trace one normal and one failing case. |
| [17](../../examples/mock_api_failures.py#L17) | `output.mkdir(parents=True, exist_ok=False)` | Trace discovery order and state the reachability or shortest-path invariant. |
| [18](../../examples/mock_api_failures.py#L18) | `results = []` | Explain the statement, track its state change and predict its effect on the worked example. |
| [19](../../examples/mock_api_failures.py#L19) | `for name, (status, expected_error) in CASES.items():` | State the loop invariant, termination argument and one boundary case. |
| [20](../../examples/mock_api_failures.py#L20) | `target = output / name` | Explain the statement, track its state change and predict its effect on the worked example. |
| [21](../../examples/mock_api_failures.py#L21) | `try:` | Explain the statement, track its state change and predict its effect on the worked example. |
| [22](../../examples/mock_api_failures.py#L22) | `run_api_rehearsal(target, failure=name)` | Explain the statement, track its state change and predict its effect on the worked example. |
| [23](../../examples/mock_api_failures.py#L23) | `except MockAPIRejected as exc:` | Construct the triggering input and explain why rejection preserves the contract. |
| [24](../../examples/mock_api_failures.py#L24) | `if expected_error not in str(exc) or exc.audit != [{"method": "GET", "path": "/v1/batches/demo-batch-001/export", "status": status}]:` | Trace both branches and identify the condition that changes the result. |
| [25](../../examples/mock_api_failures.py#L25) | `raise RuntimeError("Source failure was not rejected as expected") from exc` | Construct the triggering input and explain why rejection preserves the contract. |
| [26](../../examples/mock_api_failures.py#L26) | `if target.exists():` | Trace both branches and identify the condition that changes the result. |
| [27](../../examples/mock_api_failures.py#L27) | `raise RuntimeError("Rejected source created a study output directory")` | Construct the triggering input and explain why rejection preserves the contract. |
| [28](../../examples/mock_api_failures.py#L28) | `results.append({"case": name, "software_check": "PASS", "source_result": "REJECTED_AS_EXPECTED",` | Explain the statement, track its state change and predict its effect on the worked example. |
| [29](../../examples/mock_api_failures.py#L29) | `"error": str(exc), "request_audit": exc.audit, "model_executed": False,` | Explain the statement, track its state change and predict its effect on the worked example. |
| [30](../../examples/mock_api_failures.py#L30) | `"production_authorized": False})` | Explain the statement, track its state change and predict its effect on the worked example. |
| [31](../../examples/mock_api_failures.py#L31) | `else:` | Trace both branches and identify the condition that changes the result. |
| [32](../../examples/mock_api_failures.py#L32) | `raise RuntimeError("A deliberately failing source unexpectedly produced study outputs")` | Construct the triggering input and explain why rejection preserves the contract. |
| [33](../../examples/mock_api_failures.py#L33) | `summary = {"scope": "SYNTHETIC_API_FAILURE_REHEARSAL", "status": "EXPECTED_FAILURES_DETECTED",` | Explain the statement, track its state change and predict its effect on the worked example. |
| [34](../../examples/mock_api_failures.py#L34) | `"cases": results, "automatic_retries": False, "live_integration_complete": False,` | Explain the statement, track its state change and predict its effect on the worked example. |
| [35](../../examples/mock_api_failures.py#L35) | `"empirical_calibration_complete": False, "production_authorized": False}` | Explain the statement, track its state change and predict its effect on the worked example. |
| [36](../../examples/mock_api_failures.py#L36) | `(output / "failure-scorecard.json").write_bytes(encode(summary))` | Explain the statement, track its state change and predict its effect on the worked example. |
| [37](../../examples/mock_api_failures.py#L37) | `rows = "".join("<tr><th scope=\"row\">" + escape(row["case"]) + "</th><td>" + escape(row["error"]) +` | Explain the statement, track its state change and predict its effect on the worked example. |
| [38](../../examples/mock_api_failures.py#L38) | `"</td><td>Rejected before study</td></tr>" for row in results)` | State the loop invariant, termination argument and one boundary case. |
| [39](../../examples/mock_api_failures.py#L39) | `(output / "index.html").write_text('''<!doctype html><html lang="en"><head><meta charset="utf-8">` | Explain the statement, track its state change and predict its effect on the worked example. |
| [40](../../examples/mock_api_failures.py#L40) | `<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mock API failure rehearsal</title>` | Explain the statement, track its state change and predict its effect on the worked example. |
| [41](../../examples/mock_api_failures.py#L41) | `<style>body{font:16px/1.6 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#16263a}` | Explain the statement, track its state change and predict its effect on the worked example. |
| [42](../../examples/mock_api_failures.py#L42) | `table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:.7rem;border-bottom:1px solid #ccd4df;overflow-wrap:anywhere}` | Explain the statement, track its state change and predict its effect on the worked example. |
| [43](../../examples/mock_api_failures.py#L43) | `@media(max-width:600px){table,thead,tbody,tr,th,td{display:block}thead{display:none}tr{border:1px solid #ccd4df;margin:1rem 0}}` | Explain the statement, track its state change and predict its effect on the worked example. |
| [44](../../examples/mock_api_failures.py#L44) | `</style></head><body><h1>Mock API failure rehearsal</h1>` | Explain the statement, track its state change and predict its effect on the worked example. |
| [45](../../examples/mock_api_failures.py#L45) | `<p>Synthetic local faults only. Each PASS means a deliberately bad source was rejected,` | Explain the statement, track its state change and predict its effect on the worked example. |
| [46](../../examples/mock_api_failures.py#L46) | `not that an integration or production plan was accepted.</p>` | Explain the statement, track its state change and predict its effect on the worked example. |
| [47](../../examples/mock_api_failures.py#L47) | `<table><thead><tr><th scope="col">Case</th><th scope="col">Observed error</th><th scope="col">Outcome</th></tr></thead><tbody>'''+rows+'''</tbody></table>` | Explain the statement, track its state change and predict its effect on the worked example. |
| [48](../../examples/mock_api_failures.py#L48) | `<p>Every case made one GET, performed no automatic retry and created no study output.` | Explain the statement, track its state change and predict its effect on the worked example. |
| [49](../../examples/mock_api_failures.py#L49) | `Invalid credentials simulate a rejected credential; no real identity-provider expiration or renewal is tested.</p>` | Explain the statement, track its state change and predict its effect on the worked example. |
| [50](../../examples/mock_api_failures.py#L50) | `<p><a href="failure-scorecard.json">Full failure scorecard and request audits</a></p>` | Explain the statement, track its state change and predict its effect on the worked example. |
| [51](../../examples/mock_api_failures.py#L51) | `</body></html>''', encoding="utf-8")` | Explain the statement, track its state change and predict its effect on the worked example. |
| [52](../../examples/mock_api_failures.py#L52) | `return summary` | Predict the returned value and distinguish a computed result from authorization. |
| [55](../../examples/mock_api_failures.py#L55) | `def main():` | State the input/output contract and trace one normal and one failing case. |
| [56](../../examples/mock_api_failures.py#L56) | `parser = argparse.ArgumentParser(description=__doc__)` | Explain the statement, track its state change and predict its effect on the worked example. |
| [57](../../examples/mock_api_failures.py#L57) | `parser.add_argument("--output", type=Path, required=True, help="New rehearsal directory")` | Explain the statement, track its state change and predict its effect on the worked example. |
| [58](../../examples/mock_api_failures.py#L58) | `args = parser.parse_args()` | Explain the statement, track its state change and predict its effect on the worked example. |
| [59](../../examples/mock_api_failures.py#L59) | `try:` | Explain the statement, track its state change and predict its effect on the worked example. |
| [60](../../examples/mock_api_failures.py#L60) | `result = run_failures(args.output)` | Explain the statement, track its state change and predict its effect on the worked example. |
| [61](../../examples/mock_api_failures.py#L61) | `except Exception as exc:` | Construct the triggering input and explain why rejection preserves the contract. |
| [62](../../examples/mock_api_failures.py#L62) | `parser.exit(2, f"Mock API failure rehearsal error: {exc}\n")` | Explain the statement, track its state change and predict its effect on the worked example. |
| [63](../../examples/mock_api_failures.py#L63) | `print(json.dumps({"scope": result["scope"], "status": result["status"], "cases": len(result["cases"])}))` | Explain the statement, track its state change and predict its effect on the worked example. |
| [66](../../examples/mock_api_failures.py#L66) | `if __name__ == "__main__":` | Trace both branches and identify the condition that changes the result. |
| [67](../../examples/mock_api_failures.py#L67) | `main()` | Explain the statement, track its state change and predict its effect on the worked example. |
## Assessment and verification

A learner must explain the model, trace the capstone, identify a counterexample and state the scope boundary. Assess these four competencies equally; a numerical score cannot compensate for an unsupported scientific or operational claim.

Relevant existing checks:

- [tests/test_batch_costs.py](../../tests/test_batch_costs.py)
- [tests/test_bundle.py](../../tests/test_bundle.py)
- [tests/test_calculations.py](../../tests/test_calculations.py)

Follow [README](../../README.md) for environment and installed-package instructions. Read scripts before execution; source-reading exercises do not authorize provider calls, model downloads, live orders, hardware actions or messages. Synthetic fixtures establish software behavior only. This documentation change does not report those exercises as already executed.

## Interoperability and adoption gate

Retain explicit domain contracts. Shared assurance records should refer to domain evidence and its assumptions rather than relabeling graph reachability, homology, statistical calibration and epistemic acceptance as interchangeable quantities. The canonical ResearchOs controller remains owned by ResearchOs; this curriculum does not create another controller fork.

Adopt additional mathematics only after a versioned experiment demonstrates a useful operation, the scorecard has evidence, the simpler baseline is inadequate and existing conformance checks remain satisfied. A local mock does not establish facility calibration, enterprise acceptance or equipment safety.
