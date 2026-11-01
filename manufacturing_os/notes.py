"""Revision-bound reviewer annotations; identities and roles are self-declared."""
from copy import deepcopy
import json
from pathlib import Path

from .jsonio import read_json, MAX_REPORT_BYTES
from .calculations import fields, nonempty
from .evidence import utc_timestamp
from .models import digest
from .study import reconstruct_report

NOTES_VERSION = "review-notes-1.0"
DISPOSITIONS = ("COMMENT", "REQUEST_REVISION", "READY_FOR_FORMAL_REVIEW")
MAX_NOTES = 1000


def assess_notes(report: dict, log: dict) -> dict:
    reconstruct_report(report)
    fields(log, {"schema_version", "review_id", "revision", "study_fingerprint", "report_content_hash", "entries"}, "review notes")
    if log["schema_version"] != "1.0":
        raise ValueError("unsupported review notes schema")
    nonempty(log["review_id"], "review_id")
    if type(log["revision"]) is not int or log["revision"] <= 0:
        raise ValueError("review notes revision must be a positive integer")
    if log["study_fingerprint"] != report["study_fingerprint"] or log["report_content_hash"] != digest(report):
        raise ValueError("stale review notes: study or report content differs")
    if not isinstance(log["entries"], list) or not 1 <= len(log["entries"]) <= MAX_NOTES:
        raise ValueError("review notes require 1 to 1000 entries")
    seen, roles, requests = set(), set(), []
    previous_time = None
    codes = {finding["code"] for finding in report["findings"]}
    for entry in log["entries"]:
        fields(entry, {"note_id", "reviewer", "role", "timestamp", "disposition", "comment", "finding_code"}, "review note")
        for key in ("note_id", "reviewer", "role", "comment"):
            nonempty(entry[key], key)
        if len(entry["comment"]) > 10000:
            raise ValueError("review comment exceeds 10000 characters")
        if entry["note_id"] in seen:
            raise ValueError("duplicate review note ID")
        seen.add(entry["note_id"])
        if entry["role"] not in report["required_approvals"]:
            raise ValueError("review role must be one of the study's required approval roles")
        roles.add(entry["role"])
        stamp = utc_timestamp(entry["timestamp"])
        if previous_time is not None and stamp < previous_time:
            raise ValueError("review note timestamps must be chronological")
        previous_time = stamp
        if entry["disposition"] not in DISPOSITIONS:
            raise ValueError("invalid review disposition; approval is not supported")
        if entry["finding_code"] is not None and (not isinstance(entry["finding_code"], str) or entry["finding_code"] not in codes):
            raise ValueError("review note refers to an unknown study finding")
        if entry["disposition"] == "REQUEST_REVISION":
            requests.append(entry["note_id"])
    return {"schema_version": "1.0", "notes_version": NOTES_VERSION,
            "review_id": log["review_id"], "review_revision": log["revision"], "notes_fingerprint": digest(log),
            "study_fingerprint": report["study_fingerprint"], "report_content_hash": digest(report),
            "note_count": len(log["entries"]), "requested_revision_note_ids": requests,
            "roles_with_notes": sorted(roles), "roles_without_notes": sorted(set(report["required_approvals"])-roles),
            "state": "REQUESTED_CHANGES" if requests else "NOTES_RECORDED",
            "limitations": ["Reviewer names and roles are supplied declarations, not authenticated identities or signatures.",
                            "Requests remain recorded for this exact report; later comments or readiness notes do not erase them.",
                            "Notes and readiness dispositions are feedback only; required formal approvals remain pending."],
            "approval_state": "PENDING_HUMAN_REVIEW", "production_authorized": False}


def add_note(report: dict, entry: dict, previous: dict | None = None, review_id: str | None = None) -> dict:
    reconstruct_report(report)
    if previous is None:
        log = {"schema_version": "1.0", "review_id": review_id if review_id is not None else report["study_id"]+"/review-notes",
               "revision": 1, "study_fingerprint": report["study_fingerprint"], "report_content_hash": digest(report),
               "entries": []}
    else:
        assess_notes(report, previous)
        if review_id is not None and review_id != previous["review_id"]:
            raise ValueError("cannot change review_id while appending notes")
        log = deepcopy(previous)
        log["revision"] += 1
    log["entries"].append(deepcopy(entry))
    assess_notes(report, log)
    return log


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Record or check feedback against an exact study report")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("report", type=Path)
    add.add_argument("--notes", type=Path, help="Existing note log to append into a new output file")
    add.add_argument("--review-id")
    for name in ("note-id", "reviewer", "role", "timestamp", "comment"):
        add.add_argument("--"+name, required=True)
    add.add_argument("--disposition", required=True, choices=DISPOSITIONS)
    add.add_argument("--finding-code")
    add.add_argument("--output", required=True, type=Path)
    check = commands.add_parser("check")
    check.add_argument("report", type=Path)
    check.add_argument("notes", type=Path)
    args = parser.parse_args(argv)
    try:
        report = read_json(args.report, max_bytes=MAX_REPORT_BYTES)
        if args.command == "add":
            entry = {key: getattr(args, key) for key in ("note_id", "reviewer", "role", "timestamp", "comment", "disposition", "finding_code")}
            prior = read_json(args.notes, max_bytes=MAX_REPORT_BYTES) if args.notes else None
            log = add_note(report, entry, prior, args.review_id)
            result = assess_notes(report, log)
            with args.output.open("x", encoding="utf-8") as file:
                file.write(json.dumps(log, indent=2, sort_keys=True, allow_nan=False)+"\n")
        else:
            result = assess_notes(report, read_json(args.notes, max_bytes=MAX_REPORT_BYTES))
        print(json.dumps(result, sort_keys=True))
        return 1 if result["state"] == "REQUESTED_CHANGES" else 0
    except (ValueError, TypeError, KeyError, OSError, OverflowError, ZeroDivisionError) as exc:
        print(f"Review notes error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
