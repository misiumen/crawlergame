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
    """Try the LLM parser first if enabled; fall back to deterministic."""
    from .config import USE_OLLAMA
    if USE_OLLAMA:
        try:
            from . import llm_parser
            result = llm_parser.parse(text, world)
            if result and result.confidence >= 0.6:
                return result
        except Exception:
            pass
    return parse(text, world)
