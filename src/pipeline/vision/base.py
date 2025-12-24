from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Protocol


class VisionBackend(Protocol):
    """
    Backend returns a dict with keys:
      - summary: str
      - tags: list[str]
      - text_on_screen: str | None
      - confidence: float (0..1)
    """

    def describe_scene(self, image_paths: List[Path]) -> Dict[str, Any]: ...


@dataclass(frozen=True)
class BackendSpec:
    name: str
    kwargs: Dict[str, Any]
