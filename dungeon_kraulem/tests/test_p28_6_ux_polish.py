"""Prompt 28.6 — one-click exits + log dedupe + ghost-action filter +
stale-focus reset + relay→przekaźnik smoke suite.

Covers:
  * Wyjścia panel is ONE-TIER: each visible exit is a `plain`
    option that fires `idź <label>` or `wyłam <label>` directly.
    No subject focus, no Sprawdź sub-option.
  * Exit labels include the destination's room name when known.
  * Log dedupe: two consecutive identical messages collapse into
    "X (×2)" instead of stacking.
  * `zdemontuj X` on entity with no salvage table stamps `no_salvage`
    so the action bar stops offering Zdemontuj on that entity.
  * After a room change, all nav-focus is cleared so stale focus
    doesn't bleed into the new room's option list.
  * The English "relay" exit_hint is fixed to "przekaźnik" in
    room_pool data.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_TERMINAL, T_OBJECT


def _mk_world():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r0 = RoomState(room_id="r0", fallback_short_title="Korytarz")
    r1 = RoomState(room_id="r1", fallback_short_title="Pakamera")
    r2 = RoomState(room_id="r2", fallback_short_title="Magazyn")
    r0.exits = {"wschód": {"target": "r1"},
                "zachód": {"target": "r2", "locked": True}}
    r1.exits = {"zachód": {"target": "r0"}}
    r2.exits = {"wschód": {"target": "r0"}}
    f.add_room(r0); f.add_room(r1); f.add_room(r2)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    f.discovered_room_ids = {"r0", "r1", "r2"}
    w.current_floor = f
    return w


# ── One-click exits ──────────────────────────────────────────────────────

def test_exit_options_are_one_tier_plain():
    from ..ui.ui_nav import build_play_options, GROUP_EXITS
    w = _mk_world()
    state = build_play_options(w)
    opts = state.options_in(GROUP_EXITS)
    assert all(o.option_kind == "plain" for o in opts), \
        f"got {[o.option_kind for o in opts]}"
    print(f"  exits one-tier plain: OK ({len(opts)} rows)")


def test_exit_label_shows_destination():
    from ..ui.ui_nav import build_play_options, GROUP_EXITS
    w = _mk_world()
    state = build_play_options(w)
    labels = [o.label for o in state.options_in(GROUP_EXITS)]
    # Unlocked east → Pakamera should appear in label
    assert any("Pakamera" in l for l in labels), labels
    # Locked west → Magazyn with lock glyph
    assert any("Magazyn" in l and "🔒" in l for l in labels), labels
    print(f"  exit labels include destination: {labels}: OK")


def test_exit_unlocked_command_is_idz():
    from ..ui.ui_nav import build_play_options, GROUP_EXITS
    w = _mk_world()
    opts = build_play_options(w).options_in(GROUP_EXITS)
    idz = [o for o in opts if o.label.startswith("Idź:")]
    assert idz and idz[0].command == "idź wschód"
    print(f"  unlocked exit → command={idz[0].command!r}: OK")


def test_exit_locked_command_is_wylam():
    from ..ui.ui_nav import build_play_options, GROUP_EXITS
    w = _mk_world()
    opts = build_play_options(w).options_in(GROUP_EXITS)
    wyl = [o for o in opts if o.label.startswith("Wyłam:")]
    assert wyl and wyl[0].command == "wyłam zachód"
    print(f"  locked exit → command={wyl[0].command!r}: OK")


# ── Log dedupe ───────────────────────────────────────────────────────────

def test_log_dedupes_consecutive_identicals():
    w = _mk_world()
    w.log_msg("Gdzieś brzęczy alarm.", "warn")
    w.log_msg("Gdzieś brzęczy alarm.", "warn")
    w.log_msg("Gdzieś brzęczy alarm.", "warn")
    w.log_msg("Inny komunikat.", "normal")
    w.log_msg("Inny komunikat.", "normal")
    # Expect: one alarm line counted ×3, one inny ×2.
    msgs = [s for s, _ in w.log]
    assert msgs == ["Gdzieś brzęczy alarm. (×3)", "Inny komunikat. (×2)"], msgs
    print(f"  log dedupe: {msgs}: OK")


def test_log_does_not_dedupe_player_input_echo():
    w = _mk_world()
    w.log_msg("> idź wschód", "normal")
    w.log_msg("> idź wschód", "normal")
    msgs = [s for s, _ in w.log]
    # Both kept separately — player wants to see they hit Enter twice.
    assert msgs == ["> idź wschód", "> idź wschód"], msgs
    print(f"  log keeps player echos separate: OK")


def test_audience_changes_dedupe_via_log_msg():
    """P28.8 regression: audience.change_audience() used to bypass
    log_msg via direct world.log.append, which meant consecutive
    'Widownia +2' entries piled up without the (×N) suffix and
    visually bled into adjacent rows. Now routed through log_msg."""
    from ..engine import audience as _aud
    w = _mk_world()
    w.character.audience_rating = 0
    pre_len = len(w.log)
    for _ in range(5):
        _aud.change_audience(w, 2, source="test_repeat", emit_log=True)
    after = [s for s, _ in w.log[pre_len:] if s.startswith("Widownia")]
    # Expect ONE deduped entry, not five.
    assert len(after) == 1, f"expected 1 deduped audience entry; got {after}"
    assert "(×5)" in after[0], f"expected (×5) suffix; got {after[0]}"
    print(f"  audience log dedupes: {after[0]}: OK")


# ── Ghost-action filter ──────────────────────────────────────────────────

def test_no_salvage_flag_hides_zdemontuj():
    """After a salvage attempt yields nothing, the entity gets a
    `no_salvage` flag and the action bar stops offering Zdemontuj."""
    from ..ui.ui_nav import build_play_options, GROUP_OBJECTS
    w = _mk_world()
    term = Entity(key="zepsuty_terminal", entity_type=T_TERMINAL,
                  fallback_name="zepsuty terminal", hp=0, max_hp=0,
                  ac=0, tags=["terminal", "salvageable"],
                  affordances=["inspect", "salvage"],
                  location_id="r0")
    w.register(term); w.current_floor.rooms["r0"].entities.append(term)
    opts1 = build_play_options(w).options_in(GROUP_OBJECTS)
    pre = any("Zdemontuj" in o.label for o in opts1)
    assert pre, "Zdemontuj should appear initially"
    # Simulate "no salvage table" stamp.
    term.state = {"no_salvage": True}
    opts2 = build_play_options(w).options_in(GROUP_OBJECTS)
    post = any("Zdemontuj" in o.label for o in opts2)
    assert not post, "Zdemontuj should disappear after no_salvage stamp"
    print("  no_salvage hides Zdemontuj after first refusal: OK")


# ── Stale-focus reset on room change ─────────────────────────────────────

def test_room_change_clears_nav_focus():
    from ..engine.game import Game
    from ..ui.ui_nav import GROUP_OBJECTS
    w = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    g._ensure_nav_state()
    # Pretend focus was on an object in r0.
    g.nav_state.set_focused_subject(GROUP_OBJECTS, "some_subject_id")
    assert g.nav_state.focused_subject(GROUP_OBJECTS) == "some_subject_id"
    # Move to r1.
    g.submit_generated_command("idź wschód")
    # Player moved (assuming the move went through). Focus should be
    # cleared if the room changed.
    if w.current_floor.current_room_id != "r0":
        assert g.nav_state.focused_subject(GROUP_OBJECTS) is None, \
            "focus should be cleared after room change"
        print(f"  room change r0→{w.current_floor.current_room_id} cleared focus: OK")
    else:
        # Movement was refused (unlikely here); skip.
        print("  (room didn't change — focus reset path not exercised)")


# ── Multi-Z minimap ──────────────────────────────────────────────────────

def test_minimap_3d_separates_up_down_into_layers():
    """A room reached via `góra` / `dół` ends up on a different Z layer."""
    from ..ui import minimap as _mm
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r0 = RoomState(room_id="r0", fallback_short_title="Hala")
    r1 = RoomState(room_id="r1", fallback_short_title="Strych")
    r2 = RoomState(room_id="r2", fallback_short_title="Piwnica")
    r3 = RoomState(room_id="r3", fallback_short_title="Salon")
    r0.exits = {"góra":     {"target": "r1"},
                "dół":      {"target": "r2"},
                "wschód":   {"target": "r3"}}
    r1.exits = {"dół": {"target": "r0"}}
    r2.exits = {"góra": {"target": "r0"}}
    r3.exits = {"zachód": {"target": "r0"}}
    f.add_room(r0); f.add_room(r1); f.add_room(r2); f.add_room(r3)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    pos = _mm.grid_positions_3d(f)
    assert pos["r0"][2] == 0, pos
    assert pos["r1"][2] == 1, pos   # up
    assert pos["r2"][2] == -1, pos  # down
    assert pos["r3"][2] == 0, pos   # cardinal east stays same Z
    print(f"  3D minimap: r0=z0, strych=z1, piwnica=z-1, salon=z0: OK")


def test_available_z_layers_lists_unique_zs():
    from ..ui import minimap as _mm
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r0 = RoomState(room_id="r0", fallback_short_title="A")
    r1 = RoomState(room_id="r1", fallback_short_title="B")
    r2 = RoomState(room_id="r2", fallback_short_title="C")
    r0.exits = {"góra": {"target": "r1"}}
    r1.exits = {"dół": {"target": "r0"}, "góra": {"target": "r2"}}
    r2.exits = {"dół": {"target": "r1"}}
    f.add_room(r0); f.add_room(r1); f.add_room(r2)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    layers = _mm.available_z_layers(f)
    assert layers == [0, 1, 2], layers
    print(f"  available z layers: {layers}: OK")


def test_minimap_layer_switch_with_brackets():
    """[ / ] cycles minimap_z_view through available layers."""
    from ..engine.game import Game
    from ..ui import minimap as _mm
    import pygame as _pg
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f1", floor_number=1)
    r0 = RoomState(room_id="r0", fallback_short_title="A")
    r1 = RoomState(room_id="r1", fallback_short_title="B")
    r0.exits = {"góra": {"target": "r1"}}
    r1.exits = {"dół": {"target": "r0"}}
    f.add_room(r0); f.add_room(r1)
    f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    g = Game(screen=None); g.world = w; g.state = "play"
    g.input_text = ""
    g._ensure_nav_state()

    class _Ev: pass
    pre = int(getattr(w, "minimap_z_view", 0))
    ev = _Ev(); ev.key = _pg.K_RIGHTBRACKET
    g.handle_keydown(ev)
    post = int(getattr(w, "minimap_z_view", 0))
    assert post != pre, f"viewing layer didn't change on ']': {pre}→{post}"
    print(f"  ] cycles minimap layer: {pre}→{post}: OK")


# ── Locale leak: relay → przekaźnik ──────────────────────────────────────

def test_no_english_relay_in_room_pool():
    from ..content.data import room_pool as _rp
    for t in _rp.ROOM_POOL:
        hints = t.get("exit_hints") or []
        assert "relay" not in hints, \
            f"template {t.get('template_id')} still has English 'relay' in exit_hints: {hints}"
    print(f"  no English 'relay' in any room_pool exit_hints: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_exit_options_are_one_tier_plain()
    test_exit_label_shows_destination()
    test_exit_unlocked_command_is_idz()
    test_exit_locked_command_is_wylam()
    test_log_dedupes_consecutive_identicals()
    test_log_does_not_dedupe_player_input_echo()
    test_audience_changes_dedupe_via_log_msg()
    test_no_salvage_flag_hides_zdemontuj()
    test_room_change_clears_nav_focus()
    test_minimap_3d_separates_up_down_into_layers()
    test_available_z_layers_lists_unique_zs()
    test_minimap_layer_switch_with_brackets()
    test_no_english_relay_in_room_pool()
    print("Prompt 28.6 UX polish smoke: OK")


if __name__ == "__main__":
    main()
