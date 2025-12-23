from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol, Optional


@dataclass(frozen=True)
class VisionResult:
    summary: str
    tags: List[str]
    text_on_screen: Optional[str]
    confidence: float  # 0..1


class VisionBackend(Protocol):
    name: str

    def describe_scene(
        self, *, scene_id: str, keyframes: List[Path]
    ) -> VisionResult: ...
