"""Floor objective and exit condition templates.

Each objective is selected ONCE per floor and decides what unlocks the exit.
Every objective must offer multiple `solution_paths` so the floor never has
a single forced solution. Solution paths reference engine-level effects
the player can produce via different actions (combat, social, environment,
secret routes, etc.).

Schema:
  fallback_title         -- Polish title shown in UI
  description            -- Polish one-line description
  solution_paths         -- list of solution-key strings
                            (each maps to a player-driven path)
  clue_chains            -- (optional) clue keys that hint at the objective
  rumor_hooks            -- (optional) rumor keys that point at solutions
  required_tags          -- (optional) tags the generator should ensure are
                            present somewhere on the floor (e.g. a clinic, a
                            terminal, a specific environmental object)
  minimum_solution_paths -- contract: floor generator must wire at least this
                            many of the paths into the actual map

Solution-path semantics (engine validators read these):
  "find_keycard_loot"    -- find a keycard in a lootable container or corpse
  "find_keycard_trade"   -- buy a keycard at a safehouse merchant
  "find_keycard_social"  -- get a keycard from a friendly NPC via dialogue
  "find_keycard_steal"   -- pickpocket / lockpick / hack to acquire one
  "secret_route"         -- bypass the locked exit via a hidden room
  "lure_boss_away"       -- pull the gatekeeper out of position
  "bribe_boss"           -- pay the gatekeeper off
  "environment_trap"     -- use a room hazard to disable the gatekeeper
  "faction_deal"         -- complete a faction favour for the exit code
  "force_manual_release" -- find the override panel and force-open
  "fight"                -- defeat the gatekeeper directly
"""

FLOOR_OBJECTIVE_TEMPLATES = {
    "find_keycard": {
        "fallback_title": "Znajdź kartę dostępu",
        "description": "Wyjście jest zamknięte. Karta krąży między crawlerami, trupami "
                       "i rzeczami, które lubią błyszczące przedmioty.",
        "solution_paths": [
            "find_keycard_loot",
            "find_keycard_trade",
            "find_keycard_social",
            "find_keycard_steal",
            "secret_route",
        ],
        "minimum_solution_paths": 3,
        "clue_chains": ["keycard_chain_start", "keycard_chain_locations",
                        "vent_shortcut_path", "merchant_password"],
        "rumor_hooks": ["keycard_seen_in_cafe", "crawler_has_keycard",
                        "blackmarket_keycard", "warden_keycard"],
        "tags": ["loot", "social", "objective", "tradeable"],
        "risks": ["theft_caught", "relationship_down", "alert_patrol"],
        "rewards": ["floor_exit", "trade_credits", "stealth_affinity"],
        "required_tags": ["objective_path"],
        "floor_min": 1, "floor_max": 4,
        "weight": 5,
    },

    "bypass_warden": {
        "fallback_title": "Obejdź strażnika zejścia",
        "description": "Strażnik pilnuje najkrótszej drogi. Loch rzadko wymaga "
                       "najkrótszej.",
        "solution_paths": [
            "fight",
            "secret_route",
            "lure_boss_away",
            "bribe_boss",
            "environment_trap",
            "faction_deal",
        ],
        "minimum_solution_paths": 3,
        "clue_chains": ["boss_weakness_noise", "warden_pattern",
                        "vent_shortcut_path"],
        "rumor_hooks": ["boss_likes_noise", "boss_bribe_route", "patrol_timer"],
        "tags": ["combat", "stealth", "objective", "boss"],
        "risks": ["combat_loss", "self_damage", "alert_patrol"],
        "rewards": ["floor_exit", "audience_high", "boss_loot"],
        "required_tags": ["boss", "secret"],
        "floor_min": 1, "floor_max": 5,
        "weight": 4,
    },

    "repair_elevator": {
        "fallback_title": "Napraw windę serwisową",
        "description": "Winda do zejścia działa technicznie, czyli nie działa w "
                       "sposób obiecujący.",
        "solution_paths": [
            "tech_check",
            "find_parts",
            "bribe_maintenance_npc",
            "force_manual_release",
            "hack_override",
        ],
        "minimum_solution_paths": 2,
        "clue_chains": ["acid_pool_metal", "warden_pattern", "vent_shortcut_path"],
        "rumor_hooks": ["patrol_timer", "wiring_corridor"],
        "tags": ["mechanical", "objective", "tech"],
        "risks": ["alert_patrol", "self_damage", "item_damage"],
        "rewards": ["floor_exit", "tech_affinity"],
        "required_tags": ["power", "cable", "control_panel"],
        "floor_min": 1, "floor_max": 3,
        "weight": 4,
    },

    "complete_faction_favour": {
        "fallback_title": "Zrób przysługę frakcji",
        "description": "Pewna grupa odblokuje wyjście, jeśli rozwiążesz za nich coś, "
                       "czego nie chcą rozwiązywać sami.",
        "solution_paths": [
            "faction_kill_target",
            "faction_steal_artifact",
            "faction_deliver_message",
            "faction_betray_them_back",
        ],
        "minimum_solution_paths": 2,
        "clue_chains": ["merchant_password", "warden_pattern", "vent_shortcut_path"],
        "rumor_hooks": ["wounded_brawler_trade", "loot_goblin_betrays"],
        "tags": ["social", "objective", "faction"],
        "risks": ["relationship_down", "betrayal", "audience_swing"],
        "rewards": ["floor_exit", "faction_rep", "social_affinity"],
        "required_tags": ["faction"],
        "floor_min": 1, "floor_max": 5,
        "weight": 3,
    },

    "broadcast_stunt": {
        "fallback_title": "Zrób coś, co wygra przerywnik reklamowy",
        "description": "Sponsorzy odblokowują wyjście, jeśli twoje audytorium "
                       "podskoczy odpowiednio wysoko.",
        "solution_paths": [
            "audience_kill_creative",
            "audience_perform_stunt",
            "audience_betrayal_event",
            "audience_environment_kill",
        ],
        "minimum_solution_paths": 2,
        "clue_chains": ["acid_pool_metal", "boss_weakness_noise"],
        "rumor_hooks": ["env_class_hint", "social_class_hint"],
        "tags": ["sponsor", "audience", "objective"],
        "risks": ["audience_swing", "self_damage"],
        "rewards": ["floor_exit", "audience_high", "showmanship_affinity"],
        "required_tags": ["sponsor", "audience", "environment"],
        "floor_min": 1, "floor_max": 5,
        "weight": 3,
    },
}


def get_objective(key: str):
    return FLOOR_OBJECTIVE_TEMPLATES.get(key)


def objectives_with_path(path_key: str):
    return [k for k, v in FLOOR_OBJECTIVE_TEMPLATES.items()
            if path_key in v.get("solution_paths", [])]
