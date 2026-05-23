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

# Environment keywords that boost audience rating
_ENV_WORDS = [
    "acid", "pool", "fire", "pit", "spike", "wall", "ledge", "barrel",
    "machinery", "cable", "gravity", "ceiling", "window", "container",
]

# Hostile/target words (help disambiguate vs self-referential actions)
_TARGET_WORDS = [
    "enemy", "monster", "creature", "guard", "drone", "it", "them", "him",
    "her", "target", "opponent", "attacker", "the ",
]


def parse_input(text: str, context: str = "explore") -> Dict[str, Any]:
    """
    Parse free-text player input and return action dict.

    context: "combat" or "explore"

    Returns dict:
      intent     : str (intent key)
      stat       : str (e.g. "STR")
      dc         : int (difficulty class)
      label      : str (human-readable)
      aud_bonus  : int
      raw_text   : str
      is_combat  : bool
      has_env    : bool (uses environment — higher DC but bonus aud)
      numeric    : Optional[int]  (if player typed just a number)
      item_name  : Optional[str]  (if "use item X")
      ability_name: Optional[str]
      keyword_matched: str
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

    # Match intent via verb patterns
    matched_intent = None
    keyword_matched = ""
    for pattern, intent_key in _VERB_MAP:
        if re.search(pattern, lower):
            matched_intent = intent_key
            keyword_matched = pattern
            break

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

    return effect
