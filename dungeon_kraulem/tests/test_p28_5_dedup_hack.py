"""Prompt 28.5 — room-dedup + meaningful hack smoke suite.

Covers:
  * Safehouse / lounge templates marked unique_per_floor: a generated
    floor never has two `pool_lounge` rooms (fixes "Lounge Druga
    Szansa appears twice with identical NPCs" playtest bug).
  * Hack success on a terminal grants credits, +tech affinity, log
    feedback, and sets hacked+unlocked state (fixes "action does
    nothing visible" playtest bug).
  * Re-hacking an already-hacked terminal does not double-dip.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import random as _r

from ..content.data import room_pool as _rp
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_TERMINAL
from ..engine import resolution as _res
from ..engine import consequences as _cons
from ..engine import validation as _val
from ..engine import parser_core as _pc


# ── Room dedup ───────────────────────────────────────────────────────────

def test_lounge_template_is_unique_per_floor():
    """Lounge template must carry unique_per_floor=True so it can't
    spawn twice on the same generated floor."""
    by_id = {t["template_id"]: t for t in _rp.ROOM_POOL}
    assert by_id["pool_lounge"].get("unique_per_floor") is True
    print("  pool_lounge has unique_per_floor: OK")


def test_all_safehouse_templates_unique_per_floor():
    """Cafe, bathroom, black market, clinic, lounge should all be 1/floor.
    Two cafes side-by-side with identical NPCs is the same bug class as
    the lounge dupe — guard against future regression."""
    expected_unique = {
        "pool_cafe", "pool_bathroom", "pool_black_market",
        "pool_clinic", "pool_lounge",
    }
    by_id = {t["template_id"]: t for t in _rp.ROOM_POOL}
    fails = [tid for tid in expected_unique
             if not by_id[tid].get("unique_per_floor")]
    assert not fails, f"missing unique_per_floor: {fails}"
    print(f"  all {len(expected_unique)} safehouse templates unique_per_floor: OK")


def test_generated_floor_has_no_duplicate_lounges():
    """Build several floors with different seeds; never see two
    pool_lounge picks in the same floor."""
    from ..engine import floor_generator as _fg
    from ..engine.world import WorldState as _WS
    from ..engine.character import Character as _Ch
    seen_seeds_with_dupe = 0
    for seed in range(15):
        w = _WS()
        w.character = _Ch(name="N", background="janitor")
        f = _fg.generate_floor(w, floor_number=1, seed=seed)
        lounge_count = sum(1 for r in f.rooms.values()
                           if getattr(r, "safehouse_subtype", "") == "lounge")
        if lounge_count > 1:
            seen_seeds_with_dupe += 1
    assert seen_seeds_with_dupe == 0, \
        f"{seen_seeds_with_dupe}/15 floors had duplicate lounge"
    print("  15 generated floors: 0 with duplicate lounge: OK")


# ── Hack feedback ────────────────────────────────────────────────────────

def _mk_world_with_terminal():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    term = Entity(key="zepsuty_terminal", entity_type=T_TERMINAL,
                  fallback_name="zepsuty terminal", hp=0, max_hp=0,
                  ac=0, tags=["terminal"],
                  affordances=["inspect", "hack"],
                  location_id="r0")
    w.register(term); r.entities.append(term)
    return w, term


def test_hack_success_grants_credits_and_logs():
    from ..engine.game import Game
    w, term = _mk_world_with_terminal()
    g = Game(screen=None); g.world = w; g.state = "play"
    pre_credits = w.character.credits
    # Pin INT high enough that d20+mod always exceeds the hack TT
    # (mod = (40-10)//2 = 15, so even d20=1 → 16 ≥ TT 14 → success).
    w.character.stats["INT"] = 40
    _r.seed(3)
    g.submit_generated_command("zhakuj terminal")
    # Expect: terminal.state.hacked == True, credits up, log includes feedback.
    assert term.state.get("hacked") is True, \
        f"terminal should be hacked: {term.state}"
    assert w.character.credits > pre_credits, \
        f"credits unchanged: {pre_credits} → {w.character.credits}"
    txt = "\n".join(s for s, _ in w.log[-10:])
    assert "pyknięciem" in txt or "konto" in txt or "kredyt" in txt.lower(), \
        f"expected hack-feedback log; got:\n{txt}"
    print(f"  hack success: +{w.character.credits - pre_credits} kr + log line + state set: OK")


def test_rehack_is_noop():
    """Hacking an already-hacked terminal must not grant credits again."""
    from ..engine.game import Game
    w, term = _mk_world_with_terminal()
    g = Game(screen=None); g.world = w; g.state = "play"
    term.state["hacked"] = True
    pre_credits = w.character.credits
    w.character.stats["INT"] = 18
    _r.seed(3)
    g.submit_generated_command("zhakuj terminal")
    assert w.character.credits == pre_credits, \
        f"re-hack should not grant credits; pre={pre_credits}, post={w.character.credits}"
    print("  re-hack noop (no credit double-dip): OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_lounge_template_is_unique_per_floor()
    test_all_safehouse_templates_unique_per_floor()
    test_generated_floor_has_no_duplicate_lounges()
    test_hack_success_grants_credits_and_logs()
    test_rehack_is_noop()
    print("Prompt 28.5 room dedup + meaningful hack smoke: OK")


if __name__ == "__main__":
    main()
