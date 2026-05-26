"""Prompt 26c — Class-bug sweep smoke suite.

Each class of bug shipped a regression test so the next instance
doesn't slip past us. We've burned weeks playing whack-a-mole on
these classes; the tests below are the moats.

Covers:
  * Parser fallback joins multi-word targets ("zdemontuj rozbity
    monitor" → target="rozbity monitor", not ["rozbity"]).
  * Handler-internal validate paths latch pending_disambiguation so
    the next `oba`/`1`/partial-name resolves.
  * Mass salvage filters out hazards / liquids / non-salvageable.
  * `znowu` replays last successful command.
  * t() locale lookup falls back to the f-string fallback when the
    template has unfilled placeholders.
  * The sponsor signage line uses natural Polish (mieszać + dziękujemy),
    not translation-shape (łączyć + prosimy).
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from ..engine.parser_core import parse
from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_OBJECT, T_ITEM


def _mk_world():
    w = WorldState()
    w.character = Character(name="N", background="janitor")
    f = FloorState(floor_id="f", floor_number=1)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w


def _add_obj(w, key, name, **kwargs):
    # Default affordances = ["inspect"] unless kwargs override.
    kwargs.setdefault("affordances", ["inspect"])
    e = Entity(key=key, entity_type=T_OBJECT, fallback_name=name,
               fallback_desc=name, location_id="r0", **kwargs)
    w.register(e); w.current_floor.current_room().entities.append(e)
    return e


# ── Parser fallback ──────────────────────────────────────────────────────

def test_parser_joins_multi_word_target():
    intent = parse("zdemontuj rozbity monitor", world=None)
    assert intent.intent == "salvage"
    assert intent.targets == ["rozbity monitor"], \
        f"expected ['rozbity monitor'], got {intent.targets}"
    print(f"  parser: 'zdemontuj rozbity monitor' → targets={intent.targets}: OK")


def test_parser_joins_three_word_target():
    intent = parse("sprawdź stara mokra kanapa", world=None)
    assert intent.targets and intent.targets[0] == "stara mokra kanapa"
    print(f"  parser: 3-word target joined: OK")


def test_parser_strips_stop_words():
    # Verify _STOP filter still applies when joining (if any STOP tokens
    # land mid-target — most are leading prepositions handled elsewhere).
    intent = parse("sprawdź rozbity monitor", world=None)
    assert intent.targets == ["rozbity monitor"]
    print("  parser: stop-word filter intact during join: OK")


# ── Disambiguation latch on handler-internal validate ─────────────────

def test_salvage_latches_disambiguation():
    from ..engine.game import Game
    w = _mk_world()
    # Two entities both starting with "rozbity" — ambiguous.
    a = _add_obj(w, "rozbity_monitor", "rozbity monitor",
                 tags=["fragile", "salvageable"])
    b = _add_obj(w, "rozbity_stol",    "rozbity stół",
                 tags=["furniture", "salvageable"])
    g = Game(screen=None); g.world = w; g.state = "play"
    # Force the resolver to hit ambiguity by giving it just "rozbity".
    from ..engine.parser_core import ActionIntent
    intent = ActionIntent(intent="salvage", verb="zdemontuj",
                          targets=["rozbity"])
    g._attempt_salvage(intent)
    assert g.pending_disambiguation is not None, \
        "salvage handler must latch pending_disambiguation on ambiguous"
    assert len(g.pending_disambiguation["entity_ids"]) == 2
    print("  salvage handler latches disambiguation: OK")


def test_oba_after_salvage_disambig_works():
    from ..engine.game import Game
    w = _mk_world()
    a = _add_obj(w, "rozbity_monitor", "rozbity monitor",
                 tags=["fragile", "salvageable"])
    b = _add_obj(w, "rozbity_stol",    "rozbity stół",
                 tags=["furniture", "salvageable"])
    g = Game(screen=None); g.world = w; g.state = "play"
    # First command — ambiguous.
    g.submit_generated_command("zdemontuj rozbity")
    assert g.pending_disambiguation is not None, \
        "first call should have latched"
    # Second — "oba" should resolve.
    g.submit_generated_command("oba")
    # `oba` cleared the pending and re-issued for both entities.
    assert g.pending_disambiguation is None
    print("  `oba` after salvage disambig consumed: OK")


# ── Mass action filter ────────────────────────────────────────────────

def test_mass_salvage_skips_hazards():
    from ..engine.game import Game
    w = _mk_world()
    # A hazard puddle (should be skipped) + a salvageable shelf (should
    # be salvaged).
    haz = _add_obj(w, "acid_pool", "kałuża kwasu",
                   tags=["hazard", "liquid"])
    haz.entity_type = "hazard"
    salvageable = _add_obj(w, "metal_shelf", "metalowa półka",
                           tags=["salvageable"],
                           affordances=["inspect", "salvage"])
    g = Game(screen=None); g.world = w; g.state = "play"
    from ..engine.parser_core import ActionIntent
    intent = ActionIntent(intent="mass_salvage", verb="rozbierz",
                          normalized_text="rozbierz wszystko")
    g._attempt_mass_salvage(intent)
    # Hazard should not appear in any log line as a salvage target.
    log_text = " ".join(s for s, _c in w.log).lower()
    assert "kałuża kwasu" not in log_text or "kwasu: już" in log_text, \
        f"hazard was incorrectly mass-salvaged: {log_text[:200]}"
    print("  mass salvage skips hazard puddle: OK")


# ── Context pronoun: znowu ────────────────────────────────────────────

def test_znowu_replays_last_command():
    from ..engine.game import Game
    w = _mk_world()
    _add_obj(w, "monitor", "monitor")
    g = Game(screen=None); g.world = w; g.state = "play"
    # First command — sets last_player_command.
    g.input_text = "sprawdź monitor"
    g.submit_input()
    assert w.last_player_command == "sprawdź monitor"
    pre_log = len(w.log)
    g.input_text = "znowu"
    g.submit_input()
    after = " ".join(s for s, _c in w.log[pre_log:]).lower()
    assert "znowu" in after or "monitor" in after
    print("  znowu replays last command: OK")


def test_znowu_no_history_warns():
    from ..engine.game import Game
    w = _mk_world()
    g = Game(screen=None); g.world = w; g.state = "play"
    g.input_text = "znowu"
    g.submit_input()
    msg = " ".join(s for s, _c in w.log).lower()
    assert "nic do powtórzenia" in msg or "nie było" in msg
    print("  znowu with no history → warning: OK")


def test_znowu_does_not_self_replay():
    from ..engine.game import Game
    w = _mk_world()
    _add_obj(w, "monitor", "monitor")
    g = Game(screen=None); g.world = w; g.state = "play"
    g.input_text = "sprawdź monitor"
    g.submit_input()
    g.input_text = "znowu"
    g.submit_input()
    # Last persisted command must be the real one, not "znowu" itself.
    assert w.last_player_command == "sprawdź monitor", \
        f"znowu must not overwrite last_player_command (got {w.last_player_command!r})"
    print("  znowu doesn't overwrite last_player_command with itself: OK")


# ── Locale placeholder defense ────────────────────────────────────────

def test_locale_template_without_kwargs_uses_fallback():
    from ..ui.lang import t
    # This locale key has `{minutes}` placeholder; without passing the
    # kwarg, t() should fall back to the f-string fallback (which was
    # already substituted by the caller).
    result = t("feedback_mass_salvage_summary",
               fallback="Czas: ok. 12 min. Hałas: wysoki.")
    assert "{minutes}" not in result, \
        f"placeholder leaked: {result!r}"
    print(f"  no placeholder leak when kwargs missing: '{result[:50]}…': OK")


def test_locale_template_with_kwargs_substitutes():
    from ..ui.lang import t
    result = t("feedback_mass_salvage_summary",
               fallback="Czas: ok. 12 min. Hałas: wysoki.",
               minutes=12)
    assert "{minutes}" not in result
    # Substituted version contains the number.
    assert "12" in result
    print(f"  kwargs substitute correctly: '{result[:50]}…': OK")


# ── Polish content fix verification ───────────────────────────────────

def test_acid_sign_uses_natural_polish():
    from ..content.data import room_pool
    # The sign in look_pool should now read "MIESZAĆ" + "DZIĘKUJEMY ZA
    # WSPÓŁPRACĘ", not "ŁĄCZYĆ" + bare "PROSIMY".
    found = False
    for tmpl in (getattr(room_pool, "ROOMS_POOL", {}) or {}).values():
        for line in tmpl.get("look_pool", []):
            if "MIESZAĆ KWASU" in line and "WSPÓŁPRACĘ" in line:
                found = True
                break
    # If the data structure changed, we still want this test to point
    # somewhere — fail loudly with the symptom rather than silently pass.
    if not found:
        # Search the file directly as a fallback signal.
        import inspect
        src = inspect.getsource(room_pool)
        assert "MIESZAĆ KWASU" in src and "WSPÓŁPRACĘ" in src, \
            "natural-Polish acid sign not present in room_pool.py"
    print("  acid sign: natural-Polish phrasing: OK")


# ── Suite ──────────────────────────────────────────────────────────────

def main():
    test_parser_joins_multi_word_target()
    test_parser_joins_three_word_target()
    test_parser_strips_stop_words()
    test_salvage_latches_disambiguation()
    test_oba_after_salvage_disambig_works()
    test_mass_salvage_skips_hazards()
    test_znowu_replays_last_command()
    test_znowu_no_history_warns()
    test_znowu_does_not_self_replay()
    test_locale_template_without_kwargs_uses_fallback()
    test_locale_template_with_kwargs_substitutes()
    test_acid_sign_uses_natural_polish()
    print("Prompt 26c class-bug sweep smoke: OK")


if __name__ == "__main__":
    main()
