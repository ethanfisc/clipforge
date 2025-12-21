# run subprocess, capture logs/errors
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


class CmdError(RuntimeError):
    pass


def run_cmd(
    cmd: Sequence[str], *, log_path: Path | None = None, cwd: Path | None = None
) -> str:
    """
    Run a command. If log_path is provided, write stdout/stderr to it.
    Returns stdout (text). Raises CmdError on non-zero exit.
    """
    proc = subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    out = proc.stdout or ""
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(out, encoding="utf-8")

    if proc.returncode != 0:
        raise CmdError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{out}")
    return out
