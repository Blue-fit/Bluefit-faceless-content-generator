# Prompting Playbook — Nano Banana & Veo 3.1 (reference)

> **What this is:** how to write effective prompts for the two generation models,
> grounded in the official Gemini API docs (fetched June 2026), then tuned to the
> Blue Fit aesthetic. Pairs with [`brand-style-kit.md`](brand-style-kit.md). Reference
> doc — not code. Verify model IDs/limits against the live docs before shipping.

Sources: [Image generation](https://ai.google.dev/gemini-api/docs/image-generation) ·
[Veo 3.1 video](https://ai.google.dev/gemini-api/docs/video)

---

## 1. Images — Nano Banana (`gemini-2.5-flash-image`)

### Prompt structure (order matters less than coverage)
Cover these six, conversationally — not as rigid labels:
1. **Subject** — who/what, doing what.
2. **Composition** — framing, layout (wide shot, close-up, rule-of-thirds).
3. **Lighting** — golden hour, soft overcast, backlit.
4. **Camera / lens** — e.g. "35mm, shallow depth of field," "aerial."
5. **Style & mood** — cinematic editorial, calm, aspirational.
6. **Colour** — the Blue Fit palette (ocean/dark/light blue, black).

### Key facts
- **Aspect ratio:** supports `4:5`, `1:1`, `9:16`, `16:9`, etc. → use **`4:5`** for
  Instagram feed. Set via `imageConfig.aspectRatio`.
- **Resolution:** `512`/`1K`/`2K`/`4K` via `imageConfig.imageSize` (**uppercase K**).
  Default 1K is fine for IG; 2K for crispness.
- **Text rendering:** strong — good for legible on-image text *when asked* (use
  Montserrat). Our default is **no on-image text** unless the post needs it.
- **Reference images:** up to ~10 as image `Part`s in `contents` — this is how
  every render carries the **mascot photos** (`app/agents/mascot.py`), so the bear
  is *this* costume and not a generic blue bear.
- **Negative prompting:** there is **no separate negative field.** Express "avoid X"
  in plain language inside the prompt (this is why the style block spells out the
  negative list).

### Do / Don't
- ✅ Be **specific** about the important things (subject, light, palette, mood).
- ✅ Layer a few constraints; lead with the scene, end with the style block.
- ❌ Don't over-engineer / bloat the prompt — Gemini 3.x prompts best with direct,
  clear language and can over-analyze verbose prompts.
- ❌ Don't rely on negatives alone; also state the positive you *do* want.

---

## 2. Video — Veo 3.1 Fast (`veo-3.1-fast-generate-preview`)

### Prompt structure
1. **Subject** + **Action** (what they're doing).
2. **Scene / setting.**
3. **Camera positioning & motion** — "aerial drift," "slow dolly in," "eye-level."
4. **Composition & focus** — wide/close-up, shallow/deep focus, lens.
5. **Ambiance** — colour + lighting ("cool blue tones, sunrise").
6. **Audio** — Veo generates **native audio**:
   - Dialogue in quotes: `"keep going," she says softly`
   - SFX described: "soft splash of water, distant birdsong"
   - Ambient: "a gentle riverside hum"

### Key facts & a constraint to resolve ⚠️
- **Native duration: 4, 6, or 8 seconds.** Longer needs **video extension**
  (+~7s per step, up to 20×).
- **⚠️ Spec conflict to settle with the team:** PRD KPI §3 says video **10–30s**,
  but PRD §4.1 says **5–8s**, and Veo native max is **8s**. Reaching 10–30s means
  stitching via extension (more cost + complexity). **Recommend** confirming: a
  single 8s clip (simplest, matches §4.1) vs. extension to 10–30s (matches the KPI).
- **Resolution:** `720p` default (good for the Fast variant + cost). 1080p/4K are
  **8s-only**.
- **Aspect ratio:** `16:9` or **`9:16`** → use **9:16** (vertical Reels/Stories).
  Note Veo does **not** offer 4:5, so video ≠ image aspect ratio.
- **Image-to-video / first frame:** seed from a still. **This is how the mascot
  stays consistent in video** (decisions/008): Nano Banana renders the opening frame
  with the mascot reference photos, Veo animates it via `image=`. Prompt the *motion
  and the beat's payoff*; the composition is fixed by the still.
- **Reference images ("ingredients", ≤3 ASSET):** implemented in `render_video` as a
  probe only — reported to work only at 16:9 on the non-Fast model on the Developer
  API. `scripts/run_video.py --refs` tests it.

### Do / Don't
- ✅ Use descriptive adjectives/adverbs; name the camera move explicitly.
- ✅ Add "portrait" for better facial detail when people are featured.
- ✅ Specify the sound design: upbeat, playful, non-aggressive; no speech (the
  mascot never talks).
- ❌ Don't assume >8s "just works" — plan for extension or cap at 8s.
- ❌ Don't request hype music, crowd noise, or cuts (one continuous move).

---

## 3. Brand-tuned templates (fill-in-the-blank)

The generator writes the **scene** (the blanks); code appends the style block.

**Image (Nano Banana, 4:5):**
```
{subject + action} in {natural Blue Fit setting}, {composition}, {natural lighting},
{camera/lens}, evoking {pillar mood/theme}.
<<< append IMAGE STYLE BLOCK from brand-style-kit.md >>>
```

**Video (Veo 3.1 Fast, 9:16, ≤8s):**
```
{subject + action} in {setting}. Camera: {slow movement}. {composition + focus}.
{cool blue ambiance + light}. Audio: {natural ambient sound}.
<<< append VIDEO STYLE BLOCK from brand-style-kit.md >>>
```

See [`golden-example.md`](golden-example.md) for these filled in end-to-end.
