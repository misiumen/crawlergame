"""Problem-solving item templates for Dungeon Kraulem.

Defaults applied to every entry at lookup time (via get_item) for fields
not explicitly set in the dict:
  weight     = 1     (selection weight in loot tables)
  floor_min  = 1
  floor_max  = 5
  risks      = []    (what can go wrong if mishandled)
  rewards    = ["utility"]
"""

ITEM_DEFAULTS = {
    "weight": 1, "floor_min": 1, "floor_max": 5,
    "risks": [], "rewards": ["utility"],
}


def get_item(key: str):
    proto = ITEM_TEMPLATES.get(key)
    if proto is None:
        return None
    merged = dict(ITEM_DEFAULTS)
    merged.update(proto)
    merged["key"] = key
    return merged


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
    },
    # Prompt 12: previously-missing starter items. Without Polish entries
    # here `items.make_item()` falls through to `key.replace("_"," ")` and
    # the player sees raw English keys ("flashlight", "plastic badge", ...).
    "flashlight": {
        "type": "tool",
        "tags": ["light", "tool", "electronic"],
        "fallback_name": "latarka",
        "fallback_description": "Bateria zmęczona, plastik porysowany, ale rzuca snop światła wystarczający, żeby zobaczyć, co cię zaraz ugryzie.",
        "affordances": ["inspect", "use", "loot"],
        "value": 4,
    },
    "plastic_badge": {
        "type": "tool",
        "tags": ["badge", "disguise", "plastic"],
        "fallback_name": "plastikowa plakietka",
        "fallback_description": "Identyfikator z napisem, którego nikt nigdy nie sprawdzał. Działa na ludzi, którzy też nie chcą sprawdzać.",
        "affordances": ["inspect", "use", "loot"],
        "value": 2,
    },
    "dirty_bandage": {
        "type": "medical",
        "tags": ["medical", "consumable", "cloth"],
        "fallback_name": "brudny bandaż",
        "fallback_description": "Pomoże, jeśli pomoc nie miała być stuprocentowa. Lepsze to niż otwarta rana.",
        "affordances": ["inspect", "use", "loot"],
        "value": 3,
    },
    "snack_bar": {
        "type": "consumable",
        "tags": ["food", "consumable"],
        "fallback_name": "baton energetyczny",
        "fallback_description": "Smak: kompromis. Skład: lista pozwów zbiorowych. Kalorie: wystarczająco.",
        "affordances": ["inspect", "use", "loot"],
        "value": 2,
    },
    "credits_pile": {
        "type": "loot",
        "tags": ["currency", "loot"],
        "fallback_name": "garść kredytów",
        "fallback_description": "Pomięte banknoty + parę monet, ściągnięte gumką. Niczyje, dopóki ktoś nie zacznie się dopytywać.",
        "affordances": ["inspect", "pick_up", "loot"],
        "value": 0,
    },
    # P29.59 — klucze poprawne PL ale bez diakrytyk → display brakowało
    # akcentów. Dorzucamy fallback_name z pełnymi polskimi znakami.
    "amulet_szczescia": {
        "type": "trinket",
        "tags": ["amulet", "charm"],
        "fallback_name": "amulet szczęścia",
        "fallback_description": "Zawieszka z czterolistnej koniczyny zalanej żywicą. Sponsor twierdzi, że działa. Statystyki nic nie potwierdzają.",
        "affordances": ["inspect", "loot", "use"],
        "value": 2,
    },
    "maska_filtrujaca": {
        "type": "wearable",
        "tags": ["slot:head", "filter", "trenches"],
        "fallback_name": "maska filtrująca",
        "fallback_description": "Wojskowy filtr okopowy. Pasy ściskają policzki za mocno. Powietrze pachnie gumą i wczorajszą próbą.",
        "affordances": ["inspect", "loot", "wear"],
        "value": 4,
    },
    "broken_camera_lens": {
        "type": "oddity",
        "tags": ["junk", "glass", "sponsor"],
        "fallback_name": "stłuczona soczewka kamery",
        "fallback_description": "Soczewka z urwanej kamery sponsora. Można nią coś rozciąć — albo coś odbić w niewłaściwym momencie.",
        "affordances": ["inspect", "throw_at", "loot", "salvage"],
        "value": 1,
    },
    "coffee": {
        "type": "consumable",
        "tags": ["food", "consumable", "caffeine"],
        "fallback_name": "kawa",
        "fallback_description": "Trzy euro, jeden poziom prawdy, dwie godziny czujności. Cennik regulowany przez sponsora.",
        "affordances": ["inspect", "use", "loot"],
        "value": 2,
    },
    "suspicious_keycard": {
        "type": "tool",
        "tags": ["keycard", "key", "plastic"],
        "fallback_name": "podejrzana karta dostępu",
        "fallback_description": "Karta dostępu z nazwiskiem, którego nigdzie nie ma. Otwiera coś. Pytanie tylko gdzie i czyje.",
        "affordances": ["inspect", "use", "loot"],
        "value": 5,
    },
    "lockpick_set": {
        "type": "tool",
        "tags": ["lockpick", "tool"],
        "fallback_name": "zestaw wytrychów",
        "fallback_description": "Cztery zakrzywione druty w skórzanym etui. Jeśli wiesz co robisz — drzwi się boją. Jeśli nie — drzwi nie zauważą.",
        "affordances": ["inspect", "use", "loot"],
        "value": 7,
    },
    "improvised_lockpick": {
        "type": "tool",
        "tags": ["lockpick", "tool", "junk"],
        "fallback_name": "prowizoryczny wytrych",
        "fallback_description": "Spinka, kawałek puszki i resztki cierpliwości. Czasem działa. Czasem zostawia ci pamiątkę w zamku.",
        "affordances": ["inspect", "use", "loot"],
        "value": 2,
    },
}
