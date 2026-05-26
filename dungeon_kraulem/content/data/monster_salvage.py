"""Per-monster corpse / salvage templates (Prompt 24).

When a monster dies in combat, `engine.corpses.transform_to_corpse` looks
up its key here to decide:

  * what the corpse is called          (`name_pl` / `name_en`)
  * what flavor text it shows on inspect (`lore`)
  * what materials butchering yields    (`salvage` — {key: (min, max)})
  * how long butchering takes           (`salvage_time_min`)
  * how loud butchering is              (`salvage_noise`)
  * whether the corpse is edible        (`edible`, `eat_hp_delta`,
                                          `eat_status`, `eat_audience_tag`)
  * how long until the corpse decays    (`decay_minutes`)
  * which tag-bus events fire on each
    interaction                          (`butcher_tag`, `eat_tag`)
  * any titles awarded                   (`butcher_title_grants`)
  * any tools that make the job better   (`preferred_tool_tags`)

EXTENSIBILITY HOOKS — these fields are *defined* even when unused, so
future prompts can wire them without schema migration:

  * `decay_minutes`         — P26b (floor timer) will tick this down
  * `smell_budget`          — P26b monster AI uses for aggro pulls
  * `cannibal_tag`          — eaten by player + corpse_was_type=='crawler'
                              → tag bus emits this (P27 sponsor reactions)
  * `desecration_tag`       — butchered while sponsor=ministerstwo etc.
  * `trophy_drop`           — rare named item placed in inventory instead
                              of materials. P31 run summary references.
  * `lore_id`               — stable lookup key the journal can dereference;
                              LLM enrichment in P30 reads this for richer
                              flavor.
  * `recipe_unlock_hint`    — when butchered, surfaces a "you could use
                              this for X" line. Pillar 2 (crafting).

Authors: only `name_pl` and `salvage` are strictly required. Everything
else falls back to the DEFAULT template below.
"""
from __future__ import annotations
from typing import Dict, Any, Tuple


# ── Default template ─────────────────────────────────────────────────────

DEFAULT_TEMPLATE: Dict[str, Any] = {
    "name_pl": "ciało",
    "name_en": "corpse",
    "lore": "Bezruch. Krew już krzepnie. Nie wszystko, co tu jeszcze ciepłe, "
            "powinno zostać dotknięte.",
    "lore_id": "corpse_default",
    "salvage": {                          # material_key: (min, max)
        "meat_chunk":          (1, 1),
        "contaminated_blood":  (0, 1),
    },
    "salvage_time_min": 5,
    "salvage_noise":    2,
    "preferred_tool_tags": ["sharp"],     # any wielded weapon with `sharp`
                                          # tag yields +1 of each material
    "edible":          False,
    "eat_hp_delta":    0,
    "eat_status":      None,
    "eat_audience_tag": "ate_corpse",     # always fires on eat
    "butcher_audience_tag": None,         # optional extra tag on butcher
    "butcher_title_grants": [],           # title-tag strings awarded
    "decay_minutes":   240,               # 4 in-game hours (hook; not yet
                                          # actively decaying)
    "smell_budget":    1,                 # P26b: scaled into monster aggro
    "cannibal_tag":    "cannibal",        # fired on eat if corpse_was_type
                                          # == 'crawler'
    "desecration_tag": None,              # fired on butcher when player
                                          # has sponsor in OPPOSED_TAGS
    "trophy_drop":     None,              # optional (item_key, chance) tuple
    "recipe_unlock_hint": None,
}


# ── Per-monster overrides ────────────────────────────────────────────────

CORPSE_TEMPLATES: Dict[str, Dict[str, Any]] = {

    # ── Floor 1–3 trash mobs ────────────────────────────────────────────
    "tunnel_runt": {
        "name_pl": "padlina tunelowego szczurka",
        "lore":    "Drobne, jeszcze ciepłe. Czerwone oczy zmętniały. Łapy "
                   "kurczowo zaciśnięte na niczym — szczurki giną wściekłe.",
        "lore_id": "corpse_tunnel_runt",
        "salvage": {
            "meat_chunk":        (1, 2),
            "bone_fragments":    (0, 1),
            "tooth":             (0, 1),
            "fungal_fiber":      (0, 1),  # they nest w grzybie
        },
        "salvage_time_min": 3,
        "salvage_noise": 1,
        "edible":          True,
        "eat_hp_delta":    +2,
        "eat_status":      None,           # czysty szczurek
        "eat_audience_tag": "ate_vermin",
        "decay_minutes":   180,
        "smell_budget":    1,
    },

    "freezer_carver": {
        "name_pl": "ciało Rzeźnika z Zamrażarki",
        "lore":    "Wciąż w fartuchu, wciąż z nożem. Skóra zimna na długo "
                   "po tym, jak przestał oddychać. Pachnie jak sklepowa "
                   "chłodnia — czysto, klinicznie, źle.",
        "lore_id": "corpse_freezer_carver",
        "salvage": {
            "meat_chunk":      (1, 2),
            "leather_scraps":  (1, 2),   # fartuch
            "scrap_metal":     (0, 1),   # nóż
            "tooth":           (0, 1),
        },
        "salvage_time_min": 6,
        "salvage_noise": 3,
        "preferred_tool_tags": ["sharp"],
        "edible":          True,
        "eat_hp_delta":    -4,            # ludzkie, brudne, zimne
        "eat_status":      "sick",
        "eat_audience_tag": "ate_human",
        "cannibal_tag":    "cannibal",    # technically still humanoid
        "decay_minutes":   240,
        "smell_budget":    2,
        "desecration_tag": "desecrator",
        "trophy_drop":     ("cleaver_handle", 0.10),
    },

    "relay_warden": {
        "name_pl": "ciało Strażnika Przekaźnika",
        "lore":    "Hełm pęknięty. W pasie wciąż brzęczy elektryczna pałka. "
                   "Wciąż dobrze ubrany — Syndykat dba o image nawet wtedy, "
                   "kiedy płaci ci za jego śmierć.",
        "lore_id": "corpse_relay_warden",
        "salvage": {
            "scrap_metal":     (2, 3),    # armor
            "leather_scraps":  (1, 2),
            "battery_cell":    (1, 1),    # z pałki
            "wire_bundle":     (1, 2),
            "circuit_board":   (0, 1),
            "meat_chunk":      (1, 1),
            "crawler_badge":   (0, 1),    # mini-boss drop
        },
        "salvage_time_min": 10,
        "salvage_noise": 4,
        "preferred_tool_tags": ["sharp"],
        "edible":          False,
        "eat_audience_tag": "ate_human",
        "butcher_audience_tag": "looted_authority",
        "butcher_title_grants": ["pogromca_stra^znika"],  # Pillar 1 title hook
        "decay_minutes":   240,
        "smell_budget":    2,
        "trophy_drop":     ("warden_baton", 0.25),
    },

    # ── Sponsor responders (Prompt 20) ─────────────────────────────────
    "patrol_security": {
        "name_pl": "ciało ochroniarza",
        "lore":    "Standardowy mundur, standardowa kamizelka, standardowo "
                   "spóźniony refleks. W kieszeni pęka folia po batonie.",
        "lore_id": "corpse_patrol_security",
        "salvage": {
            "scrap_metal":     (1, 2),
            "cloth_strips":    (1, 2),
            "leather_scraps":  (1, 1),
            "meat_chunk":      (1, 1),
            "plastic_badge":   (0, 1),    # only if you butcher carefully
        },
        "salvage_time_min": 6,
        "salvage_noise": 3,
        "edible":          False,
        "eat_audience_tag": "ate_human",
        "decay_minutes":   240,
        "smell_budget":    2,
        "desecration_tag": "desecrator",
    },

    "silent_response": {
        "name_pl": "ciało agenta",
        "lore":    "Czarna kurtka, czarne buty, czarne wszystko. Tłumik "
                   "wciąż ciepły. Nie ma odznaki — to gość, którego nigdy "
                   "tu nie było.",
        "lore_id": "corpse_silent_response",
        "salvage": {
            "cloth_strips":    (1, 2),
            "leather_scraps":  (1, 1),
            "scrap_metal":     (1, 2),
            "meat_chunk":      (1, 1),
            "data_chip":       (0, 1),    # rzadko — coś, czego nie powinien mieć
        },
        "salvage_time_min": 7,
        "salvage_noise": 2,
        "edible":          False,
        "decay_minutes":   240,
        "smell_budget":    1,
        "desecration_tag": "desecrator",
    },

    "biotech_inspector": {
        "name_pl": "ciało inspektora NovaChem",
        "lore":    "Hełm zsunął się na bok. Notatki przesiąknięte krwią są "
                   "wciąż czytelne — pisał o tobie. Ostatni wpis: „subiekt "
                   "ujawnia niespodziewaną reaktywność.”",
        "lore_id": "corpse_biotech_inspector",
        "salvage": {
            "cloth_strips":    (2, 3),    # kombinezon hazmat = sporo szmaty
            "scrap_metal":     (1, 1),
            "sensor_module":   (0, 1),    # z hełmu
            "contract_scrap":  (1, 1),    # notatki
            "data_chip":       (0, 1),
        },
        "salvage_time_min": 8,
        "salvage_noise": 3,
        "edible":          False,
        "decay_minutes":   240,
        "smell_budget":    1,
        "butcher_audience_tag": "looted_novachem",
        "desecration_tag": "novachem_enemy",
    },

    # ── Prompt 18 sponsor hunters ────────────────────────────────────
    "agent_kontroli_jakosci": {
        "name_pl": "ciało Agenta Kontroli Jakości",
        "lore":    "Planszetka wypadła z dłoni. Ostatnia linia czytelna: "
                   "„subiekt nie współpracuje”. Fartuch jest dziwnie czysty.",
        "lore_id": "corpse_qc_agent",
        "salvage": {
            "cloth_strips":    (2, 2),
            "ichor_sample":    (0, 1),    # podejrzane, ale cenne
            "contract_scrap":  (1, 1),
            "sponsor_chip":    (0, 1),
        },
        "salvage_time_min": 7,
        "salvage_noise": 2,
        "edible":          False,
        "decay_minutes":   240,
        "smell_budget":    2,
        "butcher_audience_tag": "killed_novachem_agent",
        "desecration_tag": "novachem_enemy",
        "trophy_drop":     ("planszetka_inspektora", 0.20),
    },

    "egzekutor_ligi": {
        "name_pl": "ciało Egzekutora Ligi",
        "lore":    "Tarcza pęknięta, regulamin 4.2 wciąż na pięści. Numer "
                   "na napierśniku przekreślony krwią — Liga to docenia.",
        "lore_id": "corpse_league_executor",
        "salvage": {
            "scrap_metal":     (2, 3),
            "leather_scraps":  (1, 2),
            "audience_token":  (0, 1),    # arenowa pamiątka
            "meat_chunk":      (1, 1),
        },
        "salvage_time_min": 10,
        "salvage_noise": 4,
        "edible":          False,
        "decay_minutes":   240,
        "smell_budget":    2,
        "butcher_audience_tag": "killed_league",
        "butcher_title_grants": ["wrog_ligi"],
    },

    "windykator": {
        "name_pl": "ciało Windykatora",
        "lore":    "Garnitur idealny. Notes otwarty na twojej stronie. "
                   "Ostatni wpis: „wpisać do księgi długu z odsetkami.”",
        "lore_id": "corpse_collector",
        "salvage": {
            "cloth_strips":    (1, 2),
            "leather_scraps":  (1, 1),
            "contract_scrap":  (1, 2),
            "sponsor_chip":    (0, 1),
        },
        "salvage_time_min": 6,
        "salvage_noise": 1,
        "edible":          False,
        "decay_minutes":   240,
        "smell_budget":    1,
        "butcher_audience_tag": "killed_collector",
        "trophy_drop":     ("notes_windykatora", 0.30),
    },

    "redaktor_naczelny": {
        "name_pl": "ciało Redaktora Naczelnego",
        "lore":    "Tablet roztrzaskany, dyktafon wciąż nagrywa. „...nie "
                   "rozumiem, dlaczego oni tego nie widzą, to przecież "
                   "oczywiste, że...”",
        "lore_id": "corpse_chief_editor",
        "salvage": {
            "cloth_strips":    (1, 2),
            "data_chip":       (1, 1),
            "broken_screen":   (1, 1),
            "contract_scrap":  (1, 2),
        },
        "salvage_time_min": 5,
        "salvage_noise": 1,
        "edible":          False,
        "decay_minutes":   240,
        "smell_budget":    1,
        "butcher_audience_tag": "killed_editor",
        "desecration_tag": "ministerstwo_enemy",
    },
}


# ── Lookup API ──────────────────────────────────────────────────────────

def template_for(monster_key: str) -> Dict[str, Any]:
    """Resolve a corpse template by monster key. Unknown keys get the
    DEFAULT template (still butcherable, still inspectable, just generic).

    Returned dict merges DEFAULT with the override so every key in the
    schema is present — callers can read e.g. `tpl["decay_minutes"]`
    unconditionally.
    """
    out = dict(DEFAULT_TEMPLATE)
    override = CORPSE_TEMPLATES.get(monster_key)
    if override:
        out.update(override)
        # Deep-merge the salvage dict if both sides defined one. Override
        # wins entry-by-entry; default entries not mentioned in override
        # are dropped (per-monster authoring is explicit).
        if "salvage" in override:
            out["salvage"] = dict(override["salvage"])
    return out


def is_authored(monster_key: str) -> bool:
    """True iff a per-monster template exists (i.e. we won't fall back
    to DEFAULT). Useful in tests + content-validation pass."""
    return monster_key in CORPSE_TEMPLATES


def all_keys() -> Tuple[str, ...]:
    return tuple(CORPSE_TEMPLATES.keys())
