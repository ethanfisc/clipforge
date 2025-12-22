# run subprocess, capture logs/errors
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence


class CmdError(RuntimeError):
    def __init__(
        self, cmd: Sequence[str], returncode: int, output: str, log_path: Path | None
    ):
        self.cmd = list(cmd)
        self.returncode = returncode
        self.output = output
        self.log_path = log_path
        super().__init__(self._build_msg())

    def _build_msg(self) -> str:
        hint = f"\nSee log: {self.log_path}" if self.log_path else ""
        return f"Command failed ({self.returncode}): {' '.join(self.cmd)}{hint}\n{self.output}"


def run_cmd(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    # If provided, write output to this path (mode depends on write_on_success)
    log_path: Path | None = None,
    # If True, write output even on success; if False, only write on failure. false generally used for noisy commands.
    write_on_success: bool = True,
) -> str:
    """
    Run a command and capture stdout+stderr (merged).
    Returns combined output (text). Raises CmdError on non-zero exit.

    Logging:
      - if log_path is None: no file write
      - if write_on_success: write output always
      - else: write output only on failure (good for "debug log on failure")
    """
    proc = subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    out = proc.stdout or ""

    if proc.returncode != 0:
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(out, encoding="utf-8")
        raise CmdError(cmd, proc.returncode, out, log_path)

    if log_path and write_on_success:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(out, encoding="utf-8")

    return out
