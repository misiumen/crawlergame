"""P29.57b — VS-style box system: infrastructure + UI + pipelines.

Pokrywa:
* make_box helper tworzy entity z poprawnym tag/state
* attempt_open_box: spawn contents w EQ, consume box, 3 linie reveal
* Parser rozpoznaje „otwórz skrzynkę X" jako intent open_box
* UI tab „Skrzynki" filtruje EQ po tag box
* Skrzynki SĄ wykluczone z tabu Ekwipunek
* Pipelines: sponsor gift + boon → boxes (test_p29_53r covers)
"""
from __future__ import annotations
import random

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..engine.handlers.boxes import (
    make_box, attempt_open_box, tier_label_for_rarity,
    _REVEAL_BY_SOURCE,
)
from ..engine.parser_core import parse_with_optional_llm
from ..ui import ui_nav as _nav


def _mk_world() -> WorldState:
    w = WorldState()
    w.character = Character(name="Tester", background="janitor")
    w.character.credits = 0
    w.current_floor = FloorState(floor_id="f1", floor_number=1)
    return w


class _MockGame:
    def __init__(self, world):
        self.world = world
        self.logs = []

    def log(self, msg, tone=""):
        self.logs.append((tone, msg))


class _MockIntent:
    intent = "open_box"
    targets: list = []
    verb = "otwórz"


# ── make_box ────────────────────────────────────────────────────────


def test_make_box_creates_entity_with_correct_tags():
    w = _mk_world()
    box = make_box(w, source="boss",
                   source_name="Pyskaty Bandzior",
                   contents=[{"item_key": "bandage", "qty": 1}],
                   rarity="common")
    assert "box" in box.tags
    assert "unopened" in box.tags
    assert "box_source:boss" in box.tags
    assert box.entity_id in w.character.inventory_ids


def test_box_state_carries_metadata():
    w = _mk_world()
    box = make_box(w, source="sponsor",
                   source_name="NovaChem-Biotech",
                   contents=[{"item_key": "stimpak", "qty": 2}],
                   rarity="rare",
                   sponsor_tagline="Działa. Boli. Sprzedaje się.")
    state = box.state or {}
    assert state["box_source"] == "sponsor"
    assert state["box_source_name"] == "NovaChem-Biotech"
    assert state["box_contents"][0]["item_key"] == "stimpak"
    assert state["box_contents"][0]["qty"] == 2
    assert state["sponsor_tagline"] == "Działa. Boli. Sprzedaje się."
    assert state["rarity"] == "rare"


def test_tier_label_per_rarity():
    """Skrzynki mają polskie tier labels per rarity (przyszły Boss
    Box system w Etapie B użyje tych samych)."""
    assert tier_label_for_rarity("common") == "Skrzynka Brązowa"
    assert tier_label_for_rarity("uncommon") == "Skrzynka Srebrna"
    assert tier_label_for_rarity("rare") == "Skrzynka Złota"
    assert tier_label_for_rarity("epic") == "Skrzynka Platynowa"
    assert tier_label_for_rarity("legendary") == "Skrzynka Diamentowa"


# ── attempt_open_box ────────────────────────────────────────────────


def test_open_box_spawns_credits():
    w = _mk_world()
    make_box(w, source="mob",
             contents=[{"item_key": "credits", "qty": 25}],
             rarity="common")
    g = _MockGame(w)
    intent = _MockIntent()
    intent.targets = ["mob"]   # match by name (display contains "mob"
                                # actually no — display contains "Skrzynka
                                # Brązowa od …"). Use better fallback.
    # Faktycznie display name to "Skrzynka Brązowa". Match'uj po tym.
    intent.targets = ["Skrzynka"]
    attempt_open_box(g, intent)
    assert w.character.credits == 25, (
        f"kredyty nie zaszły: {w.character.credits}, logs: {g.logs}")


def test_open_box_spawns_item_in_eq():
    w = _mk_world()
    make_box(w, source="sponsor",
             source_name="dr_crucible",
             contents=[{"item_key": "bandage", "qty": 1}],
             rarity="common")
    pre_eq = len(w.character.inventory_ids or [])
    g = _MockGame(w)
    intent = _MockIntent()
    intent.targets = ["Skrzynka"]
    attempt_open_box(g, intent)
    post_eq = len(w.character.inventory_ids or [])
    # Box usunięty (1 mniej), item dodany (1 więcej) → net 0,
    # ale w EQ powinien być bandage zamiast skrzynki.
    assert post_eq == pre_eq, f"EQ delta wrong (pre={pre_eq}, post={post_eq})"
    # Check że jest bandage — może być aliasowane (P29.43 aliases
    # „bandage" → „dirty_bandage"), więc szukamy obu albo tagu medical.
    has_item = False
    for eid in (w.character.inventory_ids or []):
        ent = w.entities.get(eid)
        if ent is None:
            continue
        if ent.key in ("bandage", "dirty_bandage") or \
                "medical" in (ent.tags or []):
            has_item = True
            break
    assert has_item, (
        f"item z box.contents nie pojawił się w EQ; "
        f"items: {[w.entities.get(e).key for e in w.character.inventory_ids if w.entities.get(e)]}")


def test_open_box_consumes_skrzynkę():
    """Skrzynka znika z listy unopened po otwarciu."""
    w = _mk_world()
    box = make_box(w, source="boss",
                   contents=[{"item_key": "credits", "qty": 10}],
                   rarity="common")
    g = _MockGame(w)
    intent = _MockIntent()
    intent.targets = ["Skrzynka"]
    attempt_open_box(g, intent)
    # Box już nie powinien być w EQ (consumed)
    assert box.entity_id not in (w.character.inventory_ids or [])


def test_open_box_emits_3_line_reveal():
    w = _mk_world()
    make_box(w, source="rezyser",
             source_name="Reżyser",
             contents=[{"item_key": "credits", "qty": 5}],
             rarity="uncommon")
    g = _MockGame(w)
    intent = _MockIntent()
    intent.targets = ["Skrzynka"]
    attempt_open_box(g, intent)
    # 3 linie reveal per source template
    assert len(g.logs) == 3, f"oczekiwano 3 linii, dostałem {g.logs}"


def test_open_box_unknown_box_fails_gracefully():
    w = _mk_world()
    g = _MockGame(w)
    intent = _MockIntent()
    intent.targets = ["Nie istnieje"]
    attempt_open_box(g, intent)
    # Powinien być log warn, nie crash
    assert any("Nie masz" in m for _, m in g.logs)


# ── Reveal templates są polish-only ──────────────────────────────────


def test_reveal_templates_polish_only():
    """Sanity check że żaden template nie ma typowych angielskich
    słów."""
    suspect = {"the", "your", "with", "and", "you", "drop-pod",
               "drone", "showrunner"}
    # uwaga: „drop-pod" zostawiamy specjalnie w skrzyni Drop-Pod
    # bo to nasz wewnętrzny termin — OK loanword.
    for source, lines in _REVEAL_BY_SOURCE.items():
        if source == "drop_pod":
            continue
        for line in lines:
            words = line.lower().split()
            for w in words:
                clean = w.strip(".,!?'\"„”():→")
                assert clean not in suspect, (
                    f"reveal[{source}]: angielskie słowo '{clean}' "
                    f"w {line!r}")


# ── Parser ──────────────────────────────────────────────────────────


def test_parser_recognizes_otworz_skrzynke():
    intent = parse_with_optional_llm("otwórz skrzynkę Brązową")
    assert intent.intent == "open_box"
    assert len(intent.targets) >= 1


def test_parser_recognizes_rozpakuj_premie():
    intent = parse_with_optional_llm("rozpakuj premię Reżysera")
    assert intent.intent == "open_box"


# ── UI tab ──────────────────────────────────────────────────────────


def test_boxes_tab_lists_unopened_boxes():
    w = _mk_world()
    make_box(w, source="boss",
             contents=[{"item_key": "credits", "qty": 5}],
             rarity="common")
    opts = _nav._box_options(w)
    assert len(opts) == 1
    assert opts[0].command.startswith("otwórz skrzynkę")
    assert opts[0].group == _nav.GROUP_BOXES


def test_boxes_tab_empty_when_no_boxes():
    w = _mk_world()
    assert _nav._box_options(w) == []


def test_boxes_tab_label_is_polish():
    assert _nav.group_label(_nav.GROUP_BOXES) == "Skrzynki"


def test_boxes_excluded_from_ekwipunek_tab():
    """Skrzynki nie powinny pojawiać się w Ekwipunek (mają własny tab)."""
    w = _mk_world()
    make_box(w, source="boss",
             contents=[{"item_key": "credits", "qty": 5}],
             rarity="common")
    inv_flat = _nav._flat_inventory_verbs(w)
    # Żaden item w flat inventory nie powinien mieć tag „box"
    for opt in inv_flat:
        # find entity
        eid = opt.target_id
        ent = w.entities.get(eid)
        if ent is None:
            continue
        assert "box" not in (ent.tags or []), (
            f"skrzynka pojawia się w Ekwipunek: {opt.label}")
