"""Portable campaign overview, per-case reviews, and reconstructable manifests."""
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import zipfile
import zlib

from .bundle import MAX_ARCHIVE_BYTES,MAX_CONTENT_BYTES,publish
from .campaign import MAX_CASES,MAX_INPUT_BYTES,encode,run_campaign
from .campaign_review import render_campaign_review
from .review import render_review

BUNDLE_VERSION = "campaign-bundle-1.0"
BASE_NAMES = {"campaign-input.json","campaign-report.json","campaign-review.html","README.txt","manifest.json"}
CASE_PATH = re.compile(r"cases/[0-9]{3}/(?:study-report\.json|study-review\.html|error\.json)\Z")
README = """ManufacturingOS software-scenario campaign bundle

Open campaign-review.html after extracting with your normal archive tool.
The overview links to indexed per-case study reviews and JSON reports.
Execution-error cases retain error.json instead of a fabricated study report.
campaign-input.json and campaign-report.json preserve complete inputs/results.
manifest.json records SHA-256 hashes and byte sizes of each content file.

Verify without extracting:
  manufacturing-os campaign-bundle verify PATH_TO_BUNDLE.zip

Content verification is not a signature, authentication, calibration, or approval.
Campaign PASS means configured software expectations matched; blocked studies
remain blocked. Production authorization remains false. Captured source bytes
travel in the explicit study inputs and full reports.
"""


def content_files(spec: dict) -> tuple[dict[str,bytes],dict]:
    report = run_campaign(spec)
    files = {"campaign-input.json":encode(spec),"campaign-report.json":encode(report),
             "campaign-review.html":render_campaign_review(report).encode("utf-8"),"README.txt":README.encode("utf-8")}
    for index,case in enumerate(report["cases"],1):
        prefix = f"cases/{index:03d}/"
        if case["study_report"] is None:
            files[prefix+"error.json"] = encode({"case_id":case["case_id"],"error":case["error"],"mismatches":case["mismatches"]})
        else:
            files[prefix+"study-report.json"] = encode(case["study_report"])
            files[prefix+"study-review.html"] = render_review(case["study_report"]).encode("utf-8")
        if sum(map(len,files.values())) > MAX_CONTENT_BYTES:
            raise ValueError("campaign bundle contents exceed 128 MiB")
    manifest = {"schema_version":"1.0","bundle_version":BUNDLE_VERSION,"campaign_id":report["campaign_id"],
                "campaign_revision":report["campaign_revision"],"campaign_fingerprint":report["campaign_fingerprint"],
                "campaign_status":report["status"],"revision_required_studies":report["revision_required_studies"],
                "files":{name:{"sha256":hashlib.sha256(data).hexdigest(),"size_bytes":len(data)} for name,data in sorted(files.items())},
                "approval_state":"PENDING_HUMAN_REVIEW","production_authorized":False}
    files["manifest.json"] = encode(manifest)
    if sum(map(len,files.values())) > MAX_CONTENT_BYTES:
        raise ValueError("campaign bundle contents exceed 128 MiB")
    return files,report


def build_campaign_bundle(spec: dict) -> bytes:
    files,_ = content_files(spec)
    output = io.BytesIO()
    with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            info = zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG|0o644)<<16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info,data,compresslevel=9)
    data = output.getvalue()
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("compressed campaign bundle exceeds 64 MiB")
    return data


def verify_campaign_bundle(data: bytes) -> dict:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("compressed campaign bundle exceeds 64 MiB")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names)!=len(set(names)):
            raise ValueError("duplicate campaign bundle paths")
        if len(names)>len(BASE_NAMES)+2*MAX_CASES or not BASE_NAMES<=set(names):
            raise ValueError("invalid campaign bundle file set")
        if any(name not in BASE_NAMES and CASE_PATH.fullmatch(name) is None for name in names):
            raise ValueError("unexpected campaign bundle path")
        if sum(entry.file_size for entry in entries)>MAX_CONTENT_BYTES:
            raise ValueError("campaign bundle contents exceed 128 MiB")
        for entry in entries:
            if entry.is_dir() or stat.S_IFMT(entry.external_attr>>16) not in (0,stat.S_IFREG) or entry.flag_bits&1:
                raise ValueError("non-regular entries, directories, symlinks, and encrypted entries are unsupported")
            if entry.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
                raise ValueError("unsupported campaign bundle compression")
        files = {name:archive.read(name) for name in names}
    expected,report = content_files(json.loads(files["campaign-input.json"]))
    if set(files)!=set(expected):
        raise ValueError("campaign bundle file set differs from reconstruction")
    for name in sorted(expected):
        if files[name]!=expected[name]:
            raise ValueError("campaign bundle content differs from reconstruction: "+name)
    return {"status":"VERIFIED_CONTENT","bundle_version":BUNDLE_VERSION,"campaign_id":report["campaign_id"],
            "campaign_status":report["status"],"case_count":report["case_count"],
            "revision_required_studies":report["revision_required_studies"],"execution_errors":report["execution_errors"],
            "verified_files":sorted(expected),"scope":"CONTENT_RECONSTRUCTION_ONLY",
            "approval_state":"PENDING_HUMAN_REVIEW","production_authorized":False}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Create or verify portable campaign reviews")
    commands = parser.add_subparsers(dest="command",required=True)
    create = commands.add_parser("create")
    create.add_argument("input",type=Path)
    create.add_argument("--output",type=Path,required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("archive",type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command=="create":
            if args.input.stat().st_size>MAX_INPUT_BYTES:
                raise ValueError("campaign input exceeds 32 MiB")
            data = build_campaign_bundle(json.loads(args.input.read_text(encoding="utf-8")))
            publish(args.output,data)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                manifest = json.loads(archive.read("manifest.json"))
            result = {"status":"CREATED","archive":str(args.output),"size_bytes":len(data),
                      "campaign_status":manifest["campaign_status"],"revision_required_studies":manifest["revision_required_studies"],
                      "production_authorized":False}
        else:
            if args.archive.stat().st_size>MAX_ARCHIVE_BYTES:
                raise ValueError("compressed campaign bundle exceeds 64 MiB")
            result = verify_campaign_bundle(args.archive.read_bytes())
        print(json.dumps(result,sort_keys=True))
    except (ValueError,TypeError,KeyError,OSError,OverflowError,ZeroDivisionError,zipfile.BadZipFile,zlib.error,EOFError,RuntimeError,NotImplementedError) as exc:
        print(f"Campaign bundle error: {exc}",file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
