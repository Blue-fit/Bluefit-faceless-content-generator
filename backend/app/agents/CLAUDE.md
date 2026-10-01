# Agents

Two agents composed into an ADK `SequentialAgent`:

1. **Researcher** (Gemini Flash + `google_search`) — produces a `TrendBrief`
2. **Generator** (Gemini Pro) — produces 3 post specs using brief + brand
   RAG + active rules

The pipeline is wired in `pipeline.py`. Schemas live in `schemas.py`.

## Prompt management

System prompts live in `prompts/*.md`. Edit them as Markdown files, not as
Python strings. Three reasons:

1. Git diffs are readable
2. Claude Code can edit them as files, not surgery on triple-quoted strings
3. The `reasoning_blob` records `prompt_version` as the file's git SHA —
   this is the audit trail for "which prompt produced this post"

After editing any prompt, add a line to `docs/prompts-changelog.md` with
date, file changed, and reason.

## Schema rules

- `TrendBrief` and `PostSpec` in `schemas.py` are versioned. A breaking
  change requires a schema version bump.
- The researcher MUST return a valid `TrendBrief`. Validation failures
  are bugs in the prompt, not bugs in the schema. `pipeline._research`
  validates it and re-prompts once on a malformed reply; if it is still
  invalid the raw text is passed through with a loud
  `research.brief_unvalidated` warning rather than failing the week (no
  posts that week would be worse than a loose brief). The whole step is
  `@meter("research")`, priced from the agent's real token counts.
- The generator MUST declare `references_used` for each post — these
  become the `reasoning_blob`. Empty references means brand alignment
  is theater.
- **A theme is a protocol, not a topic.** `TrendTheme` carries a required
  `action`, `dose`, `payoff` and `evidence`; every `PostSpec` carries a
  required `takeaway`. Without them the researcher returns explainers and
  the captions tell the viewer why movement matters while handing them
  nothing to do — see `docs/decisions/011`. Two pure gates enforce it:
  `_theme_action_violations` (re-asks the researcher once inside
  `_research`, then drops what won't mend) and `_post_action_violations`
  (shares the single correction call with `_enforce_value_rules` rather
  than buying a third generator retry). Both are fail-soft: a thin brief
  still beats no posts.
- **Sources are verified, not trusted.** `_resolve_sources` fetches every
  `source_url` and nulls the ones that 404/410 or cannot be reached, so
  `TrendTheme.source_url` is optional by the time anything reads it. Both
  expired grounding redirects and URLs the researcher invented were being
  stored as provenance.

## Tool dispatch boundary

The generator declares **intent**, not action. It produces post
specifications with prompts. The pipeline then dispatches the actual
tool calls. This keeps the `@meter` on the boundary between intent and
expense.

Do not let the generator call `generate_image`, `generate_video`, etc.,
directly. Those are dispatched by the pipeline after the generator
returns.

## Caption templates

Three engagement templates: question, hot-take, observation. The generator
selects one per post based on content type. Templates live in
`prompts/caption_*.md`. The selected template is recorded in
`reasoning_blob.engagement_template`.

## Cold start

On a new deployment, neither a strategic brief nor weekly brief exists yet.
The pipeline must handle this:

- If no strategic brief: researcher proceeds without it
- If no rules: generator proceeds with brand-only context
- If brand chunks not yet ingested: this is a deployment error, not a
  runtime case — fail loud
