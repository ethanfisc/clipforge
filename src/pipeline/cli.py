from __future__ import annotations

import uuid
from pathlib import Path

import typer

from pipeline.contracts.beats import BeatsRun
from pipeline.steps.download import download_video
from pipeline.steps.normalize import normalize_max1280_cfr30
from pipeline.steps.probe import probe_video
from pipeline.steps.scene_detect import detect_scenes
from pipeline.steps.keyframes import extract_keyframes
from pipeline.steps.emit_beats import write_beats_json
from pipeline.steps.describe import describe_beats
from pipeline.vision.backends.mock import MockVisionBackend

app = typer.Typer(no_args_is_help=True)


@app.callback()
def _root() -> None:
    """clipforge pipeline CLI."""
    pass


@app.command()
def run(
    url: str,
    threshold: float = 27.0,
    min_scene_len_frames: int = 15,
    keyframes_per_scene: int = 2,
    verbose: bool = False,
):
    """
    One-shot: URL -> beats.json (+ keyframes).
    Outputs:
      - assets/raw/ (raw)
      - assets/normalized/   (normalized mp4)
      - runs/<run_id>/       (beats.json, frames/, logs/)
    """
    repo_root = Path.cwd()

    raw_dir = repo_root / "assets" / "raw"
    normalized_dir = repo_root / "assets" / "normalized"

    run_id = str(uuid.uuid4())
    run_dir = repo_root / "runs" / run_id
    frames_dir = run_dir / "frames"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    def log(msg: str):
        if verbose:
            typer.echo(msg)

    log("[1/6] downloading...")
    raw_path, video_id, title = download_video(
        url, raw_dir, log_path=logs_dir / "yt-dlp_download.log"
    )

    log(f"  video_id: {video_id}")
    log(f"  title:    {title}")
    log(f"  raw:      {raw_path}")

    log("[2/6] normalizing...")
    normalized_path = normalize_max1280_cfr30(
        raw_path, normalized_dir, video_id, log_path=logs_dir / "ffmpeg_normalize.log"
    )
    log(f"  normalized: {normalized_path}")

    log("[3/6] probing...")
    duration_s, width, height = probe_video(
        normalized_path, log_path=logs_dir / "ffprobe.log"
    )
    log(f"  duration_s: {duration_s:.2f}")
    log(f"  size:       {width}x{height}")

    log("[4/6] detecting scenes...")
    scenes = detect_scenes(
        normalized_path,
        threshold=threshold,
        min_scene_len_frames=min_scene_len_frames,
    )
    log(f"  scenes:     {len(scenes)}")

    log("[5/6] extracting keyframes...")
    scene_kfs = extract_keyframes(
        normalized_path,
        frames_dir,
        scenes,
        per_scene=keyframes_per_scene,
        log_dir=logs_dir / "ffmpeg_keyframes",
    )
    log(f"  frames_dir: {frames_dir}")

    params = {
        "normalize": {"preset": "max1280_cfr30", "crf": 16, "preset_speed": "slow"},
        "scene_detect": {
            "method": "content",
            "threshold": threshold,
            "min_scene_len_frames": min_scene_len_frames,
        },
        "keyframes": {"strategy": "uniform_interior", "per_scene": keyframes_per_scene},
    }

    log("[6/6] writing beats.json...")
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
        scenes_keyframes=scene_kfs,
        out_path=run_dir / "beats.json",
    )

    BeatsRun.model_validate_json(beats_path.read_text(encoding="utf-8"))
    typer.echo("validate: OK")

    typer.echo(f"run_id: {run_id}")
    typer.echo(f"beats:  {beats_path}")
    typer.echo(f"frames: {frames_dir}")
    typer.echo(f"video:  {normalized_path}")

    @app.command()
    def describe(
        beats_path: Path,
        backend: str = typer.Option("mock", help="Vision backend (mock for now)"),
        strict: bool = typer.Option(False, help="Fail fast on first scene error"),
        overwrite: bool = typer.Option(
            False, help="Overwrite existing beats.vision.json"
        ),
        resume: bool = typer.Option(True, help="Skip scenes already described"),
        max_keyframes: int = typer.Option(3, help="Max keyframes per scene"),
    ):
        beats_path = beats_path.resolve()
        run_dir = beats_path.parent
        out_path = run_dir / "beats.vision.json"
        errors_path = run_dir / "describe.errors.json"
        log_path = run_dir / "logs" / "describe.log"

        if backend == "mock":
            vb = MockVisionBackend()
        else:
            raise typer.BadParameter(f"Unknown backend: {backend}")

        out = describe_beats(
            beats_path=beats_path,
            backend=vb,
            out_path=out_path,
            log_path=log_path,
            errors_path=errors_path,
            strict=strict,
            overwrite=overwrite,
            resume=resume,
            max_keyframes=max_keyframes,
        )
        typer.echo(str(out))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
