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

    # P29.14 — sponsor-branded recipes require an attention-unlock flag.
    # Set by engine/sponsors.py:_check_gift_thresholds when attention
    # crosses +5 (mid-tier, between "seen you" and "first gift").
    needs_sponsor = rec.get("requires_sponsor_unlock")
    if needs_sponsor:
        flags = getattr(character, "flags", None) or {}
        if not flags.get(f"sponsor_recipe_unlocked_{needs_sponsor}"):
            return _invalid("sponsor_locked",
                            f"Ten przepis wymaga uznania sponsora "
                            f"({needs_sponsor}).")

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

# P29.51 — polskie etykiety tagów materiałów dla craft-help'u.
# Wcześniej UI wyświetlał raw klucze (sharp/wire/heavy/...). Każdy
# nowy tag wymaga dopisania tutaj — alternatywnie fallback zwraca
# raw klucz, więc system nie crashuje przy nieznanym wpisie.
_MATERIAL_TAG_PL = {
    # struktura
    "wire":       "drut",
    "binding":    "wiązanie",
    "sharp":      "ostre",
    "heavy":      "ciężkie",
    "handle":     "rękojeść",
    "metal":      "metal",
    "small":      "drobne",
    "precise":    "precyzyjne",
    "cloth":      "tkanina",
    # elektrycznie / zapalające / dymne
    "electrical": "elektryczne",
    "noise":      "hałas",
    "thrown":     "do rzucania",
    "light":      "światło",
    "smell":      "zapach",
    # przebrania / sponsor
    "badge":      "odznaka",
    "sponsor":    "sponsorskie",
    "uniform":    "mundur",
}


def tag_pl(tag_key: str) -> str:
    """Polski etykieta tagu materiału. Fallback do oryginalnego klucza
    (nie crashuje na nieznanych, ale staje się widoczny w UI jako sygnał
    że trzeba dopisać do _MATERIAL_TAG_PL)."""
    return _MATERIAL_TAG_PL.get(tag_key, tag_key)


def category_pl(category_key: str) -> str:
    """Polski label dla improvised category."""
    return _IMPROVISED_LABELS.get(category_key, category_key)


# ── Result-item factory ─────────────────────────────────────────────────────

# ── P29.14 — Quality-tier mapping ─────────────────────────────────────────
#
# Maps a roll outcome level (from utils_compat / dice resolver) to the
# `quality` state field on the crafted entity:
#   critical_success → masterwork  (mechanical bonuses, "of+" name)
#   success          → good        (slight bonuses)
#   partial_success  → flawed      (damaged tick)
#   failure          → no item
#   critical_failure → no item + waste
# Combat / equipment code reads ent.state["quality"] and applies the
# matching bonuses (see _quality_bonus_for_weapon below).

def quality_for_level(level: str) -> str:
    return {
        "critical_success": "masterwork",
        "success":          "good",
        "partial_success":  "flawed",
    }.get(level, "normal")


def quality_bonus_for_weapon(quality: str) -> Dict:
    """Return additive (attack_bonus, damage_bonus) for the given quality
    tier when the player wields the item. Tags also nudge — see
    combat damage path in engine/game.py."""
    return {
        "masterwork": {"attack_bonus": 1, "damage_bonus": 1},
        "good":       {"attack_bonus": 0, "damage_bonus": 1},
        "normal":     {"attack_bonus": 0, "damage_bonus": 0},
        "flawed":     {"attack_bonus": -1, "damage_bonus": 0},
    }.get(quality, {"attack_bonus": 0, "damage_bonus": 0})


def quality_label_pl(quality: str) -> str:
    return {
        "masterwork": "mistrzowska",
        "good":       "solidna",
        "normal":     "",
        "flawed":     "wadliwa",
    }.get(quality, "")


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
    # P29.14 — Polish display names for P23 weapon entities that the
    # fallback table missed. Without these they render in English.
    "improvised_knife":      ("improwizowany nóż",
                              "Krótki kawałek ostrego metalu owinięty taśmą."),
    "improvised_spear":      ("improwizowana włócznia",
                              "Długi kij z ostrym końcem. Obie ręce."),
    "improvised_club":       ("improwizowana pała",
                              "Coś ciężkiego z uchwytem. Logika prosta jak dno wiadra."),
    "improvised_garrote":    ("garota z drutu",
                              "Cienki drut z rączkami. Cicha sprawa."),
    "improvised_taser":      ("improwizowany paralizator",
                              "Bateria, dwa druty, dużo taśmy izolacyjnej."),
    "improvised_chembottle": ("fiolka żrąca",
                              "Cieczy w fiolce nie chcesz dotykać. Trzymaj z dystansu — i rzuć."),
    # Prompt 21 — elemental trap variants. They share `trap` tag so the
    # crafted_entity wiring picks them up; the actual damage_type is
    # read from the item.tags by game._attempt_deploy at deploy time.
    "fire_trap":             ("pułapka zapalająca",
                              "Fosfor + ciasna butelka. Coś tu się zapali, i to nie ty."),
    "acid_flask":            ("fiolka żrąca",
                              "Wykorzystany odpad chemiczny w pękniętej fiolce. Nie wąchać."),
    "poison_dart":           ("zatruta strzałka",
                              "Cienki kolec na sprężynie. Powolne, ale precyzyjne."),
    "frost_charge":          ("ładunek mrożący",
                              "Sprężona puszka z chłodziwem i bardzo wąską klapką."),
    # P29.14 — Enhancements (apply-to-item).
    "weapon_poison_coat":    ("olej zatrucia",
                              "Lepkie smary z dodatkami. Mazasz na ostrze — trucizna idzie pierwsza."),
    "weapon_grip_tape":      ("owijka uchwytu",
                              "Skórzano-taśmowy chwyt. Pewniejsza ręka, lepsze trafienia."),
    "weapon_balance_weight": ("wyważenie",
                              "Kawałek metalu w odpowiednim miejscu uderza mocniej."),
    "weapon_silencer":       ("tłumik dźwięku",
                              "Gruba osłona z gumy i materiału. Cios robi mniej hałasu."),
    "armor_padding":         ("wyściółka pancerza",
                              "Warstwy między tobą a ciosem. Cięższe, ale więcej osłony."),
    "armor_acid_lining":     ("wyłożenie kwasoodporne",
                              "Gumowa membrana na zewnątrz pancerza. Kwas spływa zamiast wgryzać."),
    # P29.14 — Cooking.
    "cooked_meat":           ("upieczone mięso",
                              "Mięso nad ogniem przestało być sapaniem. Stało się jedzeniem."),
    "morale_brew":           ("wywar morale",
                              "Smak nieokreślony. Działanie pewne — przez chwilę mówisz pewniej."),
    "caffeine_pill":         ("pigułka kofeiny",
                              "Pasta z dziwnych proszków. Działa raz mocno, potem płacisz."),
    # P29.14 — Sponsor-branded.
    "nova_chem_stim_pack":   ("stimpak NovaChem",
                              "Profesjonalny opatrunek. NovaChem płaci za każde użycie."),
    "kanal_7_microphone":    ("mikrofon Kanału 7",
                              "Kierunkowy mikrofon. Idealne ujęcia, lepsze ratingi."),
    "czarny_rynek_lockpick_kit": ("wytrychy Czarnego Rynku",
                                  "Drobne narzędzia w skórzanej rolce. Używane dziś."),
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
    # Prompt 21 — elemental trap subtypes inherit `trap` + add their
    # element tag so game._attempt_deploy picks the right damage_type.
    if result_key == "fire_trap":
        tags.extend(["trap","fire","incendiary","flammable"])
        if "deploy" not in affordances: affordances.append("deploy")
    if result_key == "acid_flask":
        tags.extend(["trap","acid","throwable"])
        if "deploy" not in affordances: affordances.append("deploy")
        affordances.append("throw_at")
    if result_key == "poison_dart":
        tags.extend(["trap","poison"])
        if "deploy" not in affordances: affordances.append("deploy")
    if result_key == "frost_charge":
        tags.extend(["trap","cold"])
        if "deploy" not in affordances: affordances.append("deploy")
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

    # ── P29.14 — Enhancement consumables ────────────────────────────────
    # Tagged so engine/game.py:_attempt_apply_enhancement picks them up.
    # Carry the recipe key in `enhancement_key` for the handler to look
    # up the effect spec at apply time.
    _ENHANCEMENT_KEYS = ("weapon_poison_coat", "weapon_grip_tape",
                         "weapon_balance_weight", "weapon_silencer",
                         "armor_padding", "armor_acid_lining")
    if result_key in _ENHANCEMENT_KEYS:
        tags.extend(["enhancement", "consumable", "apply_to_item"])
        if "use" not in affordances:
            affordances.append("use")

    # ── P29.14 — Cooked food (consumable, heals/buffs) ───────────────────
    _FOOD_KEYS = ("cooked_meat", "morale_brew", "caffeine_pill")
    if result_key in _FOOD_KEYS:
        tags.extend(["food", "consumable"])
        if "consume" not in affordances:
            affordances.append("consume")

    # ── P29.14 — Sponsor-branded gear ────────────────────────────────────
    if result_key == "nova_chem_stim_pack":
        tags.extend(["medical", "consumable", "sponsor_nova_chem"])
        if "consume" not in affordances:
            affordances.append("consume")
    if result_key == "kanal_7_microphone":
        tags.extend(["tool", "sponsor_kanal_7", "broadcast"])
        if "use" not in affordances:
            affordances.append("use")
    if result_key == "czarny_rynek_lockpick_kit":
        tags.extend(["tool", "lockpick", "sponsor_czarny_rynek"])
        if "use" not in affordances:
            affordances.append("use")

    state = {"quality": quality, "damaged": damaged, "unstable": unstable}
    if damaged: state["damage_count"] = 1
    # P29.14 — store the recipe key so enhancement application can
    # look up the effect spec without re-deriving from tags.
    if result_key in _ENHANCEMENT_KEYS:
        state["enhancement_key"] = result_key

    # Prompt 23 — weapon templates carry damage_dice + damage_type so
    # the combat code reads them when wielded. Tags here also gate
    # two-handed / offhand-only rules in the wield handler.
    WEAPON_STATS = {
        "crafted_shiv":          ("1d4+1", "physical", ["weapon","sharp","melee","one_handed"]),
        "improvised_weapon":     ("1d6",   "physical", ["weapon","melee","one_handed"]),
        "improvised_knife":      ("1d6",   "physical", ["weapon","sharp","melee","one_handed"]),
        "improvised_spear":      ("1d8",   "physical", ["weapon","sharp","melee","two_handed","reach"]),
        "improvised_club":       ("1d6+1", "physical", ["weapon","heavy","melee","one_handed"]),
        "improvised_garrote":    ("1d4",   "physical", ["weapon","silent","melee","one_handed"]),
        "improvised_taser":      ("1d4",   "electric", ["weapon","electrical","melee","one_handed"]),
        "improvised_chembottle": ("1d6",   "acid",     ["weapon","chemical","throwable","one_handed"]),
    }
    damage_dice = "1d4"
    damage_type = "physical"
    if result_key in WEAPON_STATS:
        damage_dice, damage_type, extra_tags = WEAPON_STATS[result_key]
        for tg in extra_tags:
            if tg not in tags:
                tags.append(tg)

    ent = Entity(
        key=result_key, entity_type=T_ITEM,
        name_key=f"item_{result_key}_n", fallback_name=name,
        desc_key=f"item_{result_key}_d", fallback_desc=desc,
        location_id=room_id or "inventory:player", portable=True,
        tags=tags, affordances=affordances, state=state,
    )
    # Set weapon-specific combat fields (defaults left untouched for
    # non-weapon results).
    if result_key in WEAPON_STATS:
        ent.damage_dice = damage_dice
        ent.damage_type = damage_type
    return ent
