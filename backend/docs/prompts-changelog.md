# Prompts changelog

## 2026-09-17
- `agents/prompts/style_block_typography.md` — created. Appended to IMAGE prompts that
  carry a hook: the image model renders the typography in-picture — bold deep-blue
  sans-serif headline with the key word/number on a pale-blue highlight pill, a smaller
  handwritten caption CTA and a hand-drawn arrow. Words must be exact (a Flash
  read-back verifies and re-rolls). Reason: the client's own Gemini-made post looked
  designed; our PIL overlay looked like a sticker (decisions/010).
- `agents/prompts/style_block_clean_top.md` — created. Appended to a VIDEO's opening
  frame: top quarter clean, no on-image text (the hook is overlaid after Omni).
- `agents/prompts/style_block.md` — the "clean top / no on-image text" rules moved out
  of the shared base into the two tails above (they'd have suppressed the typography).
- `agents/prompts/generator.md` — `scene_prompt` for images now includes 1–2 short,
  correctly spelled Dutch text props (chalkboard, tote, whiteboard); video frames carry
  none. `hook` bullet notes it is rendered in-picture on images, overlaid on video.

## 2026-09-15
- `agents/prompts/generator.md` — **the Blue Fit mascot is now the hero of every
  post.** New "The hero" and "Tone: attention-grabbing, not childish" sections
  (contrast / surprise / interaction / mini-challenge / visual pun devices; deadpan
  adult humour; no party props). `scene_prompt` names it only as "the Blue Fit
  mascot" and never describes its look (the reference photos + style block do; look
  words would also trip the scene-family variety guard). New required `beat` field
  (the one scroll-stopping moment); for video `scene_prompt` is the opening frame and
  `motion` is the camera move + how the beat pays off. Brand context is explicitly
  values/voice/pillars only. Faceless rule kept for real people. Reason: client
  feedback that the calm cinematic posts were too easy-going and not
  attention-grabbing; they want their mascot to carry the values.
- `agents/prompts/style_block.md` — replaced: mascot-consistency block (keep the
  design of the mascot in the provided reference image(s), no cartoon/CG restyle,
  exactly one mascot), punchy clean high-contrast photographic look, headroom for the
  on-screen hook (top quarter clear), adult club members faceless; negative list kept
  minus "calm/unhurried", plus party props / cartoon rendering / extra characters.
  The subject is deliberately framed as *"the official mascot suit of Blue Fit, an
  adult fitness club … editorial sports-marketing photography"* and never as a
  plush/teddy: Google's hard image filter blocked every photo-referenced render
  under toy-like wording (decisions/008 §8).
- `agents/prompts/style_block_image.md` — mascot is the sharp, fully visible subject.
- `agents/prompts/style_block_video.md` — replaced: animate from the provided first
  frame (image-to-video), one continuous dynamic camera move, one beat inside 8 s,
  upbeat non-aggressive sound design, no speech. Reason: same pivot; video is now
  Nano Banana still → Veo first frame (see decisions/008).
- `agents/prompts/generator.md` — scene-writing rules for the same filter: no
  *plush/teddy/toy/cuddly/kids/children/baby/bedroom*, no knives or cutting scenes,
  people are always "adult members". Hook/caption sections tightened (curiosity-gap
  shapes; the caption must pay the hook off).
- `agents/prompts/researcher.md` — brand line no longer says the content is
  calm/cinematic; prefer themes a mascot can act out visually.
- `agents/prompts/caption_*.md` — the mascot is *de Blue Fit beer*, third person,
  never the narrator, never named.
- `agents/prompts/generator.md` — **clarified the hook↔caption division of labour.**
  The `hook` (every post, image + video) is now defined as *attention/curiosity bait
  only* — its one job is to stop the scroll and make the viewer open the caption; it
  must NOT contain the insight (explicitly rejects merely-poetic lines like *"het ritme
  van het bos"*), and prefers a counter-intuitive claim / provocative question / teaser
  shape while keeping the searchable-keyword weaving. The `caption` is now stated as
  *where the real value lives* and must **pay off** the hook (deliver the promised
  insight, no dangling curiosity gap). Reason: client feedback — the hook grabs
  attention, the caption is the sauce; generated hooks were pretty but weren't driving
  people into the caption. **Same-day follow-up:** the on-screen text is now the hook
  line (≤7 words) **plus an explicit caption call-to-action** (≤16 chars so it sits on
  its own line; varied across posts: *Lees de caption* / *Meer in caption* / *Lees
  verder ↓* / *Antwoord ↓*). Reason: a curiosity gap alone assumes the viewer knows the
  answer is in the caption — tell them where to go.
- `agents/prompts/generator.md` — **weekly anchor rule.** Power-9 values are now listed
  by their nine exact names, and every post is anchored to exactly ONE value bound to
  exactly ONE pillar; the week must use 3 different values and 3 different pillars, and
  none of the values used LAST week (the message now carries a *Forbidden Power-9
  values* section = a one-week cooldown). `references_used.value` is now required and
  typed (`schemas.Power9Value`, SCHEMA_VERSION 2) so the rule matches exactly, and
  `pipeline._enforce_value_rules` re-prompts once on a violation before any rendering.
  Reason: client wants structured week-over-week diversity — 3 values x 3 pillars, 1:1,
  with last week's values off-limits.
- `agents/prompts/generator.md` — **CTA is its own line and ends in 👇.** The on-screen
  text is now hook line + line break + caption call-to-action, and the CTA always ends
  with the pointing-down emoji (*Lees de caption 👇*). `overlay_hook.py` learned to honour
  line breaks and to draw emoji from a bundled colour font (`assets/fonts/NotoColorEmoji.ttf`,
  OFL) — Montserrat has no emoji glyphs — with a plain arrow fallback if the font is
  missing. Reason: client wants an explicit, emoji-marked nudge to read the caption.
- `agents/prompts/generator.md`, `caption_question.md`, `caption_hottake.md`,
  `caption_observation.md` — **the mascot is named Bluei.** Video captions are written in
  Bluei's own voice (first person, talking to the viewer); image captions refer to Bluei
  by name in the third person. On screen it still never speaks. Replaces the earlier
  "no name / never the narrator / *de Blue Fit beer*" rule. The edit-time caption tool now
  receives the post `type` so a video re-sync also comes out in Bluei's voice. Reason:
  client direction.
- `agents/prompts/generator.md` + `caption_*.md` — **video captions: Bluei gives one
  concrete piece of advice the viewer can act on today** (a specific, doable action, not
  a vague tip), on top of speaking in first person. Images unchanged (third person by
  name). Reason: client direction.

## 2026-07-13
- `agents/prompts/generator.md` — added a **"Vary the visual setting"** rule. The
  `recently covered` block now surfaces each past post's `scene`, and the generator
  must not default to water/ocean scenes ("Blue" ≠ ocean) — each post gets a distinct
  setting and the video must use a setting not seen recently (a repeat is rejected by
  the pipeline's `_enforce_scene_variety` guard). Reason: videos were repeating the
  same ocean-swimming scene every week because the diversification memory only tracked
  concepts (pillar/theme/value/hook), never the visual scene.
- `agents/prompts/generator.md` — the **hook** now weaves in one searchable Dutch
  Instagram keyword (e.g. "hydratatie", "natuurlijk bewegen"), tied to the post's
  pillar/theme/value, while staying a punchy curiosity-gap oneliner. Reason: improve
  Instagram discoverability ("SEO") — the burned-in on-screen text is searched/OCR'd,
  so the hook doubles as a search surface. Applies to all posts (image + video).
- `agents/prompts/generator.md` — the **caption** now uses the post's searchable Dutch
  keywords naturally in the prose and ends with a short discovery line (3–6 keywords,
  " · " separated). Reason: belt-and-suspenders Instagram SEO — the caption is the
  primary text Instagram search indexes, complementing the on-screen hook keyword.

## 2026-06-22
- `agents/prompts/learning_extract.md` — created. Gemini Flash prompt for the Phase-2
  learning loop: distills the last 14 days of edit instructions into durable brand
  `rules` (imperative, generalised, with confidence; merges duplicates). Reason: build
  the nightly rule-extraction loop.

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
