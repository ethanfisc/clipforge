# ffmpeg frame extraction
from __future__ import annotations

from pathlib import Path
from typing import List

from pipeline.util.shell import run_cmd


def _sample_times(start_s: float, end_s: float, n: int) -> List[float]:
    # Uniform times inside (start, end), avoids endpoints
    dur = max(0.0, end_s - start_s)
    if n <= 0 or dur <= 0:
        return []
    return [start_s + (i + 1) * dur / (n + 1) for i in range(n)]


def extract_keyframes(
    video_path: Path,
    run_frames_dir: Path,
    scenes: List[tuple[float, float]],
    *,
    per_scene: int = 2,
    log_dir: Path,
) -> List[List[tuple[Path, float]]]:
    """
    For each scene, extract `per_scene` JPEG frames at uniform interior times.
    Returns per-scene list of (frame_path, ts_s).
    """
    run_frames_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    all_scene_kfs: List[List[tuple[Path, float]]] = []

    for scene_id, (start_s, end_s) in enumerate(scenes):
        scene_dir = run_frames_dir / f"scene_{scene_id:03d}"
        scene_dir.mkdir(parents=True, exist_ok=True)

        times = _sample_times(start_s, end_s, per_scene)
        kfs: List[tuple[Path, float]] = []

        for i, ts in enumerate(times):
            out_path = scene_dir / f"kf_{i:02d}.jpg"
            run_cmd(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{ts:.3f}",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    "-an",
                    "-sn",
                    str(out_path),
                ],
                log_path=log_dir / f"ffmpeg_keyframe_scene{scene_id:03d}_kf{i:02d}.log",
            )
            kfs.append((out_path, ts))

        all_scene_kfs.append(kfs)

    return all_scene_kfs
