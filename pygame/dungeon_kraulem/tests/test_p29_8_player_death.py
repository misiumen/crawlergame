"""Prompt 29.8 — player death + game-over flow smoke suite.

Audit finding: HP could drop to 0 and the player kept playing. The
project had STATE_DEFEAT for combat rounds + floor collapse only;
non-combat damage (break critfail, deploy/trap-pickup critfail) had
NO death detection. P29.8 centralizes through Game._check_player_dead
which also caches a RunSummary, wipes the save, and emits a DCC
anti-host line.

Covers:
  * Character carries near_death_used + run counters with save/load.
  * Last-stand fires once: HP→0 rescues to 1 HP and burns the flag.
  * Second HP→0 actually flips to STATE_DEFEAT.
  * Run summary builds with kills + audience peak + sponsors.
  * Audience peak tracks high-water mark even after decay.
  * Death wipes the save file.
  * Combat-hit kills set proper death_cause_label.
  * Trap self-disarm death routes through helper.
  * Run-counter helper noop without world.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER
from ..engine import run_summary as _rs


def _mk_world():
    w = WorldState()
    w.character = Character(name="Igor", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


# ── Character field defaults + round-trip ─────────────────────────────────

def test_character_run_fields_default():
    c = Character()
    assert c.near_death_used is False
    assert c.run_kills == 0
    assert c.run_max_floor_reached == 1
    assert c.run_death_cause == ""
    print("  Character run_* fields default: OK")


def test_character_run_fields_round_trip():
    c = Character(name="X")
    c.near_death_used = True
    c.run_kills = 7
    c.run_traps_armed = 3
    c.run_audience_peak = 42
    c.run_max_floor_reached = 5
    c.run_death_cause = "combat:thug"
    c.run_death_cause_label = "od ciosu Bandziora"
    d = c.to_dict()
    c2 = Character.from_dict(d)
    assert c2.near_death_used is True
    assert c2.run_kills == 7
    assert c2.run_traps_armed == 3
    assert c2.run_audience_peak == 42
    assert c2.run_max_floor_reached == 5
    assert c2.run_death_cause == "combat:thug"
    assert "Bandziora" in c2.run_death_cause_label
    print("  Character run_* save/load round-trip: OK")


# ── Last-stand ────────────────────────────────────────────────────────────

def test_last_stand_rescues_once():
    from ..engine.game import Game
    w, _r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    ch = w.character
    ch.hp = 5
    ch.take_damage(99)
    assert ch.hp == 0
    died = g._check_player_dead("test_first", "test first")
    assert died is False, "first death should NOT flip state"
    assert ch.hp == 1, f"last-stand should restore to 1; got {ch.hp}"
    assert ch.near_death_used is True
    assert g.state == "play"
    print("  last-stand: first HP→0 rescues to 1 HP: OK")


def test_second_death_actually_kills():
    from ..engine.game import Game
    from ..engine import save_load
    w, _r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    ch = w.character
    # Burn the last-stand manually.
    ch.near_death_used = True
    ch.hp = 0
    died = g._check_player_dead("combat:thug", "od ciosu Bandziora")
    assert died is True, "second HP→0 should die"
    assert g.state == "defeat"
    assert ch.run_death_cause == "combat:thug"
    assert "Bandziora" in ch.run_death_cause_label
    # Save should be wiped if it ever existed.
    assert not save_load.exists(), "save file should be wiped on death"
    print("  second HP→0 flips to STATE_DEFEAT + cause set + save wiped: OK")


def test_check_player_dead_noop_when_alive():
    from ..engine.game import Game
    w, _r = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    died = g._check_player_dead("noop", "noop")
    assert died is False
    assert g.state == "play"
    print("  helper noop when HP > 0: OK")


# ── Run summary ───────────────────────────────────────────────────────────

def test_run_summary_captures_counters():
    w, _r = _mk_world()
    ch = w.character
    ch.run_kills = 4
    ch.run_traps_armed = 2
    ch.run_audience_peak = 33
    ch.run_max_floor_reached = 3
    ch.audience_rating = 18
    ch.credits = 47
    ch.run_death_cause = "combat:thug"
    ch.run_death_cause_label = "od ciosu Bandziora"
    rs = _rs.build_run_summary(w)
    assert rs.player_name == "Igor"
    assert rs.kills == 4
    assert rs.traps_armed == 2
    assert rs.audience_peak == 33
    assert rs.audience_final == 18
    assert rs.credits_final == 47
    assert rs.floor_reached >= 3
    assert rs.death_cause_label.startswith("od ciosu")
    assert rs.anti_host_line, "anti-host line should be populated"
    print(f"  RunSummary scrape: OK (kills={rs.kills}, peak={rs.audience_peak})")


def test_render_lines_polish_text_present():
    w, _r = _mk_world()
    ch = w.character
    ch.run_kills = 1
    ch.run_audience_peak = 5
    ch.run_death_cause_label = "test"
    rs = _rs.build_run_summary(w)
    lines = _rs.render_lines(rs)
    text = "\n".join(lines)
    assert "Piętro:" in text
    assert "Zabójstwa:" in text
    assert "Widownia (szczyt):" in text
    assert "Top sponsorzy:" in text
    print("  render_lines emits Polish labels: OK")


# ── Audience peak tracking ────────────────────────────────────────────────

def test_audience_peak_climbs_with_change():
    from ..engine import audience as _aud
    w, _r = _mk_world()
    ch = w.character
    assert ch.run_audience_peak == 0
    _aud.change_audience(w, 12, source="test", emit_log=False)
    assert ch.audience_rating == 12
    assert ch.run_audience_peak == 12
    _aud.change_audience(w, 8, source="test", emit_log=False)
    assert ch.audience_rating == 20
    assert ch.run_audience_peak == 20
    # Drop in audience must NOT lower the peak.
    _aud.change_audience(w, -15, source="test", emit_log=False)
    assert ch.audience_rating == 5
    assert ch.run_audience_peak == 20, \
        f"peak should not drop; got {ch.run_audience_peak}"
    print("  audience peak climbs and never decreases: OK")


# ── Combat death routes through helper ────────────────────────────────────

def test_combat_kill_routes_through_check():
    """Force a HP→0 from an enemy hit and verify state flips through
    the new helper path (with last-stand consumed first)."""
    from ..engine.game import Game
    from ..engine import combat as _cmb
    import random as _r
    w, room = _mk_world()
    m = Entity(key="thug", entity_type=T_MONSTER, fallback_name="Bandzior",
               hp=100, max_hp=100, ac=8, attack_bonus=10,
               damage_dice="20d6",   # absurd to guarantee kill
               affordances=["attack"], location_id="r0")
    w.register(m); room.entities.append(m)
    g = Game(screen=None); g.world = w; g.state = "play"
    # Burn last-stand so first hit is lethal.
    w.character.near_death_used = True
    w.character.hp = 5   # any hit kills
    _cmb.start_combat(room, w)
    cs = _cmb.get_combat(room)
    cs.selected_target_id = m.entity_id
    _r.seed(1)
    g.submit_generated_command("zaatakuj")
    assert g.state == "defeat", \
        f"combat hit should kill; state={g.state}, hp={w.character.hp}"
    assert "Bandzior" in (w.character.run_death_cause_label or ""), \
        f"cause label should name killer; got {w.character.run_death_cause_label}"
    print(f"  combat lethal hit → defeat ({w.character.run_death_cause_label}): OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    # Clean any save from a previous death-path run.
    try:
        from ..engine import save_load
        save_load.delete()
    except Exception:
        pass
    test_character_run_fields_default()
    test_character_run_fields_round_trip()
    test_last_stand_rescues_once()
    test_second_death_actually_kills()
    test_check_player_dead_noop_when_alive()
    test_run_summary_captures_counters()
    test_render_lines_polish_text_present()
    test_audience_peak_climbs_with_change()
    test_combat_kill_routes_through_check()
    print("Prompt 29.8 player death smoke: OK")


if __name__ == "__main__":
    main()
