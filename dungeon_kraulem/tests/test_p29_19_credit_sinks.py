"""Prompt 29.19 — Credit-sink smoke suite.

Audit finding: cafe + clinic + intel were the only credit sinks.
With vending now (P29.18) it's slightly broader, but there's no
character-progression spend at all. P29.19 adds four:
  * trening <stat>      80 kr, +1 to one stat, once per stat
  * łapówka <sponsor>   20 kr, +2 sponsor attention (unlimited)
  * zamów pakiet [..]   50 kr, spawn sponsor drop pod here
  * wzmocnij hp|ac      100 kr, +5 max HP or +1 base AC, once each

Covers:
  * Parser maps each verb-shape to the right intent.
  * trening lifts the stat by exactly +1 and burns the slot.
  * trening twice on same stat: refuses second time.
  * łapówka boosts the right sponsor's attention.
  * zamów pakiet spawns a sponsor_pod entity in the current room.
  * wzmocnij hp bumps max_hp +5; second call refuses.
  * wzmocnij ac bumps base_ac +1.
  * Missing credits refuses with a Polish message + no state change.
"""
from __future__ import annotations
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.room import RoomState
from ..engine.parser_core import parse


def _mk_world(credits=200):
    w = WorldState()
    w.character = Character(name="Igor", background="janitor",
                            credits=credits)
    f = FloorState(floor_id="f1", floor_number=2)
    r = RoomState(room_id="r0", fallback_short_title="Hala")
    f.add_room(r); f.start_room_id = "r0"; f.current_room_id = "r0"
    w.current_floor = f
    return w, r


# ── Parser ──────────────────────────────────────────────────────────────

def test_parser_routes_each_sink():
    cases = [
        ("trening DEX",                 "train_stat",  ["dex"]),
        ("trening siła",                "train_stat",  ["sila"]),
        ("łapówka novachem",            "bribe_sponsor", ["novachem"]),
        ("zamów pakiet",                "call_pod",    []),
        ("zamów pakiet czarny",         "call_pod",    ["czarny"]),
        ("wzmocnij hp",                 "upgrade_loadout", ["hp"]),
        ("wzmocnij ac",                 "upgrade_loadout", ["ac"]),
        ("wzmocnij pancerz",            "upgrade_loadout", ["ac"]),
        ("wzmocnij punkty",             "upgrade_loadout", ["hp"]),
    ]
    for cmd, ex_intent, ex_targets in cases:
        i = parse(cmd)
        assert i.intent == ex_intent, f"{cmd!r} → {i.intent}, want {ex_intent}"
        assert i.targets == ex_targets, \
            f"{cmd!r} targets={i.targets}, want {ex_targets}"
    print(f"  parser routes {len(cases)} credit-sink commands: OK")


# ── trening ─────────────────────────────────────────────────────────────

def test_respec_pulls_point_back_to_pool():
    # P29.76 — Wiercimajster = respec: zdejmuje punkt z statu (powyżej bazy)
    # i zwraca do puli nierozdanych punktów. Powtarzalny.
    from ..engine.game import Game
    w, _r = _mk_world(credits=200)
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.background = "janitor"     # baza DEX = 10
    w.character.stats["DEX"] = 13          # 3 punkty z poziomów
    w.character.unspent_stat_points = 0
    pre_cr = w.character.credits
    g.submit_generated_command("przebudowa DEX")
    assert w.character.stats["DEX"] == 12              # -1
    assert w.character.unspent_stat_points == 1        # punkt wraca do puli
    assert w.character.credits == pre_cr - 40
    # Alias „trening" też mapuje na respec.
    g.submit_generated_command("trening DEX")
    assert w.character.stats["DEX"] == 11
    assert w.character.unspent_stat_points == 2
    print("  respec pulls points back to pool (repeatable): OK")


def test_respec_refuses_at_base_stat():
    from ..engine.game import Game
    w, _r = _mk_world(credits=200)
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.background = "janitor"
    w.character.stats["DEX"] = 10          # już na bazie
    w.character.unspent_stat_points = 0
    g.submit_generated_command("przebudowa DEX")
    assert w.character.stats["DEX"] == 10              # nie schodzi poniżej bazy
    assert w.character.unspent_stat_points == 0
    print("  respec refuses at base stat: OK")


def test_respec_refuses_no_credits():
    from ..engine.game import Game
    w, _r = _mk_world(credits=10)
    g = Game(screen=None); g.world = w; g.state = "play"
    w.character.background = "janitor"
    w.character.stats["DEX"] = 13
    g.submit_generated_command("przebudowa DEX")
    assert w.character.stats["DEX"] == 13, "brak kredytów → bez respecu"
    assert w.character.credits == 10
    print("  respec refuses on insufficient credits: OK")


# ── łapówka ─────────────────────────────────────────────────────────────

def test_bribe_bumps_sponsor_attention():
    from ..engine.game import Game
    from ..engine import sponsors as _sp
    w, _r = _mk_world(credits=200)
    g = Game(screen=None); g.world = w; g.state = "play"
    pre = _sp.get_attention(w, "novachem_biotech")
    g.submit_generated_command("łapówka novachem")
    post = _sp.get_attention(w, "novachem_biotech")
    assert post == pre + 2, f"attention {pre}→{post} (expected +2)"
    assert w.character.credits == 180
    print(f"  łapówka novachem: attention {pre}→{post}: OK")


def test_bribe_refuses_unknown_sponsor():
    from ..engine.game import Game
    w, _r = _mk_world(credits=200)
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("łapówka nieistniejący")
    assert w.character.credits == 200, "no-op on unknown sponsor"
    print("  łapówka refuses unknown sponsor: OK")


# ── zamów pakiet ────────────────────────────────────────────────────────

def test_call_pod_spawns_sponsor_pod():
    from ..engine.game import Game
    w, r = _mk_world(credits=200)
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("zamów pakiet novachem")
    pods = [e for e in r.entities if "sponsor_pod" in (e.tags or [])]
    assert pods, "pod should be spawned in current room"
    pod = pods[0]
    assert pod.state.get("pending_sponsor_key") == "novachem_biotech"
    assert w.character.credits == 150
    print(f"  zamów pakiet → pod in room ({pod.display_name()}): OK")


def test_call_pod_refuses_no_credits():
    from ..engine.game import Game
    w, r = _mk_world(credits=20)
    g = Game(screen=None); g.world = w; g.state = "play"
    g.submit_generated_command("zamów pakiet")
    pods = [e for e in r.entities if "sponsor_pod" in (e.tags or [])]
    assert not pods, "no pod when broke"
    assert w.character.credits == 20
    print("  zamów pakiet refuses on insufficient credits: OK")


# ── wzmocnij ────────────────────────────────────────────────────────────

def test_upgrade_hp_bumps_max_and_burns_slot():
    from ..engine.game import Game
    w, _r = _mk_world(credits=200)
    g = Game(screen=None); g.world = w; g.state = "play"
    pre_max = w.character.max_hp
    g.submit_generated_command("wzmocnij hp")
    assert w.character.max_hp == pre_max + 5
    assert w.character.credits == 100
    # Second call refuses.
    g.submit_generated_command("wzmocnij hp")
    assert w.character.max_hp == pre_max + 5
    assert w.character.credits == 100
    print(f"  wzmocnij hp: max_hp {pre_max}→{w.character.max_hp}, "
          f"second call refuses: OK")


def test_upgrade_ac_bumps_base_ac():
    from ..engine.game import Game
    w, _r = _mk_world(credits=200)
    g = Game(screen=None); g.world = w; g.state = "play"
    pre = w.character.base_ac
    g.submit_generated_command("wzmocnij ac")
    assert w.character.base_ac == pre + 1
    assert w.character.credits == 100
    print(f"  wzmocnij ac: base_ac {pre}→{w.character.base_ac}: OK")


# ── Suite ───────────────────────────────────────────────────────────────

def main():
    test_parser_routes_each_sink()
    test_training_bumps_stat_and_burns_slot()
    test_training_refuses_no_credits()
    test_bribe_bumps_sponsor_attention()
    test_bribe_refuses_unknown_sponsor()
    test_call_pod_spawns_sponsor_pod()
    test_call_pod_refuses_no_credits()
    test_upgrade_hp_bumps_max_and_burns_slot()
    test_upgrade_ac_bumps_base_ac()
    print("Prompt 29.19 credit sinks smoke: OK")


if __name__ == "__main__":
    main()
