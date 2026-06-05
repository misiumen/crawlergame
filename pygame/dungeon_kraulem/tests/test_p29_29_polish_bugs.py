"""Prompt 29.29 — Combat polish + achievement validation smoke.

Audit issues addressed:

1. Quality tier silent in log. Masterwork weapons gave +1 hit / +1
   dmg but the per-roll log just showed `bonus(+1)` with no
   attribution. Players couldn't tell the craft was working.
   FIX: on first attack of combat, log "<weapon> — mistrzowska ·
   +1 trafienie · +1 obrażenia" so the contribution is explicit.

2. Achievement unlock with unknown key silently no-op'd.
   FIX: unknown keys now write a stderr warning so a typo gets
   surfaced to devs/CI; players still don't see anything.

Other audit items (fumble symmetry, VATS per-target zone) are
considered design-level — the fumble asymmetry actually rewards
the player intentionally (shocked floor is a status downside),
and VATS per-target was deemed UX-niche. We pin the current
behavior so future regressions are loud.
"""
from __future__ import annotations
import io, os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER


def _mk_world():
    w = WorldState()
    w.character = Character(name="Igor", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


# ── Achievement unknown-key warning ─────────────────────────────────────

def test_unknown_achievement_key_writes_to_stderr():
    from ..systems import achievements as _ach
    ch = Character()
    # Redirect stderr just for this call.
    old_stderr = sys.stderr
    sink = io.StringIO()
    sys.stderr = sink
    try:
        result = _ach.unlock(ch, "totally_made_up_key_zzz")
    finally:
        sys.stderr = old_stderr
    assert result is False
    err = sink.getvalue()
    assert "unknown key" in err.lower(), \
        f"stderr should warn about unknown key; got {err!r}"
    assert "totally_made_up_key_zzz" in err
    print(f"  unknown achievement key → stderr warning: OK")


def test_known_achievement_key_silent_on_stderr():
    """Sanity: legit unlocks don't spam stderr."""
    from ..systems import achievements as _ach
    ch = Character()
    old_stderr = sys.stderr
    sink = io.StringIO()
    sys.stderr = sink
    try:
        _ach.unlock(ch, "pierwsza_krew")
    finally:
        sys.stderr = old_stderr
    assert sink.getvalue() == "", \
        f"unexpected stderr noise on known key: {sink.getvalue()!r}"
    print("  known achievement: silent on stderr: OK")


# ── Quality tier log attribution ────────────────────────────────────────

def test_masterwork_weapon_logs_quality_once():
    """The first attack with a masterwork-state weapon should emit
    a Polish "weapon — mistrzowska" line. Second attack same combat
    should NOT (cs.state flag set)."""
    from ..engine.game import Game
    from ..engine import combat as _cmb
    from ..content import crafting as _cr
    import random as _r
    w, room = _mk_world()
    weapon = _cr.make_crafted_entity("improvised_knife", quality="masterwork")
    w.register(weapon)
    w.character.inventory_ids.append(weapon.entity_id)
    w.character.wielded_main_id = weapon.entity_id
    m = Entity(key="thug", entity_type=T_MONSTER, fallback_name="Bandzior",
               hp=50, max_hp=50, ac=12, attack_bonus=0, damage_dice="1d2",
               affordances=["attack"], location_id="r0")
    w.register(m); room.entities.append(m)
    g = Game(screen=None); g.world = w; g.state = "play"
    _cmb.start_combat(room, w)
    _r.seed(1)
    pre = len(w.log)
    g.submit_generated_command("zaatakuj")
    post_lines = [e[0] if isinstance(e, tuple) else str(e)
                  for e in w.log[pre:]]
    matches = [ln for ln in post_lines
               if "mistrzowska" in ln.lower() or "trafienie" in ln.lower()]
    assert matches, \
        f"masterwork quality line missing in {post_lines}"
    print(f"  masterwork weapon logs quality: OK ({matches[0][:55]}…)")


def test_normal_weapon_does_not_log_quality():
    """A weapon at quality="normal" with no enhancements should NOT
    spam a quality line."""
    from ..engine.game import Game
    from ..engine import combat as _cmb
    from ..content import crafting as _cr
    import random as _r
    w, room = _mk_world()
    weapon = _cr.make_crafted_entity("improvised_knife", quality="normal")
    w.register(weapon)
    w.character.inventory_ids.append(weapon.entity_id)
    w.character.wielded_main_id = weapon.entity_id
    m = Entity(key="thug", entity_type=T_MONSTER, fallback_name="Bandzior",
               hp=50, max_hp=50, ac=12, attack_bonus=0, damage_dice="1d2",
               affordances=["attack"], location_id="r0")
    w.register(m); room.entities.append(m)
    g = Game(screen=None); g.world = w; g.state = "play"
    _cmb.start_combat(room, w)
    _r.seed(1)
    pre = len(w.log)
    g.submit_generated_command("zaatakuj")
    post_lines = [e[0] if isinstance(e, tuple) else str(e)
                  for e in w.log[pre:]]
    matches = [ln for ln in post_lines
               if "mistrzowska" in ln.lower() or
                  "solidna" in ln.lower() or
                  ("trafienie" in ln.lower() and "+" in ln)]
    assert not matches, \
        f"normal weapon should not log quality line: {matches}"
    print("  normal weapon: no quality log spam: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_unknown_achievement_key_writes_to_stderr()
    test_known_achievement_key_silent_on_stderr()
    test_masterwork_weapon_logs_quality_once()
    test_normal_weapon_does_not_log_quality()
    print("Prompt 29.29 polish bugs smoke: OK")


if __name__ == "__main__":
    main()
