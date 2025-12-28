from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import typer

from pipeline.contracts.beats import BeatsRun
from pipeline.paths import RunPaths, repo_root
from pipeline.steps.describe import describe_beats
from pipeline.steps.download import download_video
from pipeline.steps.emit_beats import write_beats_json
from pipeline.steps.keyframes import extract_keyframes
from pipeline.steps.normalize import normalize_max1280_cfr30
from pipeline.steps.probe import probe_video
from pipeline.steps.scene_detect import detect_scenes
from pipeline.util.log import RunLogger

app = typer.Typer(no_args_is_help=True)


@app.command()
def run(
    url: str,
    threshold: float = 27.0,
    min_scene_len_frames: int = 15,
    keyframes_per_scene: int = 2,
    verbose: bool = typer.Option(
        False, "--verbose", help="Print step logs to console."
    ),
    progress: bool = typer.Option(
        False, "--progress", help="Show a progress bar (requires rich)."
    ),
):
    """
    One-shot: URL -> beats.json (+ keyframes).

    Quiet by default:
      - prints only final summary + validate OK
    With --verbose:
      - prints step-by-step telemetry
    With --progress:
      - shows a progress bar for the 6 top-level steps
    """
    root = repo_root()
    raw_dir = root / "assets" / "raw"
    normalized_dir = root / "assets" / "normalized"

    run_id = str(uuid.uuid4())
    run_dir = root / "runs" / run_id
    rp = RunPaths(run_id=run_id, run_dir=run_dir)
    rp.ensure()

    log = RunLogger(
        log_path=rp.logs_dir / "run.log",
        verbose=verbose,
        progress_enabled=progress,
    )

    # 6 top-level stages
    log.set_total(6, description="pipeline run")
    t0 = time.perf_counter()

    try:
        log.step("[1/6] downloading")
        with log.time_block("download"):
            raw_path, video_id, title = download_video(
                url, raw_dir, log_path=rp.logs_dir / "yt-dlp_download.log"
            )
        log.info(f"  video_id: {video_id}")
        log.info(f"  title:    {title}")
        log.info(f"  raw:      {raw_path}")
        log.advance(1)

        log.step("[2/6] normalizing")
        with log.time_block("normalize"):
            normalized_path = normalize_max1280_cfr30(
                raw_path,
                normalized_dir,
                video_id,
                log_path=rp.logs_dir / "ffmpeg_normalize.log",
            )
        log.info(f"  normalized: {normalized_path}")
        log.advance(1)

        log.step("[3/6] probing")
        with log.time_block("probe"):
            duration_s, width, height = probe_video(
                normalized_path, log_path=rp.logs_dir / "ffprobe.log"
            )
        log.info(f"  duration_s: {duration_s:.2f}")
        log.info(f"  size:       {width}x{height}")
        log.advance(1)

        log.step("[4/6] detecting scenes")
        with log.time_block("scene_detect"):
            scenes = detect_scenes(
                normalized_path,
                threshold=threshold,
                min_scene_len_frames=min_scene_len_frames,
            )
        log.info(f"  scenes: {len(scenes)}")
        log.advance(1)

        log.step("[5/6] extracting keyframes")
        with log.time_block("keyframes"):
            scenes_keyframes = extract_keyframes(
                normalized_path,
                rp.frames_dir,
                scenes,
                per_scene=keyframes_per_scene,
                log_dir=rp.logs_dir / "ffmpeg_keyframes",
            )
        log.info(f"  frames_dir: {rp.frames_dir}")
        log.advance(1)

        params = {
            "normalize": {"preset": "max1280_cfr30"},
            "scene_detect": {
                "method": "content",
                "threshold": threshold,
                "min_scene_len_frames": min_scene_len_frames,
            },
            "keyframes": {
                "strategy": "uniform_interior",
                "per_scene": keyframes_per_scene,
            },
        }

        log.step("[6/6] writing beats.json")
        with log.time_block("emit_beats"):
            beats_path = write_beats_json(
                run_id=run_id,
                url=url,
                video_id=video_id,
                title=title,
                raw_path=raw_path,
                normalized_path=normalized_path,
                duration_s=duration_s,
                width=width,
                height=height,
                params=params,
                scenes_times=scenes,
                scenes_keyframes=scenes_keyframes,
                out_path=rp.beats_path,
            )
        log.advance(1)

        # validate + final summary (always)
        BeatsRun.model_validate_json(beats_path.read_text(encoding="utf-8"))
        elapsed = time.perf_counter() - t0

        log.close()

        typer.echo("validate: OK")
        typer.echo(f"run_id:  {run_id}")
        typer.echo(f"beats:   {beats_path}")
        typer.echo(f"frames:  {rp.frames_dir}")
        typer.echo(f"video:   {normalized_path}")
        typer.echo(f"elapsed: {elapsed:.1f}s")

    finally:
        log.close()


@app.command()
def describe(
    beats_path: Path,
    backend: str = "mock",
    backend_kwargs: str = typer.Option(
        "{}",
        "--backend-kwargs",
        help='JSON dict passed to backend build(), e.g. \'{"model":"gpt-5-mini","reasoning_effort":"low","verbosity":"low"}\'',
    ),
    prompt_version: str = typer.Option(
        "v1",
        "--prompt-version",
        help="Cache salt for prompt/schema changes (bump when you change prompts/output shaping).",
    ),
    backend_id: str | None = typer.Option(
        None,
        "--backend-id",
        help="Optional cache salt override (e.g. model name). If omitted, derived from backend + kwargs.",
    ),
    recompute: bool = typer.Option(False, "--recompute"),
    strict: bool = typer.Option(False, "--strict"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    out: Path | None = typer.Option(None, "--out"),
    verbose: bool = typer.Option(
        False, "--verbose", help="Print step logs to console."
    ),
    progress: bool = typer.Option(
        False, "--progress", help="Show a progress bar (requires rich)."
    ),
):
    """
    Fill scene.vision using keyframe images.
    Quiet by default; --verbose prints more; --progress shows per-scene bar.
    """
    try:
        backend_kwargs_dict = json.loads(backend_kwargs)
        if not isinstance(backend_kwargs_dict, dict):
            raise ValueError("backend-kwargs must be a JSON object")
    except Exception as e:
        raise typer.BadParameter(f"--backend-kwargs must be valid JSON object: {e}")

    beats_path = beats_path.resolve()
    run_dir = beats_path.parent
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log = RunLogger(
        log_path=logs_dir / "describe.log",
        verbose=verbose,
        progress_enabled=progress,
    )

    t0 = time.perf_counter()
    try:
        out_path = describe_beats(
            beats_path,
            backend=backend,
            backend_kwargs=backend_kwargs_dict,
            prompt_version=prompt_version,
            backend_id=backend_id,
            recompute=recompute,
            strict=strict,
            overwrite=overwrite,
            out_path=out,
            logger=log,
        )
        elapsed = time.perf_counter() - t0

        run = BeatsRun.model_validate_json(out_path.read_text(encoding="utf-8"))

        desc = {}
        if isinstance(run.params, dict):
            desc = run.params.get("describe", {}) or {}
        counts = desc.get("counts", {}) if isinstance(desc, dict) else {}
        failed = counts.get("failed") if isinstance(counts, dict) else None

        typer.echo("validate: OK")
        typer.echo(f"out:      {out_path}")
        typer.echo(f"elapsed:  {elapsed:.1f}s")
        if isinstance(failed, int):
            typer.echo(f"failed:   {failed}")

    finally:
        log.close()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
