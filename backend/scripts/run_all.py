"""Full chain: researcher -> generator -> render the 2 images + 1 video.

Usage (from the backend/ directory):

    uv run python scripts/run_all.py

Runs the whole agent end to end and saves the 3 posts (2 images + 1 video with a
Montserrat hook overlay) to scripts/out/. Real, paid calls — roughly €2-3 and a
few minutes (dominated by Veo). Standalone: no DB/R2; brand context + rules are
sampled here (the real pipeline retrieves them).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agents.generator import build_generator
from app.agents.prompt_builder import build_image_prompt, build_video_prompt
from app.agents.researcher import build_researcher
from app.agents.schemas import GeneratorOutput
from app.tools.generate_image import render_image
from app.tools.generate_video import render_video
from app.tools.overlay_hook import overlay_hook, overlay_hook_image

OUT = Path(__file__).resolve().parent / "out"
APP, USER = "content-agent", "client"

# Local stand-in for the DB's post history: each run appends a "week" so the next
# run can tell the generator what to avoid repeating. In production this list
# comes from post_versions / weeks (Jacob's pipeline), not a JSON file.
HISTORY = OUT / "history.json"
_RECENT_WEEKS = 3  # how many past weeks to show the generator

_BRAND = (
    'Blue Fit is "The Blue Zone on the Waal" — premium, cinematic '
    "wellness-meets-travel: open water, sunrises, riverside, wide landscapes. "
    "Real people of varied ages, candid, faceless. Not a hardcore gym."
)
_RULE = "ocean blue, not navy"


def _strip(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return t


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _recent_block() -> str:
    """Render the last few weeks of posts as a 'do not repeat' block for the generator."""
    if not HISTORY.exists():
        return "(none yet — this is the first week)"
    weeks = json.loads(HISTORY.read_text(encoding="utf-8"))[-_RECENT_WEEKS:]
    lines: list[str] = []
    for n, week in enumerate(reversed(weeks), 1):
        lines.append(f"{n} week(s) ago:")
        for p in week:
            lines.append(
                f"  - {p['pillar']} | theme: {p['theme']} | value: {p['value']} "
                f"| hook: {p['hook']}"
            )
    return "\n".join(lines)


def _record_week(out: GeneratorOutput) -> None:
    """Append this run's 3 posts to the rolling history (most recent last)."""
    week = [
        {
            "pillar": p.pillar,
            "theme": p.references_used.theme,
            "value": p.references_used.value or "-",
            "hook": p.hook or "-",
        }
        for p in out.posts
    ]
    weeks = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    weeks.append(week)
    HISTORY.write_text(json.dumps(weeks[-12:], indent=2), encoding="utf-8")


async def _run(agent: LlmAgent, message: str, session_id: str) -> str:
    runner = InMemoryRunner(agent=agent, app_name=APP)
    await runner.session_service.create_session(
        app_name=APP, user_id=USER, session_id=session_id
    )
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final = ""
    async for ev in runner.run_async(
        user_id=USER, session_id=session_id, new_message=content
    ):
        if ev.is_final_response() and ev.content and ev.content.parts:
            final = ev.content.parts[0].text or ""
    return final


async def main() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("GOOGLE_API_KEY not found — create backend/.env first.")
    OUT.mkdir(exist_ok=True)

    print("1/3  Researcher -> themes ...")
    themes = _strip(
        await _run(
            build_researcher(), "Produce this week's Blue Fit content themes.", "all-r"
        )
    )

    print("2/3  Generator -> 3 PostSpecs ...")
    gen_msg = (
        f"## This week's themes (from the researcher)\n{themes}\n\n"
        f"## Brand context (retrieved)\n{_BRAND}\n\n## Active rules\n- {_RULE}\n\n"
        f"## Recently covered (make this week DIFFERENT)\n{_recent_block()}\n\n"
        "Produce the 3 PostSpecs now (2 image, 1 video, distinct pillars). "
        "Make them clearly different from the recently covered posts above."
    )
    out = GeneratorOutput.model_validate_json(
        _strip(await _run(build_generator(), gen_msg, "all-g"))
    )
    _record_week(out)  # remember this week so next week differs from it

    # Render the cheap/fast images first and the slow Veo video last, so a slow or
    # failed video never costs us the images. Each asset is isolated: one failure
    # is reported but does not abort the others.
    posts = sorted(enumerate(out.posts, 1), key=lambda p: p[1].type == "video")
    print("3/3  Rendering assets (images first, video last) ...")
    failures = 0
    for i, post in posts:
        name = f"{i}_{_slug(post.pillar)}_{post.type}"
        try:
            if post.type == "image":
                img = await render_image(
                    build_image_prompt(post.scene_prompt), aspect_ratio="9:16"
                )
                ext = ".jpg" if "jpeg" in img.mime_type else ".png"
                data = (
                    await overlay_hook_image(img.image_bytes, post.hook, ext)
                    if post.hook
                    else img.image_bytes
                )
                (OUT / f"{name}{ext}").write_bytes(data)
                saved = f"{name}{ext}"
            else:
                print("     (video: Veo, up to a few minutes) ...")
                vid = await render_video(
                    build_video_prompt(post.scene_prompt, post.motion),
                    "9:16",
                    post.duration_seconds or 8,
                )
                data = (
                    await overlay_hook(vid.video_bytes, post.hook)
                    if post.hook
                    else vid.video_bytes
                )
                (OUT / f"{name}.mp4").write_bytes(data)
                saved = f"{name}.mp4"
        except Exception as exc:  # noqa: BLE001 — report, keep the other assets
            failures += 1
            print(f"     [{post.pillar}] {post.type} FAILED: {exc}\n")
            continue

        # caption sidecar — the ready-to-post text next to each asset
        sidecar = [f"Pillar: {post.pillar}", f"Value: {post.references_used.value or '-'}"]
        if post.hook:
            sidecar.append(f"Hook: {post.hook}")
        sidecar += ["", post.caption]
        (OUT / f"{name}.txt").write_text("\n".join(sidecar), encoding="utf-8")

        print(f"     [{post.pillar} / {post.references_used.value}] -> {saved}  (+ {name}.txt)")
        print(f"        {post.caption}\n")

    done = "Done" if not failures else f"Done with {failures} failure(s)"
    print(f"\n{done}. Assets + caption .txt files are in: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
