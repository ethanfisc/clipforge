# assemble BeatsRun + write beats.json
from __future__ import annotations

from pathlib import Path

from pipeline.contracts.beats import (
    BeatsRun,
    Source,
    Files,
    VideoMeta,
    Scene,
    Keyframe,
    Beat,
    Vision,
)


def _r(x: float, ndigits: int = 3) -> float:
    return round(float(x), ndigits)


def write_beats_json(
    *,
    run_id: str,
    url: str,
    video_id: str,
    title: str,
    raw_path: Path,
    normalized_path: Path,
    duration_s: float,
    width: int,
    height: int,
    params: dict,
    scenes_times: list[tuple[float, float]],
    scenes_keyframes: list[list[tuple[Path, float]]],
    out_path: Path,
) -> Path:
    scenes = []
    beats = []

    for scene_id, (start_s, end_s) in enumerate(scenes_times):
        start_s_r = _r(start_s)
        end_s_r = _r(end_s)

        kfs = [
            Keyframe(path=str(p), ts_s=_r(ts))
            for (p, ts) in (
                scenes_keyframes[scene_id] if scene_id < len(scenes_keyframes) else []
            )
        ]
        scenes.append(
            Scene(
                scene_id=scene_id,
                start_s=start_s_r,
                end_s=end_s_r,
                keyframes=kfs,
                vision=Vision(),  # empty for now
            )
        )
        # right now beats are just a 1:1 mirror of scenes, acting as scaffolding
        beats.append(
            Beat(
                beat_id=scene_id,
                scene_ids=[scene_id],
                start_s=start_s_r,
                end_s=end_s_r,
                summary="",
                intent="unknown",
                priority=3,
            )
        )

    run = BeatsRun(
        run_id=run_id,
        source=Source(url=url, video_id=video_id, title=title),
        files=Files(raw_path=str(raw_path), normalized_path=str(normalized_path)),
        video=VideoMeta(
            duration_s=duration_s,
            fps=30,
            width=width,
            height=height,
            sar="1:1",
        ),
        params=params,
        scenes=scenes,
        beats=beats,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    json_text = run.model_dump_json(
        indent=2,
        exclude={"scenes": {"__all__": {"duration_s"}}},
    )
    out_path.write_text(json_text, encoding="utf-8")
    return out_path
