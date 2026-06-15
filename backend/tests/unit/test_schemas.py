import pytest
from pydantic import ValidationError

from app.agents.schemas import (
    SCHEMA_VERSION,
    GeneratorOutput,
    PostReferences,
    PostSpec,
    TrendBrief,
    TrendTheme,
)


def test_schema_version_present() -> None:
    assert isinstance(SCHEMA_VERSION, int)


def test_trend_brief_valid() -> None:
    brief = TrendBrief(
        week_start="2026-06-15",  # type: ignore[arg-type]  # pydantic coerces
        themes=[TrendTheme(title="t", summary="s", why_relevant="w", source_url="u")],
    )
    assert brief.themes[0].title == "t"


def _image_spec(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "pillar": "Community",
        "type": "image",
        "scene_prompt": "x",
        "caption_template": "question",
        "caption": "c",
        "references_used": PostReferences(),
    }
    base.update(overrides)
    return base


def test_post_spec_valid_image() -> None:
    spec = PostSpec(**_image_spec())  # type: ignore[arg-type]
    assert spec.type == "image"


def test_post_spec_rejects_bad_pillar() -> None:
    with pytest.raises(ValidationError):
        PostSpec(**_image_spec(pillar="Nope"))  # type: ignore[arg-type]


def test_post_spec_rejects_bad_caption_template() -> None:
    with pytest.raises(ValidationError):
        PostSpec(**_image_spec(caption_template="hot_take"))  # type: ignore[arg-type]


def test_generator_output_holds_posts() -> None:
    out = GeneratorOutput(posts=[PostSpec(**_image_spec())])  # type: ignore[arg-type]
    assert len(out.posts) == 1
