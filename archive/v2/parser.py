"""CRAWL PROTOCOL v2 - Offline free-text intent parser.

Maps player's typed text to structured game actions using keyword matching.
No internet or AI required — fully deterministic.
"""
import re
from typing import Optional, Dict, Any, List

# ── Intent taxonomy ────────────────────────────────────────────────────────────
# Each intent has: stat used, base DC, audience bonus, and description template.

INTENTS = {
    # Combat intents
    "attack":        {"stat": "STR", "dc": 10, "aud": 1,  "combat": True,  "label": "Attack"},
    "dodge":         {"stat": "DEX", "dc": 12, "aud": 0,  "combat": True,  "label": "Dodge"},
    "flee":          {"stat": "DEX", "dc": 13, "aud": 0,  "combat": True,  "label": "Flee"},
    "shove":         {"stat": "STR", "dc": 13, "aud": 2,  "combat": True,  "label": "Shove"},
    "disarm":        {"stat": "DEX", "dc": 14, "aud": 2,  "combat": True,  "label": "Disarm"},
    "grapple":       {"stat": "STR", "dc": 13, "aud": 2,  "combat": True,  "label": "Grapple"},
    "taunt":         {"stat": "CHA", "dc": 12, "aud": 3,  "combat": True,  "label": "Taunt"},
    "intimidate":    {"stat": "CHA", "dc": 13, "aud": 2,  "combat": True,  "label": "Intimidate"},
    "blind":         {"stat": "DEX", "dc": 14, "aud": 2,  "combat": True,  "label": "Blind enemy"},
    "trip":          {"stat": "DEX", "dc": 13, "aud": 2,  "combat": True,  "label": "Trip"},
    "throw":         {"stat": "STR", "dc": 12, "aud": 2,  "combat": True,  "label": "Throw object"},
    "charge":        {"stat": "STR", "dc": 11, "aud": 2,  "combat": True,  "label": "Charge"},
    "stab":          {"stat": "DEX", "dc": 11, "aud": 1,  "combat": True,  "label": "Stab"},
    "punch":         {"stat": "STR", "dc": 10, "aud": 1,  "combat": True,  "label": "Punch"},
    "kick":          {"stat": "STR", "dc": 10, "aud": 1,  "combat": True,  "label": "Kick"},
    "shoot":         {"stat": "DEX", "dc": 11, "aud": 1,  "combat": True,  "label": "Shoot"},
    "slash":         {"stat": "STR", "dc": 10, "aud": 1,  "combat": True,  "label": "Slash"},
    "use_ability":   {"stat": "INT", "dc": 10, "aud": 1,  "combat": True,  "label": "Use ability"},
    "use_item":      {"stat": "INT", "dc": 8,  "aud": 0,  "combat": True,  "label": "Use item"},
    "defend":        {"stat": "CON", "dc": 10, "aud": 0,  "combat": True,  "label": "Defend"},
    "inspect":       {"stat": "INT", "dc": 10, "aud": 0,  "combat": True,  "label": "Inspect enemy"},
    "distract":      {"stat": "CHA", "dc": 13, "aud": 3,  "combat": True,  "label": "Distract"},
    "environment":   {"stat": "INT", "dc": 14, "aud": 4,  "combat": True,  "label": "Use environment"},
    # Exploration intents
    "search":        {"stat": "WIS", "dc": 12, "aud": 1,  "combat": False, "label": "Search"},
    "pick_lock":     {"stat": "DEX", "dc": 15, "aud": 2,  "combat": False, "label": "Pick lock"},
    "disarm_trap":   {"stat": "DEX", "dc": 14, "aud": 2,  "combat": False, "label": "Disarm trap"},
    "detect_trap":   {"stat": "WIS", "dc": 12, "aud": 1,  "combat": False, "label": "Detect trap"},
    "talk":          {"stat": "CHA", "dc": 12, "aud": 1,  "combat": False, "label": "Talk"},
    "haggle":        {"stat": "CHA", "dc": 13, "aud": 0,  "combat": False, "label": "Haggle"},
    "examine":       {"stat": "INT", "dc": 10, "aud": 0,  "combat": False, "label": "Examine"},
    "climb":         {"stat": "STR", "dc": 12, "aud": 1,  "combat": False, "label": "Climb"},
    "sneak":         {"stat": "DEX", "dc": 13, "aud": 1,  "combat": False, "label": "Sneak"},
    "break":         {"stat": "STR", "dc": 13, "aud": 1,  "combat": False, "label": "Break"},
    "hack":          {"stat": "INT", "dc": 15, "aud": 3,  "combat": False, "label": "Hack"},
    "craft":         {"stat": "INT", "dc": 13, "aud": 1,  "combat": False, "label": "Craft"},
    "rest":          {"stat": "CON", "dc": 8,  "aud": 0,  "combat": False, "label": "Rest"},
    "navigate":      {"stat": "WIS", "dc": 11, "aud": 0,  "combat": False, "label": "Navigate"},
    "loot":          {"stat": "WIS", "dc": 10, "aud": 1,  "combat": False, "label": "Loot"},
    # Step 6 additions
    "look":          {"stat": "WIS", "dc": 8,  "aud": 0,  "combat": False, "label": "Look"},
    "strip":         {"stat": "INT", "dc": 11, "aud": 1,  "combat": False, "label": "Strip"},
    "env_use":       {"stat": "INT", "dc": 12, "aud": 3,  "combat": True,  "label": "Env. use"},
    "env_combo":     {"stat": "INT", "dc": 14, "aud": 5,  "combat": True,  "label": "Env. combo"},
    "clarify":       {"stat": "WIS", "dc": 0,  "aud": 0,  "combat": False, "label": "Clarify"},
}

# Keyword → intent mapping  (order matters — first match wins per phrase)
_VERB_MAP: List[tuple] = [
    # Combat
    (r"\b(attack|hit|strike|smash|bash|beat|bludgeon)\b", "attack"),
    (r"\b(stab|pierce|thrust|impale)\b",                  "stab"),
    (r"\b(slash|slice|cut|sever|swipe)\b",                "slash"),
    (r"\b(shoot|fire|blast|zap|gun)\b",                   "shoot"),
    (r"\b(punch|fist|uppercut|haymaker)\b",               "punch"),
    (r"\b(kick|stomp|sweep)\b",                           "kick"),
    (r"\b(shove|push|tackle|bull.?rush|body.?slam)\b",    "shove"),
    (r"\b(grapple|grab|seize|wrestle|hold|pin)\b",        "grapple"),
    (r"\b(trip|knock.?down|leg.?sweep|topple)\b",         "trip"),
    (r"\b(disarm)\b",                                     "disarm"),
    (r"\b(throw|hurl|fling|lob|toss)\b",                  "throw"),
    (r"\b(charge|rush|ram|bull)\b",                       "charge"),
    (r"\b(taunt|mock|insult|jeer|provoke)\b",              "taunt"),
    (r"\b(intimidate|threaten|scare|menace)\b",           "intimidate"),
    (r"\b(blind|throw.+smoke|deploy.+smoke)\b",           "blind"),
    (r"\b(distract|feint|lure|mislead|fake)\b",           "distract"),
    (r"\b(dodge|evade|duck|sidestep|parry|block)\b",      "dodge"),
    (r"\b(flee|run|escape|bolt|retreat|leave|exit)\b",    "flee"),
    (r"\b(defend|guard|brace|shield)\b",                  "defend"),
    (r"\b(inspect|look.at|study.enemy|examine.enemy)\b",  "inspect"),
    (r"\b(use.+ability|activate|channel|cast|invoke)\b",  "use_ability"),
    (r"\b(use.+item|drink|consume|apply|take|eat)\b",     "use_item"),
    (r"\b(env|environment|pool|ledge|spike|pit|fire)\b",  "environment"),
    # Exploration
    (r"\b(search|look.around|scan|survey|investigate)\b", "search"),
    (r"\b(pick.+lock|lockpick|bypass.+door)\b",           "pick_lock"),
    (r"\b(disarm.+trap|defuse|dismantle.+trap)\b",        "disarm_trap"),
    (r"\b(detect.+trap|find.+trap|check.+trap)\b",        "detect_trap"),
    (r"\b(talk|speak|converse|negotiate|reason|ask)\b",   "talk"),
    (r"\b(haggle|barter|bargain|trade)\b",                "haggle"),
    (r"\b(examine|inspect|look.at|read|study)\b",         "examine"),
    (r"\b(climb|scale|ascend)\b",                         "climb"),
    (r"\b(sneak|stealth|skulk|creep|tiptoe)\b",           "sneak"),
    (r"\b(break|smash.down|destroy|force.open)\b",        "break"),
    (r"\b(hack|crack|access|override|interface)\b",       "hack"),
    (r"\b(craft|build|construct|make|create)\b",          "craft"),
    (r"\b(rest|sit|recover|catch.+breath)\b",             "rest"),
    (r"\b(navigate|move.to|go.to|proceed)\b",             "navigate"),
    (r"\b(loot|take|grab|collect|pick.up)\b",             "loot"),
]

# ── Polish verb map (Step 6) ──────────────────────────────────────────────────
# Matches root + most conjugations via permissive suffix patterns.
# Word boundaries kept loose because Polish forms attach suffixes directly.
_VERB_MAP_PL = [
    # Combat verbs
    (r"\b(atak\w*|uderz\w*|wal\w*|tlucz\w*|tłucz\w*)\b",   "attack"),
    (r"\b(dzgnij\w*|dźgnij\w*|przebij\w*|pchnij\w*)\b",     "stab"),
    (r"\b(tnij\w*|ciac\w*|tnac\w*|rozcina\w*)\b",           "slash"),
    (r"\b(strzel\w*|strzal\w*|strzała\w*|odpal\w*)\b",      "shoot"),
    (r"\b(uderz\w+ piesc|pies\w*|pięs\w*|pięść\w*)\b",      "punch"),
    (r"\b(kopnij\w*|kopnac\w*|kopniac\w*)\b",               "kick"),
    (r"\b(popchnij\w*|spchnij\w*|wepchn\w*|wepch\w*)\b",    "shove"),
    (r"\b(chwy[cć]\w*|złap\w*|zlap\w*|trzymaj\w*)\b",       "grapple"),
    (r"\b(potkn\w*|przewroc\w*|obal\w*)\b",                 "trip"),
    (r"\b(rozbroj\w*|odbierz\w*|wytrac\w*)\b",              "disarm"),
    (r"\b(rzuc\w*|cisnij\w*|ciska\w*|miota\w*)\b",          "throw"),
    (r"\b(szarz\w*|naciera\w*|natrzyj\w*)\b",               "charge"),
    (r"\b(prowoku\w*|prowokuj\w*|obraz\w*|oblec\w*)\b",     "taunt"),
    (r"\b(zastrasz\w*|grozic\w*|grozić\w*|strasz\w*)\b",    "intimidate"),
    (r"\b(oslep\w*|oślep\w*|zasłon\w*|zaslon\w*)\b",        "blind"),
    (r"\b(zwiedz\w*|zwiódź\w*|odciagnij\w*|odciągnij\w*)\b","distract"),
    (r"\b(uskocz\w*|unik\w*|odskocz\w*)\b",                 "dodge"),
    (r"\b(ucieka\w*|uciek\w*|wycofa\w*|spierd\w*)\b",       "flee"),
    (r"\b(broni\w*|obroni\w*|zaslon\w*|zasłon\w*|gard\w*)\b","defend"),
    (r"\b(zbadaj\w*|zbada\w*|sprawdz\w*)\b",                "inspect"),
    (r"\b(uzyj\w* zdoln\w*|użyj\w* zdoln\w*|aktywuj\w*|rzuć\w* czar\w*|rzuc\w* czar\w*)\b", "use_ability"),
    (r"\b(uzyj\w*|użyj\w*|wypij\w*|wypić\w*|zjedz\w*|zjedź\w*)\b", "use_item"),
    (r"\b(środowis\w*|srodowis\w*|wykorzysta\w* otoczeni\w*)\b", "environment"),
    # Exploration
    (r"\b(szukaj\w*|przeszuk\w*|sprawdz\w* pokój\w*|sprawdz\w* pokoj\w*)\b","search"),
    (r"\b(otworz\w* zamk\w*|otwórz\w* zamk\w*|wytrych\w*)\b", "pick_lock"),
    (r"\b(rozbroj\w* pułapk\w*|rozbroj\w* pulapk\w*|defuz\w*)\b", "disarm_trap"),
    (r"\b(wykryj\w* pułapk\w*|wykryj\w* pulapk\w*|znajdz\w* pułapk\w*)\b", "detect_trap"),
    (r"\b(porozmaw\w*|rozmaw\w*|gadaj\w*|powiedz\w*)\b",    "talk"),
    (r"\b(targuj\w*|negocj\w*|cena\w*)\b",                  "haggle"),
    (r"\b(rozejrzy\w*|rozglada\w*|obejrz\w*|zbadaj\w*)\b",  "examine"),
    (r"\b(wspina\w*|wespnij\w*|wdrap\w*)\b",                "climb"),
    (r"\b(skradaj\w*|skradnij\w*|cicho\w*)\b",              "sneak"),
    (r"\b(rozwal\w*|rozbij\w*|zniszcz\w*)\b",               "break"),
    (r"\b(hakuj\w*|włam\w*|wlam\w*|przejmij\w*)\b",         "hack"),
    (r"\b(stworz\w*|stwórz\w*|skonstruuj\w*|zbuduj\w*)\b",  "craft"),
    (r"\b(odpocznij\w*|odpoczyn\w*|przespać\w*|przespać się\w*)\b", "rest"),
    (r"\b(idź\w*|idz\w*|przejdz\w*|przejdź\w*|przemiesc\w*)\b", "navigate"),
    (r"\b(zabier\w*|wez\w*|weź\w*|podnies\w*|podnieś\w*)\b","loot"),
    # New: strip / harvest for crafting
    (r"\b(zerwij\w*|rozkrec\w*|rozkręć\w*|rozmontuj\w*|wyrwij\w*)\b", "strip"),
    (r"\b(rozejrzyj się|rozejrzyj sie|spójrz\w*|spojrz\w*|patrz\w*)\b", "look"),
]

# English: add strip and look intents as well
_VERB_MAP.extend([
    (r"\b(strip|harvest|salvage|scavenge|tear.+off|pry.+off)\b", "strip"),
    (r"\b(^look$|look around|look at room|survey room)\b",       "look"),
])

# Environment keywords that boost audience rating
_ENV_WORDS = [
    "acid", "pool", "fire", "pit", "spike", "wall", "ledge", "barrel",
    "machinery", "cable", "gravity", "ceiling", "window", "container",
    # Polish
    "kwas", "kalu", "kałuż", "ogień", "ognia", "kabl", "rur", "para",
    "regał", "regal", "szkło", "szklo", "amunicj",
]

# Hostile/target words (help disambiguate vs self-referential actions)
_TARGET_WORDS = [
    "enemy", "monster", "creature", "guard", "drone", "it", "them", "him",
    "her", "target", "opponent", "attacker", "the ",
]


def parse_input(text: str, context: str = "explore", room=None) -> Dict[str, Any]:
    """
    Parse free-text player input and return action dict.

    context: "combat" or "explore"
    room:    optional Room — used to resolve env_object references and
             to avoid "pretending" actions on objects that don't exist.

    Returns dict including:
      intent           - str
      stat, dc, label, aud_bonus
      raw_text, is_combat, has_env
      numeric          - int if input was just a number
      item_name        - extracted "use X" name
      ability_name     - extracted "cast X" name
      env_target_key   - resolved EnvObject key in room (or None)
      env_combo        - tuple (objA_key, objB_key, label) if a combo is implied
      keyword_matched  - debug
    """
    lower = text.lower().strip()

    # Numeric shortcut
    m = re.match(r'^\s*(\d+)\s*$', lower)
    if m:
        return {
            "intent": "numeric",
            "stat": "STR",
            "dc": 10,
            "label": f"Option {m.group(1)}",
            "aud_bonus": 0,
            "raw_text": text,
            "is_combat": context == "combat",
            "has_env": False,
            "numeric": int(m.group(1)),
            "item_name": None,
            "ability_name": None,
            "keyword_matched": "number",
        }

    # Check environment words (increases DC + audience)
    has_env = any(word in lower for word in _ENV_WORDS)

    # Item name extraction for "use X"
    item_name = None
    item_m = re.search(r'\buse\s+(?:my\s+)?([a-z][a-z\s]+?)(?:\s+on|\s+at|$)', lower)
    if item_m:
        item_name = item_m.group(1).strip()

    # Ability name extraction
    ability_name = None
    abl_m = re.search(r'\b(?:use|cast|activate)\s+(?:my\s+)?([a-z][a-z\s]+?)(?:\s+on|\s+at|$)', lower)
    if abl_m:
        ability_name = abl_m.group(1).strip()

    # Match intent via verb patterns — Polish first (we're Polish-primary),
    # then English. First hit wins.
    matched_intent = None
    keyword_matched = ""
    from lang import get_language
    primary = _VERB_MAP_PL if get_language() == "pl" else _VERB_MAP
    secondary = _VERB_MAP if get_language() == "pl" else _VERB_MAP_PL
    for table in (primary, secondary):
        for pattern, intent_key in table:
            if re.search(pattern, lower):
                matched_intent = intent_key
                keyword_matched = pattern
                break
        if matched_intent is not None:
            break

    # ── Object targeting (Step 6) ─────────────────────────────────────────────
    env_target_key = None
    env_combo = None
    if room is not None and hasattr(room, "env_objects"):
        try:
            from environment import find_object, available_combo
        except ImportError:
            find_object = None
            available_combo = None
        if find_object is not None:
            obj = find_object(room, lower)
            if obj is not None:
                env_target_key = obj.key
        if available_combo is not None and any(
                w in lower for w in ("combine","mix","połącz","polacz","kombinuj","wrzuc","wrzuć")):
            combo = available_combo(room)
            if combo:
                env_combo = (combo[0].key, combo[1].key, combo[2].get("label_key","combo_shock"))

    # If user invokes 'environment' / 'env_use' but no object found, force clarify.
    if matched_intent in ("environment", "env_use", "strip") and env_target_key is None and env_combo is None:
        # Allow generic 'use environment' to still work in combat as before
        # only when no room was supplied (legacy callers); otherwise clarify.
        if room is not None:
            matched_intent = "clarify"
            keyword_matched = "clarify_no_target"

    if env_combo is not None:
        matched_intent = "env_combo"
        keyword_matched = "combo_detected"
    elif env_target_key is not None and matched_intent in ("environment","strip","use_item"):
        matched_intent = "strip" if matched_intent == "strip" else "env_use"
        keyword_matched = "object_target"

    # Fallback
    if matched_intent is None:
        if context == "combat":
            matched_intent = "attack"
            keyword_matched = "fallback"
        else:
            matched_intent = "examine"
            keyword_matched = "fallback"

    intent_data = INTENTS.get(matched_intent, INTENTS["examine"])

    dc = intent_data["dc"]
    aud = intent_data["aud"]

    # Environmental action boost
    if has_env:
        dc += 2
        aud += 3

    # Compound action penalty (very long inputs are ambitious)
    word_count = len(lower.split())
    if word_count > 12:
        dc += 2
        aud += 2

    return {
        "intent": matched_intent,
        "stat": intent_data["stat"],
        "dc": dc,
        "label": intent_data["label"],
        "aud_bonus": aud,
        "raw_text": text,
        "is_combat": intent_data["combat"],
        "has_env": has_env,
        "numeric": None,
        "item_name": item_name,
        "ability_name": ability_name,
        "keyword_matched": keyword_matched,
        # Step 6 additions
        "env_target_key": env_target_key,
        "env_combo": env_combo,
    }


def skill_check(character, action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Roll the skill check for a parsed action against a character.
    Returns result dict with success/failure, roll details, narrative.
    """
    from utils import d20, ability_modifier, proficiency_bonus

    stat = action["stat"]
    dc = action["dc"]

    raw = d20()
    mod = character.stat_mod(stat)
    prof = 0
    # Proficient in stat's skill if it matches class primary
    if character.class_key:
        from character import CLASSES
        cls = CLASSES.get(character.class_key, {})
        if stat in cls.get("primary", []):
            prof = character.prof()

    # Background perks
    if character.background_perk == "soldier_training" and action["intent"] in (
            "attack", "stab", "slash", "shoot", "punch", "kick", "charge"):
        prof += 1
    if character.background_perk == "wire_sense" and action["intent"] in (
            "disarm_trap", "detect_trap"):
        mod += 3
    if character.background_perk == "peak_condition" and action["intent"] == "flee":
        mod += 2

    total = raw + mod + prof
    success = total >= dc
    crit = raw == 20
    fumble = raw == 1

    if crit:
        success = True
    if fumble:
        success = False

    aud = action["aud_bonus"]
    if crit:
        aud += 3
    if fumble:
        aud -= 1

    return {
        "success": success,
        "crit": crit,
        "fumble": fumble,
        "raw": raw,
        "mod": mod,
        "prof": prof,
        "total": total,
        "dc": dc,
        "stat": stat,
        "aud_delta": aud,
        "intent": action["intent"],
        "label": action["label"],
        "has_env": action["has_env"],
    }


def describe_result(result: Dict[str, Any], context: str = "combat") -> List[str]:
    """Return narrative lines for a skill check result."""
    lines = []
    stat = result["stat"]
    total = result["total"]
    dc = result["dc"]
    intent = result["intent"]
    label = result["label"]

    roll_line = f"  [{label}] d20({result['raw']}) + {stat}({result['mod']:+d}) + prof({result['prof']}) = {total} vs DC {dc}"
    lines.append(roll_line)

    if result["crit"]:
        lines.append("  CRITICAL SUCCESS! Natural 20. The audience erupts.")
    elif result["fumble"]:
        lines.append("  CRITICAL FAILURE. Natural 1. The Protocol winces.")
    elif result["success"]:
        if result["has_env"]:
            lines.append("  Success. Creative use of the environment. Ratings up.")
        else:
            lines.append("  Success.")
    else:
        lines.append(f"  Failed. ({total} < {dc})")

    return lines


def combat_action_from_result(result: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate a skill check result into a concrete combat effect.
    Returns effect dict consumed by combat.py.
    """
    intent = result["intent"]
    success = result["success"]
    crit = result["crit"]

    effect = {
        "type": "none",
        "damage": 0,
        "condition": None,
        "self_effect": None,
        "flee": False,
        "inspect": False,
        "aud_delta": result["aud_delta"],
        "use_weapon": False,
        "use_item": action.get("item_name"),
        "use_ability": action.get("ability_name"),
        "description": "",
    }

    if not success:
        effect["type"] = "miss"
        return effect

    if intent in ("attack", "stab", "slash", "shoot", "punch", "kick", "charge"):
        effect["type"] = "damage"
        effect["use_weapon"] = True
        if crit:
            effect["damage_multiplier"] = 2

    elif intent == "shove":
        effect["type"] = "condition"
        effect["condition"] = "prone"

    elif intent == "grapple":
        effect["type"] = "condition"
        effect["condition"] = "grappled"

    elif intent == "trip":
        effect["type"] = "condition"
        effect["condition"] = "prone"

    elif intent == "disarm":
        effect["type"] = "disarm"

    elif intent == "taunt":
        effect["type"] = "condition"
        effect["condition"] = "taunted"

    elif intent == "intimidate":
        effect["type"] = "condition"
        effect["condition"] = "weakened"

    elif intent == "blind":
        effect["type"] = "condition"
        effect["condition"] = "blinded"

    elif intent == "distract":
        effect["type"] = "condition"
        effect["condition"] = "distracted"

    elif intent == "dodge":
        effect["type"] = "self_buff"
        effect["self_effect"] = "dodge"

    elif intent == "defend":
        effect["type"] = "self_buff"
        effect["self_effect"] = "defend"

    elif intent == "flee":
        effect["type"] = "flee"
        effect["flee"] = True

    elif intent == "inspect":
        effect["type"] = "inspect"
        effect["inspect"] = True

    elif intent == "use_ability":
        effect["type"] = "ability"

    elif intent == "use_item":
        effect["type"] = "item"

    elif intent == "environment":
        effect["type"] = "environment"
        from utils import parse_dice
        extra = parse_dice("1d8") if not crit else parse_dice("2d8")
        effect["damage"] = extra

    elif intent == "throw":
        effect["type"] = "damage"
        from utils import parse_dice
        effect["damage"] = parse_dice("1d6")

    elif intent == "env_use":
        effect["type"] = "env_use"

    elif intent == "env_combo":
        effect["type"] = "env_combo"

    elif intent == "strip":
        effect["type"] = "strip"

    elif intent == "clarify":
        effect["type"] = "clarify"

    elif intent == "talk":
        effect["type"] = "social"

    elif intent == "sneak":
        effect["type"] = "stealth"

    return effect
