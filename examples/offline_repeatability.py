"""Repeat the synthetic pilot twice; compare verified outputs without real-system access."""
import argparse
import hashlib
import json
from pathlib import Path

from manufacturing_os.jsonio import loads
from .rehearsal_integrity import MANIFEST, read_file, verify_rehearsal
from .rehearsal_provenance import SOURCE_ROOT
from .temporary_pilot import run_pilot
from .temporary_use_case import encode


def compare_runs(first: Path, second: Path) -> dict:
    if first.resolve() == second.resolve():
        raise ValueError("Repeatability comparison requires two distinct run directories")
    verified = [verify_rehearsal(path) for path in (first, second)]
    manifests = [loads(read_file(path / MANIFEST)) for path in (first, second)]
    inventories = []
    for root, manifest in zip((first, second), manifests):
        entries = {row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]} for row in manifest["files"]}
        raw = read_file(root / MANIFEST)
        entries[MANIFEST] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        inventories.append(entries)
    paths = sorted(set(inventories[0]) | set(inventories[1]))
    differences = [{"path": path, "first": inventories[0].get(path), "second": inventories[1].get(path)}
                   for path in paths if inventories[0].get(path) != inventories[1].get(path)]
    return {"scope": "OFFLINE_SYNTHETIC_REPEATABILITY", "status": "REPEATABLE" if not differences else "MISMATCH",
            "compared_files": len(paths), "differences": differences,
            "source_fingerprints": [row["source_fingerprint"] for row in verified],
            "production_authorized": False, "live_integration_complete": False,
            "empirical_calibration_complete": False, "actual_shadow_pilot_complete": False,
            "limitations": ["Exact-byte repeatability of synthetic runs in this environment, not empirical accuracy or production acceptance.",
                            "Both runs are reconstructed before comparison; an invalid run raises an error rather than being compared.",
                            "Python/platform/source metadata and archive bytes may differ across environments; no cross-platform byte guarantee is claimed."]}


def run_repeatability(output: Path) -> dict:
    if any(output.resolve().is_relative_to((SOURCE_ROOT / name).resolve()) for name in ("examples", "manufacturing_os")):
        raise ValueError("Output must be outside captured source directories")
    output.mkdir(parents=True, exist_ok=False)
    status_path = output / "run-status.json"
    phase = "first-run"
    status_path.write_bytes(encode({"status": "RUNNING", "phase": phase}))
    try:
        run_pilot(output / "first")
        phase = "second-run"
        status_path.write_bytes(encode({"status": "RUNNING", "phase": phase}))
        run_pilot(output / "second")
        phase = "comparison"
        result = compare_runs(output / "first", output / "second")
        (output / "repeatability.json").write_bytes(encode(result))
        (output / "README.txt").write_text(
            "OFFLINE SYNTHETIC REPEATABILITY REHEARSAL\n"
            "Read repeatability.json, then open first/index.html and second/index.html.\n"
            "Each child directory retains its own verified source/fitting/model evidence.\n"
            "No real facility or enterprise source is contacted; mock HTTP stays on loopback.\n"
            "Repeatable synthetic output does not establish real-world accuracy or acceptance.\n", encoding="utf-8")
        status_path.write_bytes(encode({"status": "COMPLETE" if result["status"] == "REPEATABLE" else "MISMATCH", "phase": "complete"}))
        return result
    except Exception:
        status_path.write_bytes(encode({"status": "FAILED", "phase": phase}))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New repeatability directory")
    args = parser.parse_args()
    try:
        result = run_repeatability(args.output)
    except Exception as exc:
        parser.exit(2, f"Offline repeatability error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "REPEATABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
