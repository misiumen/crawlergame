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
    # P29.75c — biom areny: napędza tło (bg_<biome>) i portrety wrogów
    # (wrog_<biome>_*). Domyślnie Sortownia — jedyny zbudowany biom.
    biome: str = "intake_industrial"
    # P29.76 — poziom startowy postaci w arenie (testbed: HP + punkty do
    # pickera + skrzynka do reveala). NIE balans — dostęp do mechanik.
    suggested_level: int = 5
    # P29.65 — powłoka broni dopasowana do słabości wroga wariantu (ogień/kwas).
    # Daje graczowi narzędzie do PRZETESTOWANIA systemu słabości (2× „podatny!")
    # — bez tego arena ma tylko broń fizyczną, a nadzorca odbija fizyczne.
    arena_coating: str = ""
    enabled: bool = True  # False = grayed out 'wkrótce'


# ── Catalog ────────────────────────────────────────────────────────


ARENA_VARIANTS: Dict[str, ArenaVariant] = {
    "duel_1v1": ArenaVariant(
        key="duel_1v1",
        label_pl="Pojedynek: Rzeźnik z Zamrażarki",
        description_pl="Rzeźnik z Zamrażarki — wróg Sortowni. Słabość: ogień. "
                       "Test broni i VATS-a.",
        mob_keys=["freezer_carver"],
        arena_coating="fire",
    ),
    "miniboss_sortownia": ArenaVariant(
        key="miniboss_sortownia",
        label_pl="Miniboss: Nadzorca Sortowni",
        description_pl="Nadzorca Sortowni — opancerzony, odporny na obrażenia "
                       "fizyczne (bierz kwas). Słabość: kwas.",
        mob_keys=["nadzorca_sortowni"],
        arena_coating="acid",
    ),
    "triple_threat": ArenaVariant(
        key="triple_threat",
        label_pl="Trzech naraz",
        description_pl="Mob z różnych frakcji. Test multi-target i AI.",
        mob_keys=["tunnel_runt", "kapitan_druzyny", "freezer_carver"],
        arena_coating="fire",
    ),
    "boss_fight": ArenaVariant(
        key="boss_fight",
        label_pl="Boss: Strażnik Sortowni",
        description_pl="Strażnik Sortowni — boss piętra Sortowni. Słabość: "
                       "kwas i ogień. Test mechanik bossa.",
        mob_keys=["intake_warden"],
        arena_coating="acid",
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
    order = ["duel_1v1", "miniboss_sortownia", "boss_fight",
             "triple_threat", "trap_room"]
    return [ARENA_VARIANTS[k] for k in order if k in ARENA_VARIANTS]


def get_variant(key: str) -> Optional[ArenaVariant]:
    return ARENA_VARIANTS.get(key)


# ── Setup ─────────────────────────────────────────────────────────


def _apply_arena_loadout(world, character, weapon_key: str = "miecz_okopowy_oficera"):
    """P29.75c — ubiera arenową postać w wygrywalny zestaw (dotąd loadout był
    tylko zapisywany we flagach, nie zakładany → postać wchodziła bez broni).
    Broń biała + pancerz (AC) + zapas leczenia. Melee gracza jest fizyczne i
    nie ma gotowego itemu żywiołowego (acid_flask tylko z craftingu) — stąd
    stawiamy na solidną broń fizyczną zamiast exploitu słabości."""
    from ..content.items import make_item
    from . import equipment as _eq

    def _mk(key):
        it = make_item(key, location_id="inventory:player")
        world.register(it)
        character.inventory_ids.append(it.entity_id)
        return it

    # Broń do ręki głównej: miecz_okopowy_oficera = 1d10+2, +1 vs humanoid
    # (cała trójka Sortowni to humanoidy). Wzór wpięcia jak STARTER_LOADOUT.
    wpn = _mk(weapon_key or "miecz_okopowy_oficera")
    character.wielded_main_id = wpn.entity_id
    try:
        character.inventory_ids.remove(wpn.entity_id)
    except ValueError:
        pass

    # Pancerz na tors (AC) — przeżywalność vs boss 55 HP.
    armor = _mk("kamizelka_taktyczna")
    try:
        _eq.equip(world, character, armor, "torso")
    except Exception:
        pass

    # Zapas leczenia na walkę (pełne HP i tak na starcie).
    for _ in range(3):
        _mk("bandage")
    for _ in range(2):
        _mk("snack_bar")


def build_arena_world(variant_key: str, *, character_name: str = "Zawodnik",
                       background: str = "security_guard",
                       weapon_key: str = "miecz_okopowy_oficera"):
    """Buduje WorldState + Character + minimalne piętro arenowe
    pod konkretny wariant.

    Returns: (WorldState, FloorState) — gotowe do wpięcia do Game'a.

    Raises ValueError gdy variant_key nieznany lub disabled.
    """
    from .world import WorldState
    from .character import Character, apply_background_stats
    from .floor import FloorState
    from .room import RoomState
    from ..content.data.entity_templates import MON, apply_combat_profile
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
    # P29.75c — aplikuj staty z profilu (arena tego NIE robiła → mod +0 na
    # wszystkim, postać bezużyteczna w walce). Teraz np. security_guard ma
    # SIŁ 14 (+2 do trafienia i obrażeń).
    apply_background_stats(w.character, background)
    # Pełne HP, default credits
    w.character.hp = w.character.max_hp
    # P29.75c — loadout bojowy (broń + pancerz + leczenie do testów walki).
    _apply_arena_loadout(w, w.character, weapon_key)
    # P29.65 — powłoka broni pod słabość wroga wariantu (test systemu słabości:
    # 2× „podatny!"). Limit trafień — gdy powłoka się zużyje, gracz zobaczy też
    # zwykłe (czasem „osłabione") ciosy, więc testuje obie strony mechaniki.
    if variant.arena_coating:
        _wpn = w.get(w.character.wielded_main_id)
        if _wpn is not None:
            _wpn.state = _wpn.state or {}
            _wpn.state["coating"] = {"damage_type": variant.arena_coating,
                                     "hits_remaining": 12}
    # P29.76 — testbed: nadaj poziom startowy (skala HP + punkty do rozdania
    # w pickerze + skrzynka do reveala), żeby od razu testować nowy combat,
    # awans i otwieranie skrzynek. To NIE strojenie balansu — to dostęp do
    # mechanik progresji w sandboxie.
    try:
        from . import leveling as _lvl
        _lvl.pre_level(w, getattr(variant, "suggested_level", 1))
    except Exception:
        pass

    # Arena floor: 1 room z mobami
    floor = FloorState(floor_id=f"arena_{variant_key}", floor_number=1)
    # P29.75c — biom areny napędza tło (bg_<biome>) i portrety (wrog_<biome>_*).
    floor.biome_key = variant.biome
    room = RoomState(room_id="arena_room", actual_type="combat")
    room.biome = variant.biome
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
        # P29.75 — wspólny helper: resists/vulnerable_to/immune_to +
        # damage_type + behavior override z szablonu (jedno źródło prawdy).
        apply_combat_profile(ent, proto)
        # P29.65 — ten sam tor skalowania głębokości co realna gra (na F1
        # testbedu to no-op; trio i tak dostaje autorskie staty z MON).
        try:
            from .balance import scale_for_floor
            scale_for_floor(ent, getattr(floor, "floor_number", 1),
                            home_floor=proto.get("floor_min"))
        except Exception:
            pass
        room.entities.append(ent)
        w.register(ent)

    # P29.76 — obiekty OTOCZENIA (env) do testowania panelu OTOCZENIE,
    # `zbadaj pomieszczenie` i interakcji systemowych (ciśnij w kałużę,
    # podpal łatwopalne, zwarcie na mokrym). Stały ambient intake.
    from ..content.data.entity_templates import ENV as _ENV
    from .entity import T_OBJECT as _T_OBJ
    # Wariant z pułapkami NIE dostaje ambientu — ma własny zestaw hazardów
    # i to one są testowane (uniknij kolizji „kałuża wody" vs „kałuża kwasu").
    _env_keys = () if variant.trap_keys else (
        "sponsor_camera", "exposed_wiring", "water_pool", "broken_table")
    for env_key in _env_keys:
        proto = _ENV.get(env_key)
        if proto is None:
            continue
        eo = Entity(
            key=env_key, entity_type=_T_OBJ,
            name_key=proto.get("name_key", ""),
            fallback_name=proto.get("fallback_name", env_key),
            desc_key=proto.get("desc_key", ""),
            fallback_desc=proto.get("fallback_desc", ""),
            tags=list(proto.get("tags", [])),
            affordances=list(proto.get("affordances", ["inspect"])),
            location_id="arena_room",
        )
        room.entities.append(eo)
        w.register(eo)

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
