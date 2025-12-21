"""
# Pydantic contract for beats.json files
"""

from __future__ import annotations

from typing import Literal, Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

SchemaVersion = Literal["0.1"]
BeatIntent = Literal["hook", "step", "payoff", "broll", "unknown"]


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    video_id: str
    title: str = ""


class Files(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_path: str
    normalized_path: str


class VideoMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_s: float = Field(ge=0)
    fps: Literal[30] = 30
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    sar: Literal["1:1"] = "1:1"  # setsar=1


class Keyframe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    ts_s: float = Field(ge=0)


class Vision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = ""
    tags: List[str] = Field(default_factory=list)
    text_on_screen: Optional[str] = None
    confidence: float = Field(ge=0, le=1, default=0.0)


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_id: int = Field(ge=0)
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    keyframes: List[Keyframe] = Field(default_factory=list)
    vision: Vision = Field(default_factory=Vision)

    @model_validator(mode="after")
    def _check_times_and_keyframes(self):
        if self.end_s <= self.start_s:
            raise ValueError(f"scene {self.scene_id}: end_s must be > start_s")
        for kf in self.keyframes:
            if not (self.start_s <= kf.ts_s <= self.end_s):
                raise ValueError(
                    f"scene {self.scene_id}: keyframe ts_s {kf.ts_s} outside [{self.start_s}, {self.end_s}]"
                )
        return self

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


class Beat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    beat_id: int = Field(ge=0)
    scene_ids: List[int] = Field(default_factory=list)
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    summary: str = ""
    intent: BeatIntent = "unknown"
    priority: int = Field(ge=1, le=5, default=3)

    @model_validator(mode="after")
    def _check_times(self):
        if self.end_s <= self.start_s:
            raise ValueError(f"beat {self.beat_id}: end_s must be > start_s")
        return self


class BeatsRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = "0.1"
    run_id: str

    source: Source
    files: Files
    video: VideoMeta
    params: dict = Field(default_factory=dict)  # keep flexible early

    scenes: List[Scene] = Field(default_factory=list)
    beats: List[Beat] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_scene_ids_and_bounds(self):
        # scene_id uniqueness
        ids = [s.scene_id for s in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate scene_id in scenes")

        # optional: ensure beats reference real scenes
        scene_id_set = set(ids)
        for b in self.beats:
            missing = [sid for sid in b.scene_ids if sid not in scene_id_set]
            if missing:
                raise ValueError(f"beat {b.beat_id}: unknown scene_ids {missing}")

        # ensure scenes are within duration
        for s in self.scenes:
            if s.end_s > self.video.duration_s + 1e-3:
                raise ValueError(f"scene {s.scene_id}: end_s exceeds video duration")
        return self
