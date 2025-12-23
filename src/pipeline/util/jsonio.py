# write/read validated BeatsRun
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def write_json_stable(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    if not text.endswith("\n"):
        text += "\n"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
