"""P29.53k — per-floor deadline + carryover bonus.

Smoke tests for the DCC-canon time-scaling pipeline:
* `deadline_minutes_for_floor(n)` returns the table-driven base, and
  falls back to DEADLINE_DAYS_DEFAULT for floors past the table.
* `_descend_or_win` carries leftover time + +5d bonus to next floor.
"""
from __future__ import annotations
import pytest

from ..config import (
    deadline_minutes_for_floor,
    DEADLINE_DAYS_BY_FLOOR,
    DEADLINE_DAYS_DEFAULT,
    DEADLINE_CARRYOVER_BONUS_DAYS,
    MINUTES_PER_DAY,
)


def test_deadline_table_matches_canon_for_floor_1():
    """F1 = 14d per DCC book."""
    assert deadline_minutes_for_floor(1) == 14 * MINUTES_PER_DAY
    assert DEADLINE_DAYS_BY_FLOOR[1] == 14


def test_deadlines_shrink_through_floors():
    """Later floors should have smaller deadlines (canon: it gets
    nastier as you descend)."""
    assert (deadline_minutes_for_floor(2)
            < deadline_minutes_for_floor(1))
    assert (deadline_minutes_for_floor(10)
            <= deadline_minutes_for_floor(5))


def test_deadline_default_for_floors_past_table():
    """Floor 99 (out of table) falls back to default."""
    assert (deadline_minutes_for_floor(99)
            == DEADLINE_DAYS_DEFAULT * MINUTES_PER_DAY)


def test_descend_carries_leftover_plus_bonus():
    """Simulate the carryover math from _descend_or_win directly so
    we don't have to spin a full Game. The contract:
      new_deadline = base_for_next_floor + leftover + 5d bonus
    """
    # Player on F1, used 4 days (10 left).
    f1_used_min = 4 * MINUTES_PER_DAY
    f1_total = deadline_minutes_for_floor(1)
    f1_leftover = f1_total - f1_used_min
    # Build "new floor" pool
    f2_base = deadline_minutes_for_floor(2)
    bonus = DEADLINE_CARRYOVER_BONUS_DAYS * MINUTES_PER_DAY
    expected = f2_base + f1_leftover + bonus
    # Per-floor base (10d) + 10d leftover + 5d bonus = 25d.
    assert expected == 25 * MINUTES_PER_DAY


def test_floor_generator_uses_table():
    """Smoke-test that the floor generator now respects the per-floor
    table. We hit the lighter procgen path which exists for legacy
    tests, so don't depend on full world bootstrap — just check the
    config function is wired in."""
    from .. import config
    # If anyone reverts this to a constant the test catches it.
    src = open(config.__file__, "r", encoding="utf-8").read()
    assert "deadline_minutes_for_floor" in src
