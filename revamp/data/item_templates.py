"""Problem-solving item templates for CRAWL PROTOCOL revamp."""

ITEM_TEMPLATES = {
    "cracked_mug": {
        "type": "tool",
        "tags": ["throwable", "ceramic", "distraction", "container"],
        "fallback_name": "pęknięty kubek",
        "fallback_description": "Kubek z logo sponsora. Pęknięty, brzydki i wciąż bardziej użyteczny niż większość regulaminu.",
        "affordances": ["throw_at", "fill", "trade_small", "distract"],
        "value": 1
    },
    "duct_tape": {
        "type": "tool",
        "tags": ["repair", "crafting", "binding", "insulation"],
        "fallback_name": "taśma naprawcza",
        "fallback_description": "Srebrna taśma. Uniwersalny język desperacji.",
        "affordances": ["repair", "craft", "bind", "insulate"],
        "value": 5
    },
    "dead_phone": {
        "type": "oddity",
        "tags": ["electronic", "throwable", "decoy", "battery_slot"],
        "fallback_name": "martwy telefon",
        "fallback_description": "Nie ma zasięgu, ale wciąż może posłużyć jako przynęta, lusterko albo bardzo smutny pocisk.",
        "affordances": ["throw_at", "reflect", "decoy", "salvage"],
        "value": 2
    },
    "cheap_knife": {
        "type": "weapon",
        "tags": ["sharp", "melee", "tool", "cut"],
        "fallback_name": "tani nóż",
        "fallback_description": "Ostrze z promocji, które wygląda, jakby samo bało się walki.",
        "damage": "1d4",
        "affordances": ["attack", "cut", "pry", "threaten"],
        "value": 6
    },
    "battery": {
        "type": "material",
        "tags": ["power", "electronic", "crafting", "trade"],
        "fallback_name": "bateria",
        "fallback_description": "Ma jeszcze trochę prądu i dużo potencjału procesowego w sądzie.",
        "affordances": ["power_device", "craft", "trade", "throw_at"],
        "value": 5
    }
}
