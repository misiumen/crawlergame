"""Prompt 18 — Sponsor catalog (v1).

Six sponsor factions, each with a distinct mechanical niche so that the
"floor sponsor" choice actually changes optimal playstyle.

Each sponsor entry is pure data (no engine imports). The engine module
`engine.sponsors` reads from `SPONSORS` and `SPONSORS_BY_FLOOR` to drive
audience interventions (gifts, hunters, heckles).

Schema (all keys required unless marked optional):
    key               unique identifier; also the locale-prefix
    name_key          locale key for display name
    name_fallback     PL fallback display name
    tagline_key       locale key for the one-line "what we are"
    tagline_fallback  PL fallback tagline
    tone              one-line stylistic descriptor (PL)
    likes_tags        list of action tags that BOOST attention (+1..+2 each)
    dislikes_tags     list of action tags that COST attention (-1..-2 each)
    gift_pool         list of item template keys this sponsor drops in
                      safehouses when the player is "in favor"
    hunter_key        NPC/monster template key spawned when the player is
                      "out of favor" and audience is HOT+
    heckle_keys       list of narrator-line locale keys; one is picked at
                      band-crossings or low-attention moments
    intervention_cooldown_minutes  minimum minutes between any two
                      interventions from this sponsor (default = one
                      in-game day, MINUTES_PER_DAY)

The engine treats `likes_tags` and `dislikes_tags` as opaque strings —
they're matched against tags supplied by gameplay hooks. New hook
points (e.g. lockpicking, dialogue choices) just need to emit a tag.
"""
from __future__ import annotations

from typing import Dict, Any, List


# Sponsor keys (also used as locale-prefix and floor-rotation lookup).
SPONSOR_NOVACHEM       = "novachem_biotech"
SPONSOR_SPORT          = "sponsor_bezpieczenstwa_sportu"
SPONSOR_CZARNY_RYNEK   = "czarny_rynek_plus"
SPONSOR_MINISTERSTWO   = "ministerstwo_pamieci"
SPONSOR_RECYKLING      = "kult_recyklingu"
SPONSOR_KANAL_7        = "kanal_7_krawedz"


SPONSORS: Dict[str, Dict[str, Any]] = {
    SPONSOR_NOVACHEM: {
        "key": SPONSOR_NOVACHEM,
        "name_key": "sponsor_novachem_name",
        "name_fallback": "NovaChem Biotech",
        "tagline_key": "sponsor_novachem_tagline",
        "tagline_fallback": "Działa. Boli. Sprzedaje się.",
        "tone": "klinicznie sarkastyczny",
        "likes_tags": [
            "crafting", "salvage", "chemical", "clever_craft",
            "consumable_used", "first_aid",
        ],
        "dislikes_tags": [
            "theft", "sponsor_property_damage", "brute_force",
            "rebel_speech",
        ],
        "gift_pool": ["bandage", "stimpak", "antidote", "chem_reagent"],
        "hunter_key": "agent_kontroli_jakosci",
        "heckle_keys": [
            "sponsor_novachem_heckle_1",
            "sponsor_novachem_heckle_2",
            "sponsor_novachem_heckle_3",
        ],
        "intervention_cooldown_minutes": 24 * 60,
    },
    SPONSOR_SPORT: {
        "key": SPONSOR_SPORT,
        "name_key": "sponsor_sport_name",
        "name_fallback": "Sponsor Bezpieczeństwa Sportu",
        "tagline_key": "sponsor_sport_tagline",
        "tagline_fallback": "Widowiskowość zgodna z regulaminem 4.2.",
        "tone": "bezduszny korporacyjny biurokrata",
        "likes_tags": [
            "combat", "crit_hit", "env_kill", "heavy_attack_hit",
            "spectacle", "kill_lethal",
        ],
        "dislikes_tags": [
            "flee", "hide", "negotiate", "non_lethal", "stealth_takedown",
        ],
        "gift_pool": ["weapon_part", "kevlar_scrap", "adrenaline", "ammo_box"],
        "hunter_key": "egzekutor_ligi",
        "heckle_keys": [
            "sponsor_sport_heckle_1",
            "sponsor_sport_heckle_2",
            "sponsor_sport_heckle_3",
        ],
        "intervention_cooldown_minutes": 24 * 60,
    },
    SPONSOR_CZARNY_RYNEK: {
        "key": SPONSOR_CZARNY_RYNEK,
        "name_key": "sponsor_czarny_rynek_name",
        "name_fallback": "Czarny Rynek Plus",
        "tagline_key": "sponsor_czarny_rynek_tagline",
        "tagline_fallback": "Wszystko ma cenę. Dwie ceny.",
        "tone": "konspiracyjnie życzliwy",
        "likes_tags": [
            "theft", "lockpicking", "salvage_sponsor_property",
            "memetic_mischief", "black_market_use", "sponsor_property_damage",
        ],
        "dislikes_tags": [
            "compliance", "report_to_authority", "quiet_resolution",
            "pro_state_dialogue",
        ],
        "gift_pool": ["lockpick", "ammo_box", "cash_voucher", "fence_loot"],
        "hunter_key": "windykator",
        "heckle_keys": [
            "sponsor_czarny_rynek_heckle_1",
            "sponsor_czarny_rynek_heckle_2",
            "sponsor_czarny_rynek_heckle_3",
        ],
        "intervention_cooldown_minutes": 24 * 60,
    },
    SPONSOR_MINISTERSTWO: {
        "key": SPONSOR_MINISTERSTWO,
        "name_key": "sponsor_ministerstwo_name",
        "name_fallback": "Ministerstwo Pamięci",
        "tagline_key": "sponsor_ministerstwo_tagline",
        "tagline_fallback": "Pamiętaj prawidłowo.",
        "tone": "monotonny i niepokojąco uprzejmy",
        "likes_tags": [
            "memetic_seed", "belief_invocation", "pro_state_dialogue",
            "conform", "propaganda_recite",
        ],
        "dislikes_tags": [
            "contradict_state", "rebel_speech", "truth_leak",
            "theft", "memetic_mischief",
        ],
        "gift_pool": ["forged_id", "propaganda_zine", "authorized_stim",
                      "ration_pack"],
        "hunter_key": "redaktor_naczelny",
        "heckle_keys": [
            "sponsor_ministerstwo_heckle_1",
            "sponsor_ministerstwo_heckle_2",
            "sponsor_ministerstwo_heckle_3",
        ],
        "intervention_cooldown_minutes": 24 * 60,
    },
    SPONSOR_RECYKLING: {
        "key": SPONSOR_RECYKLING,
        "name_key": "sponsor_recykling_name",
        "name_fallback": "Kult Recyklingu",
        "tagline_key": "sponsor_recykling_tagline",
        "tagline_fallback": "Wszystko wraca do obwodu.",
        "tone": "zacietrzewienie kaznodziei na targu",
        "likes_tags": [
            "mass_salvage", "break_obj_then_salvage", "give_to_cycle",
            "clear_floor_clean", "salvage", "sponsor_property_damage",
        ],
        "dislikes_tags": [
            "hoarding", "waste", "kill_without_salvage",
            "unused_consumable",
        ],
        "gift_pool": ["scrap_bundle", "jury_tool", "blessed_amulet",
                      "bandage"],
        "hunter_key": "pielgrzym_recyklera",
        "heckle_keys": [
            "sponsor_recykling_heckle_1",
            "sponsor_recykling_heckle_2",
            "sponsor_recykling_heckle_3",
        ],
        "intervention_cooldown_minutes": 24 * 60,
    },
    SPONSOR_KANAL_7: {
        "key": SPONSOR_KANAL_7,
        "name_key": "sponsor_kanal7_name",
        "name_fallback": "Kanał 7: Krawędź",
        "tagline_key": "sponsor_kanal7_tagline",
        "tagline_fallback": "Pozostań po reklamach.",
        "tone": "napięty, telewizyjny, ironiczny",
        "likes_tags": [
            "crit_success", "env_kill", "near_death_recovery",
            "dramatic_save", "audience_high_band", "spectacle",
        ],
        "dislikes_tags": [
            "quiet_play", "hide", "long_idle", "wait_spam",
        ],
        "gift_pool": ["camera_drone", "premium_painkiller", "branded_armor",
                      "stimpak"],
        "hunter_key": "anty_gospodarz",
        "heckle_keys": [
            "sponsor_kanal7_heckle_1",
            "sponsor_kanal7_heckle_2",
            "sponsor_kanal7_heckle_3",
        ],
        "intervention_cooldown_minutes": 24 * 60,
    },
}


# P29.2 — SPONSORS_BY_FLOOR + sponsor_for_floor REMOVED.
# Sponsors compete continuously based on what the player does, not
# by floor assignment. See engine/sponsors.py:current_floor_sponsor_key
# (renamed semantics: now returns whoever has max attention).
# Floor flavor still INSPIRES via per-room `theme_sponsor_boost` in
# ROOM_POOL (content/data/room_pool.py).


def get_sponsor(key: str) -> Dict[str, Any]:
    """Return the sponsor record for `key`, or NovaChem if unknown."""
    return SPONSORS.get(key) or SPONSORS[SPONSOR_NOVACHEM]


def all_sponsor_keys() -> List[str]:
    return list(SPONSORS.keys())
