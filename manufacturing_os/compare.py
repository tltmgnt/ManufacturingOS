"""Descriptive, revision-aware comparison of reconstructable study reports."""
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from .models import digest
from .study import reconstruct_report

COMPARE_VERSION = "study-comparison-1.0"
MISSING = object()


def pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def input_changes(before: Any, after: Any, path: str = "") -> list[dict]:
    """Exact JSON differences with RFC 6901 paths; lists retain their order."""
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in sorted(set(before) | set(after)):
            changes.extend(input_changes(before.get(key, MISSING), after.get(key, MISSING), path+"/"+pointer_token(key)))
        return changes
    if isinstance(before, list) and isinstance(after, list):
        changes = []
        for index in range(max(len(before), len(after))):
            changes.extend(input_changes(before[index] if index<len(before) else MISSING,
                                         after[index] if index<len(after) else MISSING, path+"/"+str(index)))
        return changes
    if before is not MISSING and after is not MISSING and digest(before) == digest(after):
        return []
    return [{"path": path, "before_present": before is not MISSING, "after_present": after is not MISSING,
             "before": deepcopy(before) if before is not MISSING else None,
             "after": deepcopy(after) if after is not MISSING else None}]


def quantity_delta(before: dict, after: dict) -> dict:
    same_unit = before["unit"] == after["unit"]
    return {"before": deepcopy(before), "after": deepcopy(after),
            "delta": {"value": after["value"]-before["value"], "unit": before["unit"]} if same_unit else None,
            "comparison": "DESCRIPTIVE_ONLY" if same_unit else "INCOMPATIBLE_UNITS",
            "issue": None if same_unit else "Units differ; no conversion or numeric delta performed."}


def finding_changes(before: list[dict], after: list[dict]) -> dict:
    old = {(f["component"], f["code"]): f for f in before}
    new = {(f["component"], f["code"]): f for f in after}
    return {"introduced": [deepcopy(new[key]) for key in sorted(new.keys()-old.keys())],
            "no_longer_reported": [deepcopy(old[key]) for key in sorted(old.keys()-new.keys())],
            "retained": [deepcopy(new[key]) for key in sorted(old.keys() & new.keys()) if old[key] == new[key]],
            "changed": [{"before": deepcopy(old[key]), "after": deepcopy(new[key])}
                        for key in sorted(old.keys() & new.keys()) if old[key] != new[key]]}


def compare_studies(before: dict, after: dict) -> dict:
    reconstruct_report(before)
    reconstruct_report(after)
    first, second = before["input"], after["input"]
    old_product = first["manufacturing_input"]["product_id"]
    if old_product != second["manufacturing_input"]["product_id"]:
        raise ValueError("study comparisons require the same product_id")
    context = []
    contexts = {
        "DEMAND_CHANGED": (first["manufacturing_input"]["demand"], second["manufacturing_input"]["demand"]),
        "FACILITY_CHANGED": (first["manufacturing_input"]["facility"], second["manufacturing_input"]["facility"]),
        "HORIZON_CHANGED": (before["simulation"]["horizon"], after["simulation"]["horizon"]),
        "CURRENCY_CHANGED": (first["scenario"]["currency"], second["scenario"]["currency"]),
        "SIMULATION_CONFIG_CHANGED": (first["simulation"], second["simulation"]),
        "UNCERTAINTY_CONFIG_CHANGED": (first["uncertainty"], second["uncertainty"]),
        "REFERENCE_SUITE_CHANGED": (first["reference_suite"], second["reference_suite"]),
        **({"OBSERVATION_CHECKS_CHANGED":(first.get("observation_checks"),second.get("observation_checks"))}
           if "observation_checks" in first or "observation_checks" in second else {}),
        **({"REPLICATION_CONFIG_CHANGED":(first.get("replications"),second.get("replications"))}
           if "replications" in first or "replications" in second else {}),
        **({"EVIDENCE_POLICY_CHANGED": (first.get("evidence_policy"), second.get("evidence_policy"))}
           if "evidence_policy" in first or "evidence_policy" in second else {}),
        **({"EVIDENCE_SNAPSHOT_CHANGED": (first.get("evidence_snapshot"), second.get("evidence_snapshot"))}
           if "evidence_snapshot" in first or "evidence_snapshot" in second else {}),
    }
    for code, (left, right) in contexts.items():
        if digest(left) != digest(right):
            context.append({"code": code, "before": deepcopy(left), "after": deepcopy(right)})
    estimates = {key: quantity_delta(before["estimate"][key], after["estimate"][key]) for key in
                 ("unit_cost", "total_cost", "expected_starts", "expected_scrap", "route_yield", "expected_good_capacity")}
    batch = {key: quantity_delta({"value": before["simulation"][key], "unit": "piece"},
                                {"value": after["simulation"][key], "unit": "piece"}) for key in
             ("good_by_horizon", "scrapped_by_horizon", "wip_at_horizon", "eventual_good_units", "eventual_scrapped_units")}
    batch["batch_completion_time"] = quantity_delta(before["simulation"]["batch_completion_time"], after["simulation"]["batch_completion_time"])
    old_ops = {op["operation_id"]: op for op in before["estimate"]["operations"]}
    new_ops = {op["operation_id"]: op for op in after["estimate"]["operations"]}
    operation_changes = {"added": sorted(new_ops.keys()-old_ops.keys()), "removed": sorted(old_ops.keys()-new_ops.keys()),
                         "matched": {aid: {key: quantity_delta(old_ops[aid][key], new_ops[aid][key])
                                           for key in ("required_machine_time", "available_machine_time", "utilization", "expected_good_capacity", "cost")}
                                     for aid in sorted(old_ops.keys() & new_ops.keys())}}
    # Preserve full inputs for reconstruction, but keep per-sample outputs in the
    # original study reports rather than duplicating them in a comparison.
    sources = {}
    for label, report in (("before", before), ("after", after)):
        sources[label] = {"study_id": report["study_id"], "study_revision": report["study_revision"],
                          "study_fingerprint": report["study_fingerprint"], "report_content_hash": digest(report),
                          "input": deepcopy(report["input"])}
    result = {"schema_version": "1.0", "comparison_version": COMPARE_VERSION, "product_id": old_product,
            "sources": sources, "input_changes": input_changes(first, second), "context_changes": context,
            "estimates": estimates, "finite_batch": batch, "operations": operation_changes,
            "findings": finding_changes(before["findings"], after["findings"]),
            "plan_verification": {"before": deepcopy(before["plan"]["verification"]), "after": deepcopy(after["plan"]["verification"])},
            "review_state": {"before": before["review_state"], "after": after["review_state"]},
            "changed_specialist_revisions": sorted(aid for aid in before["plan"]["results"]
                                                  if before["plan"]["results"][aid]["revision"] != after["plan"]["results"][aid]["revision"]),
            "limitations": ["All deltas are descriptive; no causal attribution, ranking, or approval is inferred.",
                            "Changed demand, horizon, currency, facility, seeds, batch sizes, and uncertainty/reference settings are reported as context.",
                            "Numeric deltas require identical unit labels; no currency or other conversion is performed.",
                            "A finding no longer reported is not proof that an underlying manufacturing issue was resolved.",
                            "Input arrays are compared positionally; operation estimate rows are matched by stable operation_id.",
                            "Input changes are exact JSON differences, including revisions, bindings, list order, and source metadata."],
            "approval_state": "PENDING_HUMAN_REVIEW", "production_authorized": False}
    old_cost, new_cost = before["simulation"].get("cost_report"), after["simulation"].get("cost_report")
    if old_cost is not None or new_cost is not None:
        metrics = {}
        if old_cost is not None and new_cost is not None:
            for key in ("material_cost","machine_cost","labor_cost","total_cost","unit_cost"):
                left,right = old_cost[key],new_cost[key]
                metrics[key] = quantity_delta(left,right) if left is not None and right is not None else {
                    "before":deepcopy(left),"after":deepcopy(right),"delta":None,"comparison":"UNDEFINED_INPUT",
                    "issue":"One or both unit costs are undefined because no good output completed."}
        result["finite_batch_costs"] = {"before_available":old_cost is not None,"after_available":new_cost is not None,
                                        "scope":"FULL_SIMULATED_BATCH","metrics":metrics,
                                        "issue":None if old_cost is not None and new_cost is not None else "Costing was not enabled for both studies; no deltas computed."}
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Compare two reconstructable manufacturing study reports")
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", type=Path, help="Create a comparison report without overwriting")
    args = parser.parse_args(argv)
    try:
        result = compare_studies(json.loads(args.before.read_text(encoding="utf-8")),
                                 json.loads(args.after.read_text(encoding="utf-8")))
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+"\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as file:
                file.write(encoded)
        else:
            print(encoded, end="")
    except (ValueError, TypeError, KeyError, OSError, OverflowError, ZeroDivisionError) as exc:
        print(f"Comparison error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
