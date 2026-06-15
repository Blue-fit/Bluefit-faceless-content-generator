# Golden Example — research → specs → prompts (reference)

> **What this is:** one fully worked pass through the weekly pipeline, by hand, so
> the data contracts and the "research feeds the prompt" flow are concrete. It is
> the **north star** for the generator and a ready-made **test fixture** later.
> Values are illustrative. Pairs with [`brand-style-kit.md`](brand-style-kit.md) and
> [`prompting-playbook.md`](prompting-playbook.md).

The chain: `TrendBrief (abstract) → + brand chunks + rules → 3 PostSpecs (scene only)
→ assemble (scene + style block) → Nano Banana / Veo`.

---

## 1. Input — `TrendBrief` (from the researcher, abstract themes)

```json
{
  "week_start": "2026-06-15",
  "themes": [
    {
      "title": "Open-water morning swims as a mental-wellness ritual",
      "summary": "Cold/open-water swimming is surging as a calm, restorative ritual rather than a performance challenge.",
      "why_relevant": "Maps directly to Blue Zones longevity + the 'Blue Zone on the Waal' water identity.",
      "source_url": "https://example.com/openwater-wellness-trend"
    },
    {
      "title": "Run clubs as the new social scene",
      "summary": "Community run clubs are framed as connection-first, not competition.",
      "why_relevant": "Fits Community pillar; movement as a shared experience.",
      "source_url": "https://example.com/run-club-social"
    },
    {
      "title": "'Exercise snacking' over the long grind",
      "summary": "Short, frequent movement breaks beat punishing single sessions.",
      "why_relevant": "Reinforces 'Keep Moving' rejecting the no-excuses mindset.",
      "source_url": "https://example.com/exercise-snacking"
    }
  ]
}
```

---

## 2. Output — 3 × `PostSpec` (generator writes the **scene only**)

> Note the generator writes `scene_prompt`, **not** the style block. It also
> declares `references_used` (→ becomes `reasoning_blob`, architecture.md §6).

**Post 1 — image · Community · theme: run clubs**
```json
{
  "pillar": "Community",
  "type": "image",
  "scene_prompt": "A small, diverse run club jogging together along a riverside path at sunrise, seen as a wide shot with long soft shadows; relaxed body language, mid-conversation, no front-runner — connection over competition; shallow depth of field, 35mm.",
  "motion": null,
  "duration_seconds": null,
  "caption_template": "observation",
  "caption": "Funny how the kilometre flies when you're mid-conversation. Who's your run-talk person?",
  "references_used": { "theme": "Run clubs as the new social scene", "brand_cues": ["Community pillar: wide shots + natural interaction", "riverside/open setting"], "rule_applied": "ocean blue ≠ navy" }
}
```

**Post 2 — image · Keep Moving · theme: open-water swims**
```json
{
  "pillar": "Keep Moving",
  "type": "image",
  "scene_prompt": "A lone swimmer wading into calm open water at golden hour, ocean-blue tones across the surface, unhurried and serene — restorative, not a race; eye-level composition with generous negative space and sky.",
  "motion": null,
  "duration_seconds": null,
  "caption_template": "question",
  "caption": "If your morning started in open water instead of on your phone — what changes by lunchtime?",
  "references_used": { "theme": "Open-water morning swims as a mental-wellness ritual", "brand_cues": ["Keep Moving: outdoor swimming, anti 'no excuses'", "open water + sunrise"], "rule_applied": "ocean blue ≠ navy" }
}
```

**Post 3 — video · Keep Setting Goals · theme: exercise snacking**
```json
{
  "pillar": "Keep Setting Goals",
  "type": "video",
  "scene_prompt": "A person taking a quiet two-minute movement break by a sunlit window in a clean, light-filled space — a few calm stretches, unhurried, content; cool blue palette.",
  "motion": "Slow dolly-in, drifting handheld; calm contemplative pace.",
  "duration_seconds": 8,
  "caption_template": "hot_take",
  "caption": "Two honest minutes beats one heroic hour you'll skip tomorrow. Change my mind.",
  "references_used": { "theme": "'Exercise snacking' over the long grind", "brand_cues": ["Keep Setting Goals: quiet routine, incremental", "light-filled functional space"], "rule_applied": null }
}
```

---

## 3. Assembled final prompts (scene + style block)

**Post 1 → Nano Banana (4:5):**
```
A small, diverse run club jogging together along a riverside path at sunrise, seen
as a wide shot with long soft shadows; relaxed body language, mid-conversation, no
front-runner — connection over competition; shallow depth of field, 35mm.

Style: cinematic editorial wellness-and-travel photography, Blue Fit aesthetic —
Blue Zones-inspired, premium, calm, aspirational. Natural light (golden hour or
soft overcast). Authentic real people of varied ages and body types, candid, in
gentle motion. Open natural settings ... ocean blue (NOT navy) leads ... Avoid:
hardcore gym / "no excuses" tropes, ... on-image text unless requested. Instagram
portrait, 4:5.
```

**Post 3 → Veo 3.1 Fast (9:16, 8s):**
```
A person taking a quiet two-minute movement break by a sunlit window in a clean,
light-filled space — a few calm stretches, unhurried, content; cool blue palette.
Camera: slow dolly-in, drifting handheld; calm contemplative pace. Audio: soft
ambient room tone, faint birdsong through the window.

[+ VIDEO STYLE BLOCK: ... ocean blue (NOT navy) leads ... natural ambient sound
only, no hype music. Vertical 9:16.]
```
*(Post 2 follows the same image pattern as Post 1.)*

---

## 4. What this demonstrates

- **Research stays abstract** (themes) → the **generator visualizes** them into
  concrete scenes. The researcher never writes the image prompt.
- **Brand is enforced two ways:** soft, via the brand cues the generator leans on
  (from `brand_rag`); hard, via the **constant style block** appended in code.
- **Rules ride on top** — e.g. `ocean blue ≠ navy` is applied at assembly.
- **3 posts = 2 image + 1 video**, each a distinct pillar, each with an engagement
  caption template → satisfies the PRD weekly KPI.
- **`references_used` is mandatory** and becomes the `reasoning_blob` audit trail.

> Reuse note: when we build, this example becomes a pytest fixture — feed the
> `TrendBrief`, assert 3 valid `PostSpec`s (2 image/1 video, distinct pillars),
> and assert the assembled prompt contains the style block + any active rule.
