"""Verify retained rehearsal files and reconstruct study bundles; not authenticity."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from zipfile import ZipFile

from manufacturing_os.bundle import verify_bundle
from manufacturing_os.jsonio import loads
from manufacturing_os.models import digest
from .synthetic_calibration_rehearsal import evaluate_frozen, fit_candidate
from .temporary_use_case import encode

MANIFEST = "rehearsal-manifest.json"
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
BUNDLE_DIRS = ["planning/" + name for name in ("baseline", "cost-disagreement", "target-miss", "capacity-remedy")] + ["intake", "api", "calibration/baseline", "calibration/candidate"]


def read_file(path: Path, limit=MAX_FILE) -> bytes:
    if path.is_symlink():
        raise ValueError("Rehearsal verification rejects symlinks")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as file:
        before = os.fstat(file.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("Rehearsal file is not a bounded regular file")
        raw = file.read(limit + 1)
        after = os.fstat(file.fileno())
    if len(raw) > limit or len(raw) != after.st_size or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("Rehearsal file changed during verification")
    return raw


def safe_path(name):
    if not isinstance(name, str) or not name or len(name) > 512 or "\\" in name or ":" in name:
        raise ValueError("Invalid rehearsal manifest path")
    path = PurePosixPath(name)
    if path.is_absolute() or str(path) != name or any(part in (".", "..") for part in path.parts) or name == ".":
        raise ValueError("Invalid rehearsal manifest path")
    return name


def inventory(root: Path) -> list[dict]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Rehearsal root must be a regular directory")
    records, nodes, total = [], 0, 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        nodes += len(dirs) + len(files)
        if nodes > 500:
            raise ValueError("Too many rehearsal entries")
        if any((Path(directory) / name).is_symlink() for name in dirs + files):
            raise ValueError("Rehearsal verification rejects symlinks")
        for name in sorted(files):
            path = Path(directory) / name
            relative = safe_path(path.relative_to(root).as_posix())
            if relative == MANIFEST:
                continue
            raw = read_file(path)
            total += len(raw)
            if total > MAX_TOTAL or len(records) >= 250:
                raise ValueError("Rehearsal exceeds file/count limits")
            records.append({"path": relative, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return sorted(records, key=lambda row: row["path"])


def check_complete(root: Path) -> dict:
    status = loads(read_file(root / "run-status.json"))
    scorecard = loads(read_file(root / "rehearsal-scorecard.json"))
    if any(status.get(key) is not False for key in ("production_authorized", "empirical_calibration_complete")):
        raise ValueError("Run status scope/authorization flags are inconsistent")
    if status.get("scope") != "SYNTHETIC_PILOT_REHEARSAL" or status.get("status") != "COMPLETE" or scorecard.get("status") != "SOFTWARE_REHEARSAL_PASSED":
        raise ValueError("Only a completed synthetic rehearsal can be verified")
    if scorecard.get("scope") != "SYNTHETIC_PILOT_REHEARSAL" or any(scorecard.get(key) is not False for key in
            ("production_authorized", "empirical_calibration_complete", "live_integration_complete", "actual_shadow_pilot_complete")):
        raise ValueError("Rehearsal scope/authorization flags are inconsistent")
    return scorecard


def write_manifest(root: Path, *, replace=False) -> dict:
    scorecard = check_complete(root)
    manifest = {"schema_version": "1.0", "scope": "SYNTHETIC_REHEARSAL_FILE_MANIFEST",
                "source_fingerprint": scorecard["source_fingerprint"], "files": inventory(root),
                "production_authorized": False}
    target = root / MANIFEST
    if target.is_symlink():
        raise ValueError("Manifest must not be a symlink")
    with target.open("wb" if replace else "xb") as file:
        file.write(encode(manifest))
    return manifest


def verify_rehearsal(root: Path) -> dict:
    manifest = loads(read_file(root / MANIFEST, 256 * 1024))
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "scope", "source_fingerprint", "files", "production_authorized"}:
        raise ValueError("Invalid rehearsal manifest contract")
    if manifest["schema_version"] != "1.0" or manifest["scope"] != "SYNTHETIC_REHEARSAL_FILE_MANIFEST" or manifest["production_authorized"] is not False:
        raise ValueError("Invalid rehearsal manifest version/scope")
    records = manifest["files"]
    if not isinstance(records, list) or not 1 <= len(records) <= 250:
        raise ValueError("Invalid rehearsal manifest file count")
    names = set()
    for row in records:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise ValueError("Invalid rehearsal file record")
        name = safe_path(row["path"])
        if name in names or name == MANIFEST or type(row["bytes"]) is not int or not 0 <= row["bytes"] <= MAX_FILE or not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError("Invalid/duplicate rehearsal file record")
        names.add(name)
    if inventory(root) != records:
        raise ValueError("Rehearsal files differ from the manifest: missing, changed or extra content")
    scorecard = check_complete(root)
    provenance = loads(read_file(root / "source-provenance.json"))
    if digest(provenance["files"]) != provenance["source_fingerprint"] or provenance["source_fingerprint"] != manifest["source_fingerprint"] or scorecard["source_fingerprint"] != manifest["source_fingerprint"]:
        raise ValueError("Source provenance fingerprints differ")
    for directory in BUNDLE_DIRS:
        base = root / directory
        raw = read_file(base / "study-review.zip")
        verify_bundle(raw)
        with ZipFile(io.BytesIO(raw)) as archive:
            for name in ("study-input.json", "study-report.json"):
                if archive.read(name) != read_file(base / name):
                    raise ValueError("Loose study input/report differs from its verified bundle")
            if archive.read("study-review.html").decode().replace("\r\n", "\n") != read_file(base / "study-review.html").decode().replace("\r\n", "\n"):
                raise ValueError("Loose HTML review differs from its verified bundle")
    frozen = loads(read_file(root / "calibration/frozen-candidate.json"))
    if fit_candidate(read_file(root / "calibration/fitting-records.csv")) != frozen:
        raise ValueError("Fitting records do not reconstruct the frozen candidate")
    baseline, candidate, _, _ = evaluate_frozen(frozen, read_file(root / "calibration/heldout-export.csv"))
    for name, expected in (("baseline", baseline), ("candidate", candidate)):
        if digest(loads(read_file(root / f"calibration/{name}/study-input.json"))) != digest(expected):
            raise ValueError("Held-out study does not reconstruct from frozen fitting data")
    return {"scope": "SYNTHETIC_REHEARSAL_CONSISTENCY", "status": "VERIFIED_CONTENT",
            "verified_files": len(records), "verified_study_bundles": len(BUNDLE_DIRS),
            "source_fingerprint": manifest["source_fingerprint"], "production_authorized": False,
            "limitations": ["Manifest hashes and reconstruction check supplied content, not origin, authenticity, identity or approval.",
                            "Use the matching source checkout to reconstruct version-dependent reports."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_rehearsal(args.directory), indent=2))
    except Exception as exc:
        parser.exit(2, f"Rehearsal verification error: {exc}\n")


if __name__ == "__main__":
    main()
