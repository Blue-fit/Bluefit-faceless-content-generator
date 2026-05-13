# Tests

## Stack

- pytest
- pytest-asyncio for async tests
- pytest-mock for mocking
- Docker-compose for integration test Postgres

## Conventions

- **Unit tests** (`tests/unit/`): no network, no real DB. Mock at the
  boundary (HTTP clients, DB connections, ADK runners).
- **Integration tests** (`tests/integration/`): real Postgres in Docker.
  Mock external APIs (Google, R2, Resend) at the SDK boundary.
- **Fixtures** in `fixtures/` — reuse aggressively. Don't recreate sample
  data in every test.
- **Coverage isn't a target; meaningful tests are.** Don't pad with
  trivial tests to hit a coverage number.

## What must have tests

- `app/meter/gate.py` — every state transition
- `app/meter/pricing.py` — every model's pricing
- `app/agents/schemas.py` — schema validation including breaking-change
  detection
- Every repository in `app/db/repositories/` — round-trip insert + query
- The weekly pipeline end-to-end (integration test)
- The edit subsystem for each of the three modes (integration test)

## What doesn't need tests

- Prompt content (`*.md` files) — tested by running the agent, not
  by unit assertions
- FastAPI route boilerplate — request/response framing
- Pydantic model definitions — pydantic itself is tested
- Configuration loading — pydantic-settings is tested

## Running tests

- All: `uv run pytest`
- Unit only: `uv run pytest tests/unit/`
- Single test: `uv run pytest tests/unit/test_meter.py::test_red_state -xvs`
- With integration: `uv run pytest --integration`
- Coverage report: `uv run pytest --cov=app --cov-report=html`

## Fixtures

`fixtures/` contains:

- `brand_profile.yaml` — minimal valid brand profile for tests
- `sample_brief.json` — realistic `TrendBrief` JSON
- `sample_brand_doc.md` — small brand doc for RAG tests

Add new fixtures here when more than one test needs them.
