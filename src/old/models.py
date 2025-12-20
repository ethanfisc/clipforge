from dataclasses import dataclass
from typing import List


@dataclass
class PettyRevengeStory:
    reddit_id: str
    title: str
    body: str
    url: str
    score: int
    created_utc: float


@dataclass
class ShortScript:
    script: str
    caption_lines: List[str]
