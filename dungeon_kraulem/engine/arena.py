"""P29.60 — Arena testowa: combat-only sandbox.

Pozwala szybko przetestować combat / weapons / mobs / pułapki bez
przechodzenia całej eksploracji + dialogów + sponsor flow.

Architektura:
- Menu główne: 4-ta opcja 'Arena testowa' → STATE_ARENA_MENU
- STATE_ARENA_MENU: picker 4 wariantów
- STATE_ARENA_LOADOUT (planned, follow-up): broń + klasa picker
- STATE_ARENA_PLAY: reuses STATE_PLAY logic z arena floor
- Win/Loss → return to STATE_ARENA_MENU

MVP sesja 1 (ten plik):
- 1 wariant: 'duel_1v1' (player vs Tunelowy Szczurek)
- Fixed default loadout (janitor + tani nóż), picker = follow-up
- Arena floor: 1 room, no exits, no time pressure

Variants catalog (do iteracji w kolejnych sesjach):
- duel_1v1: 1 mob (test damage / VATS)
- triple_threat: 3 moby z różnych faction (multi-target / AI)
- boss_fight: 1 floor_boss (test boss mechanics)
- trap_room: mob + 2 traps (lure-into-trap)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class ArenaVariant:
    """Definicja jednego wariantu arenowego."""
    key: str
    label_pl: str
    description_pl: str
    mob_keys: List[str] = field(default_factory=list)
    trap_keys: List[str] = field(default_factory=list)
    enabled: bool = True  # False = grayed out 'wkrótce'


# ── Catalog ────────────────────────────────────────────────────────


ARENA_VARIANTS: Dict[str, ArenaVariant] = {
    "duel_1v1": ArenaVariant(
        key="duel_1v1",
        label_pl="Pojedynek 1 na 1",
        description_pl="Tunelowy Szczurek. Test broni i VATS-a.",
        mob_keys=["tunnel_runt"],  # MON key z entity_templates
    ),
    "triple_threat": ArenaVariant(
        key="triple_threat",
        label_pl="Trzech naraz",
        description_pl="Mob z różnych frakcji. Test multi-target i AI.",
        mob_keys=["tunnel_runt", "kapitan_druzyny", "freezer_carver"],
    ),
    "boss_fight": ArenaVariant(
        key="boss_fight",
        label_pl="Walka z bossem",
        description_pl="Pojedynek z bossem piętra. Test mechanik bossa.",
        mob_keys=["intake_warden"],
    ),
    "trap_room": ArenaVariant(
        key="trap_room",
        label_pl="Pokój z pułapkami",
        description_pl="Mob i pułapki środowiskowe. Test environmental damage.",
        mob_keys=["tunnel_runt"],
        trap_keys=["acid_pool", "zwarcie_kablowe", "peknieta_rura_pary"],
    ),
}


def all_variants() -> List[ArenaVariant]:
    """Lista wariantów w stabilnej kolejności (do menu)."""
    order = ["duel_1v1", "triple_threat", "boss_fight", "trap_room"]
    return [ARENA_VARIANTS[k] for k in order if k in ARENA_VARIANTS]


def get_variant(key: str) -> Optional[ArenaVariant]:
    return ARENA_VARIANTS.get(key)


# ── Setup ─────────────────────────────────────────────────────────


def build_arena_world(variant_key: str, *, character_name: str = "Zawodnik",
                       background: str = "janitor"):
    """Buduje WorldState + Character + minimalne piętro arenowe
    pod konkretny wariant.

    Returns: (WorldState, FloorState) — gotowe do wpięcia do Game'a.

    Raises ValueError gdy variant_key nieznany lub disabled.
    """
    from .world import WorldState
    from .character import Character
    from .floor import FloorState
    from .room import RoomState
    from ..content.data.entity_templates import MON
    from .entity import Entity, T_MONSTER

    variant = get_variant(variant_key)
    if variant is None:
        raise ValueError(f"Nieznany wariant arenowy: {variant_key!r}")
    if not variant.enabled:
        raise ValueError(
            f"Wariant {variant_key!r} jest w przygotowaniu (disabled).")

    # World + character
    w = WorldState()
    w.character = Character(name=character_name, background=background)
    # Pełne HP, default credits
    w.character.hp = w.character.max_hp

    # Arena floor: 1 room z mobami
    floor = FloorState(floor_id=f"arena_{variant_key}", floor_number=1)
    room = RoomState(room_id="arena_room", actual_type="combat")
    room.fallback_short_title = "Arena"
    room.fallback_title = f"Arena testowa: {variant.label_pl}"
    room.fallback_first_enter = (
        f"Wchodzisz na arenę. Reflektory ostre, widownia milczy. "
        f"Wariant: {variant.label_pl.lower()}. {variant.description_pl}")
    room.fallback_look = ("Okrągła sala, ściany z blachy. Nic do "
                          "schowania się, nic do podebrania. Tylko ty "
                          "i przeciwnik.")
    floor.rooms["arena_room"] = room
    floor.start_room_id = "arena_room"
    floor.current_room_id = "arena_room"
    floor.exit_room_ids = []
    w.current_floor = floor

    # Spawn mobs from variant
    for mob_key in variant.mob_keys:
        proto = MON.get(mob_key)
        if proto is None:
            continue
        ent = Entity(
            key=mob_key,
            entity_type=T_MONSTER,
            name_key=proto.get("name_key", ""),
            fallback_name=proto.get("fallback_name", mob_key),
            desc_key=proto.get("desc_key", ""),
            fallback_desc=proto.get("fallback_desc", ""),
            tags=list(proto.get("tags", [])),
            affordances=list(proto.get("affordances",
                                       ["inspect", "attack"])),
            hp=proto.get("hp", 1),
            max_hp=proto.get("max_hp", 1),
            ac=proto.get("ac", 10),
            attack_bonus=proto.get("attack_bonus", 0),
            damage_dice=proto.get("damage_dice", "1d4"),
            damage_type=proto.get("damage_type", "physical"),
            location_id="arena_room",
        )
        # Resists/vulnerabilities z proto
        ent.resists = list(proto.get("resists", []))
        ent.vulnerable_to = list(proto.get("vulnerable_to", []))
        ent.immune_to = list(proto.get("immune_to", []))
        room.entities.append(ent)
        w.register(ent)

    # Spawn traps from HAZ catalog (P29.60 cz.2 — trap variant).
    from ..content.data.entity_templates import HAZ
    from .entity import Entity as E, T_HAZARD
    for trap_key in variant.trap_keys:
        proto = HAZ.get(trap_key)
        if proto is None:
            continue
        ent = E(
            key=trap_key,
            entity_type=T_HAZARD,
            name_key=proto.get("name_key", ""),
            fallback_name=proto.get("fallback_name", trap_key),
            desc_key=proto.get("desc_key", ""),
            fallback_desc=proto.get("fallback_desc", ""),
            tags=list(proto.get("tags", [])),
            affordances=list(proto.get("affordances",
                                       ["inspect"])),
            location_id="arena_room",
        )
        ent.damage_type = proto.get("damage_type", "physical")
        room.entities.append(ent)
        w.register(ent)

    # Mark arena flag — używane przez game.py win/loss routing
    w.flags = getattr(w, "flags", {}) or {}
    w.flags["arena_mode"] = True
    w.flags["arena_variant"] = variant_key

    return w, floor


def arena_is_won(world) -> bool:
    """True gdy wszyscy enemies w arena_room są martwi."""
    if not getattr(world, "current_floor", None):
        return False
    room = world.current_floor.current_room()
    if room is None:
        return False
    from .entity import T_MONSTER, T_CRAWLER
    for ent in room.entities:
        if ent.entity_type not in (T_MONSTER, T_CRAWLER):
            continue
        if ent.is_alive():
            return False
    return True


def arena_is_lost(world) -> bool:
    """True gdy player HP <= 0."""
    ch = getattr(world, "character", None)
    if ch is None:
        return False
    return not ch.is_alive()
