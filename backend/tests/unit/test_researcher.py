from app.agents.researcher import build_researcher
from app.genai_client import MODEL_FLASH


def test_researcher_wiring() -> None:
    agent = build_researcher()
    assert agent.name == "researcher"
    assert agent.model == MODEL_FLASH
    assert agent.output_key == "trend_brief"
    tool_names = [getattr(t, "name", None) for t in agent.tools]
    assert "google_search" in tool_names


def test_researcher_instruction_is_brand_grounded() -> None:
    instruction = build_researcher().instruction
    assert isinstance(instruction, str)
    assert "Blue Fit" in instruction
    assert "JSON" in instruction
