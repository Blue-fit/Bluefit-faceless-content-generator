-- Allow 'generation' in usage.call_type.
--
-- The weekly generator (Gemini Pro, via the ADK runner) was never metered: it did
-- not fit any existing call type, so its spend never reached `usage`. Forward-only:
-- widen the CHECK rather than editing 001.

ALTER TABLE usage DROP CONSTRAINT IF EXISTS usage_call_type_check;

ALTER TABLE usage ADD CONSTRAINT usage_call_type_check
    CHECK (call_type IN (
        'image', 'video', 'caption', 'edit', 'research', 'generation',
        'explain', 'embedding', 'extraction'
    ));
