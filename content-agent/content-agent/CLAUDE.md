# Content Agent — Claude Code Context

## What this is

Per-client Instagram content generation agent. One Python service per client
deployment. Every Friday 09:00 UTC, generates 2 images + 1 short video with
captions, surfaces them in a chat UI for review, downloads finals for manual
posting. Single-tenant per deployment.

**Read order before any task:**
1. `PRD.md` — product requirements (what to build)
2. This file — operational principles (how to build)
3. `docs/architecture.md` — technical reference
4. `docs/decisions/` — why decisions were made
5. Directory-level `CLAUDE.md` files when working in those directories

## Tech stack — do not propose alternatives without explicit approval

- Python 3.12, async throughout
- Google ADK for agent orchestration
- `google-genai` for ALL model calls (Gemini Pro, Flash, Nano Banana, Veo 3.1 Fast)
- FastAPI + uvicorn (single process)
- APScheduler in-process with persistent jobstore
- Self-hosted Postgres 16 + pgvector (NOT Supabase — see `docs/decisions/003`)
- Cloudflare R2 via boto3
- Resend for email
- structlog for logging
- pydantic + pydantic-settings for config and schemas
- uv for dependency management

## Architectural principles — do not violate

1. **Per-client isolation.** No `client_id` columns anywhere. Each deployment
   is single-tenant by design.
2. **All paid tool calls go through `@meter`.** No exceptions. See `app/meter/`.
3. **Posts are versioned, not mutated.** Edits always insert a new
   `post_versions` row with a parent pointer.
4. **`reasoning_blob` is structured JSONB, written at generation time.**
   Never rely on post-hoc LLM narration of "why."
5. **System prompts live in `app/agents/prompts/*.md`.** Version controlled
   as files, not as strings in code.
6. **SQL queries live in `app/db/repositories/`.** Don't scatter them across
   routes or tools.
7. **No third-party model abstraction layers.** Direct `google-genai` only.
   See `docs/decisions/007`.

## Code conventions

- Async functions everywhere. No sync DB calls. No `time.sleep`.
- Type hints on every function. `mypy --strict` must pass.
- Pydantic models for all structured data crossing module boundaries.
- Errors: raise specific exceptions, never bare `except`.
- Logging: `structlog` with bound context. No `print()`.
- Imports: absolute, from `app.module.thing`. Never relative beyond one level.
- One concern per file in `routes/` and `repositories/`. Don't grow files
  beyond a single concern.
- Tests: pytest + pytest-asyncio. Unit tests mock at the boundary; integration
  tests use real Postgres in Docker.

## When making changes

- Schema changes require a new migration in `app/db/migrations/`.
  Never edit an existing migration. Forward-only.
- New tools require `@meter` wrapping. See `app/meter/CLAUDE.md`.
- New routes go in `app/routes/{concern}.py`. Don't add to existing files
  unless the concern matches.
- Prompt edits: change the `.md` file, then add a line to
  `docs/prompts-changelog.md` with date and reason.
- When adding a new top-level concern, ask before creating it. Prefer
  extending existing directories.

## Never do without explicit approval

- Switch model providers (we are Google-only — see `docs/decisions/002`)
- Add `client_id` to any table (multi-tenancy is out of scope)
- Bypass `@meter` on a paid tool call
- Use blocking I/O in async functions
- Commit secrets or hard-code API keys
- Add a new external service dependency (currently: Google, R2, Resend — that's it)
- Add a third-party "skills" or model-abstraction package (see `docs/decisions/007`)

## Commands

- Install: `uv sync`
- Migrate: `uv run python -m app.db.migrate`
- Dev server: `uv run uvicorn app.main:app --reload`
- Tests: `uv run pytest`
- Lint: `uv run ruff check . && uv run mypy app/`
- Trigger weekly manually: `uv run python scripts/trigger_weekly.py`

## How to ask for clarification

If a task seems to require a tradeoff between principles, ask before
deciding. If a requirement in `PRD.md` conflicts with a principle here,
surface the conflict — don't silently resolve it. Architecture decisions
do not belong inside a commit.

## Working style

- Build one phase at a time per `PRD.md` §8. Don't build Phase 2 features
  inside Phase 1.
- Prefer boring solutions. Every new dependency is a future upgrade
  obligation across N client deployments.
- When in doubt about scope, write less code, not more.
- When something feels like it needs an abstraction, write the concrete
  version first. Abstract on the second use, not the first.
