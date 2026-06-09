# Architecture — Content Agent

Technical reference for this system. Read PRD.md for requirements, CLAUDE.md for conventions.

---

## 1. System overview

A single FastAPI process running on one VPS per client. The process contains:

- **ADK Runner** — executes agent pipelines and edit sessions
- **APScheduler** — fires the weekly generation cron, monthly research cron, nightly rule extraction
- **asyncpg pool** — all DB I/O goes through a single shared pool
- **Cloudflare R2** (remote) — generated asset storage via boto3

There is no separate worker process. The scheduler and the HTTP server share the same event loop via lifespan startup.

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI + uvicorn (single process)                      │
│                                                          │
│  ┌────────────┐  ┌────────────────────────────────────┐  │
│  │ APScheduler │  │ ADK Runner                         │  │
│  │  weekly    │  │  SequentialAgent (weekly pipeline)  │  │
│  │  monthly   │  │  LlmAgent        (edit sessions)    │  │
│  │  nightly   │  │  PostgresSessionService              │  │
│  └─────┬──────┘  └────────────────┬───────────────────┘  │
│        │                          │                        │
│        └──────────┬───────────────┘                        │
│                   │                                        │
│           asyncpg pool                                     │
└───────────────────┼────────────────────────────────────────┘
                    │
          ┌─────────┴──────────┐
          │   Postgres 16       │
          │   + pgvector        │
          └─────────────────────┘
```

---

## 2. Database schema

### 2.1 Content tables

**`weeks`** — one row per Friday generation run
```
id           UUID        PK, gen_random_uuid()
week_start   DATE        UNIQUE — prevents double-generation
trend_brief  JSONB       researcher agent's TrendBrief output
status       TEXT        CHECK IN ('pending', 'ready', 'failed')
created_at   TIMESTAMPTZ DEFAULT NOW()
```

**`posts`** — one row per post, stable across versions
```
id                 UUID  PK
week_id            UUID  FK → weeks.id ON DELETE CASCADE
type               TEXT  CHECK IN ('image', 'video')
pillar             TEXT  brand pillar (Keep Moving, Community, etc.)
current_version_id UUID  FK → post_versions.id DEFERRABLE INITIALLY DEFERRED
created_at         TIMESTAMPTZ DEFAULT NOW()
```

**`post_versions`** — immutable. never updated after insert
```
id                  UUID  PK
post_id             UUID  FK → posts.id ON DELETE CASCADE
parent_version_id   UUID  FK → post_versions.id (null on v1)
version_number      INT   NOT NULL
asset_url           TEXT  R2 object URL
caption             TEXT
edit_instruction    TEXT  null for generated versions
reasoning_blob      JSONB structured provenance (see §6)
reasoning_embedding VECTOR(768) for "make it like week N" lookups
created_at          TIMESTAMPTZ DEFAULT NOW()
```

> **Circular FK note:** `posts.current_version_id` and `post_versions.post_id` are mutually dependent.
> Resolved by declaring `current_version_id` as `DEFERRABLE INITIALLY DEFERRED`.
> Insert order: begin transaction → insert post (current_version_id = NULL) → insert post_version → update post SET current_version_id → commit.

### 2.2 Operational tables

**`usage`** — append-only. ground truth for spend. never updated
```
id          UUID         PK
model       TEXT         e.g. gemini-2.0-pro, veo-3-fast
call_type   TEXT         CHECK IN ('image','video','caption','edit','research','explain','embedding')
cost_eur    NUMERIC(10,6)
trigger     TEXT         CHECK IN ('cron','edit','explain','ingest')
post_id     UUID         nullable (research calls have no post)
created_at  TIMESTAMPTZ  DEFAULT NOW()
```

Spend bar query:
```sql
SELECT SUM(cost_eur) FROM usage
WHERE created_at >= date_trunc('month', NOW());
```

**`messages`** — the persistent backing store for ADK sessions (see §4.2)
```
id          UUID  PK
post_id     UUID  FK → posts.id ON DELETE CASCADE
role        TEXT  CHECK IN ('user', 'model')
content     TEXT
created_at  TIMESTAMPTZ DEFAULT NOW()
```

### 2.3 Context tables

**`rules`** — extracted user preferences, injected into every generation run
```
id             UUID  PK
text           TEXT
confidence     REAL  0.0–1.0
status         TEXT  CHECK IN ('active', 'user_removed')
source_week_id UUID  FK → weeks.id
created_at     TIMESTAMPTZ DEFAULT NOW()
updated_at     TIMESTAMPTZ DEFAULT NOW()
```

**`brand_chunks`** — chunked brand document for generation-time RAG
```
id          UUID  PK
content     TEXT
embedding   VECTOR(768)
source      TEXT  section name from the brand document
created_at  TIMESTAMPTZ DEFAULT NOW()
```

**`strategic_briefs`** — monthly Gemini Deep Research output
```
id          UUID  PK
month       DATE  UNIQUE (first day of the month)
content     TEXT  full Deep Research output as plain text
created_at  TIMESTAMPTZ DEFAULT NOW()
```

### 2.4 Indexes

```sql
-- brand RAG retrieval (cosine)
CREATE INDEX ON brand_chunks USING hnsw (embedding vector_cosine_ops);

-- "make it like week N" lookups (cosine)
CREATE INDEX ON post_versions USING hnsw (reasoning_embedding vector_cosine_ops);

-- chat history load by post
CREATE INDEX ON messages (post_id, created_at);

-- spend bar
CREATE INDEX ON usage (created_at);
```

---

## 3. ADK integration

### 3.1 How ADK concepts map to this system

| ADK concept | This system |
|---|---|
| `Runner` | One shared instance in `app/agents/pipeline.py`, created at startup |
| `SessionService` | Custom `PostgresSessionService` backed by `messages` table |
| `SequentialAgent` | Weekly pipeline: Researcher → Generator |
| `LlmAgent` | One per role (researcher, generator, editor) |
| `session.state` | Carries context between pipeline stages (brief, rules, week_id) |
| `before_tool_callback` | `@meter` gate — checks spend before executing |
| `after_tool_callback` | `@meter` writer — writes to `usage` after execution |
| `ToolConfirmation` | Red-state spend gate in `app/meter/gate.py` |
| Built-in `google_search` | Registered on the researcher agent |

### 3.2 Session scoping

Each post has exactly one ADK session. The session ID is the post UUID:

```
session_id = str(post.id)
user_id    = "client"          # single-tenant, one user per deployment
app_name   = "content-agent"
```

The weekly pipeline does **not** use a persistent session — it runs start-to-finish in memory and writes results to the DB. Persistent sessions are only used for the edit/chat interface.

### 3.3 PostgresSessionService

ADK's `BaseSessionService` interface is implemented by `app/db/session_service.py`. It reads and writes the `messages` table.

The session service stores only `role=user` and `role=model` turns — the human-visible conversation. Internal tool call/result events are not persisted; they are reconstructed by the ADK runtime within a turn.

On `get_session`, the service loads all messages for the given `post_id` ordered by `created_at` and reconstructs them as ADK `Content` objects. On `append_event`, it writes new user and model turns to the `messages` table.

This gives:
- One source of truth for chat history (Postgres)
- Full conversation replay across process restarts
- No sync problem between two stores

### 3.4 Runner setup

```python
runner = Runner(
    agent=pipeline_agent,       # SequentialAgent for weekly runs
    app_name="content-agent",
    session_service=PostgresSessionService(pool),
)
```

The editor agent uses the same runner instance but a different root agent registered for edit sessions.

---

## 4. Agents

### 4.1 Researcher (weekly pipeline)

- **Model:** Gemini Flash
- **Tools:** `google_search` (built-in)
- **System prompt:** `app/agents/prompts/researcher.md`
- **Output:** `TrendBrief` Pydantic model written to `session.state["trend_brief"]`
- **Context injected via session.state:**
  - Latest `strategic_briefs.content` (if exists)
  - `week_start` date

The researcher runs first in the `SequentialAgent`. Its output in `session.state` is automatically visible to the generator.

### 4.2 Generator (weekly pipeline)

- **Model:** Gemini Pro
- **Tools:** `brand_rag`, `memory_search` (read-only — no generation tools)
- **System prompt:** `app/agents/prompts/generator.md`
- **Output:** list of 3 `PostSpec` Pydantic models written to `session.state["post_specs"]`
- **Context injected via session.state:**
  - `trend_brief` (from researcher)
  - Active rules fetched from `rules` table
  - `week_id` (pre-inserted pending weeks row)

The generator declares **intent only** — it returns post specifications with image/video prompts and selects caption templates. It does not call generation tools directly. The pipeline dispatches those after the agent returns.

### 4.3 Editor (chat sessions)

- **Model:** Gemini Flash
- **Tools:** `brand_rag`, `edit_post`, `generate_caption`, `explain`
- **System prompt:** derived from current post context + active rules
- **Session:** persistent, backed by `PostgresSessionService`

The editor agent handles all user interactions: edit requests, explain requests, rule removals, version browsing.

### 4.4 Pipeline flow (weekly)

```
APScheduler fires Friday 09:00 UTC
        │
        ▼
pipeline.py: pre-flight
  - INSERT weeks row (status=pending, week_start=this_monday)
  - Load latest strategic_brief
  - Load active rules
  - Seed session.state
        │
        ▼
SequentialAgent runs (ephemeral in-memory session)
  [Researcher] → TrendBrief → session.state["trend_brief"]
  [Generator]  → 3 PostSpecs → session.state["post_specs"]
        │
        ▼
pipeline.py: dispatch (for each PostSpec)
  - INSERT posts row (current_version_id deferred)
  - Call generate_image × 2 OR generate_video × 1  (metered)
  - Call generate_caption × 3                       (metered)
  - Upload assets to R2
  - Embed reasoning_blob via text-embedding-005      (metered)
  - INSERT post_versions row
  - UPDATE posts.current_version_id
        │
        ▼
pipeline.py: post-flight
  - UPDATE weeks SET status='ready'
  - Run rule extraction job (see §7.3)
  - Send digest email via Resend
```

On any unrecoverable error: UPDATE weeks SET status='failed', send operator alert.

---

## 5. Tools

All tools in `app/tools/`. Each paid tool is wrapped with `@meter`.

| Tool | Model | Call type | Trigger |
|---|---|---|---|
| `generate_image` | Nano Banana | image | cron, edit |
| `generate_video` | Veo 3.1 Fast | video | cron, edit |
| `generate_caption` | Gemini Flash | caption | cron, edit |
| `edit_post` | Nano Banana / Flash | edit | edit |
| `explain` | Gemini Flash | explain | explain |
| `brand_rag` | text-embedding-005 | embedding | cron, edit |
| `memory_search` | text-embedding-005 | embedding | cron, edit |

`brand_rag` and `memory_search` are read-only DB tools — they query pgvector and return text chunks. They do not write to `usage` (embedding calls are tracked when the vector is first inserted, not on retrieval).

### 5.1 brand_rag

Embeds the query, runs cosine similarity against `brand_chunks.embedding`, returns the top-k chunks. Used by both the generator (brand alignment) and the editor (edit context).

### 5.2 memory_search

Embeds the query against `post_versions.reasoning_embedding`. Used to resolve references like "make this like week 3." Returns the matching post version's `reasoning_blob`.

### 5.3 edit_post

Classifies intent (tweak / regenerate / rewrite), dispatches the appropriate generation tool, inserts a new `post_versions` row, and updates `posts.current_version_id`. Enforces the version soft-warn at v5 and hard-block at v10.

### 5.4 explain

Reads `post_versions.reasoning_blob` for the given version, passes it to Gemini Flash with the `prompts/explain_render.md` template, returns prose. Cached for 24 hours per `post_version_id` in `session.state`.

---

## 6. reasoning_blob schema

Written at generation time. Never computed after the fact.

```json
{
  "prompt_version": "<git SHA of the prompt .md file>",
  "model_versions": {
    "generator": "gemini-2.0-pro",
    "image": "nano-banana-...",
    "caption": "gemini-flash-..."
  },
  "week_brief_id": "<uuid>",
  "brief_entries_used": ["entry_1_title", ...],
  "strategic_brief_id": "<uuid>",
  "strategic_themes_used": ["theme_a", ...],
  "brand_chunk_ids": ["<uuid>", ...],
  "rules_applied": [
    {"rule_id": "<uuid>", "text": "...", "confidence": 0.87}
  ],
  "engagement_template": "question | hot_take | observation"
}
```

---

## 7. Background jobs (APScheduler)

All jobs use the APScheduler `AsyncIOScheduler` with a Postgres jobstore for misfire recovery.

### 7.1 Weekly pipeline — Fridays 09:00 UTC

See §4.4. Misfire grace: 1 hour. On misfire: run once on next startup within the grace window, then skip.

### 7.2 Monthly strategic brief — 1st of month, 02:00 UTC

Calls the Gemini Interactions API (Deep Research). Stores full output in `strategic_briefs`. On failure: operator email, do not retry (next month's run will catch up).

### 7.3 Nightly rule extraction — 02:30 UTC

Reads all `messages` and `post_versions.edit_instruction` from the past 14 days. Calls Gemini Flash to identify durable user preferences. Upserts `rules` rows — increments confidence on match, inserts new rows for new preferences. Does not remove rules (only user action via chat transitions to `user_removed`).

---

## 8. Cost governance

### 8.1 Metering callbacks

`app/meter/callbacks.py` registers two ADK callbacks on every paid tool:

- `before_tool_callback` — calls `gate.py` to check current month spend against cap. Returns `ToolConfirmation` object if red state. No I/O; gate uses current-spend value passed from the runner context.
- `after_tool_callback` — inserts one row into `usage` via `repositories/usage.py`.

### 8.2 Gate states

| State | Spend | Behavior |
|---|---|---|
| green | 0–79% of cap | Proceed silently |
| amber | 80–99% | Proceed + surface warning in agent message + rate-limited email |
| red | 100%+ | `ToolConfirmation` pauses execution, posts prompt to UI, waits for user approval |

`hard_cap_eur` in `brand/profile.yaml` (optional): if set, red state returns a hard refusal instead of a confirmation prompt.

### 8.3 Pricing source of truth

`app/meter/pricing.py` — one constant per model per call type. All cost calculations reference this module. No prices anywhere else in the codebase.

---

## 9. Authentication

Single bearer token per deployment. Set in `brand/profile.yaml`, loaded via `pydantic-settings`. The FastAPI `auth.py` dependency validates it on every request. No session management. No user accounts.

---

## 10. Storage

Assets (images, video) are uploaded to Cloudflare R2 immediately after generation. `asset_url` in `post_versions` stores the public object URL. R2 bucket is EU-jurisdiction only (Hetzner HEL1 + R2 EU).

Download endpoint: `GET /posts/{post_id}/versions/{version_id}/download` — returns a signed R2 URL with a short TTL.

---

## 11. Observability

- **Structured logs:** `structlog` with bound context (week_id, post_id, trigger). Written to journald.
- **ADK traces:** OpenTelemetry traces emitted by ADK Runner. Collected locally; no external sink in v1.
- **Spend:** queried live from `usage` table. No cache — always reflects real state.
- **Health:** `GET /health` returns 200 + DB connectivity check. Checked by external monitor.

---

## 12. Module map

```
app/
  agents/
    pipeline.py         SequentialAgent wiring + pre/post-flight dispatch
    researcher.py       researcher LlmAgent definition
    generator.py        generator LlmAgent definition
    schemas.py          TrendBrief, PostSpec Pydantic models
    prompts/            system prompt .md files (one per agent + caption templates)
  db/
    connection.py       asyncpg pool init and teardown
    session_service.py  PostgresSessionService (BaseSessionService implementation)
    migrate.py          forward-only migration runner
    migrations/         NNN_description.sql files
    models.py           Pydantic models mirroring DB rows
    repositories/       one file per table — all SQL lives here
  meter/
    callbacks.py        ADK before/after tool callbacks
    gate.py             green/amber/red state logic (pure functions)
    pricing.py          unit cost constants
  tools/                one file per tool, all paid tools wrapped with @meter
  jobs/
    weekly.py           weekly generation job
    monthly.py          strategic brief job
    nightly.py          rule extraction job
    scheduler.py        APScheduler setup and job registration
  learning/
    extract.py          Flash-based preference extraction
    apply.py            rule upsert logic
  routes/
    chat.py             POST /chat/{post_id}, GET /chat/{post_id}/history
    posts.py            GET/PATCH /posts, GET /posts/{id}/versions
    usage.py            GET /usage/current-month
    health.py           GET /health
  notifications/
    email.py            Resend wrappers (digest, spend alert, failure alert)
  storage/
    r2.py               R2 upload + signed URL generation
  auth.py               bearer token FastAPI dependency
  config.py             pydantic-settings config from env
  main.py               FastAPI app + lifespan (pool, scheduler, runner startup)
```
