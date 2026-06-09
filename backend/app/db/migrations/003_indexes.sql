-- Add vector columns now that the pgvector extension exists (002).
-- HNSW indexes use cosine distance, matching text-embedding-005 output.

ALTER TABLE brand_chunks
    ADD COLUMN embedding VECTOR(768) NOT NULL;

ALTER TABLE post_versions
    ADD COLUMN reasoning_embedding VECTOR(768);

-- Vector indexes
CREATE INDEX ON brand_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX ON post_versions USING hnsw (reasoning_embedding vector_cosine_ops)
    WHERE reasoning_embedding IS NOT NULL;

-- Relational indexes
CREATE INDEX ON messages (post_id, created_at);
CREATE INDEX ON post_versions (post_id, version_number);
CREATE INDEX ON posts (week_id);
CREATE INDEX ON usage (created_at);
CREATE INDEX ON post_versions (created_at);
CREATE INDEX ON rules (status);
