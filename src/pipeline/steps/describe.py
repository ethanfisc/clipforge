from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from pipeline.contracts.beats import BeatsRun  # adjust import to your actual contract
from pipeline.util.jsonio import write_json_stable
from pipeline.util.log import log_event
from pipeline.vision.base import VisionBackend, VisionResult


def _sorted_keyframes(scene) -> List[Path]:
    kfs = sorted(scene.keyframes, key=lambda k: (float(k.ts_s), str(k.path)))
    return [Path(k.path) for k in kfs]


def _vision_to_contract_dict(v: VisionResult) -> Dict[str, Any]:
    # Keep rounding consistent. Pick one convention and stick to it.
    conf = float(v.confidence)
    if conf < 0.0:
        conf = 0.0
    if conf > 1.0:
        conf = 1.0
    conf = round(conf, 3)

    # Tags: normalize + stabilize (optional). If you do this, do it consistently forever.
    tags = [t.strip() for t in v.tags if t and t.strip()]
    # Keep original order from backend; or sort(tags) if you want deterministic ordering across models.
    # Sorting is more deterministic but may remove “importance ordering”.
    # tags = sorted(set(tags), key=str.lower)

    return {
        "summary": v.summary.strip(),
        "tags": tags,
        "text_on_screen": (v.text_on_screen.strip() if v.text_on_screen else None),
        "confidence": conf,
    }


def describe_beats(
    *,
    beats_path: Path,
    backend: VisionBackend,
    out_path: Path,
    log_path: Path,
    errors_path: Path,
    strict: bool,
    overwrite: bool,
    resume: bool,
    max_keyframes: int,
) -> Path:
    beats_dict = _read_json(beats_path)
    run = BeatsRun.model_validate(beats_dict)

    if out_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing output: {out_path}")

    errors: List[Dict[str, Any]] = []

    for scene in run.scenes:
        scene_id = str(scene.scene_id)

        # Resume logic (assumes vision exists or is optional)
        if resume and getattr(scene, "vision", None):
            v = scene.vision
            if getattr(v, "confidence", 0.0) > 0 and getattr(v, "summary", ""):
                log_event(
                    log_path, {"event": "scene_skip_resume", "scene_id": scene_id}
                )
                continue

        keyframes = _sorted_keyframes(scene)[:max_keyframes]

        try:
            if not keyframes:
                raise RuntimeError("No keyframes found for scene")

            result = backend.describe_scene(scene_id=scene_id, keyframes=keyframes)
            vision_dict = _vision_to_contract_dict(result)

            # Assign into contract model safely.
            # If your contract uses a Vision model class, you can build it:
            # scene.vision = Vision.model_validate(vision_dict)
            # Otherwise, if it’s a plain dict field, just assign:
            scene.vision = scene.vision.__class__.model_validate(
                vision_dict
            )  # adjust if needed

            log_event(
                log_path,
                {
                    "event": "scene_described",
                    "scene_id": scene_id,
                    "backend": getattr(backend, "name", "unknown"),
                    "confidence": vision_dict["confidence"],
                    "keyframes": [str(p) for p in keyframes],
                },
            )

        except Exception as e:
            err = {
                "scene_id": scene_id,
                "error": type(e).__name__,
                "message": str(e),
                "keyframes": [str(p) for p in keyframes],
            }
            errors.append(err)
            log_event(log_path, {"event": "scene_error", **err})

            if strict:
                raise

            # Contract-safe fallback
            fallback = {
                "summary": "",
                "tags": [],
                "text_on_screen": None,
                "confidence": 0.0,
            }
            scene.vision = scene.vision.__class__.model_validate(
                fallback
            )  # adjust if needed

    # Validate with existing contract before writing
    validated = BeatsRun.model_validate(run.model_dump())

    # Write main artifact (stable)
    write_json_stable(out_path, validated.model_dump())

    # Write sidecar errors (optional, not contract-bound)
    if errors:
        write_json_stable(errors_path, {"errors": errors})

    return out_path


def _read_json(path: Path) -> Dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
