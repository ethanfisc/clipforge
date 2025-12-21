from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

from pipeline.util.shell import run_cmd


def probe_video(path: Path, *, log_path: Path) -> Tuple[float, int, int]:
    """
    Returns (duration_s, width, height) from ffprobe.
    """
    out = run_cmd(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        log_path=log_path,
    )
    data = json.loads(out)
    duration_s = float(data["format"]["duration"])
    width = int(data["streams"][0]["width"])
    height = int(data["streams"][0]["height"])
    return duration_s, width, height
