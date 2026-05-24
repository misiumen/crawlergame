"""CRAWL PROTOCOL - Lightweight dialog engine.

Each NPC archetype × disposition has a small node graph keyed in
locales/<lang>.json under `dialog_{archetype}_{dispo}_{state}_*`:
   `_say`     - the NPC line
   `_opt1..N` - the player option labels
   `_next1..N`- next state id, or terminal markers
                "@combat"  starts combat
                "@trade"   grants a small bonus
                "@end"     closes dialog
"""
import random
from typing import Optional, List, Tuple

from lang import tr, has_key


def get_node(crawler, state: Optional[str] = None) -> dict:
    """Return a dict {say, options:[(label, next), ...]} for current dialog state."""
    s = state or crawler.dialog_state or "start"
    arc = crawler.archetype
    dispo = crawler.disposition
    base = f"dialog_{arc}_{dispo}_{s}"

    say = tr(f"{base}_say")
    if say == f"{base}_say":  # missing — fallback to generic
        say = tr(f"dialog_generic_{dispo}_say")

    options = []
    for i in range(1, 5):
        lbl_key = f"{base}_opt{i}"
        nxt_key = f"{base}_next{i}"
        if has_key(lbl_key):
            options.append((tr(lbl_key), tr(nxt_key)))
        else:
            break
    if not options:
        options = [(tr("common_continue"), "@end")]

    return {"say": say, "options": options, "state": s}


def advance(crawler, next_id: str) -> str:
    """
    Apply a chosen next-state id to the crawler.
    Returns a terminal marker (@combat, @trade, @end, @aggro) or "" if just
    transitioned to a non-terminal state.
    """
    if not next_id:
        return ""
    if next_id.startswith("@"):
        return next_id
    crawler.dialog_state = next_id
    return ""
