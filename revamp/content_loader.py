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


# ── Failure / partial-success narration ─────────────────────────────────────

def _failure_table(level: str) -> Dict[str, List[str]]:
    try:
        from .data import failure_templates as ft
    except Exception:
        return {}
    return {
        "partial":  getattr(ft, "PARTIAL_SUCCESS_TEMPLATES", {}),
        "failure":  getattr(ft, "FAILURE_TEMPLATES", {}),
        "crit_fail":getattr(ft, "CRITICAL_FAILURE_TEMPLATES", {}),
    }.get(level, {})


def random_partial_success_line(category: Optional[str] = None) -> Optional[str]:
    return _pick_failure_line("partial", category)


def random_failure_line(category: Optional[str] = None) -> Optional[str]:
    return _pick_failure_line("failure", category)


def random_critical_failure_line(category: Optional[str] = None) -> Optional[str]:
    return _pick_failure_line("crit_fail", category)


def _pick_failure_line(level: str, category: Optional[str]) -> Optional[str]:
    table = _failure_table(level)
    if not table:
        return None
    if category and category in table:
        bucket = table[category]
    else:
        bucket = [line for arr in table.values() for line in arr]
    if not bucket:
        return None
    return random.choice(bucket)


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
