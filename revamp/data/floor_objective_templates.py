"""Floor objective and exit condition templates."""

FLOOR_OBJECTIVE_TEMPLATES = {
    "find_keycard": {
        "fallback_title": "Znajdź kartę dostępu",
        "description": "Wyjście jest zamknięte. Karta krąży między crawlerami, trupami i rzeczami, które lubią błyszczące przedmioty.",
        "solution_paths": ["trade", "steal", "loot_corpse", "help_crawler", "black_market"],
        "rumor_hooks": ["keycard_seen_in_cafe", "crawler_has_keycard"]
    },
    "repair_elevator": {
        "fallback_title": "Napraw windę serwisową",
        "description": "Winda do zejścia działa technicznie, czyli nie działa w sposób obiecujący.",
        "solution_paths": ["tech_check", "find_parts", "bribe_maintenance_npc", "force_manual_release"],
        "required_tags": ["power", "cable", "control_panel"]
    },
    "bypass_boss": {
        "fallback_title": "Obejdź strażnika zejścia",
        "description": "Boss pilnuje najkrótszej drogi. Loch rzadko wymaga najkrótszej.",
        "solution_paths": ["secret_route", "lure_boss_away", "environment_trap", "faction_deal", "fight"]
    }
}
