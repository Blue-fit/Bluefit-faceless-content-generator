-- Initial schema: all tables except vector columns (added in 003 after extension).
--
-- Creation order matters for FK resolution:
--   weeks → posts → post_versions (circular FK resolved via DEFERRABLE constraint)
--   weeks → rules
--   posts → messages, usage

CREATE TABLE weeks (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    week_start  DATE        NOT NULL UNIQUE,
    trend_brief JSONB,
    status      TEXT        NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'ready', 'failed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- current_version_id FK is added below after post_versions exists.
-- The constraint is DEFERRABLE so both rows can be inserted in one transaction.
CREATE TABLE posts (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    week_id            UUID        NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
    type               TEXT        NOT NULL CHECK (type IN ('image', 'video')),
    pillar             TEXT        NOT NULL,
    current_version_id UUID,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sacred table: rows are never updated after insert. version_number is
-- monotonically increasing per post_id. reasoning_embedding added in 003.
CREATE TABLE post_versions (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id           UUID        NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    parent_version_id UUID        REFERENCES post_versions(id) ON DELETE SET NULL,
    version_number    INT         NOT NULL,
    asset_url         TEXT,
    caption           TEXT,
    edit_instruction  TEXT,
    reasoning_blob    JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (post_id, version_number)
);

-- Complete the circular FK. DEFERRABLE INITIALLY DEFERRED means the check
-- runs at COMMIT, not at INSERT. Insert order: post (NULL) → version → UPDATE post.
ALTER TABLE posts
    ADD CONSTRAINT posts_current_version_id_fkey
    FOREIGN KEY (current_version_id)
    REFERENCES post_versions(id)
    ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;

-- Sacred table: append-only. Never update or delete rows. Ground truth for spend.
CREATE TABLE usage (
    id         UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    model      TEXT           NOT NULL,
    call_type  TEXT           NOT NULL
               CHECK (call_type IN ('image', 'video', 'caption', 'edit', 'research', 'explain', 'embedding', 'extraction')),
    cost_eur   NUMERIC(10,6)  NOT NULL,
    trigger    TEXT           NOT NULL
               CHECK (trigger IN ('cron', 'edit', 'explain', 'ingest')),
    post_id    UUID           REFERENCES posts(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE TABLE messages (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id    UUID        NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    role       TEXT        NOT NULL CHECK (role IN ('user', 'model')),
    content    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sacred table: status transitions only. Active rules are injected into every
-- generation run. Rows are never deleted; user_removed preserves the audit trail.
CREATE TABLE rules (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    text           TEXT        NOT NULL,
    confidence     REAL        NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    status         TEXT        NOT NULL DEFAULT 'active'
                               CHECK (status IN ('active', 'user_removed')),
    source_week_id UUID        REFERENCES weeks(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- embedding column added in 003 after pgvector extension is installed.
CREATE TABLE brand_chunks (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    content    TEXT        NOT NULL,
    source     TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE strategic_briefs (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    month      DATE        NOT NULL UNIQUE,
    content    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
