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
    # Audit gap 1: Polish "X z Y" / English "X from Y" extraction
    desired_material: Optional[str] = None   # the X token (what player wants)
    desired_part: Optional[str] = None       # alias for human-readable parts
    source_text: Optional[str] = None        # the Y token (source entity)
    raw_target_text: Optional[str] = None    # the original target fragment

    # Prompt 07: memetic action payload.
    memetic_method: Optional[str] = None     # rumor / lie / false_order / ...
    core_claim: Optional[str] = None         # the proposition the player asserts
    spread_channel: Optional[str] = None     # narrative channel for the claim

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
    # ask_rumor is reserved for an NPC-side action; the journal tab cues
    # (plotki/rumors) now live in `check_beliefs` and route to the rumors
    # tab through phrasing detection in game.py.
    "ask_rumor":     ["zapytaj o plotki","ask about rumors"],
    "save":          ["zapisz","save"],
    # Multi-word "pomoc X" matches MUST come before bare "help" so they win.
    "craft_help":      ["pomoc craftingu","craft help"],
    "salvage_help":    ["pomoc odzyskiwania","salvage help"],
    "trap_help":       ["pomoc pułapek","pomoc pulapek","trap help","pomoc rozstawiania"],
    "help":          ["pomoc","help","?"],
    "flee":          ["uciekaj","spierdalaj","run","flee","wycofaj"],
    "check_materials": ["materiały","materialy","materials","surowce"],
    "check_beliefs":   ["idee","plotki","wpływy","wplywy","beliefs","rumors",
                        "memy","mem","mity","przekonania"],
    # Prompt 07b: knowledge journal (clues + facts + passwords + routes).
    "check_knowledge": ["wiedza","informacje","wskazówki","wskazowki",
                        "clues","facts","notes"],
    # Prompt 09: resolution / display settings
    "show_resolutions":   ["rozdzielczość","rozdzielczosc","resolution","resolutions"],
    "set_fullscreen":     ["fullscreen","pełny ekran","pelny ekran","ekran"],
    "set_windowed":       ["windowed","tryb okna","okno","tryb okien"],
    # Prompt 10: journal overlay
    "journal_open":       ["dziennik","journal","notatki","notes"],
    "journal_close":      ["zamknij","close","wyjdź","wyjdz","zamknij dziennik"],
    "journal_objectives": ["cele","objectives","zadania","cel"],
    "journal_crawlers":   ["crawlerzy","crawlers","znajomi"],
    "journal_crafting":   ["crafting","przepisy","recipes"],
    "journal_achievements":["osiągnięcia","osiagniecia","achievements","sukcesy"],
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

    # ── Prompt 09: "ustaw rozdzielczość 1600x900" / "set resolution 1600x900" ──
    res_re = re.compile(
        r"^(?:ustaw|set)\s+(?:rozdzielczosc|rozdzielczość|resolution)\s+"
        r"(?P<w>\d{3,5})\s*[x×]\s*(?P<h>\d{3,5})$"
    )
    rm2 = res_re.match(folded)
    if rm2:
        intent.intent = "set_resolution"
        intent.verb = "set_resolution"
        try:
            intent.modifiers.append(f"w:{int(rm2.group('w'))}")
            intent.modifiers.append(f"h:{int(rm2.group('h'))}")
        except (ValueError, TypeError):
            pass
        intent.confidence = 0.95
        return intent

    # ── Prompt 07b: "użyj hasła [do X]" must beat the generic "use" regex ────
    pwd_re_early = re.compile(
        r"^(?:uzyj|użyj|use|wprowadz|wprowadź|enter|wpisz)\s+"
        r"(?:hasla|hasła|password|kodu|code)"
        r"(?:\s+(?:do|na|on|to|for)\s+(?P<who>.+))?$"
    )
    pme = pwd_re_early.match(folded)
    if pme:
        intent.intent = "use_password"
        intent.verb = pme.group(0).split()[0]
        if pme.group("who"):
            intent.targets.append(_strip_articles(pme.group("who")))
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

    # ── Salvage / harvest / loot "X z Y" (Polish) and "X from Y" (English) ────
    # Patterns: pozyskaj X z Y / wyciągnij X z Y / odzyskaj X z Y / zbierz X z Y
    #           weź X z Y / wymontuj X z Y / zdemontuj X z Y / wyjmij X z Y
    # English:   harvest/take/recover/pull X from/out of Y
    extract_re = re.compile(
        r"^(?P<verb>"
        r"pozyskaj\w*|wyciagnij\w*|wyciągnij\w*|odzyskaj\w*|zbierz\w*|wez\w*|weź\w*|"
        r"wymontuj\w*|zdemontuj\w*|wyjmij\w*|wyjm\w*|wyrwij\w*|wypruj\w*|"
        r"harvest|take|recover|pull|grab|salvage|extract"
        r")\s+"
        r"(?P<obj>.+?)"
        r"\s+(?:z\s+tego\s+|z\s+|ze\s+|from\s+|out\s+of\s+)"
        r"(?P<src>.+)$"
    )
    em = extract_re.match(folded)
    if em:
        verb = em.group("verb")
        aff = find_affordance_by_verb(verb, intent.language_guess)
        # Verb -> intent override: 'wez/take' is loot, 'pozyskaj/harvest' is harvest,
        # everything else defaults to salvage. Override if affordance lookup says
        # something different (loot, harvest, salvage).
        intent_key = aff.key if aff else "salvage"
        if any(verb.startswith(p) for p in ("wez","weź","take","grab","wyjmij","wyjm")):
            intent_key = "loot"
        elif any(verb.startswith(p) for p in ("pozyskaj","harvest","wypruj","wyrwij")):
            intent_key = "harvest"
        elif any(verb.startswith(p) for p in (
                "wyciagnij","wyciągnij","odzyskaj","zbierz","wymontuj","zdemontuj",
                "salvage","recover","pull","extract")):
            intent_key = "salvage"
        intent.intent = intent_key
        intent.verb = verb
        obj_text = _strip_articles(em.group("obj"))
        src_text = _strip_articles(em.group("src"))
        intent.targets.append(src_text)        # source is the main target
        intent.source_text = src_text
        intent.desired_material = obj_text
        intent.desired_part = obj_text
        intent.raw_target_text = f"{obj_text} z {src_text}"
        intent.confidence = 0.9
        return intent

    # ── Prompt 07b: clue-gated resolution phrasings ───────────────────────────
    # "użyj hasła / use password [on X]"
    pwd_re = re.compile(
        r"^(?:uzyj|użyj|use|wprowadz|wprowadź|enter|wpisz)\s+"
        r"(?:hasla|hasła|password|kodu|code)"
        r"(?:\s+(?:do|na|on|to|for)\s+(?P<who>.+))?$"
    )
    pm2 = pwd_re.match(folded)
    if pm2:
        intent.intent = "use_password"
        intent.verb = pm2.group(0).split()[0]
        if pm2.group("who"):
            intent.targets.append(_strip_articles(pm2.group("who")))
        intent.confidence = 0.9
        return intent

    # "wykorzystaj słabość [X] / exploit weakness [of X]"
    weak_re = re.compile(
        r"^(?:wykorzystaj|exploit|target)\s+(?:slabosc|słabość|weakness)"
        r"(?:\s+(?:of\s+|na\s+|of\s+the\s+)?(?P<who>.+))?$"
    )
    wm = weak_re.match(folded)
    if wm:
        intent.intent = "exploit_weakness"
        if wm.group("who"):
            intent.targets.append(_strip_articles(wm.group("who")))
        intent.confidence = 0.9
        return intent

    # "przypominam / invoke belief / use myth"
    invoke_re = re.compile(
        r"^(?:przypominam|przypomnij|przyzywam|invoke|remind|cite)\s+"
        r"(?P<who>.+?)(?:\s+(?:o|of|about|że|that)\s+(?P<claim>.+))?$"
    )
    im = invoke_re.match(folded)
    if im and ("serca" in folded or "heart" in folded or "myth" in folded
               or "wierze" in folded or "wierzą" in folded
               or "tabu" in folded or "prawd" in folded):
        intent.intent = "invoke_belief"
        intent.verb = "invoke"
        intent.targets.append(_strip_articles(im.group("who")))
        intent.core_claim = (im.group("claim") or "").strip()
        intent.confidence = 0.82
        return intent

    # ── Prompt 07: memetic / belief-seed phrasing ─────────────────────────────
    # Patterns the player typically types when planting an idea, lie, rumor,
    # or false order. Each branch fills intent.memetic_method, .core_claim,
    # and .targets where possible. Validation/resolution lives in game.py
    # (`_attempt_memetic`) so we don't pollute the standard validate pipeline.

    # 1) "wmów / wmów im / convince <target>, że <claim>"
    #    → identity_attack OR seed_belief depending on phrasing
    seed_re = re.compile(
        r"^(?P<verb>wmow\w*|wmaw\w*|przekonaj\w*|przekonuj\w*|powiedz\w*|"
        r"convince|tell|persuade|make)\s+"
        r"(?P<who>[^,]+?)"
        r"[, ]+(?:ze|że|that)\s+"
        r"(?P<claim>.+)$"
    )
    sm = seed_re.match(folded)
    if sm:
        intent.intent = "seed_belief"
        intent.verb = sm.group("verb")
        who = _strip_articles(sm.group("who"))
        intent.targets.append(who)
        intent.core_claim = sm.group("claim").strip()
        intent.memetic_method = "identity_attack" if "wmow" in intent.verb else "lie"
        intent.confidence = 0.85
        return intent

    # 2) "rozpuszczam plotkę, że X" / "spread rumor that X"
    rumor_re = re.compile(
        r"^(?P<verb>rozpuszczam|rozpu[sś]c\w*|rozglos\w*|rozg[lł]os\w*|plotkuj\w*|"
        r"powtarzam|spread|circulate|start)\s+"
        r"(?:plotk\w*|rumor\w*|gossip)\s*"
        r"(?:[, ]+(?:ze|że|that)\s+)?"
        r"(?P<claim>.+)$"
    )
    rm = rumor_re.match(folded)
    if rm:
        intent.intent = "spread_rumor"
        intent.verb = rm.group("verb")
        intent.core_claim = rm.group("claim").strip()
        intent.memetic_method = "rumor"
        intent.spread_channel = "crawler_gossip"
        intent.confidence = 0.85
        return intent

    # 3) "podaj fałszywy rozkaz / issue false order to <target>: <claim>"
    order_re = re.compile(
        r"^(?P<verb>podaj|wydaj|issue|fake)\s+(?:falszywy|fa[lł]szywy|fake|false)\s+"
        r"(?:rozkaz|order)\s+"
        r"(?:(?:dla|do|to)\s+)?(?P<who>[^:,]+?)"
        r"(?:\s*[:,]\s*(?P<claim>.+))?$"
    )
    om = order_re.match(folded)
    if om:
        intent.intent = "issue_false_order"
        intent.verb = om.group("verb")
        intent.targets.append(_strip_articles(om.group("who")))
        intent.core_claim = (om.group("claim") or "").strip()
        intent.memetic_method = "false_order"
        intent.spread_channel = "machine_radio"
        intent.confidence = 0.85
        return intent

    # 4) "ogłaszam / broadcast / propaganda" — broadcast-mode framing
    propaganda_re = re.compile(
        r"^(?P<verb>ogla\w*|og[lł]a\w*|nadaj\w*|broadcast|announce|propagand\w*)"
        r"(?:\s+(?:przez|via|through)\s+(?P<chan>kamer\w*|terminal\w*|radio|camera))?"
        r"[, ]+"
        r"(?:(?:ze|że|that)\s+)?(?P<claim>.+)$"
    )
    pm = propaganda_re.match(folded)
    if pm:
        intent.intent = "propaganda"
        intent.verb = pm.group("verb")
        chan = (pm.group("chan") or "").strip()
        intent.spread_channel = ("sponsor_replay" if "kamer" in chan or "camera" in chan
                                 else "terminal_logs" if "terminal" in chan
                                 else "audience_memes")
        intent.core_claim = pm.group("claim").strip()
        intent.memetic_method = "propaganda"
        intent.confidence = 0.82
        return intent

    # 5) "stwórz tabu / create taboo about X"
    taboo_re = re.compile(
        r"^(?P<verb>stworz|stw[oó]rz|nada\w*|ustanow\w*|create|declare)\s+"
        r"(?:tabu|taboo|przeklen\w*|cursed)\s+"
        r"(?:(?:o|on|about|wok[oó][lł]|wokol)\s+)?(?P<claim>.+)$"
    )
    tm2 = taboo_re.match(folded)
    if tm2:
        intent.intent = "create_taboo"
        intent.verb = tm2.group("verb")
        intent.core_claim = tm2.group("claim").strip()
        intent.memetic_method = "taboo_creation"
        intent.spread_channel = "graffiti"
        intent.confidence = 0.8
        return intent

    # 6) "rozsiej / sow distrust / divide them" — sow_distrust
    distrust_re = re.compile(
        r"^(?P<verb>skloc\w*|sk[lł]oc\w*|podziel\w*|zasiej\w*|sow|divide|"
        r"turn against)\s+"
        r"(?P<who>.+?)"
        r"(?:\s+(?:przeciw|against|na|with)\s+(?P<who2>.+))?$"
    )
    dm = distrust_re.match(folded)
    if dm and "nieufnos" in folded or (dm and ("sow" in folded or "divide" in folded)):
        intent.intent = "sow_distrust"
        intent.verb = dm.group("verb")
        who = _strip_articles(dm.group("who"))
        if dm.group("who2"):
            intent.targets.extend([who, _strip_articles(dm.group("who2"))])
        else:
            intent.targets.append(who)
        intent.memetic_method = "social_proof"
        intent.confidence = 0.78
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


_WEAK_FIELD_PLACEHOLDERS = {
    # Single-word generic stubs commonly returned by the deterministic
    # parser when player phrasing was bare ("plotka", "belief", etc.).
    "", "?", "??", "...", "x", "y",
    "belief", "rumor", "lie", "myth", "mit", "plotka", "plotki",
    "machine", "maszyna", "maszyny", "drono", "dron", "drony", "robot", "roboty",
    "crawler", "crawlerzy", "sponsor", "sponsorzy",
}


def is_weak_memetic_field(value) -> bool:
    """Return True when `value` is so generic that an LLM expansion would
    plausibly improve it. Used by the Ollama enrichment path."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    s = value.strip()
    if len(s) < 8:
        return True
    if s.lower() in _WEAK_FIELD_PLACEHOLDERS:
        return True
    # Single token or two-token short phrase is also weak.
    if s.count(" ") < 1:
        return True
    return False


def _strip_articles(s: str) -> str:
    """Remove leading filler tokens from a target phrase."""
    parts = [t for t in re.split(r"\s+", s.strip()) if t and t not in _STOP]
    return " ".join(parts).strip()


def parse_with_optional_llm(text: str, world=None) -> ActionIntent:
    """Pipeline: deterministic first; if confidence is low and Ollama is
    enabled, call the LLM to produce a fallback intent. Either way, return
    an ActionIntent for the validator to interpret. Never raise.

    Prompt-07b follow-up: for memetic / social intents we *also* try
    Ollama enrichment at high deterministic confidence — but only to fill
    in optional fields (core_claim, method, target_tags, hooks). The
    deterministic intent label, verb, and targets stay authoritative.
    """
    from .config import USE_OLLAMA

    deterministic = parse(text, world)

    # Intents where an LLM can usefully enrich even when the deterministic
    # parser was confident. Keep this list narrow — these are all already
    # social/memetic flavored.
    _ENRICH_MEMETIC = {
        "seed_belief", "spread_rumor", "create_taboo", "issue_false_order",
        "logic_exploit", "identity_attack", "sow_distrust", "incite_panic",
        "religious_framing", "sponsor_disinformation", "propaganda",
        "forge_social_proof", "invoke_belief", "talk",
    }

    if deterministic.intent == "numeric":
        return deterministic

    # Path 1: deterministic was confident enough; enrich memetic intents
    # for optional fields. Post-07b follow-up: also allow Ollama to UPGRADE
    # weak deterministic memetic fields (placeholders, single tokens, etc.)
    # but never override explicit objects, destinations, or the intent label.
    if deterministic.confidence >= 0.7:
        if (not USE_OLLAMA) or (deterministic.intent not in _ENRICH_MEMETIC):
            return deterministic
        try:
            from . import llm_parser
            ctx = _build_compact_context(world)
            llm_dict = llm_parser.parse_with_ollama(text, ctx)
        except Exception:
            llm_dict = None
        if not llm_dict:
            return deterministic

        def _upgrade(field_name, llm_key, allow_upgrade=True):
            cur = getattr(deterministic, field_name, None)
            new = llm_dict.get(llm_key)
            if not new:
                return
            if not cur:
                setattr(deterministic, field_name, new)
                return
            if allow_upgrade and is_weak_memetic_field(cur) and not is_weak_memetic_field(new):
                setattr(deterministic, field_name, new)

        _upgrade("core_claim",      "core_claim",      allow_upgrade=True)
        _upgrade("memetic_method",  "method",          allow_upgrade=True)
        _upgrade("spread_channel",  "spread_channel",  allow_upgrade=False)
        _upgrade("desired_outcome", "desired_outcome", allow_upgrade=True)
        # Stash target_tags onto modifiers so downstream sees them. We never
        # remove deterministic tags — only add LLM-discovered ones.
        for tg in (llm_dict.get("target_tags") or []):
            mod = f"target_tag:{tg}"
            if mod not in deterministic.modifiers:
                deterministic.modifiers.append(mod)
        # Stash LLM's suggested_stat too; select_memetic_stat will read it.
        st = llm_dict.get("suggested_stat")
        if isinstance(st, str) and st.upper() in {"STR","DEX","CON","INT","WIS","CHA"}:
            stat_mod = f"stat:{st.upper()}"
            if stat_mod not in deterministic.modifiers:
                deterministic.modifiers.append(stat_mod)
        return deterministic

    # Path 2: deterministic low-confidence fallback — original behavior.
    if not USE_OLLAMA:
        return deterministic

    context = _build_compact_context(world)
    try:
        from . import llm_parser
        llm_dict = llm_parser.parse_with_ollama(text, context)
    except Exception:
        llm_dict = None

    if not llm_dict:
        return deterministic

    llm_intent = _intent_from_llm_dict(llm_dict, raw_text=text)
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
    # Prompt 07: pass through memetic extras if present.
    intent.memetic_method = d.get("method")
    intent.core_claim = d.get("core_claim")
    intent.spread_channel = d.get("spread_channel")
    if d.get("target_tags"):
        # Stash on modifiers so downstream can pick them up.
        for tg in d.get("target_tags") or []:
            intent.modifiers.append(f"target_tag:{tg}")
    return intent


# Whitelist of intent strings the LLM may produce that we accept verbatim.
_LLM_INTENT_PASSTHROUGH = {
    "look","inspect","search","move","listen","wait","rest_short","rest_long",
    "attack","defend","use","talk","intimidate","bribe","sneak","hide","flee",
    "craft","loot","open","close","hack","force","lockpick","throw_at",
    "push_into","lure","perform","ask_rumor","check_inventory","check_character",
    "check_map","save","help","deploy","salvage","strip","harvest",
    # Prompt 07: memetic intent labels.
    "seed_belief","spread_rumor","create_taboo","issue_false_order",
    "logic_exploit","identity_attack","sow_distrust","incite_panic",
    "religious_framing","sponsor_disinformation","propaganda",
    "forge_social_proof","check_beliefs","check_knowledge",
    "use_password","exploit_weakness","invoke_belief",
    "show_resolutions","set_fullscreen","set_windowed","set_resolution",
    "journal_open","journal_close","journal_objectives","journal_crawlers",
    "journal_crafting","journal_achievements",
}
