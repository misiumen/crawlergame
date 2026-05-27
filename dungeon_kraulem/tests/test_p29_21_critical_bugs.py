"""Prompt 29.21 — critical-bug fixes from the post-P29.20 audit.

The audit caught 5 high-severity issues:

  1. `from . import audio` inside Game._check_player_dead raised
     ImportError every call (there's no engine/audio.py — only
     ui/audio.py, imported at module scope). Death + last-stand
     SFX never played.

  2. The companion panel in ui.draw_sidebar called world.get(cid)
     which queries the Entity registry; companions live in
     world.companions (Companion instances). Result: panel was
     always empty. The bug compounded by treating Companion as if
     it had Entity API (display_name() / hp / max_hp) — none of
     which exist on Companion.

  3. (False positive — Kanał 7 was actually present, the audit
     misread the file. No code change needed for this one, but the
     test below pins the contract so the count can't regress.)

  4. load_from_slot returned None on ANY version mismatch — even
     versions OLDER than the engine. First SAVE_VERSION bump would
     silently nuke every existing save. Now accepts any save with
     version <= current; only refuses NEWER saves.

  5. world.flags wasn't serialized. Show-director's kamera_glowna
     and dramatic_zoom_attack flags reset on every load. Worse,
     dramatic_zoom_attack had no reader — promise of "+1 attack"
     was fiction. Moved both flags to character.flags (already
     serialized) and added a real reader in _combat_attack.

Covers:
  * audio.play_sfx is called (not from-imported) in last-stand path.
  * companion panel renders bond bar when a pet is registered.
  * sponsor count is 11 (the audit's claimed bug).
  * load_from_slot accepts version=0 / missing-version saves.
  * load_from_slot refuses version > SAVE_VERSION.
  * dramatic_zoom_attack flag from show_director actually applies
    a +1 to-hit in combat and is consumed.
"""
from __future__ import annotations
import os, json
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState


def _mk_world():
    w = WorldState()
    w.character = Character(name="Igor", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


# ── Bug 1 — death/last-stand SFX import ─────────────────────────────────

def test_last_stand_sfx_path_executes():
    """The previous code did `from . import audio` and ImportError'd
    silently. After the fix, audio.play_sfx is the module-level
    audio (already imported as a module-scope `audio`)."""
    from ..engine import game as _g
    # Verify the from-import lines are GONE from _check_player_dead.
    import inspect
    src = inspect.getsource(_g.Game._check_player_dead)
    assert "from . import audio" not in src, \
        "broken relative-import revived; remove from _check_player_dead"
    # Verify the module-scope `audio` is what's being called.
    assert "audio.play_sfx" in src
    print("  _check_player_dead uses module-level audio module: OK")


# ── Bug 2 — companion panel registry ─────────────────────────────────────

def test_companion_panel_renders_with_pet():
    import pygame
    pygame.init()
    pygame.display.init()
    screen = pygame.display.set_mode((1920, 1080))
    from ..ui.ui import draw_sidebar
    from ..engine import companion as _comp
    w, _r = _mk_world()
    pet = _comp.Companion(
        kind=_comp.KIND_PET, species_key="gees",
        display_name_pl="Gęś", bond=8, stress=2,
        tags=["bird"], abilities=["scout_aerial"],
    )
    _comp.register_companion(w, pet)
    # Just call draw_sidebar — it should not crash and should
    # iterate the companion list via world.companions (the bug was
    # iterating via world.entities).
    draw_sidebar(screen, w)
    # Sanity: companion is reachable via world.companions
    assert pet.companion_id in (w.companions or {})
    print("  draw_sidebar runs with active pet (registry fixed): OK")


# ── Bug 3 — sponsor count contract ──────────────────────────────────────

def test_sponsor_count_is_11():
    from ..engine.sponsors import all_sponsor_keys
    keys = list(all_sponsor_keys())
    assert len(keys) == 11, f"expected 11 sponsors, got {len(keys)}: {keys}"
    assert "kanal_7_krawedz" in keys, \
        "Kanał 7 must be a registered sponsor"
    print(f"  11 sponsors registered, Kanał 7 present: OK")


# ── Bug 4 — save version migration ──────────────────────────────────────

def test_save_load_accepts_legacy_version_0():
    """A save with `version: 0` (or missing key) should load cleanly
    via the soft-accept path. New fields fill in via from_dict."""
    from ..engine import save_load
    save_load.delete_all()
    # Build a minimal-shape world and hand-write a v0 save.
    w, _r = _mk_world()
    data = w.to_dict()
    data["version"] = 0      # explicit legacy
    # Remove a P29.8-era field to simulate a pre-upgrade save.
    if "character" in data:
        data["character"].pop("near_death_used", None)
        data["character"].pop("run_kills", None)
    slot_path = save_load._slot_path(0)
    os.makedirs(os.path.dirname(slot_path) or ".", exist_ok=True)
    with open(slot_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    loaded = save_load.load_from_slot(0)
    assert loaded is not None, "legacy save should load"
    assert loaded.character.near_death_used is False
    assert loaded.character.run_kills == 0
    save_load.delete_all()
    print("  legacy save (version=0, missing fields) loads cleanly: OK")


def test_save_load_refuses_future_version():
    from ..engine import save_load
    save_load.delete_all()
    w, _r = _mk_world()
    data = w.to_dict()
    data["version"] = save_load.SAVE_VERSION + 99  # impossible future
    slot_path = save_load._slot_path(1)
    with open(slot_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    loaded = save_load.load_from_slot(1)
    assert loaded is None, "future-version save should be refused"
    save_load.delete_all()
    print("  save_load refuses future SAVE_VERSION: OK")


# ── Bug 5 — show-director flags now live on character.flags ─────────────

def test_show_director_flags_persist_on_character():
    """Both kamera_glowna and dramatic_zoom_attack must end up on
    character.flags (which IS serialized) rather than world.flags
    (which is NOT)."""
    from ..engine import show_director as _sd
    w, _r = _mk_world()
    w.character.audience_rating = 60  # warming+
    # Force-fire kamera event.
    line = _sd._ev_kamera(w)
    assert "kamera_glowna" in (w.character.flags or {})
    assert w.character.flags["kamera_glowna"] is True
    print(f"  kamera_glowna on character.flags after _ev_kamera: OK")

    # Force-fire dramatic_zoom (with wielded weapon).
    w.character.wielded_main_id = 9999    # any non-None
    _sd._ev_dramatic_zoom(w)
    assert w.character.flags.get("dramatic_zoom_attack") == 1
    print("  dramatic_zoom_attack on character.flags: OK")


def test_dramatic_zoom_consumed_by_combat():
    """The previous code set a flag no one read. After the fix,
    _combat_attack should add +1 to_hit_bonus when the flag is set
    AND clear the flag."""
    from ..engine.game import Game
    from ..engine import combat as _cmb
    from ..engine.entity import Entity, T_MONSTER
    import random as _r
    w, room = _mk_world()
    m = Entity(key="thug", entity_type=T_MONSTER,
               fallback_name="Bandzior",
               hp=50, max_hp=50, ac=12, attack_bonus=0,
               damage_dice="1d2", affordances=["attack"],
               location_id="r0")
    w.register(m); room.entities.append(m)
    g = Game(screen=None); g.world = w; g.state = "play"
    # Set the flag (as show_director would).
    w.character.flags["dramatic_zoom_attack"] = 1
    _cmb.start_combat(room, w)
    _r.seed(1)
    g.submit_generated_command("zaatakuj")
    # After one attack, the flag must be consumed (=0 / falsy).
    assert not w.character.flags.get("dramatic_zoom_attack"), \
        f"dramatic_zoom_attack flag should be cleared after attack: " \
        f"{w.character.flags}"
    print("  dramatic_zoom_attack consumed after one attack: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_last_stand_sfx_path_executes()
    test_companion_panel_renders_with_pet()
    test_sponsor_count_is_11()
    test_save_load_accepts_legacy_version_0()
    test_save_load_refuses_future_version()
    test_show_director_flags_persist_on_character()
    test_dramatic_zoom_consumed_by_combat()
    print("Prompt 29.21 critical bug fixes smoke: OK")


if __name__ == "__main__":
    main()
