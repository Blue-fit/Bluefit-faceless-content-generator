# 008 — The mascot is the hero of every post

Date: 2026-09-15 · Status: accepted

(First ADR file in this directory. 001–007 are referenced from the root `CLAUDE.md`
but were never written; numbering starts at 008 so they can be backfilled.)

## Context

The weekly output (2 images + 1 video, calm cinematic faceless scenes) was judged
by Blue Fit as too easy-going and not attention-grabbing. Blue Fit has a real,
life-size plush blue bear mascot and asked for content that stars it, uses it to
communicate the four pillars, is attention-grabbing and interactive, does not need
to be ultra-realistic, and is not childish. The product remains "faceless": the
mascot has no identifiable human face, and real people beside it stay faceless.

## Decisions

1. **Mascot in all three weekly posts**, as the real plush costume placed in real
   photographic settings (no cartoon/CG restyle). No name; captions stay in brand
   voice with the mascot in the third person; it never speaks.
2. **Likeness via reference photos.** Three curated photos live in
   `backend/assets/mascot/` (committed, ~1024 px, JPEG q85; originals stay out of
   git): `01-front` (lobby), `02-front-hall` (gym hall, mid distance), `03-side`
   (treadmill). The warm-lit face close-up was dropped — it tinted the rendered
   muzzle pink; the description in the style block says white. `app/agents/mascot.py` loads them once per process and fingerprints them
   (`mascot_refs_version`, stamped into every `reasoning_blob`).
   Resize command used (Pillow, EXIF-transposed):
   `ImageOps.exif_transpose(Image.open(src)).convert("RGB").thumbnail((1024, 1024))`
   then `save(dst, "JPEG", quality=85, optimize=True)`.
3. **Video = image-to-video, not Veo reference images.** The pipeline renders the
   opening frame with Nano Banana + the reference photos, then hands that still to
   Veo 3.1 Fast as `image=` (first frame). Rationale: Nano Banana's multi-image
   conditioning pins the likeness far better than Veo "ingredients"; Veo then
   animates real pixels so the mascot holds for 8 s; 9:16 image-to-video on the
   Fast model is documented; the still's headroom carries into the clip. Cost is
   one extra image (€0.039) per video. Veo's `reference_images` path is implemented
   in `render_video` as a probe only (`scripts/run_video.py --refs`): the Developer
   API has been reported to accept it only at 16:9 on the non-Fast model. Probe
   result: _not yet run_ (`scripts/run_video.py --refs`, ~€0.80). The primary path
   was verified 2026-09-15: 9:16 image-to-video on Fast, 8 s, audio track present,
   mascot identical across the clip.
4. **One shared render path.** `app/agents/render.py::render_base` is used by both
   the weekly pipeline and chat edits, so an edit can never regress to a
   mascot-less render. This was the second use of the render sequence.
5. **`beat` on every PostSpec** — the one scroll-stopping moment. It is shown in
   the generator's "recently covered" avoid-list (via `memory_search`) so gags are
   not repeated week over week, and stored in `reasoning_blob`.
6. **Hook overlay moves to the upper third on images** (`_HOOK_Y_FRAC = 0.22`,
   same as video) — centred text would sit on the bear. The style block reserves
   the top quarter of the frame.
7. **Brand grounding.** A `Mascotte` section was appended to the ingested
   requirements doc (`context/…Requirements.md`) and `brand_chunks` re-ingested;
   additionally the generator message labels brand context as values/voice/pillars
   only, because the rest of that doc still describes the old calm/cinematic look.

8. **Google's image filter and the "teddy" problem.** Measured 2026-09-15 with
   `gemini-3.1-flash-image`: any request that included a mascot photo came back
   with `finish_reason=PROHIBITED_CONTENT` (the non-configurable hard filter) and
   an empty candidate, while the same photo could be *described* fine and a
   text-only "plush blue bear" rendered fine. The filter is stochastic — identical
   requests pass ~50–65 % of the time — and is pushed over the edge by *toy/child*
   context: "plush", "soft", "friendly", "no clothes", a knife in the scene, the
   photo of a giant teddy. Framing the subject as **"the official mascot suit of
   Blue Fit, an adult fitness club … editorial sports-marketing photography …
   adult members"** is what got the front-facing photos through at all (0/7 → ~2/3).
   Neither dropping the faceless-people sentence nor using a Google-generated
   "character sheet" as the reference changed the rate materially, so real photos
   stay the reference. Mitigations that ship: (a) that framing in
   `style_block.md`; (b) `render_image` re-rolls a blocked candidate up to 5×
   (a blocked call bills no output tokens); (c) `generator.md` forbids
   *plush/teddy/toy/cuddly/kids/children/baby/bedroom* and cutting/knife scenes in
   `scene_prompt` and requires "adult" for any people. Expect a
   `genai.image_blocked` warning on roughly every other render; a post that fails
   after 5 attempts is isolated by the pipeline like any other failure.

## Consequences

- Editing a pre-pivot post now produces a mascot version (refs are always passed).
- Video edits bill two `usage` rows (still + clip), both `trigger="edit"`.
- `PostSpec.beat` is optional in the schema (additive; older posts have none).
- Image cost per post is unchanged; wall-clock per image grows by one extra call
  on about half of renders.
