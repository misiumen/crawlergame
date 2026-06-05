"""P29.53s — Highlight reel.

Track standout moments during a run. At floor descent / victory /
defeat, surface up to 3 highlights as a short montage. Each highlight
is a structured record so future UI can show icons / timestamps.

Recorded via `record(world, key, line, value=...)`. The reel keeps the
TOP entries by `value`, capped at `MAX_REEL_ENTRIES` per kind, so it
doesn't grow unbounded for long runs.
"""
from __future__ import annotations
from typing import Dict, List


MAX_REEL_ENTRIES = 12   # global cap per character
TOP_N_PER_SHOW = 3      # how many surface in the floor-end montage


# ── Reel storage ─────────────────────────────────────────────────────


def _reel(character) -> List[dict]:
    if character is None:
        return []
    if character.flags is None:
        character.flags = {}
    reel = character.flags.get("highlight_reel")
    if not isinstance(reel, list):
        reel = []
        character.flags["highlight_reel"] = reel
    return reel


def record(world, kind: str, line_pl: str, value: int = 1) -> None:
    """Add a highlight. `kind` groups records (e.g. „crit_kill",
    „big_drop", „close_call"). `value` is used for sorting — bigger
    = more impressive."""
    if world is None or getattr(world, "character", None) is None:
        return
    if not kind or not line_pl:
        return
    reel = _reel(world.character)
    floor_num = int(getattr(world, "floor_number", 1) or 1)
    minute = 0
    if getattr(world, "current_floor", None):
        minute = int(getattr(world.current_floor,
                             "current_minute", 0) or 0)
    reel.append({"kind": kind, "line": line_pl,
                 "value": int(value), "floor": floor_num,
                 "minute": minute})
    # Trim: keep the top MAX_REEL_ENTRIES by value across all kinds.
    if len(reel) > MAX_REEL_ENTRIES:
        reel.sort(key=lambda r: int(r.get("value", 0)), reverse=True)
        del reel[MAX_REEL_ENTRIES:]
        # Persist trimmed view.
        world.character.flags["highlight_reel"] = reel


def top_n(character, n: int = TOP_N_PER_SHOW) -> List[dict]:
    """Return the top-N most impressive entries by `value`."""
    reel = _reel(character)
    return sorted(reel, key=lambda r: int(r.get("value", 0)),
                  reverse=True)[:max(0, int(n))]


def emit_floor_end_montage(world) -> List[str]:
    """Return Polish lines suitable for floor-end / run-end logging.
    Empty list when reel is empty."""
    if world is None or getattr(world, "character", None) is None:
        return []
    picks = top_n(world.character, TOP_N_PER_SHOW)
    if not picks:
        return []
    out = ["═══ Highlight Reel ═══"]
    for i, h in enumerate(picks, 1):
        out.append(f"  {i}. F{h.get('floor','?')} — {h.get('line','')}")
    return out


def clear(character) -> None:
    """Reset reel — called on new run / load."""
    if character is None or character.flags is None:
        return
    character.flags["highlight_reel"] = []
