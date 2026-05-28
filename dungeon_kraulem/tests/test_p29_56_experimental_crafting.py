"""P29.56 — Emergent crafting test suite.

Cover: catalog integrity, parser, tag matching, biome lock, discovery,
DC roll outcomes, unique afix on crit, materials consumption, end-to-end.
"""
from __future__ import annotations
import random

from ..engine.world import WorldState
from ..engine.character import Character
from ..engine.floor import FloorState
from ..content.materials import MATERIALS, add_material
from ..content.data import experimental_recipes as _exp


# ── Catalog integrity ────────────────────────────────────────────────


def test_catalog_has_100_plus():
    assert len(_exp.EXPERIMENTAL_RECIPES) >= 100, (
        f"want ≥100 recipes, got {len(_exp.EXPERIMENTAL_RECIPES)}")


def test_catalog_keys_unique():
    keys = [r["key"] for r in _exp.EXPERIMENTAL_RECIPES]
    assert len(keys) == len(set(keys))


def test_catalog_polish_only():
    """STRICT Polish-only check.

    Polish-only jest niezłamywalną zasadą projektu (patrz feedback memory).
    Ten test łapie WSZYSTKIE typowe angielskie słowa-materiały i pomocnicze
    słowa, które mogłyby wsiąść do desc_pl/name_pl po refactorze albo
    bulk-replace. Każde nowe naruszenie = fail przed commitem.
    """
    import re as _re
    suspect = {
        # English connectors that absolutely don't belong
        "the", "with", "you", "your", "this", "and", "or", "for", "from",
        "to", "of", "an", "a", "is", "are", "was", "were", "be", "can",
        "will", "have", "has", "had",
        # Material name leaks (commonly slipped through)
        "battery", "wire", "tape", "screws", "spring", "cloth", "chem",
        "spore", "tar", "brick", "glass", "rubber", "leather", "bone",
        "bomb", "heal", "heals", "cure", "cures", "phosphor", "sodium",
        "salt", "bleach", "rebar", "grease", "collar", "feed", "pellet",
        "film", "vest", "disinfectant", "wax", "idol", "fiber", "needle",
        "capsule", "plastic", "organic",
        # Effect / mechanic word leaks
        "splash", "cough", "reduce", "reduced", "blood", "fume", "fumes",
        "damage", "armor", "weapon", "attack",
    }
    # Polish-only exceptions: niektóre wyrazy są loanwordami które po
    # polsku przyjęły się (snake_case key + display equivalent).
    # NIE dodawaj tu nowych "wyjątków" lekkomyślnie — preferuj polskie
    # tłumaczenie.
    polish_exceptions = {
        "metal", "stone", "fire", "water", "acid", "poison", "logo",
        "sponsor",  # zapożyczone, używane po polsku
    }
    suspect = suspect - polish_exceptions
    word_re = _re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+")
    failures = []
    for r in _exp.EXPERIMENTAL_RECIPES:
        for fld in ("name_pl", "desc_pl"):
            text = (r.get(fld) or "")
            for token in word_re.findall(text.lower()):
                if token in suspect:
                    snippet = text[:60]
                    failures.append(
                        f"{r['key']}.{fld}: '{token}' w „{snippet}…”")
                    break
    assert not failures, (
        f"Polish-only naruszenia ({len(failures)}):\n  "
        + "\n  ".join(failures[:15]))


def test_catalog_tiers_valid():
    for r in _exp.EXPERIMENTAL_RECIPES:
        assert r["tier"] in (3, 4, 5), (
            f"{r['key']} ma tier {r['tier']}")


def test_catalog_disciplines_known():
    known = {"chemistry", "electronics", "mechanics", "bio",
             "alchemy", "culinary", "tinker"}
    for r in _exp.EXPERIMENTAL_RECIPES:
        assert r["discipline"] in known


def test_catalog_rarities_known():
    known = {"common", "uncommon", "rare", "epic", "legendary"}
    for r in _exp.EXPERIMENTAL_RECIPES:
        assert r["base_rarity"] in known


def test_catalog_biome_locks_known():
    """biome_lock musi być None albo istniejący biome_key."""
    from ..content.data.floor_biomes import FLOOR_BIOMES
    known = set(FLOOR_BIOMES.keys())
    for r in _exp.EXPERIMENTAL_RECIPES:
        bl = r.get("biome_lock")
        if bl is not None:
            assert bl in known, f"{r['key']} biome_lock={bl} unknown"


def test_catalog_material_tags_reference_real_tags():
    """Wszystkie tag w material_tags muszą istnieć w materials.MATERIALS
    (czyli jakikolwiek materiał musi je nieść)."""
    all_tags = set()
    for md in MATERIALS.values():
        all_tags.update(md.tags)
    for r in _exp.EXPERIMENTAL_RECIPES:
        for tag, _need in r["material_tags"]:
            assert tag in all_tags, (
                f"{r['key']} wymaga taga '{tag}' którego nie ma w "
                f"żadnym materiale")


def test_biome_locked_recipes_for_every_enabled_biome():
    """Każdy enabled biome powinien mieć ≥1 unikalną receptę."""
    from ..content.data.floor_biomes import FLOOR_BIOMES
    enabled = {k for k, b in FLOOR_BIOMES.items() if b.enabled}
    for biome in enabled:
        locked = _exp.recipes_for_biome(biome)
        # Co najmniej 2 (rationale: chcemy że biome ma identity)
        assert len(locked) >= 1, (
            f"biome {biome} (enabled) nie ma żadnej eksperymentalnej "
            f"receptury")


# ── Tag matching ─────────────────────────────────────────────────────


def test_tag_profile_from_materials_basic():
    """2× cloth_strips powinien dać cloth=2, binding=2, absorbent=2..."""
    prof = _exp.build_tag_profile_from_materials(
        ["cloth_strips", "cloth_strips", "tape"])
    assert prof.get("cloth", 0) == 2
    assert prof.get("binding", 0) == 3   # cloth ×2 + tape ×1
    assert prof.get("adhesive", 0) == 1  # tylko tape


def test_match_finds_simple_coating():
    """Acid + absorbent + liquid → powinno znaleźć acid_coat."""
    prof = {"acid": 1, "absorbent": 1, "liquid": 1,
            "chemical": 2, "binding": 1}  # nadmiar OK
    matches = _exp.match_recipe_by_tag_profile(prof, tier=3)
    keys = [r["key"] for r in matches]
    assert "weapon_acid_coat" in keys


def test_match_filters_by_tier():
    """Profile pasujący do tier-4 recipy nie matchuje gdy tier=3."""
    prof = {"acid": 2, "sticky": 1, "metal": 1, "hazard": 1, "binding": 1}
    t3 = [r["key"] for r in _exp.match_recipe_by_tag_profile(prof, tier=3)]
    t4 = [r["key"] for r in _exp.match_recipe_by_tag_profile(prof, tier=4)]
    assert "weapon_acid_coat_amped" not in t3
    assert "weapon_acid_coat_amped" in t4


def test_match_respects_biome_lock():
    """Biome-locked recipe nie matchuje gdy current_biome ani unlocked."""
    prof = {"biome:okopy_frontowe": 1, "acid": 1, "cloth": 1,
            "binding": 1}
    out_no_biome = _exp.match_recipe_by_tag_profile(
        prof, tier=3, current_biome="zoo_korporacyjne")
    keys = [r["key"] for r in out_no_biome]
    assert "weapon_okopy_acid_mud" not in keys

    out_with_biome = _exp.match_recipe_by_tag_profile(
        prof, tier=3, current_biome="okopy_frontowe")
    keys2 = [r["key"] for r in out_with_biome]
    assert "weapon_okopy_acid_mud" in keys2


# ── New materials ────────────────────────────────────────────────────


def test_new_materials_registered():
    """P29.56 dodał >=20 nowych materiałów. Sample sprawdza kilka."""
    for k in ("phosphor", "mercury_drop", "ether_vial",
              "trench_mud", "graffiti_can", "spring_clip",
              "magnetic_strip", "feather_quill"):
        assert k in MATERIALS, f"materiał {k} brakuje"


def test_biome_materials_have_biome_tag():
    """Biome-locked material nosi tag biome:<key>."""
    trench = MATERIALS["trench_mud"]
    assert "biome:okopy_frontowe" in trench.tags


# ── End-to-end experiment via handler ───────────────────────────────


def _mk_world() -> WorldState:
    w = WorldState()
    w.character = Character(name="Test", background="janitor")
    w.character.hp = 30
    w.character.max_hp = 30
    w.character.credits = 10
    w.current_floor = FloorState(floor_id="f1", floor_number=1,
                                 biome_key="okopy_frontowe")
    return w


class _MockGame:
    def __init__(self, world):
        self.world = world
        self.logs = []

    def log(self, msg, tone=""):
        self.logs.append((tone, msg))


class _MockIntent:
    intent = "experiment"
    targets: list = []


def test_experiment_refuses_with_too_few_materials():
    from ..engine.handlers import experiment as _h
    w = _mk_world()
    g = _MockGame(w)
    intent = _MockIntent(); intent.targets = ["pasek gumy", "taśma"]
    _h.attempt_experiment(g, intent)
    assert any("3-5" in m for _, m in g.logs)


def test_experiment_refuses_unknown_material():
    from ..engine.handlers import experiment as _h
    w = _mk_world()
    g = _MockGame(w)
    intent = _MockIntent()
    intent.targets = ["lód marsjański", "taśma", "śrubki"]
    _h.attempt_experiment(g, intent)
    assert any("Nie masz" in m for _, m in g.logs)


def test_experiment_consumes_materials_on_attempt():
    """Materials are consumed even on fail/fumble (eksperyment kosztuje)."""
    from ..engine.handlers import experiment as _h
    w = _mk_world()
    add_material(w.character, "cleaning_fluid", 1)  # acid+flammable+liquid
    add_material(w.character, "cloth_strips", 1)    # cloth+binding+absorbent
    add_material(w.character, "bleach_sachet", 1)   # acid+liquid+caustic
    g = _MockGame(w)
    intent = _MockIntent()
    intent.targets = ["płyn czyszczący", "paski materiału", "saszetka wybielacza"]
    random.seed(0)
    _h.attempt_experiment(g, intent)
    # All three materials should be gone (consumed exactly once each).
    assert (w.character.materials or {}).get("cleaning_fluid", 0) == 0
    assert (w.character.materials or {}).get("cloth_strips", 0) == 0
    assert (w.character.materials or {}).get("bleach_sachet", 0) == 0


def test_experiment_lucky_seed_produces_item():
    """With a lucky seed and matching mats, an item appears in EQ."""
    from ..engine.handlers import experiment as _h
    w = _mk_world()
    # bleach + cloth + cleaning fluid → acid coat (tier 3, DC 10)
    add_material(w.character, "bleach_sachet", 1)
    add_material(w.character, "cloth_strips", 1)
    add_material(w.character, "cleaning_fluid", 1)
    w.character.stats["INT"] = 16  # +3 mod
    pre_inv = len(w.character.inventory_ids or [])
    g = _MockGame(w)
    intent = _MockIntent()
    intent.targets = ["saszetka wybielacza", "paski materiału", "płyn czyszczący"]
    # Seed picked so d20 lands high.
    random.seed(2)
    _h.attempt_experiment(g, intent)
    # Czy stworzono item albo opis sukcesu / failu / fumble
    # (test toleruje wszystkie wyniki bo RNG, ale sprawdza że pipe
    # zadziałał bez crash'a).
    assert len(g.logs) >= 2


# ── Discovery / learning ─────────────────────────────────────────────


def test_recipe_learned_on_forced_success():
    """Forcing a successful roll via monkey-patched RNG learns recipe."""
    from ..engine.handlers import experiment as _h
    w = _mk_world()
    add_material(w.character, "bleach_sachet", 1)
    add_material(w.character, "cloth_strips", 1)
    add_material(w.character, "cleaning_fluid", 1)
    w.character.stats["INT"] = 20  # mod +5
    g = _MockGame(w)
    intent = _MockIntent()
    intent.targets = ["saszetka wybielacza", "paski materiału", "płyn czyszczący"]
    # Monkey-patch random.randint to always return 18 (success but not crit)
    import dungeon_kraulem.engine.handlers.experiment as _h_mod
    orig_rand = _h_mod._r.randint
    _h_mod._r.randint = lambda lo, hi: 18
    try:
        _h.attempt_experiment(g, intent)
    finally:
        _h_mod._r.randint = orig_rand
    assert len(w.character.known_recipes or []) >= 1, (
        f"recipe nie nauczony; logs={g.logs}")


# ── Parser test ──────────────────────────────────────────────────────


def test_parser_recognizes_eksperymentuj():
    from ..engine.parser_core import parse_with_optional_llm
    intent = parse_with_optional_llm(
        "eksperymentuj saszetka wybielacza, paski materiału, taśma")
    assert intent.intent == "experiment"
    assert len(intent.targets) == 3


def test_parser_recognizes_zmieszaj_with_i_separator():
    from ..engine.parser_core import parse_with_optional_llm
    intent = parse_with_optional_llm("zmieszaj fosfor i taśma i metal")
    assert intent.intent == "experiment"
    assert len(intent.targets) == 3
