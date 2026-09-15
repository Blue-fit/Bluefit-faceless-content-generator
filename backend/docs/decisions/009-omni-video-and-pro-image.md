# 009 — Gemini Omni Flash for video, Gemini 3 Pro Image for stills

**Date:** 2026-09-15 · **Status:** accepted · **Supersedes** the video-model part of 008
(Veo 3.1 Fast image-to-video) and the Aug-2026 "stay on Veo" evaluation.

## Decision
- `MODEL_VIDEO = gemini-omni-1.1-flash` via the **Interactions API**
  (`client.aio.interactions.create`, `video_config.task = image_to_video`).
- `MODEL_IMAGE = gemini-3-pro-image` (Gemini 3 Pro Image) via `generate_content` as before.

## Why (measured, not assumed)
Spike + real run on 2026-09-15 with the actual mascot still, from the Netherlands (EEA):
- **Image-to-video is native and exact:** frame 1 *is* the input still; the mascot's
  likeness held through the whole 8 s clip. This is what the mascot design depends on.
- **EEA:** an uploaded still as *generation* input is accepted. (The EEA block applies to
  *editing uploaded videos*, which we never do — edits regenerate from a new still.)
- **Speed:** ~40 s per clip vs Veo's 90 s–6 min (and Veo's 6-min timeout risk).
- **Cost:** identical — $17.50/M video tokens at 5,792 tok/s ≈ $0.10/s of 720p; an 8 s
  clip used 46,336 tokens = $0.81. Veo was $0.80.
- **Pro Image:** noticeably sharper stills and better prompt adherence (rendered a
  legible wall-clock time); reference-photo likeness held. Price $0.134 vs $0.039/image
  (~3.4×). The toy/child filter still blocks ~50–75% of attempts, so the re-roll loop
  is now the dominant weekly cost (~€1 of images per run, worst case ~€2).

## Consequences
- `generate_video.py` no longer uses `generate_videos`/operations; it polls an
  interaction. `with_retry` duck-types the HTTP status (`.code` / `.status_code`) so
  Interactions 429/503 are retried like the classic client's.
- `reference_images` maps to Omni's `reference_to_video` (probe only; unchanged use).
- Pricing: `_PER_IMAGE` 0.039 → 0.134; `_PER_VIDEO_SECOND` stays 0.10.
- Revisit if Google changes Omni's EEA terms or the Pro Image filter rate; the cheaper
  `gemini-3.1-flash-image` remains a one-line fallback for the still.
