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
            "format=duration:stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        log_path=log_path,
    )
    data = json.loads(out)

    streams = data.get("streams") or []
    if not streams:
        raise RuntimeError(f"No video stream found in {path}. See log: {log_path}")

    fmt = data.get("format") or {}
    dur = fmt.get("duration")
    if dur in (None, "N/A", ""):
        raise RuntimeError(
            f"No duration reported by ffprobe for {path}. See log: {log_path}"
        )

    duration_s = float(dur)
    width = int(streams[0]["width"])
    height = int(streams[0]["height"])
    return duration_s, width, height
