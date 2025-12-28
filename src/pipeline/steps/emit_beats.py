# assemble BeatsRun + write beats.json
from __future__ import annotations

from pathlib import Path
from typing import Any

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
from pipeline.util.jsonio import write_text
from pipeline.util.log import RunLogger


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
    params: dict[str, Any],
    scenes_times: list[tuple[float, float]],
    scenes_keyframes: list[list[tuple[Path, float]]],
    out_path: Path,
    logger: RunLogger | None = None,
) -> Path:
    scenes: list[Scene] = []
    beats: list[Beat] = []

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

        # beats mirror scenes 1:1 as scaffolding
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

    json_text = run.model_dump_json(
        indent=2,
        exclude={"scenes": {"__all__": {"duration_s"}}},
    )
    write_text(out_path, json_text)

    if logger:
        logger.info(
            f"emit_beats: wrote {out_path.name} scenes={len(scenes)} beats={len(beats)}"
        )

    return out_path
