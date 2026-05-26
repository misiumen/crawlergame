"""Body-part plans for body-aware combat (Prompt 26a).

Each body plan describes a creature's targetable zones. When an attacker
selects a zone, combat applies the zone's hit modifier and damage scaling;
zone HP depletes alongside total HP; when a zone reaches 0 it "breaks"
and applies a maim status to the victim (and is later surfaced as a
butcher yield modifier in `engine.corpses`).

Each zone field:
    label_pl     — Polish display label
    hp_frac      — fraction of max_hp the zone takes as its zone-pool
    to_hit_mod   — penalty/bonus to the to-hit roll when targeted
    damage_mul   — damage scaled by this multiplier if zone is hit
    maim_status  — combat status applied when zone HP reaches 0
                   (None means no maim — the break is cosmetic / butcher-only)
    butcher_intact_bonus  — material key + count granted on butcher if the
                            zone wasn't broken (zone "survived" the fight)
    butcher_broken_bonus  — material key + count granted on butcher if the
                            zone WAS broken (e.g. severed limb → leather)

The default plan ("humanoid") is used by every monster unless their key
has an override in `PLANS_BY_MONSTER_KEY` below, or their tags resolve
through `plan_for_entity`.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple


# ── Zone defs ─────────────────────────────────────────────────────────

# Status constants — declared here as strings to avoid an import cycle
# with engine.combat. The combat module reads these by string match.
STATUS_DISARMED = "disarmed"
STATUS_SLOWED   = "slowed"
STATUS_BLINDED  = "blinded"
STATUS_STUNNED  = "stunned"
STATUS_PRONE    = "prone"
STATUS_BLEEDING = "bleeding"


# Plan tables: zone_key → properties.
# `display_order` is the order zones are presented in the VATS HUD
# (top to bottom). Render layout in ui.py uses this order.
PLAN_HUMANOID: Dict[str, dict] = {
    "head":   {"label_pl": "głowa",     "hp_frac": 0.30, "to_hit_mod": -3,
               "damage_mul": 1.5, "maim_status": STATUS_STUNNED,
               "butcher_intact_bonus": [("tooth", 1)],
               "butcher_broken_bonus": [("bone_fragments", 1)],
               "display_order": 0},
    "torso":  {"label_pl": "tors",      "hp_frac": 0.65, "to_hit_mod":  0,
               "damage_mul": 1.0, "maim_status": None,
               "butcher_intact_bonus": [],
               "butcher_broken_bonus": [("meat_chunk", 1)],
               "display_order": 1},
    "l_arm":  {"label_pl": "lewa ręka", "hp_frac": 0.25, "to_hit_mod": -1,
               "damage_mul": 0.8, "maim_status": STATUS_DISARMED,
               "butcher_intact_bonus": [],
               "butcher_broken_bonus": [("leather_scraps", 1), ("bone_fragments", 1)],
               "display_order": 2},
    "r_arm":  {"label_pl": "prawa ręka","hp_frac": 0.25, "to_hit_mod": -1,
               "damage_mul": 0.8, "maim_status": STATUS_DISARMED,
               "butcher_intact_bonus": [],
               "butcher_broken_bonus": [("leather_scraps", 1), ("bone_fragments", 1)],
               "display_order": 3},
    "l_leg":  {"label_pl": "lewa noga", "hp_frac": 0.30, "to_hit_mod": -2,
               "damage_mul": 0.9, "maim_status": STATUS_SLOWED,
               "butcher_intact_bonus": [],
               "butcher_broken_bonus": [("sinew", 1)],
               "display_order": 4},
    "r_leg":  {"label_pl": "prawa noga","hp_frac": 0.30, "to_hit_mod": -2,
               "damage_mul": 0.9, "maim_status": STATUS_SLOWED,
               "butcher_intact_bonus": [],
               "butcher_broken_bonus": [("sinew", 1)],
               "display_order": 5},
}


PLAN_SMALL_QUADRUPED: Dict[str, dict] = {
    "head":   {"label_pl": "łeb",        "hp_frac": 0.35, "to_hit_mod": -3,
               "damage_mul": 1.6, "maim_status": STATUS_STUNNED,
               "butcher_intact_bonus": [("tooth", 1)],
               "butcher_broken_bonus": [("bone_fragments", 1)],
               "display_order": 0},
    "torso":  {"label_pl": "tułów",      "hp_frac": 0.70, "to_hit_mod":  0,
               "damage_mul": 1.0, "maim_status": None,
               "butcher_intact_bonus": [],
               "butcher_broken_bonus": [("meat_chunk", 1)],
               "display_order": 1},
    "l_leg":  {"label_pl": "lewa łapa", "hp_frac": 0.20, "to_hit_mod": -1,
               "damage_mul": 0.8, "maim_status": STATUS_SLOWED,
               "butcher_intact_bonus": [("claw", 1)],
               "butcher_broken_bonus": [("sinew", 1)],
               "display_order": 2},
    "r_leg":  {"label_pl": "prawa łapa","hp_frac": 0.20, "to_hit_mod": -1,
               "damage_mul": 0.8, "maim_status": STATUS_SLOWED,
               "butcher_intact_bonus": [("claw", 1)],
               "butcher_broken_bonus": [("sinew", 1)],
               "display_order": 3},
}


PLAN_DRONE: Dict[str, dict] = {
    "sensor":    {"label_pl": "sensor",       "hp_frac": 0.25, "to_hit_mod": -2,
                  "damage_mul": 1.3, "maim_status": STATUS_BLINDED,
                  "butcher_intact_bonus": [("camera_lens", 1)],
                  "butcher_broken_bonus": [("broken_screen", 1)],
                  "display_order": 0},
    "body":      {"label_pl": "korpus",       "hp_frac": 0.70, "to_hit_mod":  0,
                  "damage_mul": 1.0, "maim_status": None,
                  "butcher_intact_bonus": [],
                  "butcher_broken_bonus": [("scrap_metal", 2), ("wire_bundle", 1)],
                  "display_order": 1},
    "propulsion":{"label_pl": "napęd",        "hp_frac": 0.30, "to_hit_mod": -2,
                  "damage_mul": 0.9, "maim_status": STATUS_SLOWED,
                  "butcher_intact_bonus": [("motor_unit", 1)],
                  "butcher_broken_bonus": [("scrap_metal", 1)],
                  "display_order": 2},
}


PLAN_BLOB: Dict[str, dict] = {
    "mass":   {"label_pl": "masa", "hp_frac": 1.0, "to_hit_mod": 0,
               "damage_mul": 1.0, "maim_status": None,
               "butcher_intact_bonus": [],
               "butcher_broken_bonus": [("ichor_sample", 2)],
               "display_order": 0},
}


PLANS: Dict[str, Dict[str, dict]] = {
    "humanoid":         PLAN_HUMANOID,
    "small_quadruped":  PLAN_SMALL_QUADRUPED,
    "drone":            PLAN_DRONE,
    "blob":             PLAN_BLOB,
}


# Per-monster-key plan overrides. Most monsters resolve via tags
# (see plan_for_entity below); this dict is for hard-coded exceptions.
PLANS_BY_MONSTER_KEY: Dict[str, str] = {
    "tunnel_runt": "small_quadruped",
    # All other monsters from MON default to humanoid via tag dispatch.
}


# Tag → plan-key dispatch. First match wins.
PLAN_BY_TAG: List[Tuple[str, str]] = [
    ("drone",      "drone"),
    ("robot",      "drone"),
    ("blob",       "blob"),
    ("ooze",       "blob"),
    ("small",      "small_quadruped"),
    ("humanoid",   "humanoid"),
    ("monster",    "humanoid"),
]


# ── Lookup ────────────────────────────────────────────────────────────

def plan_for_entity(entity) -> Dict[str, dict]:
    """Resolve a body plan for the entity. Order:
       1. Monster-key override (PLANS_BY_MONSTER_KEY)
       2. Tag-based dispatch (PLAN_BY_TAG)
       3. Default: humanoid
    """
    if entity is None:
        return PLAN_HUMANOID
    key = getattr(entity, "key", "") or ""
    if key in PLANS_BY_MONSTER_KEY:
        return PLANS[PLANS_BY_MONSTER_KEY[key]]
    tags = list(getattr(entity, "tags", []) or [])
    for tag, plan_key in PLAN_BY_TAG:
        if tag in tags and plan_key in PLANS:
            return PLANS[plan_key]
    return PLAN_HUMANOID


def init_body_parts(entity) -> Dict[str, dict]:
    """Build the runtime body-parts dict for an entity. Idempotent —
    if already initialized, returns the existing dict unchanged."""
    if entity is None:
        return {}
    existing = getattr(entity, "body_parts", None)
    if existing:
        return existing
    plan = plan_for_entity(entity)
    max_hp = max(1, int(getattr(entity, "max_hp", 1)))
    parts: Dict[str, dict] = {}
    for zone, props in plan.items():
        zone_max = max(1, int(round(max_hp * props["hp_frac"])))
        parts[zone] = {
            "hp": zone_max,
            "max_hp": zone_max,
            "broken": False,
        }
    entity.body_parts = parts
    return parts


def zones_in_display_order(plan: Dict[str, dict]) -> List[Tuple[str, dict]]:
    """Return (zone_key, props) pairs sorted by `display_order`."""
    return sorted(plan.items(), key=lambda kv: kv[1].get("display_order", 99))
