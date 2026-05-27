"""P29.32 — Debug-aware exception helper.

The audit flagged 137 `except Exception: pass` blocks across 27
files. Mass-rewriting to scoped types is high-risk; many of those
swallows are legitimate "this side-effect is best-effort, never
crash the player" guards.

But the audio-import bug (P29.21) proved the pattern hides real
defects. This module ships a tiny helper:

    swallow(scope: str)
        Context manager. In production, behaves identically to
        `except Exception: pass`. With DK_DEBUG=1 in the env,
        writes the exception to stderr with the scope tag so a
        developer can find the offending site without affecting
        end users.

Usage at call sites converted from `try: ... except: pass`:

    from ._debug import swallow

    with swallow("audio.play_sfx"):
        audio.play_sfx("player_death")

Call sites NOT converted (~130 remaining) keep their old shape
for back-compat. Targeted upgrades land on the highest-risk
silent swallows where a real bug would otherwise lurk.
"""
from __future__ import annotations
import os
import sys
import traceback
from contextlib import contextmanager


_DEBUG = os.environ.get("DK_DEBUG", "") in ("1", "true", "True", "yes")


@contextmanager
def swallow(scope: str = ""):
    """Best-effort context manager. Catches Exception, returns
    quietly in production, surfaces the trace to stderr under
    DK_DEBUG=1.

    `scope` is a free-text tag (e.g. "audio.play_sfx" or
    "sponsors.adjust_attention") used as the stderr prefix so the
    devstream is greppable.
    """
    try:
        yield
    except Exception as exc:
        if _DEBUG:
            try:
                sys.stderr.write(
                    f"[DK_DEBUG] swallowed in {scope!r}: "
                    f"{type(exc).__name__}: {exc}\n")
                traceback.print_exc(file=sys.stderr)
            except Exception:
                pass
        # Otherwise: silent, matching the pre-P29.32 contract.


def is_debug() -> bool:
    """True when DK_DEBUG=1. Useful for assert / log gating."""
    return _DEBUG
