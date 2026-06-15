"""Pure spend-gate logic (no I/O). Easy to unit-test exhaustively.

Three states (architecture.md §8 / PRD §4.7):
- green: 0-79% of the monthly cap consumed -> proceed silently
- amber: 80-99% -> proceed but warn
- red:   100%+  -> block (caller decides whether to confirm-through)
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

AMBER_FRACTION = Decimal("0.80")


class GateState(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


def evaluate(spend_eur: Decimal, cap_eur: Decimal) -> GateState:
    """Return the gate state for the given spend against the cap.

    A cap of 0 or less disables the gate (treated as GREEN / unlimited).
    """
    if cap_eur <= 0:
        return GateState.GREEN
    fraction = spend_eur / cap_eur
    if fraction >= 1:
        return GateState.RED
    if fraction >= AMBER_FRACTION:
        return GateState.AMBER
    return GateState.GREEN


def fraction_used(spend_eur: Decimal, cap_eur: Decimal) -> float:
    """Fraction of the cap consumed (for the UI spend bar). 0.0 if no cap."""
    if cap_eur <= 0:
        return 0.0
    return float(spend_eur / cap_eur)
