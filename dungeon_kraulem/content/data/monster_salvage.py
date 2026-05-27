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

    # P29.0 — patrol_security / silent_response salvage tables REMOVED
    # along with their entity templates. No more dispatched responders
    # to leave corpses.

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

    # ═════════════════════════════════════════════════════════════════════
    # P29.1 — Floors 3-6 salvage tables. Materials map to standard
    # crafting tables (meat_chunk, bone_fragments, leather_scraps,
    # cloth_strips, scrap_metal, data_chip).
    # ═════════════════════════════════════════════════════════════════════

    # ── Piętro 3: ZOO ─────────────────────────────────────────────────────
    "mutant_szczur": {
        "name_pl": "ciało zmutowanego szczura",
        "lore":    "Trzy oczy patrzą w trzy strony jednocześnie. "
                   "Sponsor Czarnego Rynku ceni te ciała za organy.",
        "lore_id": "corpse_mutant_szczur",
        "salvage": {
            "meat_chunk":      (1, 2),
            "bone_fragments":  (1, 2),
            "tooth":           (0, 2),
        },
        "salvage_time_min": 4,
        "salvage_noise": 2,
        "edible":          True,
        "eat_hp_delta":    -2,   # mutant meat upsets the stomach
        "decay_minutes":   180,
        "smell_budget":    2,
    },
    "klatkowy_kot": {
        "name_pl": "ciało klatkowego kota",
        "lore":    "Mięso na pasie sprężyn. Pazury wciąż wysunięte.",
        "lore_id": "corpse_klatkowy_kot",
        "salvage": {
            "meat_chunk":      (1, 2),
            "leather_scraps":  (1, 2),
            "tooth":           (1, 2),
        },
        "salvage_time_min": 5,
        "salvage_noise": 2,
        "edible":          True,
        "eat_hp_delta":    3,
        "decay_minutes":   180,
        "smell_budget":    1,
    },
    "bekajacy_paw": {
        "name_pl": "ciało bekającego pawa",
        "lore":    "Wciąż wydaje z siebie dźwięk co kilka minut, nawet "
                   "martwe. Klatka piersiowa pełna mikrofonu.",
        "lore_id": "corpse_bekajacy_paw",
        "salvage": {
            "meat_chunk":      (1, 1),
            "feather_clump":   (1, 3),
            "scrap_metal":     (0, 1),
        },
        "salvage_time_min": 4,
        "salvage_noise": 3,   # the corpse keeps making noise
        "edible":          True,
        "eat_hp_delta":    1,
        "decay_minutes":   120,
        "smell_budget":    1,
    },
    "miniboss_alfa_szczur": {
        "name_pl": "ciało Alfa Szczurów",
        "lore":    "Krwawe kółka wokół oczu — kiedyś miała obrożę. Pod "
                   "skórą wciśnięty chip sponsorski.",
        "lore_id": "corpse_alfa_szczur",
        "salvage": {
            "meat_chunk":      (2, 3),
            "bone_fragments":  (2, 3),
            "tooth":           (2, 3),
            "data_chip":       (0, 1),    # sponsorski tracking chip
        },
        "salvage_time_min": 8,
        "salvage_noise": 3,
        "edible":          True,
        "eat_hp_delta":    -1,
        "butcher_audience_tag": "killed_miniboss_zoo",
        "decay_minutes":   240,
        "smell_budget":    2,
    },
    "boss_panicz_zoo": {
        "name_pl": "ciało Panicza Zoo",
        "lore":    "Headliner sezonu. Sierść w dwóch kolorach od reflektora. "
                   "Trofeum na każdej ścianie korporacji.",
        "lore_id": "corpse_boss_panicz_zoo",
        "salvage": {
            "meat_chunk":      (3, 5),
            "bone_fragments":  (3, 5),
            "leather_scraps":  (3, 5),
            "tooth":           (2, 4),
            "trophy_drop":     ("zoo_pelt", 1.0),
        },
        "salvage_time_min": 12,
        "salvage_noise": 4,
        "edible":          False,
        "butcher_audience_tag": "killed_boss_zoo",
        "decay_minutes":   480,
        "smell_budget":    3,
    },

    # ── Piętro 4: NEIGHBORHOOD ────────────────────────────────────────────
    "usmiechniety_sasiad": {
        "name_pl": "ciało sąsiada",
        "lore":    "Mundur firmowy 'Witamy w Sąsiedztwie' wciąż wisi "
                   "schludnie. Identyfikator 'OBYWATEL ROKU 11'.",
        "lore_id": "corpse_usmiechniety_sasiad",
        "salvage": {
            "cloth_strips":    (1, 2),
            "meat_chunk":      (1, 1),
            "scrap_metal":     (0, 1),
            "plastic_badge":   (0, 1),
        },
        "salvage_time_min": 5,
        "salvage_noise": 2,
        "edible":          False,
        "eat_audience_tag": "ate_human",
        "decay_minutes":   240,
        "smell_budget":    1,
        "desecration_tag": "ministerstwo_enemy",
    },
    "dzieciak_z_blokowiska": {
        "name_pl": "ciało dzieciaka",
        "lore":    "Czapeczka logo Ministerstwa wciąż na głowie. Kieszenie "
                   "ciężkie od cegieł.",
        "lore_id": "corpse_dzieciak",
        "salvage": {
            "cloth_strips":    (1, 2),
            "scrap_metal":     (1, 2),    # cegły = surowiec
            "meat_chunk":      (1, 1),
        },
        "salvage_time_min": 4,
        "salvage_noise": 2,
        "edible":          False,
        "eat_audience_tag": "ate_child",     # mocne audience consequence
        "decay_minutes":   240,
        "smell_budget":    1,
        "desecration_tag": "desecrator",     # Kanał 7 też zauważy
    },
    "kucharka_z_swietlicy": {
        "name_pl": "ciało kucharki",
        "lore":    "Fartuch w plamach, których nikt nie chce identyfikować. "
                   "Wałek wciąż w ręku.",
        "lore_id": "corpse_kucharka",
        "salvage": {
            "cloth_strips":    (2, 3),
            "meat_chunk":      (1, 1),
            "scrap_metal":     (0, 1),
        },
        "salvage_time_min": 5,
        "salvage_noise": 2,
        "edible":          False,
        "eat_audience_tag": "ate_human",
        "decay_minutes":   240,
        "smell_budget":    1,
        "desecration_tag": "ministerstwo_enemy",
    },
    "miniboss_oddzialowa": {
        "name_pl": "ciało Oddziałowej Osiedlowej",
        "lore":    "Pełen mundur z odznaką, pas z latarką, gwizdek na "
                   "szyi. Wciąż wisi etyk: 'Bezpieczeństwo i Porządek'.",
        "lore_id": "corpse_oddzialowa",
        "salvage": {
            "cloth_strips":    (2, 3),
            "leather_scraps":  (1, 2),
            "scrap_metal":     (1, 2),
            "plastic_badge":   (1, 1),
        },
        "salvage_time_min": 7,
        "salvage_noise": 2,
        "edible":          False,
        "butcher_audience_tag": "killed_miniboss_neighborhood",
        "decay_minutes":   300,
        "smell_budget":    2,
        "desecration_tag": "ministerstwo_enemy",
    },
    "boss_blok_parent": {
        "name_pl": "ciało Block Parenta",
        "lore":    "Pęk kluczy do każdych drzwi osiedla. Notatnik z "
                   "planami życiowymi cudzych dzieci. Pierścień rodzinny.",
        "lore_id": "corpse_blok_parent",
        "salvage": {
            "cloth_strips":    (2, 3),
            "scrap_metal":     (2, 3),
            "meat_chunk":      (1, 2),
            "data_chip":       (1, 1),
            "trophy_drop":     ("klucze_osiedlowe", 1.0),
        },
        "salvage_time_min": 12,
        "salvage_noise": 3,
        "edible":          False,
        "butcher_audience_tag": "killed_boss_neighborhood",
        "decay_minutes":   480,
        "smell_budget":    2,
        "desecration_tag": "ministerstwo_enemy",
    },

    # ── Piętro 5: MUSEUM ──────────────────────────────────────────────────
    "kostny_kurator": {
        "name_pl": "szkielet kuratora",
        "lore":    "Zsuszony i ożywiony żartem. Kości tylko częściowo "
                   "trzymają się siebie nawzajem.",
        "lore_id": "corpse_kostny_kurator",
        "salvage": {
            "bone_fragments":  (2, 4),
            "cloth_strips":    (1, 2),
            "scrap_metal":     (0, 1),
        },
        "salvage_time_min": 4,
        "salvage_noise": 1,
        "edible":          False,
        "decay_minutes":   600,    # kości się nie psują szybko
        "smell_budget":    0,
    },
    "duch_zwiedzajacego": {
        "name_pl": "rozpadające się ślady ducha",
        "lore":    "Półprzezroczyste resztki. Nie da się dotknąć, da się "
                   "spakować do termosu (jeśli masz odpowiedni termos).",
        "lore_id": "corpse_duch",
        "salvage": {
            "ectoplasm":       (1, 2),     # nowy material
            "data_chip":       (0, 1),     # 'pamięć ze świata przed'
        },
        "salvage_time_min": 6,
        "salvage_noise": 1,
        "edible":          False,
        "decay_minutes":   60,             # ulatnia się
        "smell_budget":    0,
    },
    "mechaniczny_strazak": {
        "name_pl": "wrak mechanicznego strażaka",
        "lore":    "Hydrant na nogach. Pomalowany czerwono, plamy rdzy "
                   "wokół spawów. Pojemnik wciąż pełny czegoś żrącego.",
        "lore_id": "corpse_mechaniczny_strazak",
        "salvage": {
            "scrap_metal":     (3, 5),
            "battery":         (1, 1),     # jako entity
            "pek_przewodow":   (1, 2),
        },
        "salvage_time_min": 7,
        "salvage_noise": 3,
        "edible":          False,
        "decay_minutes":   720,    # nie ulega rozkładowi
        "smell_budget":    1,
    },
    "miniboss_strazak_galerii": {
        "name_pl": "ciało Strażaka Galerii",
        "lore":    "Mundur galeryjny z naszywką naczelnika. Pierwsza "
                   "generacja pałki elektrycznej — antyk dla kolekcjonera.",
        "lore_id": "corpse_strazak_galerii",
        "salvage": {
            "scrap_metal":     (2, 3),
            "cloth_strips":    (1, 2),
            "meat_chunk":      (1, 1),
            "battery":         (1, 1),
            "trophy_drop":     ("zabytkowa_palka", 1.0),
        },
        "salvage_time_min": 8,
        "salvage_noise": 2,
        "edible":          False,
        "eat_audience_tag": "ate_human",
        "butcher_audience_tag": "killed_miniboss_museum",
        "decay_minutes":   300,
        "smell_budget":    2,
    },
    "boss_kurator_naczelny": {
        "name_pl": "ciało Kuratora Naczelnego",
        "lore":    "Sześciopalca dłoń. Monokl ze szkła, którego już nikt "
                   "nie produkuje. Pierścień z czaszką w środku.",
        "lore_id": "corpse_boss_kurator",
        "salvage": {
            "cloth_strips":    (2, 3),
            "scrap_metal":     (1, 2),
            "data_chip":       (1, 2),
            "bone_fragments":  (1, 2),
            "trophy_drop":     ("monokl_kuratora", 1.0),
        },
        "salvage_time_min": 12,
        "salvage_noise": 2,
        "edible":          False,
        "butcher_audience_tag": "killed_boss_museum",
        "decay_minutes":   480,
        "smell_budget":    2,
        "desecration_tag": "occult_meddler",
    },

    # ── Piętro 6: BAR ─────────────────────────────────────────────────────
    "pijany_crawler": {
        "name_pl": "ciało pijanego crawlera",
        "lore":    "Spóźniony bohater. Tatuaż sponsorski wyblakły. W "
                   "kieszeni wciąż butelka, nadal pełna.",
        "lore_id": "corpse_pijany_crawler",
        "salvage": {
            "cloth_strips":    (1, 2),
            "meat_chunk":      (1, 1),
            "scrap_metal":     (0, 1),
        },
        "salvage_time_min": 5,
        "salvage_noise": 2,
        "edible":          False,
        "eat_audience_tag": "ate_human",
        "decay_minutes":   240,
        "smell_budget":    2,
        "desecration_tag": "cannibal",   # killing a fellow crawler
    },
    "lokator_baru": {
        "name_pl": "ciało stałego bywalca",
        "lore":    "Pił tu od piętra trzeciego. Wiedział więcej niż "
                   "powinien. Teraz wie zero.",
        "lore_id": "corpse_lokator_baru",
        "salvage": {
            "cloth_strips":    (1, 2),
            "meat_chunk":      (1, 1),
            "data_chip":       (0, 1),   # zapisywał wszystko
        },
        "salvage_time_min": 5,
        "salvage_noise": 2,
        "edible":          False,
        "eat_audience_tag": "ate_human",
        "decay_minutes":   240,
        "smell_budget":    1,
        "desecration_tag": "cannibal",
    },
    "bramkarz": {
        "name_pl": "ciało bramkarza",
        "lore":    "Garnitur skrojony na zamówienie. Słuchawka wciąż "
                   "syczy w uchu. Ręce wielkości twojej głowy.",
        "lore_id": "corpse_bramkarz",
        "salvage": {
            "cloth_strips":    (2, 3),
            "leather_scraps":  (1, 2),
            "meat_chunk":      (2, 3),
            "scrap_metal":     (0, 1),
        },
        "salvage_time_min": 7,
        "salvage_noise": 2,
        "edible":          False,
        "eat_audience_tag": "ate_human",
        "decay_minutes":   300,
        "smell_budget":    2,
    },
    "miniboss_szef_baru": {
        "name_pl": "ciało Szefa Baru",
        "lore":    "Trzykrotny zwycięzca, wrócił do roboty. Rewolwer z "
                   "czasów, kiedy nie szanowano klientów.",
        "lore_id": "corpse_szef_baru",
        "salvage": {
            "cloth_strips":    (2, 3),
            "leather_scraps":  (1, 2),
            "meat_chunk":      (1, 2),
            "scrap_metal":     (1, 2),
            "trophy_drop":     ("stary_rewolwer", 0.6),
        },
        "salvage_time_min": 8,
        "salvage_noise": 2,
        "edible":          False,
        "eat_audience_tag": "ate_human",
        "butcher_audience_tag": "killed_miniboss_bar",
        "decay_minutes":   300,
        "smell_budget":    2,
        "desecration_tag": "cannibal",
    },
    "boss_showman": {
        "name_pl": "ciało Showmana",
        "lore":    "Smoking od krawca, którego już nie ma. Mikrofon "
                   "wciąż ciepły. Zęby zbyt regularne — wszystkie "
                   "wymienne.",
        "lore_id": "corpse_boss_showman",
        "salvage": {
            "cloth_strips":    (3, 4),
            "leather_scraps":  (1, 2),
            "data_chip":       (1, 2),
            "scrap_metal":     (1, 2),
            "trophy_drop":     ("mikrofon_showmana", 1.0),
        },
        "salvage_time_min": 12,
        "salvage_noise": 3,
        "edible":          False,
        "butcher_audience_tag": "killed_boss_bar",
        "decay_minutes":   480,
        "smell_budget":    2,
        "desecration_tag": "kanal_7_enemy",
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
