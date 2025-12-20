import json
import subprocess
from pathlib import Path
from typing import Union

from openai import OpenAI

from .config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def get_media_duration(path: Union[str, Path]) -> float:
    path = str(path)
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def synthesize_voice(script: str, out_path: Path) -> float:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Text-to-speech via OpenAI (using gpt-4o-mini-tts model)
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=script,
    ) as response:
        response.stream_to_file(out_path)

    duration = get_media_duration(out_path)
    return duration
