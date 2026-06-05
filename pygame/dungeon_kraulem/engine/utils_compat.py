"""Tiny shared utilities for the revamp engine."""
import random


def roll_d20() -> int:
    return random.randint(1, 20)
