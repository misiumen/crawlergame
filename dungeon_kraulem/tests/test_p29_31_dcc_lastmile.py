"""Prompt 29.31 — DCC last-mile flavor smoke.

Audit findings addressed:
  * Anti-host death lines were generic. Added 3 variants formatted
    with the player's name.
  * Corpse `inspect` didn't include the enemy's last-words quip.
    Added a tag-routed picker (boss / humanoid / cult / machine /
    fungal / beast / generic).
  * NG+ unlock fired into the run-history file but the title menu
    never surfaced it. Added a gold "✓ NewGame+ ODBLOKOWANE" badge.
  * Each floor descent now logs a 3-row "Sponsorzy oddali głos"
    scoreboard with PL display names.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.entity import Entity, T_MONSTER


def _mk_world(*, name="Igor"):
    w = WorldState()
    w.character = Character(name=name, background="janitor",
                            audience_rating=15)
    w.character.run_audience_peak = 15
    f = FloorState(floor_id="f1", floor_number=2)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


# ── Anti-host name-format ───────────────────────────────────────────────

def test_anti_host_can_format_name():
    """At least one of the run_summary anti-host lines should contain
    `{name}` so the player can hear their name said by the host on
    death."""
    from ..engine import run_summary as _rs
    name_template_count = sum(1 for ln in _rs.ANTI_HOST_DEATH_LINES
                              if "{name}" in ln)
    assert name_template_count >= 3, \
        f"expected >=3 anti-host variants with {{name}}, got {name_template_count}"
    print(f"  {name_template_count} anti-host lines reference {{name}}: OK")


def test_anti_host_line_actually_formats():
    """Build a RunSummary 10 times. At least one should produce a
    line that contains the player's name (probabilistic; 11 lines,
    3 with name → ~27% per draw, 95%+ over 10 draws)."""
    import random as _rand
    from ..engine import run_summary as _rs
    w, _r = _mk_world(name="ZenonTester")
    seen_personalized = False
    for seed in range(50):
        rng = _rand.Random(seed)
        rs = _rs.build_run_summary(w, rng=rng)
        if "ZenonTester" in (rs.anti_host_line or ""):
            seen_personalized = True
            break
    assert seen_personalized, \
        "anti_host_line never inserted player name across 50 RNG seeds"
    print("  build_run_summary formats {name} variant when picked: OK")


# ── Corpse last-words ───────────────────────────────────────────────────

def test_corpse_last_words_picked_on_transform():
    from ..engine import corpses as _cp
    e = Entity(key="thug", entity_type=T_MONSTER,
               fallback_name="Bandzior",
               tags=["monster", "humanoid"], hp=10, max_hp=10)
    _cp.transform_to_corpse(None, e)
    assert (e.state or {}).get("last_words"), \
        "transform_to_corpse should set last_words"
    print(f"  corpse last_words set on transform: "
          f"OK ({e.state['last_words'][:40]}…)")


def test_inspect_corpse_includes_last_words():
    from ..engine import corpses as _cp
    e = Entity(key="thug", entity_type=T_MONSTER,
               fallback_name="Bandzior",
               tags=["monster", "humanoid"], hp=10, max_hp=10)
    _cp.transform_to_corpse(None, e)
    lore = _cp.inspect_corpse(None, e)
    assert "Ostatnie słowa:" in lore, \
        f"inspect_corpse should surface last_words; got: {lore!r}"
    print("  inspect_corpse surfaces last_words: OK")


def test_last_words_picker_routes_by_tag():
    """Different tags hit different pools — boss line for a boss,
    machine line for a drone, etc."""
    from ..engine import corpses as _cp
    e_boss = Entity(key="boss_x", entity_type=T_MONSTER,
                    fallback_name="Boss",
                    tags=["monster", "boss"], hp=1, max_hp=1)
    _cp.transform_to_corpse(None, e_boss)
    boss_pool = _cp._LAST_WORDS_BY_TAG["boss"]
    assert e_boss.state["last_words"] in boss_pool

    e_mach = Entity(key="drone_x", entity_type=T_MONSTER,
                    fallback_name="Dron",
                    tags=["monster", "machine"], hp=1, max_hp=1)
    _cp.transform_to_corpse(None, e_mach)
    machine_pool = _cp._LAST_WORDS_BY_TAG["machine"]
    assert e_mach.state["last_words"] in machine_pool
    print("  last-words picker routes by tag (boss / machine): OK")


# ── NG+ surface ──────────────────────────────────────────────────────────

def test_ng_plus_unlocked_drawable():
    """Verify the run_history has_unlock path the title screen
    consumes."""
    from ..engine import run_history as _rh
    _rh.reset()
    assert _rh.has_unlock("new_game_plus") is False
    _rh.unlock("new_game_plus")
    assert _rh.has_unlock("new_game_plus") is True
    _rh.reset()
    print("  NG+ unlock state queryable for title screen: OK")


# ── Between-floor sponsor scoreboard ─────────────────────────────────────

def test_descent_logs_sponsor_scoreboard():
    """Driving _descend_or_win should append a Polish "Sponsorzy
    oddali głos:" header + at most 3 sponsor rows."""
    from ..engine.game import Game
    from ..engine import sponsors as _sp
    w, _r = _mk_world()
    # Build a phantom floor 2 + 3 so descent has somewhere to go.
    # The actual descent path tries to generate floor_number+1 via
    # floor_generator — we stub it to avoid the full procgen run.
    g = Game(screen=None); g.world = w; g.state = "play"
    # Seed three non-zero sponsor attentions.
    _sp.adjust_attention(w, "novachem_biotech", 5)
    _sp.adjust_attention(w, "kanal_7_krawedz", 3)
    _sp.adjust_attention(w, "kult_recyklingu", -2)
    # Stub floor_generator.generate_floor to a no-op that returns
    # a fresh FloorState.
    from ..engine import floor_generator as _fg
    orig = _fg.generate_floor
    def stub_gen(world, *, floor_number=1, seed=None, archetype=None):
        nf = FloorState(floor_id=f"f{floor_number}",
                        floor_number=floor_number)
        r2 = RoomState(room_id="r0", fallback_short_title="x",
                       actual_type="social")
        nf.add_room(r2)
        nf.start_room_id = "r0"; nf.current_room_id = "r0"
        return nf
    _fg.generate_floor = stub_gen
    try:
        pre = len(w.log)
        g._descend_or_win()
        new_lines = [e[0] if isinstance(e, tuple) else str(e)
                     for e in w.log[pre:]]
    finally:
        _fg.generate_floor = orig
    joined = "\n".join(new_lines)
    assert "Sponsorzy oddali głos" in joined, \
        f"scoreboard header missing: {joined}"
    # At least one of the three sponsors named in the log.
    assert ("NovaChem" in joined or "Kanał 7" in joined or
            "Recykling" in joined), f"no sponsor name in scoreboard: {joined}"
    print("  descent logs sponsor scoreboard: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_anti_host_can_format_name()
    test_anti_host_line_actually_formats()
    test_corpse_last_words_picked_on_transform()
    test_inspect_corpse_includes_last_words()
    test_last_words_picker_routes_by_tag()
    test_ng_plus_unlocked_drawable()
    test_descent_logs_sponsor_scoreboard()
    print("Prompt 29.31 DCC last-mile smoke: OK")


if __name__ == "__main__":
    main()
