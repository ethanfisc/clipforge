import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Reddit
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "petty-shorts-bot/0.1")

SUBREDDIT = "pettyrevenge"

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Paths
ASSETS_DIR = BASE_DIR / "assets"
GAMEPLAY_DIR = ASSETS_DIR / "gameplay"

OUTPUT_DIR = BASE_DIR / "outputs"
AUDIO_DIR = OUTPUT_DIR / "audio"
SUBTITLES_DIR = OUTPUT_DIR / "subtitles"
VIDEOS_DIR = OUTPUT_DIR / "videos"

SEEN_IDS_PATH = OUTPUT_DIR / "seen_ids.txt"

for d in [AUDIO_DIR, SUBTITLES_DIR, VIDEOS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
