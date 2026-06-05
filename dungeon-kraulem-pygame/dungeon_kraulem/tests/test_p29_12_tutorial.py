"""Prompt 29.12 — Floor 1 tutorial / onboarding tips smoke suite.

Audit finding: sponsor attention, threat escalation, fog-of-war,
VATS, save slots, drop pods, and last-stand are all opaque to a new
player. Tasks #73 + #74 sat pending since P27. P29.12 adds a
lightweight in-log tutorial that fires once per character at
context-relevant trigger points.

Covers:
  * TIPS catalog has Polish entries for the key mechanics.
  * try_show_tip is no-op when world has no character.
  * try_show_tip emits a log line + stamps tutorial_seen flag.
  * Calling try_show_tip a second time is a no-op (flag honors).
  * Tips only fire on floor 1 unless `force_any_floor=True`.
  * is_disabled gates everything when set.
  * Welcome tip fires from start_new_game flow.
  * sprawdź on unknown emits fog_of_war tip the first time.
  * Tutorial flags persist via Character save/load.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER
from ..engine import tutorial as _tut


def _mk_world(floor=1):
    w = WorldState()
    w.character = Character(name="Igor", background="janitor")
    f = FloorState(floor_id="f1", floor_number=floor)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


# ── Catalog + basic API ─────────────────────────────────────────────────

def test_tips_catalog_has_polish_text():
    for key in ("welcome", "fog_of_war", "sponsors", "threat",
                "combat_vats", "save_slots", "drop_pods", "low_hp",
                "trap_deploy", "descend"):
        assert key in _tut.TIPS, f"missing tip key: {key}"
        txt = _tut.TIPS[key]
        # Sanity: Polish accented chars or known Polish words.
        assert any(ch in txt for ch in "ąćęłńóśźż") or "się" in txt, \
            f"tip {key} doesn't look Polish: {txt!r}"
    print(f"  {len(_tut.TIPS)} tips in catalog, all Polish: OK")


def test_try_show_tip_noop_without_character():
    # An empty WorldState (no character) should silently no-op.
    w = WorldState()
    assert _tut.try_show_tip(w, "welcome") is False
    print("  try_show_tip noop without character: OK")


def test_try_show_tip_emits_log_and_stamps_flag():
    w, _r = _mk_world(floor=1)
    assert _tut.has_seen(w, "welcome") is False
    ok = _tut.try_show_tip(w, "welcome")
    assert ok is True
    assert _tut.has_seen(w, "welcome") is True
    # Log line should mention TUTORIAL.
    last = w.log[-1] if w.log else ("", "")
    text = last[0] if isinstance(last, tuple) else str(last)
    assert "TUTORIAL" in text, f"log line missing TUTORIAL prefix: {text!r}"
    print(f"  tip fires + stamps flag + log line: OK ({text[:50]}…)")


def test_try_show_tip_only_once():
    w, _r = _mk_world(floor=1)
    _tut.try_show_tip(w, "welcome")
    pre_len = len(w.log)
    fired = _tut.try_show_tip(w, "welcome")
    assert fired is False
    assert len(w.log) == pre_len, "tip re-emitted to log"
    print("  tip fires once, second call is noop: OK")


# ── Floor gating ─────────────────────────────────────────────────────────

def test_tip_gated_to_floor_1_by_default():
    w, _r = _mk_world(floor=3)
    fired = _tut.try_show_tip(w, "welcome")
    assert fired is False, "tip should NOT fire past floor 1 by default"
    # force_any_floor unlocks.
    fired2 = _tut.try_show_tip(w, "welcome", force_any_floor=True)
    assert fired2 is True
    print("  floor-1 gating works; force_any_floor overrides: OK")


def test_disabled_flag_suppresses_all_tips():
    w, _r = _mk_world(floor=1)
    w.character.flags = {"tutorial_disabled": True}
    fired = _tut.try_show_tip(w, "welcome")
    assert fired is False
    print("  tutorial_disabled flag suppresses tips: OK")


# ── Integration: welcome tip fires from start_new_game ─────────────────

def test_welcome_tip_fires_on_new_game():
    from ..engine.game import Game
    g = Game(screen=None)
    g.start_new_game("TestPlayer", "janitor")
    assert g.world is not None
    assert _tut.has_seen(g.world, "welcome"), \
        "welcome tip should fire from start_new_game"
    # Save slots tip too.
    assert _tut.has_seen(g.world, "save_slots")
    print("  start_new_game fires welcome + save_slots tips: OK")


# ── Integration: sprawdź triggers fog_of_war tip ────────────────────────

def test_sprawdz_fires_fog_of_war_tip():
    from ..engine.game import Game
    w, r = _mk_world(floor=1)
    m = Entity(key="thug", entity_type=T_MONSTER, fallback_name="Bandzior",
               hp=80, max_hp=80, ac=11, affordances=["attack","inspect"],
               tags=["monster","humanoid"], location_id="r0")
    w.register(m); r.entities.append(m)
    g = Game(screen=None); g.world = w; g.state = "play"
    assert not _tut.has_seen(w, "fog_of_war")
    g.submit_generated_command("sprawdź Bandzior")
    assert _tut.has_seen(w, "fog_of_war"), \
        "first sprawdź should fire fog_of_war tip"
    print("  sprawdź on unknown fires fog_of_war tip: OK")


# ── Save / load preserves tutorial flags ─────────────────────────────────

def test_tutorial_flags_survive_round_trip():
    w, _r = _mk_world(floor=1)
    _tut.try_show_tip(w, "welcome")
    _tut.try_show_tip(w, "sponsors")
    d = w.character.to_dict()
    c2 = Character.from_dict(d)
    assert c2.flags.get("tutorial_seen_welcome") is True
    assert c2.flags.get("tutorial_seen_sponsors") is True
    print("  tutorial flags round-trip via Character save/load: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_tips_catalog_has_polish_text()
    test_try_show_tip_noop_without_character()
    test_try_show_tip_emits_log_and_stamps_flag()
    test_try_show_tip_only_once()
    test_tip_gated_to_floor_1_by_default()
    test_disabled_flag_suppresses_all_tips()
    test_welcome_tip_fires_on_new_game()
    test_sprawdz_fires_fog_of_war_tip()
    test_tutorial_flags_survive_round_trip()
    print("Prompt 29.12 tutorial smoke: OK")


if __name__ == "__main__":
    main()
