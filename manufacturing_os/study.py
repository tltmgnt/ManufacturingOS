"""Revision-bound integrated study reports; no manufacturing approval authority."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

from .calculations import Scenario, estimate, fields, nonempty
from .engine import Orchestrator
from .evidence import assess_evidence
from .experiments import simulate, validate_references
from .models import ManufacturingInput, digest
from .simulation import simulate_batch
from .sources import verify_sources

STUDY_VERSION = "integrated-study-1.0"


def binding(package: dict, scenario: dict) -> dict:
    """Create the explicit content binding after a caller reviews both inputs."""
    return {"input_fingerprint": ManufacturingInput.from_dict(package).fingerprint,
            "scenario_fingerprint": digest(asdict(Scenario.from_dict(scenario)))}


def run_study(spec: dict) -> dict:
    optional = set(spec) & {"evidence_policy", "evidence_snapshot"} if isinstance(spec, dict) else set()
    fields(spec, {"schema_version", "study_id", "revision", "manufacturing_input", "scenario", "binding",
                  "simulation", "uncertainty", "reference_suite"} | optional, "study")
    if "evidence_snapshot" in optional and "evidence_policy" not in optional:
        raise ValueError("evidence_snapshot requires evidence_policy")
    if spec["schema_version"] != "1.0":
        raise ValueError("unsupported study schema")
    for key in ("study_id", "revision"):
        nonempty(spec[key], key)
    package = ManufacturingInput.from_dict(spec["manufacturing_input"])
    scenario = Scenario.from_dict(spec["scenario"])
    expected_binding = binding(spec["manufacturing_input"], spec["scenario"])
    fields(spec["binding"], set(expected_binding), "binding")
    if spec["binding"] != expected_binding:
        raise ValueError("stale study binding: input or scenario changed; review and explicitly rebind")
    # A bounded study has one declared batch demand. Do not infer a calendar
    # conversion from Phase 1's generic demand units.
    if package.demand.unit != "piece" or package.demand.value != scenario.target_good_units:
        raise ValueError("study requires demand in piece equal to scenario target_good_units")
    simulation_optional = {"downtime"} if isinstance(spec["simulation"],dict) and "downtime" in spec["simulation"] else set()
    fields(spec["simulation"], {"seed", "batch_size"} | simulation_optional, "simulation configuration")
    fields(spec["uncertainty"], {"seed", "samples", "ranges"}, "uncertainty configuration")
    # Every component receives a copy of the one authoritative scenario.
    simulation_input = {"schema_version": "1.0", "simulation_id": spec["study_id"]+"/batch",
                        "revision": spec["revision"], "scenario": deepcopy(spec["scenario"]), **spec["simulation"]}
    uncertainty_input = {"schema_version": "1.0", "experiment_id": spec["study_id"]+"/uncertainty",
                         "revision": spec["revision"], "scenario": deepcopy(spec["scenario"]), **spec["uncertainty"]}
    batch = simulate_batch(simulation_input)
    exploration = simulate(uncertainty_input)
    references = None
    if spec["reference_suite"] is not None:
        references = validate_references(spec["reference_suite"])
        # A passing but unrelated suite cannot be presented as this model input's
        # reference coverage. Cases may additionally include alternate scenarios.
        covered = any(digest(asdict(Scenario.from_dict(case["scenario"]))) == expected_binding["scenario_fingerprint"]
                      for case in spec["reference_suite"]["cases"])
        if not covered:
            raise ValueError("reference suite does not cover this study scenario")
    plan = Orchestrator().run(package)
    calculation = estimate(scenario)
    findings = [{"code": "UNVALIDATED_MODELS", "severity": "REVIEW", "component": "study",
                 "message": "Calculations, simulation, and assumed input distributions require qualified review and facility calibration."},
                {"code": "MOCK_SPECIALISTS", "severity": "REVIEW", "component": "plan",
                 "message": "A1-A9 outputs remain mocks; the study adds advisory analyses without replacing specialist conclusions."}]
    if spec["simulation"].get("downtime"):
        findings.append({"code": "DOWNTIME_SCOPE", "severity": "REVIEW", "component": "simulation",
                         "message": "Scheduled downtime affects only finite-batch simulation; steady-state cost/capacity and uncertainty estimates exclude these windows."})
    if plan.verification.status == "FAIL":
        findings.append({"code": "PLAN_VERIFICATION_FAILED", "severity": "BLOCKING", "component": "plan",
                         "message": "Original plan verification failed; inspect plan verification findings and conflict records."})
    if not calculation["capacity_feasible"]:
        findings.append({"code": "ESTIMATED_CAPACITY_SHORTFALL", "severity": "BLOCKING", "component": "estimate",
                         "message": "Target exceeds capacity under the configured steady-state model assumptions."})
    if not batch["target_met"]:
        findings.append({"code": "SIMULATED_TARGET_MISS", "severity": "BLOCKING", "component": "simulation",
                         "message": "This seeded finite-batch simulation does not complete the target good units by the horizon."})
    if references is None:
        findings.append({"code": "NO_REFERENCE_SUITE", "severity": "REVIEW", "component": "references",
                         "message": "No synthetic arithmetic reference suite was supplied."})
    elif references["status"] == "FAIL":
        findings.append({"code": "REFERENCE_CHECK_FAILED", "severity": "BLOCKING", "component": "references",
                         "message": "One or more supplied arithmetic reference checks failed."})
    else:
        findings.append({"code": "SYNTHETIC_REFERENCE_ONLY", "severity": "REVIEW", "component": "references",
                         "message": "Passing synthetic reference checks establish arithmetic agreement, not facility validation."})
    evidence_report = assess_evidence(spec["manufacturing_input"], spec["evidence_policy"]) if "evidence_policy" in optional else None
    if evidence_report is not None:
        if evidence_report["uncovered_requirements"]:
            findings.append({"code": "EVIDENCE_COVERAGE_GAPS", "severity": "BLOCKING", "component": "evidence",
                             "message": "Requirements lack evidence meeting the configured metadata policy: "+", ".join(evidence_report["uncovered_requirements"])})
        elif evidence_report["ineligible_record_count"]:
            findings.append({"code": "INELIGIBLE_EVIDENCE_RECORDS", "severity": "REVIEW", "component": "evidence",
                             "message": "Some records fail metadata checks; every requirement has at least one eligible record."})
        findings.append({"code": "EVIDENCE_METADATA_ONLY", "severity": "REVIEW", "component": "evidence",
                         "message": "Evidence policy checks do not verify source identity, content hashes, claim truth, or substantive conformance."})
    source_report = None
    if "evidence_snapshot" in optional:
        source_report = verify_sources(spec["manufacturing_input"], spec["evidence_snapshot"])
        combined = {claim: sorted(set(refs) & set(source_report["hash_matched_coverage"][claim]))
                    for claim, refs in evidence_report["eligible_coverage"].items()}
        source_report["combined_eligible_coverage"] = combined
        gaps = sorted(claim for claim, refs in combined.items() if not refs)
        source_report["combined_uncovered_requirements"] = gaps
        if gaps:
            findings.append({"code": "EVIDENCE_SOURCE_GAPS", "severity": "BLOCKING", "component": "sources",
                             "message": "Requirements lack a single record with both eligible metadata and matching captured content: "+", ".join(gaps)})
        elif source_report["unmatched_record_count"]:
            findings.append({"code": "UNMATCHED_CAPTURED_RECORDS", "severity": "REVIEW", "component": "sources",
                             "message": "Some captured-content records do not match; every requirement has another record meeting both checks."})
        findings.append({"code": "CAPTURED_CONTENT_ONLY", "severity": "REVIEW", "component": "sources",
                         "message": "Captured-byte hash matches do not authenticate source origin or establish claim truth or conformance."})
    blocking = any(finding["severity"] == "BLOCKING" for finding in findings)
    result = {"schema_version": "1.0", "study_version": STUDY_VERSION, "study_id": spec["study_id"],
            "study_revision": spec["revision"], "study_fingerprint": digest(spec), "input": deepcopy(spec),
            "binding": expected_binding, "plan": asdict(plan), "estimate": calculation,
            "simulation": batch, "uncertainty": exploration, "reference_report": references,
            "findings": findings, "review_state": "REVISION_REQUIRED" if blocking else "HUMAN_REVIEW",
            "required_approvals": list(plan.required_approvals), "approval_state": "PENDING_HUMAN_REVIEW",
            "production_authorized": False}
    if evidence_report is not None:
        result["evidence_report"] = evidence_report
    if source_report is not None:
        result["source_report"] = source_report
    return result


def reconstruct_report(report: dict) -> dict:
    """Reject stale or altered reports before downstream consumption."""
    if not isinstance(report, dict) or "input" not in report:
        raise ValueError("expected a complete integrated study report")
    reconstructed = run_study(report["input"])
    if digest(report) != digest(reconstructed):
        raise ValueError("study report differs from reconstruction; regenerate with the matching model version")
    return reconstructed


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Run a revision-bound advisory manufacturing study")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, help="Create a complete report without overwriting an existing file")
    args = parser.parse_args(argv)
    try:
        report = run_study(json.loads(args.input.read_text(encoding="utf-8")))
        encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+"\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as file:
                file.write(encoded)
        else:
            print(encoded, end="")
        return 1 if report["review_state"] == "REVISION_REQUIRED" else 0
    except (ValueError, TypeError, KeyError, OSError, OverflowError, ZeroDivisionError) as exc:
        print(f"Study error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
