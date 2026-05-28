"""Deterministic hybrid parser.

Turns free-text into an ActionIntent dict. Never decides success.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Any

from .affordances import find_affordance_by_verb, fold
from ..ui.lang import get_language


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

    # Prompt 16: mass action flag. Set when the player explicitly targets
    # everything in the room ("wszystko" / "cały pokój" / "all" / etc.).
    # The validator skips entity-name matching; the game-layer handler
    # iterates visible entities instead.
    mass_target: bool = False

    def to_dict(self):
        return self.__dict__.copy()


# Top-level fast-path intents that don't have entity targets
_QUICK_INTENTS = {
    "look":          ["rozejrzyj","rozejrzy","spójrz","spojrz","look","look around"],
    "search":        ["przeszukaj","szukaj","przetrzas","search"],
    "wait":          ["czekaj","poczekaj","wait"],
    "rest_short":    ["odpocznij","short rest","odpoczynek"],
    # P27.7 — class active ability trigger.
    "class_active":  ["umiejętność","umiejetnosc","umiejetność","umiejetnosć",
                      "klasa","class ability","ability"],
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
    # Prompt 23: removed bare "wycofaj" (collided with "wycofaj broń"
    # for the sheathe verb). Flee now requires the reflexive form
    # "wycofuj się" / "wycofaj się" which is the natural Polish anyway.
    "flee":          ["uciekaj","spierdalaj","run","flee",
                      "wycofuj się","wycofaj się","wycofaj sie","wycofuj sie"],
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
    # Prompt 22 — set_monitor previously had quick-intent cues, but
    # "monitor" matched via endswith(" monitor"), so typing
    # `sprawdź rozbity monitor` (in-game object) routed to display
    # settings. Removed entirely; the dedicated regex `mon_re` below
    # is anchored at `^` and handles both bare `monitor` and
    # `monitor N` forms.
    # Prompt 10: journal overlay
    "journal_open":       ["dziennik","journal","notatki","notes"],
    "journal_close":      ["zamknij","close","wyjdź","wyjdz","zamknij dziennik"],
    "journal_objectives": ["cele","objectives","zadania","cel"],
    "journal_crawlers":   ["crawlerzy","crawlers","znajomi"],
    "journal_crafting":   ["crafting","przepisy","recipes"],
    "journal_achievements":["osiągnięcia","osiagniecia","achievements","sukcesy"],

    # Prompt 19 — pet / companion intents. The verbs themselves live on
    # the affordance catalog (engine.affordances) for richer matching;
    # here we just list quick phrasings so the parser picks up the
    # intent class. game.py routes these to engine.companion_actions
    # rather than the normal entity-validation pipeline.
    "companion_inspect": ["sprawdź zwierzę","sprawdz zwierze","sprawdź pupila",
                          "obejrzyj zwierzę","status zwierzęcia",
                          "check pet","inspect pet"],
    "companion_feed":    ["nakarm zwierzę","nakarm zwierze","nakarm pupila",
                          "nakarm chowańca","podaj jedzenie zwierzęciu",
                          "feed pet","feed companion"],
    "companion_calm":    ["uspokój zwierzę","uspokoj zwierze","głaszcz zwierzę",
                          "pogłaszcz zwierzę","ukoj zwierzę","calm pet"],
    "companion_scout":   ["wyślij zwierzę na zwiad","wyslij zwierze na zwiad",
                          "wyślij na zwiad","wyślij pupila","wyślij zwierzę",
                          "każ zwierzęciu szukać","send pet to scout"],
    "companion_lure":    ["użyj zwierzęcia jako wabika",
                          "uzyj zwierzecia jako wabika",
                          "wabik ze zwierzęcia","użyj pupila jako wabika",
                          "use pet as lure","use pet as distraction"],

    # Quick journal tab nav.
    "journal_companions": ["towarzysze","chowańce","chowance","pupile","companions"],

    # Prompt 23 — wield / sheathe / coat. The regex below extracts the
    # target item name + optional hand modifier. Quick-intent cues
    # below are only the BARE verbs (matched via the fast-path) —
    # the regex handles the typed-with-target form.
    "sheathe":       ["wycofaj broń","wycofaj bron","schowaj broń",
                      "schowaj bron","odłóż broń","odloz bron",
                      "sheathe","stow"],

    # Prompt 20 — encounter prep.
    "prep_room":  ["przygotuj się","przygotuj sie","oceń pokój","ocen pokoj",
                   "zaplanuj","zaplanuj obronę","zaplanuj obrone",
                   "rozeznaj","co tu mam","co mam tu",
                   "prepare","prep","assess","plan defense"],
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

    # Prompt 19 audit fix N1: rewrite the player's pet alias to the
    # generic word `zwierzę` so commands like "sprawdź gęś" /
    # "nakarm szczura" / "uspokój papugę" route into the companion
    # quick-intents below. Only fires when the player actually has an
    # active pet whose catalog aliases include the typed token.
    if world is not None:
        try:
            from . import companion as _comp
            from ..content.data.pets import get_pet_template
            pet = _comp.active_pet(world)
            if pet is not None:
                tmpl = get_pet_template(pet.species_key)
                aliases = list(tmpl.get("name_aliases_pl") or [])
                aliases.append(pet.display_name_pl or "")
                aliases_folded = sorted(
                    {fold(a) for a in aliases if a},
                    key=len, reverse=True   # longer aliases first
                )
                for af in aliases_folded:
                    if not af:
                        continue
                    # Match the alias as a standalone token (start/end
                    # of string OR surrounded by non-word chars).
                    import re as _re
                    pattern = r"(?:^|(?<=\W))" + _re.escape(af) + r"(?=\W|$)"
                    if _re.search(pattern, folded):
                        folded = _re.sub(pattern, "zwierze", folded)
                        # Also touch lower so downstream patterns see it.
                        lower = _re.sub(pattern, "zwierze",
                                        fold(lower))
                        break
        except Exception:
            pass

    # ── Prompt 16: mass-action detection ─────────────────────────────────────
    # Recognize "wszystko / cały pokój / all / everything" as room-wide
    # targets. These commands ALWAYS take priority over the LLM enrichment
    # path so a model can never collapse "rozbierz wszystko" into "look".
    # Verb determines the kind of mass action.
    #
    # Verbs → mass intents:
    #   rozbierz / zdemontuj / pozyskaj                    → mass_salvage
    #   przeszukaj                                          → mass_search
    #   weź / zbierz / weź wszystko                         → mass_loot_take
    #   ograb                                               → mass_loot_loose
    #   rozbij / zniszcz / rozwal / roztrzaskaj / strzaskaj → mass_break
    # Mass-target trigger. Either an explicit "everything"-style noun
    # phrase OR a bare room reference ("pokoj" / "room") — the latter is
    # OK because the verb-gate below means it only activates for mass
    # verbs like "ogołoć pokój" / "rozbierz pokój".
    _MASS_TARGET_RE = re.compile(
        r"\b(wszystko|wszystkie|wszystkim|wszystkimi|"
        r"cały\s+pokoj|caly\s+pokoj|"
        r"cały\s+pokój|caly\s+pokój|"
        r"cale\s+pomieszczenie|całe\s+pomieszczenie|"
        r"wszystkie\s+rzeczy|"
        r"pokoj|pokój|pomieszczenie|"
        r"all|everything|every\s+single\s+thing)\b"
    )
    if _MASS_TARGET_RE.search(folded):
        # Verb→intent map. Verbs are listed in canonical Polish forms +
        # common conjugations. Match policy: exact equality OR full-verb
        # prefix (`first_token.startswith(verb)`), NOT a fixed-length
        # prefix — otherwise "rozbij" collides with "rozbierz" (both
        # share the 5-char prefix "rozbi").
        _MASS_VERB_MAP = [
            # mass_break comes first so its short, distinctive verbs win
            # before any longer stem accidentally matches.
            (("rozbij","rozbijam","rozbic","rozbić","rozwal","rozwalam",
              "rozwalic","rozwalić","roztrzaskaj","roztrzaskac","roztrzaskać",
              "strzaskaj","strzaskac","strzaskać","zniszcz","zniszczyc",
              "zniszczyć","niszcz","niszczyc","niszczyć",
              "break","smash","destroy","wreck","shatter"),
             "mass_break"),
            (("rozbierz","rozbieram","rozbieraj","rozebrac","rozebrać",
              "zdemontuj","zdemontowac","zdemontować","demontuj",
              "pozyskaj","pozyskac","pozyskać","ogołoc","ogoloc","ogołoć",
              "ogoloć","strip","dismantle","salvage","scrap","harvest"),
             "mass_salvage"),
            (("przeszukaj","przeszukac","przeszukać","przetrzasnij",
              "przetrzasnac","przetrząsnij","przetrząsnąć",
              "search","rifle","scan"),
             "mass_search"),
            (("wez","weź","zbierz","zbieram","pick","take","grab","collect",
              "podnies","podnieś","podnoszę","podnos"),
             "mass_loot_take"),
            (("ograb","obrabuj","obrabowac","obrabować","loot","rob"),
             "mass_loot_loose"),
        ]
        first_token = folded.split()[0] if folded.strip() else ""
        for verb_set, mass_intent in _MASS_VERB_MAP:
            if any(first_token == v or first_token.startswith(v)
                   for v in verb_set):
                intent.intent = mass_intent
                intent.verb = first_token
                intent.mass_target = True
                intent.confidence = 0.95
                return intent

    # ── Fast-path quick intents ──────────────────────────────────────────────
    for ikey, cues in _QUICK_INTENTS.items():
        for cue in cues:
            cf = fold(cue)
            if folded == cf or folded.startswith(cf + " ") or folded.endswith(" " + cf):
                # Prompt 14: "przeszukaj X" with an explicit target should
                # route to `loot` (container/corpse search) instead of the
                # no-target global search. The quick-intent fast-path only
                # matches the bare verb; anything after it implies a target.
                if ikey == "search" and folded.startswith(cf + " "):
                    rest = folded[len(cf) + 1:].strip()
                    if rest and rest not in ("pokoj", "pokój", "room", "wszystko"):
                        intent.intent = "loot"
                        intent.verb = cue
                        intent.targets.append(_strip_articles(rest))
                        intent.confidence = 0.9
                        return intent
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

    # P28.3 (P27-UX-23) — movement UX normalization. Accept bare
    # cardinal directions as movement: "wschód" → idź wschód, "n" →
    # idź północ, etc. Maps single-letter (n/s/e/w) and short
    # English/Polish forms to a canonical exit label so the validator
    # can find the matching room exit. Anything with leading whitespace
    # was already stripped by `folded`.
    BARE_DIRS = {
        "n": "północ", "p": "północ", "pn": "północ",
        "polnoc": "północ", "północ": "północ", "north": "północ",
        "s": "południe", "pd": "południe",
        "poludnie": "południe", "południe": "południe", "south": "południe",
        "e": "wschód", "w_": "wschód",  # avoid clash with "w"
        "wschod": "wschód", "wschód": "wschód", "east": "wschód",
        "w": "zachód", "z": "zachód",
        "zachod": "zachód", "zachód": "zachód", "west": "zachód",
        "u": "góra", "g": "góra",
        "gora": "góra", "góra": "góra", "up": "góra",
        "d": "dół",
        "dol": "dół", "dół": "dół", "down": "dół",
    }
    if folded in BARE_DIRS:
        intent.intent = "move"
        intent.verb = "idź"
        intent.destination = BARE_DIRS[folded]
        intent.confidence = 0.85
        return intent

    # ── P29.23 — Cooking + reading verbs ───────────────────────────────────
    # `gotuj`/`piecz`/`smaż` <X>     → cook (raw meat → cooked food)
    # `czytaj`/`przeczytaj`         → read (lore items, posters)
    import re as _re_cook
    cook_re = _re_cook.compile(
        r"^(?:gotuj|gotować|piecz|piec|smaż|smaz|smazyc|smażyć|usmaz|"
        r"upiec|cook|fry|roast)(?:\s+(.+))?$")
    cm = cook_re.match(folded)
    if cm:
        intent.intent = "cook"
        intent.verb = "gotuj"
        target_name = (cm.group(1) or "").strip()
        if target_name:
            intent.targets.append(_strip_articles(target_name))
        intent.confidence = 0.9
        return intent

    read_re = _re_cook.compile(
        r"^(?:czytaj|przeczytaj|read)(?:\s+(.+))?$")
    rm = read_re.match(folded)
    if rm:
        intent.intent = "read"
        intent.verb = "czytaj"
        target_name = (rm.group(1) or "").strip()
        if target_name:
            intent.targets.append(_strip_articles(target_name))
        intent.confidence = 0.9
        return intent

    # ── P29.19 — Credit-sink commands ──────────────────────────────────────
    # `trening <stat>`        → train_stat (80 kr → +1 to one stat, once per stat)
    # `łapówka <sponsor>`     → bribe_sponsor (20 kr → +2 attention)
    # `zamów pakiet [<sponsor>]` → call_pod (50 kr → spawn pod in room)
    # `wzmocnij hp|ac`        → upgrade_loadout (100 kr → +5 HP or +1 AC)
    import re as _re_cs
    train_re = _re_cs.compile(
        r"^(?:trening|trenuj|trenowanie|train)\s+(.+)$")
    tm = train_re.match(folded)
    if tm:
        intent.intent = "train_stat"
        intent.verb = "trening"
        intent.targets.append(_strip_articles(tm.group(1)))
        intent.confidence = 0.9
        return intent

    bribe_re = _re_cs.compile(
        r"^(?:łapówka|lapowka|łapowka|bribe)\s+(.+)$")
    bm = bribe_re.match(folded)
    if bm:
        intent.intent = "bribe_sponsor"
        intent.verb = "łapówka"
        intent.targets.append(_strip_articles(bm.group(1)))
        intent.confidence = 0.9
        return intent

    # call-pod uses noun "pakiet" + optional sponsor name
    pod_call_re = _re_cs.compile(
        r"^(?:zamów|zamow|wezwij|order|call)"
        r"\s+(?:pakiet|paczkę|paczke|drop|pod)(?:\s+(.+))?$")
    pm = pod_call_re.match(folded)
    if pm:
        intent.intent = "call_pod"
        intent.verb = "zamów"
        target_name = (pm.group(1) or "").strip()
        if target_name:
            intent.targets.append(_strip_articles(target_name))
        intent.confidence = 0.9
        return intent

    upgrade_re = _re_cs.compile(
        r"^(?:wzmocnij|ulepsz|upgrade)\s+(hp|ac|punkty|pancerz)$")
    um = upgrade_re.match(folded)
    if um:
        intent.intent = "upgrade_loadout"
        intent.verb = "wzmocnij"
        which = um.group(1).lower()
        if which in ("hp", "punkty"):
            intent.targets.append("hp")
        else:
            intent.targets.append("ac")
        intent.confidence = 0.9
        return intent

    # ── P29.14 — Apply an enhancement to a weapon/armor ────────────────────
    # "nałóż <enhancement> na <target>" / "zamontuj <X> na <Y>" /
    # "apply <X> to <Y>" — produces intent="apply_enhancement" with the
    # enhancement in `tool` and the target item in `targets[0]`.
    import re as _re_app
    apply_re = _re_app.compile(
        r"^(?:nałóż|naloz|nałozyć|załóż|zaloz|zamontuj|zaaplikuj|"
        r"apply|coat|attach)\s+(.+?)\s+(?:na|on|to|do)\s+(.+)$")
    app_m = apply_re.match(folded)
    if app_m:
        intent.intent = "apply_enhancement"
        intent.verb = "nałóż"
        intent.tool = _strip_articles(app_m.group(1))
        intent.targets.append(_strip_articles(app_m.group(2)))
        intent.confidence = 0.9
        return intent

    # ── P29.56 — Emergent crafting: experiment with N materials ────────────
    # "eksperymentuj X, Y, Z" / "zmieszaj X i Y i Z" / "spróbuj X+Y+Z"
    # Materiały rozdzielone przecinkiem, " i ", " oraz ", " z ", " + "
    import re as _re_exp
    exp_re = _re_exp.compile(
        r"^(?:eksperymentuj|zmieszaj|spróbuj|sprobuj|łącz|lacz|combine|"
        r"experiment|mix)\s+(.+)$")
    exp_m = exp_re.match(folded)
    if exp_m:
        intent.intent = "experiment"
        intent.verb = "eksperymentuj"
        raw_body = exp_m.group(1).strip()
        for sep in (" oraz ", " i ", " z ", " + "):
            raw_body = raw_body.replace(sep, ",")
        parts = [p.strip() for p in raw_body.split(",") if p.strip()]
        intent.targets = parts
        intent.confidence = 0.9
        return intent

    # ── P29.57b — Open a box (skrzynka) — dedykowany intent ────────────────
    # "otwórz skrzynkę X" / "otwórz <nazwa>" gdy slowo "skrzynka" / "skrzynkę"
    # / "premia" w komendzie. Plus aliasy: paczka widowni / paczkę bossa.
    import re as _re_box
    box_re = _re_box.compile(
        r"^(?:otwórz|otworz|rozpakuj|odbierz)\s+"
        r"(?:skrzynkę|skrzynke|skrzynka|premię|premie|paczkę|paczke|paczka)"
        r"(?:\s+(.+))?$")
    box_m = box_re.match(folded)
    if box_m:
        intent.intent = "open_box"
        intent.verb = "otwórz"
        target_name = (box_m.group(1) or "").strip()
        if target_name:
            intent.targets.append(_strip_articles(target_name))
        intent.confidence = 0.94
        return intent

    # ── P29.57e — Wiercimajster: codex bossów ─────────────────────────────
    # „wezwij trenera" / „porozmawiaj z wiercimajstrem" / „kodeks bossów"
    # → intent consult_codex. Gated do safehouse'u w handlerze.
    import re as _re_wier
    wier_re = _re_wier.compile(
        r"^(?:wezwij|wezwac|wezwę|porozmawiaj|rozmawiaj|"
        r"otworz|otwórz|przejrzyj|sprawdz|sprawdź|pokaz|pokaż)"
        r"\s+(?:z\s+)?"
        r"(?:trenera|wiercimajstra|wiercimajstrem|kodeks|kodeksu)"
        r"(?:\s+(?:bossow|bossów))?$"
        r"|^kodeks(?:\s+(?:bossow|bossów))?$"
        r"|^wiercimajster$|^trener$")
    if wier_re.match(folded):
        intent.intent = "consult_codex"
        intent.verb = "wezwij"
        intent.confidence = 0.95
        return intent

    # ── P29.10 — Open a sponsor drop pod (mid-floor gift) ──────────────────
    # "otwórz/rozbij/zgarnij pakiet" (sponsorski) — drop-pods are how
    # mid-floor sponsor gifts now arrive (was: queued for safehouse).
    import re as _re_pod
    pod_re = _re_pod.compile(
        r"^(?:otwórz|otworz|rozbij|zgarnij|odbierz|open|claim)"
        r"\s+(?:pakiet|paczke|paczkę|pakunek|kapsule|kapsułę|drop|pod)"
        r"(?:\s+(.+))?$")
    pod_m = pod_re.match(folded)
    if pod_m:
        intent.intent = "open_pod"
        intent.verb = "otwórz"
        target_name = (pod_m.group(1) or "").strip()
        if target_name:
            intent.targets.append(_strip_articles(target_name))
        intent.confidence = 0.92
        return intent

    # ── P29.7 — Pick up a deployed trap (fallback when placed wrong) ───────
    # "zwiń pułapkę X" / "podnieś pułapkę X" / "rozbrój pułapkę X"
    import re as _re_tp
    trap_pickup_re = _re_tp.compile(
        r"^(?:zwiń|zwin|podnies|podnieś|rozbrój|rozbroj|disarm|pickup)"
        r"\s+(?:pułapkę|pulapke|pułapka|pulapka|trap)(?:\s+(.+))?$")
    tp_m = trap_pickup_re.match(folded)
    if tp_m:
        intent.intent = "trap_pickup"
        intent.verb = "podnieś"
        target_name = (tp_m.group(1) or "").strip()
        if target_name:
            intent.targets.append(_strip_articles(target_name))
        intent.confidence = 0.9
        return intent

    # ── P29.4 — Buy / sell follow-ups in black-market safehouses ────────────
    # "kup <X>" → bm_buy   ;   "sprzedaj <X>" → bm_sell
    import re as _re_bm
    bm_buy_re = _re_bm.compile(r"^(?:kup|kupić|buy)\s+(.+)$")
    bm_sell_re = _re_bm.compile(r"^(?:sprzedaj|sprzedać|sell)\s+(.+)$")
    bm_m = bm_buy_re.match(folded)
    if bm_m:
        intent.intent = "bm_buy"
        intent.verb = "kup"
        intent.targets.append(_strip_articles(bm_m.group(1)))
        intent.confidence = 0.9
        return intent
    bm_m = bm_sell_re.match(folded)
    if bm_m:
        intent.intent = "bm_sell"
        intent.verb = "sprzedaj"
        intent.targets.append(_strip_articles(bm_m.group(1)))
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

    # ── Prompt 23: "dobądź X" / "dobądź X w lewą rękę" / "wyciągnij X"
    # — wield an inventory item. Hand modifier optional (defaults main).
    # "wycofaj broń" (sheathe) is handled via the quick-intent table
    # above because it has no target.
    # Hand alternatives must match the FOLDED input (no diacritics).
    # "lewą rękę" folds to "lewa reke" (NOT "reka"), "prawą rękę" → "prawa reke".
    # Prompt 23: removed `wyciągnij` from the verb set — it collided with
    # `wyciągnij X z Y` (extract for salvage). `dobądź` / `chwyć` /
    # `uzbrój się` are the canonical Polish wield verbs.
    wield_re = re.compile(
        r"^(?:dobądź|dobadz|chwyć|chwyc|"
        r"uzbrój się|uzbroj sie|wield|equip)"
        r"\s+(?P<item>.+?)"
        r"(?:\s+(?:w|do)\s+(?P<hand>lewą\s+rękę|lewa\s+reke|"
        r"prawą\s+rękę|prawa\s+reke|główną\s+rękę|glowna\s+reke|"
        r"off\s+hand|main\s+hand))?$"
    )
    wm = wield_re.match(folded)
    if wm:
        intent.intent = "wield"
        intent.verb = "wield"
        intent.targets.append(_strip_articles(wm.group("item")))
        hand_str = (wm.group("hand") or "").lower()
        if "lew" in hand_str or "off" in hand_str:
            intent.modifiers.append("hand:offhand")
        else:
            intent.modifiers.append("hand:main")
        intent.confidence = 0.92
        return intent

    # ── Prompt 23: "nasącz X Y" — coat weapon X with substance Y.
    # Two-target form. Placed before generic verb routing so it doesn't
    # collide with single-target verbs.
    coat_re = re.compile(
        r"^(?:nasącz|nasacz|posmaruj|pokryj|powlecz|namaść|namasc|"
        r"coat|imbue|slather|anoint)"
        r"\s+(?P<weapon>.+?)\s+(?P<substance>.+)$"
    )
    cm = coat_re.match(folded)
    if cm:
        intent.intent = "coat_weapon"
        intent.verb = "coat_weapon"
        intent.targets.append(_strip_articles(cm.group("weapon")))
        intent.targets.append(_strip_articles(cm.group("substance")))
        intent.confidence = 0.9
        return intent

    # ── Prompt 22: monitor switcher. Anchored at `^` to avoid matching
    # in-game objects with "monitor" in their name (e.g. "rozbity monitor").
    # Both bare `monitor` (lists displays) and `monitor N` (switches)
    # are handled here.
    mon_re = re.compile(
        r"^(?:monitor|ekran(?:\s+nr)?|display|wyświetlacz|wyswietlacz)"
        r"(?:\s+(?P<idx>\d{1,2}))?$"
    )
    mm = mon_re.match(folded)
    if mm:
        intent.intent = "set_monitor"
        intent.verb = "set_monitor"
        idx_str = mm.group("idx")
        if idx_str is not None:
            try:
                intent.modifiers.append(f"index:{int(idx_str)}")
            except (ValueError, TypeError):
                pass
        intent.confidence = 0.95
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

    # ── Consume: "skonsumuj X" / "zjedz X" / "wypij X" / "eat X" / "drink X" ──
    # P27.9 (P27-UX-15) — eat/drink alias for `use X` with food semantics.
    # The handler enforces "food" or "consumable" tag and runs heal/buff
    # effects per item key (snack_bar, coffee, etc.).
    #
    # IMPORTANT: defer to `eat_corpse` (P24 corpse affordance) when the
    # target word references a body/corpse. We don't want `zjedz ciało
    # szczurka` to hit the snack-bar path.
    consume_re = re.compile(
        r"^(?:skonsumuj|zjedz|wypij|eat|drink|spożyj|spozyj)\s+(.+)$")
    cm = consume_re.match(folded)
    if cm:
        tgt = _strip_articles(cm.group(1))
        if not any(corpse_kw in tgt for corpse_kw in
                   ("ciał", "cial", "trup", "padlin", "zwłok", "zwlok",
                    "corpse", "body", "szczątk", "szczatk")):
            intent.intent = "consume"
            intent.verb = "consume"
            intent.targets.append(tgt)
            intent.confidence = 0.9
            return intent
        # Else fall through — the affordance-based eat_corpse parser
        # will pick it up downstream.

    # ── Use: "użyj X na Y" / "use X on Y" ────────────────────────────────────
    use_re = re.compile(r"^(?:uzyj|użyj|use)\s+(.+?)(?:\s+(?:na|on|at|aby|do)\s+(.+))?$")
    um = use_re.match(folded)
    if um:
        intent.intent = "use"
        intent.verb = "use"
        intent.tool = _strip_articles(um.group(1))
        if um.group(2):
            intent.targets.append(_strip_articles(um.group(2)))
        else:
            # P27.5 (P27-UX-14): `użyj X` single-arg form. Without
            # this, validator gets empty targets and the inventory-
            # first resolution (P24.6) never fires — the player sees
            # "Nie widzisz tu tego" even with the item in their pocket.
            # Copy `tool` into `targets[0]` so the standard resolver
            # finds it.
            intent.targets.append(intent.tool)
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
            # P26c class-fix: previously this loop appended each
            # remaining token as a separate target string — so
            # "zdemontuj rozbity monitor" became targets=["rozbity",
            # "monitor"]. The validator then only saw "rozbity" and
            # surfaced an ambiguity prompt for every entity starting
            # with that word. Now we JOIN the non-stop tokens into
            # one target phrase, so multi-word adjective+noun names
            # resolve uniquely.
            rest_tokens = [tok for tok in tokens[1:] if tok not in _STOP]
            if rest_tokens:
                intent.targets.append(" ".join(rest_tokens))
            intent.confidence = 0.6 if intent.targets else 0.7
            return intent

    # Prompt 16: bare exit-label / destination commands. If the player
    # typed something that doesn't start with any known verb but matches
    # an exit label or a known room title visible from here, treat it as
    # a `move` intent. Prompt 18: also tolerate Polish inflections via
    # _polish_match — "przejścia" matches an exit labeled "przejście".
    if world is not None:
        floor = getattr(world, "current_floor", None)
        room = floor.current_room() if floor is not None else None
        if room is not None and getattr(room, "exits", None):
            from .validation import _polish_match, _strip_movement_prepositions
            target_clean = _strip_movement_prepositions(folded)
            target_f = fold(target_clean)
            for label, ed in room.exits.items():
                if ed.get("hidden"):
                    continue
                if _polish_match(target_f, fold(label)):
                    intent.intent = "move"
                    intent.verb = "move"
                    intent.destination = label
                    intent.confidence = 0.85
                    return intent
            # Also check destination room titles visible from here.
            for label, ed in room.exits.items():
                if ed.get("hidden"):
                    continue
                tgt_room = floor.rooms.get(ed.get("target", ""))
                if tgt_room is None:
                    continue
                if ed.get("target", "") not in (floor.discovered_room_ids or set()) \
                        and ed.get("target", "") not in (floor.known_room_ids or set()):
                    continue
                title_f = fold(tgt_room.display_short_title())
                if title_f and _polish_match(target_f, title_f):
                    intent.intent = "move"
                    intent.verb = "move"
                    intent.destination = label
                    intent.confidence = 0.85
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


# Prompt 13: availability gating now lives in `llm_roles`. The parser
# defers to `llm_roles.is_role_available(ROLE_INTENT)` which checks the
# role flag, the cached Ollama reachability, and whether the intent
# model is actually installed. Old `_OLLAMA_AVAILABLE_CACHE` removed.

def _intent_llm_available() -> bool:
    try:
        from ..llm import llm_roles
        return llm_roles.is_role_available(llm_roles.ROLE_INTENT)
    except Exception:
        return False


def reset_ollama_cache() -> None:
    """Back-compat shim — tests still call this. Forwards to the new
    central availability cache."""
    try:
        from ..llm import llm_roles
        llm_roles.reset_availability_cache()
    except Exception:
        pass


def parse_with_optional_llm(text: str, world=None) -> ActionIntent:
    """Pipeline: deterministic first; if confidence is low and Ollama is
    enabled AND reachable, call the LLM to produce a fallback intent.
    Either way, return an ActionIntent for the validator to interpret.
    Never raise.

    Prompt-07b follow-up: for memetic / social intents we *also* try
    Ollama enrichment at high deterministic confidence — but only to fill
    in optional fields (core_claim, method, target_tags, hooks). The
    deterministic intent label, verb, and targets stay authoritative.

    Prompt 13: all "is the LLM reachable" gating now lives in
    `llm_roles.is_role_available(ROLE_INTENT)`. The intent role can be
    independently disabled even if other roles (narrator, lootbox) are
    enabled.
    """
    deterministic = parse(text, world)

    # Prompt 16: mass-action commands MUST stay deterministic. The LLM is
    # never asked to interpret "rozbierz wszystko" / "weź wszystko" /
    # "rozbij wszystko" — a model that doesn't recognize "wszystko" as a
    # mass-target keyword would otherwise collapse the verb into a
    # generic "look" or similar and the playtest already showed this
    # failure mode. Hard guardrail: deterministic wins, no enrichment.
    if deterministic.mass_target or deterministic.intent.startswith("mass_"):
        return deterministic

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
        # Memetic enrichment branch: only call out when (a) the player
        # phrasing is one of the intents that benefits from richer
        # interpretation AND (b) the intent role is enabled AND its
        # model is actually installed AND Ollama is reachable.
        if deterministic.intent not in _ENRICH_MEMETIC:
            return deterministic
        if not _intent_llm_available():
            return deterministic
        try:
            from ..llm import llm_parser
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
    if not _intent_llm_available():
        return deterministic

    context = _build_compact_context(world)
    try:
        from ..llm import llm_parser
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
    # Prompt 16: mass-action intents. The LLM is allowed to surface them
    # but deterministic detection already runs first; the whitelist just
    # prevents the validator from rejecting them as unknown if an LLM
    # path produces one.
    "mass_salvage","mass_search","mass_loot_take","mass_loot_loose","mass_break",
}
