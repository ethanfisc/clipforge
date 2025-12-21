# yt-dlp wrapper
from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

from pipeline.util.shell import run_cmd


def _extract_video_id(url: str) -> str:
    # Minimal parse to find YouTube ID from common URL patterns.
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    m = re.search(r"youtube\.com/shorts/([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    return ""


def fetch_metadata(url: str, *, log_path: Path) -> Tuple[str, str]:
    """
    Returns (video_id, title). Uses yt-dlp metadata (no download).
    """
    out = run_cmd(
        [
            "yt-dlp",
            "--no-playlist",
            "--skip-download",
            "--print",
            "%(id)s",
            "--print",
            "%(title)s",
            url,
        ],
        log_path=log_path,
    ).splitlines()

    if len(out) >= 2 and out[0].strip():
        return out[0].strip(), out[1].strip()

    # fallback: try to extract id from URL if yt-dlp output is weird
    vid = _extract_video_id(url) or "unknown"
    title = "unknown"
    return vid, title


def download_video(url: str, raw_dir: Path, *, log_path: Path) -> Tuple[Path, str, str]:
    """
    Downloads using yt-dlp. Returns (raw_path, video_id, title).
    Output filename pattern: "<title> [<id>].<ext>".
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    video_id, title = fetch_metadata(
        url, log_path=log_path.with_name("yt-dlp_meta.log")
    )

    out_tmpl = str(raw_dir / "%(title).200s [%(id)s].%(ext)s")
    run_cmd(
        ["yt-dlp", "--no-playlist", "-f", "bv*+ba/b", "-o", out_tmpl, url],
        log_path=log_path,
    )

    # Find the downloaded file for this id (ext can vary).
    matches = sorted(
        raw_dir.glob(f"* [{video_id}].*"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not matches:
        raise RuntimeError(
            f"Download completed but no file matching id {video_id} found in {raw_dir}"
        )
    return matches[0], video_id, title
