"""
Validate any beats.json file against the BeatsRun contract
"""

from pathlib import Path
from pipeline.contracts.beats import BeatsRun

p = Path("runs/latest/beats.json")
data = p.read_text()
BeatsRun.model_validate_json(data)
print("OK")
