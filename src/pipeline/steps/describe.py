# describe.py - fill scene.vision using keyframe images (restartable + cached)
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from pipeline.contracts.beats import BeatsRun, Vision
from pipeline.util.shell import CmdError  # only for nicer error categorization

from pipeline.vision.base import BackendSpec, VisionBackend


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _r(x: float, ndigits: int = 3) -> float:
    return round(float(x), ndigits)


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def _stable_backend_id(name: str, kwargs: Dict[str, Any]) -> str:
    # Deterministic string representing backend configuration.
    # If kwargs include secrets, don't put them here.
    safe_kwargs = {}
    for k, v in kwargs.items():
        if k.lower() in {"api_key", "key", "token"}:
            continue
        safe_kwargs[k] = v
    return f"{name}:{_json_dumps_stable(safe_kwargs, indent=0)}"


def _json_dumps_stable(obj: Any, *, indent: int = 2) -> str:
    # stable keys + stable separators for deterministic output
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=indent)


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _append_log(log_path: Path, msg: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{_utc_ts()}] {msg}\n")


def _load_backend(spec: BackendSpec) -> VisionBackend:
    """
    Model-agnostic plugin loader.

    Expected module: pipeline.vision.backends.<name>
    It may provide one of:
      - build(**kwargs) -> VisionBackend
      - Backend(**kwargs) with method describe_scene(...)
      - backend(**kwargs) -> VisionBackend

    If none found, raises ValueError.
    """
    import importlib

    mod = importlib.import_module(f"pipeline.vision.backends.{spec.name}")

    if hasattr(mod, "build"):
        return getattr(mod, "build")(**spec.kwargs)

    if hasattr(mod, "backend"):
        return getattr(mod, "backend")(**spec.kwargs)

    if hasattr(mod, "Backend"):
        return getattr(mod, "Backend")(**spec.kwargs)

    raise ValueError(
        f"Vision backend '{spec.name}' must expose build(), backend(), or Backend class"
    )


def _vision_from_backend_payload(payload: Dict[str, Any]) -> Vision:
    # enforce deterministic shaping + bounds + types via the Vision model
    summary = (payload.get("summary") or "").strip()
    tags = payload.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if str(t).strip()]
    text_on_screen = payload.get("text_on_screen", None)
    if text_on_screen is not None:
        text_on_screen = str(text_on_screen).strip() or None

    conf = payload.get("confidence", 0.0)
    try:
        conf_f = float(conf)
    except Exception:
        conf_f = 0.0
    conf_f = max(0.0, min(1.0, _r(conf_f, 3)))

    return Vision(
        summary=summary, tags=tags, text_on_screen=text_on_screen, confidence=conf_f
    )


def _should_skip(scene_vision: Vision) -> bool:
    return (scene_vision.summary or "") != "" and float(scene_vision.confidence) > 0.0


def describe_beats(
    beats_path: Path,
    *,
    backend: str = "mock",
    backend_kwargs: Optional[Dict[str, Any]] = None,
    prompt_version: str = "v1",
    backend_id: Optional[str] = None,
    recompute: bool = False,
    strict: bool = False,
    overwrite: bool = False,
    out_path: Optional[Path] = None,
) -> Path:
    """
    Reads beats.json, fills scene.vision, writes beats.vision.json (default) next to beats.json.
    Resume-by-default unless recompute=True.

    Caching:
    runs/<run_id>/cache/vision/<sha256>.json where sha is hash of image bytes (per keyframe).
    """
    beats_path = beats_path.resolve()
    run_dir = beats_path.parent
    logs_dir = run_dir / "logs"
    log_path = logs_dir / "describe.log"

    run = BeatsRun.model_validate_json(_read_text(beats_path))

    # output path
    if out_path is None:
        out_path = beats_path.with_name("beats.vision.json")
    out_path = out_path.resolve()

    if out_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {out_path}")

    cache_dir = run_dir / "cache" / "vision"
    cache_dir.mkdir(parents=True, exist_ok=True)

    _append_log(
        log_path,
        f"describe: start beats_path={beats_path.name} backend={backend} recompute={recompute} strict={strict}",
    )

    spec = BackendSpec(name=backend, kwargs=backend_kwargs or {})
    vb = _load_backend(spec)

    # errors recorded under params (since Vision cannot accept extra fields) :contentReference[oaicite:2]{index=2}
    params = dict(run.params or {})
    describe_meta: Dict[str, Any] = dict(params.get("describe", {}))
    errors: Dict[str, Any] = dict(describe_meta.get("errors", {}))

    total = len(run.scenes)
    done = 0
    skipped = 0
    failed = 0

    # stable ordering by scene_id
    scenes_sorted = sorted(run.scenes, key=lambda s: int(s.scene_id))

    for idx, scene in enumerate(scenes_sorted, start=1):
        sid = int(scene.scene_id)

        if (not recompute) and _should_skip(scene.vision):
            skipped += 1
            _append_log(log_path, f"[{idx}/{total}] scene {sid}: skip (resume)")
            continue

        # collect keyframes deterministically (as stored)
        kf_paths = [Path(kf.path) for kf in scene.keyframes]
        kf_paths = [p for p in kf_paths if p.exists()]

        if not kf_paths:
            failed += 1
            errors[str(sid)] = {
                "ts": _utc_ts(),
                "type": "no_keyframes",
                "message": "No existing keyframe images found for scene",
            }
            scene.vision = Vision(
                summary="", tags=[], text_on_screen=None, confidence=0.0
            )
            _append_log(log_path, f"[{idx}/{total}] scene {sid}: FAIL (no_keyframes)")
            if strict:
                raise RuntimeError(f"describe strict mode: scene {sid} failed")
            continue

        # per-image cache: load cached descriptors and pass through backend if anything missing
        # NOTE: backend still sees full list; cache is for backend outputs per-image if you want it.
        # For MVP: we cache the final per-scene result keyed by *combined* image hashes for the scene.
        try:
            hashes = [
                _sha256_file(p) for p in kf_paths
            ]  # stable order = keyframes order in beats.json
            b_id = backend_id or _stable_backend_id(backend, backend_kwargs or {})
            salt = f"backend={b_id}|prompt_version={prompt_version}"

            scene_key_material = {
                "salt": salt,
                "keyframes_sha256": hashes,
            }
            scene_key = _sha256_bytes(
                _json_dumps_stable(scene_key_material, indent=0).encode("utf-8")
            )
            scene_cache_path = cache_dir / f"{scene_key}.json"

            if scene_cache_path.exists():
                payload = json.loads(_read_text(scene_cache_path))
                scene.vision = _vision_from_backend_payload(payload.get("vision", {}))
                done += 1
                _append_log(
                    log_path,
                    f"[{idx}/{total}] scene {sid}: cache hit ({scene_key[:8]})",
                )
                continue

            payload = vb.describe_scene(kf_paths)
            vision = _vision_from_backend_payload(payload)

            # if backend gives nothing useful, treat as failure unless it at least sets confidence>0
            if (vision.summary == "") and (vision.confidence <= 0.0):
                raise ValueError("backend_returned_empty")

            scene.vision = vision

            cache_payload = {
                "cache_version": 1,
                "salt": salt,
                "scene_key": scene_key,
                "keyframes_sha256": hashes,
                "vision": vision.model_dump(),
            }
            _write_text(scene_cache_path, _json_dumps_stable(cache_payload))

            done += 1
            _append_log(
                log_path,
                f"[{idx}/{total}] scene {sid}: OK conf={vision.confidence:.3f}",
            )

        except Exception as e:
            failed += 1
            etype = type(e).__name__
            msg = str(e)[:500]

            if isinstance(e, CmdError):
                etype = "CmdError"

            errors[str(sid)] = {
                "ts": _utc_ts(),
                "type": etype,
                "message": msg,
            }
            scene.vision = Vision(
                summary="", tags=[], text_on_screen=None, confidence=0.0
            )
            _append_log(
                log_path, f"[{idx}/{total}] scene {sid}: FAIL type={etype} msg={msg}"
            )

            if strict:
                raise RuntimeError(f"describe strict mode: scene {sid} failed")

    describe_meta["backend"] = backend
    describe_meta["recompute"] = bool(recompute)
    describe_meta["strict"] = bool(strict)
    describe_meta["updated_at"] = _utc_ts()
    describe_meta["counts"] = {
        "total": total,
        "done": done,
        "skipped": skipped,
        "failed": failed,
    }
    describe_meta["errors"] = errors
    params["describe"] = describe_meta
    run.params = params

    # validate output with contract before writing :contentReference[oaicite:3]{index=3}
    BeatsRun.model_validate(
        run.model_dump(exclude={"scenes": {"__all__": {"duration_s"}}})
    )

    json_text = run.model_dump_json(
        indent=2,
        exclude={
            "scenes": {"__all__": {"duration_s"}}
        },  # match emit_beats convention :contentReference[oaicite:4]{index=4}
    )
    _write_text(out_path, json_text)

    _append_log(
        log_path,
        f"describe: end out={out_path.name} done={done} skipped={skipped} failed={failed}",
    )
    return out_path
