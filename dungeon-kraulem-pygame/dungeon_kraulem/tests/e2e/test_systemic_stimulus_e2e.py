"""E2E P29.68 — silnik A/5: bodźce + reakcje (hałas jako NARZĘDZIE).

Każdy mob ma profil reakcji (ciekawski/płochliwy/agresywny/obojętny).
Gracz emituje hałas → mob reaguje wg profilu, nie wg płaskiej liczby.
`odwróć uwagę` ściąga ciekawskich, płoszy płochliwych, zajmuje
agresywnych — i zabiera im turę przeciw graczowi.
"""
from __future__ import annotations
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine import systemic as _sys
from ...engine import parser_core as _pc
from ...engine.entity import Entity, T_MONSTER
from .headless import HeadlessSession


def _mob(*tags, hp=30):
    return Entity(key="m", entity_type=T_MONSTER, fallback_name="stwór",
                  tags=list(tags), hp=hp, max_hp=hp, affordances=["attack"])


# ── Inferencja profilu ──────────────────────────────────────────────


def test_profile_inference():
    assert _sys.reaction_profile(_mob("monster", "brute")) == "agresywny"
    assert _sys.reaction_profile(_mob("monster", "cunning")) == "ciekawski"
    assert _sys.reaction_profile(_mob("monster", "beast")) == "płochliwy"
    assert _sys.reaction_profile(_mob("monster", "robot")) == "obojętny"
    assert _sys.reaction_profile(_mob("monster")) == "obojętny"   # domyślnie


def test_explicit_reaction_tag_overrides():
    # Jawny tag wygrywa nawet nad „beast" (który inferuje płochliwy).
    assert _sys.reaction_profile(
        _mob("monster", "beast", "reakcja:agresywny")) == "agresywny"


# ── Reakcje na bodziec ──────────────────────────────────────────────


def test_curious_is_lured():
    m = _mob("monster", "cunning")
    r = _sys.apply_stimulus(m, "hałas")
    assert r.matched and _sys.has_systemic_status(m, "zwabiony")
    assert (m.state or {}).get("systemic_slow") is True


def test_skittish_is_spooked():
    m = _mob("monster", "beast")
    r = _sys.apply_stimulus(m, "hałas")
    assert r.matched and _sys.has_systemic_status(m, "spłoszony")
    assert (m.state or {}).get("systemic_stun_chance", 0) > 0


def test_aggressive_charges_decoy():
    m = _mob("monster", "brute")
    r = _sys.apply_stimulus(m, "hałas")
    assert r.matched and _sys.has_systemic_status(m, "rozjuszony")


def test_indifferent_unmoved():
    m = _mob("monster", "robot")
    r = _sys.apply_stimulus(m, "hałas")
    assert r.matched is False
    assert r.lines and "drgnie" in r.lines[0]


# ── Parser ──────────────────────────────────────────────────────────


def test_parse_distract_verbs():
    assert _pc.parse("odwróć uwagę").intent == "distract"
    assert _pc.parse("hałasuj").intent == "distract"
    assert _pc.parse("narób hałasu").intent == "distract"


# ── Integracja gry ──────────────────────────────────────────────────


def test_distract_spooks_skittish_in_room():
    sess = HeadlessSession()
    beast = _mob("monster", "beast", hp=20)
    sess.put_in_room(beast)
    out = sess.send("odwróć uwagę")
    text = "\n".join(t for t, _ in out)
    assert "płoszy" in text or "pierzcha" in text
    assert _sys.has_systemic_status(beast, "spłoszony")


def test_distract_empty_room_graceful():
    sess = HeadlessSession()
    out = sess.send("hałasuj")
    text = "\n".join(t for t, _ in out)
    assert "Cisza" in text or "nadstawia" in text or "raban" in text
