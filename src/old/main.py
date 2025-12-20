from pathlib import Path

from .config import AUDIO_DIR, SUBTITLES_DIR, VIDEOS_DIR, SEEN_IDS_PATH
from .models import PettyRevengeStory
from .reddit_fetcher import load_seen_ids, save_seen_ids, pick_best_story
from .script_gen import generate_short_script
from .tts_client import synthesize_voice
from .subtitles import write_srt
from .video_composer import pick_gameplay_clip, compose_short


def build_one_short() -> Path | None:
    seen_ids = load_seen_ids()

    story = pick_best_story(seen_ids)
    if story is None:
        print("No suitable r/pettyrevenge story found.")
        return None

    print(f"Using story: {story.title!r} (score={story.score})")

    short_script = generate_short_script(story)
    print("Generated script.")

    audio_path = AUDIO_DIR / f"{story.reddit_id}.mp3"
    duration = synthesize_voice(short_script.script, audio_path)
    print(f"Synthesized audio ({duration:.1f}s).")

    srt_path = SUBTITLES_DIR / f"{story.reddit_id}.srt"
    write_srt(short_script.caption_lines, duration, srt_path)
    print("Wrote subtitles.")

    gameplay_clip = pick_gameplay_clip()
    video_path = VIDEOS_DIR / f"{story.reddit_id}.mp4"
    compose_short(gameplay_clip, audio_path, srt_path, video_path)
    print(f"Composed video: {video_path}")

    # Mark as seen
    seen_ids.add(story.reddit_id)
    save_seen_ids(seen_ids)

    return video_path


if __name__ == "__main__":
    build_one_short()
