"""Edits may touch the asset, the caption, or BOTH — the client's top complaint."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.tools.edit_post import _CLASSIFY, EditPlan


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
