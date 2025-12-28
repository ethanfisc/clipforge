from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RunLogger:
    """
    - Always appends to log_path.
    - Prints to console only when verbose=True.
    - Shows a Rich progress bar only when progress_enabled=True.

    IMPORTANT:
    When a Rich Progress is active, route console output through Rich's Console
    to avoid terminal redraw glitches.
    """

    log_path: Path
    verbose: bool = False
    progress_enabled: bool = False

    _console: Any = field(default_factory=Console, init=False, repr=False)

    # rich objects initialized lazily
    _progress: Any = field(default=None, init=False, repr=False)
    _task_id: Any = field(default=None, init=False, repr=False)

    def _append_file(self, msg: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{_utc_ts()}] {msg}\n")

    def _print(self, msg: str) -> None:
        if not self.verbose:
            return

        # If progress is active, print via its console so it stays above the bar cleanly.
        if self._progress is not None:
            self._progress.console.print(msg)
        else:
            self._console.print(msg)

    def info(self, msg: str) -> None:
        self._append_file(msg)
        self._print(msg)

    def step(self, msg: str) -> None:
        self.info(msg)
        if self._progress and self._task_id is not None:
            self._progress.update(self._task_id, description=msg)

    def set_total(self, total: int, *, description: str = "working") -> None:
        if not self.progress_enabled:
            return

        from rich.progress import (
            Progress,
            SpinnerColumn,
            TextColumn,
            BarColumn,
            TimeElapsedColumn,
        )

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            transient=True,
            console=self._console,  # unify console
        )
        self._progress.__enter__()
        self._task_id = self._progress.add_task(description, total=total)

    def advance(self, n: int = 1) -> None:
        if self._progress and self._task_id is not None:
            self._progress.advance(self._task_id, n)

    def close(self) -> None:
        if self._progress:
            self._progress.__exit__(None, None, None)
        self._progress = None
        self._task_id = None

    @contextmanager
    def time_block(self, label: str):
        t0 = time.perf_counter()
        yield
        dt = time.perf_counter() - t0
        self.info(f"timing {label}={dt:.3f}s")
