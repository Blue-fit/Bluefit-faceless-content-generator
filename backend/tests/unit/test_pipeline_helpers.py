"""Pipeline helpers that carry the beat / mascot fingerprint through a weekly run."""

from uuid import uuid4

import pytest

from app.agents import pipeline
from app.agents.schemas import PostReferences, PostSpec
from app.tools.memory_search import RecentPost


def _recent(beat: str | None) -> RecentPost:
    return RecentPost(
        version_id=uuid4(),
        pillar="Community",
        theme="t",
        value="belonging",
        hook="h",
        beat=beat,
        scene_prompt="The Blue Fit mascot in a park",
        caption=None,
        asset_url=None,
    )


def test_recent_block_surfaces_beats_when_present() -> None:
    block = pipeline._recent_block([_recent("high-fives the lens"), _recent(None)])
    lines = block.splitlines()
    assert "| beat: high-fives the lens |" in lines[0]
    assert "beat:" not in lines[1]


def test_generator_message_scopes_brand_context_to_values() -> None:
    msg = pipeline._generator_message("themes", ["chunk"], [], [])
    assert "VALUES" in msg and "ignore any visual" in msg
    assert "each starring the Blue Fit mascot" in msg


def test_reasoning_blob_carries_beat_and_mascot_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline, "mascot_refs_version", lambda: "abc123def456")
    spec = PostSpec(
        pillar="Keep Moving",
        type="image",
        scene_prompt="The Blue Fit mascot on the stairs",
        beat="looks back as if to say 'coming?'",
        caption_template="question",
        caption="c",
        references_used=PostReferences(theme="t", value="Move naturally"),
    )
    blob = pipeline._reasoning_blob(spec, [], [], "img-model", "https://r2/base.jpg")
    assert blob["beat"] == spec.beat
    assert blob["mascot_refs_version"] == "abc123def456"
    assert spec.beat in pipeline._reason_text(spec)
