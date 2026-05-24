"""Crafting engine (Prompt 06).

Two paths:
  1. Known recipes — exact material requirements + tags.
  2. Improvised crafting — pick a category, ensure player has materials
     with the right tag SETS, run a stat check, produce a generic item.

Both paths feed through resolution levels (critical_success / success /
partial / failure / critical_failure) and produce a result dict the
consequence engine consumes.

Public entry:
  try_known_recipe(character, recipe_key, room=None) -> dict
  try_improvise(character, category, mentioned_materials=None, mentioned_tools=None) -> dict

Both return:
  {
    "valid":          bool,
    "reason":         str,                # if not valid
    "fallback_message": str,              # immersive feedback
    "recipe_key":     str | None,
    "category":       str | None,
    "stat":           "INT|DEX|WIS|CHA|...",
    "dc":             int,
    "required_materials": dict,
    "required_tools":     list,
    "time_cost":      int,
    "risks":          list,
    "rewards":        list,
    "result_item":    str | None,         # entity-template key to instantiate on success
    "category_label_pl": str,
  }
"""
from typing import Dict, List, Optional, Tuple

from . import materials


# ── Catalog accessors ───────────────────────────────────────────────────────

def all_recipes() -> Dict[str, Dict]:
    try:
        from .data.recipe_templates import RECIPES
        return RECIPES
    except Exception:
        return {}


def improvised_categories() -> Dict[str, Dict]:
    try:
        from .data.recipe_templates import IMPROVISED_CATEGORIES
        return IMPROVISED_CATEGORIES
    except Exception:
        return {}


def recipes_by_category(category: str) -> List[Tuple[str, Dict]]:
    return [(k, v) for k, v in all_recipes().items() if v.get("category") == category]


# ── Material/tag matching ────────────────────────────────────────────────────

def _player_material_tag_pool(character) -> Dict[str, int]:
    """Return tag -> available unit count across the character's materials."""
    pool = getattr(character, "materials", None) or {}
    tag_totals: Dict[str, int] = {}
    for key, qty in pool.items():
        md = materials.get(key)
        if not md: continue
        for tag in md.tags:
            tag_totals[tag] = tag_totals.get(tag, 0) + qty
    return tag_totals


def _matches_tag_set(character, required_set) -> bool:
    """All tags in required_set must be available in the player's pool."""
    if not required_set:
        return True
    tag_pool = _player_material_tag_pool(character)
    return all(tag_pool.get(t, 0) >= 1 for t in required_set)


# ── Known recipe attempt ─────────────────────────────────────────────────────

def try_known_recipe(character, recipe_key: str, room=None) -> Dict:
    """Validate that the player can attempt a known recipe."""
    rec = all_recipes().get(recipe_key)
    if rec is None:
        return _invalid("unknown_recipe",
                        f"Nie znasz takiego przepisu: „{recipe_key}”.")

    needed = rec.get("required_materials") or {}
    if not materials.has_materials(character, needed):
        # List specifically what's missing
        missing = []
        pool = getattr(character, "materials", None) or {}
        for k, v in needed.items():
            have = pool.get(k, 0)
            if have < v:
                md = materials.get(k)
                name = md.name() if md else k
                missing.append(f"{v - have}x {name}")
        return _invalid("missing_materials",
                        "Brakuje: " + ", ".join(missing))

    req_tags = rec.get("required_tags") or []
    if req_tags and not _matches_tag_set(character, req_tags):
        return _invalid("missing_material_tags",
                        f"Materiały, które masz, nie pasują (potrzeba: {', '.join(req_tags)}).")

    return {
        "valid": True,
        "reason": "",
        "fallback_message": "",
        "recipe_key": recipe_key,
        "category": rec.get("category", "tool"),
        "category_label_pl": rec.get("name_pl", rec.get("category", "")),
        "stat": rec.get("stat", "INT"),
        "dc":   int(rec.get("dc", 10)),
        "required_materials": dict(needed),
        "required_tools": list(rec.get("tools", [])),
        "time_cost": int(rec.get("time_minutes", 15)),
        "risks":   list(rec.get("failure_risks", [])),
        "rewards": list(rec.get("rewards", [])),
        "result_item": rec.get("result", {}).get("item_key"),
    }


# ── Improvised craft attempt ─────────────────────────────────────────────────

def try_improvise(character, category: str,
                  mentioned_materials: Optional[List[str]] = None,
                  mentioned_tools: Optional[List[str]] = None) -> Dict:
    """Validate an improvised craft of the given category.

    Strategy: the player must own at least ONE material matching at least
    ONE of the category's `required_tag_sets`. If multiple sets match, we
    pick the one that uses the smallest number of materials. The cost is
    one unit per tag in the chosen set; we'll consume by-tag at apply
    time (cheapest material first).
    """
    cats = improvised_categories()
    cat = cats.get(category)
    if cat is None:
        return _invalid("unknown_category",
                        f"Nie wiem, jak improwizować coś z kategorii „{category}”.")

    tag_sets = cat.get("required_tag_sets") or []
    matching_set = None
    for ts in tag_sets:
        if _matches_tag_set(character, ts):
            if matching_set is None or len(ts) < len(matching_set):
                matching_set = ts
    if matching_set is None:
        return _invalid("no_matching_materials",
                        "Twoje materiały nie składają się na to.")

    # Convert tag-set into a synthetic per-tag-1-unit cost
    needed_tags = list(matching_set)

    return {
        "valid": True,
        "reason": "",
        "fallback_message": "",
        "recipe_key": None,
        "category": category,
        "category_label_pl": _IMPROVISED_LABELS.get(category, category),
        "stat": cat.get("stat", "INT"),
        "dc":   int(cat.get("base_dc", 11)),
        "required_materials": {},           # by-tag consumption below
        "required_material_tags": needed_tags,
        "required_tools": list(mentioned_tools or []),
        "time_cost": 20,
        "risks":   list(cat.get("risks", ["unstable_item"])),
        "rewards": list(cat.get("rewards", [])),
        "result_item": cat.get("default_result"),
    }


# ── Material consumption + crafting outcome ─────────────────────────────────

def consume_for(plan: Dict, character) -> bool:
    """Spend materials per the plan. Returns True on success."""
    needed = plan.get("required_materials") or {}
    if needed and not materials.consume_materials(character, needed):
        return False
    # Improvised tag consumption: 1 unit per tag
    for tag in plan.get("required_material_tags", []) or []:
        materials.consume_by_tag(character, tag, 1)
    return True


def waste_for(plan: Dict, character):
    """On failure, partially waste materials (half of declared cost)."""
    needed = plan.get("required_materials") or {}
    half = {k: max(1, v // 2) for k, v in needed.items() if v > 0}
    if half:
        materials.consume_materials(character, half)
    for tag in (plan.get("required_material_tags") or [])[:1]:
        materials.consume_by_tag(character, tag, 1)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _invalid(reason: str, message: str) -> Dict:
    return {
        "valid": False, "reason": reason, "fallback_message": message,
        "recipe_key": None, "category": None, "category_label_pl": "",
        "stat": "INT", "dc": 0,
        "required_materials": {}, "required_tools": [],
        "time_cost": 0, "risks": [], "rewards": [], "result_item": None,
    }


_IMPROVISED_LABELS = {
    "trap":        "improwizowana pułapka",
    "weapon":      "improwizowana broń",
    "distraction": "improwizowana dystrakcja",
    "tool":        "improwizowane narzędzie",
    "disguise":    "improwizowane przebranie",
}


# ── Result-item factory ─────────────────────────────────────────────────────

_CATEGORY_ITEM_FALLBACKS = {
    "improvised_trap":       ("improwizowana pułapka",
                              "Coś, co ma zadziałać raz, jeśli ofiara tu wejdzie."),
    "improvised_weapon":     ("improwizowana broń",
                              "Krótki argument dla bliskiego zasięgu."),
    "improvised_distraction":("improwizowana dystrakcja",
                              "Hałas, kierunek, nagrana sponsorska podpowiedź."),
    "improvised_tool":       ("improwizowane narzędzie",
                              "Drobiazg, który podnosi szanse na jeden test."),
    "improvised_disguise":   ("improwizowane przebranie",
                              "Wystarczy, żeby kamera się zawahała."),
    "crafted_shiv":          ("shiv",
                              "Coś między nożem a skargą do BHP."),
    "tripwire_trap":         ("linka potykająca",
                              "Prosty dowód, że grawitacja ma poczucie humoru."),
    "shock_trap":            ("pułapka zwarciowa",
                              "Kable, bateria i przekonanie, że prąd lubi niespodzianki."),
    "smoke_bottle":          ("dymiąca butelka",
                              "Nie tyle bomba, co sugestia, że powietrze ma problem."),
    "armor_patch":           ("łatka pancerza",
                              "Warstwa śmieci między tobą a konsekwencją."),
    "bait_bundle":           ("pakunek przynęty",
                              "Organiczny argument za tym, żeby potwór poszedł gdzie indziej."),
    "improvised_bandage":    ("prowizoryczny opatrunek",
                              "Brudna, ale lepsza niż nic próba zatrzymania krwawienia."),
}


def make_crafted_entity(result_key: str, room_id: str = "",
                        quality: str = "normal",
                        damaged: bool = False, unstable: bool = False):
    """Build the Entity for a crafted-item result."""
    from ..engine.entity import Entity, T_ITEM
    name, desc = _CATEGORY_ITEM_FALLBACKS.get(
        result_key, (result_key.replace("_", " "), ""))
    tags = ["crafted"]
    affordances = ["inspect", "use", "loot"]
    if result_key.endswith("trap"):
        tags.append("trap"); affordances.append("deploy")
    if result_key.endswith("weapon") or result_key == "crafted_shiv":
        tags.extend(["weapon","sharp","melee"])
        affordances.append("attack")
    if result_key in ("smoke_bottle", "improvised_distraction"):
        tags.extend(["distraction","throwable"])
        affordances.extend(["throw_at"])
    if result_key in ("improvised_bandage",):
        tags.extend(["medical","consumable"])
    if result_key in ("armor_patch",):
        tags.extend(["armor"])
    if result_key in ("bait_bundle",):
        tags.extend(["bait","organic"])
    if result_key in ("improvised_tool",):
        tags.extend(["tool"])
    state = {"quality": quality, "damaged": damaged, "unstable": unstable}
    if damaged: state["damage_count"] = 1
    return Entity(
        key=result_key, entity_type=T_ITEM,
        name_key=f"item_{result_key}_n", fallback_name=name,
        desc_key=f"item_{result_key}_d", fallback_desc=desc,
        location_id=room_id or "inventory:player", portable=True,
        tags=tags, affordances=affordances, state=state,
    )
