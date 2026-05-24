"""Deterministic hybrid parser.

Turns free-text into an ActionIntent dict. Never decides success.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .affordances import AFFORDANCE_CATALOG, find_affordance_by_verb, fold
from .lang import get_language


# Polish stop words / connector tokens we filter out of target extraction.
_STOP = {
    # Polish prepositions / pronouns / fillers
    "w","we","na","do","ze","z","i","oraz","albo","lub","tym","ten","ta","to",
    "tego","tej","tych","mnie","mi","go","ją","ja","im","sie","się","u","o",
    "po","za","przed","obok","obok","wokół","wokol","mojego","moja","mój","moj",
    # English equivalents
    "the","a","an","my","this","that","with","into","onto","at","on","to","of",
    "and","or","into","in","out","up","down",
    # Common imperative-leading particles
    "no","ok","dobra","ej","hej","hey",
}


@dataclass
class ActionIntent:
    raw_text: str = ""
    normalized_text: str = ""
    language_guess: str = "pl"
    intent: str = "unknown"           # affordance key or "unknown"
    verb: str = ""
    targets: List[str] = field(default_factory=list)       # candidate object/entity names
    tool: Optional[str] = None
    destination: Optional[str] = None
    desired_outcome: Optional[str] = None
    modifiers: List[str] = field(default_factory=list)
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_options: List[str] = field(default_factory=list)
    parser_source: str = "deterministic"

    def to_dict(self):
        return self.__dict__.copy()


# Top-level fast-path intents that don't have entity targets
_QUICK_INTENTS = {
    "look":          ["rozejrzyj","rozejrzy","spójrz","spojrz","look","look around"],
    "search":        ["przeszukaj","szukaj","przetrzas","search"],
    "wait":          ["czekaj","poczekaj","wait"],
    "rest_short":    ["odpocznij","short rest","odpoczynek"],
    "rest_long":     ["spij","śpij","sleep","wyspij","wyśpij","long rest"],
    "check_inventory": ["ekwipunek","plecak","inventory"],
    "check_character": ["postać","postac","karta","character"],
    "check_map":     ["mapa","map"],
    "ask_rumor":     ["plotki","rumors"],
    "save":          ["zapisz","save"],
    "help":          ["pomoc","help","?"],
    "flee":          ["uciekaj","spierdalaj","run","flee","wycofaj"],
}


def parse(text: str, world=None) -> ActionIntent:
    """Parse the player's natural-language command."""
    intent = ActionIntent(raw_text=text)
    lower = (text or "").lower().strip()
    intent.normalized_text = lower
    intent.language_guess = get_language() or "pl"

    if not lower:
        intent.intent = "unknown"
        return intent

    # ── Numeric quick-pick ───────────────────────────────────────────────────
    m = re.match(r"^\s*(\d+)\s*$", lower)
    if m:
        intent.intent = "numeric"
        intent.modifiers.append(m.group(1))
        intent.confidence = 1.0
        return intent

    folded = fold(lower)

    # ── Fast-path quick intents ──────────────────────────────────────────────
    for ikey, cues in _QUICK_INTENTS.items():
        for cue in cues:
            cf = fold(cue)
            if folded == cf or folded.startswith(cf + " ") or folded.endswith(" " + cf):
                intent.intent = ikey
                intent.verb = cue
                intent.confidence = 0.95
                return intent

    # ── Movement: "idź do X" / "go to X" / "wróć do X" ───────────────────────
    nav_re = re.compile(
        r"^(?:idz|idź|przejdz|przejdź|wejdz|wejdź|wroc|wróć|go|move|enter|return)\s+(?:do |to |back to )?(.+)$"
    )
    nm = nav_re.match(folded)
    if nm:
        intent.intent = "move"
        intent.verb = nm.group(0).split()[0]
        intent.destination = _strip_articles(nm.group(1))
        intent.confidence = 0.9
        return intent

    # ── Listen: "nasłuchuj <exit>" / "listen at <exit>" ──────────────────────
    if folded.startswith(("nasluchuj","posluchaj","listen")):
        intent.intent = "listen"
        rest = folded.split(maxsplit=1)
        if len(rest) > 1:
            intent.destination = _strip_articles(rest[1])
        intent.confidence = 0.9
        return intent

    # ── Talk: "pogadaj z X" / "talk to X" ────────────────────────────────────
    talk_re = re.compile(r"^(?:pogadaj|porozmawiaj|zagadaj|talk|speak)(?:\s+(?:z|to|with))?\s+(.+)$")
    tm = talk_re.match(folded)
    if tm:
        intent.intent = "talk"
        intent.verb = "talk"
        intent.targets.append(_strip_articles(tm.group(1)))
        intent.confidence = 0.9
        return intent

    # ── Use: "użyj X na Y" / "use X on Y" ────────────────────────────────────
    use_re = re.compile(r"^(?:uzyj|użyj|use)\s+(.+?)(?:\s+(?:na|on|at|aby|do)\s+(.+))?$")
    um = use_re.match(folded)
    if um:
        intent.intent = "use"
        intent.verb = "use"
        intent.tool = _strip_articles(um.group(1))
        if um.group(2):
            intent.targets.append(_strip_articles(um.group(2)))
        intent.confidence = 0.85
        return intent

    # ── Push/throw/lure into/at/onto X — environment chains ──────────────────
    chain_re = re.compile(
        r"^(?P<verb>wepchnij|pchnij|popchnij|rzuc|rzuć|cisnij|ciśnij|zwab|push|shove|throw|hurl|lure)\s+"
        r"(?P<obj>.+?)"
        r"(?:\s+(?:do|w|w stronę|do strony|na|onto|into|in|at|toward)\s+(?P<dest>.+))?$"
    )
    cm = chain_re.match(folded)
    if cm:
        verb = cm.group("verb")
        aff = find_affordance_by_verb(verb, intent.language_guess)
        if aff is not None:
            intent.intent = aff.key
            intent.verb = verb
            intent.targets.append(_strip_articles(cm.group("obj")))
            if cm.group("dest"):
                intent.destination = _strip_articles(cm.group("dest"))
            intent.confidence = 0.85
            return intent

    # ── Fallback: first token is verb, the rest is target ────────────────────
    tokens = [t for t in re.split(r"\s+", folded) if t]
    if tokens:
        verb_token = tokens[0]
        aff = find_affordance_by_verb(verb_token, intent.language_guess)
        if aff is not None:
            intent.intent = aff.key
            intent.verb = verb_token
            # Everything else is potential target / modifier
            for tok in tokens[1:]:
                if tok in _STOP:
                    continue
                intent.targets.append(tok)
            intent.confidence = 0.6 if intent.targets else 0.7
            return intent

    intent.intent = "unknown"
    intent.confidence = 0.0
    return intent


def _strip_articles(s: str) -> str:
    """Remove leading filler tokens from a target phrase."""
    parts = [t for t in re.split(r"\s+", s.strip()) if t and t not in _STOP]
    return " ".join(parts).strip()


def parse_with_optional_llm(text: str, world=None) -> ActionIntent:
    """Pipeline: deterministic first; if confidence is low and Ollama is
    enabled, call the LLM to produce a fallback intent. Either way, return
    an ActionIntent for the validator to interpret. Never raise."""
    from .config import USE_OLLAMA

    # Always run the deterministic parser first.
    deterministic = parse(text, world)
    if deterministic.confidence >= 0.7 or deterministic.intent == "numeric":
        return deterministic

    if not USE_OLLAMA:
        return deterministic

    # Build a compact context the LLM can actually use without paying tokens
    # for the entire world.
    context = _build_compact_context(world)

    try:
        from . import llm_parser
        llm_dict = llm_parser.parse_with_ollama(text, context)
    except Exception:
        llm_dict = None

    if not llm_dict:
        return deterministic

    llm_intent = _intent_from_llm_dict(llm_dict, raw_text=text)
    # Prefer the LLM's interpretation only if it's at least as confident.
    if llm_intent.confidence >= deterministic.confidence:
        return llm_intent
    return deterministic


def _build_compact_context(world) -> dict:
    """Compact context for the LLM. No save dumps, no long logs."""
    ctx = {"mode": "exploration"}
    if world is None or world.current_floor is None:
        return ctx
    room = world.current_floor.current_room()
    if room is None:
        return ctx

    desc = room.display_first_enter() or room.display_look() or ""
    # Single short paragraph
    ctx["room_short_description"] = desc.strip()[:240]

    visible_objects = []
    visible_entities = []
    for e in room.visible_entities():
        name = e.display_name()
        if e.entity_type in ("object", "hazard", "environmental_feature",
                             "container", "door", "terminal", "service",
                             "safehouse_service", "exit", "corpse"):
            visible_objects.append(name)
        elif e.entity_type in ("crawler", "monster", "npc", "player"):
            visible_entities.append(name)
        else:
            visible_objects.append(name)
    ctx["visible_objects"] = visible_objects
    ctx["visible_entities"] = visible_entities
    ctx["exits"] = list(room.exits.keys())

    inv = []
    for eid in world.character.inventory_ids:
        ent = world.entities.get(eid)
        if ent is not None:
            inv.append(ent.display_name())
    ctx["inventory"] = inv

    # Mode hint — used by the prompt to influence intent space
    if room.safehouse_subtype:
        ctx["mode"] = "safehouse"
    elif any(e.entity_type == "monster" and e.is_alive() for e in room.entities):
        ctx["mode"] = "combat"
    return ctx


def _intent_from_llm_dict(d: dict, raw_text: str) -> ActionIntent:
    """Convert an LLM-returned dict into an ActionIntent.

    The result still must pass through the deterministic validator —
    we are not granting the LLM authority over success/failure or any
    world-state mutation.
    """
    intent = ActionIntent(raw_text=raw_text, parser_source="ollama")

    # Map any model verb-y intent back onto our affordance vocabulary if
    # possible, while keeping the original string as a hint.
    raw_intent = (d.get("intent") or "").strip().lower()
    raw_verb   = (d.get("verb") or "").strip().lower()

    # Try our verb resolver — it's more reliable than the LLM's intent label
    aff_match = None
    for candidate in (raw_intent, raw_verb):
        if candidate:
            aff = find_affordance_by_verb(candidate, "pl") or find_affordance_by_verb(candidate, "en")
            if aff is not None:
                aff_match = aff
                break

    if aff_match is not None:
        intent.intent = aff_match.key
    elif raw_intent in _LLM_INTENT_PASSTHROUGH:
        intent.intent = raw_intent
    else:
        # Last resort: keep the raw label so the validator can refuse it
        intent.intent = raw_intent or "unknown"

    intent.verb = raw_verb or raw_intent or ""
    intent.targets = list(d.get("targets") or [])
    intent.tool = d.get("tool")
    intent.destination = d.get("destination")
    intent.desired_outcome = d.get("desired_outcome")
    if d.get("suggested_stat"):
        intent.modifiers.append(f"stat:{d['suggested_stat']}")
    if d.get("risk_level"):
        intent.modifiers.append(f"risk:{d['risk_level']}")
    try:
        intent.confidence = float(d.get("confidence", 0.5))
    except (TypeError, ValueError):
        intent.confidence = 0.5
    return intent


# Whitelist of intent strings the LLM may produce that we accept verbatim.
_LLM_INTENT_PASSTHROUGH = {
    "look","inspect","search","move","listen","wait","rest_short","rest_long",
    "attack","defend","use","talk","intimidate","bribe","sneak","hide","flee",
    "craft","loot","open","close","hack","force","lockpick","throw_at",
    "push_into","lure","perform","ask_rumor","check_inventory","check_character",
    "check_map","save","help",
}
