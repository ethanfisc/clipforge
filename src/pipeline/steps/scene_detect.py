# PySceneDetect wrapper
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector


def detect_scenes(
    video_path: Path,
    *,
    threshold: float = 27.0,
    min_scene_len_frames: int = 15,
) -> List[Tuple[float, float]]:
    """
    Returns list of (start_s, end_s) scenes.
    """
    video = open_video(str(video_path))
    sm = SceneManager()
    sm.add_detector(
        ContentDetector(threshold=threshold, min_scene_len=min_scene_len_frames)
    )
    sm.detect_scenes(video=video)
    scenes = sm.get_scene_list()

    out: List[Tuple[float, float]] = []
    for start_tc, end_tc in scenes:
        out.append((start_tc.get_seconds(), end_tc.get_seconds()))
    return out
