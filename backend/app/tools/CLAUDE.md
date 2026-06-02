# Tools

Functions the agent can call. Each tool is one file. Each tool does one
thing.

## Rules

1. **Async only.** No sync functions in this directory.
2. **Pydantic input + output models.** No raw dicts crossing tool
   boundaries.
3. **All paid tools wrapped in `@meter`.** See `app/meter/CLAUDE.md`.
4. **Raise `ToolError` on user-facing failures**; log and re-raise on
   unexpected bugs.
5. **Tools do not call other tools directly.** A tool returns a result;
   the agent or pipeline decides what to do next. This keeps `@meter` on
   the boundary and prevents hidden tool chains.

## Tools and what they wrap

| Tool | Wraps | Paid? |
|---|---|---|
| `generate_image.py` | Nano Banana (`gemini-2.5-flash-image`) | Yes |
| `generate_video.py` | Veo 3.1 Fast (`veo-3.1-fast-generate-preview`) | Yes |
| `generate_caption.py` | Gemini Flash with engagement template | Yes |
| `edit_post.py` | Dispatches tweak/regenerate/rewrite | Calls paid tools |
| `brand_rag.py` | pgvector retrieval over `brand_chunks` | No |
| `memory_search.py` | pgvector over `post_versions.reasoning_embedding` | No |
| `explain.py` | Flash render of `reasoning_blob` | Yes |

## Asset upload

Any tool that produces a binary asset (image, video) must:

1. Generate the asset
2. Upload to R2 via `app/storage/r2.py`
3. Return the R2 key + signed URL in its output model

Do not return raw bytes across tool boundaries. R2 is the canonical home
for asset binaries.

## Edit dispatch

`edit_post.py` is the only place that knows about tweak/regenerate/rewrite
modes. It receives an instruction, classifies it, and dispatches the
appropriate underlying tool. The classification logic lives here, not in
the agent prompt.

## When adding a tool

1. Create `app/tools/your_tool.py`
2. Wrap with `@meter` if it's paid
3. Add input/output Pydantic models
4. Add a unit test in `tests/unit/`
5. Register it with the agent in `app/agents/pipeline.py` if it's
   agent-callable
