# Database

Self-hosted Postgres 16 + pgvector. Co-located on the same VPS as the
FastAPI service. NOT Supabase (see `docs/decisions/003`).

## Migration rules

1. Migrations are forward-only. No rollback files.
2. Never edit a migration after it ships. Always add a new one.
3. Numbered sequentially with 3-digit zero-padding: `001_`, `002_`, `003_`.
4. One migration per logical change. Don't bundle unrelated changes.
5. Migration runner lives in `app/db/migrate.py`. It tracks applied
   migrations in a `schema_migrations` table.

## Query rules

1. **All SQL lives in `repositories/`.** One file per entity. Do not
   scatter queries across routes or tools.
2. **Use asyncpg.** Never psycopg or psycopg2.
3. **Parameterize all inputs.** Never string-format SQL.
4. **Connection pooling via `connection.py`.** Tools and routes receive
   a connection from the pool, don't create their own.
5. **Transactions** wrap any multi-statement operation. Use the connection's
   transaction context.

## Schema conventions

- Primary keys: `UUID` with `gen_random_uuid()` default
- Timestamps: `TIMESTAMPTZ`, default `NOW()`
- Soft enums: `TEXT` with `CHECK` constraints (not Postgres ENUM types —
  they're a migration headache)
- JSONB for structured data with evolving schemas (`reasoning_blob`, etc.)
- Foreign keys: always `ON DELETE` policy specified explicitly

## Embeddings

- 768 dimensions (text-embedding-005)
- Cosine similarity for retrieval
- HNSW index on every embedding column
- Two embedding surfaces:
  - `brand_chunks.embedding` — chunked brand doc for generation-time RAG
  - `post_versions.reasoning_embedding` — for "make this like week N"
    lookups

## Sacred tables

These tables have non-obvious invariants. Read the comments in their
migration files before modifying:

- `post_versions` — versioned, never updated, parent-linked
- `usage` — append-only, ground truth for spend
- `rules` — status transitions only, full audit trail preserved

## When adding a new table

1. Write the migration in `migrations/NNN_description.sql`
2. Add a Pydantic model in `models.py`
3. Create a repository in `repositories/{name}.py`
4. Add unit tests for the repository
5. If the table has sacred invariants, document them in this file and in
   the migration comments
