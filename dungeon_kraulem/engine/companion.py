"""Prompt 19 — Companion data model (pets, crawler allies, drones, summons).

The Companion dataclass is the shared shape for everything that
"follows the player." V1 only ships live pets (kind="pet") from the
opiekun_zwierzaka background, but `kind` accepts "crawler" / "drone" /
"summon" / "temp_npc" so later content can spawn allies without
re-modelling.

Two-axis state (bond, stress) is intentional — adding morale / loyalty
/ trust / needs / contract-duration was tempting but the prompt-18
review concluded those are v2. The dataclass leaves room
(`tags`, `abilities`, `temporary`, `contract_minutes_remaining`) so a
later content drop can add them without breaking save compat.

Companions live in `world.companions: Dict[int, Companion]` and are
referenced by id from `character.companion_ids`. Status `"missing"`
removes them from the room temporarily; status `"dead"` keeps the
record (so the journal can show "Gęś — nie żyje" rather than the pet
silently vanishing).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import itertools


# ── ID counter (mirrors Entity._eid_counter pattern) ───────────────────────

_cid_counter = itertools.count(start=1)


def _next_cid() -> int:
    return next(_cid_counter)


# ── Status / kind constants ────────────────────────────────────────────────

STATUS_ACTIVE  = "active"
STATUS_MISSING = "missing"
STATUS_INJURED = "injured"
STATUS_DEAD    = "dead"

KIND_PET       = "pet"
KIND_CRAWLER   = "crawler"
KIND_DRONE     = "drone"
KIND_SUMMON    = "summon"
KIND_TEMP_NPC  = "temp_npc"

ALL_KINDS = (KIND_PET, KIND_CRAWLER, KIND_DRONE, KIND_SUMMON, KIND_TEMP_NPC)
ALL_STATUSES = (STATUS_ACTIVE, STATUS_MISSING, STATUS_INJURED, STATUS_DEAD)


# ── Polish display labels ──────────────────────────────────────────────────
#
# Internal slugs (above) stay snake_case because saves + tests read them.
# The game is Polish-only, so anywhere status / abilities / sponsor-tags
# are rendered to the player, we route through these dicts. status_pl()
# + abilities_pl_list() + sponsor_tag_pl() are the public helpers — UI
# code should never f-string the raw slug.

_STATUS_PL = {
    STATUS_ACTIVE:  "aktywny",
    STATUS_MISSING: "zaginiony",
    STATUS_INJURED: "ranny",
    STATUS_DEAD:    "martwy",
}

_ABILITY_PL = {
    "scout_tight":     "zwiad w ciasnych miejscach",
    "scout_aerial":    "zwiad z powietrza",
    "find_scrap":      "wynajdywanie złomu",
    "distract_weak":   "rozproszenie słabych wrogów",
    "intimidate":      "zastraszanie",
    "repeat_phrase":   "powtarzanie zasłyszanych zdań",
    "detect_chemical": "wykrywanie chemii",
    "morale_boost":    "podnoszenie morale",
    "mark_trail":      "znakowanie tropu",
    "unlock_assist":   "pomoc przy zamkach",
    "reduce_noise":    "tłumienie hałasu",
    "warn_danger":     "ostrzeganie przed pułapkami",
}

_SPONSOR_TAG_PL = {
    "novachem_biotech":           "NovaChem-Biotech",
    "kanal_7_krawedz":            "Kanał 7 Krawędź",
    "kult_recyklingu":            "Kult Recyklingu",
    "ministerstwo_pamieci":       "Ministerstwo Pamięci",
    "sponsor_bezpieczenstwa_sportu": "Sponsor Bezpieczeństwa Sportu",
    "czarny_rynek_plus":          "Czarny Rynek+",
    "bractwo_komornika":          "Bractwo Komornika",
    "liga_brawurowa":             "Liga Brawurowa",
    "spoldzielnia_mrowek":        "Spółdzielnia Mrówek",
    "bog_polimerow":              "Bóg Polimerów",
    "stadion_wolnosci":           "Stadion Wolności",
    # Pet-template flavor tags — these aren't sponsor keys, just
    # descriptive markers ("bird", "cat", "talking"). Translate the
    # common ones; unknowns fall through as raw slug.
    "bird":          "ptak",
    "cat":           "kot",
    "dog":           "pies",
    "rat":           "szczur",
    "talking":       "mówiący",
    "celebrity_pet": "zwierzę gwiazdy",
    "broadcast":     "transmisja",
    "small":         "mały",
    "large":         "duży",
    "stealthy":      "skradający",
    "loyal":         "lojalny",
    "aggressive":    "agresywny",
}


def status_pl(status_key: str) -> str:
    """Polish display name for a companion status. Falls back to the
    raw slug if unmapped (loud signal that we need to add an entry)."""
    return _STATUS_PL.get(status_key, status_key)


def abilities_pl_list(abilities) -> list:
    """Polish display labels for a list of ability slugs. Unknown
    slugs pass through (signals 'we forgot to translate this')."""
    return [_ABILITY_PL.get(a, a) for a in (abilities or [])]


def sponsor_tag_pl(tag: str) -> str:
    return _SPONSOR_TAG_PL.get(tag, tag)


def sponsor_tags_pl_list(tags) -> list:
    return [sponsor_tag_pl(t) for t in (tags or [])]


# ── Data model ────────────────────────────────────────────────────────────

@dataclass
class Companion:
    companion_id: int = field(default_factory=_next_cid)
    kind: str = KIND_PET
    species_key: str = ""           # catalog lookup key, e.g. "gees"
    display_name_pl: str = ""       # localized or generated, e.g. "Gęś"

    # Two-axis state.
    bond:   int = 5                 # 0-10, how attached the companion is
    stress: int = 0                 # 0-10, how panicky / unwilling

    status: str = STATUS_ACTIVE     # active | missing | injured | dead
    location_room_id: str = ""      # where the companion currently is

    # Lifecycle.
    temporary: bool = False
    contract_minutes_remaining: int = 0   # 0 = permanent

    # Catalog-derived (cached on assignment so save/load doesn't need to
    # re-resolve via the pet catalog every load).
    tags: List[str] = field(default_factory=list)
    abilities: List[str] = field(default_factory=list)
    sponsor_likes_tags: List[str] = field(default_factory=list)

    # Per-encounter flags.
    advantage_used_this_encounter: bool = False

    # ── Two-axis helpers ────────────────────────────────────────────────

    def adjust_bond(self, delta: int) -> int:
        self.bond = max(0, min(int(self.bond + delta), 10))
        return self.bond

    def adjust_stress(self, delta: int) -> int:
        self.stress = max(0, min(int(self.stress + delta), 10))
        return self.stress

    def is_alive(self) -> bool:
        return self.status != STATUS_DEAD

    def is_available(self) -> bool:
        """Available to receive a command this turn."""
        return self.status == STATUS_ACTIVE

    def has_ability(self, ability_key: str) -> bool:
        return ability_key in (self.abilities or [])

    # ── Serialization ───────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "companion_id": int(self.companion_id),
            "kind": self.kind,
            "species_key": self.species_key,
            "display_name_pl": self.display_name_pl,
            "bond": int(self.bond),
            "stress": int(self.stress),
            "status": self.status,
            "location_room_id": self.location_room_id,
            "temporary": bool(self.temporary),
            "contract_minutes_remaining": int(self.contract_minutes_remaining),
            "tags": list(self.tags or []),
            "abilities": list(self.abilities or []),
            "sponsor_likes_tags": list(self.sponsor_likes_tags or []),
            "advantage_used_this_encounter":
                bool(self.advantage_used_this_encounter),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Companion":
        return cls(
            companion_id=int(d.get("companion_id") or _next_cid()),
            kind=str(d.get("kind") or KIND_PET),
            species_key=str(d.get("species_key") or ""),
            display_name_pl=str(d.get("display_name_pl") or ""),
            bond=int(d.get("bond") if d.get("bond") is not None else 5),
            stress=int(d.get("stress") or 0),
            status=str(d.get("status") or STATUS_ACTIVE),
            location_room_id=str(d.get("location_room_id") or ""),
            temporary=bool(d.get("temporary") or False),
            contract_minutes_remaining=int(
                d.get("contract_minutes_remaining") or 0),
            tags=list(d.get("tags") or []),
            abilities=list(d.get("abilities") or []),
            sponsor_likes_tags=list(d.get("sponsor_likes_tags") or []),
            advantage_used_this_encounter=bool(
                d.get("advantage_used_this_encounter") or False),
        )


# ── Registry API ──────────────────────────────────────────────────────────

def register_companion(world, companion: Companion) -> Companion:
    """Add a companion to the world's registry and to the player's
    companion_ids list. Returns the same Companion for chaining."""
    if not hasattr(world, "companions") or world.companions is None:
        world.companions = {}
    world.companions[companion.companion_id] = companion
    char = getattr(world, "character", None)
    if char is not None:
        cids = getattr(char, "companion_ids", None)
        if cids is None:
            char.companion_ids = []
            cids = char.companion_ids
        if companion.companion_id not in cids:
            cids.append(companion.companion_id)
    return companion


def get_companion(world, companion_id: int) -> Optional[Companion]:
    return (getattr(world, "companions", {}) or {}).get(int(companion_id))


def player_companions(world) -> List[Companion]:
    """Return all companions owned by the player, in id-order."""
    char = getattr(world, "character", None)
    if char is None:
        return []
    cids = getattr(char, "companion_ids", None) or []
    registry = getattr(world, "companions", {}) or {}
    out = []
    for cid in cids:
        comp = registry.get(int(cid))
        if comp is not None:
            out.append(comp)
    return out


def active_pet(world) -> Optional[Companion]:
    """Return the player's first ACTIVE pet (kind=='pet'). V1 always
    returns at most one pet; the model supports more later."""
    for comp in player_companions(world):
        if comp.kind == KIND_PET and comp.is_available():
            return comp
    return None


def serialize_companions(world) -> Dict[str, Dict[str, Any]]:
    reg = getattr(world, "companions", {}) or {}
    return {str(cid): c.to_dict() for cid, c in reg.items()}


def deserialize_companions(world, raw: Dict[str, Any]) -> None:
    reg: Dict[int, Companion] = {}
    for sid, d in (raw or {}).items():
        try:
            comp = Companion.from_dict(d)
            reg[comp.companion_id] = comp
        except Exception:
            continue
    world.companions = reg
