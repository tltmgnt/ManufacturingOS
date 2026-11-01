"""Bounded synthetic invariant checks; no facility or enterprise access."""
import argparse
from copy import deepcopy
from itertools import product
import json
import math
from pathlib import Path

from manufacturing_os.calculations import hours
from manufacturing_os.models import digest
from manufacturing_os.simulation import simulate_batch
from .offline_edge_cases import cases
from .rehearsal_provenance import SOURCE_ROOT, capture_provenance, verify_source_unchanged
from .temporary_use_case import encode


def sweep_cases():
    base = cases()[0][1]
    for seed, size, yield_fraction, machines in product((0, 1, 42), (1, 3, 10), (0.2, 0.8, 1.0), (1, 2)):
        name = f"seed-{seed}-batch-{size}-yield-{int(yield_fraction*100)}-machines-{machines}"
        spec = deepcopy(base)
        spec.update(simulation_id="synthetic-" + name, seed=seed, batch_size=size)
        spec["scenario"].update(scenario_id="synthetic-" + name, source_reference="synthetic://" + name)
        spec["scenario"]["operations"][1].update(yield_fraction=yield_fraction, machines=machines)
        yield name, spec


def check_invariants(report, replay, extended):
    issues = []
    if extended["horizon"]["value"] <= max(report["horizon"]["value"], report["batch_completion_time"]["value"]):
        issues.append("Extended horizon must exceed both the original horizon and batch completion")
    size = report["batch_size"]
    counts = [report[key] for key in ("good_by_horizon", "scrapped_by_horizon", "wip_at_horizon")]
    if any(type(value) is not int or value < 0 for value in counts) or sum(counts) != size:
        issues.append("Horizon counts do not reconcile to released starts")
    if report["eventual_good_units"] + report["eventual_scrapped_units"] != size:
        issues.append("Final dispositions do not reconcile to released starts")
    if report["good_by_horizon"] > report["eventual_good_units"] or report["scrapped_by_horizon"] > report["eventual_scrapped_units"]:
        issues.append("Horizon dispositions exceed final dispositions")
    cost = report["cost_report"]
    amounts = [cost[key]["value"] for key in ("material_cost", "machine_cost", "labor_cost")]
    total = cost["total_cost"]["value"]
    if any(not math.isfinite(value) or value < 0 for value in [*amounts, total]) or not math.isclose(total, math.fsum(amounts), rel_tol=1e-12, abs_tol=1e-9):
        issues.append("Full-batch costs do not reconcile")
    good = report["eventual_good_units"]
    if good == 0:
        if cost["unit_cost"] is not None or not cost["unit_cost_issue"]:
            issues.append("Zero-good output must retain undefined unit cost with a diagnostic")
    elif cost["unit_cost"] is None or not math.isclose(cost["unit_cost"]["value"], total/good, rel_tol=1e-12, abs_tol=1e-9):
        issues.append("Defined unit cost does not reconcile to total cost and final good output")
    if digest(report) != digest(replay):
        issues.append("Same-input replay changed the retained report")
    for key in ("eventual_good_units", "eventual_scrapped_units", "batch_completion_time", "cost_report"):
        if digest(report[key]) != digest(extended[key]):
            issues.append("Extending the reporting horizon changed full-batch output: " + key)
    if extended["good_by_horizon"] != report["eventual_good_units"] or extended["scrapped_by_horizon"] != report["eventual_scrapped_units"] or extended["wip_at_horizon"] != 0:
        issues.append("Horizon beyond batch completion did not retain all final dispositions")
    if any(row["production_authorized"] or row["cost_report"]["production_authorized"] for row in (report, replay, extended)):
        issues.append("Synthetic report incorrectly claimed production authorization")
    return issues


def run_sweep(output: Path):
    if any(output.resolve().is_relative_to((SOURCE_ROOT / name).resolve()) for name in ("examples", "manufacturing_os")):
        raise ValueError("Output must be outside captured source directories")
    output.mkdir(parents=True, exist_ok=False)
    provenance = capture_provenance()
    (output / "source-provenance.json").write_bytes(encode(provenance))
    outcomes = []
    for name, spec in sweep_cases():
        report, replay = simulate_batch(spec), simulate_batch(spec)
        extended_spec = deepcopy(spec)
        extended_spec["scenario"]["horizon"] = {"value": max(hours(spec["scenario"]["horizon"], positive=True), report["batch_completion_time"]["value"]) + 1, "unit": "h"}
        extended = simulate_batch(extended_spec)
        issues = check_invariants(report, replay, extended)
        directory = output / name
        directory.mkdir()
        (directory / "simulation-report.json").write_bytes(encode(report))
        (directory / "extended-horizon-report.json").write_bytes(encode(extended))
        outcomes.append({"case": name, "status": "FAIL" if issues else "PASS", "issues": issues,
                         "seed": spec["seed"], "batch_size": spec["batch_size"],
                         "finish_yield": spec["scenario"]["operations"][1]["yield_fraction"],
                         "finish_machines": spec["scenario"]["operations"][1]["machines"],
                         "zero_good_output": report["eventual_good_units"] == 0,
                         "target_met": report["target_met"], "report_fingerprint": digest(report),
                         "replay_fingerprint": digest(replay)})
    verify_source_unchanged(provenance)
    result = {"scope": "OFFLINE_SYNTHETIC_INVARIANT_SWEEP", "status": "PASS" if all(row["status"] == "PASS" for row in outcomes) else "FAIL",
              "case_count": len(outcomes), "simulation_count": 3*len(outcomes), "cases": outcomes,
              "source_fingerprint": provenance["source_fingerprint"], "production_authorized": False,
              "empirical_calibration_complete": False, "live_integration_complete": False,
              "limitations": ["Bounded synthetic self-consistency checks, not independent measured validation or a calibrated success probability.",
                              "The fixed grid covers three seeds, three batch sizes, three finishing yields and two machine counts; it is not exhaustive.",
                              "Horizon changes preserve the physical batch/seed; this does not assert monotonicity for arbitrary parameter or stochastic changes."]}
    (output / "invariant-scorecard.json").write_bytes(encode(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New invariant-sweep directory")
    args = parser.parse_args()
    try:
        result = run_sweep(args.output)
    except Exception as exc:
        parser.exit(2, f"Offline invariant sweep error: {exc}\n")
    print(json.dumps({key: result[key] for key in ("scope", "status", "case_count", "simulation_count")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
