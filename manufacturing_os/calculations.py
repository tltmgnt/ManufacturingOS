"""Bounded serial-route estimates; deliberately separate from release verification."""
from dataclasses import asdict, dataclass
import math
from typing import Any

from .models import digest, nonempty

MODEL_VERSION = "serial-route-1.0"
TIME_TO_HOURS = {"s": 1 / 3600, "min": 1 / 60, "h": 1.0}


def number(value: Any, name: str, *, low: float = 0, high: float | None = None,
           positive: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < low or (positive and value == low) or (high is not None and value > high):
        raise ValueError(f"{name} outside allowed range")
    return float(value)


def fields(data: Any, expected: set[str], name: str) -> None:
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError(f"{name} requires exactly {sorted(expected)}")


def measure(data: Any, unit: str, *, positive: bool = False) -> float:
    fields(data, {"value", "unit"}, "measurement")
    if data["unit"] != unit:
        raise ValueError(f"expected unit {unit}")
    return number(data["value"], unit, positive=positive)


def hours(data: Any, *, positive: bool = False) -> float:
    fields(data, {"value", "unit"}, "duration")
    if data["unit"] not in TIME_TO_HOURS:
        raise ValueError("duration unit must be s, min, or h")
    return number(data["value"], "duration", positive=positive) * TIME_TO_HOURS[data["unit"]]


@dataclass(frozen=True)
class Operation:
    operation_id: str
    cycle_hours: float
    setup_hours: float
    machines: int
    availability: float
    yield_fraction: float
    machine_rate: float
    labor_rate: float


@dataclass(frozen=True)
class Scenario:
    schema_version: str
    scenario_id: str
    revision: str
    currency: str
    target_good_units: int
    horizon_hours: float
    material_cost_per_start: float
    operations: tuple[Operation, ...]
    source_reference: str
    assumptions: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        fields(data, {"schema_version", "scenario_id", "revision", "currency", "target_good_units",
                      "horizon", "material_cost_per_start", "operations", "source_reference", "assumptions"}, "scenario")
        if data["schema_version"] != "1.0":
            raise ValueError("unsupported scenario schema")
        for key in ("scenario_id", "revision", "currency", "source_reference"):
            nonempty(data[key], key)
        currency = data["currency"]
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha() or currency != currency.upper():
            raise ValueError("currency must be a three-letter uppercase code")
        target = data["target_good_units"]
        if type(target) is not int or target <= 0:
            raise ValueError("target_good_units must be a positive integer")
        if not isinstance(data["assumptions"], list) or not data["assumptions"]:
            raise ValueError("explicit assumptions required")
        for assumption in data["assumptions"]:
            nonempty(assumption, "assumption")
        if not isinstance(data["operations"], list) or not data["operations"]:
            raise ValueError("serial route requires at least one operation")
        operations = []
        for row in data["operations"]:
            fields(row, {"operation_id", "cycle_time", "setup_time", "machines", "availability",
                         "yield_fraction", "machine_rate", "labor_rate"}, "operation")
            nonempty(row["operation_id"], "operation_id")
            if type(row["machines"]) is not int or row["machines"] <= 0:
                raise ValueError("machines must be a positive integer")
            operations.append(Operation(row["operation_id"], hours(row["cycle_time"], positive=True),
                                        hours(row["setup_time"]), row["machines"],
                                        number(row["availability"], "availability", high=1, positive=True),
                                        number(row["yield_fraction"], "yield", high=1, positive=True),
                                        measure(row["machine_rate"], f"{currency}/h"),
                                        measure(row["labor_rate"], f"{currency}/h")))
        if len({op.operation_id for op in operations}) != len(operations):
            raise ValueError("duplicate operation_id")
        return cls("1.0", data["scenario_id"], data["revision"], currency, target,
                   hours(data["horizon"], positive=True),
                   measure(data["material_cost_per_start"], f"{currency}/piece"), tuple(operations),
                   data["source_reference"], tuple(data["assumptions"]))


def quantity(value: float, unit: str) -> dict:
    if not math.isfinite(value):
        raise ValueError("calculation overflow; input scale is unsupported")
    return {"value": value, "unit": unit}


def estimate(scenario: Scenario) -> dict:
    """Steady-state expected-value model; fractional starts are intentional."""
    remaining_yield = 1.0
    downstream_yields = {}
    for op in reversed(scenario.operations):
        remaining_yield *= op.yield_fraction
        downstream_yields[op.operation_id] = remaining_yield
    if remaining_yield == 0:
        raise ValueError("route yield underflow; input scale is unsupported")
    starts = scenario.target_good_units / remaining_yield
    total_cost = starts * scenario.material_cost_per_start
    rows, bottleneck = [], None
    good_capacity = math.inf
    for op in scenario.operations:
        required = scenario.target_good_units / downstream_yields[op.operation_id]
        # Setup is incurred once on every configured machine per horizon.
        available = scenario.horizon_hours * op.machines * op.availability
        setup = op.setup_hours * op.machines
        processing = required * op.cycle_hours
        load = processing + setup
        capacity = max(0.0, available - setup) / op.cycle_hours * downstream_yields[op.operation_id]
        cost = load * (op.machine_rate + op.labor_rate)
        total_cost += cost
        if capacity < good_capacity:
            good_capacity, bottleneck = capacity, op.operation_id
        rows.append({"operation_id": op.operation_id,
                     "expected_input": quantity(required, "piece"),
                     "required_machine_time": quantity(load, "h"),
                     "available_machine_time": quantity(available, "h"),
                     "utilization": quantity(load / available, "fraction"),
                     "expected_good_capacity": quantity(capacity, "piece/horizon"),
                     "cost": quantity(cost, scenario.currency)})
    return {"schema_version": "1.0", "model_version": MODEL_VERSION,
            "scenario_id": scenario.scenario_id, "scenario_revision": scenario.revision,
            "input_fingerprint": digest(asdict(scenario)), "source_reference": scenario.source_reference,
            "assumptions": list(scenario.assumptions) + [
                "Serial route; no rework, queues, transfers, overtime, or shared resources.",
                "Independent fixed yields; expected fractional starts, not a dispatch schedule.",
                "One setup per machine per horizon; availability reduces usable horizon.",
                "Labor is dedicated per machine and billed for processing and setup only.",
                "Material is charged at route entry; downstream costs reflect upstream attrition.",
                "Steady-state capacity excludes pipeline fill/drain; no lead-time guarantee."],
            "route_yield": quantity(remaining_yield, "fraction"),
            "expected_starts": quantity(starts, "piece"),
            "expected_scrap": quantity(starts - scenario.target_good_units, "piece"),
            "expected_good_capacity": quantity(good_capacity, "piece/horizon"),
            "bottleneck_operation": bottleneck,
            "capacity_feasible": all(r["required_machine_time"]["value"] <= r["available_machine_time"]["value"] for r in rows),
            "total_cost": quantity(total_cost, scenario.currency),
            "unit_cost": quantity(total_cost / scenario.target_good_units, f"{scenario.currency}/good_piece"),
            "operations": rows, "validation_status": "UNVALIDATED_ESTIMATE",
            "production_authorized": False}


def sensitivity(data: dict, variants: dict[str, dict]) -> dict:
    """Explicit alternative inputs; validate independently rather than silently clamp."""
    baseline = estimate(Scenario.from_dict(data))
    results = {}
    for name, variant in variants.items():
        nonempty(name, "variant name")
        result = estimate(Scenario.from_dict(variant))
        if result["unit_cost"]["unit"] != baseline["unit_cost"]["unit"]:
            raise ValueError("sensitivity currencies must match")
        results[name] = {"estimate": result,
                         "unit_cost_delta": quantity(result["unit_cost"]["value"] - baseline["unit_cost"]["value"], baseline["unit_cost"]["unit"])}
    return {"baseline": baseline, "variants": results}


def main() -> int:
    import argparse
    import json
    import sys
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Evaluate an unvalidated synthetic serial route")
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--variants", type=Path, help="JSON object mapping names to complete scenarios")
    args = parser.parse_args()
    try:
        data = json.loads(args.scenario.read_text())
        if args.variants:
            variants = json.loads(args.variants.read_text())
            if not isinstance(variants, dict):
                raise ValueError("variants must be an object")
            result = sensitivity(data, variants)
        else:
            result = estimate(Scenario.from_dict(data))
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    except (ValueError, TypeError, KeyError, OSError, OverflowError, ZeroDivisionError) as exc:
        print(f"Scenario error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
