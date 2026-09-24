"""Edits may touch the asset, the caption, or BOTH — the client's top complaint."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.tools.edit_post import _CLASSIFY, EditNeedsClarification, EditPlan


def test_plan_accepts_both_targets() -> None:
    plan = EditPlan(targets=["asset", "caption"], mode="rewrite")
    assert set(plan.targets) == {"asset", "caption"}


def test_plan_accepts_a_single_target() -> None:
    assert EditPlan(targets=["caption"], mode="tweak").targets == ["caption"]


def test_plan_rejects_an_unknown_target() -> None:
    with pytest.raises(ValidationError):
        EditPlan(targets=["hashtags"], mode="tweak")  # type: ignore[list-item]


def test_classifier_is_told_never_to_drop_half_a_request() -> None:
    assert '"targets"' in _CLASSIFY
    assert "If the request mentions BOTH, return BOTH" in _CLASSIFY
    assert "Never silently drop half of what was asked" in _CLASSIFY
    # the real instruction that used to lose its caption half
    assert "ook in de caption" in _CLASSIFY


def test_classifier_returns_targets_not_target() -> None:
    """The output contract must name the list, or the plan won't validate."""
    assert '{"targets","mode"' in _CLASSIFY
    assert '{"target","mode"' not in _CLASSIFY


# ---- asking instead of guessing -------------------------------------------------


def test_plan_tolerates_an_explicit_null_mode() -> None:
    """A clarification reply carries mode=null; it must still parse.

    Without this the whole plan fails validation and the client sees
    "that edit failed" instead of the question.
    """
    plan = EditPlan.model_validate_json('{"targets": [], "mode": null, "clarify": "Wat precies?"}')
    assert plan.mode == "tweak" and plan.targets == [] and plan.clarify == "Wat precies?"


def test_plan_tolerates_an_explicit_null_targets() -> None:
    assert EditPlan.model_validate_json('{"targets": null, "mode": "tweak"}').targets == []


def test_classifier_is_told_to_ask_rather_than_guess() -> None:
    assert '"clarify"' in _CLASSIFY
    assert "too vague to act on" in _CLASSIFY
    # the real messages that were silently acted on
    assert "dit kan echt beter" in _CLASSIFY
    assert "wat is er verkeerd gegaan?" in _CLASSIFY
    assert "A request that names something concrete is NOT vague" in _CLASSIFY


def test_clarification_carries_its_question() -> None:
    exc = EditNeedsClarification("Wat zal ik aanpassen?")
    assert exc.question == "Wat zal ik aanpassen?"
    assert str(exc) == "Wat zal ik aanpassen?"


def test_clarify_fallback_exists_in_every_language() -> None:
    """A hardcoded Dutch fallback used to reach English speakers too."""
    from app.tools.edit_post import _PHRASES

    for lang, phrases in _PHRASES.items():
        assert "clarify_fallback" in phrases, lang
        assert "{media}" in phrases["clarify_fallback"], lang
        assert "—" not in phrases["clarify_fallback"], lang


def test_classifier_asks_for_a_reply_not_a_menu() -> None:
    assert "write it as a REPLY, not a menu" in _CLASSIFY
    assert "acknowledge what they actually said" in _CLASSIFY
    assert "Never use a dash as punctuation" in _CLASSIFY
    # the three real messages that must get a human answer
    for msg in ("dit kan echt beter", "wat is er verkeerd gegaan?", "heb ik gebruikt!"):
        assert msg in _CLASSIFY
