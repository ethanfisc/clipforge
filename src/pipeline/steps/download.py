from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Tuple

from pipeline.util.shell import CmdError, run_cmd


def _extract_video_id(url: str) -> str:
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


_YTDLP_ARGS = [
    "yt-dlp",
    "--no-playlist",
    "--js-runtimes",
    "node",
    "--remote-components",
    "ejs:github",
    "--retries",
    "10",
    "--fragment-retries",
    "10",
    "--retry-sleep",
    "1:5",
    "-f",
    "bv*+ba/bv*",
    "--print-json",
]


def _last_json_line(text: str) -> dict:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def _pick_filepath(info: dict) -> str | None:
    fp = info.get("filepath") or info.get("_filename")
    if isinstance(fp, str) and fp.strip():
        return fp.strip()
    rd = info.get("requested_downloads")
    if isinstance(rd, list) and rd:
        fp2 = rd[0].get("filepath")
        if isinstance(fp2, str) and fp2.strip():
            return fp2.strip()
    return None


def _write_summary(log_path: Path, *, url: str, info: dict, raw_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                "yt-dlp download summary",
                f"url:   {url}",
                f"id:    {(info.get('id') or '').strip()}",
                f"title: {(info.get('title') or '').strip()}",
                f"path:  {raw_path}",
                f"ext:   {(info.get('ext') or raw_path.suffix.lstrip('.')).strip()}",
                f"fmt:   {(info.get('format_id') or '').strip()}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def download_video(url: str, raw_dir: Path, *, log_path: Path) -> Tuple[Path, str, str]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(raw_dir / "%(title).200s [%(id)s].%(ext)s")
    cmd = [*_YTDLP_ARGS, "-o", out_tmpl, url]

    debug_log = log_path.with_suffix(".debug.log")

    try:
        out = run_cmd(cmd, log_path=debug_log, write_on_success=False)
    except CmdError as e:
        # debug log is already written by run_cmd on failure
        raise RuntimeError(f"yt-dlp failed. See: {debug_log}") from e

    info = _last_json_line(out)
    video_id = (info.get("id") or _extract_video_id(url) or "unknown").strip()
    title = (info.get("title") or "unknown").strip()

    fp = _pick_filepath(info)
    if not fp:
        debug_log.parent.mkdir(parents=True, exist_ok=True)
        debug_log.write_text(out, encoding="utf-8")
        raise RuntimeError(f"yt-dlp succeeded but no filepath found. See: {debug_log}")

    raw_path = Path(fp)
    if not raw_path.is_absolute():
        raw_path = (Path.cwd() / raw_path).resolve()

    if not raw_path.exists():
        debug_log.parent.mkdir(parents=True, exist_ok=True)
        debug_log.write_text(out, encoding="utf-8")
        raise RuntimeError(
            f"yt-dlp reported {raw_path} but it doesn't exist. See: {debug_log}"
        )

    _write_summary(log_path, url=url, info=info, raw_path=raw_path)
    return raw_path, video_id, title
