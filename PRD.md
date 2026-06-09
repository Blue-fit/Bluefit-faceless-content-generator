# Product Requirements Document — Content Agent

**Status:** Draft, pre-build
**Audience:** Claude Code (primary builder), operator (you)
**Read order:** This document first, then `CLAUDE.md`, then `docs/architecture.md`.

---

## 1. What we are building

A per-client Instagram content generation agent. One Python service per client deployment. The agent:

- Generates 3 brand-aligned posts per week (2 images, 1 short video) every Friday at 09:00 UTC
- Surfaces those posts in a conversational chat UI for human review
- Accepts edit requests in natural language and produces new versions
- Learns durable preferences from edits and applies them to future generations
- Lets the client download finalized assets for manual posting to Instagram
- Operates within a configurable monthly spend cap

Publication is manual by design. The system does not post to Instagram on the client's behalf.

## 2. Who this is for

The system is built **once as a template** and **deployed per client** to a dedicated VPS. Each deployment serves exactly one client.

- **Operator:** the person maintaining the deployment (you). Has SSH access, owns the secrets, responds to incidents.
- **End user:** the client. Has access to one URL (chat UI), reviews and downloads assets, requests edits.
- **Audience the content is for:** the client's Instagram followers. The agent never talks to them directly.

## 3. KPIs
### 1. Content Output Deliverables
The agent must consistently produce brand-aligned assets without manual intervention, following these specific constraints:
Weekly Volume: Auto-generation of exactly three posts per week, which include 1 video and 2 images
Video Specifications: All generated video content must be between 10 and 30 seconds in duration
Engagement-Driven Captions: Every visual asset must include a caption tailored to spark conversations in the comment section.
Brand Alignment: Content must strictly adhere to the Blue Fit Ideology and brand values as defined in the post-kickoff requirements document.

### 2. System Functionality & User Interface
The user interface (UI) must facilitate seamless review and refinement of pre-generated content:
Conversational Chat Interface: A dedicated UI allowing users to discuss and review posts in a natural, conversational manner.
Weekly Chat Window: Each week and each post will have a unique chat thread to prevent operational complexity and to maintain clear historical records.
Collaborative Editing: Users must be able to request specific edits to the visuals (videos/images) and the text (captions) directly through the chat.
Asset Accessibility: Users must be able to access/download finalized content for manual posting to social media platforms.
Strategic Transparency: The agent must be able to explain the logic and research behind why a specific post was created.

### 3. Agent Intelligence & Feedback Loops
The agent’s value is defined by its ability to learn from user interactions:
Memory Retention: The agent must keep track of all historical chats, allowing users to reference past styles, e.g. ‘make this like week two’
Continuous Improvement: The agent must demonstrate the ability to apply user feedback to future posts. For example, if a user specifies a preference for "ocean blue" over "navy blue," the agent must remember and implement this for all subsequent content.

### 4. Operational Controls
To ensure reliability and budget predictability, the following operational standards apply:
24/7 Availability: The interface and agent must be operational and accessible at all times for user edits.
Predictive Usage Notifications: The system must proactively notify users if their current editing activity is about to exceed the pre-defined monthly budget limit.
Internal Prompt Support: Major structural changes that would apply to each subsequent post (e.g. increasing post volume) are managed via manual internal prompt changes by the developer

## 4. Functional requirements

### 4.1 Weekly generation pipeline

Every Friday at 09:00 UTC, the system must:

1. Run the researcher agent (Gemini Flash with `google_search` tool) to produce a structured `TrendBrief`. The brief is grounded in the latest strategic brief if one exists.
2. Run the generator agent (Gemini Pro) using the weekly brief, the strategic brief, brand RAG context, and active rules. Generator produces 3 post specifications with prompts and captions.
3. Dispatch generation tools: Nano Banana for 2 images, Veo 3.1 Fast for 1 video (5–8s, 720p, audio optional), Gemini Flash for 3 captions (using question/hot-take/observation templates).
4. Upload assets to Cloudflare R2.
5. Insert one `weeks` row, three `posts` rows, three `post_versions` rows (each with a `reasoning_blob`).
6. Run the weekly rule extraction job over the past 14 days of chat messages and edit instructions.
7. Send a digest email via Resend with a link to the new week's chat thread.

### 4.2 Monthly strategic research

On the 1st of every month at 02:00 UTC, run a Gemini Deep Research job via the Interactions API. Store the result in `strategic_briefs`. The latest brief is always referenced by the weekly researcher.

### 4.3 Chat interface

The chat UI must:

- Present one thread per week, with three nested post discussions per thread
- Show each post's current version with a download button
- Show a "version N of M" indicator with a dropdown history
- Accept free-text edit requests scoped to a specific post
- Show a spend bar at the top, reading from the `usage` table, with green/amber/red states
- Show a confirmation prompt when the agent would exceed the spend cap
- Allow the user to ask "why did you make this post?" and receive a rendered explanation

### 4.4 Edit subsystem

When the user requests an edit, the agent must:

1. Classify the intent: tweak, regenerate, or rewrite
2. Dispatch the appropriate tool:
   - **Tweak (image):** Nano Banana edit-in-place using previous image as reference
   - **Tweak (video):** Veo 3.1 image-to-video using previous video's first frame
   - **Tweak (caption):** Flash rewrite inline
   - **Regenerate:** same prompt, new seed
   - **Rewrite:** generator produces new prompt, then dispatches
3. Insert a new `post_versions` row with `parent_version_id` and `edit_instruction`
4. Update `posts.current_version_id` pointer
5. Soft-warn the user at version 5; hard-block at version 10 unless manually overridden

### 4.5 Learning loop

A weekly Flash extraction job must:

1. Read `messages` and `post_versions.edit_instruction` from the past 14 days
2. Identify durable user preferences with confidence and provenance
3. Create new `rules` rows or increment confidence on matching existing rules
4. Active rules are injected into the generator's context on every subsequent run

Users can disable rules through chat ("stop preferring warm tones"), which transitions them to `user_removed` status while preserving the audit trail.

### 4.6 Strategic transparency

Every post version must store a structured `reasoning_blob` JSONB at write time, recording:

- Weekly brief ID and which entries were used
- Strategic brief ID and which themes were referenced
- Brand chunk IDs used in RAG retrieval
- Rules applied and their confidence
- Engagement template selected
- Model versions used
- Prompt version (git SHA of the prompt file)

When the user clicks "explain," a Flash render call turns the blob into prose. The rendered output is cached for 24 hours per `post_version_id`.

### 4.7 Cost governance

Every paid tool call must route through `app/meter/`. Behavior:

- **Green (0–79% of monthly cap):** silent, proceed
- **Amber (80–99%):** surface warning in user-facing message, send alert email (rate-limited)
- **Red (100%+):** pause via ADK `ToolConfirmation`, post confirmation prompt in chat, wait for user approval

The cap is soft by default — the user can confirm-through. A `hard_cap_eur` option in `brand/profile.yaml` enables an absolute ceiling.

`app/meter/pricing.py` is the single source of truth for unit costs. When prices change, update one file.

### 4.8 Notifications

| Trigger | Channel | Recipient |
|---|---|---|
| Weekly cron complete | Email (Resend) | User |
| Spend amber/red state crossed | Email | User |
| Cron failure | Email | Operator |
| Generation failure after 3 retries | Email | Operator |

### 4.9 Database Schema
Content Databases:

Weeks - Stores data from each week of posts:
─────────────────────────────────────────────
id           UUID        — unique identifier for the row
week_start   DATE        — the Monday that week begins (unique — prevents double generation)
trend_brief  JSONB       — the researcher agent's structured weekly brief
status       TEXT        — where the week is in the pipeline (pending, ready, failed)
created_at   TIMESTAMPTZ — when the row was created

Posts - Stores data from each post:
─────────────────────────────────────────────
id                 UUID        — unique identifier for the row
week_id            UUID        — which week this post belongs to (FK → weeks.id)
type               TEXT        — image or video
pillar             TEXT        — which brand pillar (Keep Moving, Community, etc.)
current_version_id UUID        — pointer to the live version (FK → post_versions.id)
created_at         TIMESTAMPTZ — when the row was created

Post_versions - Stores data from each post version:
─────────────────────────────────────────────
id                   UUID        — unique identifier for the row
post_id              UUID        — which post this version belongs to (FK → posts.id)
parent_version_id  UUID        — which version this was edited from (null for v1)
version_number       INT         — 1, 2, 3... increments with each edit
asset_url            TEXT        — link to the image or video stored in R2
caption              TEXT        — the Instagram caption for this version
edit_instruction     TEXT        — what the user asked for (null for generated versions)
reasoning_blob       JSONB       — why this was made (brief IDs, brand chunks, rules used)
reasoning_embedding  VECTOR(768) — vectorised reasoning, for "make it like week N" lookups
created_at           TIMESTAMPTZ — when this version was created

Operational Databases:

Usage - Stores agent usage data (to be used for spend bar):
─────────────────────────────────────────────
id          UUID           — unique identifier for the row
model       TEXT           — which AI model was called (e.g. gemini-pro, veo-3)
call_type   TEXT           — what kind of call (image, video, caption, edit, research, explain, embedding)
cost_eur    NUMERIC(10,6)  — how much it cost in euros, to 6 decimal places
trigger     TEXT           — what caused the call (cron, edit, explain, ingest)
post_id     UUID           — which post it relates to (nullable — research calls have no post)
created_at  TIMESTAMPTZ    — when the call happened

Spend bar query: 
SELECT SUM(cost_eur) FROM usage
WHERE created_at >= start_of_current_month

Messages - Stores each message that the user and agent sends:
─────────────────────────────────────────────
id          UUID        — unique identifier for the row
post_id     UUID        — which post this message belongs to (FK → posts.id)
role        TEXT        — who sent it (user or agent)
content     TEXT        — the message text
created_at  TIMESTAMPTZ — when it was sent


Context Databases:

Rules - Stores the feedback that user gives to generator agent (extracted from patterns across messages for 14 days):
─────────────────────────────────────────────
id             UUID        — unique identifier for the row
text           TEXT        — the preference in plain English
confidence     REAL        — how strongly established this preference is (0.0 to 1.0)
status         TEXT        — active or user_removed
source_week_id UUID        — which week this rule was extracted from (FK → weeks.id)
created_at     TIMESTAMPTZ — when the rule was created
updated_at     TIMESTAMPTZ — when the rule was last updated

Brand_chunks - Vectorized brand document to save token costs
─────────────────────────────────────────────
id          UUID        — unique identifier for the row
content     TEXT        — a chunk of text from the brand document
embedding   VECTOR(768) — the vectorised version of that chunk
source      TEXT        — which section of the brand document it came from
created_at  TIMESTAMPTZ — when the chunk was inserted

Strategic_briefs - Stores monthly Gemini deep research strategic briefs 
─────────────────────────────────────────────
id          UUID        — unique identifier for the row
month       DATE        — first day of the month this brief covers (unique)
content     TEXT        — the full Deep Research output as plain text
created_at  TIMESTAMPTZ — when the row was created


## 5. Non-functional requirements

### 5.1 Tenancy

Each client deployment is single-tenant. No `client_id` columns. No multi-tenant patterns. One VPS, one Postgres database, one R2 bucket per client.

### 5.2 Authentication

Single long-lived bearer token per deployment. The client receives one URL containing the token. No magic links, no session management, no multi-user.

### 5.3 Data residency

All client data must stay in EU jurisdictions: Hetzner HEL1 region, R2 EU jurisdiction, no transfers outside the EU.

### 5.4 Reliability

- Weekly cron success rate: ≥99% over rolling 90 days
- Chat UI availability: ≥99.5% during EU business hours
- Edit response: ≤60s P95 for tweaks, ≤180s P95 for video regenerations
- Cron misfire grace window: 1 hour (recovers if process restarts within window)

### 5.5 Cost

Per-client operating cost should stay within €25–35/month at typical edit volume (1.5× base generation). This is enforced architecturally (single VPS, self-hosted Postgres, free tiers where applicable) and via the spend cap.

### 5.6 Observability

- Every paid tool call writes to `usage` with timestamp, cost, trigger source
- Every agent run produces ADK OpenTelemetry traces
- Structured logs via structlog, written to journald
- `/health` endpoint exposes liveness for external monitoring

## 6. Out of scope (v1)

- Direct publication to Instagram or any social platform
- Engagement analytics ingestion (Instagram Graph API)
- Multi-platform content adaptation (TikTok, LinkedIn, etc.)
- Multi-user collaboration per deployment
- Real-time or daily generation cadence
- Paid media or ad creative generation
- Non-English brands or right-to-left languages

## 7. Open decisions blocking implementation

| ID | Decision | Required by | Notes |
|---|---|---|---|
| D1 | Brand document for client #1 | Phase 1 start | System cannot do brand alignment without this |
| D2 | Cron failure policy (retry-and-skip vs. partial-and-flag) | Phase 1 design | Default: retry 3× with jitter, then partial-and-flag |
| D3 | Frontend framework | Phase 1 design | Default: React + Vite, deployed to Cloudflare Pages |
| D4 | Default monthly spend cap value | Pre-deploy | Default: €50 |
| D5 | Hard cap option default | Pre-deploy | Default: disabled (soft only) |

## 8. Phased build plan

### Phase 1 — Core pipeline (target: 4 weeks)

- Database schema and migrations
- Self-hosted Postgres setup script
- Researcher and generator agents with prompts as files
- All four generation tools (image, video, caption, edit) with `@meter` wrapping
- Brand RAG via pgvector
- FastAPI service with chat, posts, usage, health routes
- APScheduler with weekly + monthly + nightly jobs
- Minimal frontend (single chat surface, spend bar, version history)
- Deploy script for new VPS provisioning
- One end-to-end test of the weekly flow

**Exit criteria:** Friday cron generates three posts on schedule for client #1, viewable in chat, downloadable from R2.

### Phase 2 — Production hardening (target: weeks 5–8)

- Edit subsystem with all three modes
- Strategic transparency (`reasoning_blob` and explain endpoint)
- Learning loop (rule extraction + injection)
- ADK ToolConfirmation for red-state spend gate
- Email notifications (digest, spend alerts, cron failures)
- Monitoring, alerting, incident response runbook
- Backup verification

**Exit criteria:** Client #1 has been in production for 4 weeks with ≥99% cron success and no unrecovered incidents.

### Phase 3 — Scale (target: weeks 9–12)

- Onboarding automation (deploy script reduces to ≤30 minutes)
- Operator dashboard for cost view across portfolio
- Client #2 through #5 onboarding
- Refined template versioning and divergence tracking

**Exit criteria:** 5 clients in production, operator burden ≤4 hours/week total.

## 9. How to work with this PRD

This document is the specification. `CLAUDE.md` is the operational guide. `docs/architecture.md` is the technical reference. `docs/decisions/` records why decisions were made.

When a requirement is ambiguous, ask before guessing. When a requirement conflicts with `CLAUDE.md` principles, surface the conflict — do not silently resolve it.

The system is built one phase at a time. Do not build Phase 2 features inside Phase 1. Each phase has explicit exit criteria; meet them before moving on.
