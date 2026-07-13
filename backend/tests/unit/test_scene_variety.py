"""Scene-variety helpers that stop the video reusing the same setting each week."""

from uuid import uuid4

from app.agents.pipeline import _recent_scene_families, _scene_family
from app.tools.memory_search import RecentPost


def _post(scene: str | None) -> RecentPost:
    return RecentPost(
        version_id=uuid4(),
        pillar="Keep Moving",
        theme=None,
        value=None,
        hook=None,
        scene_prompt=scene,
        caption=None,
        asset_url=None,
    )


def test_water_scenes_map_to_water_family() -> None:
    assert _scene_family("People swimming in the ocean at sunrise") == "water"
    assert _scene_family("A calm lake with a paddleboarder, seen from behind") == "water"
    assert _scene_family("Waves rolling onto the beach") == "water"


def test_other_families_recognised() -> None:
    assert _scene_family("A quiet home kitchen preparing a fresh salad") == "kitchen"
    assert _scene_family("Hands lifting a dumbbell in a bright gym") == "gym"
    assert _scene_family("A runner on a forest trail") == "nature"
    assert _scene_family("A rooftop cafe in the city at dusk") == "urban"


def test_unrecognised_scene_is_other() -> None:
    assert _scene_family("An abstract close-up of textured fabric") == "other"
    assert _scene_family(None) == "other"


def test_recent_families_collects_and_drops_other() -> None:
    recent = [
        _post("People swimming in the ocean"),
        _post("A home living room with morning light"),
        _post("An abstract close-up of textured fabric"),  # -> other, dropped
    ]
    assert _recent_scene_families(recent) == {"water", "home"}