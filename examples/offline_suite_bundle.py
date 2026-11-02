"""Portable ZIPs for verified synthetic suites; private temporary staging only."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import struct
import tempfile
import unicodedata
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from manufacturing_os.jsonio import loads
from .offline_suite_integrity import MANIFEST, verify_suite
from .rehearsal_integrity import MAX_FILE, read_file, safe_path

MAX_ARCHIVE = 256 * 1024 * 1024
MAX_CONTENT = 256 * 1024 * 1024


def checked_entries(raw):
    if len(raw) > MAX_ARCHIVE or len(raw) < 22 or raw[:4] != b"PK\x03\x04" or raw[-22:-18] != b"PK\x05\x06":
        raise ValueError("Invalid or excessive suite ZIP")
    _, disk, central_disk, disk_count, count, size, offset, comment = struct.unpack("<4s4H2LH", raw[-22:])
    if disk or central_disk or disk_count != count or not 1 <= count <= 500 or size > 1024*1024 or offset + size != len(raw)-22 or comment:
        raise ValueError("Unsupported ZIP directory, count, metadata, or multipart/ZIP64 structure")
    archive = ZipFile(io.BytesIO(raw))
    try:
        infos = archive.infolist()
        if len(infos) != count:
            raise ValueError("Suite ZIP entry count differs from directory metadata")
        names, aliases, total = set(), set(), 0
        for info in infos:
            name = safe_path(info.filename)
            alias = unicodedata.normalize("NFC", name).casefold()
            reserved = {"con", "prn", "aux", "nul", *[f"com{i}" for i in range(1, 10)], *[f"lpt{i}" for i in range(1, 10)]}
            if info.orig_filename != name:
                raise ValueError("Unsupported portable suite ZIP path")
            for part in PurePosixPath(name).parts:
                stem = unicodedata.normalize("NFKC", part.split(".", 1)[0]).strip(" .").casefold()
                if part.rstrip(" .") != part or stem in reserved or any(ord(char) < 32 or char in '<>"|?*' for char in part):
                    raise ValueError("Unsupported portable suite ZIP path")
            if name in names or alias in aliases:
                raise ValueError("Duplicate or case-colliding suite ZIP path")
            names.add(name); aliases.add(alias)
            if info.is_dir() or stat.S_IFMT(info.external_attr >> 16) not in (0, stat.S_IFREG):
                raise ValueError("Suite ZIP supports only regular files")
            if info.flag_bits & 1 or info.compress_type != ZIP_DEFLATED or info.extra or info.comment:
                raise ValueError("Unsupported encryption, compression, or extra ZIP metadata")
            if not 0 <= info.file_size <= MAX_FILE:
                raise ValueError("Suite ZIP file exceeds byte limit")
            total += info.file_size
            if total > MAX_CONTENT:
                raise ValueError("Suite ZIP content exceeds total byte limit")
        for name in names:
            if any(unicodedata.normalize("NFC", parent.as_posix()).casefold() in aliases for parent in PurePosixPath(name).parents if parent.as_posix() != "."):
                raise ValueError("Suite ZIP file/directory path collision")
        if MANIFEST not in names:
            raise ValueError("Suite ZIP has no outer manifest")
        return archive, infos
    except Exception:
        archive.close()
        raise


def verify_archive(raw: bytes):
    archive, infos = checked_entries(raw)
    with archive, tempfile.TemporaryDirectory(prefix="manufacturingos-suite-") as temporary:
        root = Path(temporary)
        for info in infos:
            with archive.open(info) as file:
                data = file.read(MAX_FILE + 1)
            if len(data) != info.file_size or len(data) > MAX_FILE:
                raise ValueError("Suite ZIP payload length differs from bounded metadata")
            path = root / info.filename
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as file:
                file.write(data)
        result = verify_suite(root)
    return {**result, "archive_sha256": hashlib.sha256(raw).hexdigest(), "archive_bytes": len(raw),
            "staging": "PRIVATE_TEMPORARY_DIRECTORY_REMOVED_AFTER_VERIFICATION"}


def create_archive(root: Path) -> bytes:
    verify_suite(root)
    manifest = loads(read_file(root / MANIFEST))
    names = sorted([row["path"] for row in manifest["files"]] + [MANIFEST])
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9, allowZip64=False) as archive:
        for name in names:
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, read_file(root / name), compresslevel=9)
    raw = output.getvalue()
    verify_archive(raw)
    return raw


def export_archive(root: Path, output: Path):
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("ZIP output must be outside the verified suite directory")
    if output.exists() or output.is_symlink():
        raise FileExistsError("ZIP output already exists")
    raw = create_archive(root)
    with output.open("xb") as file:
        file.write(raw)
    return {"status": "CREATED", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "production_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("directory", type=Path)
    create.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        result = export_archive(args.directory, args.output) if args.command == "create" else verify_archive(read_file(args.archive, MAX_ARCHIVE))
        print(json.dumps(result, indent=2))
    except Exception as exc:
        parser.exit(2, f"Offline suite ZIP error: {exc}\n")


if __name__ == "__main__":
    main()
