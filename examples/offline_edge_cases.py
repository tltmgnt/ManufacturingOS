"""Hand-derived synthetic scheduling/cost edge cases; no enterprise or network access."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from manufacturing_os.simulation import simulate_batch
from .rehearsal_provenance import SOURCE_ROOT, capture_provenance, verify_source_unchanged
from .temporary_use_case import encode


def cases():
    scenario = json.loads((Path(__file__).resolve().parent / "observation-study.json").read_text())["scenario"]
    base = {"schema_version": "1.0", "simulation_id": "offline-edge-baseline", "revision": "1",
            "seed": 42, "batch_size": 3, "scenario": scenario, "include_costs": True}
    definitions = [
        ("baseline", {}, (2, 0, 1, 3, 0, 7, True, 225, 75)),
        ("slower-finish", {"finish_cycle": 3}, (1, 0, 2, 3, 0, 10, False, 285, 95)),
        ("short-deadline", {"horizon": 2}, (0, 0, 3, 3, 0, 7, False, 225, 75)),
        ("small-batch", {"batch_size": 1}, (1, 0, 0, 1, 0, 3, False, 75, 75)),
        ("seeded-finish-scrap", {"finish_yield": 0.01}, (0, 2, 1, 0, 3, 7, False, 225, None)),
        ("seeded-upstream-scrap", {"cut_yield": 0.01}, (0, 3, 0, 0, 3, 3, False, 105, None)),
    ]
    names = ("good_by_horizon", "scrapped_by_horizon", "wip_at_horizon", "eventual_good_units",
             "eventual_scrapped_units", "completion_h", "target_met", "total_cost_usd", "unit_cost_usd_per_good")
    result = []
    for name, changes, expected in definitions:
        spec = deepcopy(base)
        spec["simulation_id"] = "offline-edge-" + name
        spec["scenario"].update(scenario_id="offline-edge-" + name, revision="1", source_reference="synthetic://offline-edge-" + name)
        spec["scenario"]["assumptions"].append("Synthetic seeded edge case only; no measured facility reference.")
        if "finish_cycle" in changes:
            spec["scenario"]["operations"][1]["cycle_time"]["value"] = changes["finish_cycle"]
        if "horizon" in changes:
            spec["scenario"]["horizon"]["value"] = changes["horizon"]
        if "batch_size" in changes:
            spec["batch_size"] = changes["batch_size"]
        for key, index in (("cut_yield", 0), ("finish_yield", 1)):
            if key in changes:
                spec["scenario"]["operations"][index]["yield_fraction"] = changes[key]
        result.append((name, spec, dict(zip(names, expected))))
    return result


def metrics(report):
    result = {key: report[key] for key in ("good_by_horizon", "scrapped_by_horizon", "wip_at_horizon",
                                         "eventual_good_units", "eventual_scrapped_units", "target_met")}
    result.update(completion_h=report["batch_completion_time"]["value"],
                  total_cost_usd=report["cost_report"]["total_cost"]["value"],
                  unit_cost_usd_per_good=None if report["cost_report"]["unit_cost"] is None else report["cost_report"]["unit_cost"]["value"])
    return result


def run_edges(output: Path) -> dict:
    if any(output.resolve().is_relative_to((SOURCE_ROOT / name).resolve()) for name in ("examples", "manufacturing_os")):
        raise ValueError("Output must be outside captured source directories")
    output.mkdir(parents=True, exist_ok=False)
    provenance = capture_provenance()
    (output / "source-provenance.json").write_bytes(encode(provenance))
    outcomes = []
    for name, spec, expected in cases():
        report = simulate_batch(spec)
        if report["production_authorized"] or report["cost_report"]["production_authorized"]:
            raise RuntimeError("Synthetic model incorrectly claimed production authorization")
        actual = metrics(report)
        differences = [{"metric": key, "expected": expected[key], "actual": actual[key]}
                       for key in expected if expected[key] != actual[key]]
        if actual["unit_cost_usd_per_good"] is None and not report["cost_report"]["unit_cost_issue"]:
            raise RuntimeError("Undefined unit cost lost its diagnostic")
        directory = output / name
        directory.mkdir()
        (directory / "simulation-input.json").write_bytes(encode(spec))
        (directory / "simulation-report.json").write_bytes(encode(report))
        outcomes.append({"case": name, "software_check": "FAIL" if differences else "PASS", "expected": expected,
                         "actual": actual, "differences": differences, "production_authorized": False})
    verify_source_unchanged(provenance)
    summary = {"scope": "OFFLINE_SYNTHETIC_EDGE_CASES", "status": "PASS" if all(row["software_check"] == "PASS" for row in outcomes) else "FAIL",
               "source_fingerprint": provenance["source_fingerprint"], "cases": outcomes,
               "production_authorized": False, "empirical_calibration_complete": False,
               "live_integration_complete": False,
               "limitations": ["Hand-derived toy cases only; software expectations are not measured facility performance.",
                               "Target misses and undefined unit costs are expected outcomes, not production approvals.",
                               "Full-batch cost includes work after the horizon and excludes capex, overhead, taxes and rework."]}
    (output / "edge-scorecard.json").write_bytes(encode(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New edge-case directory")
    args = parser.parse_args()
    try:
        result = run_edges(args.output)
    except Exception as exc:
        parser.exit(2, f"Offline edge-case error: {exc}\n")
    print(json.dumps({"scope": result["scope"], "status": result["status"], "cases": len(result["cases"])}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
