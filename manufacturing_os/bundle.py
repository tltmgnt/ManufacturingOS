"""Portable study bundles with deterministic contents and local reconstruction."""
import hashlib
import io
import json
from pathlib import Path
import stat
import zipfile
import zlib

from .compare import compare_studies
from .review import render_review
from .notes import assess_notes
from .study import run_study

BUNDLE_VERSION = "study-bundle-1.0"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_CONTENT_BYTES = 128 * 1024 * 1024
BASE_NAMES = {"study-input.json", "study-report.json", "study-review.html", "README.txt", "manifest.json"}
OPTIONAL_NAMES = {"previous-study-report.json", "comparison.json"}
NOTE_NAMES = {"review-notes.json", "review-notes-assessment.json"}
README = """ManufacturingOS advisory study bundle

Open study-review.html in a browser for the offline review summary.
study-report.json contains exact metrics, timelines, samples, and provenance.
study-input.json is the original versioned study input.
Optional previous-study-report.json and comparison.json show revision changes.
manifest.json records SHA-256 hashes and byte sizes of each content file.

Verify without extracting:
  python -m manufacturing_os.bundle verify PATH_TO_BUNDLE.zip

Verification checks content consistency and reconstruction with the current
implementation. It is not a digital signature, proof of source truth, human
approval, or facility validation. Models remain unvalidated; all required
approvals are pending and production authorization remains false.
"""


def encode(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n").encode("utf-8")


def content_files(spec: dict, previous: dict | None = None, notes: dict | None = None) -> tuple[dict[str, bytes], dict]:
    report = run_study(spec)
    files = {"study-input.json": encode(spec), "study-report.json": encode(report),
             "study-review.html": render_review(report, notes).encode("utf-8"), "README.txt": README.encode("utf-8")}
    if previous is not None:
        comparison = compare_studies(previous, report)
        files["previous-study-report.json"] = encode(previous)
        files["comparison.json"] = encode(comparison)
    if notes is not None:
        files["review-notes.json"] = encode(notes)
        files["review-notes-assessment.json"] = encode(assess_notes(report, notes))
        files["README.txt"] += b"\nOptional review-notes.json and review-notes-assessment.json contain declared reviewer feedback, not approvals.\n"
    manifest = {"schema_version": "1.0", "bundle_version": BUNDLE_VERSION,
                "study_id": report["study_id"], "study_revision": report["study_revision"],
                "study_fingerprint": report["study_fingerprint"], "review_state": report["review_state"],
                "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
                          for name, data in sorted(files.items())},
                "approval_state": "PENDING_HUMAN_REVIEW", "production_authorized": False}
    if notes is not None:
        manifest["notes_state"] = json.loads(files["review-notes-assessment.json"])["state"]
    files["manifest.json"] = encode(manifest)
    if sum(len(data) for data in files.values()) > MAX_CONTENT_BYTES:
        raise ValueError("bundle contents exceed 128 MiB")
    return files, report


def build_bundle(spec: dict, previous: dict | None = None, notes: dict | None = None) -> bytes:
    files, _ = content_files(spec, previous, notes)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    result = output.getvalue()
    if len(result) > MAX_ARCHIVE_BYTES:
        raise ValueError("compressed bundle exceeds 64 MiB")
    return result


def verify_bundle(data: bytes) -> dict:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("compressed bundle exceeds 64 MiB")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError("duplicate bundle paths")
        if not BASE_NAMES <= set(names) or not set(names) <= BASE_NAMES | OPTIONAL_NAMES | NOTE_NAMES:
            raise ValueError("missing or unexpected bundle paths")
        if bool(set(names) & OPTIONAL_NAMES) and not OPTIONAL_NAMES <= set(names):
            raise ValueError("optional comparison files must occur together")
        if bool(set(names) & NOTE_NAMES) and not NOTE_NAMES <= set(names):
            raise ValueError("optional note files must occur together")
        if sum(entry.file_size for entry in entries) > MAX_CONTENT_BYTES:
            raise ValueError("bundle contents exceed 128 MiB")
        for entry in entries:
            mode = entry.external_attr >> 16
            if entry.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or entry.flag_bits & 1:
                raise ValueError("non-regular entries, directories, symbolic links, and encrypted entries are unsupported")
            if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError("unsupported bundle compression")
        files = {name: archive.read(name) for name in names}
    # Rebuild expected files from the authoritative input; matching checksums
    # alone are insufficient if a report and its manifest were edited together.
    spec = json.loads(files["study-input.json"])
    previous = json.loads(files["previous-study-report.json"]) if "previous-study-report.json" in files else None
    notes = json.loads(files["review-notes.json"]) if "review-notes.json" in files else None
    expected, report = content_files(spec, previous, notes)
    if set(files) != set(expected):
        raise ValueError("bundle file set differs from reconstruction")
    for name in sorted(expected):
        if files[name] != expected[name]:
            raise ValueError(f"bundle content differs from reconstruction: {name}")
    result = {"status": "VERIFIED_CONTENT", "bundle_version": BUNDLE_VERSION,
            "study_id": report["study_id"], "study_revision": report["study_revision"],
            "review_state": report["review_state"], "verified_files": sorted(expected),
            "approval_state": "PENDING_HUMAN_REVIEW", "production_authorized": False,
            "scope": "Content consistency and reconstruction only; no signature, source validation, or approval."}
    if notes is not None:
        result["notes_state"] = json.loads(expected["review-notes-assessment.json"])["state"]
    return result


def publish(path: Path, data: bytes) -> None:
    """Exclusive output; remove our partial file if a write fails."""
    with path.open("xb") as file:
        try:
            file.write(data)
        except BaseException:
            file.close()
            path.unlink(missing_ok=True)
            raise


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Create or verify a portable advisory study bundle")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("input", type=Path)
    create.add_argument("--before", type=Path, help="Optional complete previous study report")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--notes", type=Path, help="Optional reviewer notes bound to the generated study report")
    verify = subparsers.add_parser("verify")
    verify.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            spec = json.loads(args.input.read_text(encoding="utf-8"))
            previous = json.loads(args.before.read_text(encoding="utf-8")) if args.before else None
            notes = json.loads(args.notes.read_text(encoding="utf-8")) if args.notes else None
            data = build_bundle(spec, previous, notes)
            publish(args.output, data)
            # The study state is reported, but does not turn bundle creation into
            # an approval/feasibility gate. Revision-required studies are portable.
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                bundle_manifest = json.loads(archive.read("manifest.json"))
                state = bundle_manifest["review_state"]
            result = {"status": "CREATED", "archive": str(args.output), "size_bytes": len(data),
                      "review_state": state, "production_authorized": False}
            if "notes_state" in bundle_manifest:
                result["notes_state"] = bundle_manifest["notes_state"]
        else:
            if args.archive.stat().st_size > MAX_ARCHIVE_BYTES:
                raise ValueError("compressed bundle exceeds 64 MiB")
            result = verify_bundle(args.archive.read_bytes())
        print(json.dumps(result, sort_keys=True))
    except (ValueError, TypeError, KeyError, OSError, OverflowError, ZeroDivisionError,
            zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError) as exc:
        print(f"Bundle error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
