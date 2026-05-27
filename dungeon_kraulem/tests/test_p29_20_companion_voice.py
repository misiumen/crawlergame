"""Prompt 29.20 — Companion narrative arc smoke suite.

Audit finding: the Companion data model (bond/stress fields,
10-pet catalog) was paper. No chatter, no narrative arc — the
pet just existed as a stat-stick. P29.20 adds:
  * engine/companion_voice.py — chatter pool by trigger × bond band
  * 6 trigger sites in game.py + time_system.py
  * a flagship DCC-flavor talking parrot (papuga_anty_host)

Covers:
  * maybe_say is no-op when no active pet.
  * maybe_say emits a Polish line when a pet exists.
  * Bond bands route to different lines (estranged vs devoted).
  * Cooldown gates repeat fires of the same trigger.
  * Per-pet OVERRIDE lines win over the generic pool.
  * Flagship parrot helper creates a Companion with the right key.
  * Enemy kill triggers chatter via _apply_attack.
  * Sponsor pod open triggers chatter.
  * player_death force=True bypasses cooldown.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine import companion as _comp
from ..engine import companion_voice as _cv


def _mk_world():
    w = WorldState()
    w.character = Character(name="Igor", background="janitor")
    f = FloorState(floor_id="f1", floor_number=2)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


def _give_pet(w, *, bond: int = 5, species_key: str = "gees"):
    pet = _comp.Companion(
        kind=_comp.KIND_PET,
        species_key=species_key,
        display_name_pl="Gęś",
        bond=bond,
        stress=0,
        tags=["bird"],
        abilities=["scout_aerial"],
    )
    _comp.register_companion(w, pet)
    return pet


# ── Basic emission ──────────────────────────────────────────────────────

def test_no_pet_means_silent():
    w, _r = _mk_world()
    out = _cv.maybe_say(w, "combat_start", force=True)
    assert out is None
    print("  no active pet → maybe_say returns None: OK")


def test_emits_polish_line_when_pet_present():
    w, _r = _mk_world()
    _give_pet(w, bond=5)
    out = _cv.maybe_say(w, "combat_start", force=True)
    assert out is not None
    assert any(ch in out for ch in "ąćęłńóśźż") or "zwierzę" in out, \
        f"line doesn't look Polish: {out!r}"
    # And the world.log got the line.
    assert any(out in entry[0] for entry in w.log[-3:]), \
        f"line not in world.log: {w.log[-3:]}"
    print(f"  pet emits Polish line: OK ({out[:55]}…)")


# ── Bond bands route differently ────────────────────────────────────────

def test_bond_estranged_vs_devoted_routes_different_pools():
    """At bond 0 the line should differ from bond 10 (same trigger).
    We can't assert exact strings, but we can assert the two lines
    are NOT the same — and that each falls in its band's pool."""
    w_a, _r = _mk_world()
    _give_pet(w_a, bond=0)
    line_estranged = _cv.maybe_say(w_a, "hp_low", force=True)
    w_b, _r = _mk_world()
    _give_pet(w_b, bond=10)
    line_devoted = _cv.maybe_say(w_b, "hp_low", force=True)
    assert line_estranged is not None
    assert line_devoted is not None
    assert line_estranged != line_devoted, \
        "bond bands should pick different lines"
    # Estranged lines are in the 0-2 bracket of _LINES.
    estranged_pool = [ln for trig, lo, hi, ln in _cv._LINES
                      if trig == "hp_low" and lo <= 2]
    devoted_pool = [ln for trig, lo, hi, ln in _cv._LINES
                    if trig == "hp_low" and hi >= 10 and lo >= 7]
    assert line_estranged in estranged_pool, \
        f"estranged line outside its pool: {line_estranged}"
    assert line_devoted in devoted_pool, \
        f"devoted line outside its pool: {line_devoted}"
    print("  bond band routes differ between estranged + devoted: OK")


# ── Cooldown gating ────────────────────────────────────────────────────

def test_cooldown_blocks_repeat_fires():
    w, _r = _mk_world()
    _give_pet(w, bond=5)
    a = _cv.maybe_say(w, "combat_start")
    b = _cv.maybe_say(w, "combat_start")
    assert a is not None
    assert b is None, "second fire within cooldown should noop"
    # Advance time past cooldown.
    w.current_floor.current_minute += 30
    c = _cv.maybe_say(w, "combat_start")
    assert c is not None
    print("  cooldown gates repeat chatter: OK")


def test_force_bypasses_cooldown():
    w, _r = _mk_world()
    _give_pet(w, bond=5)
    _cv.maybe_say(w, "player_death", force=True)
    out = _cv.maybe_say(w, "player_death", force=True)
    assert out is not None, "force should bypass cooldown"
    print("  force=True bypasses cooldown: OK")


# ── Overrides ───────────────────────────────────────────────────────────

def test_flagship_parrot_uses_override_lines():
    """The papuga_anty_host species has its OWN per-trigger lines
    that should win over the generic pool. Verify a sponsor_pod_open
    chatter from the parrot is the override-pool line."""
    w, _r = _mk_world()
    _cv.add_flagship_pet(w)
    out = _cv.maybe_say(w, "sponsor_pod_open", force=True)
    assert out is not None
    # Override line for the parrot mentions "Papuga".
    assert "Papuga" in out, \
        f"parrot override should label with 'Papuga': {out!r}"
    print(f"  flagship parrot override line: OK ({out[:55]}…)")


def test_add_flagship_pet_registers_companion():
    w, _r = _mk_world()
    pet = _cv.add_flagship_pet(w)
    assert pet is not None
    assert pet.species_key == "papuga_anty_host"
    assert pet.bond == 7
    # Should be picked up as the active pet.
    assert _comp.active_pet(w) is pet
    print("  flagship helper registers + bond=7: OK")


# ── Integration: kill chatter fires through real combat ─────────────────

def test_enemy_kill_emits_chatter():
    from ..engine.game import Game
    from ..engine import combat as _cmb
    from ..engine.entity import Entity, T_MONSTER
    import random as _r
    w, room = _mk_world()
    _give_pet(w, bond=9)
    m = Entity(key="thug", entity_type=T_MONSTER, fallback_name="Bandzior",
               hp=1, max_hp=1, ac=5, attack_bonus=0, damage_dice="1d2",
               affordances=["attack"], location_id="r0")
    w.register(m); room.entities.append(m)
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.stats["STR"] = 25
    _cmb.start_combat(room, w)
    _r.seed(7)
    pre_log_len = len(w.log)
    g.submit_generated_command("zaatakuj")
    # After the kill, at least one log line must mention "zwierzę"
    # (companion chatter) OR be a Polish line — relax to existence
    # of any new log entries.
    assert len(w.log) > pre_log_len, "kill should produce log entries"
    # Look for either generic ("zwierzę") or override ("Papuga") in
    # newly added lines.
    found = False
    for entry in w.log[pre_log_len:]:
        text = (entry[0] if isinstance(entry, tuple) else str(entry)).lower()
        if "zwierzę" in text or "papuga" in text:
            found = True
            break
    assert found, \
        f"no companion chatter found; lines={[e[0] for e in w.log[pre_log_len:]]}"
    print("  enemy kill triggers companion chatter: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_no_pet_means_silent()
    test_emits_polish_line_when_pet_present()
    test_bond_estranged_vs_devoted_routes_different_pools()
    test_cooldown_blocks_repeat_fires()
    test_force_bypasses_cooldown()
    test_flagship_parrot_uses_override_lines()
    test_add_flagship_pet_registers_companion()
    test_enemy_kill_emits_chatter()
    print("Prompt 29.20 companion narrative arc smoke: OK")


if __name__ == "__main__":
    main()
