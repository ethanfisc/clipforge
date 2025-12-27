# openai.py - OpenAI vision backend for describe_scene()
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Literal, cast

from openai import OpenAI
from openai.types.responses import ResponseInputParam
from pydantic import BaseModel, Field

Verbosity = Literal["low", "medium", "high"]
ReasoningEffort = Literal[
    "minimal", "low", "medium", "high"
]  # avoid "none" for gpt-5-mini


class VisionOut(BaseModel):
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    text_on_screen: str | None = None
    confidence: float = Field(ge=0, le=1, default=0.0)


def _mime_for(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suf == ".png":
        return "image/png"
    return "image/jpeg"


def _to_data_url(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{_mime_for(path)};base64,{b64}"


def _best_effort_json(raw: str) -> dict[str, Any] | None:
    raw = raw.strip()
    # Try direct
    try:
        return json.loads(raw)
    except Exception:
        pass
    # Try to extract the first {...} block
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except Exception:
            return None
    return None


def _strip_fences(s: str) -> str:
    # Keep this small: sometimes models still wrap output.
    s = s.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        lines = lines[1:] if lines else []
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


class Backend:
    def __init__(
        self,
        *,
        model: str = "gpt-5-mini",
        max_output_tokens: int = 500,
        api_key: str | None = None,
        base_url: str | None = None,
        reasoning_effort: ReasoningEffort = "low",
        verbosity: Verbosity = "low",
    ) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key and not base_url:
            raise ValueError("OPENAI_API_KEY is not set (or pass api_key=...)")

        self._client = OpenAI(api_key=key, base_url=base_url)
        self._model = model
        self._max_output_tokens = int(max_output_tokens)
        self._reasoning_effort: ReasoningEffort = reasoning_effort
        self._verbosity: Verbosity = verbosity

        self._instructions = (
            "You are a careful visual describer. "
            "Use ONLY what is visible in the provided keyframes. "
            "Do not infer intent, time, location, or creator identity. "
            "If uncertain, be conservative and lower confidence. "
            "Return ONLY valid JSON matching the requested schema."
        )

        self._prompt = (
            "Return ONLY JSON with keys: summary, tags, text_on_screen, confidence.\n"
            "summary: 1-2 sentences of visible action; concrete nouns+verbs; no guessing.\n"
            "tags: 3-8 lowercase tags, 1-2 words each.\n"
            "text_on_screen: exact readable text else null.\n"
            "confidence: 0..1; if unclear set summary='' and confidence=0.\n\n"
            "No markdown/code fences. No extra keys."
        )

    def describe_scene(self, image_paths: list[Path]) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": self._prompt}]
        content.extend(
            {"type": "input_image", "image_url": _to_data_url(p)} for p in image_paths
        )
        input_payload = cast(ResponseInputParam, [{"role": "user", "content": content}])

        resp = self._client.responses.create(
            model=self._model,
            instructions=self._instructions,
            input=input_payload,
            max_output_tokens=self._max_output_tokens,
            reasoning={"effort": self._reasoning_effort},
            text={"verbosity": self._verbosity},
        )

        raw = _strip_fences((getattr(resp, "output_text", "") or "").strip())
        if not raw:
            raise ValueError("openai_returned_empty_text")

        data = _best_effort_json(raw)
        if data is None:
            raise ValueError(f"openai_returned_non_json: {raw[:200]}")

        return VisionOut.model_validate(data).model_dump()


def build(**kwargs: Any) -> Backend:
    return Backend(**kwargs)
