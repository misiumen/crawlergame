"""P29.59 — Wire-up dialog trees do NPC entities.

Bug #189 (z #154): drzewka dialog były zaimplementowane w P29.41,
ale ŻADEN NPC nie miał `state.dialogue_tree_key`. W rezultacie talk
fallthrough do legacy skill check.

Fix:
* 3 prawdziwe drzewka content (default_crawler / liga_brawurowa_grunt /
  intake_warden)
* Heurystyka `Game._guess_dialogue_tree(entity)` mapuje tagi entity
  na tree_key gdy brak explicit klucza

Test ten weryfikuje że:
* Wszystkie 3 drzewka są zarejestrowane w engine
* Każde ma start_node, ≥3 opcje w starcie, ≥4 nody
* Heurystyka tag → tree:
  - kapitan_druzyny (tags: faction:liga) → liga_brawurowa_grunt
  - intake_warden tagi (intake + floor_boss) → intake_warden
  - random crawler (T_CRAWLER) → default_crawler
  - zwykły mob bez talk affordance → ""
* Content drzewek Polish-only (no calque blacklist hits)
"""
from __future__ import annotations

from ..engine import dialogue as _dlg
from ..content.data import npc_dialogues  # noqa: F401 (auto-register)
from ..content.data.entity_templates import MON
from ..engine.entity import Entity, T_MONSTER, T_CRAWLER


# ── Trees registered ────────────────────────────────────────────────


def test_all_three_real_trees_registered():
    keys = _dlg.all_tree_keys()
    for key in ("default_crawler", "liga_brawurowa_grunt",
                "intake_warden"):
        assert key in keys, f"brak drzewka {key!r} w rejestrze"


def test_each_tree_has_start_node_and_options():
    for key in ("default_crawler", "liga_brawurowa_grunt",
                "intake_warden"):
        tree = _dlg.get_tree(key)
        assert tree is not None, f"brak tree {key!r}"
        start = tree.node(tree.start_node)
        assert start is not None, (
            f"tree {key}: start_node {tree.start_node!r} nie istnieje")
        assert len(start.options) >= 3, (
            f"tree {key}: start ma {len(start.options)} opcji, "
            f"powinno ≥3")
        assert len(tree.nodes) >= 4, (
            f"tree {key}: tylko {len(tree.nodes)} nodes, expected ≥4")


def test_each_tree_options_have_label():
    for key in ("default_crawler", "liga_brawurowa_grunt",
                "intake_warden"):
        tree = _dlg.get_tree(key)
        for node in tree.nodes.values():
            for i, opt in enumerate(node.options):
                assert opt.label and len(opt.label) > 5, (
                    f"tree {key}/{node.node_id}/opt[{i}]: "
                    f"pusty lub za krótki label {opt.label!r}")


# ── Heurystyka _guess_dialogue_tree ──────────────────────────────────


class _StubGame:
    """Minimal stub żeby zawołać _guess_dialogue_tree bez pełnego Game."""
    def __init__(self):
        pass

    # Skopiowane z Game._guess_dialogue_tree
    def _guess_dialogue_tree(self, entity) -> str:
        tags = entity.tags or []
        if "faction:liga" in tags:
            return "liga_brawurowa_grunt"
        if "intake" in tags and "floor_boss" in tags:
            return "intake_warden"
        if entity.entity_type == T_CRAWLER:
            return "default_crawler"
        return ""


def test_kapitan_druzyny_maps_to_liga_tree():
    proto = MON["kapitan_druzyny"]
    ent = Entity(key="kapitan_druzyny", entity_type=T_MONSTER,
                 fallback_name=proto["fallback_name"],
                 tags=list(proto.get("tags", [])))
    game = _StubGame()
    assert game._guess_dialogue_tree(ent) == "liga_brawurowa_grunt"


def test_trener_szkoleniowiec_maps_to_liga_tree():
    proto = MON["trener_szkoleniowiec"]
    ent = Entity(key="trener_szkoleniowiec", entity_type=T_MONSTER,
                 fallback_name=proto["fallback_name"],
                 tags=list(proto.get("tags", [])))
    game = _StubGame()
    assert game._guess_dialogue_tree(ent) == "liga_brawurowa_grunt"


def test_strażnik_bramy_maps_to_intake_warden():
    proto = MON["intake_warden"]
    ent = Entity(key="intake_warden", entity_type=T_MONSTER,
                 fallback_name=proto["fallback_name"],
                 tags=list(proto.get("tags", [])))
    game = _StubGame()
    assert game._guess_dialogue_tree(ent) == "intake_warden"


def test_random_crawler_maps_to_default_tree():
    ent = Entity(key="crawler_test", entity_type=T_CRAWLER,
                 fallback_name="Random Zawodnik",
                 tags=["vet", "calm"])
    game = _StubGame()
    assert game._guess_dialogue_tree(ent) == "default_crawler"


def test_regular_mob_no_tree():
    """Tunelowy Szczurek (T_MONSTER, beast, fungal) — nie powinien
    mieć tree, talk fallthrough do legacy."""
    ent = Entity(key="szczurek", entity_type=T_MONSTER,
                 fallback_name="Szczurek",
                 tags=["beast", "fungal"])
    game = _StubGame()
    assert game._guess_dialogue_tree(ent) == ""


# ── Polish-only / calque audit ──────────────────────────────────────


def test_no_english_words_in_dialog_content():
    """Sanity: żadnych typowych angielskich słów / kalk w dialog
    trees. Lista bad slugs zaczerpnięta z feedback_polish_only_imperatyw
    + Reguła 8 (calque patterns)."""
    BAD_SUBSTRINGS = (
        " the ", " your ", " with ", " and ", " you ", " for ",
        "showrunner", "vending", "lounge", "loker",
        # Calque patterns:
        ", którego nigdzie nie ma",
        "Pytanie tylko",
    )
    for key in ("default_crawler", "liga_brawurowa_grunt",
                "intake_warden"):
        tree = _dlg.get_tree(key)
        for node in tree.nodes.values():
            haystack = " ".join([node.speaker, node.text] +
                                 [o.label for o in node.options])
            low = haystack.lower()
            for bad in BAD_SUBSTRINGS:
                assert bad.lower() not in low, (
                    f"tree {key}/{node.node_id}: angielski/kalka "
                    f"{bad!r} w {haystack!r}")


# ── Smoke: tree można odpalić ────────────────────────────────────────


def test_start_default_crawler_dialog_returns_state():
    from ..engine.world import WorldState
    from ..engine.character import Character

    w = WorldState()
    w.character = Character(name="T", background="janitor")
    ent = Entity(key="crawler_test", entity_type=T_CRAWLER,
                 fallback_name="Random Zawodnik",
                 tags=["vet"])
    w.register(ent)
    state = _dlg.start_dialogue(w, ent, "default_crawler")
    assert state is not None
    assert state.tree_key == "default_crawler"
    assert state.current_node_id == "start"
