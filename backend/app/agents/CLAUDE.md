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
  are bugs in the prompt, not bugs in the schema.
- The generator MUST declare `references_used` for each post — these
  become the `reasoning_blob`. Empty references means brand alignment
  is theater.

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
