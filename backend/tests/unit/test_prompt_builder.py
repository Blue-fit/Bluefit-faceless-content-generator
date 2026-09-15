"""The code-appended style blocks carry the mascot brief, not the old faceless one."""

from app.agents.prompt_builder import build_image_prompt, build_video_prompt


def test_image_prompt_leads_with_scene_and_names_the_mascot() -> None:
    prompt = build_image_prompt("The Blue Fit mascot in a kitchen.")
    assert prompt.startswith("The Blue Fit mascot in a kitchen.")
    assert "Blue Fit mascot" in prompt
    assert "9:16" in prompt
    assert "Faceless" not in prompt and "silhouette" not in prompt.lower()


def test_video_prompt_animates_from_first_frame_without_speech() -> None:
    prompt = build_video_prompt("The Blue Fit mascot at a desk.", "Slow push-in.")
    assert "Camera & motion: Slow push-in." in prompt
    assert "first frame" in prompt
    assert "no speech" in prompt
    assert "never talks" in prompt
