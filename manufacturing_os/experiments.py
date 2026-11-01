"""Reproducible exploratory sampling and explicit arithmetic reference checks."""
from copy import deepcopy
import json
import math
from pathlib import Path
import random
from typing import Any

from .calculations import MODEL_VERSION, Scenario, estimate, fields, nonempty, number, quantity
from .models import digest

EXPERIMENT_VERSION = "experiments-1.0"
# Paths are deliberately enumerated. No arbitrary attribute access or code execution.
PARAMETERS = {"cycle_time", "setup_time", "availability", "yield_fraction", "machine_rate", "labor_rate"}
METRICS = {"unit_cost", "total_cost", "expected_good_capacity", "route_yield", "expected_starts", "expected_scrap"}


def percentile(values: list[float], probability: float) -> float:
    """Linear interpolation at (n-1)*p; documented rather than library-dependent."""
    values = sorted(values)
    index = (len(values) - 1) * probability
    lower, upper = math.floor(index), math.ceil(index)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def apply_value(scenario: dict, operation_id: str, parameter: str, value: float) -> None:
    operation = next(row for row in scenario["operations"] if row["operation_id"] == operation_id)
    if isinstance(operation[parameter], dict):
        operation[parameter]["value"] = value
    else:
        operation[parameter] = value


def simulate(spec: dict) -> dict:
    fields(spec, {"schema_version", "experiment_id", "revision", "seed", "samples", "scenario", "ranges"}, "experiment")
    if spec["schema_version"] != "1.0":
        raise ValueError("unsupported experiment schema")
    for name in ("experiment_id", "revision"):
        nonempty(spec[name], name)
    if type(spec["seed"]) is not int or not 0 <= spec["seed"] <= 2**32-1:
        raise ValueError("seed must be an integer in [0, 2**32-1]")
    if type(spec["samples"]) is not int or not 1 <= spec["samples"] <= 10000:
        raise ValueError("samples must be an integer in [1, 10000]")
    baseline = estimate(Scenario.from_dict(spec["scenario"]))
    if not isinstance(spec["ranges"], list):
        raise ValueError("ranges must be a list")
    ids = {row["operation_id"] for row in spec["scenario"]["operations"]}
    seen = set()
    for row in spec["ranges"]:
        fields(row, {"operation_id", "parameter", "low", "high"}, "range")
        if not isinstance(row["operation_id"], str) or row["operation_id"] not in ids:
            raise ValueError("unknown operation_id")
        if not isinstance(row["parameter"], str) or row["parameter"] not in PARAMETERS:
            raise ValueError("unsupported sampled parameter")
        key = row["operation_id"], row["parameter"]
        if key in seen:
            raise ValueError("duplicate sampled parameter")
        seen.add(key)
        low, high = number(row["low"], "low"), number(row["high"], "high")
        if low > high:
            raise ValueError("range low exceeds high")
        for endpoint in (low, high):
            candidate = deepcopy(spec["scenario"])
            apply_value(candidate, *key, endpoint)
            # Enforce field-specific units and admissible domains at both endpoints.
            Scenario.from_dict(candidate)
    rng = random.Random(spec["seed"])
    values = {key: [] for key in METRICS}
    bottlenecks: dict[str, int] = {}
    feasible = 0
    samples = []
    ranges = sorted(spec["ranges"], key=lambda row: (row["operation_id"], row["parameter"]))
    for index in range(spec["samples"]):
        candidate = deepcopy(spec["scenario"])
        sampled = []
        for row in ranges:
            value = rng.uniform(row["low"], row["high"])
            apply_value(candidate, row["operation_id"], row["parameter"], value)
            sampled.append({**row, "value": value})
        result = estimate(Scenario.from_dict(candidate))
        for key in METRICS:
            values[key].append(result[key]["value"])
        feasible += int(result["capacity_feasible"])
        bottleneck = result["bottleneck_operation"]
        bottlenecks[bottleneck] = bottlenecks.get(bottleneck, 0) + 1
        samples.append({"sample_index": index, "sampled_parameters": sampled,
                        "input_fingerprint": result["input_fingerprint"],
                        "capacity_feasible": result["capacity_feasible"],
                        "bottleneck_operation": bottleneck,
                        "metrics": {key: result[key] for key in sorted(METRICS)}})
    summary = {}
    for key in sorted(METRICS):
        unit = baseline[key]["unit"]
        summary[key] = {name: quantity(value, unit) for name, value in {
            "min": min(values[key]), "p05": percentile(values[key], .05),
            "p50": percentile(values[key], .5), "p95": percentile(values[key], .95),
            "max": max(values[key]), "mean": math.fsum(v / spec["samples"] for v in values[key])}.items()}
    return {"schema_version": "1.0", "experiment_version": EXPERIMENT_VERSION,
            "model_version": MODEL_VERSION, "experiment_id": spec["experiment_id"],
            "experiment_revision": spec["revision"], "experiment_fingerprint": digest(spec),
            "input": deepcopy(spec), "baseline": baseline, "summary": summary,
            "feasible_samples": feasible, "sample_count": spec["samples"],
            "sampled_feasible_fraction": quantity(feasible / spec["samples"], "fraction"),
            "bottleneck_counts": bottlenecks, "samples": samples,
            "method": "Independent uniform ranges; local seeded Python Random; linear quantiles at (n-1)*p.",
            "limitations": ["Exploratory input uncertainty propagation, not calibrated manufacturing risk probabilities.",
                            "Uniform and independent inputs are assumptions, not empirical distributions.",
                            "Percentiles describe sampled model outputs, not confidence intervals.",
                            "Range values use the corresponding scenario field's declared unit.",
                            "All serial-route model limitations and baseline assumptions apply."],
            "validation_status": "UNVALIDATED_EXPLORATION", "production_authorized": False}


def validate_references(suite: dict) -> dict:
    fields(suite, {"schema_version", "suite_id", "revision", "reference_type", "cases"}, "reference suite")
    if suite["schema_version"] != "1.0" or suite["reference_type"] != "synthetic_arithmetic":
        raise ValueError("only v1 synthetic_arithmetic reference suites are supported")
    for name in ("suite_id", "revision"):
        nonempty(suite[name], name)
    if not isinstance(suite["cases"], list) or not suite["cases"]:
        raise ValueError("reference cases cannot be empty")
    cases, seen = [], set()
    for case in suite["cases"]:
        fields(case, {"case_id", "objective", "reference_revision", "source_reference", "scenario", "expected"}, "case")
        for name in ("case_id", "objective", "reference_revision", "source_reference"):
            nonempty(case[name], name)
        if case["case_id"] in seen:
            raise ValueError("duplicate case_id")
        seen.add(case["case_id"])
        actual = estimate(Scenario.from_dict(case["scenario"]))
        if not isinstance(case["expected"], dict) or not case["expected"] or not set(case["expected"]) <= METRICS:
            raise ValueError("expected must contain supported numeric metrics")
        checks = []
        for metric, expected in sorted(case["expected"].items()):
            fields(expected, {"value", "unit", "absolute_tolerance"}, "expected metric")
            value = number(expected["value"], "expected value")
            tolerance = number(expected["absolute_tolerance"], "absolute_tolerance")
            if expected["unit"] != actual[metric]["unit"]:
                raise ValueError("reference unit differs from model output")
            residual = actual[metric]["value"] - value
            checks.append({"metric": metric, "expected": deepcopy(expected), "actual": actual[metric],
                           "residual": quantity(residual, expected["unit"]),
                           "status": "PASS" if abs(residual) <= tolerance else "FAIL"})
        cases.append({"case_id": case["case_id"], "objective": case["objective"],
                      "reference_revision": case["reference_revision"], "source_reference": case["source_reference"],
                      "input_fingerprint": actual["input_fingerprint"], "checks": checks,
                      "status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"})
    return {"schema_version": "1.0", "experiment_version": EXPERIMENT_VERSION, "model_version": MODEL_VERSION,
            "suite_id": suite["suite_id"], "suite_revision": suite["revision"],
            "suite_fingerprint": digest(suite), "input": deepcopy(suite), "cases": cases,
            "status": "PASS" if all(c["status"] == "PASS" for c in cases) else "FAIL",
            "check_count": sum(len(case["checks"]) for case in cases),
            "passed_checks": sum(c["status"] == "PASS" for case in cases for c in case["checks"]),
            "reviewer": None, "validation_scope": "Synthetic arithmetic only; no facility calibration or release approval.",
            "production_authorized": False}


def main() -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Run exploratory simulations or synthetic reference checks")
    parser.add_argument("mode", choices=["simulate", "validate"])
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, help="Create a new JSON report; existing files are never overwritten")
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        result = simulate(data) if args.mode == "simulate" else validate_references(data)
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as file:
                file.write(encoded)
        else:
            print(encoded, end="")
        return 1 if result.get("status") == "FAIL" else 0
    except (ValueError, TypeError, KeyError, OSError, OverflowError, ZeroDivisionError) as exc:
        print(f"Experiment error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
