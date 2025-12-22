# constants/defaults (fps=30, max1280 preset, paths)
from __future__ import annotations

from pipeline.steps.normalize import Profile

NORMALIZE_PROFILE_DEFAULT: Profile = "balanced"
FPS_DEFAULT: int = 30
MAX_WIDTH_DEFAULT: int = 1280
MAX_HEIGHT_DEFAULT: int = 720
