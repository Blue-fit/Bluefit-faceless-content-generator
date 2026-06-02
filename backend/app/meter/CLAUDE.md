# Cost Metering — Sacred Directory

This directory enforces spend caps. Every paid tool call routes through here.
Bugs here cost real money.

## What lives here

- `pricing.py` — SINGLE source of truth for unit costs. When Google changes
  prices, update this file and predicted costs across the system update.
- `callbacks.py` — ADK `before_tool_callback` and `after_tool_callback` hooks.
  These wrap every paid tool. Pure ADK integration; no business logic.
- `gate.py` — Pure functions implementing the three-state logic
  (green/amber/red). Easy to unit test. No I/O.

## Rules

1. The `@meter` decorator MUST wrap any function that calls a paid API.
   Adding a tool without `@meter` is a bug.
2. `pricing.py` is the single source of truth. Do not hardcode prices
   anywhere else in the codebase.
3. The three states (green/amber/red) are user-visible. Don't add a fourth
   state without coordinating UI changes.
4. Predicted vs actual cost discrepancies >10% trigger an alert. If you're
   changing pricing logic, run `scripts/verify_pricing.py`.
5. The `usage` table is the ground truth for "what has been spent."
   Never compute spend from logs or traces; always query `usage`.

## What lives elsewhere

- The actual `usage` table schema lives in `app/db/migrations/`.
- The `usage` repository (write/query) lives in
  `app/db/repositories/usage.py`.
- The UI spend bar reads from `app/routes/usage.py`, which queries the
  repository.

This directory writes to `usage` via the repository. It does not own the
table.

## When extending

- New paid model? Add its pricing constant to `pricing.py`, wrap its tool
  with `@meter`, done.
- New state behavior? Update `gate.py`, update the UI, update the user-facing
  copy in `docs/architecture.md`.
- New alert trigger? Coordinate with `app/notifications/email.py` —
  rate-limit alerts to avoid spamming the operator.
