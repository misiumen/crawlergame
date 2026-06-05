"""E2E dla P29.61 krok 1 — systemowy silnik reguł materii.

Dowodzi że resolver dopasowuje TAGI (nie obiekty) i produkuje
emergentne interakcje. Te same 5 reguł obsłuży później dowolny
otagowany obiekt/moba/czar.

Rule 12b — testy capturują core behaviour silnika immersive sim.
"""
from __future__ import annotations

from ...engine import systemic as _sys
from ...engine.entity import Entity, T_MONSTER, T_OBJECT, T_HAZARD


def _mk(key, *, tags=None, damage_type="physical", hp=0, ac=10,
        name=None):
    return Entity(
        key=key, entity_type=T_MONSTER if hp else T_OBJECT,
        fallback_name=name or key,
        tags=list(tags or []), damage_type=damage_type,
        hp=hp, max_hp=hp, ac=ac)


# ── Reguła 1: ogień + łatwopalne → pożar ────────────────────────────


def test_fire_source_ignites_flammable_target():
    koktajl = _mk("koktajl", damage_type="fire", name="koktajl zapalający")
    regal = _mk("regal", tags=["łatwopalne"], name="regał z księgami")

    r = _sys.resolve(None, "rzuć", koktajl, regal)
    assert r.matched is True
    assert r.effect == "pożar"
    assert _sys.has_systemic_status(regal, "płonie")
    assert any("płomien" in l.lower() for l in r.lines)


def test_fire_source_via_pl_tag_ignites():
    """Źródło może deklarować element wprost tagiem PL (czar żywiołów /
    crafted item bez damage_type)."""
    czar = _mk("czar_ognia", tags=["ogień"], name="zaklęcie ognia")
    regal = _mk("regal", tags=["łatwopalne"])
    r = _sys.resolve(None, "rzuć", czar, regal)
    assert r.matched and r.effect == "pożar"


# ── Reguła 2: prąd + przewodzące → porażenie ────────────────────────


def test_electric_source_shocks_conductive_target():
    zwarcie = _mk("zwarcie", damage_type="electric", name="zwarcie kablowe")
    mokry_wrog = _mk("szczur", tags=["przewodzące"], hp=40,
                     name="Szczur w kałuży")
    pre_hp = mokry_wrog.hp
    r = _sys.resolve(None, "wepchnij", zwarcie, mokry_wrog)
    assert r.matched and r.effect == "porażenie"
    assert mokry_wrog.hp < pre_hp, "porażenie powinno zadać obrażenia"
    assert _sys.has_systemic_status(mokry_wrog, "porażony")


# ── Reguła 3: kwas + metal → korozja (AC down) ──────────────────────


def test_acid_corrodes_metal_target_ac():
    kwas = _mk("kaluza_kwasu", damage_type="acid", name="kałuża kwasu")
    opancerzony = _mk("strazni", tags=["metal"], hp=30, ac=16,
                      name="Strażnik w zbroi")
    pre_ac = opancerzony.ac
    r = _sys.resolve(None, "wepchnij", kwas, opancerzony)
    assert r.matched and r.effect == "korozja"
    assert opancerzony.ac < pre_ac, "korozja powinna obniżyć AC"


# ── Reguła 4: mróz + mokre → zamrożenie ─────────────────────────────


def test_frost_freezes_wet_target():
    czar_mrozu = _mk("czar_mrozu", damage_type="cold")
    mokry = _mk("mokry_mob", tags=["mokre"], hp=20)
    r = _sys.resolve(None, "rzuć", czar_mrozu, mokry)
    assert r.matched and r.effect == "zamrożenie"
    assert _sys.has_systemic_status(mokry, "zamrożony")


# ── Reguła 5: uderzenie + kruche → roztrzaskanie ────────────────────


def test_blunt_shatters_fragile_target():
    palka = _mk("palka", tags=["blunt"], name="zardzewiała pałka")
    gablota = _mk("gablota", tags=["kruche"], hp=10, name="gablota szklana")
    r = _sys.resolve(None, "uderz", palka, gablota)
    assert r.matched and r.effect == "roztrzaskanie"
    assert gablota.hp <= 2, "kruche powinno paść niemal od razu"


# ── No-match: graceful ──────────────────────────────────────────────


def test_fire_on_metal_no_match():
    """Ogień na metalu (bez łatwopalności) = brak reguły, grzecznie."""
    koktajl = _mk("koktajl", damage_type="fire")
    metal_obj = _mk("metalowa_skrzynia", tags=["metal"])
    r = _sys.resolve(None, "rzuć", koktajl, metal_obj)
    assert r.matched is False
    assert r.lines == []


def test_no_element_source_no_match():
    """Źródło bez elementu (zwykły physical) = brak interakcji."""
    noz = _mk("noz", damage_type="physical")
    regal = _mk("regal", tags=["łatwopalne"])
    r = _sys.resolve(None, "rzuć", noz, regal)
    assert r.matched is False


def test_none_source_or_target_safe():
    assert _sys.resolve(None, "rzuć", None, None).matched is False
    regal = _mk("regal", tags=["łatwopalne"])
    assert _sys.resolve(None, "rzuć", None, regal).matched is False


# ── Element display mapping (PL) ────────────────────────────────────


def test_element_pl_mapping():
    assert _sys.element_pl("fire") == "ogień"
    assert _sys.element_pl("acid") == "kwas"
    assert _sys.element_pl("electric") == "prąd"
    assert _sys.element_pl("cold") == "mróz"
    # physical bez mapowania → fallback (nie wyświetlane jako element)
    assert _sys.element_pl("physical") == "physical"


# ── Polish-only: log lines bez angielskich kalk ─────────────────────


def test_environmental_acid_vs_electric_differ():
    """A (user feedback): kwas ≠ prąd. Różne flavor + status + DoT,
    nawet na celu BEZ synergii (zwykły szczur, nie metal/przewodzące)."""
    acid = _mk("kaluza", damage_type="acid", name="kałuża kwasu")
    cable = _mk("zwarcie", damage_type="electric", name="zwarcie")
    rat_a = _mk("szczur_a", tags=["small"], hp=40, name="Szczur")
    rat_b = _mk("szczur_b", tags=["small"], hp=40, name="Szczur")

    r_acid = _sys.apply_environmental(None, "wepchnij", acid, rat_a)
    r_elec = _sys.apply_environmental(None, "wepchnij", cable, rat_b)

    assert r_acid.matched and r_elec.matched
    # Różne efekty / linie / statusy
    assert r_acid.effect != r_elec.effect, "kwas i prąd ten sam efekt!"
    assert r_acid.lines[0] != r_elec.lines[0], "identyczny flavor!"
    assert _sys.has_systemic_status(rat_a, "trawiony kwasem")
    assert _sys.has_systemic_status(rat_b, "porażony")
    # Kwas zostawia DoT, prąd zostawia szansę stunu
    assert (rat_a.state or {}).get("systemic_dot") is not None
    assert (rat_b.state or {}).get("systemic_stun_chance") is not None


def test_environmental_each_element_distinct_flavor():
    """5 żywiołów = 5 różnych linii bazowych."""
    seen = set()
    for dt, name in [("acid", "kwas"), ("electric", "prąd"),
                     ("fire", "ogień"), ("cold", "mróz")]:
        src = _mk("src", damage_type=dt)
        tgt = _mk("t", tags=["small"], hp=40, name="Cel")
        r = _sys.apply_environmental(None, "wepchnij", src, tgt)
        assert r.matched, f"żywioł {dt} nie zadziałał bazowo"
        seen.add(r.lines[0])
    assert len(seen) == 4, f"flavor się powtarza: {seen}"


def test_all_rule_logs_polish_only():
    """Każdy szablon logu reguły materii Polish-only."""
    BAD = (" the ", " fire", " acid", "shatter", "frozen", "burns")
    for _el, _prop, _eff, _status, tmpl in _sys._MATTER_RULES:
        low = (" " + tmpl.lower() + " ")
        for bad in BAD:
            assert bad not in low, (
                f"reguła {_eff}: angielski {bad!r} w {tmpl!r}")
