"""Local source snapshots for rehearsal traceability; not signed build provenance."""
import hashlib
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys

from manufacturing_os._version import __version__
from manufacturing_os.models import digest

SOURCE_ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024


def source_records(root: Path) -> list[dict]:
    root = root.resolve()
    paths = [root / "pyproject.toml"]
    for directory in ("manufacturing_os", "examples"):
        base = root / directory
        if base.is_symlink() or not base.is_dir():
            raise ValueError("Expected regular source directories")
        for path in base.rglob("*"):
            if path.is_symlink():
                raise ValueError("Source snapshot does not follow symlinks")
            if path.is_file() and path.suffix in (".py", ".json", ".csv"):
                paths.append(path)
    records, total = [], 0
    for path in sorted(paths):
        if path.is_symlink():
            raise ValueError("Source snapshot does not follow symlinks")
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags), "rb") as file:
            before = os.fstat(file.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
                raise ValueError("Source snapshot requires bounded regular files")
            raw = file.read(MAX_FILE_BYTES + 1)
            after = os.fstat(file.fileno())
        if len(raw) > MAX_FILE_BYTES or len(raw) != after.st_size or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("Source changed during snapshot capture")
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Source snapshot exceeds total byte limit")
        records.append({"path": path.relative_to(root).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return records


def git_context(root: Path) -> dict:
    context = {"git_commit": None, "captured_source_roots_dirty": None}
    try:
        def git(*args):
            return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=2, check=True).stdout.strip()
        if Path(git("rev-parse", "--show-toplevel")).resolve() != root.resolve():
            return context
        commit = git("rev-parse", "HEAD")
        if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
            return context
        dirty = bool(git("status", "--porcelain", "--untracked-files=normal", "--", "manufacturing_os", "examples", "pyproject.toml"))
        return {"git_commit": commit, "captured_source_roots_dirty": dirty}
    except (OSError, ValueError, subprocess.SubprocessError):
        return context


def capture_provenance(root: Path = SOURCE_ROOT) -> dict:
    root = root.resolve()
    records = source_records(root)
    return {"schema_version": "1.0", "scope": "LOCAL_REHEARSAL_SOURCE_SNAPSHOT",
            "software_version": __version__, "source_fingerprint": digest(records), "files": records,
            "python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
            "platform": sys.platform, "machine": platform.machine(), **git_context(root),
            "limitations": ["Hashes describe local package/example source files and pyproject, not authenticated loaded code or a signed build.",
                            "Git commit alone does not identify uncommitted source changes; retain the source hashes and any required patch.",
                            "Tests, documentation, system libraries and external environment are not included in the source fingerprint."]}


def verify_source_unchanged(provenance: dict, root: Path = SOURCE_ROOT) -> None:
    if digest(source_records(root)) != provenance["source_fingerprint"]:
        raise ValueError("Rehearsal source changed during execution; no successful scorecard published")
