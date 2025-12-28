from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, s: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(s, encoding="utf-8")


def dumps_stable(obj: Any, *, indent: int = 2) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=indent)


def write_json_atomic(path: Path, obj: Any, *, indent: int = 2) -> None:
    """
    Atomic-ish JSON write:
    write to temp in same directory then replace.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dumps_stable(obj, indent=indent)

    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        Path(tmp).replace(path)
    finally:
        # if replace failed, tmp might exist
        try:
            Path(tmp).unlink(missing_ok=True)  # py3.10 supports missing_ok
        except Exception:
            pass
