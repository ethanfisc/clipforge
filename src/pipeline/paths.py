from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def repo_root() -> Path:
    # Assumption: CLI is run from repo root. This matches your current conventions.
    return Path.cwd().resolve()


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    run_dir: Path

    @property
    def logs_dir(self) -> Path:
        return self.run_dir / "logs"

    @property
    def frames_dir(self) -> Path:
        return self.run_dir / "frames"

    @property
    def cache_vision_dir(self) -> Path:
        return self.run_dir / "cache" / "vision"

    @property
    def beats_path(self) -> Path:
        return self.run_dir / "beats.json"

    @property
    def beats_vision_path(self) -> Path:
        return self.run_dir / "beats.vision.json"

    @property
    def beats_edit_path(self) -> Path:
        return self.run_dir / "beats.edit.json"

    def ensure(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.cache_vision_dir.mkdir(parents=True, exist_ok=True)
