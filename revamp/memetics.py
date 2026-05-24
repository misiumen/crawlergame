"""Memetic / belief-seed runtime (Prompt 07).

Belief seeds are persistent social-engineering effects that the player can
plant into the world: rumors, lies, false orders, taboos, logic exploits,
symbolic attacks. Once seeded, they live on the world state, propagate
slowly, and can warp future encounters, dialogue, and rumors.

This module owns the data model and the lifecycle. It deliberately stays
out of UI and out of the parser — `parser_core` and `game.py` translate
player commands into `try_seed()` calls, and the consequence engine
applies the effects that this module emits.

Public API:
    Stages, Methods, SpreadChannels        — enum-like string constants
    BeliefSeed                              — dataclass with to_dict/from_dict
    BeliefEffect                            — dataclass with to_dict/from_dict
    create_seed(...)                        — build + register a seed
    register_seed(world, seed)              — add to world.belief_seeds
    unregister_seed(world, seed_id)         — remove
    seeds_targeting(world, target_tags)     — list seeds whose target_tags
                                              intersect the supplied tags
    process_belief_seeds(world, minutes)    — propagation tick; called
                                              periodically by game / time_system
    encounter_modifiers_for(world, room)    — list of effect dicts to overlay
                                              onto encounter resolution
    pick_method_template(method_key)        — pull a memetic_templates entry
    summarize_seed(seed)                    — short Polish/English summary
"""
from __future__ import annotations
import itertools
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── String constants (deliberately strings so save/load is trivial) ──────────

class Stages:
    SEEDED              = "seeded"
    NOTICED             = "noticed"
    SPREADING           = "spreading"
    DISTORTED           = "distorted"
    INSTITUTIONALIZED   = "institutionalized"
    BACKLASH            = "backlash"
    BURNED_OUT          = "burned_out"

    ALL = (SEEDED, NOTICED, SPREADING, DISTORTED, INSTITUTIONALIZED,
           BACKLASH, BURNED_OUT)


class Methods:
    RUMOR                  = "rumor"
    LIE                    = "lie"
    MYTHIC_COMPARISON      = "mythic_comparison"
    FALSE_ORDER            = "false_order"
    RELIGIOUS_FRAMING      = "religious_framing"
    LOGIC_EXPLOIT          = "logic_exploit"
    IDENTITY_ATTACK        = "identity_attack"
    PROPAGANDA             = "propaganda"
    TABOO_CREATION         = "taboo_creation"
    SPONSOR_DISINFORMATION = "sponsor_disinformation"
    SOCIAL_PROOF           = "social_proof"
    PERFORMANCE            = "performance"
    FORGED_EVIDENCE        = "forged_evidence"

    ALL = (RUMOR, LIE, MYTHIC_COMPARISON, FALSE_ORDER, RELIGIOUS_FRAMING,
           LOGIC_EXPLOIT, IDENTITY_ATTACK, PROPAGANDA, TABOO_CREATION,
           SPONSOR_DISINFORMATION, SOCIAL_PROOF, PERFORMANCE, FORGED_EVIDENCE)


class SpreadChannels:
    CRAWLER_GOSSIP    = "crawler_gossip"
    MACHINE_RADIO     = "machine_radio"
    SPONSOR_REPLAY    = "sponsor_replay"
    SAFEHOUSE_RUMOR   = "safehouse_rumor"
    GRAFFITI          = "graffiti"
    BLACK_MARKET      = "black_market"
    FACTION_CHANNEL   = "faction_channel"
    COMBAT_LOGS       = "combat_logs"
    TERMINAL_LOGS     = "terminal_logs"
    BATHROOM_GRAFFITI = "bathroom_graffiti"
    AUDIENCE_MEMES    = "audience_memes"

    ALL = (CRAWLER_GOSSIP, MACHINE_RADIO, SPONSOR_REPLAY, SAFEHOUSE_RUMOR,
           GRAFFITI, BLACK_MARKET, FACTION_CHANNEL, COMBAT_LOGS,
           TERMINAL_LOGS, BATHROOM_GRAFFITI, AUDIENCE_MEMES)


# ── Effect ─────────────────────────────────────────────────────────────────

@dataclass
class BeliefEffect:
    """A single mechanical hook attached to a seed.

    `effect_type` matches a key handled either by `consequences.apply` (e.g.
    `world_flag`, `add_audience`, `gain_rumor`) OR by the memetic-specific
    handlers in this module (e.g. `hesitation`, `target_priority_shift`).
    """
    key: str = ""
    trigger_context: str = ""           # "spread_tick", "encounter_start", "talk"
    target_tags: List[str] = field(default_factory=list)
    chance: float = 1.0                 # 0.0..1.0 per evaluation
    effect_type: str = ""
    effect_value: Any = None
    description_key: str = ""
    fallback_description_pl: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dict(
            key=self.key, trigger_context=self.trigger_context,
            target_tags=list(self.target_tags), chance=self.chance,
            effect_type=self.effect_type, effect_value=self.effect_value,
            description_key=self.description_key,
            fallback_description_pl=self.fallback_description_pl,
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BeliefEffect":
        if d is None:
            return cls()
        return cls(
            key=d.get("key", ""),
            trigger_context=d.get("trigger_context", ""),
            target_tags=list(d.get("target_tags", [])),
            chance=float(d.get("chance", 1.0)),
            effect_type=d.get("effect_type", ""),
            effect_value=d.get("effect_value"),
            description_key=d.get("description_key", ""),
            fallback_description_pl=d.get("fallback_description_pl", ""),
        )


# ── Seed ───────────────────────────────────────────────────────────────────

@dataclass
class BeliefSeed:
    seed_id: str = ""
    key: str = ""                       # short stable slug (e.g. "stolen_heart")
    origin_text: str = ""               # the player's actual phrase
    created_by: str = "player"
    created_floor: int = 1
    created_time: int = 0               # in-game minute when planted
    source_room_id: str = ""

    target_tags: List[str] = field(default_factory=list)
    affected_factions: List[str] = field(default_factory=list)
    affected_entity_tags: List[str] = field(default_factory=list)
    affected_crawler_ids: List[str] = field(default_factory=list)

    core_claim: str = ""                # short single sentence claim
    emotional_hook: str = ""
    logic_hook: str = ""
    method: str = Methods.RUMOR
    desired_effect: str = ""
    spread_channels: List[str] = field(default_factory=list)

    # 0..100. Strength = how forceful the original planting was. Stability =
    # how well it holds together against scrutiny. Distortion = how warped
    # it has become as it propagates. The three drift over time.
    strength: int = 50
    stability: int = 50
    distortion: int = 0

    current_stage: str = Stages.SEEDED
    tags: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    rewards: List[str] = field(default_factory=list)
    effects: List[BeliefEffect] = field(default_factory=list)
    consequences: List[Dict[str, Any]] = field(default_factory=list)

    known_to_player: bool = True
    public_visibility: int = 1          # 0=secret, 1=local, 2=floor, 3=audience-wide
    sponsor_attention: bool = False

    # If 0: never expires. Otherwise: minute after which it auto-burns out.
    expires_at_time: int = 0

    # Internal counters
    last_tick_time: int = 0
    spread_count: int = 0               # how many propagation ticks landed
    last_rumor_key: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dict(
            seed_id=self.seed_id, key=self.key, origin_text=self.origin_text,
            created_by=self.created_by, created_floor=self.created_floor,
            created_time=self.created_time, source_room_id=self.source_room_id,
            target_tags=list(self.target_tags),
            affected_factions=list(self.affected_factions),
            affected_entity_tags=list(self.affected_entity_tags),
            affected_crawler_ids=list(self.affected_crawler_ids),
            core_claim=self.core_claim, emotional_hook=self.emotional_hook,
            logic_hook=self.logic_hook, method=self.method,
            desired_effect=self.desired_effect,
            spread_channels=list(self.spread_channels),
            strength=self.strength, stability=self.stability,
            distortion=self.distortion, current_stage=self.current_stage,
            tags=list(self.tags), risks=list(self.risks),
            rewards=list(self.rewards),
            effects=[e.to_dict() for e in self.effects],
            consequences=list(self.consequences),
            known_to_player=self.known_to_player,
            public_visibility=self.public_visibility,
            sponsor_attention=self.sponsor_attention,
            expires_at_time=self.expires_at_time,
            last_tick_time=self.last_tick_time,
            spread_count=self.spread_count,
            last_rumor_key=self.last_rumor_key,
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BeliefSeed":
        if d is None:
            return cls()
        s = cls()
        for k in ("seed_id", "key", "origin_text", "created_by",
                  "source_room_id", "core_claim", "emotional_hook",
                  "logic_hook", "method", "desired_effect",
                  "current_stage", "last_rumor_key"):
            v = d.get(k)
            if v is not None:
                setattr(s, k, v)
        for k in ("created_floor", "created_time", "strength", "stability",
                  "distortion", "public_visibility", "expires_at_time",
                  "last_tick_time", "spread_count"):
            v = d.get(k)
            if v is not None:
                setattr(s, k, int(v))
        s.target_tags          = list(d.get("target_tags", []))
        s.affected_factions    = list(d.get("affected_factions", []))
        s.affected_entity_tags = list(d.get("affected_entity_tags", []))
        s.affected_crawler_ids = list(d.get("affected_crawler_ids", []))
        s.spread_channels      = list(d.get("spread_channels", []))
        s.tags     = list(d.get("tags", []))
        s.risks    = list(d.get("risks", []))
        s.rewards  = list(d.get("rewards", []))
        s.effects  = [BeliefEffect.from_dict(e) for e in d.get("effects", [])]
        s.consequences = list(d.get("consequences", []))
        s.known_to_player = bool(d.get("known_to_player", True))
        s.sponsor_attention = bool(d.get("sponsor_attention", False))
        return s


# ── Construction ───────────────────────────────────────────────────────────

_seed_counter = itertools.count(1)


def _new_id() -> str:
    """Stable-ish id. Uses a short uuid suffix to avoid collisions across
    save/load roundtrips that reuse the counter."""
    return f"bs_{next(_seed_counter):04d}_{uuid.uuid4().hex[:6]}"


def create_seed(*, method: str, core_claim: str,
                target_tags: Optional[List[str]] = None,
                origin_text: str = "",
                source_room_id: str = "",
                created_floor: int = 1,
                created_time: int = 0,
                strength: int = 50,
                stability: int = 50,
                key: Optional[str] = None,
                spread_channels: Optional[List[str]] = None,
                emotional_hook: str = "",
                logic_hook: str = "",
                desired_effect: str = "",
                tags: Optional[List[str]] = None,
                risks: Optional[List[str]] = None,
                effects: Optional[List[BeliefEffect]] = None,
                public_visibility: int = 1,
                sponsor_attention: bool = False) -> BeliefSeed:
    """Build a `BeliefSeed`. Does NOT register it on the world — call
    `register_seed(world, seed)` to persist it."""
    return BeliefSeed(
        seed_id=_new_id(),
        key=key or _slug_from_claim(core_claim) or method,
        origin_text=origin_text or core_claim,
        created_floor=int(created_floor),
        created_time=int(created_time),
        source_room_id=source_room_id,
        target_tags=list(target_tags or []),
        core_claim=core_claim,
        emotional_hook=emotional_hook,
        logic_hook=logic_hook,
        method=method,
        desired_effect=desired_effect,
        spread_channels=list(spread_channels or []),
        strength=int(strength), stability=int(stability),
        tags=list(tags or []),
        risks=list(risks or []),
        effects=list(effects or []),
        public_visibility=int(public_visibility),
        sponsor_attention=bool(sponsor_attention),
    )


def _slug_from_claim(claim: str, max_len: int = 28) -> str:
    if not claim:
        return ""
    folded = []
    for ch in claim.lower():
        if ch.isalnum():
            folded.append(ch)
        elif ch in " -_":
            folded.append("_")
        elif ch in "ąćęłńóśźż":
            folded.append({"ą":"a","ć":"c","ę":"e","ł":"l","ń":"n",
                           "ó":"o","ś":"s","ź":"z","ż":"z"}[ch])
    out = "".join(folded)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")[:max_len]


# ── World registry helpers ────────────────────────────────────────────────

def _world_seeds(world) -> Dict[str, BeliefSeed]:
    """Get-or-create the world's belief_seeds dict."""
    bs = getattr(world, "belief_seeds", None)
    if bs is None:
        bs = {}
        try:
            setattr(world, "belief_seeds", bs)
        except Exception:
            pass
    return bs


def register_seed(world, seed: BeliefSeed) -> BeliefSeed:
    """Add seed to world.belief_seeds and (best-effort) link it to the
    current floor's active list."""
    if seed is None or not seed.seed_id:
        return seed
    bs = _world_seeds(world)
    bs[seed.seed_id] = seed
    f = getattr(world, "current_floor", None)
    if f is not None:
        active = getattr(f, "active_belief_seed_ids", None)
        if active is None:
            try:
                f.active_belief_seed_ids = []
                active = f.active_belief_seed_ids
            except Exception:
                active = None
        if active is not None and seed.seed_id not in active:
            active.append(seed.seed_id)
    return seed


def unregister_seed(world, seed_id: str) -> bool:
    bs = _world_seeds(world)
    seed = bs.pop(seed_id, None)
    f = getattr(world, "current_floor", None)
    if f is not None:
        active = getattr(f, "active_belief_seed_ids", None)
        if isinstance(active, list) and seed_id in active:
            active.remove(seed_id)
    return seed is not None


def all_active(world) -> List[BeliefSeed]:
    return [s for s in _world_seeds(world).values()
            if s.current_stage not in (Stages.BURNED_OUT,)]


def seeds_targeting(world, target_tags) -> List[BeliefSeed]:
    """Return seeds whose `target_tags` intersect the supplied set/list."""
    if not target_tags:
        return []
    needle = set(target_tags)
    return [s for s in all_active(world)
            if needle.intersection(s.target_tags or [])]


# ── Template lookup ────────────────────────────────────────────────────────

def pick_method_template(method_key: str) -> Dict[str, Any]:
    """Look up a method's static template from data/memetic_templates.

    Returns an empty dict on miss — every caller treats missing fields as
    soft defaults.
    """
    try:
        from .data import memetic_templates as mt
    except Exception:
        return {}
    table = getattr(mt, "METHOD_TEMPLATES", None) or {}
    return dict(table.get(method_key, {}))


def archetype_for_claim(claim: str, target_tags) -> Optional[Dict[str, Any]]:
    """Match a claim against known BELIEF_ARCHETYPES by keyword overlap."""
    try:
        from .data.memetic_templates import BELIEF_ARCHETYPES
    except Exception:
        return None
    if not claim:
        return None
    needle_text = claim.lower()
    needle_tags = set(target_tags or [])
    best = None
    best_score = 0
    for key, arch in BELIEF_ARCHETYPES.items():
        score = 0
        ats = set(arch.get("target_tags", []) or [])
        score += len(ats & needle_tags) * 2
        sample = (arch.get("core_claim_template_pl") or "").lower()
        for token in needle_text.split():
            if len(token) >= 4 and token in sample:
                score += 1
        if score > best_score:
            best_score = score
            best = {"key": key, **arch}
    return best


# ── Propagation tick ───────────────────────────────────────────────────────

# Stage transitions are intentionally coarse — propagation is a slow burn.
_STAGE_ORDER = [Stages.SEEDED, Stages.NOTICED, Stages.SPREADING,
                Stages.DISTORTED, Stages.INSTITUTIONALIZED]


def process_belief_seeds(world, minutes_elapsed: int = 0,
                         trigger: str = "tick") -> List[Dict[str, Any]]:
    """Tick the belief-seed lifecycle. Return a list of summary events
    (dicts) the game layer can display or log. Never raises.

    `trigger` is informational: "tick", "safehouse_entry", "broadcast",
    "floor_transition". It can influence which channels get a chance to
    spread.
    """
    out: List[Dict[str, Any]] = []
    if world is None:
        return out
    seeds = _world_seeds(world)
    if not seeds:
        return out
    floor = getattr(world, "current_floor", None)
    now = getattr(floor, "current_minute", 0) if floor is not None else 0

    for seed in list(seeds.values()):
        if seed.current_stage in (Stages.BURNED_OUT,):
            continue
        # Expiration check first.
        if seed.expires_at_time and now >= seed.expires_at_time:
            seed.current_stage = Stages.BURNED_OUT
            out.append({"seed_id": seed.seed_id, "kind": "burned_out"})
            continue

        # Trigger-aware spread chance. Safehouse entries and broadcasts
        # have an obvious boost.
        base_chance = max(0.05, min(0.85, seed.strength / 120.0))
        if trigger == "safehouse_entry":
            base_chance += 0.20
        elif trigger == "broadcast":
            base_chance += 0.30
        elif trigger == "floor_transition":
            base_chance += 0.10
        # Stability dampens randomness; high stability → predictable.
        base_chance += (seed.stability - 50) / 200.0
        base_chance = max(0.02, min(0.95, base_chance))

        if random.random() > base_chance:
            continue

        # Spread happened. Track.
        seed.spread_count += 1
        seed.last_tick_time = now

        # Drift: distortion creeps up; strength slowly bleeds.
        seed.distortion = min(100, seed.distortion +
                              random.randint(1, max(2, 100 - seed.stability) // 10 + 1))
        seed.strength = max(0, seed.strength - random.randint(0, 3))

        # Stage advancement.
        idx = _STAGE_ORDER.index(seed.current_stage) if seed.current_stage in _STAGE_ORDER else 0
        if random.random() < 0.5 and idx < len(_STAGE_ORDER) - 1:
            seed.current_stage = _STAGE_ORDER[idx + 1]
            out.append({"seed_id": seed.seed_id, "kind": "stage_up",
                        "stage": seed.current_stage})
        # Drift into distorted/backlash on very high distortion.
        if seed.distortion >= 80 and seed.current_stage != Stages.BACKLASH:
            if random.random() < 0.35:
                seed.current_stage = Stages.BACKLASH
                out.append({"seed_id": seed.seed_id, "kind": "backlash"})

        # Burnout when strength bleeds to zero.
        if seed.strength <= 0:
            seed.current_stage = Stages.BURNED_OUT
            out.append({"seed_id": seed.seed_id, "kind": "burned_out"})
            continue

        # Maybe produce a rumor through the rumor system.
        if floor is not None and random.random() < 0.55:
            rk = _emit_rumor_from_seed(seed, floor, world=world)
            if rk:
                out.append({"seed_id": seed.seed_id, "kind": "rumor",
                            "rumor_key": rk})

    return out


def _emit_rumor_from_seed(seed: BeliefSeed, floor, world=None) -> str:
    """Attach a synthetic rumor key to the floor based on a seed.

    We push a stable key `memetic:<seed_id>:<spread_count>` onto
    `floor.rumors` so save/load handles it for free and the journal can
    match it back to the originating seed via `render_rumor_key`.

    Prompt 07b follow-up: also feed the resulting Polish text into the
    07b knowledge store as a `known_fact` so the player sees the rumor
    in their journal AND so any seed-derived enable_paths land in
    `world.unlocked_paths`. Adds no entry if no world ref is provided.
    """
    key = f"memetic:{seed.seed_id}:{seed.spread_count}"
    if key not in (floor.rumors or []):
        floor.rumors.append(key)
        seed.last_rumor_key = key
    if world is not None:
        try:
            from . import knowledge as _kn
            text = render_memetic_rumor(seed, index=seed.spread_count,
                                        language="pl")
            tags = list(set((seed.target_tags or []) + (seed.tags or [])))
            # Enable paths matching the seed's method so e.g. invoking
            # the myth becomes available once you've heard it.
            enables = []
            if seed.method in ("identity_attack", "logic_exploit",
                               "mythic_comparison", "religious_framing"):
                enables.append("invoke_belief")
            _kn.add_known_fact(world, {
                "key": key,
                "text": text,
                "tags": tags + ["memetic", "rumor"],
                "source": "memetic_propagation",
                "confidence": seed.strength / 100.0,
                "enables_paths": enables,
            })
        except Exception:
            pass
    return key


# ── Natural-language rendering of memetic rumors ──────────────────────────

_TARGET_LABEL_PL = {
    "machine":   "maszyny", "drone": "drony", "construct": "konstrukty",
    "ai":        "sztuczne inteligencje", "robot": "roboty",
    "crawler":   "crawlerzy", "npc": "ktoś z mieszkańców",
    "cult":      "kultyści", "monster": "potwory",
    "sponsor":   "sponsorzy", "audience": "widownia",
    "civilian":  "cywile", "faction": "frakcja",
}
_TARGET_LABEL_EN = {
    "machine":   "machines", "drone": "drones", "construct": "constructs",
    "ai":        "the AIs", "robot": "robots",
    "crawler":   "the crawlers", "npc": "one of the locals",
    "cult":      "the cultists", "monster": "the monsters",
    "sponsor":   "sponsors", "audience": "the audience",
    "civilian":  "civilians", "faction": "the faction",
}

# Frame templates — varied rhythm, no anaphora cluster. Each frame is a
# format string with placeholders {who} (target label) and {claim} (the
# seed's core_claim). Frames are chosen by `index % len(frames)` so the
# same seed's repeated propagation produces different text each time.
_FRAMES_RUMOR_PL = [
    "Przy automacie ktoś mruczy, że {who} {claim_clause}.",
    "Na ścianie ktoś wydrapał: {claim_caps}. Pismo wygląda zbyt równo jak na człowieka.",
    "Crawler w kawiarni twierdzi, że {who} {claim_clause}.",
    "Plotka wraca z dwóch różnych ust w tym samym tygodniu — {who} {claim_clause}.",
    "W kanale safehouse pojawia się szept: {claim_caps}.",
    "Streamerka kiwa głową: {who} {claim_clause}, ale dodaje, że to akurat sama widziała.",
]
_FRAMES_FALSE_ORDER_PL = [
    "Z terminalu schodzi krótki komunikat dla {who_acc}: {claim_caps}.",
    "Logi serwera dzisiaj rano: {who} otrzymali rozkaz, {claim_clause}.",
    "Drobny napis na panelu: ten rozkaz dotyczy {who_gen}, nie was. Pod spodem: {claim_caps}.",
]
_FRAMES_MYTH_PL = [
    "W bathroomie ktoś dorzucił do graffiti nową linijkę: {claim_caps}.",
    "Cytat krąży, jakby pochodził z dawnej instrukcji: '{claim_caps}'. Nikt nie sprawdzał, czy taka instrukcja istniała.",
    "Słychać w korytarzu, że {who} {claim_clause}, i że to nie pierwszy raz.",
]
_FRAMES_PROPAGANDA_PL = [
    "Kamera sponsora pokazuje ten sam klip drugi raz, tylko z innym podpisem: {claim_caps}.",
    "Pomiędzy reklamami pojawia się sucha linijka: {claim_caps}.",
    "Komentator z audience-feedu dodaje od siebie, że {who} {claim_clause}. Reklamodawca milczy.",
]
_FRAMES_DISTORTED_PL = [
    "Wersja, którą słyszysz, brzmi już nieco inaczej: {claim_caps}.",
    "Ktoś próbuje powtórzyć tę plotkę i pomysł zmienia mu się w pół zdania na: {claim_caps}.",
    "To, co krąży, jest podobne, ale nie identyczne — '{claim_caps}', z dopiskiem 'tym razem na pewno'.",
]


# Post-07b follow-up: claim mutators for high-distortion propagation. Each
# entry is (test_substring, replacement) applied case-insensitively. The
# goal is to take a seed's `core_claim` and produce a plausibly-wrong cousin
# that NPCs propagate further. Mutations are small but meaning-flipping.
_CLAIM_MUTATIONS_PL = [
    # heart / organ family
    ("ukradl im serca",      "szukają serc w żywych rzeczach"),
    ("ukradł im serca",      "szukają serc w żywych rzeczach"),
    ("skradzionych sercach", "brakujących sercach w skrzynkach sponsora"),
    ("serce",                "serce, które jest częścią zamienną"),
    ("organ",                "nadmiarowy organ"),
    # spy / sponsor family
    ("sponsor",              "sponsor po cichu"),
    ("kamera",               "kamera z drugim obiektywem"),
    # boss / weakness family
    ("boi się",              "udaje, że boi się"),
    ("słabość",              "słabość, która jest pułapką"),
    ("weakness",             "weakness that is a trap"),
    # generic intensifier
    ("zostali zdradzeni",    "zostali zdradzeni dwa razy"),
]


def _mutate_claim(claim: str) -> str:
    """Return a high-distortion variant of the claim, or the claim unchanged
    if nothing matched. We apply only the FIRST matching mutation so the
    output stays readable."""
    if not claim:
        return claim
    low = claim.lower()
    for needle, repl in _CLAIM_MUTATIONS_PL:
        n = needle.lower()
        if n in low:
            # Replace the first hit, preserving original-case prefix/suffix.
            idx = low.find(n)
            return claim[:idx] + repl + claim[idx + len(n):]
    # Fall back to a generic exaggeration suffix.
    return claim.rstrip(".") + ", i to jest dopiero połowa"
_FRAMES_RUMOR_EN = [
    "Someone mutters by the vending machine that {who} {claim_clause}.",
    "Scratched on the wall: {claim_caps}. The writing is too even to be a person's.",
    "A crawler in the cafe insists that {who} {claim_clause}.",
    "The rumor comes back from two different mouths in the same week — {who} {claim_clause}.",
    "A whisper drifts down the safehouse channel: {claim_caps}.",
]


def _frames_for(seed: BeliefSeed, language: str) -> list:
    if language == "en":
        return _FRAMES_RUMOR_EN
    m = seed.method
    if m in ("false_order",):
        return _FRAMES_FALSE_ORDER_PL
    if m in ("mythic_comparison", "religious_framing", "taboo_creation"):
        return _FRAMES_MYTH_PL
    if m in ("propaganda", "sponsor_disinformation", "performance"):
        return _FRAMES_PROPAGANDA_PL
    return _FRAMES_RUMOR_PL


def _label_for_targets(target_tags, language: str, case: str = "nom") -> str:
    """Pick a single Polish/English label representing the seed's target tags."""
    table = _TARGET_LABEL_PL if language == "pl" else _TARGET_LABEL_EN
    label = None
    for tg in target_tags or []:
        if tg in table:
            label = table[tg]; break
    if label is None:
        label = "ktoś" if language == "pl" else "someone"
    if language == "pl" and case == "acc":
        # crude acc: maszyny→maszyn, drony→drony, etc. — keep it simple.
        return {"maszyny":"maszyn","drony":"dron","konstrukty":"konstruktów",
                "roboty":"robotów","crawlerzy":"crawlerów","kultyści":"kultystów",
                "sponsorzy":"sponsorów"}.get(label, label)
    if language == "pl" and case == "gen":
        return {"maszyny":"maszyn","drony":"dron","crawlerzy":"crawlerów",
                "sponsorzy":"sponsorów"}.get(label, label)
    return label


def _claim_as_clause(claim: str) -> str:
    """Lowercase first letter; trim trailing dot/period."""
    if not claim:
        return "coś się dzieje"
    c = claim.strip()
    if c.endswith("."):
        c = c[:-1]
    return c[0].lower() + c[1:] if c else c


def _claim_as_caps(claim: str) -> str:
    """Uppercase first letter, trim trailing punctuation."""
    if not claim:
        return "Coś się dzieje"
    c = claim.strip().rstrip(".!?")
    return c[0].upper() + c[1:] if c else c


def render_memetic_rumor(seed: BeliefSeed, index: int = 0,
                         context=None, language: str = "pl") -> str:
    """Convert a belief seed + propagation index into natural Polish (or EN)
    text suitable for the journal. Never returns the raw key form.

    Post-07b: at high distortion (`seed.distortion >= 60`) we also MUTATE
    the underlying claim — e.g. "ukradł im serca" → "szukają serc w żywych
    rzeczach" — so the rumor that crawlers propagate further is not
    literally the player's original. The seed itself is untouched; this is
    purely a render-time view of the distorted state.

    `context` is reserved for future room/audience context; ignored for now.
    """
    if seed is None:
        return "" if language != "pl" else "(pusta plotka)"
    # High distortion swaps to the distorted frames pool.
    if seed.distortion >= 60 and language == "pl":
        frames = _FRAMES_DISTORTED_PL
    else:
        frames = _frames_for(seed, language)
    frame = frames[int(index or 0) % len(frames)]
    who_nom = _label_for_targets(seed.target_tags, language, "nom")
    who_acc = _label_for_targets(seed.target_tags, language, "acc")
    who_gen = _label_for_targets(seed.target_tags, language, "gen")
    base_claim = seed.core_claim or seed.origin_text or ""
    # Apply claim mutator for high-distortion Polish renderings only. EN
    # keeps the literal claim because the EN frames don't have the same
    # idiomatic distortion pool yet.
    if seed.distortion >= 60 and language == "pl" and base_claim:
        base_claim = _mutate_claim(base_claim)
    claim_clause = _claim_as_clause(base_claim)
    claim_caps = _claim_as_caps(base_claim)
    try:
        return frame.format(who=who_nom, who_acc=who_acc, who_gen=who_gen,
                            claim_clause=claim_clause, claim_caps=claim_caps)
    except (KeyError, IndexError):
        return claim_caps


# ── Method-aware stat selection (post-07b follow-up) ───────────────────────

# Map a memetic method onto the stat that best models that kind of work.
# CHA: persuasion / showmanship / rhetoric / public speech / emotional pressure.
# INT: logic exploits, technical disinformation, syntax tricks, machine reasoning.
# WIS: reading the target's fears / timing / sensing what will stick.
# DEX: physical stagecraft under pressure (rare; only chosen via override).
_METHOD_STAT = {
    "rumor":                  "CHA",
    "lie":                    "CHA",
    "performance":            "CHA",
    "propaganda":             "CHA",
    "social_proof":           "CHA",
    "sponsor_disinformation": "CHA",
    "false_order":            "INT",
    "logic_exploit":          "INT",
    "forged_evidence":        "INT",
    "identity_attack":        "WIS",
    "mythic_comparison":      "WIS",
    "religious_framing":      "WIS",
    "taboo_creation":         "WIS",
}

# Keyword hints culled from the raw player text. We use them as a TIE-BREAKER
# only — never override an explicit method.
_KEYWORD_STAT_PL = {
    "INT": ["protokol","protokół","logika","kod","skladn","składn","komenda",
            "instrukcja","rozkaz","syntaks","exploit","obejście","obejscie",
            "system","baza","kalibracja","matryca"],
    "WIS": ["lęk","lek","strach","wstyd","wina","trauma","tabu","święte","swiete",
            "wierzy","czas","moment","obserwacja","wzorzec","przesąd","przesad"],
    "CHA": ["mowi","mówię","mowię","krzycz","krzyczę","perform","wystąp","wystap",
            "widownia","publika","retoryka","błagam","blagam","prosz","intym",
            "wstrzymaj","emocje"],
    "DEX": ["podsuwam","podstawiam","podrzucam","plakat","podkł","podkl",
            "podstęp ręczny","wciska","pod stoł","pod stol"],
}


def select_memetic_stat(seed_or_method, intent=None, context=None) -> str:
    """Choose a stat for a memetic check.

    `seed_or_method` can be either a `BeliefSeed` (with `.method`) or the
    raw method string. `intent` may carry an Ollama `suggested_stat` (via
    `intent.modifiers` like `'stat:INT'`) — if it agrees with the method
    mapping, we honor it. If it conflicts with a CLEAR method preference,
    method wins. If method is unknown, we fall back to keyword scoring on
    `intent.raw_text`, then CHA.
    """
    # 1) Resolve the method.
    method = ""
    if isinstance(seed_or_method, str):
        method = seed_or_method
    elif seed_or_method is not None:
        method = getattr(seed_or_method, "method", "") or ""

    method_stat = _METHOD_STAT.get(method)

    # 2) Pick up any LLM-suggested stat from intent.modifiers.
    suggested = None
    if intent is not None:
        for m in getattr(intent, "modifiers", None) or []:
            if isinstance(m, str) and m.startswith("stat:"):
                cand = m.split(":", 1)[1].strip().upper()
                if cand in ("STR","DEX","CON","INT","WIS","CHA"):
                    suggested = cand
                    break

    # 3) Reconcile.
    if method_stat:
        if suggested and suggested == method_stat:
            return suggested
        # If LLM suggested a *different* stat AND it's INT/WIS/CHA, accept
        # it only when method is ambiguous (i.e. one of the social methods
        # where INT/WIS overlap meaningfully).
        soft_methods = {"rumor","lie","social_proof","propaganda","performance",
                        "sponsor_disinformation"}
        if suggested in ("INT","WIS","CHA") and method in soft_methods:
            return suggested
        return method_stat

    # 4) Method unknown. Keyword scoring on the raw text.
    text = ""
    if intent is not None:
        text = (getattr(intent, "raw_text", "") or "").lower()
    if text:
        from .affordances import fold as _fold
        folded = _fold(text)
        scores = {"INT": 0, "WIS": 0, "CHA": 0, "DEX": 0}
        for stat, words in _KEYWORD_STAT_PL.items():
            for w in words:
                if _fold(w) in folded:
                    scores[stat] += 1
        winner = max(scores, key=scores.get)
        if scores[winner] > 0:
            return winner

    # 5) LLM-only suggestion as a soft last resort.
    if suggested:
        return suggested

    return "CHA"


# ── Thin resolution wrapper ────────────────────────────────────────────────

def resolve_memetic_attempt(world, intent, *, log_fn=None,
                            narrate_fn=None) -> Dict[str, Any]:
    """Stable wrapper around the memetic action resolution flow.

    Currently delegates to `Game._attempt_memetic` (kept there because it
    already touches log+narrator+time_system+risk_reward+consequences in a
    single function). This wrapper exists so future callers — including a
    refactored `resolution.resolve()` — can invoke memetic resolution
    without depending on Game.

    Returns a small status dict for the caller's inspection:
        {"resolved": bool, "via": "game._attempt_memetic" | "stub"}

    TODO(memetics): move the actual logic out of Game into this function
    once `resolution.py` grows a memetic branch. Until then this is a
    thin adapter that simply runs the game-side handler when a Game is
    reachable through `world.settings["_game"]`.
    """
    # Best-effort game lookup. Most call sites just call Game directly.
    g = (getattr(world, "settings", {}) or {}).get("_game")
    if g is not None and hasattr(g, "_attempt_memetic"):
        g._attempt_memetic(intent)
        return {"resolved": True, "via": "game._attempt_memetic"}
    return {"resolved": False, "via": "stub"}


def render_rumor_key(world, key: str, language: str = "pl") -> str:
    """Resolve any rumor key to natural text. Recognizes the
    `memetic:<seed_id>:<index>` form; defers everything else to
    `content_loader.get_rumor`."""
    if not key:
        return ""
    if isinstance(key, str) and key.startswith("memetic:"):
        parts = key.split(":")
        if len(parts) >= 3:
            sid = parts[1]
            try:
                idx = int(parts[2])
            except (ValueError, TypeError):
                idx = 0
            seed = (getattr(world, "belief_seeds", {}) or {}).get(sid)
            if seed is not None:
                return render_memetic_rumor(seed, idx, language=language)
        return ""
    # Non-memetic key — try the rumor template registry.
    try:
        from .data.rumor_templates import get_rumor
        r = get_rumor(key)
        if r:
            return r.get("text", "") or ""
    except Exception:
        pass
    return ""


# ── Encounter / contextual modifiers ───────────────────────────────────────

def encounter_modifiers_for(world, room) -> List[Dict[str, Any]]:
    """Return effect dicts that should modify an encounter starting in `room`.

    Caller (resolution / consequences) decides what to do with them. The
    payload is intentionally generic — `{"type": "hesitation", "amount": 1}`
    style — so older callsites can ignore unknown types safely.
    """
    if world is None or room is None:
        return []
    tags = set(room.sensory_tags or []) | {room.actual_type or ""}
    for e in room.entities:
        tags.update(e.tags or [])
    relevant = seeds_targeting(world, list(tags))
    out: List[Dict[str, Any]] = []
    for s in relevant:
        # Burned-out seeds don't influence anything new.
        if s.current_stage == Stages.BURNED_OUT:
            continue
        for eff in s.effects:
            if eff.trigger_context in ("", "encounter_start"):
                if random.random() <= eff.chance:
                    out.append({"type": eff.effect_type,
                                "amount": eff.effect_value,
                                "seed_id": s.seed_id,
                                "target_tags": list(eff.target_tags),
                                "fallback_line": eff.fallback_description_pl})
    return out


# ── Summaries ──────────────────────────────────────────────────────────────

def summarize_seed(seed: BeliefSeed, lang: str = "pl") -> str:
    """Short journal-friendly line. Hides hidden seeds with a vague stub."""
    if seed is None:
        return ""
    if not seed.known_to_player:
        return "?  (krąży coś, czego nie potrafisz nazwać)" if lang == "pl" \
            else "?  (something circulates that you can't name)"
    stage = seed.current_stage
    tgt = ", ".join(seed.target_tags[:3]) if seed.target_tags else "?"
    if lang == "pl":
        return f"• {seed.core_claim or seed.key}  [cel: {tgt} · etap: {stage}]"
    return f"• {seed.core_claim or seed.key}  [target: {tgt} · stage: {stage}]"
