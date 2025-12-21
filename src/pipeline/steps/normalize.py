# ffmpeg normalize wrapper
from __future__ import annotations

from pathlib import Path

from pipeline.util.shell import run_cmd


def normalize_max1280_cfr30(
    raw_path: Path, normalized_dir: Path, video_id: str, *, log_path: Path
) -> Path:
    """
    Hard requirements:
    - MP4 container
    - H.264 (libx264)
    - yuv420p
    - CFR 30
    - SAR 1:1 (setsar=1)
    - max dimension 1280 (preserve aspect)
    """
    normalized_dir.mkdir(parents=True, exist_ok=True)
    out_path = normalized_dir / f"{video_id}.normalized_max1280.mp4"

    vf = "scale='if(gte(iw,ih),1280,-2)':'if(gte(ih,iw),1280,-2)',fps=30,setsar=1"
    run_cmd(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_path),
            "-vf",
            vf,
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "16",
            "-preset",
            "slow",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        log_path=log_path,
    )
    return out_path
