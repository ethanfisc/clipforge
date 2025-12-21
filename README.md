# Project Spec
run ```pip install -e ".[dev]"```
## Downloading from youtube

```jsx
 yt-dlp --no-playlist -f "bv*+ba/b" "https://www.youtube.com/watch?v=GYahXGrMGgU"
```

## Normalization

### Hard requirements

- Container: MP4
- Video codec: H.264 (libx264)
- Pixel format: yuv420p (compat)
- Frame rate: CFR 30 (predictable timebase)
- Aspect metadata: setsar=1
- Resolution: **720x1280** (vertical) or “max dimension 1280”
- Audio: prob wont use but keep it (AAC)

```jsx
// "max dimension 1280"
ffmpeg -i "Cowhide drum牛皮大鼓 [GYahXGrMGgU].webm" \
  -vf "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1" \
  -r 30 \
  -c:v libx264 -pix_fmt yuv420p -crf 16 -preset slow \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  "normalized_720x1280.mp4"

// Force exact 720x1280 (vertical) + fill frame (crop instead of pad)
// Force exact 720x1280 (vertical) + keep full image (letterbox/pillarbox)
```

## Option 2: DIY timeline (most controllable, easiest to debug)

**Pieces**

- **Scene/shot segmentation**: PySceneDetect finds cuts and gives you timecodes; it can also split into clips. [SceneDetect+1](https://www.scenedetect.com/)
- **Keyframes per scene**: extract 1–3 representative frames (ffmpeg).
- **Vision summarizer**: send those frames to a multimodal model (OpenAI vision is image-input oriented, so this is a natural fit). [OpenAI Platform](https://platform.openai.com/docs/guides/images-vision)

**Output**

- A JSON like:
    - `[{start_ts, end_ts, keyframes[], beat_summary, objects/actions, confidence}]`
- This is the clean “link summaries to specific timestamps/scenes” artifact you described.

**Tradeoff**

- More glue code, but you get *exact* start/end times (because you own the segmentation).

High-level architecture for “video -> beats.json”:

- Inputs
    - `video_path` (downloaded asset)
    - config: target fps for sampling, min scene length, max beats, output format
- Stage 1: Normalize (optional but common)
    - Purpose: make everything consistent (resolution, fps, audio presence)
    - Output: `normalized.mp4`
- Stage 2: Segment into scenes (timeline backbone)
    - Purpose: detect cut points / boundaries so you have clean start/end timestamps
    - Output: `scenes = [{id, start_ts, end_ts}]`
- Stage 3: Represent each scene (reduce data)
    - Purpose: turn each scene into a small “visual signature”
    - Typical: pick 1–3 keyframes per scene + optional low-res clip snippet
    - Output: `scene_assets = [{scene_id, keyframes[]}]`
- Stage 4: Describe each scene (vision labeling)
    - Purpose: produce a compact, consistent description of what’s happening
    - Output per scene:
        - `summary` (1–2 sentences)
        - `tags` (objects/actions/materials)
        - `step_hint` (is it part of a process, what step number likely)
        - `salience` (how important for story)
- Stage 5: Consolidate into beats (make it usable)
    - Purpose: merge redundant scenes, compress into 5–12 beats, keep the story
    - Output: `beats = [{beat_id, start_ts, end_ts, summary, keyframes, tags}]`
- Stage 6: Emit your core artifact
    - `beats.json` (this is the contract for your next layer: context + scripting)

What this gives you

- A stable interface between “understanding” and “rewriting/context”
- Exact timestamps you can cut to later
- A place to plug in improvements (better segmentation, better keyframes, better labeling) without redoing the whole system

If you want one guiding constraint: design everything so you can run it like

- `ingest(video) -> beats.json`
- `beats.json + context -> script.json`
- `script.json -> edit/render`

Smallest next step

- Define the beats.json schema (fields + constraints). Then you can build each stage independently.

##
