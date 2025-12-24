from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


class Backend:
    def __init__(self, *, confidence: float = 0.5) -> None:
        self._confidence = float(confidence)

    def describe_scene(self, image_paths: List[Path]) -> Dict[str, Any]:
        # deterministic mock: based only on filenames
        names = [p.name for p in image_paths]
        return {
            "summary": f"Mock summary from {len(names)} keyframes: {', '.join(names[:3])}"
            + ("..." if len(names) > 3 else ""),
            "tags": ["mock"],
            "text_on_screen": None,
            "confidence": max(0.0, min(1.0, round(self._confidence, 3))),
        }


def build(**kwargs: Any) -> Backend:
    return Backend(**kwargs)
