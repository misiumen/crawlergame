"""Affordance system — what can reasonably be done with an entity."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# Time costs (minutes) — used by validator/resolution.
TIME_LOOK    = 1
TIME_INSPECT = 5
TIME_SEARCH  = 30
TIME_MOVE    = 10
TIME_LISTEN  = 5
TIME_TALK    = 15
TIME_FIGHT   = 5
TIME_REST_SHORT = 60
TIME_REST_LONG  = 6 * 60
TIME_CRAFT      = 60


@dataclass
class Affordance:
    key: str
    verbs_pl: List[str] = field(default_factory=list)
    verbs_en: List[str] = field(default_factory=list)
    required_state: Dict = field(default_factory=dict)
    required_tool_tags: List[str] = field(default_factory=list)
    accepted_target_types: List[str] = field(default_factory=list)
    stat: Optional[str] = None
    base_dc: int = 10
    time_cost: int = 5
    risk_tags: List[str] = field(default_factory=list)
    success_effects: List = field(default_factory=list)
    partial_effects: List = field(default_factory=list)
    failure_effects: List = field(default_factory=list)
    critical_failure_effects: List = field(default_factory=list)
    class_affinity: Optional[str] = None
    audience_effect: int = 0


# Built-in affordances. Entities reference these by key.
AFFORDANCE_CATALOG: Dict[str, Affordance] = {}


def register(a: Affordance):
    AFFORDANCE_CATALOG[a.key] = a
    return a


# ── Core verb-only affordances ────────────────────────────────────────────────

register(Affordance("look",
    verbs_pl=["rozejrzyj się","rozejrzyj sie","spójrz","spojrz","patrz","patrze","patrzę"],
    verbs_en=["look","look around"],
    time_cost=1))

register(Affordance("inspect",
    verbs_pl=["sprawdź","sprawdz","obejrzyj","zbadaj"],
    verbs_en=["inspect","examine"],
    time_cost=TIME_INSPECT))

register(Affordance("search",
    verbs_pl=["przeszukaj","szukaj","przetrząsnij","przetrzasnij"],
    verbs_en=["search"],
    time_cost=TIME_SEARCH, stat="WIS", base_dc=10))

register(Affordance("listen",
    verbs_pl=["nasłuchuj","nasluchuj","posłuchaj","posluchaj"],
    verbs_en=["listen"],
    time_cost=TIME_LISTEN, stat="WIS", base_dc=8))

register(Affordance("move",
    verbs_pl=["idź","idz","przejdź","przejdz","wejdź","wejdz"],
    verbs_en=["go","move","enter"],
    time_cost=TIME_MOVE))

register(Affordance("wait",
    verbs_pl=["czekaj","poczekaj","poczekam"],
    verbs_en=["wait"],
    time_cost=15))

register(Affordance("rest_short",
    verbs_pl=["odpocznij","krótki odpoczynek","krotki odpoczynek"],
    verbs_en=["rest","short rest"],
    time_cost=TIME_REST_SHORT))

register(Affordance("rest_long",
    verbs_pl=["śpij","spij","wyśpij","wyspij","długi odpoczynek"],
    verbs_en=["sleep","long rest"],
    time_cost=TIME_REST_LONG))

# ── Object/entity affordances ─────────────────────────────────────────────────

register(Affordance("push_into",
    verbs_pl=["wepchnij","pchnij","popchnij"],
    verbs_en=["push","shove","push into"],
    stat="STR", base_dc=13, time_cost=2,
    risk_tags=["dangerous"], class_affinity="environment", audience_effect=5))

register(Affordance("throw_at",
    verbs_pl=["rzuć","rzuc","cisnij","ciśnij","miotaj"],
    verbs_en=["throw","hurl"],
    stat="DEX", base_dc=12, time_cost=1, class_affinity="environment", audience_effect=3))

register(Affordance("hack",
    verbs_pl=["zhakuj","hakuj","włam","wlam","obejdź","obejdz"],
    verbs_en=["hack","crack"],
    stat="INT", base_dc=14, time_cost=15, class_affinity="tech"))

register(Affordance("force",
    verbs_pl=["wyłam","wylam","wyważ","wywaz"],
    verbs_en=["force","break open","pry open"],
    stat="STR", base_dc=14, time_cost=10, class_affinity="melee"))

# Prompt 12: distinct `break` affordance for object destruction.
# `force` is for locked doors / panels (a pry/leverage check); `break`
# is for fragile or salvageable objects (mirrors, fixtures, monitors,
# windows). Several entity templates already reference `break` — this
# registration closes the catalog mismatch.
register(Affordance("break",
    verbs_pl=["rozbij","rozbijam","rozbic","roztrzaskaj","roztrzaskac",
              "zniszcz","zniszczyc","strzaskaj","strzaskac","rozwal",
              "kopnij","kopniecie","stłucz","stluc","stluc","walnij"],
    verbs_en=["break","smash","shatter","destroy","wreck","kick"],
    stat="STR", base_dc=11, time_cost=4,
    risk_tags=["noise","damages_item"],
    class_affinity="environment", audience_effect=2))

register(Affordance("lockpick",
    verbs_pl=["wytrych","otwórz zamek","otworz zamek"],
    verbs_en=["lockpick","pick lock"],
    stat="DEX", base_dc=13, time_cost=10,
    required_tool_tags=["lockpick"], class_affinity="stealth"))

register(Affordance("talk",
    verbs_pl=["pogadaj","porozmawiaj","zagadaj","powiedz"],
    verbs_en=["talk","speak","chat"],
    stat="CHA", base_dc=10, time_cost=TIME_TALK, class_affinity="diplomacy"))

register(Affordance("intimidate",
    verbs_pl=["zastrasz","zagroź","zagroz","groź","groz"],
    verbs_en=["intimidate","threaten"],
    stat="CHA", base_dc=13, time_cost=5, class_affinity="showmanship"))

register(Affordance("bribe",
    verbs_pl=["przekup","zaoferuj kredyty"],
    verbs_en=["bribe","pay off"],
    stat="CHA", base_dc=11, time_cost=5, class_affinity="diplomacy"))

register(Affordance("attack",
    verbs_pl=["zaatakuj","atakuj","uderz","tnij","dźgnij","dzgnij","walnij"],
    verbs_en=["attack","hit","strike","stab"],
    stat="STR", base_dc=10, time_cost=TIME_FIGHT, class_affinity="melee"))

register(Affordance("shoot",
    verbs_pl=["strzel","strzelaj"],
    verbs_en=["shoot","fire"],
    stat="DEX", base_dc=10, time_cost=TIME_FIGHT,
    required_tool_tags=["ranged"], class_affinity="ranged"))

register(Affordance("sneak",
    verbs_pl=["skradaj się","skradaj sie","cicho","skradnij"],
    verbs_en=["sneak","stealth"],
    stat="DEX", base_dc=12, time_cost=5, class_affinity="stealth"))

register(Affordance("hide",
    verbs_pl=["ukryj się","ukryj sie","schowaj się","schowaj sie"],
    verbs_en=["hide"],
    stat="DEX", base_dc=11, time_cost=5, class_affinity="stealth"))

register(Affordance("flee",
    verbs_pl=["uciekaj","wycofaj się","wycofaj sie","spierdalaj"],
    verbs_en=["flee","run"],
    stat="DEX", base_dc=10, time_cost=2, class_affinity="survival"))

register(Affordance("use",
    verbs_pl=["użyj","uzyj","aktywuj"],
    verbs_en=["use","activate"],
    time_cost=5))

register(Affordance("open",
    verbs_pl=["otwórz","otworz"],
    verbs_en=["open"],
    time_cost=2))

register(Affordance("close",
    verbs_pl=["zamknij"],
    verbs_en=["close"],
    time_cost=2))

register(Affordance("loot",
    verbs_pl=["zbierz","podnieś","podnies","lootuj","weź","wez","weż","weź",
              "ograb","ograbiam","ograbic","obrabuj","obrabowac","przeszukaj"],
    verbs_en=["take","loot","pick up","grab","rob","rifle"],
    time_cost=2))

register(Affordance("craft",
    verbs_pl=["zrób","zrob","wytwórz","wytworz","craftuj","skleć","sklec","skleic",
              "robię","robie","tworzę","tworze","owijam"],
    verbs_en=["craft","make","build","fashion","tape together"],
    stat="INT", base_dc=11, time_cost=TIME_CRAFT, class_affinity="crafting"))

register(Affordance("salvage",
    verbs_pl=["zdemontuj","odzyskaj","rozbierz","rozłóż","rozloz","rozkręć","rozkrec",
              "rozwal i weź","rozbij na części","odzyskuję części"],
    verbs_en=["salvage","dismantle","break down","recover","strip down"],
    stat="STR", base_dc=10, time_cost=20, class_affinity="survival",
    risk_tags=["noise","damages_item"]))

register(Affordance("strip",
    verbs_pl=["zerwij","zedrzyj","zdejmij ubrania","przeszukaj i zedrzyj"],
    verbs_en=["strip","pry off","tear off"],
    stat="DEX", base_dc=10, time_cost=15, class_affinity="survival",
    risk_tags=["social_suspicion"]))

register(Affordance("harvest",
    verbs_pl=["pozyskaj","wycinam","wytnij","zbieraj organy","wytnij kości"],
    verbs_en=["harvest","carve","reap"],
    stat="WIS", base_dc=11, time_cost=20, class_affinity="survival",
    risk_tags=["disease_risk"]))

register(Affordance("repair",
    verbs_pl=["napraw"],
    verbs_en=["repair","fix"],
    stat="INT", base_dc=12, time_cost=30, class_affinity="tech"))

register(Affordance("lure",
    verbs_pl=["zwab","przywab"],
    verbs_en=["lure","bait"],
    stat="CHA", base_dc=12, time_cost=3, class_affinity="stealth"))

register(Affordance("perform",
    verbs_pl=["wystąp","wystap","pozuj"],
    verbs_en=["perform","pose"],
    stat="CHA", base_dc=11, time_cost=5, class_affinity="showmanship", audience_effect=10))

# Gap 4: deploy a crafted/portable trap or device into the current room
register(Affordance("deploy",
    verbs_pl=["rozstaw","ustaw","podłóż","podloz","zamontuj","rozłóż","rozloz",
              "rozłożę","rozloze","stawiam","kładę pułapkę","kladę pułapkę",
              "kladk","podstaw"],
    verbs_en=["deploy","place","set","plant","rig","arm"],
    stat="DEX", base_dc=11, time_cost=5, class_affinity="trap",
    risk_tags=["noise"]))


# ── Prompt 19 — pet / companion affordances ────────────────────────────────
# Routed by parser_core to engine.companion_actions rather than the
# normal entity-targeting resolver — `accepted_target_types` left empty.

register(Affordance("companion_inspect",
    verbs_pl=["sprawdź zwierzę","sprawdz zwierze","sprawdź pupila",
              "obejrzyj zwierzę","obejrzyj pupila","zobacz zwierzę",
              "status zwierzęcia"],
    verbs_en=["check pet","inspect pet","look at pet"],
    time_cost=1))

register(Affordance("companion_feed",
    verbs_pl=["nakarm zwierzę","nakarm zwierze","nakarm pupila",
              "podaj jedzenie zwierzęciu","daj jeść zwierzęciu","nakarm chowańca"],
    verbs_en=["feed pet","feed companion"],
    time_cost=3))

register(Affordance("companion_calm",
    verbs_pl=["uspokój zwierzę","uspokoj zwierze","głaszcz zwierzę",
              "głaszcz pupila","pogłaszcz zwierzę","ukoj zwierzę",
              "uspokój pupila"],
    verbs_en=["calm pet","soothe pet","pet companion"],
    stat="CHA", base_dc=10, time_cost=5))

register(Affordance("companion_scout",
    verbs_pl=["wyślij zwierzę na zwiad","wyslij zwierze na zwiad",
              "wyślij na zwiad","poślij zwierzę na zwiad",
              "wyślij pupila","każ zwierzęciu szukać","wyślij zwierzę"],
    verbs_en=["send pet to scout","scout with pet","send pet"],
    stat="WIS", base_dc=11, time_cost=15,
    risk_tags=["noise","pet_risk"]))

register(Affordance("companion_lure",
    verbs_pl=["użyj zwierzęcia jako wabika","uzyj zwierzecia jako wabika",
              "wabik ze zwierzęcia","użyj pupila jako wabika",
              "użyj zwierzęcia jako odwrócenia uwagi"],
    verbs_en=["use pet as lure","use pet as distraction","pet decoy"],
    stat="CHA", base_dc=12, time_cost=5,
    risk_tags=["noise","pet_risk"], audience_effect=2))


# ── Prompt 20 — encounter prep ────────────────────────────────────────────

register(Affordance("prep_room",
    verbs_pl=["przygotuj się","oceń pokój","ocen pokoj",
              "zaplanuj","zaplanuj obronę","zaplanuj obrone",
              "co mam tu","co tu mam","sprawdź pokój pod kątem",
              "rozeznaj"],
    verbs_en=["prepare","prep","assess","plan defense","scout room"],
    time_cost=1))


def find_affordance_by_verb(verb: str, lang: str = "pl") -> Optional[Affordance]:
    """Match a verb root against any affordance's verb list. Polish-stem aware.

    Prompt 19 audit fix S3: stem-matching delegates to
    `engine.polish_text.verb_stem_match` so all verb-side matching in
    the codebase uses one strategy. Behavior is unchanged: scaled 4/5/6
    stem length based on candidate length.
    """
    if not verb:
        return None
    from .polish_text import fold as _f, verb_stem_match
    folded = _f(verb)
    if not folded:
        return None

    best = None
    for aff in AFFORDANCE_CATALOG.values():
        candidates = aff.verbs_pl if lang == "pl" else aff.verbs_en
        for cand in candidates:
            cf = _f(cand)
            if cf == folded:
                return aff
            if verb_stem_match(folded, cf):
                best = aff if best is None else best
    if best:
        return best
    # Cross-lang fallback (exact match only — keeps EN players' English
    # verbs working even when running with lang="pl").
    other = "en" if lang == "pl" else "pl"
    if other != lang:
        for aff in AFFORDANCE_CATALOG.values():
            for cand in (aff.verbs_en if other == "en" else aff.verbs_pl):
                if _f(cand) == folded:
                    return aff
    return None


# ASCII fold for Polish diacritics
_FOLD = str.maketrans({
    "ą":"a","ć":"c","ę":"e","ł":"l","ń":"n","ó":"o","ś":"s","ź":"z","ż":"z",
    "Ą":"a","Ć":"c","Ę":"e","Ł":"l","Ń":"n","Ó":"o","Ś":"s","Ź":"z","Ż":"z",
})


def _fold(s: str) -> str:
    return s.lower().translate(_FOLD).strip()


def fold(s: str) -> str:
    return _fold(s)
