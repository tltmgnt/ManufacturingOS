"""Metadata-only preflight for pilot handoffs; referenced sources are never opened."""
import argparse
import json
from pathlib import Path
import re

from manufacturing_os.calculations import fields
from manufacturing_os.jsonio import read_json
from manufacturing_os.models import digest
from .temporary_use_case import encode

REQUIREMENTS = {
    "M1": ("data_authority", "measurement_definitions", "frozen_fit", "heldout_results", "qualified_decision"),
    "M2": ("source_contract", "field_mapping", "read_only_permission", "audit_recovery_tests", "security_decision"),
    "M3": ("entry_decisions", "frozen_plan", "baseline", "measured_results", "qualified_acceptance"),
}


def text(value, label, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > 1024 or any(char in value for char in ("\r", "\n", "\x00")):
        raise ValueError(label + " must be a nonempty single-line string of at most 1024 characters")


def assess(plan):
    fields(plan, {"schema_version", "plan_id", "revision", "milestones"}, "pilot handoff index")
    if plan["schema_version"] != "1.0":
        raise ValueError("Unsupported handoff index version")
    text(plan["plan_id"], "plan ID"); text(plan["revision"], "revision")
    if not isinstance(plan["milestones"], list) or len(plan["milestones"]) != 3:
        raise ValueError("Handoff index requires exactly M1, M2 and M3")
    milestones = {}
    for item in plan["milestones"]:
        fields(item, {"milestone_id", "owner_reference", "evidence"}, "milestone record")
        key = item["milestone_id"]
        if not isinstance(key, str) or key not in REQUIREMENTS or key in milestones:
            raise ValueError("Unknown or duplicate milestone ID")
        text(item["owner_reference"], "owner reference", nullable=True)
        if not isinstance(item["evidence"], list) or len(item["evidence"]) > len(REQUIREMENTS[key]):
            raise ValueError("Invalid evidence-index size")
        records = {}
        for row in item["evidence"]:
            fields(row, {"requirement_id", "reference", "revision", "sha256"}, "evidence reference")
            requirement = row["requirement_id"]
            if not isinstance(requirement, str) or requirement not in REQUIREMENTS[key] or requirement in records:
                raise ValueError("Unknown or duplicate evidence requirement")
            text(row["reference"], "record reference", nullable=True)
            text(row["revision"], "record revision", nullable=True)
            if row["sha256"] is not None and (not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-fA-F]{64}", row["sha256"])):
                raise ValueError("Declared SHA-256 must be null or 64 hexadecimal characters")
            records[requirement] = row
        checks = []
        for requirement in REQUIREMENTS[key]:
            row = records.get(requirement)
            missing = [field for field in ("reference", "revision", "sha256") if row is None or row[field] is None]
            checks.append({"requirement_id": requirement,
                           "status": "MISSING_DECLARED_METADATA" if missing else "DECLARED_METADATA_PRESENT_NOT_VERIFIED",
                           "missing_fields": missing, "record": None if row is None else dict(row)})
        complete = item["owner_reference"] is not None and all(not row["missing_fields"] for row in checks)
        milestones[key] = {"milestone_id": key, "owner_reference": item["owner_reference"],
                           "missing_owner": item["owner_reference"] is None,
                           "status": "DECLARED_METADATA_COMPLETE_NOT_VERIFIED" if complete else "MISSING_DECLARED_METADATA",
                           "evidence_checks": checks, "closure_assessed": False}
    if set(milestones) != set(REQUIREMENTS):
        raise ValueError("Handoff index requires M1, M2 and M3")
    ordered = [milestones[key] for key in REQUIREMENTS]
    complete_count = sum(row["status"] == "DECLARED_METADATA_COMPLETE_NOT_VERIFIED" for row in ordered)
    return {"schema_version": "1.0", "scope": "PILOT_HANDOFF_METADATA_PREFLIGHT",
            "plan_id": plan["plan_id"], "revision": plan["revision"], "input_fingerprint": digest(plan),
            "status": "DECLARED_METADATA_COMPLETE_NOT_VERIFIED" if complete_count == 3 else "MISSING_DECLARED_METADATA",
            "milestones": ordered, "metadata_complete_milestones": complete_count,
            "missing_owners": sum(row["missing_owner"] for row in ordered),
            "missing_evidence_records": sum(bool(check["missing_fields"]) for row in ordered for check in row["evidence_checks"]),
            "external_sources_accessed": False, "source_hashes_verified": False, "identities_authenticated": False,
            "milestone_closure_assessed": False, "production_authorized": False,
            "limitations": ["Only declared reference presence and format are checked; references are never fetched or opened.",
                            "Declared hashes, owners and decisions do not establish source truth, identity or organizational acceptance.",
                            "Metadata completeness does not close any real-world milestone or authorize production."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--output", type=Path, help="New report file; existing output is preserved")
    args = parser.parse_args()
    try:
        result = assess(read_json(args.index, max_bytes=128*1024))
        if args.output:
            with args.output.open("xb") as file:
                file.write(encode(result))
        else:
            print(json.dumps(result, indent=2))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Pilot handoff preflight error: {exc}\n")
    return 0 if result["status"] == "DECLARED_METADATA_COMPLETE_NOT_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
