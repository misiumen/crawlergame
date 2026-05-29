"""E2E P29.63 — głębia walki: efekty systemowe ŻYJĄ w turach.

User: „brakuje mi poczucia impaktu... to przypomina bardziej excel niż
grę." Diagnoza: silnik systemowy zadawał jeden hit i umierał — DoT/stun/
slow zapisywane na cel, ale nic ich nie tykało. Tu dowodzimy, że:
  * synergia zostawia efekt trwały (pożar pali dalej),
  * tick() aplikuje DoT co turę i wygasa, czyszcząc stan,
  * paraliż (stun) i spowolnienie (slow) są odczytywalne,
  * ogień pełznie na łatwopalne sąsiedztwo (reaktywne otoczenie),
  * gra loguje skutki i dobity DoT-em wróg staje się trupem.
"""
from __future__ import annotations
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine import systemic as _sys
from ...engine.entity import Entity, T_MONSTER, T_OBJECT, T_CORPSE
from .headless import HeadlessSession


def _mob(key, *, hp=40, tags=None, name=None, ac=12, dt="physical"):
    return Entity(key=key, entity_type=T_MONSTER, fallback_name=name or key,
                  tags=list(tags or []), damage_type=dt,
                  hp=hp, max_hp=hp, ac=ac)


def _obj(key, *, tags=None, name=None):
    return Entity(key=key, entity_type=T_OBJECT, fallback_name=name or key,
                  tags=list(tags or []))


class _Room:
    """Lekki pokój — spread_fire czyta tylko .entities."""
    def __init__(self, entities):
        self.entities = list(entities)


# ── Synergia zostawia efekt TRWAŁY (nie jednorazowy hit) ────────────


def test_synergy_fire_leaves_lingering_dot():
    src = _obj("czar_ognia", tags=["ogień"])
    mob = _mob("mob", tags=["łatwopalne"], hp=40)
    r = _sys.resolve(None, "rzuć", src, mob)
    assert r.matched and r.effect == "pożar"
    st = mob.state or {}
    assert st.get("systemic_turns", 0) > 0, "pożar nie zostawił żywotności"
    assert isinstance(st.get("systemic_dot"), dict), "brak DoT po pożarze"
    assert _sys.has_systemic_status(mob, "płonie")


def test_synergy_shock_leaves_stun_chance():
    src = _obj("kable", tags=["prąd"])
    mob = _mob("mob", tags=["przewodzące"], hp=40)
    r = _sys.resolve(None, "wepchnij", src, mob)
    assert r.matched and r.effect == "porażenie"
    assert (mob.state or {}).get("systemic_stun_chance") is not None


# ── tick(): DoT aplikuje się co turę i wygasa ───────────────────────


def test_tick_applies_dot_each_turn_then_expires():
    mob = _mob("mob", hp=40)
    mob.state = {"systemic_statuses": ["płonie"],
                 "systemic_dot": {"dmg": 3, "turns": 3, "status": "płonie"},
                 "systemic_turns": 3}
    hp0 = mob.hp
    r1 = _sys.tick(mob)
    assert r1.damage == 3 and mob.hp == hp0 - 3 and not r1.expired
    assert r1.flavor == "ogień trawi"
    r2 = _sys.tick(mob)
    assert mob.hp == hp0 - 6 and not r2.expired
    r3 = _sys.tick(mob)
    assert r3.expired and mob.hp == hp0 - 9
    # Po wygaśnięciu stan systemowy wyczyszczony.
    assert (mob.state or {}).get("systemic_turns", 0) == 0
    assert "systemic_dot" not in (mob.state or {})
    assert _sys.tick(mob) is None


def test_tick_none_on_clean_target():
    assert _sys.tick(_mob("x", hp=10)) is None


def test_corrosion_persists_no_expiry():
    """Korozja: turns=0, więc tick jej nie rusza — AC w dół zostaje."""
    src = _obj("kwas", tags=["kwas"])
    guard = _mob("guard", tags=["metal"], hp=30, ac=16)
    ac0 = guard.ac
    r = _sys.resolve(None, "wepchnij", src, guard)
    assert r.matched and r.effect == "korozja"
    assert guard.ac < ac0
    # tick nic nie zmienia (turns 0) i AC zostaje obniżone.
    assert _sys.tick(guard) is None
    assert guard.ac < ac0


# ── stun / slow odczytywalne ────────────────────────────────────────


def test_roll_stun_respects_chance():
    stunned = _mob("m", hp=10)
    stunned.state = {"systemic_stun_chance": 1.0}
    assert _sys.roll_stun(stunned, random.Random(0)) is True
    assert _sys.roll_stun(_mob("c", hp=10), random.Random(0)) is False


def test_is_slowed():
    slow = _mob("m", hp=10)
    slow.state = {"systemic_slow": True}
    assert _sys.is_slowed(slow) is True
    assert _sys.is_slowed(_mob("c", hp=10)) is False


# ── Rozprzestrzenianie ognia (reaktywne otoczenie) ──────────────────


def test_fire_spreads_to_flammable_neighbour():
    burning = _mob("zrodlo", hp=20)
    burning.state = {"systemic_statuses": ["płonie"]}
    regal = _obj("regal", tags=["łatwopalne"], name="regał z księgami")
    glaz = _obj("glaz", tags=["metal"], name="głaz")
    room = _Room([burning, regal, glaz])
    lines = _sys.spread_fire(None, room)
    assert lines and "regał" in lines[0]
    assert _sys.has_systemic_status(regal, "płonie")
    assert not _sys.has_systemic_status(glaz, "płonie")


def test_fire_no_spread_without_flammable():
    burning = _mob("zrodlo", hp=20)
    burning.state = {"systemic_statuses": ["płonie"]}
    room = _Room([burning, _obj("glaz", tags=["metal"])])
    assert _sys.spread_fire(None, room) == []


def test_fire_spread_bounded_one_per_turn():
    burning = _mob("zrodlo", hp=20)
    burning.state = {"systemic_statuses": ["płonie"]}
    a = _obj("a", tags=["łatwopalne"], name="skrzynia")
    b = _obj("b", tags=["łatwopalne"], name="paleta")
    room = _Room([burning, a, b])
    lines = _sys.spread_fire(None, room)
    assert len(lines) == 1, "ogień nie powinien zająć wszystkiego naraz"
    burned = [e for e in (a, b) if _sys.has_systemic_status(e, "płonie")]
    assert len(burned) == 1


# ── Integracja z grą: log skutków + dobicie DoT-em → trup ───────────


def test_game_tick_logs_dot_and_damages():
    sess = HeadlessSession()
    mob = _mob("szczur", hp=40, name="Szczur")
    mob.state = {"systemic_statuses": ["trawiony kwasem"],
                 "systemic_dot": {"dmg": 2, "turns": 2,
                                  "status": "trawiony kwasem"},
                 "systemic_turns": 2}
    sess.game._tick_systemic_on(mob)
    assert mob.hp == 38
    assert sess.log_contains("kwas żre")


def test_game_tick_dot_kill_makes_corpse():
    sess = HeadlessSession()
    mob = _mob("szczur", hp=2, name="Szczur")
    sess.put_in_room(mob)
    mob.state = {"systemic_statuses": ["płonie"],
                 "systemic_dot": {"dmg": 3, "turns": 3, "status": "płonie"},
                 "systemic_turns": 3}
    sess.game._tick_systemic_on(mob)
    assert mob.hp == 0
    assert mob.entity_type == T_CORPSE
    assert sess.log_contains("dogorywa")
