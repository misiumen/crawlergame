"""Prompt 27 — Show Layer + Floor 2 smoke suite.

Covers:
  * LLM mode UI removed from settings (4 rows, not 5)
  * DCC main menu draws without crash at multiple resolutions
  * Viewer HUD: audience_history tracked across change_audience writes
  * Sponsor voice bus: maybe_speak fires for primary sponsor on
    tag-weight≥2 events
  * Sponsor voice cooldown enforced (no chatter twice within window)
  * Inventory tab now has Załóż verb for wearables, Dobądź for weapons
  * Audio play_sfx silent-no-ops when audio not initialized (asset
    files missing is fine)
  * Floor 2 builds + has correct sponsor + has floor_min:2 monsters
  * Descent: from floor 1 exit → floor 2 (or onward)
  * Floor 2 boss + minibosses are tagged with miniboss/floor_boss
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import random as _r

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))


# ── LLM removal ────────────────────────────────────────────────────────

def test_settings_has_4_rows_not_5():
    """LLM mode row removed; settings draws with 4 rows now."""
    from ..engine.game import Game
    g = Game(screen=pygame.display.get_surface())
    g.state = "settings"
    g.settings_state = {"row": 0, "res_idx": 0, "fullscreen": False, "llm_idx": 0}
    g.draw()
    # Hit Up from row 0 — should wrap to row 3 (4 rows total: 0..3).
    class _Ev: pass
    ev = _Ev(); ev.key = pygame.K_UP
    g.handle_keydown(ev)
    assert g.settings_state["row"] == 3, \
        f"expected wrap to row 3, got {g.settings_state['row']}"
    print("  settings has 4 rows (LLM row hidden): OK")


# ── Main menu ─────────────────────────────────────────────────────────

def test_main_menu_draws_at_resolutions():
    from ..ui.ui import draw_title
    for w, h in ((1280, 720), (1920, 1080), (3440, 1440)):
        pygame.display.set_mode((w, h))
        surf = pygame.display.get_surface()
        draw_title(surf, save_exists=False, selected_idx=0)
        draw_title(surf, save_exists=True, selected_idx=2)
    print("  DCC main menu draws at 3 resolutions: OK")


# ── Viewer HUD ────────────────────────────────────────────────────────

def test_audience_history_tracks():
    from ..engine.game import Game
    from ..engine import audience as _aud
    pygame.display.set_mode((1280, 720))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    _aud.change_audience(g.world, 5)
    _aud.change_audience(g.world, -2)
    _aud.change_audience(g.world, 3)
    hist = getattr(g.world, "audience_history", None) or []
    assert len(hist) == 3, f"expected 3 entries, got {len(hist)}"
    print(f"  audience_history tracks {len(hist)} changes: OK")


def test_audience_history_bounded():
    from ..engine.game import Game
    from ..engine import audience as _aud
    pygame.display.set_mode((1280, 720))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    for _ in range(50):
        _aud.change_audience(g.world, 1)
    hist = g.world.audience_history
    assert len(hist) <= 32, f"history should cap at 32, got {len(hist)}"
    print(f"  audience_history bounded to {len(hist)}: OK")


# ── Sponsor voice bus ─────────────────────────────────────────────────

def test_sponsor_voice_fires_with_low_roll():
    from ..engine.game import Game
    from ..engine import sponsor_voice as _sv
    pygame.display.set_mode((1280, 720))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    # Use a forced-low RNG that ALWAYS rolls 0.0 so the probability
    # gate definitely passes. Then test the quip lands.
    class _ForceLow:
        def random(self): return 0.0
        def choice(self, seq): return seq[0]
    pre = sum(1 for s, c in g.world.log if c == "syndicate")
    _sv.maybe_speak(g.world, "kill_lethal", weight=3, rng=_ForceLow())
    post_lines = [s for s, c in g.world.log if c == "syndicate"]
    assert len(post_lines) > pre, \
        f"expected a new syndic line after forced-low roll; got {len(post_lines)}"
    # The new line should be the quip format: `SponsorName: „...”`.
    new_line = post_lines[-1]
    assert "„" in new_line and ":" in new_line, \
        f"expected quip format, got: {new_line!r}"
    print(f"  sponsor voice fires: OK ('{new_line[:60]}…')")


def test_sponsor_voice_cooldown_blocks_second_speak():
    from ..engine.game import Game
    from ..engine import sponsor_voice as _sv
    pygame.display.set_mode((1280, 720))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    class _ForceLow:
        def random(self): return 0.0
        def choice(self, seq): return seq[0]
    rng = _ForceLow()
    _sv.maybe_speak(g.world, "kill_lethal", weight=3, rng=rng)
    syndic_count_1 = sum(1 for s, c in g.world.log if c == "syndicate")
    # Second call within cooldown — should NOT add a new line.
    _sv.maybe_speak(g.world, "kill_lethal", weight=3, rng=rng)
    syndic_count_2 = sum(1 for s, c in g.world.log if c == "syndicate")
    assert syndic_count_2 == syndic_count_1, \
        f"cooldown failed: {syndic_count_1} → {syndic_count_2}"
    print("  sponsor voice cooldown blocks rapid re-speak: OK")


def test_sponsor_voice_below_weight_threshold_silent():
    from ..engine.game import Game
    from ..engine import sponsor_voice as _sv
    pygame.display.set_mode((1280, 720))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    pre = sum(1 for s, c in g.world.log if c == "syndicate")
    # Weight 1 = trivial; should NOT trigger voice.
    _sv.maybe_speak(g.world, "kill_lethal", weight=1, rng=_r.Random(0))
    post = sum(1 for s, c in g.world.log if c == "syndicate")
    assert pre == post, "weight<2 must not trigger voice"
    print("  sponsor voice silent below weight threshold: OK")


# ── Inventory verbs ───────────────────────────────────────────────────

def test_inventory_tab_has_wear_verb_for_wearable():
    from ..ui import ui_nav
    from ..engine.world import WorldState
    from ..engine.character import Character
    from ..engine.floor import FloorState
    from ..engine.room import RoomState
    from ..content.items import make_item
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    helmet = make_item("helm_konstrukcyjny", location_id="inventory:player")
    w.register(helmet)
    w.character.inventory_ids.append(helmet.entity_id)
    state = ui_nav.build_play_options(w)
    # Focus the helmet so we see its verb list.
    state.set_focused_subject(ui_nav.GROUP_INVENTORY, str(helmet.entity_id))
    state2 = ui_nav.build_play_options(w, prev_state=state)
    labels = [o.label for o in state2.options_in(ui_nav.GROUP_INVENTORY)]
    assert any("Załóż" in l for l in labels), \
        f"expected Załóż verb, got {labels}"
    print(f"  inventory tab has Załóż for wearable: OK ({labels})")


# ── Audio ─────────────────────────────────────────────────────────────

def test_audio_play_sfx_no_op_when_missing():
    """No crash when SFX file doesn't exist — silently skips."""
    from ..ui import audio
    # Don't initialize; play should noop without error.
    audio.play_sfx("definitely_not_a_real_sfx_xyz")
    print("  audio.play_sfx silent no-op when missing: OK")


# ── Floor 2 build ─────────────────────────────────────────────────────

def test_floor_2_builds_with_correct_sponsor():
    from ..engine.game import Game
    from ..engine.floor_generator import generate_floor
    pygame.display.set_mode((1280, 720))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    f2 = generate_floor(g.world, floor_number=2)
    assert f2.floor_number == 2
    # Floor 2 sponsor is Sponsor Bezpieczeństwa Sportu.
    assert "sport" in f2.sponsor_key.lower(), \
        f"expected sport sponsor for F2, got {f2.sponsor_key}"
    assert len(f2.rooms) >= 8, f"F2 should have ≥8 rooms, got {len(f2.rooms)}"
    print(f"  Floor 2 built: {len(f2.rooms)} rooms, sponsor={f2.sponsor_key}: OK")


def test_floor_2_has_floor_min_2_monsters_in_pool():
    from ..content.data.entity_templates import MON
    f2_keys = [k for k, v in MON.items()
               if "floor_min:2" in (v.get("tags") or [])]
    assert len(f2_keys) >= 4, \
        f"expected ≥4 Floor 2-tagged monsters, got {f2_keys}"
    print(f"  Floor 2-tagged monsters: {len(f2_keys)} ({f2_keys[:4]}…): OK")


def test_floor_2_has_minibosses_and_boss():
    from ..content.data.entity_templates import MON
    minibosses = [k for k, v in MON.items()
                  if "miniboss" in (v.get("tags") or [])
                  and "floor_min:2" in (v.get("tags") or [])]
    bosses = [k for k, v in MON.items()
              if ("boss" in (v.get("tags") or [])
                  or "floor_boss" in (v.get("tags") or []))
              and "floor_min:2" in (v.get("tags") or [])]
    assert len(minibosses) >= 2, \
        f"DCC convention: ≥2 minibosses per floor, got {minibosses}"
    assert len(bosses) >= 1, \
        f"DCC convention: 1 boss guards exit, got {bosses}"
    print(f"  Floor 2: {len(minibosses)} miniboss(es) + {len(bosses)} boss: OK")


# ── Descent flow ──────────────────────────────────────────────────────

def test_descent_advances_floor_number():
    from ..engine.game import Game
    pygame.display.set_mode((1280, 720))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    f = g.world.current_floor
    # Force "at unlocked exit" state.
    f.current_room_id = f.exit_room_ids[0] if f.exit_room_ids else f.start_room_id
    f.exits_unlocked.add("boss_defeated")
    pre_floor = g.world.floor_number
    g._descend_or_win()
    assert g.world.floor_number == pre_floor + 1
    assert g.world.current_floor.floor_number == pre_floor + 1
    print(f"  descent: floor {pre_floor} → {g.world.floor_number}: OK")


def test_descent_resets_context_pronoun_state():
    from ..engine.game import Game
    pygame.display.set_mode((1280, 720))
    g = Game(screen=pygame.display.get_surface())
    g.start_new_game("Tester", "janitor")
    g.world.last_player_command = "sprawdź monitor"
    g.world.last_targeted_entity_id = 42
    f = g.world.current_floor
    f.current_room_id = f.exit_room_ids[0] if f.exit_room_ids else f.start_room_id
    f.exits_unlocked.add("boss_defeated")
    g._descend_or_win()
    assert g.world.last_player_command == ""
    assert g.world.last_targeted_entity_id is None
    print("  descent resets context pronouns: OK")


# ── Suite ──────────────────────────────────────────────────────────────

def main():
    test_settings_has_4_rows_not_5()
    test_main_menu_draws_at_resolutions()
    test_audience_history_tracks()
    test_audience_history_bounded()
    test_sponsor_voice_fires_with_low_roll()
    test_sponsor_voice_cooldown_blocks_second_speak()
    test_sponsor_voice_below_weight_threshold_silent()
    test_inventory_tab_has_wear_verb_for_wearable()
    test_audio_play_sfx_no_op_when_missing()
    test_floor_2_builds_with_correct_sponsor()
    test_floor_2_has_floor_min_2_monsters_in_pool()
    test_floor_2_has_minibosses_and_boss()
    test_descent_advances_floor_number()
    test_descent_resets_context_pronoun_state()
    print("Prompt 27 show layer + Floor 2 smoke: OK")


if __name__ == "__main__":
    main()
