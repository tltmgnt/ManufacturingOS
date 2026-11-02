"""Verify the complete synthetic offline suite; no real-system access or authenticity claim."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from manufacturing_os.calculations import hours
from manufacturing_os.jsonio import loads
from manufacturing_os.models import digest
from manufacturing_os.simulation import simulate_batch
from .offline_edge_cases import cases, metrics
from .offline_invariant_sweep import check_invariants, sweep_cases
from .offline_repeatability import compare_runs
from .rehearsal_integrity import MAX_FILE, inventory, read_file, safe_path
from .temporary_use_case import encode

MANIFEST = "offline-suite-manifest.json"


def suite_inventory(root):
    return inventory(root, max_files=500, max_entries=1000, max_total=256*1024*1024, exclude_manifest=MANIFEST)


def same(actual, expected, label):
    if digest(actual) != digest(expected):
        raise ValueError(label + " differs from reconstructed offline evidence")


def complete_scorecard(root):
    scorecard = loads(read_file(root / "offline-suite.json"))
    status = loads(read_file(root / "run-status.json"))
    if status != {"status": "COMPLETE", "phase": "complete"} or scorecard.get("scope") != "OFFLINE_SYNTHETIC_SUITE" or scorecard.get("status") != "PASS":
        raise ValueError("Offline suite is not complete and passing")
    if any(scorecard.get(key) is not False for key in ("production_authorized", "empirical_calibration_complete", "live_integration_complete", "actual_shadow_pilot_complete")):
        raise ValueError("Offline suite claimed real-world authorization or completion")
    return scorecard


def write_suite_manifest(root: Path, *, replace=False):
    complete_scorecard(root)
    manifest = {"schema_version": "1.0", "scope": "OFFLINE_SYNTHETIC_SUITE_MANIFEST",
                "files": suite_inventory(root), "production_authorized": False}
    path = root / MANIFEST
    if path.is_symlink():
        raise ValueError("Suite manifest must not be a symlink")
    with path.open("wb" if replace else "xb") as file:
        file.write(encode(manifest))
    return manifest


def verify_suite(root: Path):
    def load(name):
        return loads(read_file(root / name))
    manifest = loads(read_file(root / MANIFEST, 256*1024))
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "scope", "files", "production_authorized"} or manifest["schema_version"] != "1.0" or manifest["scope"] != "OFFLINE_SYNTHETIC_SUITE_MANIFEST" or manifest["production_authorized"] is not False:
        raise ValueError("Invalid offline suite manifest")
    records = manifest["files"]
    if not isinstance(records, list) or not 1 <= len(records) <= 500:
        raise ValueError("Invalid offline suite file count")
    names = set()
    for row in records:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise ValueError("Invalid offline suite file record")
        name = safe_path(row["path"])
        if name == MANIFEST or name in names or type(row["bytes"]) is not int or not 0 <= row["bytes"] <= MAX_FILE or not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("Invalid/duplicate offline suite file record")
        names.add(name)
    if suite_inventory(root) != records:
        raise ValueError("Offline suite files differ from manifest: missing, changed or extra content")
    scorecard = complete_scorecard(root)
    repeatability = compare_runs(root / "repeatability/first", root / "repeatability/second")
    same(load("repeatability/repeatability.json"), repeatability, "Repeatability scorecard")
    if repeatability["status"] != "REPEATABLE" or load("repeatability/run-status.json") != {"status": "COMPLETE", "phase": "complete"}:
        raise ValueError("Paired pilot runs are not repeatable and complete")

    def source_fingerprint(name):
        provenance = load(name + "/source-provenance.json")
        same(digest(provenance["files"]), provenance["source_fingerprint"], "Source fingerprint")
        return provenance["source_fingerprint"]

    def check_component(name, scope):
        value = load(name + ("/edge-scorecard.json" if name == "edges" else "/invariant-scorecard.json"))
        if value.get("scope") != scope or value.get("status") != "PASS" or any(value.get(key) is not False for key in ("production_authorized", "empirical_calibration_complete", "live_integration_complete")):
            raise ValueError("Offline component scope/status is inconsistent")
        same(value["source_fingerprint"], source_fingerprint(name), "Component source provenance")
        return value

    edges = check_component("edges", "OFFLINE_SYNTHETIC_EDGE_CASES")
    edge_outcomes = []
    for name, spec, expected in cases():
        report = load("edges/" + name + "/simulation-report.json")
        same(load("edges/" + name + "/simulation-input.json"), spec, "Edge-case input")
        same(report, simulate_batch(spec), "Edge-case report")
        actual = metrics(report)
        if actual != expected:
            raise ValueError("Hand-derived edge expectation differs from reconstructed offline evidence")
        edge_outcomes.append({"case": name, "software_check": "PASS", "expected": expected, "actual": actual,
                              "differences": [], "production_authorized": False})
    same(edges["cases"], edge_outcomes, "Edge scorecard")

    invariants = check_component("invariants", "OFFLINE_SYNTHETIC_INVARIANT_SWEEP")
    invariant_outcomes = []
    for name, spec in sweep_cases():
        report = load("invariants/" + name + "/simulation-report.json")
        replay = simulate_batch(spec)
        same(report, replay, "Invariant base report")
        extended_spec = deepcopy(spec)
        extended_spec["scenario"]["horizon"] = {"value": max(hours(spec["scenario"]["horizon"], positive=True), replay["batch_completion_time"]["value"]) + 1, "unit": "h"}
        extended = load("invariants/" + name + "/extended-horizon-report.json")
        same(extended, simulate_batch(extended_spec), "Extended-horizon report")
        issues = check_invariants(report, replay, extended)
        if issues:
            raise ValueError("Retained invariant report failed its domain checks")
        invariant_outcomes.append({"case": name, "status": "PASS", "issues": [], "seed": spec["seed"],
            "batch_size": spec["batch_size"], "finish_yield": spec["scenario"]["operations"][1]["yield_fraction"],
            "finish_machines": spec["scenario"]["operations"][1]["machines"], "zero_good_output": report["eventual_good_units"] == 0,
            "target_met": report["target_met"], "report_fingerprint": digest(report), "replay_fingerprint": digest(replay)})
    same(invariants["cases"], invariant_outcomes, "Invariant scorecard")
    same([invariants["case_count"], invariants["simulation_count"]], [54, 162], "Invariant coverage")
    fingerprints = [*repeatability["source_fingerprints"], edges["source_fingerprint"], invariants["source_fingerprint"]]
    same(scorecard["source_fingerprints"], fingerprints, "Suite source provenance")
    if len(set(fingerprints)) != 1 or scorecard["source_consistent"] is not True:
        raise ValueError("Offline components do not share captured sources")
    same(scorecard["components"], [{"component": name, "observed_status": status, "software_check": "PASS"} for name, status in
         (("Repeatability", "REPEATABLE"), ("Edge cases", "PASS"), ("Invariant sweep", "PASS"))], "Suite component scorecard")
    from .offline_suite import render_suite
    if read_file(root / "index.html").decode().replace("\r\n", "\n") != render_suite(scorecard).replace("\r\n", "\n"):
        raise ValueError("Offline overview differs from its scorecard")
    return {"scope": "OFFLINE_SYNTHETIC_SUITE_CONSISTENCY", "status": "VERIFIED_CONTENT",
            "verified_files": len(records), "verified_pilot_runs": 2, "verified_study_bundles": 16,
            "verified_edge_cases": 6, "verified_invariant_cases": 54, "production_authorized": False,
            "limitations": ["Supplied-content consistency and reconstruction only; not authenticated origin, measured accuracy or approval.",
                            "Use the matching source checkout and environment for version-dependent reconstruction."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_suite(args.directory), indent=2))
    except Exception as exc:
        parser.exit(2, f"Offline suite verification error: {exc}\n")


if __name__ == "__main__":
    main()
