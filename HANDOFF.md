# Deployment & Connection Handoff

Status: the **content-generation backend is functionally complete and live-verified**
against the Neon DB (generation, RAG, weekly pipeline, explain, edit, learning loop —
all on `main`). What remains is the **deploy + connect** layer.

## Deployment topology

| Layer | Where | Owner | Status |
|---|---|---|---|
| **Database** | Jacob's call (Postgres + pgvector) | Jacob | ✅ an instance is live; backend builds against it. Hosting choice is Jacob's. |
| **Backend** | **Render** (Frankfurt / EU — web service + cron jobs) | Jacob | ⬜ to deploy |
| **Frontend** | **Vercel** | Us | ⬜ to deploy |

The database (host, region, provider) is **Jacob's to own and decide** — not our
concern. Requirement: Postgres 16 + pgvector, reachable from the Render backend, EU
region for data residency. Keep `DATABASE_URL` pointed at whatever Jacob chooses.

---

## Jacob — backend on Render + connections

### 1. R2 storage (`app/storage/r2.py`)
Implement the **`AssetUploader`** Protocol already defined in `app/storage/__init__.py`:
```python
async def upload(self, *, data: bytes, key: str, content_type: str) -> str  # returns the asset URL
```
The pipeline + edit code already depend on this interface (tests use a local stand-in).
boto3 → Cloudflare R2 (EU bucket), return a signed/public URL stored in `post_versions.asset_url`.

### 2. FastAPI app + routes (`app/main.py`, `app/routes/*` — currently empty)
- `app/main.py`: create the FastAPI app; on startup call `create_pool()`, on shutdown `close_pool()` (`app/db/connection.py`).
- Routes (this is the backend↔frontend connection the frontend calls):
  - `routes/health.py` — `GET /health` (DB connectivity check)
  - `routes/chat.py` — chat per post (store/read `messages`; drives the **edit** flow via `app/tools/edit_post.py`)
  - `routes/posts.py` — list weeks/posts/versions; serve current version + asset URL + caption
  - `routes/usage.py` — **spend bar**: live read of the `usage` table (ground truth for spend)
- Add **CORS** for the Vercel frontend origin; auth via the single `AUTH_BEARER_TOKEN`.

### 3. Cron jobs — OURS (see "Us" below)
The scheduled triggers (weekly + nightly) are **our scope**. Jacob only needs to ensure
the Render Blueprint runs the cron services with the **same env** (DB + secrets) as the
web service; we own the schedule definitions and the entrypoint scripts.

### 4. Env vars on Render (from `app/config.py`)
`DATABASE_URL` (Neon), `GOOGLE_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI=false`, `R2_ACCOUNT_ID`,
`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ENDPOINT_URL`, `RESEND_API_KEY`,
`EMAIL_FROM`, `CLIENT_EMAIL`, `OPERATOR_EMAIL`, `AUTH_BEARER_TOKEN`. (Spend cap defaults to €50.)

### 5. Email notifications — OURS (see "Us" below)
The Resend email notifications are our scope. Jacob only needs `RESEND_API_KEY` +
the email env vars set on Render.

---

## Us — frontend (Vercel) + cron jobs + email

### Frontend on Vercel
- Deploy the frontend (`frontend/`, Vue 3 + Vite) to **Vercel**.
- Point it at the Render backend API base URL; send the `AUTH_BEARER_TOKEN`.
- Chat/review UI: per-post thread, version dropdown ("v2 of 3"), asset (from R2) + caption
  (from the DB) side by side, spend bar, download.

### Cron jobs (Render Cron, defined by us)
- **Weekly** (Fri 09:00 UTC) → `scripts/trigger_weekly.py` → `run_weekly(...)` — gated on Jacob's R2 uploader.
- **Nightly** → `scripts/run_learning.py` → `run_learning(14)` — built & verified, ready to schedule.
- (Monthly strategic Deep Research — future, not built.)
- We author the cron definitions (render.yaml) + entrypoint scripts; they run in Jacob's Render env.

### Automatic email (`app/notifications/email.py` — empty)
- Resend integration: **weekly digest** ("your 3 posts are ready", at the end of `run_weekly`),
  **spend alerts** (amber/red, off `@meter`), and **cron/generation-failure** alerts.
- Event-driven, not a separate schedule (the digest rides the weekly cron).

---

## Ready-made seams (so the connect work is plug-in, not rebuild)
- `run_weekly(week_start, *, uploader)` — the whole weekly flow (research → RAG → generate → render → persist)
- `run_learning(days)` — nightly rule extraction (active rules already feed the generator)
- `AssetUploader` Protocol (`app/storage/__init__.py`) — implement in `r2.py`
- All DB repos done; `scripts/ingest_brand.py` populates `brand_chunks` (run once per brand-doc change)
- `@meter` already records all paid calls to `usage` → the spend bar just reads it

## ⚠️ Security
- **Rotate now:** the Neon DB password and the `GOOGLE_API_KEY` were exposed in chat earlier.
  Update Render env vars + `backend/.env` after rotating.
- `backend/.env` is gitignored — keep all secrets out of git. Set them as Render env vars, not in code.
