# Prompts changelog

## 2026-06-21
- `agents/prompts/caption_question.md`, `caption_hottake.md`, `caption_observation.md`
  — created. Canonical specs for the three engagement caption styles the generator
  selects per post (recorded in `reasoning_blob.engagement_template`): shape, do's/
  don'ts, and a Blue Fit-voice example adapted from the requirements doc. Source of
  truth for the future `generate_caption.py` (Phase-2 caption rewrite). Reason: fill
  the empty template placeholders.
- `agents/prompts/explain_render.md` — created. Gemini Flash prompt for the Phase-2
  `explain` tool (PRD §4.6): renders a post's structured `reasoning_blob` into a
  plain-English, client-friendly "why we made this", translating raw fields
  (IDs/hashes/model names) into human terms. Reason: build the explain transparency tool.

## 2026-06-19
- `agents/prompts/generator.md` — `hook` is now produced for **every** post
  (image and video), not video only. The brand requirements doc calls for *"een
  pakkende oneliner centraal in beeld"* on posts, so images now also carry a
  curiosity-gap oneliner that's overlaid (centered) on the still. Reason:
  user request to add a hook to images, backed by the brand doc.

## 2026-06-16
- `agents/prompts/researcher.md` — created. Gemini Flash + `google_search`
  researcher; outputs abstract `TrendBrief` themes grounded in Blue Fit's 4
  pillars + Power-9 values; JSON-only output.
- `agents/prompts/generator.md` — created. Gemini Pro generator; static brand
  constitution + task to produce 3 `PostSpec`s (2 image, 1 video, distinct
  pillars). Hybrid injection: the week's themes/brand/rules arrive in the message;
  `scene_prompt` is scene-only (style block appended downstream).
- `agents/prompts/style_block*.md` — created. Code-appended brand visual style
  for the hybrid build: shared base (`style_block.md`) + image/video tails.
- `style_block.md` + `generator.md` — enforce **faceless** content: no
  identifiable faces (people from behind, in silhouette, cropped, or distant; or
  the focus on hands / activity / scenery). The product is faceless-content, but
  nothing previously instructed the models to avoid faces. Verified by re-render.
