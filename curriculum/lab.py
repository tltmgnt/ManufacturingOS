"""Offline curriculum answer key. Synthetic checks, never operational approval."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
for base in (ROOT, ROOT / "src", ROOT / "layer-b"):
    sys.path.insert(0, str(base))
CASES = []

def check(name, actual, expected):
    passed = actual == expected
    CASES.append({"case": name, "actual": actual, "expected": expected, "passed": passed})
    if not passed:
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")

def rejects(name, call, error=ValueError):
    try:
        call()
    except error:
        check(name, error.__name__, error.__name__)
    else:
        raise AssertionError(f"{name}: expected {error.__name__}")

def sample(path):
    return json.loads((ROOT / path).read_text())



def run():
    from manufacturing_os.calculations import Scenario, estimate
    data = sample("examples/serial-route.json")
    r = estimate(Scenario.from_dict(data))
    check("route yield 0.9*0.8", round(r["route_yield"]["value"],12), .72)
    check("72 good pieces require 100 expected starts", round(r["expected_starts"]["value"],9), 100.0)
    check("cost: 500+165+150", round(r["total_cost"]["value"],9), 815.0)
    check("finishing is bottleneck", r["bottleneck_operation"], "finish")
    check("steady-state good capacity", round(r["expected_good_capacity"]["value"],9), 76.8)
    larger = copy.deepcopy(data); larger["target_good_units"] = 144
    check("doubling target exceeds capacity", estimate(Scenario.from_dict(larger))["capacity_feasible"], False)
    check("estimate grants no production authority", r["production_authorized"], False)
    bad = copy.deepcopy(data); bad["operations"][0]["yield_fraction"] = 0
    rejects("zero yield is rejected", lambda: Scenario.from_dict(bad))

if __name__ == "__main__":
    if sys.argv[1:] not in ([], ["--verify"]):
        raise SystemExit("Usage: python curriculum/lab.py [--verify]")
    run()
    report = {"schema_version": 1, "status": "PASS", "case_count": len(CASES),
              "cases": CASES, "scope": "Synthetic curriculum checks only"}
    if sys.argv[1:] == ["--verify"]:
        expected = json.loads((Path(__file__).parent / "expected.json").read_text())
        if report != expected:
            raise AssertionError("Observed answers differ from curriculum/expected.json")
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))
