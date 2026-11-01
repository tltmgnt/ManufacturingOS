"""Bounded UTF-8 JSON ingestion with unambiguous keys and finite floats."""
import json
import math
import os
from pathlib import Path
import stat
from typing import Any

MAX_INPUT_BYTES = 32*1024*1024
MAX_REPORT_BYTES = 128*1024*1024
MAX_CONTAINER_DEPTH = 128


def _limit(value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError("JSON byte limit must be a positive integer")


def _object(pairs: list[tuple[str,Any]]) -> dict:
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError("non-finite JSON number is unsupported")


def _float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("JSON number is outside the finite float range")
    return result


def _check_depth(value: Any) -> None:
    stack = [(iter((value,)),0)]
    while stack:
        children,depth = stack[-1]
        try:
            item = next(children)
        except StopIteration:
            stack.pop()
            continue
        if isinstance(item,(dict,list)):
            if depth >= MAX_CONTAINER_DEPTH:
                raise ValueError("JSON nesting exceeds 128 container levels")
            stack.append((iter(item.values() if isinstance(item,dict) else item),depth+1))


def loads(data: str | bytes, *, max_bytes: int = MAX_REPORT_BYTES) -> Any:
    _limit(max_bytes)
    if not isinstance(data,(str,bytes)):
        raise ValueError("JSON input must be UTF-8 text or bytes")
    raw = data.encode("utf-8") if isinstance(data,str) else data
    if len(raw) > max_bytes:
        raise ValueError("JSON input exceeds configured byte limit")
    # Accept an optional UTF-8 BOM, without silently accepting UTF-16/32.
    text = raw.decode("utf-8-sig")
    try:
        result = json.loads(text,object_pairs_hook=_object,parse_constant=_constant,parse_float=_float)
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds supported parser depth") from exc
    _check_depth(result)
    return result


def _fingerprint(info: os.stat_result) -> tuple:
    return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)


def read_json(path: str | Path, *, max_bytes: int = MAX_INPUT_BYTES) -> Any:
    _limit(max_bytes)
    path = Path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("JSON input must be a regular file")
    if info.st_size > max_bytes:
        raise ValueError("JSON input exceeds configured byte limit")
    descriptor = os.open(path,os.O_RDONLY|getattr(os,"O_NONBLOCK",0)|getattr(os,"O_BINARY",0))
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("JSON input must be a regular file")
        if before.st_size > max_bytes:
            raise ValueError("JSON input exceeds configured byte limit")
        with os.fdopen(descriptor,"rb",closefd=False) as file:
            raw = file.read(max_bytes+1)
        after = os.fstat(descriptor)
        if _fingerprint(before)!=_fingerprint(after):
            raise ValueError("JSON input changed during read")
        return loads(raw,max_bytes=max_bytes)
    finally:
        os.close(descriptor)
