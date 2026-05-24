"""Map content-metadata risk/reward keys to effect dicts (Prompt 06a, gap #1).

Templates declare what *kind* of bad/good thing can happen but stay out of
mechanics. This module converts those declarative keys into the effect
dicts that `consequences.apply()` already understands, plus a few new
soft ones (sponsor_attention, world flags).

Lookup is safe — unknown keys produce no effect.

Public:
    risk_effects(keys)   -> list[effect-dict]
    reward_effects(keys) -> list[effect-dict]
    risk_log_lines(keys) -> list[str]       (narrative-only hint lines)
    reward_log_lines(keys)-> list[str]
"""
from typing import List, Optional


# Risks: bad-flavored effects + a short Polish hint line per key.
_RISK_TABLE = {
    "tracked_by_sponsor": {
        "effects": [
            {"type": "add_audience", "amount": 1},
            {"type": "world_flag",   "key": "sponsor_attention", "value": True},
        ],
        "line": "Kamera sponsora notuje. Coś trafi w przyszły briefing.",
    },
    "black_market_interest": {
        "effects": [
            {"type": "world_flag", "key": "blackmarket_intel_leaked", "value": True},
            {"type": "gain_rumor", "category": "false_or_biased"},
        ],
        "line": "Ktoś z czarnego rynku dowiaduje się o tobie szybciej, niż chciałeś.",
    },
    "makes_noise": {
        "effects": [{"type": "add_noise", "amount": 1}],
        "line": "Coś trzaska. Echo niesie się dalej, niż liczyłeś.",
    },
    "attracts_patrol": {
        "effects": [{"type": "alert_patrol"}],
        "line": "Patrol odbiera sygnał. Idą.",
    },
    "damages_item": {
        "effects": [{"type": "item_damage", "tag": "*"}],
        "line": "Coś trzeszczy w plecaku. Niedobrze.",
    },
    "increases_alert": {
        "effects": [{"type": "trigger_alarm", "amount": 1}],
        "line": "Alarm rośnie o stopień. Sponsor wyraża troskę.",
    },
    "social_suspicion": {
        "effects": [{"type": "change_relationship", "amount": -1}],
        "line": "Patrzą na ciebie inaczej. To rzadko jest komplement.",
    },
    "unsafe_crafting": {
        "effects": [
            {"type": "damage_self", "amount": 1},
            {"type": "item_damage", "tag": "*"},
        ],
        "line": "Coś rwie palce. Składasz to nadal, ale gorzej.",
    },
    "disease_risk": {
        "effects": [{"type": "world_flag", "key": "infected_exposure", "value": True}],
        "line": "Mokro. Ciepło. Niedobrze.",
    },
    "chemical_exposure": {
        "effects": [
            {"type": "damage_self", "amount": 1},
            {"type": "world_flag", "key": "chem_exposure", "value": True},
        ],
        "line": "W gardle masz coś, czego nie powinieneś znać z bliska.",
    },
    "betrayal":             {"effects": [{"type": "change_relationship", "amount": -2}],
                             "line": "Coś się złamało w relacji. Trudniej będzie to skleić."},
    "audience_swing":       {"effects": [{"type": "add_audience", "amount": -1}],
                             "line": "Widownia traci wątek. Wraca do innych transmisji."},
    "alert_patrol":         {"effects": [{"type": "alert_patrol"}],
                             "line": "Patrol wie."},
    "self_damage":          {"effects": [{"type": "damage_self", "amount": 1}],
                             "line": "Coś cię ugryzło. Niedosłownie. Może."},
    "item_damage":          {"effects": [{"type": "item_damage", "tag": "*"}],
                             "line": "Sprzęt protestuje."},
    "relationship_down":    {"effects": [{"type": "change_relationship", "amount": -1}],
                             "line": "Sympatia spadła."},
    "framed":               {"effects": [{"type": "world_flag", "key": "framed", "value": True},
                                         {"type": "add_audience", "amount": -1}],
                             "line": "Sponsor już ma materiał. Materiał już ma kontekst."},
    "combat_loss":          {"effects": [{"type": "damage_self", "amount": 2}],
                             "line": "Walka nie poszła tak, jak miało wyglądać."},
}


# Rewards: small positive effects + Polish hint line per key.
_REWARD_TABLE = {
    "audience_awareness": {
        "effects": [{"type": "add_audience", "amount": 1}],
        "line": "Widownia notuje pozytywnie.",
    },
    "audience_boost": {
        "effects": [{"type": "add_audience", "amount": 3}],
        "line": "Widownia wybucha aprobatą.",
    },
    "audience_high": {
        "effects": [{"type": "add_audience", "amount": 5}],
        "line": "Ratingi skaczą.",
    },
    "clue_gain": {
        "effects": [{"type": "reveal_clue"}],
        "line": "Coś rzuca ci się w oczy. Może to coś.",
    },
    "material_gain": {
        # Engine doesn't yet have a materials inventory; we add a world flag
        # so future salvage code can pick it up.
        "effects": [{"type": "world_flag", "key": "pending_materials", "value": True}],
        "line": "Coś zbierasz po cichu. Na później.",
    },
    "relationship_gain": {
        "effects": [{"type": "change_relationship", "amount": 1}],
        "line": "Patrzy na ciebie inaczej. Tym razem życzliwiej.",
    },
    "safehouse_discount": {
        "effects": [{"type": "world_flag", "key": "safehouse_discount", "value": True}],
        "line": "Ktoś zostawia ci niższą cenę. Z notatką: nie mów nikomu.",
    },
    "rumor_gain":      {"effects": [{"type": "gain_rumor"}], "line": "Słyszysz coś nowego."},
    "class_affinity_gain": {
        # Generic; specific kind is provided in the effect call when applicable
        "effects": [{"type": "class_affinity_shift", "kind": "social", "amount": 1}],
        "line": "Twoje zachowanie pasuje do nowego profilu zawodnika.",
    },
    "hidden_exit_hint": {
        "effects": [{"type": "world_flag", "key": "hidden_exit_hinted", "value": True}],
        "line": "W kącie pokoju jest coś, co nie powinno być widoczne. Teraz wiesz.",
    },
    "boss_weakness_hint": {
        "effects": [{"type": "reveal_clue"}],
        "line": "Dostajesz coś, co przyda się na bossa.",
    },
    "floor_exit":      {"effects": [{"type": "world_flag", "key": "exit_unlocked", "value": True}],
                        "line": "Wyjście jest teraz w zasięgu."},
    "trade_credits":   {"effects": [{"type": "add_credits", "amount": 25}],
                        "line": "Coś sprzedajesz, coś zostaje."},
    "stealth_affinity":{"effects": [{"type": "class_affinity_shift", "kind": "stealth", "amount": 1}],
                        "line": "Twój profil cienia się pogłębia."},
    "tech_affinity":   {"effects": [{"type": "class_affinity_shift", "kind": "tech", "amount": 1}],
                        "line": "Twój profil technika się pogłębia."},
    "social_affinity": {"effects": [{"type": "class_affinity_shift", "kind": "social", "amount": 1}],
                        "line": "Twój profil społeczny się pogłębia."},
    "showmanship_affinity":{"effects": [{"type": "class_affinity_shift", "kind": "showmanship", "amount": 1}],
                            "line": "Twój profil performera się pogłębia."},
    "boss_loot":       {"effects": [{"type": "add_credits", "amount": 50}],
                        "line": "Coś, co miało być na bossie, jest teraz przy tobie."},
    "faction_rep":     {"effects": [{"type": "world_flag", "key": "faction_rep_up", "value": True}],
                        "line": "Frakcja zapamiętuje. Sponsor zauważa, że frakcja zapamiętuje."},
    "sponsor_intel":   {"effects": [{"type": "gain_rumor"}],
                        "line": "Sponsor coś niechcący ujawnia."},
    "kill_intel":      {"effects": [{"type": "gain_rumor"}],
                        "line": "Wiesz teraz, kto i czemu."},
    "intel_floor":     {"effects": [{"type": "reveal_clue"}],
                        "line": "Mapa piętra robi się o krok jaśniejsza."},
    "temporary_ally":  {"effects": [{"type": "world_flag", "key": "ally_present", "value": True}],
                        "line": "Ktoś idzie z tobą. Na razie."},
    "contraband":      {"effects": [{"type": "world_flag", "key": "contraband_acquired", "value": True}],
                        "line": "Masz coś, czego nie powinno tu być."},
    "secret_route_hint":{"effects": [{"type": "world_flag", "key": "secret_route_hinted", "value": True}],
                         "line": "Druga droga zaczyna nabierać kształtu."},
    "map_hint":        {"effects": [{"type": "world_flag", "key": "map_hint", "value": True}],
                        "line": "Coś, co było mgliste, robi się bardziej trójwymiarowe."},
    "partial_information":{"effects": [], "line": "To wiesz. Reszta jeszcze nie."},
    "utility":         {"effects": [], "line": ""},
}


# ── Public API ───────────────────────────────────────────────────────────────

def risk_effects(keys) -> List[dict]:
    return _flatten(keys, _RISK_TABLE, "effects")


def reward_effects(keys) -> List[dict]:
    return _flatten(keys, _REWARD_TABLE, "effects")


def risk_log_lines(keys) -> List[str]:
    return _flatten(keys, _RISK_TABLE, "line", as_lines=True)


def reward_log_lines(keys) -> List[str]:
    return _flatten(keys, _REWARD_TABLE, "line", as_lines=True)


def all_risks() -> List[str]:
    return list(_RISK_TABLE.keys())


def all_rewards() -> List[str]:
    return list(_REWARD_TABLE.keys())


def _flatten(keys, table, field, as_lines=False) -> List:
    if not keys:
        return []
    out = []
    for k in keys:
        entry = table.get(k)
        if not entry:
            continue
        val = entry.get(field)
        if val is None:
            continue
        if as_lines:
            if val:
                out.append(val)
        else:
            if isinstance(val, list):
                out.extend(val)
    return out
