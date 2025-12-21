"""
Generate the JSON Schema from the BeatsRun contract
"""

import json
from pathlib import Path
from pipeline.contracts.beats import BeatsRun

out = Path("schemas/beats.schema.json")
out.parent.mkdir(parents=True, exist_ok=True)

schema = BeatsRun.model_json_schema()
out.write_text(json.dumps(schema, indent=2))
print(f"Wrote {out}")
