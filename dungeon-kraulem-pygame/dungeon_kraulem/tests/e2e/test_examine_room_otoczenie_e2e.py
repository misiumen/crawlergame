"""E2E P29.64 — panel OTOCZENIE + `zbadaj pomieszczenie`.

User (duży krok B): „to zbadanie pomieszczenia powinno też się rozciągać
na resztę rzeczy w pomieszczeniu". Realizacja:
  * panel kontekstowy nazwany jak świat: Istoty / Środowisko / Wyjścia,
  * `zbadaj pomieszczenie` = zunifikowane odkrycie, które UJAWNIA
    WŁAŚCIWOŚCI środowiska (łatwopalne / przewodzące / żrące...) przez
    silnik systemowy — gracz dedukuje użycie, menu nie podaje combosa,
  * `zbadaj <obiekt>` nadal działa jak sprawdź (inspect).
"""
from __future__ import annotations
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from ...engine import parser_core as _pc
from ...engine import systemic as _sys
from ...engine.entity import Entity, T_MONSTER, T_OBJECT
from ...ui import ui_nav as _nav
from .headless import HeadlessSession, assert_polish_only


def _obj(key, *, tags=None, name=None, dt="physical"):
    return Entity(key=key, entity_type=T_OBJECT, fallback_name=name or key,
                  tags=list(tags or []), damage_type=dt)


# ── Parser: zbadaj rozgałęzia na examine_room vs inspect ────────────


def test_parse_zbadaj_pomieszczenie_examine_room():
    for txt in ("zbadaj pomieszczenie", "zbadaj otoczenie", "zbadaj",
                "zbadaj pokój", "zbadaj wokół"):
        intent = _pc.parse(txt)
        assert intent.intent == "examine_room", f"{txt!r} → {intent.intent}"


def test_parse_zbadaj_object_routes_to_inspect():
    intent = _pc.parse("zbadaj rozdzielnię")
    assert intent.intent == "inspect"
    assert intent.targets and "rozdziel" in intent.targets[0].lower()


# ── systemic.salient_observations: właściwości, nie przepis ─────────


def test_observations_surface_flammable():
    regal = _obj("regal", tags=["łatwopalne"], name="regał")
    obs = _sys.salient_observations(regal)
    assert obs and any("ogni" in o.lower() for o in obs)


def test_observations_surface_element_of_hazard():
    kaluza = _obj("kaluza", tags=[], name="kałuża kwasu", dt="acid")
    obs = _sys.salient_observations(kaluza)
    assert obs and any("żr" in o.lower() or "syczy" in o.lower() for o in obs)


def test_observations_empty_for_inert():
    glaz = _obj("glaz", tags=["heavy"], name="głaz")
    assert _sys.salient_observations(glaz) == []


# ── Panel OTOCZENIE: etykiety i akcja zbadaj ────────────────────────


def test_group_labels_renamed_to_otoczenie():
    assert _nav.group_label(_nav.GROUP_OBJECTS) == "Środowisko"
    assert _nav.group_label(_nav.GROUP_ENTITIES) == "Istoty"
    assert _nav.group_label(_nav.GROUP_EXITS) == "Wyjścia"


def test_basic_actions_offer_examine_room():
    opts = _nav._basic_actions(None)
    ids = [o.option_id for o in opts]
    assert "act_examine" in ids
    examine = next(o for o in opts if o.option_id == "act_examine")
    assert examine.command == "zbadaj pomieszczenie"


# ── Integracja gry: pełny readout OTOCZENIA ─────────────────────────


def test_examine_room_lists_sections_and_properties():
    sess = HeadlessSession()
    being = Entity(key="szczur", entity_type=T_MONSTER,
                   fallback_name="Szczur tunelowy", hp=20, max_hp=20,
                   affordances=["attack"])
    regal = _obj("regal", tags=["łatwopalne"], name="regał z księgami")
    sess.put_in_room(being)
    sess.put_in_room(regal)
    # Dodaj wyjście do bieżącego pokoju.
    sess.current_room.exits = {"północ": {"target": "r_side"}}

    out = sess.send("zbadaj pomieszczenie")
    text = "\n".join(t for t, _ in out)
    assert "ISTOTY" in text and "Szczur" in text
    assert "ŚRODOWISKO" in text and "regał" in text
    assert "WYJŚCIA" in text and "północ" in text
    # Właściwość systemowa ujawniona (łatwopalność regału).
    assert any("ogni" in t.lower() for t, _ in out), "brak ujawnionej cechy"
    assert_polish_only(text)


def test_examine_room_empty_room_graceful():
    sess = HeadlessSession()
    sess.current_room.exits = {}
    out = sess.send("zbadaj pomieszczenie")
    text = "\n".join(t for t, _ in out)
    assert "Pusto" in text
