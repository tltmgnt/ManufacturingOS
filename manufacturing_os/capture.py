"""Capture explicitly selected local files into an input-bound source snapshot."""
import base64
from contextlib import ExitStack
import json
import os
from pathlib import Path, PurePosixPath
import stat

from .jsonio import read_json
from .calculations import fields, nonempty
from .models import ManufacturingInput
from .sources import MAX_SOURCE_BYTES, MAX_SOURCE_FILES, verify_sources


def relative_parts(value: str) -> tuple[str, ...]:
    nonempty(value, "relative source path")
    path = PurePosixPath(value)
    if (path.is_absolute() or not path.parts or ".." in path.parts or "\\" in value
            or ":" in value or str(path) != value):
        raise ValueError("source paths must be canonical relative POSIX paths without traversal")
    return path.parts


def fingerprint(metadata: os.stat_result) -> tuple:
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns)


def read_selected(root_fd: int, parts: tuple[str, ...], limit: int) -> bytes:
    with ExitStack() as stack:
        directory = root_fd
        for part in parts[:-1]:
            directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            stack.callback(os.close, directory)
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        stack.callback(os.close, descriptor)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("captured source must be a regular file")
        if before.st_size > limit:
            raise ValueError("captured sources exceed 16 MiB")
        # Keep the descriptor open for both stat checks; never reopen by path.
        chunks, count = [], 0
        while count <= limit:
            chunk = os.read(descriptor, min(65536, limit+1-count))
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
        if count > limit:
            raise ValueError("captured sources exceed 16 MiB")
        after = os.fstat(descriptor)
        if fingerprint(before) != fingerprint(after):
            raise ValueError("source changed during capture; retry with a stable file")
        return b"".join(chunks)


def capture_sources(data: dict, manifest: dict, root: str | Path) -> dict:
    package = ManufacturingInput.from_dict(data)
    fields(manifest, {"schema_version", "snapshot_id", "revision", "files"}, "capture manifest")
    if manifest["schema_version"] != "1.0":
        raise ValueError("unsupported capture manifest schema")
    for key in ("snapshot_id", "revision"):
        nonempty(manifest[key], key)
    if not isinstance(manifest["files"], list) or len(manifest["files"]) > MAX_SOURCE_FILES:
        raise ValueError("capture files must be a list of at most 1000 records")
    ids = {record.evidence_id for record in package.evidence}
    selected, paths = {}, set()
    # Validate every selection before opening any source files.
    for row in manifest["files"]:
        fields(row, {"evidence_id", "path"}, "capture selection")
        nonempty(row["evidence_id"], "evidence_id")
        if row["evidence_id"] not in ids or row["evidence_id"] in selected:
            raise ValueError("unknown or duplicate capture evidence ID")
        parts = relative_parts(row["path"])
        if parts in paths:
            raise ValueError("duplicate capture source path")
        paths.add(parts)
        selected[row["evidence_id"]] = parts
    if (os.name != "posix" or os.open not in os.supports_dir_fd
            or not all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"))):
        raise ValueError("secure file capture requires POSIX descriptor-relative no-follow support")
    root_path = Path(root).resolve(strict=True)
    total, files = 0, []
    descriptor = os.open(root_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for evidence_id, parts in sorted(selected.items()):
            raw = read_selected(descriptor, parts, MAX_SOURCE_BYTES-total)
            total += len(raw)
            files.append({"evidence_id": evidence_id, "content_base64": base64.b64encode(raw).decode("ascii")})
    finally:
        os.close(descriptor)
    return {"schema_version": "1.0", "snapshot_id": manifest["snapshot_id"], "revision": manifest["revision"],
            "input_fingerprint": package.fingerprint, "files": files}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Capture only manifest-selected files under an explicit local root")
    parser.add_argument("input", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Create a new source snapshot without overwriting")
    args = parser.parse_args(argv)
    try:
        data = read_json(args.input)
        snapshot = capture_sources(data, read_json(args.manifest), args.root)
        verification = verify_sources(data, snapshot)
        encoded = json.dumps(snapshot, indent=2, sort_keys=True, allow_nan=False)+"\n"
        with args.output.open("x", encoding="utf-8") as file:
            file.write(encoded)
        print(json.dumps({"snapshot": str(args.output), "snapshot_id": snapshot["snapshot_id"],
                          "captured_files": len(snapshot["files"]), "captured_total_bytes": verification["captured_total_bytes"],
                          "content_status": verification["status"], "production_authorized": False}, sort_keys=True))
        return 1 if verification["status"] == "CONTENT_COVERAGE_GAPS" else 0
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        print(f"Capture error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
