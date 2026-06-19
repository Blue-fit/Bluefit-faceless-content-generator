from app.agents.generator import build_generator
from app.agents.schemas import GeneratorOutput
from app.genai_client import MODEL_PRO


def test_generator_wiring() -> None:
    agent = build_generator()
    assert agent.name == "generator"
    assert agent.model == MODEL_PRO
    assert agent.output_key == "post_specs"
    assert agent.output_schema is GeneratorOutput
    assert not agent.tools  # output_schema disables tools


def test_generator_instruction_is_static_brand() -> None:
    instruction = build_generator().instruction
    assert isinstance(instruction, str)
    assert "Blue Fit" in instruction
    assert "scene_prompt" in instruction
