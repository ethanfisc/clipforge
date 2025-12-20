import random
import subprocess
from pathlib import Path

from .config import GAMEPLAY_DIR


def run_ffmpeg(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def pick_gameplay_clip() -> Path:
    clips = [p for p in GAMEPLAY_DIR.glob("*.mp4")]
    if not clips:
        raise RuntimeError("No gameplay clips found in assets/gameplay")
    return random.choice(clips)


def compose_short(
    gameplay_path: Path,
    audio_path: Path,
    subtitles_path: Path,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.stem + "_temp.mp4")

    # Step 1: make vertical video and add VO audio
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(gameplay_path),
            "-i",
            str(audio_path),
            "-filter_complex",
            "[0:v]scale=-1:1920,crop=1080:1920[v]",
            "-map",
            "[v]",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-shortest",
            str(temp_path),
        ]
    )

    # Step 2: burn subtitles
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(temp_path),
            "-vf",
            f"subtitles={subtitles_path}",
            "-c:a",
            "copy",
            str(output_path),
        ]
    )

    try:
        temp_path.unlink()
    except FileNotFoundError:
        pass
