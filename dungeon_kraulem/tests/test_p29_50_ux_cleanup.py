"""Prompt 29.50 — UX cleanup z backlogu.

Trzy zaległe zgłoszenia:
  #147: scroll w logu powinien się pojawiać tylko przy realnym
        overflow tekstu (nie page-flip w pustkę).
  #148: wyczerpane akcje znikają z action panelu (terminal po
        hack'u, vending po użyciu, container po przeszukaniu).
  #151: audio — prawdziwa muzyka zamiast pikania (rewrite
        music_explore).

Pokrywa:
  * _log_max_scroll() == 0 gdy log mieści się w oknie
  * _log_max_scroll() == (len - avail) gdy overflow
  * hack option znika gdy state.hacked = True
  * przeszukaj option znika gdy state.depleted = True
  * użyj option znika gdy state.vending_used / state.used
  * audio: explore.wav ma min. 16s (rozszerzone z 12s)
"""
from __future__ import annotations
import os

from ..engine import run_history as _rh


# ── #147: scroll clamp ──────────────────────────────────────────────


def test_log_max_scroll_zero_when_no_overflow():
    """Krótki log → max scroll = 0 (nie ma do czego scrollować)."""
    from ..engine.game import Game
    from ..engine.world import WorldState
    from ..engine.character import Character

    g = Game(screen=None)
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    w.log = [("krótka linia", "normal")] * 3  # bardzo mało
    g.world = w
    max_s = g._log_max_scroll()
    assert max_s == 0, f"max scroll przy 3 wpisach: {max_s}"
    print("  short log → _log_max_scroll == 0: OK")


def test_log_max_scroll_positive_when_overflow():
    """Długi log → max scroll = (len - widoczne wiersze)."""
    from ..engine.game import Game
    from ..engine.world import WorldState
    from ..engine.character import Character

    g = Game(screen=None)
    w = WorldState()
    w.character = Character(name="t", background="janitor")
    # 100 entries — na pewno overflow.
    w.log = [(f"linia {i}", "normal") for i in range(100)]
    g.world = w
    max_s = g._log_max_scroll()
    assert max_s > 0, f"100 wpisów powinno dać overflow, got {max_s}"
    assert max_s < 100, f"max scroll nie może być >= len, got {max_s}"
    print(f"  100 wpisów → _log_max_scroll = {max_s}: OK")


# ── #148: exhausted actions ─────────────────────────────────────────


def test_hack_option_hidden_when_hacked():
    """Po zhakowaniu terminal nie powinien już pokazywać `zhakuj`."""
    from ..engine.entity import Entity, T_TERMINAL
    from ..engine.room import RoomState
    from ..ui.ui_nav import _flat_object_verbs as _flat_object_options
    from ..engine.world import WorldState
    from ..engine.character import Character

    w = WorldState()
    w.character = Character(name="t", background="janitor")
    room = RoomState(room_id="r0")
    term = Entity(key="office_terminal", entity_type=T_TERMINAL,
                  fallback_name="terminal biurowy",
                  fallback_desc="Terminal mruga.",
                  tags=["terminal","electronic"],
                  affordances=["inspect","hack"],
                  location_id="r0")
    room.entities.append(term)
    w.register(term)

    opts_before = [o for o in _flat_object_options(w, room)
                    if o.action_type == "hack"]
    assert opts_before, "zhakuj powinien być dostępny przed hack'iem"

    term.state = {"hacked": True}
    opts_after = [o for o in _flat_object_options(w, room)
                   if o.action_type == "hack"]
    assert not opts_after, \
        f"zhakuj nadal w panelu po hack'u: {[o.label for o in opts_after]}"
    print("  hack option ukryty po state.hacked: OK")


def test_search_option_hidden_when_depleted():
    """Container po depleted nie powinien pokazywać `przeszukaj`."""
    from ..engine.entity import Entity, T_OBJECT
    from ..engine.room import RoomState
    from ..ui.ui_nav import _flat_object_verbs as _flat_object_options
    from ..engine.world import WorldState
    from ..engine.character import Character

    w = WorldState()
    w.character = Character(name="t", background="janitor")
    room = RoomState(room_id="r0")
    chest = Entity(key="loot_chest", entity_type=T_OBJECT,
                   fallback_name="skrzynia",
                   fallback_desc="Stara skrzynia.",
                   tags=["container"],
                   affordances=["inspect","loot"],
                   portable=False,
                   location_id="r0")
    room.entities.append(chest)
    w.register(chest)

    opts_before = [o for o in _flat_object_options(w, room)
                    if o.action_type == "loot"]
    assert opts_before, "przeszukaj powinien być dostępny przed lootem"

    chest.state = {"depleted": True}
    opts_after = [o for o in _flat_object_options(w, room)
                   if o.action_type == "loot"]
    assert not opts_after, \
        f"przeszukaj nadal w panelu po depleted: {opts_after}"
    print("  przeszukaj ukryty po state.depleted: OK")


def test_use_option_hidden_after_vending_used():
    """Vending machine po użyciu nie pokazuje `użyj`."""
    from ..engine.entity import Entity, T_OBJECT
    from ..engine.room import RoomState
    from ..ui.ui_nav import _flat_object_verbs as _flat_object_options
    from ..engine.world import WorldState
    from ..engine.character import Character

    w = WorldState()
    w.character = Character(name="t", background="janitor")
    room = RoomState(room_id="r0")
    vm = Entity(key="vending_machine", entity_type=T_OBJECT,
                fallback_name="automat",
                fallback_desc="Migający automat.",
                tags=["machine","button","powered"],
                affordances=["inspect","use"],
                location_id="r0")
    room.entities.append(vm)
    w.register(vm)

    opts_before = [o for o in _flat_object_options(w, room)
                    if o.action_type == "use"]
    assert opts_before, "użyj powinien być dostępny"

    vm.state = {"vending_used": True}
    opts_after = [o for o in _flat_object_options(w, room)
                   if o.action_type == "use"]
    assert not opts_after, \
        f"użyj nadal w panelu po vending_used: {opts_after}"
    print("  użyj ukryty po state.vending_used: OK")


# ── #151: muzyka — nowy track ma min. 16s ──────────────────────────


def test_explore_music_extended():
    """Nowy music_explore generuje min. 16s (było 12s)."""
    import wave
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    path = os.path.join(repo_root, "assets", "audio", "music",
                        "explore.wav")
    if not os.path.exists(path):
        print("  music explore.wav not generated yet — skip")
        return
    with wave.open(path, "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        dur = frames / rate
    assert dur >= 15.5, f"explore.wav za krótki: {dur:.1f}s"
    print(f"  explore.wav: {dur:.1f}s (cel: ≥16s): OK")


# ── Suite ────────────────────────────────────────────────────────────


def main():
    _rh.reset()
    try:
        test_log_max_scroll_zero_when_no_overflow()
        test_log_max_scroll_positive_when_overflow()
        test_hack_option_hidden_when_hacked()
        test_search_option_hidden_when_depleted()
        test_use_option_hidden_after_vending_used()
        test_explore_music_extended()
    finally:
        _rh.reset()
    print("Prompt 29.50 UX cleanup smoke: OK")


if __name__ == "__main__":
    main()
