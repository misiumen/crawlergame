"""P29.56 — Eksperymentalny crafting handler.

Player: `eksperymentuj X, Y, Z` (3-5 materiałów separated by " , " or " i ").

Mechanika:
1. Resolve materiały po nazwie/key. Walidacja: 3-5 materials, gracz je
   ma w `character.materials`.
2. Zbuduj tag_profile (z `MATERIAL_DEF.tags`).
3. Match w `EXPERIMENTAL_RECIPES` po tag_profile (filtr per tier =
   liczba materiałów + per biome).
4. Brak match'a → fumble: zmarnowane materiały + 1 audience.
5. Match → rzut d20 + INT mod + dyscyplinarne bonusy (klasa, rasa,
   achievement) vs DC = {3:10, 4:13, 5:16}.
6. Wynik:
    fumble (nat 1-2)        → hazard z `fumble_hazard`
    fail (total<DC)         → materiały zmarnowane, mały feedback
    success (>=DC)          → item z `base_rarity` + recipe learned
    big_success (>=DC+5)    → rarity +1 (cap epic)
    crit (nat 20)           → rarity +2 (cap epic) + UNIQUE afix
7. Crit + 5 mats + dwa legendary-tagi → LEGENDARY unique (cap raised).
"""
from __future__ import annotations
from typing import Dict, List, Optional
import random as _r


_FUMBLE_RANGE = (1, 2)
_DC_BY_TIER = {3: 10, 4: 13, 5: 16}


# ── Discipline → klasy / rasy / achievementy które dają +1 do rzutu ──
#
# Wartości dobrane ostrożnie — jeśli klasy/rasy nie ma w grze, klucz
# po prostu nigdy nie matchuje. Każda kategoria może dodać max +1 do
# rzutu (sumarycznie max +3 z dyscypliny).
_DISCIPLINE_BONUSES: Dict[str, Dict[str, list]] = {
    "chemistry":   {"class": ["scientist", "medic", "paramedic", "cook"],
                    "race":  ["glassblood"],
                    "achievement": ["medyk_polowy", "archiwista"]},
    "electronics": {"class": ["mechanic", "streamer", "haker"],
                    "race":  ["chimera", "ferromanta"],
                    "achievement": ["inzynier_niedoli"]},
    "mechanics":   {"class": ["mechanic", "soldier"],
                    "race":  ["ferromanta"],
                    "achievement": ["inzynier_niedoli", "saper"]},
    "bio":         {"class": ["medic", "paramedic", "nurse", "opiekun_zwierzaka"],
                    "race":  ["fungal_host", "half_dead"],
                    "achievement": ["kazdy_ma_imie", "medyk_polowy"]},
    "alchemy":     {"class": ["scientist", "student"],
                    "race":  ["void", "fungal_host"],
                    "achievement": ["archiwista"]},
    "culinary":    {"class": ["cook"],
                    "race":  [],
                    "achievement": []},
    "tinker":      {"class": ["mechanic", "janitor", "courier"],
                    "race":  [],
                    "achievement": ["saper", "inzynier_niedoli"]},
}


def _discipline_bonus(ch, discipline: str) -> int:
    """Sum class / race / achievement bonuses for a given discipline.
    Max +3 (one per category)."""
    spec = _DISCIPLINE_BONUSES.get(discipline) or {}
    bonus = 0
    cls = (getattr(ch, "class_key", "") or "").lower()
    bg = (getattr(ch, "background", "") or "").lower()
    if cls in spec.get("class", []) or bg in spec.get("class", []):
        bonus += 1
    sp = (getattr(ch, "species_key", "") or "").lower()
    if sp in spec.get("race", []):
        bonus += 1
    ach = set(getattr(ch, "unlocked_achievements", None) or [])
    if any(a in ach for a in spec.get("achievement", [])):
        bonus += 1
    return bonus


# ── Material resolver ─────────────────────────────────────────────────


def _resolve_material_name(name_lower: str, ch) -> Optional[str]:
    """Match a Polish material name (lowered+folded) to a MATERIALS key
    THE PLAYER ACTUALLY OWNS. Returns key or None."""
    from ...content.materials import MATERIALS
    from ..affordances import fold as _fold
    needle = _fold(name_lower).strip()
    pool = getattr(ch, "materials", None) or {}
    # Exact name match first
    for key, qty in pool.items():
        if qty <= 0:
            continue
        md = MATERIALS.get(key)
        if md is None:
            continue
        if _fold(md.fallback_name_pl) == needle or _fold(key) == needle:
            return key
    # Substring match second
    for key, qty in pool.items():
        if qty <= 0:
            continue
        md = MATERIALS.get(key)
        if md is None:
            continue
        if needle in _fold(md.fallback_name_pl) or needle in _fold(key):
            return key
    return None


def _split_materials(raw_targets: list) -> List[str]:
    """The parser passes targets[] either as one combined string with
    separators (",", " i ", " oraz ", " z ") OR as a pre-split list.
    Normalize to a list of trimmed material-name fragments."""
    if not raw_targets:
        return []
    combined = " , ".join(t for t in raw_targets if t)
    # Replace polish separators with comma
    for sep in (" oraz ", " i ", " z "):
        combined = combined.replace(sep, ",")
    parts = [p.strip() for p in combined.split(",")]
    return [p for p in parts if p]


# ── Main handler ─────────────────────────────────────────────────────


def attempt_experiment(game, intent) -> None:
    """Player intent="experiment", targets=[material names].

    Emits log lines via game.log(). Spends materials. Mints item on
    success."""
    from ..time_system import advance as ts_advance
    from ...content.data import experimental_recipes as _exp
    from ...content.materials import MATERIALS, consume_materials
    from ...content.items import make_item
    from ...content.crafting import teach_recipe, knows_recipe
    from ...ui.lang import t
    from ...config import LOG_NORMAL, LOG_SYSTEM, LOG_WARN, LOG_DANGER, LOG_SUCCESS

    ch = game.world.character
    if ch is None:
        return

    fragments = _split_materials(getattr(intent, "targets", []) or [])
    if len(fragments) < 3:
        game.log("Eksperyment wymaga 3-5 składników. Składnia: "
                 "eksperymentuj X, Y, Z (lub: zmieszaj X i Y i Z).",
                 LOG_WARN)
        return
    if len(fragments) > 5:
        game.log("Maksymalnie 5 składników na próbę. Reszta by się "
                 "rozsadziła.", LOG_WARN)
        return

    # Resolve each fragment to a material key. Track per-key counts so
    # gracz może użyć tego samego materiału kilka razy (jeśli ma >=N).
    resolved: List[str] = []
    counts: Dict[str, int] = {}
    for frag in fragments:
        key = _resolve_material_name(frag.lower(), ch)
        if key is None:
            game.log(f"Nie masz „{frag}” w materiałach.", LOG_WARN)
            return
        resolved.append(key)
        counts[key] = counts.get(key, 0) + 1

    # Check stock
    for k, n in counts.items():
        owned = int((ch.materials or {}).get(k, 0))
        if owned < n:
            md = MATERIALS.get(k)
            name = md.fallback_name_pl if md else k
            game.log(f"Potrzebujesz {n}× „{name}”, masz {owned}.",
                     LOG_WARN)
            return

    # Build tag profile
    profile = _exp.build_tag_profile_from_materials(resolved)

    # Biome context
    floor = game.world.current_floor
    current_biome = (getattr(floor, "biome_key", "") or "") if floor else ""
    unlocked_biomes = set()
    try:
        from .. import run_history as _rh
        unlocked_biomes = set(_rh.meta().get("unlocks", []) or [])
    except Exception:
        pass

    # Match
    tier = len(resolved)
    candidates = _exp.match_recipe_by_tag_profile(
        profile, tier=tier,
        current_biome=current_biome,
        unlocked_biomes=unlocked_biomes,
    )
    # Prefer recipes the player does NOT already know — eksperyment to
    # ścieżka odkrywania, nie powtarzania.
    unknown = [r for r in candidates if not knows_recipe(ch, r["key"])]
    chosen = (unknown[0] if unknown else
              (candidates[0] if candidates else None))

    # Roll d20
    raw = _r.randint(1, 20)
    int_mod = ch.stat_mod("INT") if hasattr(ch, "stat_mod") else 0
    discipline = (chosen or {}).get("discipline", "tinker")
    disc_bonus = _discipline_bonus(ch, discipline)
    # Rare-material bonus: każdy material rarity ≥ uncommon → +1, cap +3
    rare_bonus = 0
    for k in resolved:
        md = MATERIALS.get(k)
        if md and md.rarity in ("uncommon", "rare", "epic", "weird"):
            rare_bonus += 1
    rare_bonus = min(3, rare_bonus)
    total = raw + int_mod + disc_bonus + rare_bonus
    dc = _DC_BY_TIER.get(tier, 12)

    is_fumble = raw <= _FUMBLE_RANGE[1]
    is_crit = (raw == 20)
    is_success = (not is_fumble) and total >= dc
    is_big_success = is_success and total >= dc + 5
    rarity_up = 0
    if is_crit:
        rarity_up = 2
    elif is_big_success:
        rarity_up = 1

    # Consume materials regardless of outcome (eksperyment kosztuje).
    consume_materials(ch, counts)

    # Time cost
    try:
        ts_advance(game.world, 30 + 10 * tier)
    except Exception:
        pass

    # Log header line
    mat_names = ", ".join(
        (MATERIALS.get(k).fallback_name_pl if MATERIALS.get(k) else k)
        for k in resolved)
    game.log(f"Eksperyment: {mat_names}.", LOG_SYSTEM)
    game.log(f"  d20({raw}) + INT({int_mod:+d}) + "
             f"dyscyplina({disc_bonus:+d}) + składniki({rare_bonus:+d}) "
             f"= {total} vs DC {dc}", LOG_SYSTEM)

    if is_fumble:
        _apply_fumble(game, chosen, profile)
        return

    if chosen is None:
        # No recipe match — flavor + small audience
        game.log("Materiały reagują, ale niczego sensownego nie powstaje. "
                 "Sponsor docenia próbę.", LOG_NORMAL)
        try:
            from .. import audience as _aud
            _aud.change_audience(game.world, 1, source="experiment_blind")
        except Exception:
            pass
        return

    if not is_success:
        # Failed match — partial knowledge hint
        game.log(f"Coś tu się nie spina. Notujesz: „{chosen['name_pl']}” "
                 f"wymaga lepszej ręki.", LOG_NORMAL)
        try:
            from .. import audience as _aud
            _aud.change_audience(game.world, 1, source="experiment_fail")
        except Exception:
            pass
        return

    # Success — mint item
    _mint_experimental_item(game, chosen, rarity_up, is_crit, tier, resolved)


def _apply_fumble(game, chosen, profile: Dict[str, int]) -> None:
    """Translate the recipe's `fumble_hazard` into actual damage / status."""
    from ...config import LOG_DANGER
    ch = game.world.character
    fumble = (chosen or {}).get("fumble_hazard", "waste_materials")

    if fumble == "chemical_splash":
        try:
            from .. import combat as _cmb
            _cmb.add_status(ch, _cmb.STATUS_CORRODED, 3)
        except Exception:
            pass
        ch.hp = max(1, ch.hp - 3)
        game.log("Kwas pryska ci na palce. −3 HP, skorodowany.",
                 LOG_DANGER)

    elif fumble == "ignite_self":
        try:
            from .. import combat as _cmb
            _cmb.add_status(ch, _cmb.STATUS_BURNING, 3)
        except Exception:
            pass
        ch.hp = max(1, ch.hp - 4)
        game.log("Mieszanka zapala się w dłoniach. −4 HP, płoniesz.",
                 LOG_DANGER)

    elif fumble == "shock_self":
        try:
            from .. import combat as _cmb
            _cmb.add_status(ch, _cmb.STATUS_SHOCKED, 2)
        except Exception:
            pass
        ch.hp = max(1, ch.hp - 3)
        game.log("Iskra przeskakuje na ciebie. −3 HP, porażony.",
                 LOG_DANGER)

    elif fumble == "explode_self":
        ch.hp = max(1, ch.hp - 8)
        game.log("Mieszanka wybucha ci w dłoni. −8 HP. Następnym razem "
                 "dalej od twarzy.", LOG_DANGER)

    elif fumble == "trap_misfire":
        game.log("Pułapka odpala w trakcie składania. Materiały po sufice.",
                 LOG_DANGER)
        ch.hp = max(1, ch.hp - 2)

    elif fumble == "reality_glitch":
        try:
            from .. import combat as _cmb
            _cmb.add_status(ch, _cmb.STATUS_AFRAID, 2)
        except Exception:
            pass
        game.log("Coś się przekręca w pokoju. Materiały znikają, "
                 "zostawiają niesmak. Spanikowany.", LOG_DANGER)

    elif fumble == "food_poisoning":
        try:
            from .. import combat as _cmb
            _cmb.add_status(ch, _cmb.STATUS_POISONED, 4)
        except Exception:
            pass
        game.log("Próbowałeś. Nie powinieneś był. Zatruty.", LOG_DANGER)

    elif fumble == "contamination":
        try:
            from .. import combat as _cmb
            _cmb.add_status(ch, _cmb.STATUS_BLEEDING, 2)
        except Exception:
            pass
        game.log("Skażony preparat. Niewinna ranka, paskudna infekcja.",
                 LOG_DANGER)

    else:  # waste_materials / flawed_item
        game.log("Materiały rozsypują się i giną. Następnym razem powoli.",
                 LOG_DANGER)


# ── Mint helper ──────────────────────────────────────────────────────


_RARITY_LADDER = ["common", "uncommon", "rare", "epic", "legendary"]


def _bump_rarity(base: str, by: int) -> str:
    try:
        idx = _RARITY_LADDER.index(base)
    except ValueError:
        idx = 0
    return _RARITY_LADDER[min(idx + max(0, by), len(_RARITY_LADDER) - 1)]


def _mint_experimental_item(game, recipe: dict, rarity_up: int,
                            is_crit: bool, tier: int,
                            resolved: List[str]) -> None:
    """Create the actual Entity in player inventory + learn recipe."""
    from ...config import LOG_SUCCESS, LOG_SYSTEM
    from ...content.materials import MATERIALS
    from ...content.data import experimental_recipes as _exp
    from ...content.crafting import teach_recipe
    from ..entity import Entity, T_ITEM

    ch = game.world.character
    base_rarity = recipe.get("base_rarity", "common")
    final_rarity = _bump_rarity(base_rarity, rarity_up)

    # Special: crit + 5 tier + ≥2 rare materials → cap pushed to legendary
    rare_count = sum(1 for k in resolved
                     if (md := MATERIALS.get(k)) and
                     md.rarity in ("rare", "epic", "weird"))
    if is_crit and tier == 5 and rare_count >= 2:
        final_rarity = "legendary"

    # Build the entity from the recipe result
    result = recipe.get("result", {})
    base_name = recipe.get("name_pl", recipe["key"])
    base_desc = recipe.get("desc_pl", "")
    tags = list(result.get("tags") or [])
    affordances = ["inspect", "use", "loot"]

    # Result-effect routing
    effect = result.get("effect")
    state = {"quality": "normal", "rarity": final_rarity,
             "recipe_key": recipe["key"]}

    if effect == "coating":
        # Enhancement item — applied via apply_enhancement handler.
        tags = list(set(tags + ["enhancement", "consumable", "apply_to_item"]))
        state["enhancement_key"] = recipe["key"]
        # Register a runtime spec the handler can read.
        state["enhancement_spec"] = {
            "applies_to_tags": result.get("applies_to_tags", ["weapon"]),
            "effect": "coating",
            "coating": dict(result.get("coating", {})),
        }

    elif effect == "permanent":
        tags = list(set(tags + ["enhancement", "consumable", "apply_to_item"]))
        state["enhancement_key"] = recipe["key"]
        state["enhancement_spec"] = {
            "applies_to_tags": result.get("applies_to_tags", ["weapon"]),
            "effect": "permanent",
            "permanent": dict(result.get("permanent", {})),
        }

    elif effect == "weapon":
        tags = list(set(tags + ["weapon", "crafted"]))
        affordances.append("attack")
        state["damage_dice"] = result.get("damage_dice", "1d4")
        state["damage_type"] = result.get("damage_type", "physical")

    elif effect == "trap":
        tags = list(set(tags + ["trap", "deployable", "crafted"]))
        if "deploy" not in affordances:
            affordances.append("deploy")
        state["trap_payload"] = dict(result.get("payload", {}))

    elif effect == "throwable":
        tags = list(set(tags + ["throwable", "consumable", "crafted"]))
        if "throw_at" not in affordances:
            affordances.append("throw_at")
        state["throwable_payload"] = dict(result.get("payload", {}))

    elif effect == "food":
        tags = list(set(tags + ["food", "consumable", "crafted"]))
        if "consume" not in affordances:
            affordances.append("consume")
        state["heal_amount"] = int(result.get("heal", 0))
        state["buff_status"] = result.get("buff_status") or ""

    elif effect == "medical":
        tags = list(set(tags + ["medical", "consumable", "crafted"]))
        if "consume" not in affordances:
            affordances.append("consume")
        state["heal_amount"] = int(result.get("heal", 0))
        state["cures_statuses"] = list(result.get("cures_statuses") or [])

    elif effect == "tool":
        tags = list(set(tags + ["tool", "crafted"]))
        state["tool_kind"] = result.get("tool_kind", "generic")

    # Crit bonus: unique affix
    unique_label = ""
    if is_crit:
        import random as _rng
        affix_pl, perk_key, perk_val = _exp.random_unique_affix(_rng.Random())
        state["unique_affix"] = {"label_pl": affix_pl,
                                 "perk_key": perk_key,
                                 "perk_val": perk_val}
        unique_label = f" {affix_pl}"
        tags = list(set(tags + ["unique"]))

    fb_name = base_name + unique_label
    ent = Entity(
        key=recipe["key"], entity_type=T_ITEM,
        name_key=f"item_{recipe['key']}_n", fallback_name=fb_name,
        desc_key=f"item_{recipe['key']}_d", fallback_desc=base_desc,
        location_id="inventory:player",
        portable=True,
        tags=tags, affordances=affordances,
        state=state,
    )
    game.world.register(ent)
    if ch.inventory_ids is None:
        ch.inventory_ids = []
    ch.inventory_ids.append(ent.entity_id)

    # Learn recipe permanently
    teach_recipe(ch, recipe["key"])

    # Log success
    rar_pl = {
        "common": "pospolity", "uncommon": "niepospolity",
        "rare": "rzadki", "epic": "epicki", "legendary": "legendarny",
    }.get(final_rarity, final_rarity)
    if is_crit:
        line = (f"KRYTYCZNY SUKCES! Tworzysz „{fb_name}” "
                f"({rar_pl}). Nowy przepis odkryty.")
        tone = LOG_SUCCESS
    elif rarity_up > 0:
        line = (f"Świetny rzut. Powstaje „{fb_name}” ({rar_pl}). "
                f"Lepszy niż sama receptura.")
        tone = LOG_SUCCESS
    else:
        line = (f"Mieszanka stabilizuje się: „{fb_name}” ({rar_pl}). "
                f"Notujesz przepis.")
        tone = LOG_SUCCESS
    game.log(line, tone)

    # Audience credit for the spectacle
    try:
        from .. import audience as _aud
        gain = int(recipe.get("audience_create", 2))
        if is_crit:
            gain += 3
        elif rarity_up > 0:
            gain += 1
        _aud.change_audience(game.world, gain,
                             source=f"experiment:{recipe['key']}")
    except Exception:
        pass
