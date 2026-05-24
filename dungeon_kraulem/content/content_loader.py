"""Content loader — single safe layer over revamp/data/*.

Every function in this module returns either a usable value or None. If a
template module is missing, malformed, or contains no matching entries,
callers can safely default. Engine code should never import the template
modules directly — go through here.

This module deliberately does NOT change game state. It only reads.
"""
import random
from typing import Dict, List, Optional, Tuple, Any


# ── Encounter templates ──────────────────────────────────────────────────────

def all_encounter_templates() -> Dict[str, Dict]:
    try:
        from .data.encounter_templates import ENCOUNTER_TEMPLATES
        return ENCOUNTER_TEMPLATES
    except Exception:
        return {}


def random_encounter_template(floor_num: int = 1,
                              required_tags: Optional[List[str]] = None,
                              exclude_keys: Optional[List[str]] = None
                              ) -> Optional[Tuple[str, Dict]]:
    """Pick a weighted random encounter template eligible for this floor."""
    table = all_encounter_templates()
    if not table:
        return None
    pool = []
    for key, tmpl in table.items():
        if exclude_keys and key in exclude_keys:
            continue
        if tmpl.get("floor_min", 1) > floor_num:
            continue
        if required_tags:
            tags = set(tmpl.get("tags", []))
            if not all(t in tags for t in required_tags):
                continue
        weight = max(1, int(tmpl.get("weight", 1)))
        pool.append((key, tmpl, weight))
    if not pool:
        return None
    keys = [(k, t) for k, t, _ in pool]
    weights = [w for _, _, w in pool]
    return random.choices(keys, weights=weights, k=1)[0]


def encounter_intro_line(tmpl: Dict) -> Optional[str]:
    intros = tmpl.get("intro") or []
    return random.choice(intros) if intros else None


# ── NPC archetypes ───────────────────────────────────────────────────────────

def all_crawler_archetypes() -> Dict[str, Dict]:
    try:
        from .data.npc_templates import CRAWLER_ARCHETYPES
        return CRAWLER_ARCHETYPES
    except Exception:
        return {}


def random_crawler_archetype(exclude_keys: Optional[List[str]] = None
                             ) -> Optional[Tuple[str, Dict]]:
    table = all_crawler_archetypes()
    if not table:
        return None
    candidates = [(k, v) for k, v in table.items()
                  if not (exclude_keys and k in exclude_keys)]
    if not candidates:
        return None
    return random.choice(candidates)


def crawler_archetype_data(key: str) -> Optional[Dict]:
    return all_crawler_archetypes().get(key)


def crawler_name_from_archetype(archetype: Dict) -> Optional[str]:
    pool = archetype.get("fallback_name_pool") or []
    return random.choice(pool) if pool else None


def crawler_opener(archetype: Dict) -> Optional[str]:
    lines = archetype.get("dialogue") or []
    return random.choice(lines) if lines else None


def all_safehouse_npcs() -> Dict[str, Dict]:
    try:
        from .data.npc_templates import SAFEHOUSE_NPCS
        return SAFEHOUSE_NPCS
    except Exception:
        return {}


# ── Rumors ───────────────────────────────────────────────────────────────────

def all_rumor_categories() -> Dict[str, List[Dict]]:
    try:
        from .data.rumor_templates import RUMOR_TEMPLATES
        return RUMOR_TEMPLATES
    except Exception:
        return {}


def random_rumor(category: Optional[str] = None,
                 floor_num: int = 1) -> Optional[Dict]:
    table = all_rumor_categories()
    if not table:
        return None
    if category:
        bucket = table.get(category) or []
    else:
        bucket = [r for vs in table.values() for r in vs]
    if not bucket:
        return None
    return random.choice(bucket)


# ── Safehouse templates ──────────────────────────────────────────────────────

def all_safehouse_templates() -> Dict[str, Dict]:
    try:
        from .data.safehouse_templates import SAFEHOUSE_TEMPLATES
        return SAFEHOUSE_TEMPLATES
    except Exception:
        return {}


def safehouse_template(subtype: str) -> Optional[Dict]:
    return all_safehouse_templates().get(subtype)


def safehouse_name(subtype: str) -> Optional[str]:
    tmpl = safehouse_template(subtype)
    if not tmpl:
        return None
    pool = tmpl.get("name_pool") or []
    return random.choice(pool) if pool else None


def safehouse_entry_description(subtype: str) -> Optional[str]:
    tmpl = safehouse_template(subtype)
    if not tmpl:
        return None
    pool = tmpl.get("entry_descriptions") or []
    return random.choice(pool) if pool else None


def safehouse_ambient_line(subtype: str) -> Optional[str]:
    tmpl = safehouse_template(subtype)
    if not tmpl:
        return None
    pool = tmpl.get("ambient_lines") or []
    return random.choice(pool) if pool else None


# ── Items ────────────────────────────────────────────────────────────────────

def all_item_templates() -> Dict[str, Dict]:
    try:
        from .data.item_templates import ITEM_TEMPLATES
        return ITEM_TEMPLATES
    except Exception:
        return {}


def item_template(key: str) -> Optional[Dict]:
    return all_item_templates().get(key)


# ── Failure / partial-success narration (context-driven, Prompt 03) ─────────

def pick_fail_outcome(level: str, context: Optional[Dict] = None) -> Optional[Dict]:
    """Context-aware picker. Returns a full template dict
    (with text + effects) or None. `level` ∈ partial / failure / critical_failure.
    """
    try:
        from .data.failure_templates import pick_outcome
    except Exception:
        return None
    return pick_outcome(level, context or {})


def pick_fail_line(level: str, context: Optional[Dict] = None) -> Optional[str]:
    """Backward-compat helper: returns only the text. Effects are dropped."""
    t = pick_fail_outcome(level, context)
    return t.get("text") if t else None


# Aliases for older call sites
def random_partial_success_line(category: Optional[str] = None) -> Optional[str]:
    return pick_fail_line("partial", {"intent_category": category} if category else None)


def random_failure_line(category: Optional[str] = None) -> Optional[str]:
    return pick_fail_line("failure", {"intent_category": category} if category else None)


def random_critical_failure_line(category: Optional[str] = None) -> Optional[str]:
    return pick_fail_line("critical_failure", {"intent_category": category} if category else None)


# ── Floor objectives ─────────────────────────────────────────────────────────

def all_floor_objectives() -> Dict[str, Dict]:
    try:
        from .data.floor_objective_templates import FLOOR_OBJECTIVE_TEMPLATES
        return FLOOR_OBJECTIVE_TEMPLATES
    except Exception:
        return {}


def random_floor_objective() -> Optional[Tuple[str, Dict]]:
    table = all_floor_objectives()
    if not table:
        return None
    key = random.choice(list(table.keys()))
    return key, table[key]


# ── Room pool (procedural floor generator) ──────────────────────────────────

def all_room_templates() -> List[Dict]:
    try:
        from .data.room_pool import ROOM_POOL
        return list(ROOM_POOL)
    except Exception:
        return []


def room_templates_for_role(role: str) -> List[Dict]:
    return [t for t in all_room_templates() if t.get("role") == role]


def room_templates_with_tag(tag: str) -> List[Dict]:
    return [t for t in all_room_templates() if tag in t.get("tags", [])]


def random_room_template(role: Optional[str] = None,
                         required_tag: Optional[str] = None,
                         floor_num: int = 1,
                         exclude_template_ids: Optional[List[str]] = None
                         ) -> Optional[Dict]:
    """Weighted random pick from the room pool. Filters by role and tag."""
    pool = all_room_templates()
    if not pool:
        return None
    if role:
        pool = [t for t in pool if t.get("role") == role]
    if required_tag:
        pool = [t for t in pool if required_tag in t.get("tags", [])]
    pool = [t for t in pool if t.get("floor_min", 1) <= floor_num]
    if exclude_template_ids:
        pool = [t for t in pool if t.get("template_id") not in exclude_template_ids]
    if not pool:
        return None
    weights = [max(1, int(t.get("weight", 1))) for t in pool]
    return random.choices(pool, weights=weights, k=1)[0]


# ── Clues ────────────────────────────────────────────────────────────────────

def all_clue_templates() -> Dict[str, Dict]:
    try:
        from .data.clue_templates import CLUE_TEMPLATES
        return CLUE_TEMPLATES
    except Exception:
        return {}


def get_clue(key: str) -> Optional[Dict]:
    return all_clue_templates().get(key)


def clues_for_objective(objective_key: str) -> List[Tuple[str, Dict]]:
    """Pull the explicit `clue_chains` listed under a floor objective."""
    obj_table = all_floor_objectives().get(objective_key, {})
    chain_keys = obj_table.get("clue_chains", []) or []
    clues = all_clue_templates()
    return [(k, clues[k]) for k in chain_keys if k in clues]


def random_clue(source: Optional[str] = None) -> Optional[Tuple[str, Dict]]:
    table = all_clue_templates()
    if not table:
        return None
    pool = [(k, v) for k, v in table.items()
            if source is None or v.get("source") == source]
    if not pool:
        return None
    return random.choice(pool)


# ── Clue delivery with false-variant rolling (post-07b follow-up) ───────────

def roll_clue_delivery(clue: Dict, rng=None) -> Dict[str, Any]:
    """Decide how a clue lands on delivery.

    Reads `false_variant_chance` (0..1) and optional `false_variant` /
    `false_variant_pl` text. Returns a dict with:
        text           — Polish text to show (true or distorted)
        reliability    — float, lowered if false variant fired
        contaminated   — bool, True iff the false variant fired
        used_false     — bool (alias of contaminated)

    Falls back safely if `false_variant_chance` is 0 or no false_variant
    text is defined. The caller decides whether to mark the stored clue
    `contaminated`. Returned reliability is the new effective value to
    store on `known_clues`.
    """
    if not isinstance(clue, dict):
        return {"text": "", "reliability": 1.0, "contaminated": False,
                "used_false": False}
    chance = float(clue.get("false_variant_chance") or 0.0)
    true_text = (clue.get("text_pl") or clue.get("text") or
                 clue.get("description") or "")
    false_text = (clue.get("false_variant_pl") or clue.get("false_variant")
                  or "")
    rel = float(clue.get("reliability", clue.get("truth", 1.0)))
    R = rng or random
    if chance > 0.0 and false_text and R.random() < chance:
        # Distortion landed. Lower reliability to half of declared truth, or
        # 0.3 floor — whichever is lower.
        new_rel = min(0.3, rel * 0.5)
        return {"text": false_text, "reliability": new_rel,
                "contaminated": True, "used_false": True}
    return {"text": true_text, "reliability": rel,
            "contaminated": False, "used_false": False}
