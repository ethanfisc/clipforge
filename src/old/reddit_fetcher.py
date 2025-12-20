import json
from pathlib import Path
from typing import Set, Optional

import praw

from .config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    SUBREDDIT,
    SEEN_IDS_PATH,
)
from .models import PettyRevengeStory


def load_seen_ids(path: Path = SEEN_IDS_PATH) -> Set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_seen_ids(ids: Set[str], path: Path = SEEN_IDS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for _id in sorted(ids):
            f.write(_id + "\n")


def get_reddit_client() -> praw.Reddit:
    if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET):
        raise RuntimeError("Reddit credentials missing in .env")
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )
    return reddit


def pick_best_story(seen_ids: Set[str]) -> Optional[PettyRevengeStory]:
    reddit = get_reddit_client()
    sub = reddit.subreddit(SUBREDDIT)

    candidates = []
    for submission in sub.top(time_filter="day", limit=50):
        if submission.over_18:
            continue
        if submission.stickied:
            continue
        if submission.id in seen_ids:
            continue
        if not submission.selftext:
            continue

        text_len = len(submission.selftext)
        if text_len < 300 or text_len > 4000:
            continue

        candidates.append(submission)

    if not candidates:
        return None

    candidates.sort(key=lambda s: s.score, reverse=True)
    s = candidates[0]

    return PettyRevengeStory(
        reddit_id=s.id,
        title=s.title,
        body=s.selftext,
        url=f"https://reddit.com{s.permalink}",
        score=s.score,
        created_utc=float(s.created_utc),
    )
