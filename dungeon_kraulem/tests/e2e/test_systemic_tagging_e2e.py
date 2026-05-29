"""E2E P29.65 — silnik A krok 2: cały bestiariusz reaguje na materię.

Zamiast ręcznie tagować 141 szablonów, właściwości są WNIOSKOWANE z tagów
contentu (robot→metal+przewodzące, fungal→łatwopalne, ceramic→kruche,
liquid→mokre, electric→źródło prądu). Jeden tag może dać kilka właściwości.

Dowodzi: archetypy reagują, źródła żywiołu są rozpoznawane, synergia
odpala na wywnioskowanych właściwościach — i NIE ma over-aplikacji
(zwykły humanoid/beast pozostaje obojętny na materię).
"""
from __future__ import annotations
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine import systemic as _sys
from ...engine.entity import Entity, T_MONSTER, T_OBJECT


def _e(*tags, dt="physical", hp=30, ac=12):
    return Entity(key="t", entity_type=T_MONSTER, fallback_name="cel",
                  tags=list(tags), damage_type=dt, hp=hp, max_hp=hp, ac=ac)


# ── Inferencja właściwości celu ─────────────────────────────────────


def test_robot_is_metal_and_conductive():
    props = _sys.target_matter_props(_e("monster", "robot"))
    assert "metal" in props and "przewodzące" in props


def test_armored_is_metal():
    assert "metal" in _sys.target_matter_props(_e("humanoid", "armored"))


def test_fungal_and_wood_are_flammable():
    assert "łatwopalne" in _sys.target_matter_props(_e("monster", "fungal"))
    assert "łatwopalne" in _sys.target_matter_props(_e("furniture", "wood"))


def test_ceramic_is_fragile():
    assert "kruche" in _sys.target_matter_props(_e("ceramic"))


def test_liquid_is_wet():
    assert "mokre" in _sys.target_matter_props(_e("water", "liquid"))


def test_no_overapplication_on_generic_mob():
    """Zwykły humanoid/beast bez materiałowego tagu = obojętny."""
    assert _sys.target_matter_props(_e("monster", "humanoid", "beast")) == set()
    assert _sys.target_matter_props(_e("monster", "fast", "cunning")) == set()


# ── Inferencja źródła żywiołu ───────────────────────────────────────


def test_electric_tag_is_prad_source():
    assert "prąd" in _sys.source_elements(_e("electric", "spark"))


def test_acid_tag_is_kwas_source():
    assert "kwas" in _sys.source_elements(_e("acid", "hazardous"))


def test_passive_metal_is_not_a_source():
    # Sam metal/wire NIE jest aktywnym źródłem (to cel, nie hazard).
    assert _sys.source_elements(_e("metal", "wire")) == set()


# ── Synergia odpala na WYWNIOSKOWANYCH właściwościach ───────────────


def test_acid_corrodes_inferred_metal():
    kwas = Entity(key="kaluza", entity_type=T_OBJECT,
                  fallback_name="kałuża kwasu", tags=["acid"])
    guard = _e("humanoid", "armored", ac=16)
    pre = guard.ac
    r = _sys.resolve(None, "wepchnij", kwas, guard)
    assert r.matched and r.effect == "korozja" and guard.ac < pre


def test_fire_ignites_inferred_flammable_mob():
    czar = Entity(key="czar", entity_type=T_OBJECT,
                  fallback_name="ogień", tags=["fire"])
    grzyb = _e("monster", "fungal")
    r = _sys.resolve(None, "rzuć", czar, grzyb)
    assert r.matched and r.effect == "pożar"
    assert _sys.has_systemic_status(grzyb, "płonie")


# ── Pokrycie realnego bestiariusza ──────────────────────────────────


def test_real_bestiary_lights_up_broadly():
    """Po inferencji wyraźny odłam realnych mobów ma właściwości materii
    (opancerzeni korodują, grzybnia płonie, maszyny rażą) — silnik gryzie
    na contencie, nie tylko na encjach testowych. Reszta (czyste mięso)
    będzie reagować przez inne rodziny reguł (psychika itd.)."""
    from ...content.data.entity_templates import MON
    reactive = 0
    for tmpl in MON.values():
        tags = tmpl.get("tags") or []
        dummy = Entity(key="x", entity_type=T_OBJECT, fallback_name="x",
                       tags=list(tags))
        if _sys.target_matter_props(dummy) or _sys.source_elements(dummy):
            reactive += 1
    assert reactive >= 12, (
        f"za mało reaktywnych mobów: {reactive} (oczekiwane ≥12)")
