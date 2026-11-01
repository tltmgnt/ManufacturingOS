"""Deterministic evidence metadata policy checks; no network/source verification."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import re

from .calculations import fields, measure, nonempty, quantity
from .models import ManufacturingInput, digest

EVIDENCE_VERSION = "evidence-policy-1.0"


def utc_timestamp(value: str) -> datetime:
    stamp = datetime.fromisoformat(nonempty(value, "UTC timestamp").replace("Z", "+00:00"))
    if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError("policy timestamps must be timezone-aware UTC")
    return stamp


def assess_evidence(data: dict, policy: dict) -> dict:
    package = ManufacturingInput.from_dict(data)
    fields(policy, {"schema_version", "policy_id", "revision", "as_of", "max_age", "require_declared_sha256", "sources"}, "evidence policy")
    if policy["schema_version"] != "1.0":
        raise ValueError("unsupported evidence policy schema")
    for key in ("policy_id", "revision"):
        nonempty(policy[key], key)
    as_of = utc_timestamp(policy["as_of"])
    max_age = measure(policy["max_age"], "day")
    if type(policy["require_declared_sha256"]) is not bool:
        raise ValueError("require_declared_sha256 must be boolean")
    if not isinstance(policy["sources"], list) or not policy["sources"]:
        raise ValueError("policy must pin at least one source")
    sources = {}
    for source in policy["sources"]:
        fields(source, {"source_uri", "source_owner", "revision", "evidence_type"}, "pinned source")
        for key, value in source.items():
            nonempty(value, key)
        if source["source_uri"] in sources:
            raise ValueError("duplicate pinned source URI")
        sources[source["source_uri"]] = source
    coverage = {row["requirement_id"]: [] for row in package.requirements}
    records = []
    for record in sorted(package.evidence, key=lambda item: item.evidence_id):
        issues = []
        age = (as_of - utc_timestamp(record.captured_at)).total_seconds()/86400
        if age < 0:
            issues.append("FUTURE_CAPTURE_TIMESTAMP")
        elif age > max_age:
            issues.append("STALE_EVIDENCE")
        pinned = sources.get(record.source_uri)
        if pinned is None:
            issues.append("UNPINNED_SOURCE")
        else:
            for key, code in [("source_owner", "SOURCE_OWNER_MISMATCH"), ("revision", "SOURCE_REVISION_MISMATCH"),
                              ("evidence_type", "EVIDENCE_TYPE_MISMATCH")]:
                if getattr(record, key) != pinned[key]:
                    issues.append(code)
        hash_valid = record.content_hash is not None and re.fullmatch(r"[0-9a-fA-F]{64}", record.content_hash) is not None
        if record.content_hash is not None and not hash_valid:
            issues.append("INVALID_DECLARED_SHA256")
        if record.content_hash is None and policy["require_declared_sha256"]:
            issues.append("MISSING_DECLARED_SHA256")
        eligible = not issues
        if eligible:
            for claim in sorted(set(record.claim_ids)):
                coverage[claim].append(record.evidence_id)
        records.append({"evidence_id": record.evidence_id, "source_uri": record.source_uri,
                        "source_revision": record.revision, "age": quantity(age, "day"),
                        "metadata_eligible": eligible, "issues": issues,
                        "declared_hash_status": "DECLARED_NOT_VERIFIED" if hash_valid else "ABSENT" if record.content_hash is None else "INVALID",
                        "claim_ids": sorted(set(record.claim_ids))})
    missing = sorted(claim for claim, refs in coverage.items() if not refs)
    excluded = sum(not row["metadata_eligible"] for row in records)
    return {"schema_version": "1.0", "evidence_version": EVIDENCE_VERSION,
            "policy_id": policy["policy_id"], "policy_revision": policy["revision"],
            "input_fingerprint": package.fingerprint, "policy_fingerprint": digest(policy), "policy": deepcopy(policy),
            "status": "COVERAGE_GAPS" if missing else "COVERED_WITH_EXCLUSIONS" if excluded else "METADATA_CHECKS_PASSED",
            "records": records, "eligible_coverage": {claim: sorted(refs) for claim, refs in sorted(coverage.items())},
            "uncovered_requirements": missing, "ineligible_record_count": excluded,
            "limitations": ["Checks declared metadata only; source identity, source bytes, hashes, and claim truth are not independently verified.",
                            "Capture age is measured against the explicit policy as_of timestamp; it is not the age of the underlying source content.",
                            "Coverage means an eligible record names a requirement, not that the requirement has been substantively verified."],
            "production_authorized": False}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Check declared evidence metadata against a pinned policy")
    parser.add_argument("input", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--output", type=Path, help="Create a new JSON report without overwriting")
    args = parser.parse_args(argv)
    try:
        result = assess_evidence(json.loads(args.input.read_text(encoding="utf-8")), json.loads(args.policy.read_text(encoding="utf-8")))
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+"\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as file:
                file.write(encoded)
        else:
            print(encoded, end="")
        return 1 if result["status"] == "COVERAGE_GAPS" else 0
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        print(f"Evidence policy error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
