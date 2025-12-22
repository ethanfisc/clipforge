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
    stdout = run_cmd(
        [
            "yt-dlp",
            "--no-playlist",
            "--js-runtimes",
            "node",
            "--skip-download",
            "--no-warnings",
            "--quiet",
            "--print",
            "%(id)s\t%(title)s",
            url,
        ],
        log_path=log_path,
    ).strip()

    if stdout:
        line = stdout.splitlines()[-1].strip()
        if "\t" in line:
            vid, title = line.split("\t", 1)
            vid = vid.strip()
            title = title.strip()
            if vid:
                return vid, title

    # fallback: parse id from URL
    vid = _extract_video_id(url) or "unknown"
    return vid, "unknown"


def download_video(url: str, raw_dir: Path, *, log_path: Path) -> Tuple[Path, str, str]:
    """
    Downloads using yt-dlp. Returns (raw_path, video_id, title).

    Strategy:
    - First fetch metadata (id/title).
    - Download using output template "<title> [<id>].<ext>".
    - Prefer the exact filepath printed by yt-dlp via `after_move:filepath`.
    - Fall back to scanning the raw_dir for a file containing "[<id>]".
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    video_id, title = fetch_metadata(
        url, log_path=log_path.with_name("yt-dlp_meta.log")
    )

    out_tmpl = str(raw_dir / "%(title).200s [%(id)s].%(ext)s")
    run_cmd(
        [
            "yt-dlp",
            "--no-playlist",
            "--js-runtimes",
            "node",
            "-f",
            "bv*+ba/b",
            "-o",
            out_tmpl,
            "--print",
            "after_move:filepath",
            url,
        ],
        log_path=log_path,
    )

    # Find the downloaded file for this id (ext can vary).
    needle = f"[{video_id.strip()}]"
    matches = sorted(
        (p for p in raw_dir.iterdir() if p.is_file() and needle in p.name),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not matches:
        raise RuntimeError(
            f"yt-dlp did not produce a file for id {video_id} in {raw_dir}. "
            f"See log: {log_path}. Files present: {[p.name for p in raw_dir.iterdir() if p.is_file()]}"
        )
    return matches[0], video_id, title
