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
# P29.16 — five new sponsors. Audit: 6 sponsors was thin for a
# DCC-faithful crawler. Each new entry has a distinct mechanical niche
# (debt, stunt, anarcho, mutation, populist) so likes/dislikes carve
# different optimal plays.
SPONSOR_BRACTWO        = "bractwo_komornika"
SPONSOR_LIGA_BRAWUR    = "liga_brawurowa"
SPONSOR_MROWKI         = "spoldzielnia_mrowek"
SPONSOR_POLIMERY       = "bog_polimerow"
SPONSOR_STADION        = "stadion_wolnosci"


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

    # ── P29.16 — New sponsors ─────────────────────────────────────────────

    SPONSOR_BRACTWO: {
        "key": SPONSOR_BRACTWO,
        "name_key": "sponsor_bractwo_name",
        "name_fallback": "Bractwo Komornika",
        "tagline_key": "sponsor_bractwo_tagline",
        "tagline_fallback": "Każdy dług ma piękną formę.",
        "tone": "sadystycznie kurtuazyjny",
        "likes_tags": [
            "bribe", "intimidate", "sponsor_property_damage", "theft",
            "credit_spent", "extortion",
        ],
        "dislikes_tags": [
            "charity", "free_giveaway", "amnesty", "negotiate_kindly",
            "quiet_resolution",
        ],
        "gift_pool": ["debt_collector_baton", "blank_iou_pad",
                      "stim_wytrzymalosci", "cash_voucher"],
        "hunter_key": "asesor_komornika",
        "heckle_keys": [
            "sponsor_bractwo_heckle_1",
            "sponsor_bractwo_heckle_2",
            "sponsor_bractwo_heckle_3",
        ],
        "intervention_cooldown_minutes": 24 * 60,
    },
    SPONSOR_LIGA_BRAWUR: {
        "key": SPONSOR_LIGA_BRAWUR,
        "name_key": "sponsor_liga_brawur_name",
        "name_fallback": "Liga Brawurowa",
        "tagline_key": "sponsor_liga_brawur_tagline",
        "tagline_fallback": "Skacz, zanim pomyślisz. Filmuj, póki spadasz.",
        "tone": "ekstatycznie głośny komentator stuntów",
        "likes_tags": [
            "heavy_attack_hit", "env_kill", "dramatic_save",
            "fall_damage_self", "spectacle", "near_death_recovery",
        ],
        "dislikes_tags": [
            "careful_attack", "wait_spam", "long_idle", "stealth_takedown",
        ],
        "gift_pool": ["liga_helmet", "rampage_stim", "improvised_spear",
                      "premium_painkiller"],
        "hunter_key": "ekstremalny_zawodnik",
        "heckle_keys": [
            "sponsor_liga_brawur_heckle_1",
            "sponsor_liga_brawur_heckle_2",
            "sponsor_liga_brawur_heckle_3",
        ],
        "intervention_cooldown_minutes": 24 * 60,
    },
    SPONSOR_MROWKI: {
        "key": SPONSOR_MROWKI,
        "name_key": "sponsor_mrowki_name",
        "name_fallback": "Spółdzielnia Mrówek",
        "tagline_key": "sponsor_mrowki_tagline",
        "tagline_fallback": "Mała stopa, wielki nacisk grupowy.",
        "tone": "społecznikowski, naiwnie idealistyczny",
        "likes_tags": [
            "stealth_takedown", "non_lethal", "negotiate_kindly",
            "quiet_resolution", "stealth", "free_giveaway",
        ],
        "dislikes_tags": [
            "kill_lethal", "spectacle", "crit_hit", "extortion",
            "intimidate",
        ],
        "gift_pool": ["lockpick", "smoke_bottle", "bandage",
                      "rope_bundle"],
        "hunter_key": "koordynator_robotniczy",
        "heckle_keys": [
            "sponsor_mrowki_heckle_1",
            "sponsor_mrowki_heckle_2",
            "sponsor_mrowki_heckle_3",
        ],
        "intervention_cooldown_minutes": 24 * 60,
    },
    SPONSOR_POLIMERY: {
        "key": SPONSOR_POLIMERY,
        "name_key": "sponsor_polimery_name",
        "name_fallback": "Bóg Polimerów",
        "tagline_key": "sponsor_polimery_tagline",
        "tagline_fallback": "Wszystko miękkie, miękkie, MIĘKKIE.",
        "tone": "syntetyczna ekstaza, oddech reaktora",
        "likes_tags": [
            "chemical", "fungal", "fungal_kill", "mutate_self",
            "consumable_used", "novachem_accident",
        ],
        "dislikes_tags": [
            "fire_damage_dealt", "burn_organic", "anti_chemical",
            "sterile_kill",
        ],
        "gift_pool": ["fungal_pill", "polymer_balm", "weapon_poison_coat",
                      "antidote"],
        "hunter_key": "kaplan_polimerow",
        "heckle_keys": [
            "sponsor_polimery_heckle_1",
            "sponsor_polimery_heckle_2",
            "sponsor_polimery_heckle_3",
        ],
        "intervention_cooldown_minutes": 24 * 60,
    },
    SPONSOR_STADION: {
        "key": SPONSOR_STADION,
        "name_key": "sponsor_stadion_name",
        "name_fallback": "Stadion Wolności",
        "tagline_key": "sponsor_stadion_tagline",
        "tagline_fallback": "Krzycz głośniej, żeby studio słyszało.",
        "tone": "populistyczny, fanowski, transmisyjny",
        "likes_tags": [
            "rebel_speech", "mass_kill", "audience_high_band",
            "dramatic_save", "crit_hit", "spectacle",
        ],
        "dislikes_tags": [
            "compliance", "pro_state_dialogue", "report_to_authority",
            "quiet_resolution",
        ],
        "gift_pool": ["megafon_propaganda", "fan_throwable", "improvised_club",
                      "morale_brew"],
        "hunter_key": "weteran_trybun",
        "heckle_keys": [
            "sponsor_stadion_heckle_1",
            "sponsor_stadion_heckle_2",
            "sponsor_stadion_heckle_3",
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
