# Brand Style Kit — Blue Fit (reference)

> **What this is:** the Blue Fit visual "constitution," distilled from
> [`brand/document.md`](../../../brand/document.md) into a build-ready form. It is the
> source material for the eventual `prompts/style_block.md` (the immutable prompt
> suffix) and the brand section of `prompts/generator.md`. Reference doc — not code.

## 1. Brand essence

Blue Fit is **not a gym brand**. It's a premium **lifestyle / nature / performance**
brand inspired by the **Blue Zones** (regions where people live longer, healthier
lives). Position: *"The Blue Zone on the Waal."* The visual world is **cinematic,
free, and open** — wellness-meets-travel: sunrises, open water, wide landscapes,
calm and aspirational. It bridges physical health, mental tranquility, and
connection.

## 2. The four content pillars (with visual cues)

Every post maps to exactly one pillar. `posts.pillar` stores this.

| Pillar | Meaning | Concrete visual cues |
|--------|---------|----------------------|
| **Community** (Connection & Flow) | Health as a shared experience | Wide shots, silhouettes, natural group interaction, live moments, riverside/outdoor gatherings |
| **Keep Moving** (Sustainable Movement) | Rejects "no excuses"/"push your limits" | Functional training **and** outdoor running, cycling, swimming, open-air bootcamps; movement that looks joyful, not punishing |
| **Keep Setting Goals** (Consistent Growth) | Quiet performance, routine, incremental progress | Solo focus, calm determination, repeatable rituals; understated, not competitive |
| **Natural Eating** (Pure & Real) | Pure products, hydration, balance | Real whole foods, water, natural light on a table; no rigid "diet" stress |

## 3. The 9 Blue Fit values (Blue Zones "Power 9")

The ideology *behind* the four pillars — the Blue Zones "Power 9," localized for
Blue Fit (Dutch in parentheses). These are the deepest source of **content themes
and caption angles**: a post is usually *about* one of these values, expressed
through a pillar's visuals.

| # | Value (NL) | In one line |
|---|-----------|-------------|
| 1 | Move naturally (Beweeg natuurlijk) | Stay physically active daily — no need for formal, structured sport |
| 2 | Have a purpose (Doel hebben) | Know exactly why you get out of bed in the morning |
| 3 | Relaxation (Ontspanning) | Build deliberate daily rest and stress reduction into your routine |
| 4 | The 80% rule (80%-regel) | Stop eating when you're 80% full, not stuffed |
| 5 | Plant-based diet (Plantaardig eten) | Mostly plants; keep meat low |
| 6 | Wine with meals (Wijn bij het eten) | Wine in moderation, in good company |
| 7 | Belonging & meaning (Geloof of zingeving) | Take part in a spiritual or philosophical community |
| 8 | Family first (Familie eerst) | Prioritise loved ones; actively invest in family bonds |
| 9 | Social circles (Sociale kringen) | Surround yourself with a supportive community |

**Map values → pillars** (pick a value, render it through a pillar):
- **Keep Moving** ← Move naturally
- **Keep Setting Goals** ← Have a purpose · Relaxation
- **Natural Eating** ← The 80% rule · Plant-based diet · Wine with meals
- **Community** ← Belonging & meaning · Family first · Social circles

**Use:** the values drive *what a post is about* (theme + caption); pillars + the
style block drive *how it looks*. Where possible the researcher's themes should
ladder up to one of these — it keeps content unmistakably Blue Fit.

> Caveat: a few values are sensitive to depict literally on Instagram — **Wine with
> meals** (alcohol) and **Belonging/spiritual** — favour them as caption/theme
> angles or subtle context, not hero imagery.

## 4. Visual palette

**Primary colours:** Ocean Blue · Dark Blue · Light Blue · Black.

- **Ocean blue leads, and ocean blue ≠ navy.** This is a known preference and is
  exactly the kind of thing the `rules` system will reinforce — keep it explicit
  in the style block.
- Palette is cool and natural; **avoid warm/orange/neon grades.**

**Typography:** Montserrat — only relevant when text is rendered *into* an image
(Nano Banana renders text well; see the playbook).

## 5. Aesthetic — DO

- Cinematic, editorial photography feel; premium but authentic.
- **Natural light** — golden-hour or soft overcast.
- **Real people**, varied ages and body types, candid and in motion.
- Open natural environments (open water, riverside, sunrise skies, mountains) or
  clean, light-filled functional training spaces.
- Spacious composition with room to breathe; unhurried mood.

## 6. Aesthetic — the NEGATIVE list (never)

This is as important as the DO list. **Avoid:**
- Hardcore gym tropes, "no-excuses" / grind / sweat-and-strain intensity.
- "Perfect fitness bodies," flawless model/influencer physiques.
- Aggressive, salesy, or hype influencer energy.
- Warm/orange/neon colour grades; harsh artificial lighting.
- Stock-photo cheesiness; on-image text unless explicitly requested.

## 7. Ready-to-paste STYLE BLOCK drafts

The deterministic suffix appended to every generated scene prompt (the "hybrid
build"). Two variants because video needs motion + ambiance.

**Image style block (Nano Banana):**
```
Style: cinematic editorial wellness-and-travel photography, Blue Fit aesthetic —
Blue Zones-inspired, premium, calm, aspirational. Natural light (golden hour or
soft overcast). Authentic real people of varied ages and body types, candid, in
gentle motion. Open natural settings (open water, riverside, sunrise skies, wide
landscapes) or clean, light-filled functional training spaces. Colour palette:
ocean blue, dark blue, light blue, black — ocean blue (NOT navy) leads; cool,
natural grade. Spacious, unhurried composition. Avoid: hardcore gym / "no excuses"
tropes, sweat-and-grind intensity, flawless model/influencer physiques, aggressive
or salesy energy, warm/orange/neon grades, stock-photo cheesiness, on-image text
unless requested. Instagram portrait, 4:5.
```

**Video style block (Veo 3.1 Fast) — adds motion/ambiance/audio:**
```
[everything above, then:] Camera: slow, smooth, observational movement (gentle
dolly, drifting handheld, or aerial drift over water). Pace: calm, contemplative.
Ambient audio: natural sound only (water, wind, birdsong, soft footfalls) — no
aggressive or hype music. Vertical 9:16.
```

> Note: the style block is intentionally a **constant** so brand consistency does
> not depend on the LLM remembering it each run. The generator writes only the
> *scene*; code appends this. Active `rules` (e.g. "ocean blue not navy") are
> applied on top at assembly time.
