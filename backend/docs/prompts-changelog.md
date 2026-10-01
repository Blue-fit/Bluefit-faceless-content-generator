# Prompts changelog

## 2026-10-01 (c) - no medical claims, enforced in code
- `agents/prompts/researcher.md` + `agents/pipeline.py` - a researcher audit over 14
  live themes found one payoff claiming "je vermindert het risico op
  gezondheidsproblemen", and two evidence lines built on mortality findings ("een
  lagere kans op overlijden", "een forse daling van het sterfterisico"). The prompt
  already forbade clinical wording; it needed the mortality/risk case spelled out,
  and a gate. `_clinical_claims()` now blocks risk, mortality, treatment and
  diagnosis language in a theme's payoff AND evidence (the evidence becomes a
  caption line), and again in the generated caption. Organ words stay legal:
  "verlagen de hartslag, bloeddruk en stresshormonen" is a body doing something.
  Calibrated against 11 real lines from the audit, 0 mismatches. Re-audited over 16
  fresh themes: no vague actions, no missing doses, no medical claims.

## 2026-10-01 (b) - the caption has to be worth reading, and sound like us
- `agents/prompts/generator.md` - two additions to the caption, after the action
  landed but the back half stayed generic. (1) **The "why it works" line must earn
  its place**: it has to be a counter-intuitive fact, a reframe, or a comparison
  that shows the size of the effect - never the textbook fact everyone already has.
  The three live captions before this change ended on "blauw licht blokkeert dit
  natuurlijke proces", "je lichaam heeft urenlang niets gedronken" and "rekken
  warmt het lichaam op". Nobody saves a post for that. (2) **The caption must tie
  the action back to its pillar or Power-9 value**, in our words and woven into a
  sentence, never as a slogan or a label - it is what makes it a Blue Fit post
  rather than a wellness tip anyone could publish. Caption length 3-5 -> 4-6
  sentences to fit both without crowding out the action.
- `agents/prompts/researcher.md` - `evidence` must now carry the part a reader
  would NOT already know, with one more search if the source only confirms the
  obvious. Same lesson as the action: the generator cannot write a surprising line
  from an unsurprising brief.
- `agents/prompts/generator.md` - **the nine Power-9 values now carry one-line
  definitions.** They were listed by name only, so the model guessed: a live run
  wrote "Dit is de 80%-regel in de praktijk: kleine, bewuste keuzes", when hara
  hachi bu means stop eating at 80% full and nothing else. Values must be used for
  what they actually are.
- `agents/prompts/generator.md` - the value is written as a **Dutch idea, never its
  English name**: "de mensen direct om je heen", not "de ware kracht van 'Social
  circles'", which read like a brand deck leaked into the feed. Plus a hard size
  rule (4-6 sentences, under 900 characters) after captions ballooned to ten
  sentences once the back half had more to do, and "no em dashes".
- `agents/schemas.py` + `tools/generate_caption.py` - em dashes are stripped in code
  (`strip_em_dashes`), on both the weekly and the edit path. Typographic rules do
  not survive on prompt instruction alone: the model reaches for a dash whenever a
  clause runs on.
- `agents/prompts/caption_{question,hottake,observation}.md` - both rules repeated,
  so an edit-time caption rewrite holds the same bar.

## 2026-10-01 - a theme is a protocol, not a topic
- `agents/prompts/researcher.md` - rewritten around the job of finding **protocols**.
  A theme must now carry an `action`, a `dose`, a `payoff` and one line of
  `evidence`, and must pass: could a member do this today, without buying anything,
  and know tonight whether they did it? Search for the intervention and its dose
  ("hoeveel minuten wandelen na het eten"), not the subject ("waarom bewegen gezond
  is"). The vague register is banned by name - beweeg meer, wees bewust, neem rust -
  because those are the phrases the failing captions ended on. Payoffs may be
  physical ("je bloedsuiker piekt minder") but never clinical. Reason: three of the
  last five video captions gave the viewer nothing to do; see `docs/decisions/011`.
- `agents/prompts/generator.md` - new "Every post hands the viewer something to do"
  section. The video `beat` is now the action being PERFORMED by Bluey, not a
  metaphor for it. Caption order fixed for all 3 posts: pay off the hook in one
  sentence, then the action with its dose by sentence two, then the payoff, one line
  of why, and the comment prompt. At most one sentence of philosophy first. New
  `takeaway` field on every PostSpec.
- `agents/prompts/caption_{question,hottake,observation}.md` - the weak "give one
  concrete piece of advice" clause replaced by the same ordering rule, so an
  edit-time caption rewrite cannot regress to an explainer. The observation
  template's "don't instruct" rule relaxed to "don't lecture": the action is still
  there, offered rather than commanded. New examples in all three.

## 2026-09-24 (b) - the edit agent can see the conversation
- `tools/edit_post.py` `_CLASSIFY` - new "Reading the conversation" section, fed by
  the last 6 turns of the thread. Until now every message was classified alone, so
  an answer to the agent's own question ("de photo", after it offered "de foto, de
  tekst in beeld, of de caption?") read as a fresh vague request and earned the
  identical question back - a loop the client could not escape. The rules: an answer
  to your own question is merged with that question and acted on; never ask the same
  question twice, and if something is still missing ask about that part only and ask
  something narrower; after two clarifications in the thread, stop asking and act on
  the most reasonable reading; a bare "try again" repeats the client's last real
  instruction; typos still count as an answer when the context makes it obvious.
  Verified by replaying the client's real 2026-09-24 thread: all five turns that
  previously looped now act.

## 2026-09-24 - the reply names what was made
- `tools/edit_post.py` `_CLASSIFY` - new `change_note`: whenever the classifier sets
  `new_scene_prompt` it also writes a short noun phrase, in the client's language,
  describing what the NEW image or video shows ("Bluey samen met mensen op een
  terras"). It completes "ik heb een nieuwe foto gemaakt met ...", so it is lower
  case and describes the picture, not the instruction: a look-only change reads
  "dezelfde scene, maar lichter", never "een lichtere foto". Null when the media is
  not changing. Reason: the reply said "ik heb een nieuwe foto gemaakt" without
  saying what of, so the client had to open the post to find out whether the edit
  was what they asked for.

## 2026-09-22 (b) - edit fixes from a production audit
- `tools/edit_post.py` `_CLASSIFY` - asking the POST ITSELF to say something now
  rewrites the on-screen text: "vertel iets in de post zelf over X", "zeg iets in de
  tekst over X" set `new_hook` (and `new_scene_prompt` too when the same message also
  asks for a different scene). Seen live: the client asked the post to talk about
  community and got a new photo and caption while the on-screen text stayed put.
  Naming a TOPIC is also declared concrete, so "zeg iets over mobiliteit" no longer
  goes to clarify. "Laat zien in de foto" stays a scene change, not a text change.
- `tools/edit_post.py` `_CLASSIFY` - the clarification is now a REPLY, not a menu:
  it first answers or acknowledges what the client said, then asks what to change and
  names the options, in their language and naming THIS post's medium (foto vs video).
  The fallback question was hardcoded Dutch and would have reached English speakers;
  it is now per-language in `_PHRASES`. No dashes in any client-facing copy.
- `tools/edit_post.py` `_CLASSIFY` - new "language": the classifier reports the ISO code
  of the request so every reply is written in the language the client is using. The
  client writes Dutch and was being answered in English.
- `tools/edit_post.py` `_CLASSIFY` - `clarify` also covers messages that are NOT change
  requests: praise ("Deze is nu erg mooi en heb ik gebruikt!"), bare commands with no
  object ("doe het", "fix het"), and complaints ("er verandert niks in de post"). All
  six produced a failure reply in production; the system must never edit a post on the
  strength of a compliment.
- `tools/edit_post.py` `_CLASSIFY` - **new `clarify`: ask rather than guess.** A vague
  request ("dit kan echt beter", "niet goed") or a QUESTION ("wat is er verkeerd
  gegaan?") now returns a short question in the client's language naming the concrete
  options, instead of a guessed edit. No version is created and nothing is rendered -
  only the classify call is spent. Reason: production showed "wat is er verkeerd
  gegaan?" silently rewriting the caption and "dit kan echt beter" regenerating the
  picture. A request naming something concrete is explicitly NOT vague, so the system
  does not start nagging on clear instructions.
- `tools/edit_post.py` `_CLASSIFY` - **`target` became `targets`, a list.** An audit of
  all 39 real client edits showed the top complaint's cause: the client asks for the
  media AND the caption in one sentence and only half was ever applied. Examples from
  production: "verwijs hierin meer naar de blue zones, ook in de caption" (caption
  untouched; asked again 5 minutes later), "geen kettle bell ... en zeg iets in de tekst
  over mobiliteit" (followed by "wat is er verkeerd gegaan?"), "maak een helemaal nieuwe
  post hierover en dan met een nieuwe caption", "vooral de tekst in de foto en de tekst
  in de caption". The classifier is now told to return both and never drop half a
  request; the asset is applied first so the caption reflects the new scene/hook.
- `agents/prompts/generator.md` - the caption must be **written in Dutch**. It was only
  implied ("Dutch keywords"), and a caption shipped in Spanish: "Waarom opeens spaans
  en niet nederlands".

## 2026-09-22
- **New: `tools/search_demand.py`** mines Google autocomplete (national NL, free, no
  key) for the PROBLEMS the audience types, in their own words. Seeds are everyday
  Dutch ("altijd moe", "geen tijd om te sporten") and deliberately NOT derived from
  the pillars/values — the brand lens is applied afterwards. City seeds were dropped
  ("fitness lent nijmegen" returns 1 suggestion and caps reach). Results are ranked
  per topic and interleaved so no single topic floods the list, with medical,
  competitor and price queries filtered out. Fail-soft: no data = the old behaviour.
- `agents/prompts/researcher.md` — now works problem → pillar/value → **solution**:
  pick a real searched problem, match the value that speaks to it, build the theme
  around the solution Bluey can act out, and record the query in `search_query`
  (new optional `TrendTheme.search_query`; additive, no SCHEMA_VERSION bump).
  `google_search` becomes evidence-finding rather than topic-finding.
- `agents/prompts/generator.md` — the hook/caption keyword must be taken FROM the
  mined queries rather than invented. Reason: client wants posts built on what the
  audience actually searches, to maximise views.

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
  `caption_observation.md` — **the mascot is named Bluey.** Video captions are written in
  Bluey's own voice (first person, talking to the viewer); image captions refer to Bluey
  by name in the third person. On screen it still never speaks. Replaces the earlier
  "no name / never the narrator / *de Blue Fit beer*" rule. The edit-time caption tool now
  receives the post `type` so a video re-sync also comes out in Bluey's voice. Reason:
  client direction.
- `agents/prompts/generator.md` + `caption_*.md` — **video captions: Bluey gives one
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
