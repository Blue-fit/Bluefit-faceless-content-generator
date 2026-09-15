"""Weekly anchor rule: 3 different Power-9 values x 3 different pillars, none used last week."""

from app.agents.pipeline import _generator_message, _value_rule_violations
from app.agents.schemas import GeneratorOutput, PostReferences, PostSpec


def _post(pillar: str, value: str, type_: str = "image") -> PostSpec:
    return PostSpec(
        pillar=pillar,  # type: ignore[arg-type]
        type=type_,  # type: ignore[arg-type]
        scene_prompt="The Blue Fit mascot somewhere",
        caption_template="question",
        caption="c",
        references_used=PostReferences(value=value),  # type: ignore[arg-type]
    )


def _week(*pairs: tuple[str, str]) -> GeneratorOutput:
    return GeneratorOutput(posts=[_post(p, v) for p, v in pairs])


def test_valid_week_has_no_violations() -> None:
    out = _week(("Community", "Belonging"), ("Keep Moving", "Move naturally"),
                ("Natural Eating", "The 80% rule"))
    assert _value_rule_violations(out, frozenset()) == []


def test_repeated_value_is_flagged() -> None:
    out = _week(("Community", "Belonging"), ("Keep Moving", "Belonging"),
                ("Natural Eating", "The 80% rule"))
    problems = _value_rule_violations(out, frozenset())
    assert len(problems) == 1 and "values repeat" in problems[0]


def test_repeated_pillar_is_flagged() -> None:
    out = _week(("Community", "Belonging"), ("Community", "Move naturally"),
                ("Natural Eating", "The 80% rule"))
    problems = _value_rule_violations(out, frozenset())
    assert len(problems) == 1 and "pillars repeat" in problems[0]


def test_last_weeks_values_are_forbidden() -> None:
    out = _week(("Community", "Belonging"), ("Keep Moving", "Move naturally"),
                ("Natural Eating", "The 80% rule"))
    problems = _value_rule_violations(out, frozenset({"Belonging", "Relaxation"}))
    assert len(problems) == 1
    assert "forbidden" in problems[0] and "Belonging" in problems[0]
    assert "Relaxation" not in problems[0]  # only values actually used are reported


def test_message_lists_forbidden_values_and_rule() -> None:
    msg = _generator_message("themes", ["chunk"], [], [], frozenset({"Belonging"}))
    assert "Forbidden Power-9 values" in msg and "Belonging" in msg
    assert "3 DIFFERENT values and 3 DIFFERENT pillars" in msg


def test_message_marks_first_week_when_nothing_forbidden() -> None:
    assert "(none — first week)" in _generator_message("t", [], [], [])


def test_forbidden_match_is_case_insensitive_for_legacy_values() -> None:
    out = _week(("Community", "Belonging"), ("Keep Moving", "Move naturally"),
                ("Natural Eating", "The 80% rule"))
    problems = _value_rule_violations(out, frozenset({"move naturally"}))  # legacy lowercase
    assert len(problems) == 1 and "Move naturally" in problems[0]
