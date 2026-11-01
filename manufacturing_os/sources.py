"""Verify captured source bytes against declared evidence hashes, without I/O."""
import base64
import binascii
import hashlib
import json
from pathlib import Path
import re

from .calculations import fields, nonempty
from .models import ManufacturingInput, digest

SOURCE_VERSION = "captured-sources-1.0"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_FILES = 1000


def verify_sources(data: dict, snapshot: dict) -> dict:
    package = ManufacturingInput.from_dict(data)
    fields(snapshot, {"schema_version", "snapshot_id", "revision", "input_fingerprint", "files"}, "source snapshot")
    if snapshot["schema_version"] != "1.0":
        raise ValueError("unsupported source snapshot schema")
    for key in ("snapshot_id", "revision", "input_fingerprint"):
        nonempty(snapshot[key], key)
    if snapshot["input_fingerprint"] != package.fingerprint:
        raise ValueError("stale source snapshot input fingerprint")
    if not isinstance(snapshot["files"], list) or len(snapshot["files"]) > MAX_SOURCE_FILES:
        raise ValueError("snapshot files must be a list of at most 1000 records")
    evidence_ids = {record.evidence_id for record in package.evidence}
    captured = {}
    total = 0
    for row in snapshot["files"]:
        fields(row, {"evidence_id", "content_base64"}, "captured source")
        nonempty(row["evidence_id"], "evidence_id")
        if row["evidence_id"] not in evidence_ids or row["evidence_id"] in captured:
            raise ValueError("unknown or duplicate snapshot evidence ID")
        encoded = row["content_base64"]
        if not isinstance(encoded, str) or len(encoded) > 4*((MAX_SOURCE_BYTES+2)//3):
            raise ValueError("source content must be bounded base64 text")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("invalid source base64") from exc
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise ValueError("source base64 must be canonical")
        total += len(raw)
        if total > MAX_SOURCE_BYTES:
            raise ValueError("captured sources exceed 16 MiB")
        captured[row["evidence_id"]] = {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
    records, coverage = [], {row["requirement_id"]: [] for row in package.requirements}
    for record in sorted(package.evidence, key=lambda item: item.evidence_id):
        actual = captured.get(record.evidence_id)
        expected = record.content_hash
        if actual is None:
            status = "MISSING_CAPTURED_CONTENT"
        elif expected is None:
            status = "MISSING_DECLARED_SHA256"
        elif re.fullmatch(r"[0-9a-fA-F]{64}", expected) is None:
            status = "INVALID_DECLARED_SHA256"
        elif actual["sha256"] != expected.lower():
            status = "HASH_MISMATCH"
        else:
            status = "HASH_MATCHED"
            for claim in sorted(set(record.claim_ids)):
                coverage[claim].append(record.evidence_id)
        records.append({"evidence_id": record.evidence_id, "source_uri": record.source_uri,
                        "source_revision": record.revision, "declared_sha256": expected,
                        "captured_sha256": actual["sha256"] if actual else None,
                        "captured_size_bytes": actual["size_bytes"] if actual else None, "status": status})
    missing = sorted(claim for claim, refs in coverage.items() if not refs)
    excluded = sum(record["status"] != "HASH_MATCHED" for record in records)
    return {"schema_version": "1.0", "source_version": SOURCE_VERSION,
            "snapshot_id": snapshot["snapshot_id"], "snapshot_revision": snapshot["revision"],
            "input_fingerprint": package.fingerprint, "snapshot_fingerprint": digest(snapshot),
            "status": "CONTENT_COVERAGE_GAPS" if missing else "CAPTURED_CONTENT_COVERED_WITH_EXCLUSIONS" if excluded else "CAPTURED_CONTENT_COVERED",
            "unmatched_record_count": excluded,
            "records": records, "hash_matched_coverage": {claim: sorted(refs) for claim,refs in sorted(coverage.items())},
            "uncovered_requirements": missing, "captured_total_bytes": total,
            "limitations": ["Hashes compare supplied captured bytes with supplied declarations; neither establishes authentic origin or claim truth.",
                            "Hash coverage does not include freshness or pinned metadata checks; integrated studies combine both independently.",
                            "Source URIs are labels only; this verifier performs no network, filesystem, decoding, or document execution beyond base64 decoding."],
            "production_authorized": False}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Check captured bytes against declared evidence SHA-256 hashes")
    parser.add_argument("input", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output", type=Path, help="Create a new source verification report without overwriting")
    args = parser.parse_args(argv)
    try:
        report = verify_sources(json.loads(args.input.read_text(encoding="utf-8")), json.loads(args.snapshot.read_text(encoding="utf-8")))
        encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+"\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as file:
                file.write(encoded)
        else:
            print(encoded, end="")
        return 1 if report["status"] == "CONTENT_COVERAGE_GAPS" else 0
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        print(f"Source verification error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
