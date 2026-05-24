"""Fail-forward narrative + effect templates (context-driven).

Each template is a dict:
  key            -- stable ASCII id
  category       -- mechanical|social|stealth|environmental|safehouse|combat_escape
  level          -- partial|failure|critical_failure
  text           -- Polish narrative line
  requires_any   -- list of tags; AT LEAST ONE must match the action context
  requires_all   -- list of tags; ALL must match the action context
  forbids_any    -- list of tags; NONE of these may match
  effects        -- list of effect dicts consumed by consequences.apply()

Context dict (built by resolution.py from world/room/entity/intent):
  {
    "room_tags":            [...],   # room.sensory_tags + actual_type + safehouse
    "entity_tags":          [...],   # tags of targeted entity if any
    "entity_types":         [...],   # entity_types of visible entities
    "encounter_type":       "...",   # room.encounter_key if any
    "safehouse_subtype":    "...",
    "noise_level":          int,
    "danger_level":         int,
    "available_exits":      int,
    "visible_crawler":      bool,
    "visible_sponsor_cam":  bool,
    "floor_objective":      "...",
    "affordance_key":       "...",
    "intent_category":      "...",   # mechanical/social/stealth/...
    "tools":                [...],   # tags of player's inventory items
  }

A template matches when:
  - level matches
  - context fulfils requires_any (>=1 tag) OR requires_any is empty
  - context fulfils requires_all (all tags present) OR requires_all is empty
  - no forbids_any tag matches

If no template matches, the picker returns None and resolution.py falls
back to a generic line ("Coś pika..."), which is also in the pool below
as a tag-less fallback.
"""

# ── 30 fail-forward templates (failure + critical_failure) ───────────────────

FAIL_TEMPLATES = [
    # ── MECHANICAL (5) ──────────────────────────────────────────────────────
    {
        "key": "mech_sparks_alert",
        "category": "mechanical", "level": "failure",
        "text": "Coś iskrzy. Coś syczy. Coś alarmuje na korytarzu obok.",
        "requires_any": ["mechanical", "electric", "wire", "terminal"],
        "effects": [
            {"type": "add_noise", "amount": 3},
            {"type": "trigger_alarm", "amount": 1},
        ],
    },
    {
        "key": "mech_jam",
        "category": "mechanical", "level": "failure",
        "text": "Mechanizm zacina się w połowie obrotu. Coś trzyma, ale nie tak, jak chciałeś.",
        "requires_any": ["mechanical", "machine", "container"],
        "effects": [
            {"type": "add_noise", "amount": 1},
        ],
    },
    {
        "key": "mech_short_circuit",
        "category": "mechanical", "level": "critical_failure",
        "text": "Iskra trafia w mokrą podłogę. Świetlówki gasną na trzy sekundy. Ktoś krzyczy z sąsiedniego pokoju.",
        "requires_any": ["mechanical", "electric"],
        "effects": [
            {"type": "damage_self", "amount": 2},
            {"type": "add_noise", "amount": 4},
            {"type": "trigger_alarm", "amount": 1},
        ],
    },
    {
        "key": "mech_broken_tool",
        "category": "mechanical", "level": "failure",
        "text": "Twoje narzędzie protestuje ostatnim trzaskiem. Nie znikło, ale już nie jest sobą.",
        "requires_any": ["mechanical"],
        "forbids_any": [],
        "effects": [
            {"type": "item_damage", "tag": "tool"},
        ],
    },
    {
        "key": "mech_terminal_lockout",
        "category": "mechanical", "level": "critical_failure",
        "text": "Terminal wyświetla DOSTĘP ZABLOKOWANY na pięć minut. Sponsor odnotowuje twoją wytrwałość.",
        "requires_any": ["terminal", "electronic"],
        "effects": [
            {"type": "add_audience", "amount": -2},
            {"type": "add_noise", "amount": 2},
            {"type": "trigger_alarm", "amount": 1},
        ],
    },

    # ── SOCIAL (5) ──────────────────────────────────────────────────────────
    {
        "key": "social_offense",
        "category": "social", "level": "failure",
        "text": "Twoje słowa lądują źle. Druga strona zapamiętuje minę bardziej niż treść.",
        "requires_any": ["crawler", "npc", "social"],
        "effects": [
            {"type": "change_relationship", "amount": -1},
            {"type": "add_audience", "amount": 1},
        ],
    },
    {
        "key": "social_audience_facepalm",
        "category": "social", "level": "failure",
        "text": "Widownia milczy w sposób, który mówi bardzo dużo.",
        "requires_any": ["social", "sponsor_ads", "audience"],
        "effects": [
            {"type": "add_audience", "amount": -2},
        ],
    },
    {
        "key": "social_burned_bridge",
        "category": "social", "level": "critical_failure",
        "text": "Zamiast pomóc, nazywasz go po imieniu i przez chwilę myśli, że wiesz, co znaczy. Wie, że nie wiesz.",
        "requires_any": ["crawler", "npc"],
        "effects": [
            {"type": "change_relationship", "amount": -3},
            {"type": "add_audience", "amount": 1},
        ],
    },
    {
        "key": "social_overheard",
        "category": "social", "level": "failure",
        "text": "Ktoś z boku słyszał wszystko. Patrzy na ciebie tak, jakby był świadkiem w przyszłym procesie.",
        "requires_any": ["social", "safehouse", "crawler"],
        "effects": [
            {"type": "add_noise", "amount": 1},
            {"type": "gain_rumor", "category": "false_or_biased"},
        ],
    },
    {
        "key": "social_sponsor_disapproval",
        "category": "social", "level": "critical_failure",
        "text": "Sponsor wyświetla ci na suficie krótką notatkę: REKLAMA NIE BĘDZIE PRZEDŁUŻONA.",
        "requires_any": ["sponsor", "social"],
        "forbids_any": ["audience_high"],
        "effects": [
            {"type": "add_audience", "amount": -4},
        ],
    },

    # ── STEALTH (5) ─────────────────────────────────────────────────────────
    {
        "key": "stealth_step_loud",
        "category": "stealth", "level": "failure",
        "text": "Coś chrupie pod stopą. Cisza, którą stworzyłeś, wraca jak echo zdrady.",
        "requires_any": ["stealth", "dark", "narrow", "damp"],
        "effects": [
            {"type": "add_noise", "amount": 3},
        ],
    },
    {
        "key": "stealth_spotted",
        "category": "stealth", "level": "failure",
        "text": "Spojrzenie nad ramieniem. Twoje. W jego oczach. Już za późno.",
        "requires_any": ["stealth", "crawler", "monster"],
        "effects": [
            {"type": "add_noise", "amount": 2},
            {"type": "change_relationship", "amount": -1},
        ],
    },
    {
        "key": "stealth_lost_item",
        "category": "stealth", "level": "failure",
        "text": "Coś wypada ci z kieszeni i toczy się w nieoptymalną stronę.",
        "requires_any": ["stealth"],
        "effects": [
            {"type": "item_damage", "tag": "*"},
            {"type": "add_noise", "amount": 1},
        ],
    },
    {
        "key": "stealth_alarm_triggered",
        "category": "stealth", "level": "critical_failure",
        "text": "Czujnik mruga, mruga szybciej, krzyczy. Patrol już idzie.",
        "requires_any": ["mechanical", "electric", "sponsor"],
        "effects": [
            {"type": "trigger_alarm", "amount": 2},
            {"type": "alert_patrol"},
        ],
    },
    {
        "key": "stealth_caught_in_dark",
        "category": "stealth", "level": "failure",
        "text": "W ciemności kogoś nie widzisz, ale ktoś widzi ciebie aż za dobrze.",
        "requires_any": ["dark"],
        "effects": [
            {"type": "damage_self", "amount": 1},
            {"type": "add_noise", "amount": 1},
        ],
    },

    # ── ENVIRONMENTAL (5) ───────────────────────────────────────────────────
    {
        "key": "env_acid_splash",
        "category": "environmental", "level": "partial",
        "text": "Coś pryska. Kropla kwasu zjada twój pasek. Pasek wnosi pretensje.",
        "requires_any": ["acid", "liquid", "lab"],
        "effects": [
            {"type": "item_damage", "tag": "*"},
            {"type": "damage_self", "amount": 1},
        ],
    },
    {
        "key": "env_gas_choke",
        "category": "environmental", "level": "failure",
        "text": "Wciągasz coś, co nie chciało być wciągnięte. Świat na moment się przekrzywia.",
        "requires_any": ["gas", "chem"],
        "effects": [
            {"type": "damage_self", "amount": 2},
            {"type": "add_noise", "amount": 0},
        ],
    },
    {
        "key": "env_collapse",
        "category": "environmental", "level": "critical_failure",
        "text": "Coś wali się z hukiem. Wyjście, które miałeś, teraz nie ma.",
        "requires_any": ["heavy", "structural", "machine"],
        "effects": [
            {"type": "block_route"},
            {"type": "add_noise", "amount": 4},
        ],
    },
    {
        "key": "env_spark_blow",
        "category": "environmental", "level": "critical_failure",
        "text": "Iskra plus gaz to nadal iskra plus gaz. Sufit traci kawałek.",
        "requires_any": ["gas", "flammable"],
        "effects": [
            {"type": "damage_self", "amount": 4},
            {"type": "add_noise", "amount": 5},
            {"type": "block_route"},
        ],
    },
    {
        "key": "env_slip",
        "category": "environmental", "level": "failure",
        "text": "Mokro. Płytko. Krótko. Spadasz, jakbyś to ćwiczył.",
        "requires_any": ["water", "liquid", "damp"],
        "effects": [
            {"type": "damage_self", "amount": 1},
            {"type": "add_noise", "amount": 1},
        ],
    },

    # ── SAFEHOUSE (5) ───────────────────────────────────────────────────────
    {
        "key": "safe_kicked_out",
        "category": "safehouse", "level": "critical_failure",
        "text": "Obsługa prosi cię o opuszczenie lokalu. Bardzo grzecznie. Bardzo definitywnie.",
        "requires_any": ["safehouse"],
        "effects": [
            {"type": "safehouse_consequence", "consequence": "kicked_out"},
            {"type": "add_audience", "amount": 1},
        ],
    },
    {
        "key": "safe_price_marked_up",
        "category": "safehouse", "level": "failure",
        "text": "Cennik nie zmienia się oficjalnie. Nieoficjalnie — tak.",
        "requires_any": ["safehouse"],
        "effects": [
            {"type": "safehouse_consequence", "consequence": "prices_up"},
        ],
    },
    {
        "key": "safe_rumor_distorted",
        "category": "safehouse", "level": "failure",
        "text": "Słyszysz plotkę, ale brzmi, jakby ktoś ją przepuścił przez pralkę.",
        "requires_any": ["safehouse"],
        "effects": [
            {"type": "gain_rumor", "category": "false_or_biased"},
        ],
    },
    {
        "key": "safe_barista_silent",
        "category": "safehouse", "level": "failure",
        "text": "Barista patrzy w bok. Nie ma czasu. Nigdy więcej dla ciebie.",
        "requires_any": ["safehouse", "cafe"],
        "effects": [
            {"type": "change_relationship", "amount": -1},
            {"type": "safehouse_consequence", "consequence": "service_denied"},
        ],
    },
    {
        "key": "safe_brawl_started",
        "category": "safehouse", "level": "critical_failure",
        "text": "Zaczynasz coś, czego skończyć nie wolno w safehouse. Reszta klienteli wstaje synchronicznie.",
        "requires_any": ["safehouse", "crowded"],
        "effects": [
            {"type": "safehouse_consequence", "consequence": "kicked_out"},
            {"type": "damage_self", "amount": 3},
            {"type": "add_audience", "amount": 3},
        ],
    },

    # ── COMBAT / ESCAPE (5) ─────────────────────────────────────────────────
    {
        "key": "combat_drop_weapon",
        "category": "combat_escape", "level": "failure",
        "text": "Broń wypada z ręki w najgorszym możliwym momencie. Jest jeden lepszy: nie wypaść.",
        "requires_any": ["combat", "monster", "crawler"],
        "effects": [
            {"type": "item_damage", "tag": "weapon"},
        ],
    },
    {
        "key": "combat_clipped",
        "category": "combat_escape", "level": "partial",
        "text": "Trafiasz, ale przy okazji obrywasz. Wymiana, ale na niekorzyść.",
        "requires_any": ["combat", "monster"],
        "effects": [
            {"type": "damage_self", "amount": 2},
        ],
    },
    {
        "key": "combat_route_blocked",
        "category": "combat_escape", "level": "critical_failure",
        "text": "Coś przewraca regał między tobą a wyjściem. Nie zdążysz tego obejść w tej rundzie.",
        "requires_any": ["combat", "machine", "heavy"],
        "effects": [
            {"type": "block_route"},
            {"type": "add_noise", "amount": 3},
        ],
    },
    {
        "key": "escape_clumsy",
        "category": "combat_escape", "level": "failure",
        "text": "Uciekasz tak, że widownia układa choreografię do twojego upadku.",
        "requires_any": ["combat", "audience", "sponsor_ads"],
        "effects": [
            {"type": "damage_self", "amount": 1},
            {"type": "add_audience", "amount": 2},
        ],
    },
    {
        "key": "escape_betrayed",
        "category": "combat_escape", "level": "critical_failure",
        "text": "Crawler, na którego liczyłeś, robi krok w tył akurat wtedy, gdy ty robisz krok w przód.",
        "requires_any": ["crawler", "combat"],
        "effects": [
            {"type": "damage_self", "amount": 3},
            {"type": "change_relationship", "amount": -2},
        ],
    },

    # ── Tag-less fallbacks (always eligible) ─────────────────────────────────
    {
        "key": "generic_no_effect",
        "category": "general", "level": "failure",
        "text": "Nie działa. Przez sekundę wszyscy obecni solidarnie udają, że nie widzieli.",
        "effects": [],
    },
    {
        "key": "generic_alarm",
        "category": "general", "level": "failure",
        "text": "Coś pika. Potem pika szybciej. To rzadko jest etap sukcesu.",
        "effects": [
            {"type": "trigger_alarm", "amount": 1},
        ],
    },
    {
        "key": "generic_painful",
        "category": "general", "level": "critical_failure",
        "text": "Przez krótką chwilę jesteś jedyną osobą w pokoju zaskoczoną tym, jak głupi był ten pomysł.",
        "effects": [
            {"type": "damage_self", "amount": 2},
        ],
    },
    {
        "key": "generic_sponsor_facepalm",
        "category": "general", "level": "critical_failure",
        "text": "Korporacyjny alarm brzmi jak kasa fiskalna w piekle.",
        "effects": [
            {"type": "trigger_alarm", "amount": 1},
            {"type": "add_audience", "amount": -1},
        ],
    },
]


# ── 20 partial-success templates ─────────────────────────────────────────────

PARTIAL_TEMPLATES = [
    # Mechanical
    {
        "key": "p_mech_works_loud",
        "category": "mechanical", "level": "partial",
        "text": "Udaje się, ale dźwięk niesie się korytarzem jak zaproszenie dla rzeczy bez kalendarza.",
        "requires_any": ["mechanical", "electric"],
        "effects": [{"type": "add_noise", "amount": 3}],
    },
    {
        "key": "p_mech_slow",
        "category": "mechanical", "level": "partial",
        "text": "Robisz to, ale zajmuje dłużej, niż rozsądek obiecywał.",
        "requires_any": ["mechanical"],
        "effects": [],
    },
    {
        "key": "p_mech_item_strain",
        "category": "mechanical", "level": "partial",
        "text": "Działa, ale przedmiot protestuje ostatnim, niepokojąco drogim trzaskiem.",
        "requires_any": ["mechanical"],
        "effects": [{"type": "item_damage", "tag": "tool"}],
    },
    # Social
    {
        "key": "p_social_grudging_yes",
        "category": "social", "level": "partial",
        "text": "Zgadza się, ale tak, jakby ktoś go obciążył kontraktem na przyszłość.",
        "requires_any": ["crawler", "npc"],
        "effects": [{"type": "change_relationship", "amount": 1},
                    {"type": "add_audience", "amount": 1}],
    },
    {
        "key": "p_social_split",
        "category": "social", "level": "partial",
        "text": "Część obecnych ci wierzy. Część czeka, jak skończysz.",
        "requires_any": ["social", "crowded", "safehouse"],
        "effects": [{"type": "add_audience", "amount": 1}],
    },
    # Stealth
    {
        "key": "p_stealth_pass_louder",
        "category": "stealth", "level": "partial",
        "text": "Przemykasz się, ale ktoś po drugiej stronie krótko podniesie głowę i wróci do swojego.",
        "requires_any": ["stealth", "dark", "damp"],
        "effects": [{"type": "add_noise", "amount": 1}],
    },
    {
        "key": "p_stealth_seen_briefly",
        "category": "stealth", "level": "partial",
        "text": "Widzą cię przez ćwierć sekundy. Tyle, ile trwa decyzja: jeszcze nie.",
        "requires_any": ["stealth", "crawler", "monster"],
        "effects": [{"type": "change_relationship", "amount": -1}],
    },
    # Environmental
    {
        "key": "p_env_splash_safe",
        "category": "environmental", "level": "partial",
        "text": "Plusk. Twoje buty już nigdy nie będą takie same, ale ty tak.",
        "requires_any": ["water", "liquid"],
        "effects": [{"type": "add_noise", "amount": 1}],
    },
    {
        "key": "p_env_smoke_useful",
        "category": "environmental", "level": "partial",
        "text": "Dym wypełnia korytarz. Wykorzystujesz to. Twoja widownia też.",
        "requires_any": ["smoke", "flammable", "gas"],
        "effects": [{"type": "add_audience", "amount": 2}],
    },
    {
        "key": "p_env_drop_useful",
        "category": "environmental", "level": "partial",
        "text": "Spadasz, ale wpół drogi łapiesz coś, czego inni jeszcze nie widzieli.",
        "requires_any": ["high", "heavy"],
        "effects": [{"type": "reveal_clue"}],
    },
    # Safehouse
    {
        "key": "p_safe_service_costs_more",
        "category": "safehouse", "level": "partial",
        "text": "Otrzymujesz, czego chciałeś, ale cennik dyskretnie się przegrupowuje.",
        "requires_any": ["safehouse"],
        "effects": [{"type": "safehouse_consequence", "consequence": "prices_up"}],
    },
    {
        "key": "p_safe_rumor_traded",
        "category": "safehouse", "level": "partial",
        "text": "Dowiadujesz się czegoś. W zamian zostawiasz po sobie ślad, który ktoś sprzeda dalej.",
        "requires_any": ["safehouse", "cafe", "bathroom", "lounge"],
        "effects": [{"type": "gain_rumor"},
                    {"type": "change_relationship", "amount": -1}],
    },
    # Combat/escape
    {
        "key": "p_combat_disable_briefly",
        "category": "combat_escape", "level": "partial",
        "text": "Trafiasz w coś krytycznego. Tylko nie po obu stronach.",
        "requires_any": ["combat", "monster"],
        "effects": [{"type": "add_audience", "amount": 1}],
    },
    {
        "key": "p_combat_escape_with_cost",
        "category": "combat_escape", "level": "partial",
        "text": "Uciekasz, ale jedna rzecz zostaje. Twoja albo czyjaś.",
        "requires_any": ["combat", "crawler"],
        "effects": [{"type": "item_damage", "tag": "*"}],
    },
    # Clue / objective
    {
        "key": "p_clue_partial",
        "category": "general", "level": "partial",
        "text": "Zauważasz coś, czego nie szukałeś. Może się przyda. Może wpadnie z hukiem.",
        "requires_any": ["lore", "loot", "graffiti", "terminal"],
        "effects": [{"type": "reveal_clue"}],
    },
    {
        "key": "p_audience_loves_it",
        "category": "general", "level": "partial",
        "text": "Sponsorzy notują. Algorytm cię polubi, jak skończysz.",
        "requires_any": ["sponsor", "sponsor_ads", "audience"],
        "effects": [{"type": "add_audience", "amount": 4}],
    },
    {
        "key": "p_class_pivot",
        "category": "general", "level": "partial",
        "text": "Twoje zachowanie zaczyna trafiać do innego profilu zawodnika. Algorytm sobie szepcze.",
        "requires_any": ["environment", "stealth", "social"],
        "effects": [{"type": "class_affinity_shift", "kind": "environment", "amount": 1}],
    },
    {
        "key": "p_path_unblocked",
        "category": "general", "level": "partial",
        "text": "Coś, co było zamknięte, klika cicho. Zamknięcie to nie zawsze koniec.",
        "requires_any": ["mechanical", "terminal", "secret"],
        "effects": [{"type": "unblock_route"}],
    },
    {
        "key": "p_generic_works",
        "category": "general", "level": "partial",
        "text": "Częściowy sukces. Reszta dzieje się obok ciebie i jest tańsza.",
        "effects": [],
    },
    {
        "key": "p_generic_pricey",
        "category": "general", "level": "partial",
        "text": "Sukces kosztuje cię kawałek sprzętu i trochę wiary w gwarancje.",
        "effects": [{"type": "item_damage", "tag": "*"}],
    },
]


def _matches(template: dict, context: dict) -> bool:
    tags = set()
    for k in ("room_tags", "entity_tags", "entity_types"):
        tags.update(context.get(k, []) or [])
    if context.get("safehouse_subtype"):
        tags.add("safehouse"); tags.add(context["safehouse_subtype"])
    if context.get("intent_category"):
        tags.add(context["intent_category"])
    if context.get("visible_sponsor_cam"):
        tags.add("sponsor"); tags.add("sponsor_ads"); tags.add("audience")
    if context.get("visible_crawler"):
        tags.add("crawler")

    req_any = template.get("requires_any") or []
    req_all = template.get("requires_all") or []
    forbid = template.get("forbids_any") or []

    if forbid and any(t in tags for t in forbid):
        return False
    if req_all and not all(t in tags for t in req_all):
        return False
    if req_any and not any(t in tags for t in req_any):
        return False
    return True


def pick_outcome(level: str, context: dict) -> "dict | None":
    """Pick a template matching the given level and context.

    Lookup order: exact level match with all tags satisfied -> tagless
    fallback (template with no requires_any). Returns None if nothing fits.
    """
    import random
    pool = PARTIAL_TEMPLATES if level == "partial" else FAIL_TEMPLATES
    candidates = [t for t in pool if t.get("level") == level and _matches(t, context)]
    if not candidates:
        # Allow tagless general-category templates for the same level
        candidates = [t for t in pool
                      if t.get("level") == level and not t.get("requires_any")]
    if not candidates:
        return None
    return random.choice(candidates)
