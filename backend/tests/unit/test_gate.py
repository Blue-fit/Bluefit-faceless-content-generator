from decimal import Decimal

from app.meter.gate import GateState, evaluate, fraction_used


def test_green_below_80_percent() -> None:
    assert evaluate(Decimal("0"), Decimal("50")) is GateState.GREEN
    assert evaluate(Decimal("39.99"), Decimal("50")) is GateState.GREEN


def test_amber_at_and_above_80_percent() -> None:
    assert evaluate(Decimal("40"), Decimal("50")) is GateState.AMBER  # exactly 80%
    assert evaluate(Decimal("49.99"), Decimal("50")) is GateState.AMBER


def test_red_at_and_above_100_percent() -> None:
    assert evaluate(Decimal("50"), Decimal("50")) is GateState.RED  # exactly 100%
    assert evaluate(Decimal("75"), Decimal("50")) is GateState.RED


def test_zero_or_negative_cap_disables_gate() -> None:
    assert evaluate(Decimal("100"), Decimal("0")) is GateState.GREEN
    assert evaluate(Decimal("100"), Decimal("-5")) is GateState.GREEN


def test_fraction_used() -> None:
    assert fraction_used(Decimal("25"), Decimal("50")) == 0.5
    assert fraction_used(Decimal("10"), Decimal("0")) == 0.0
