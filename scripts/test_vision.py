from pathlib import Path
from pipeline.vision.backends.openai import Backend

# adjust paths to real keyframe files
frames = [
    Path("runs/c1ebe80f-d9fe-4f0f-9464-b8d7b3789b3e/frames/scene_000/kf_00.jpg"),
    Path("runs/c1ebe80f-d9fe-4f0f-9464-b8d7b3789b3e/frames/scene_000/kf_01.jpg"),
]

b = Backend(model="gpt-5-mini", reasoning_effort="low", verbosity="low")
out = b.describe_scene(frames)
print(out)
