# 010 — Model-rendered typography on images

**Date:** 2026-09-17 · **Status:** accepted · builds on 008 (mascot), 009 (Pro Image / Omni)

## Decision
For **images**, the on-screen hook is rendered **by Gemini 3 Pro Image inside the picture**
(headline with a highlighted keyword, handwritten caption CTA, hand-drawn arrow) plus 1–2
in-scene Dutch text props, instead of a PIL overlay. A metered Flash **read-back** transcribes
the result; a misspelled headline/CTA re-rolls (max 3). **Video** keeps the clean opening
frame + code overlay (text baked into a still would move/warp under Omni's camera).

## Why
The client produced a visibly better post in the Gemini app with the same model: designed
typography and on-brand signage read as a real social post; our uniform Montserrat block read
as a sticker. A prototype through our own stack matched it first try with every word exact.

## Consequences
- `prompt_builder.build_image_prompt(scene, hook)` appends `style_block_typography.md`;
  without a hook it appends `style_block_clean_top.md`. The shared base no longer forbids text.
- `render.render_base(..., hook=)` verifies text via `tools/read_image_text.py`
  (`@meter("extraction")`). For images the final IS the base (one R2 object).
- **Image edits:** a hook/size change uses Pro Image *edit mode* on the stored final
  (`render.edit_still_text`) — same picture, new text (~$0.13 + read-back) instead of the free
  overlay. Video edits are unchanged (overlay on the clean clip).
- Cost per weekly run: unchanged image calls (+ ~2 cents of read-backs; a re-roll on a
  misspelling costs one extra image). Brand font is the model's, not Montserrat, on images.
- Known limit: text exactness is verified, but layout/legibility is the model's; the
  overlay restyle for video (matching hierarchy/pill/arrow) is a follow-up.
