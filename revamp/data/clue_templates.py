"""Clue templates — partial information chains.

A clue is a small revelation that points the player toward the next step
without solving anything. Chains are explicit: clue A says where to find
clue B, clue B unlocks an objective path.

Schema per clue:
  key            -- stable ASCII id
  source         -- "rumor" | "terminal" | "graffiti" | "corpse_note" | "npc_dialogue" | "lore_fragment"
  text           -- Polish line shown to the player
  reveals        -- list of stable tags the player now "knows"
  unlocks_chain  -- (optional) key of the next clue this one points to
  enables_paths  -- (optional) list of objective_solution_path keys
                    that become available when this clue is known

Engine usage:
  - When emitted, the clue's `reveals` tags are added to a player-side
    "known_facts" set on Character (TBD; for now `Character.flags["known_clues"]`).
  - When picking an encounter resolution, the validator may consult the
    player's known_facts to widen `possible_resolutions`.

Clues compose with rumors — a rumor can be the *source* of a clue but
clues are stronger: their `reveals` tags are treated as factual by the
validator, even if the rumor that delivered them had `truth < 1.0`.

Defaults applied to every clue at lookup time (via get_clue) when the
field is missing:
  weight       = 1
  floor_min    = 1
  floor_max    = 5
  tags         = []
  risks        = []
  rewards      = ["partial_information"]
"""

CLUE_DEFAULTS = {
    "weight": 1, "floor_min": 1, "floor_max": 5,
    "tags": [], "risks": [], "rewards": ["partial_information"],
    "requires_clues": [],          # prerequisite clue keys (sequence support)
    "can_skip_sequence": False,    # if True, this clue is always revealable
}

CLUE_TEMPLATES = {
    # ── Keycard chain (for the find_keycard objective) ──────────────────────
    "keycard_chain_start": {
        "source": "rumor",
        "text": "Karta dostępu Strażnika krąży po piętrze. Trzy razy widziano ją "
                "w okolicy kafejki, raz w schowku serwisowym, raz pod ladą u handlarza.",
        "reveals": ["keycard_in_circulation"],
        "unlocks_chain": "keycard_chain_locations",
        "enables_paths": [],
    },
    "keycard_chain_locations": {
        "source": "graffiti",
        "text": "Na ścianie obok wentylatora wydrapane: 'Karta = czerwona z napisem "
                "KONTRAKTOR. Schowek za biurem albo Bezparagonu. Nie u ochroniarzy. "
                "Już nie.'",
        "reveals": ["keycard_in_maintenance", "keycard_in_blackmarket",
                    "keycard_color_red"],
        "enables_paths": ["loot_corpse", "black_market", "steal"],
        "requires_clues": ["keycard_chain_start"],
    },

    "warden_pattern": {
        "source": "terminal",
        "text": "Log dyżurów strażnika: '04:00-12:00 — relay. 12:00-20:00 — przerwa. "
                "20:00-04:00 — patrol korytarza A.' Aktualna godzina mruga.",
        "reveals": ["warden_schedule_known"],
        "enables_paths": ["bypass_during_break", "sneak_during_patrol"],
    },

    "boss_weakness_noise": {
        "source": "corpse_note",
        "text": "Na ciele crawlera notatka, jakby spisana na kolanie: 'Boss nie "
                "atakuje, gdy wszyscy krzyczą. Hałas mu się podoba. Ja krzyczałem.'",
        "reveals": ["boss_pacified_by_noise"],
        "enables_paths": ["lure_boss_away"],
    },

    "freezer_silent_kill": {
        "source": "npc_dialogue",
        "text": "Stary technik: 'Rzeźnik z Zamrażarki nie zaatakuje, jak nie usłyszy "
                "twojego oddechu. Wstrzymaj go. Albo nie wchodź.'",
        "reveals": ["carver_pacified_by_silence"],
        "enables_paths": ["sneak_past"],
    },

    "acid_pool_metal": {
        "source": "lore_fragment",
        "text": "Zaszyte w protokole bezpieczeństwa: 'Kwas reaguje z metalem trzykrotnie "
                "szybciej niż z tkanką. Stąd to nie jest zalecane jako broń, ALE...'",
        "reveals": ["acid_eats_metal"],
        "enables_paths": ["use_environment"],
    },

    "vent_shortcut_path": {
        "source": "graffiti",
        "text": "Wydrapane na lustrze w łazience: 'Krata w suficie prowadzi do biura. "
                "Biuro ma klucz do relay. Reszta — w twoich rękach.'",
        "reveals": ["vent_to_office", "office_has_keycard"],
        "enables_paths": ["secret_route"],
    },

    "merchant_password": {
        "source": "npc_dialogue",
        "text": "Barista, ściszonym głosem: 'Powiedz handlarzowi: «szyba boli». Wtedy "
                "pokaże ci to, czego oficjalnie nie ma.'",
        "reveals": ["blackmarket_password_known"],
        "enables_paths": ["black_market", "trade_info"],
    },
}


def all_clue_keys():
    return list(CLUE_TEMPLATES.keys())


def get_clue(key: str):
    """Return clue dict with CLUE_DEFAULTS layered in for missing fields."""
    c = CLUE_TEMPLATES.get(key)
    if c is None:
        return None
    merged = dict(CLUE_DEFAULTS)
    merged.update(c)
    # Ensure key always present
    merged["key"] = key
    return merged


def clues_unlocking_path(path_key: str):
    """Reverse-lookup: which clues enable the given solution path."""
    return [c for c in CLUE_TEMPLATES.values()
            if path_key in c.get("enables_paths", [])]
