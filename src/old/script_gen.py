import json
from openai import OpenAI

from .config import OPENAI_API_KEY
from .models import PettyRevengeStory, ShortScript

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You write scripts for 40–55 second YouTube Shorts.

Source: a petty revenge story.

Task:
1. Hook: 1–2 sentences that grab attention.
2. Body: retell the story in first person, fast-paced, clear setup, petty revenge action, and payoff.
3. Ending: a satisfying or slightly smug final line.

Constraints:
- 110–160 words total.
- Do NOT mention Reddit, posts, or usernames.
- Do NOT say “I saw this online”; just tell the story as if it's being told directly.
- Keep the tone casual and conversational.

Return ONLY valid JSON in this exact format:

{
  "script": "<full script>",
  "caption_lines": [
    "first caption line",
    "second caption line",
    "..."
  ]
}

caption_lines should be short, natural subtitle chunks (1–2 short sentences each).
""".strip()


def generate_short_script(story: PettyRevengeStory) -> ShortScript:
    user_content = f"Title: {story.title}\n\nBody:\n{story.body}"

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.7,
    )

    raw = completion.choices[0].message.content
    # In case the model accidentally wraps JSON in ```json ``` or similar
    raw = raw.strip().strip("`").strip()
    if raw.lower().startswith("json"):
        raw = raw[4:].lstrip()

    data = json.loads(raw)
    return ShortScript(
        script=data["script"].strip(),
        caption_lines=[line.strip() for line in data["caption_lines"] if line.strip()],
    )
