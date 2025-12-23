from __future__ import annotations

from pathlib import Path
from typing import List

from pipeline.vision.base import VisionBackend, VisionResult


class MockVisionBackend:
    name = "mock"

    def describe_scene(self, *, scene_id: str, keyframes: List[Path]) -> VisionResult:
        # Deterministic placeholder, good for wiring + tests.
        # You can make it slightly non-empty if you want to see flow end-to-end.
        return VisionResult(
            summary="",
            tags=[],
            text_on_screen=None,
            confidence=0.0,
        )
