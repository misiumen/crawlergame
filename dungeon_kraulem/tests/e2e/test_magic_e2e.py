"""E2E P29.67 — magia jako warstwa silnika (A/4a).

Czar = ŹRÓDŁO wpadające w te same reguły co fizyka. Płomień pali to, co
łatwopalne; pchnięcie roztrzaskuje kruche; mara odpala lęk celu. Mana
gatuje. Akwizycja: w normalnej grze brak zaklęć (szary człowiek), w
arenie/testach grant.
"""
from __future__ import annotations
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine import magic as _magic
from ...engine import systemic as _sys
from ...engine import parser_core as _pc
from ...engine.character import Character
from ...engine.entity import Entity, T_MONSTER, T_OBJECT
from .headless import HeadlessSession


def _mage(int_score=16):
    c = Character(name="Mag", background="student")
    c.stats["INT"] = int_score
    _magic.grant_core(c)
    _magic.ensure_mana(c)
    c.flags["mana"] = _magic.max_mana(c)
    return c


def _foe(*tags, hp=40, ac=12):
    return Entity(key="foe", entity_type=T_MONSTER, fallback_name="cel",
                  tags=list(tags), hp=hp, max_hp=hp, ac=ac)


# ── Rozpoznawanie szkoły + mana ─────────────────────────────────────


def test_resolve_school_folds_diacritics():
    assert _magic.resolve_school("ogien") == "ogień"
    assert _magic.resolve_school("ogień") == "ogień"
    assert _magic.resolve_school("mroz") == "mróz"
    assert _magic.resolve_school("iluzja") == "iluzja"
    assert _magic.resolve_school("bzdura") is None


def test_mana_scales_with_int_and_spends():
    smart = Character(name="a", background="student"); smart.stats["INT"] = 16
    dim = Character(name="b", background="soldier"); dim.stats["INT"] = 8
    assert _magic.max_mana(smart) > _magic.max_mana(dim)
    _magic.ensure_mana(smart)
    m0 = _magic.mana(smart)
    assert _magic.spend_mana(smart, 2) and _magic.mana(smart) == m0 - 2
    _magic.restore_mana(smart, 100)
    assert _magic.mana(smart) == _magic.max_mana(smart)


# ── Gating: nieznane / brak many ────────────────────────────────────


def test_cast_unknown_when_not_learned():
    c = Character(name="x", background="janitor")   # nie zna zaklęć
    _magic.ensure_mana(c)
    r = _magic.cast(None, "ogień", c, _foe("łatwopalne"))
    assert r.ok is False and r.reason == "unknown"


def test_cast_blocked_without_mana():
    c = _mage()
    c.flags["mana"] = 0
    r = _magic.cast(None, "ogień", c, _foe("łatwopalne"))
    assert r.ok is False and r.reason == "no_mana"


# ── Żywioły wpadają w reguły materii ────────────────────────────────


def test_fire_spell_ignites_flammable():
    c = _mage()
    foe = _foe("łatwopalne")
    r = _magic.cast(None, "ogień", c, foe)
    assert r.ok and _sys.has_systemic_status(foe, "płonie")
    assert _magic.mana(c) == _magic.max_mana(c) - _magic.SPELLS["ogień"]["mana"]


def test_acid_spell_corrodes_metal():
    c = _mage()
    foe = _foe("armored", ac=16)        # armored → metal (inferencja)
    pre = foe.ac
    r = _magic.cast(None, "kwas", c, foe)
    assert r.ok and foe.ac < pre


def test_telekinesis_shatters_fragile():
    c = _mage()
    foe = _foe("kruche", hp=10)
    r = _magic.cast(None, "telekineza", c, foe)
    assert r.ok and foe.hp < 10


# ── Iluzja czyta umysł i odpala psyche ──────────────────────────────


def test_illusion_triggers_targets_fear():
    c = _mage()
    foe = _foe("lęk:robactwo")
    r = _magic.cast(None, "iluzja", c, foe)
    assert r.ok and _sys.has_systemic_status(foe, "przerażony")


def test_illusion_fizzles_on_fearless():
    c = _mage()
    foe = _foe("monster", "humanoid")
    r = _magic.cast(None, "iluzja", c, foe)
    assert r.ok and r.reason == "fizzle"


# ── Parser ──────────────────────────────────────────────────────────


def test_parse_czaruj_with_target():
    i = _pc.parse("czaruj ogień w szczura")
    assert i.intent == "cast" and _magic.resolve_school(i.tool) == "ogień"
    assert i.targets and "szczur" in i.targets[0].lower()


def test_parse_rzuc_czar():
    i = _pc.parse("rzuć czar mróz na strażnika")
    assert i.intent == "cast" and _magic.resolve_school(i.tool) == "mróz"


def test_parse_plain_rzuc_is_not_cast():
    # „rzuć X" bez słowa „czar" zostaje rzutem fizycznym (throw), nie magią.
    i = _pc.parse("rzuć kamień w szczura")
    assert i.intent != "cast"


# ── Integracja gry ──────────────────────────────────────────────────


def test_cast_via_command_in_session():
    sess = HeadlessSession()
    _magic.grant_core(sess.character)
    sess.character.stats["INT"] = 16
    sess.character.flags["mana"] = _magic.max_mana(sess.character)
    foe = sess.spawn_from_mon("tunnel_runt")          # flammable
    pre = foe.hp
    out = sess.send("czaruj ogień w szczurek")
    text = "\n".join(t for t, _ in out)
    assert "Płomień" in text or "płomien" in text.lower()
    assert foe.hp < pre and _sys.has_systemic_status(foe, "płonie")


def test_cast_refused_when_player_knows_nothing():
    sess = HeadlessSession()                          # brak grantu
    sess.spawn_from_mon("tunnel_runt")
    out = sess.send("czaruj ogień w szczurek")
    text = "\n".join(t for t, _ in out)
    assert "nie umiesz" in text.lower() or "nie nauczył" in text.lower()
