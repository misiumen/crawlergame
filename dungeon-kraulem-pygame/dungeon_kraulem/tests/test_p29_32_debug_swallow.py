"""Prompt 29.32 — Debug-aware exception swallow smoke.

Audit secondary finding: 137 `except Exception: pass` blocks hide
real defects (the P29.21 audio-import bug being the smoking gun).
Mass-rewriting to scoped types is high-risk for legitimate
best-effort guards.

Solution: `engine/_debug.swallow(scope)` context manager. In
production behaves identically to the old pattern. With
DK_DEBUG=1 env var, surfaces the trace to stderr with the scope
tag so devs can grep for the problem.

Targeted retrofits this round (high-risk silent swallows):
  * Game._check_player_dead: last-stand SFX + death SFX
  * Game._check_player_dead: run_history.record_run + save_load.delete
  * time_system.advance: show_director / proxy_wars / companion_voice
"""
from __future__ import annotations
import io, os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


# ── swallow() basic behavior ────────────────────────────────────────────

def test_swallow_silent_in_production():
    """Default mode (DK_DEBUG not set / not '1'): swallows
    exceptions without writing anywhere."""
    from ..engine._debug import swallow
    # Force-clear any DK_DEBUG that the parent process set, just for
    # this test. The module-level flag is captured at import; we
    # work around by directly poking the flag.
    from ..engine import _debug as _d
    saved = _d._DEBUG
    _d._DEBUG = False
    old_stderr = sys.stderr
    sink = io.StringIO()
    sys.stderr = sink
    try:
        with swallow("test.scope"):
            raise ValueError("nope")
    finally:
        sys.stderr = old_stderr
        _d._DEBUG = saved
    assert sink.getvalue() == "", \
        f"production swallow should not write stderr; got {sink.getvalue()!r}"
    print("  swallow silent in production: OK")


def test_swallow_writes_to_stderr_in_debug():
    """DK_DEBUG=1 mode: swallowed exception is reported with the
    scope tag."""
    from ..engine._debug import swallow
    from ..engine import _debug as _d
    saved = _d._DEBUG
    _d._DEBUG = True
    old_stderr = sys.stderr
    sink = io.StringIO()
    sys.stderr = sink
    try:
        with swallow("test.scope"):
            raise RuntimeError("boom")
    finally:
        sys.stderr = old_stderr
        _d._DEBUG = saved
    out = sink.getvalue()
    assert "DK_DEBUG" in out
    assert "test.scope" in out
    assert "RuntimeError" in out
    assert "boom" in out
    print(f"  swallow in DEBUG mode: writes scope + exc to stderr: OK")


def test_swallow_does_not_re_raise():
    """The whole point: the caller continues normally."""
    from ..engine._debug import swallow
    ran_after = False
    with swallow("test"):
        raise ValueError("nope")
    ran_after = True
    assert ran_after
    print("  swallow returns control to caller after exception: OK")


# ── Integration: existing call sites use it ─────────────────────────────

def test_game_uses_swallow_in_death_path():
    """Audit smoking gun: _check_player_dead silently failed to play
    SFX. After P29.32 the call site uses swallow() so DK_DEBUG=1
    would now print the failure if it ever resurfaces."""
    import inspect
    from ..engine.game import Game
    src = inspect.getsource(Game._check_player_dead)
    # The literal `swallow(` should be reachable from the patched
    # body (used for audio + run_history + save_load).
    assert "swallow(" in src, \
        "Game._check_player_dead should use the new swallow helper"
    print("  Game._check_player_dead uses swallow(): OK")


def test_time_system_uses_swallow():
    import inspect
    from ..engine import time_system as _ts
    src = inspect.getsource(_ts.advance)
    assert "swallow(" in src
    print("  time_system.advance uses swallow(): OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_swallow_silent_in_production()
    test_swallow_writes_to_stderr_in_debug()
    test_swallow_does_not_re_raise()
    test_game_uses_swallow_in_death_path()
    test_time_system_uses_swallow()
    print("Prompt 29.32 debug-swallow smoke: OK")


if __name__ == "__main__":
    main()
