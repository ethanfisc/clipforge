from pathlib import Path
from typing import List


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(
    caption_lines: List[str],
    total_duration: float,
    out_path: Path,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = max(len(caption_lines), 1)
    segment = total_duration / n

    lines = []
    current_start = 0.0

    for idx, caption in enumerate(caption_lines, start=1):
        start = current_start
        end = total_duration if idx == n else current_start + segment
        current_start = end

        lines.append(str(idx))
        lines.append(f"{format_timestamp(start)} --> {format_timestamp(end)}")
        lines.append(caption)
        lines.append("")  # blank line

    out_path.write_text("\n".join(lines), encoding="utf-8")
