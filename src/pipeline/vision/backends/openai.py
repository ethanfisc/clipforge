from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


class Backend:
    def __init__(self, **_: Any) -> None:
        # Keep import-free until you actually implement it.
        pass

    def describe_scene(self, image_paths: List[Path]) -> Dict[str, Any]:
        raise NotImplementedError(
            "OpenAI backend not implemented yet. Use --backend mock for now."
        )


def build(**kwargs: Any) -> Backend:
    return Backend(**kwargs)
