# ffmpeg normalize wrapper
from __future__ import annotations
from pathlib import Path
from typing import Literal

from pipeline.util.shell import run_cmd

Profile = Literal["hq", "balanced", "fast", "preview"]

_PROFILES = {
    "hq": {"crf": "16", "preset": "slow", "ab": "192k"},
    "balanced": {"crf": "18", "preset": "medium", "ab": "160k"},
    "fast": {"crf": "20", "preset": "veryfast", "ab": "128k"},
    "preview": {"crf": "23", "preset": "ultrafast", "ab": "96k"},
}


def normalize_max1280_cfr30(
    raw_path: Path,
    normalized_dir: Path,
    video_id: str,
    *,
    log_path: Path,
    profile: Profile = "hq",
) -> Path:
    normalized_dir.mkdir(parents=True, exist_ok=True)
    out_path = normalized_dir / f"{video_id}.normalized_max1280_cfr30_{profile}.mp4"

    cfg = _PROFILES[profile]
    vf = "scale='if(gte(iw,ih),1280,-2)':'if(gte(ih,iw),1280,-2)',fps=30,setsar=1"
    run_cmd(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_path),
            "-vf",
            vf,
            "-hide_banner",
            "-nostdin",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            cfg["crf"],
            "-preset",
            cfg["preset"],
            "-c:a",
            "aac",
            "-b:a",
            cfg["ab"],
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        log_path=log_path,
    )
    return out_path
