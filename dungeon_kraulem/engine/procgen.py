"""Floor builder — instantiates Floor 1 from hand-authored templates."""
import copy
import random

from .floor import FloorState
from .room import RoomState
from .entity import Entity, T_OBJECT, T_HAZARD, T_TERMINAL, T_MONSTER, T_SERVICE
from ..systems.crawlers import make_random_crawler
from ..content.items import make_item
from ..content.data.room_templates import (
    ROOMS, FLOOR_1_TITLE_KEY, FLOOR_1_TITLE_FALLBACK,
    FLOOR_1_THEME_KEY, FLOOR_1_THEME_FALLBACK,
    FLOOR_1_SPONSOR_KEY, FLOOR_1_SPONSOR_FALLBACK,
)
from ..content.data.entity_templates import ENV, HAZ, TERM, SVC, MON


_TYPE_FOR_SEED = {
    "env":  T_OBJECT,
    "haz":  T_HAZARD,
    "term": T_TERMINAL,
    "svc":  T_SERVICE,
    "mon":  T_MONSTER,
}


def build_floor_1(world) -> FloorState:
    """Entry point for Floor 1 construction.

    Default path: procedural generator (revamp.floor_generator.generate_floor).
    Debug fallback (config.USE_HANDMADE_FLOOR_1 = True): the hand-built
    15-room vertical slice defined below.
    """
    from ..config import USE_HANDMADE_FLOOR_1
    if not USE_HANDMADE_FLOOR_1:
        from .floor_generator import generate_floor
        return generate_floor(world, floor_number=1)
    return _build_handmade_floor_1(world)


def _build_handmade_floor_1(world) -> FloorState:
    """The original hand-authored Floor 1 — kept as opt-in debug harness."""
    f = FloorState(floor_id="floor_1", floor_number=1)
    f.title_key = FLOOR_1_TITLE_KEY; f.title_fallback = FLOOR_1_TITLE_FALLBACK
    f.theme_key = FLOOR_1_THEME_KEY; f.theme_fallback = FLOOR_1_THEME_FALLBACK
    # P29.2 — no floor sponsor lock. The actual current primary is
    # whoever wins attention from player actions (see engine.sponsors).
    f.sponsor_key = ""
    f.sponsor_fallback = "Sponsorzy obserwują."

    # Build rooms
    for tmpl in ROOMS:
        r = RoomState(room_id=tmpl["id"])
        for k in ("short_title_key","fallback_short_title","title_key","fallback_title",
                  "first_enter_key","fallback_first_enter","look_key","fallback_look",
                  "search_key","fallback_search","public_hint_key","fallback_public_hint",
                  "actual_type"):
            setattr(r, k, tmpl.get(k, getattr(r, k)))
        r.sensory_tags = list(tmpl.get("sensory_tags", []))
        r.locked = tmpl.get("locked", False)
        r.secret = tmpl.get("secret", False)
        r.safehouse_subtype = tmpl.get("safehouse_subtype")
        r.exits = {k: dict(v) for k, v in tmpl.get("exits", {}).items()}
        # Instantiate seeded entities
        for seed in tmpl.get("entity_seeds", []):
            ent = _instantiate_seed(seed, r.room_id, world, floor_num=1)
            if ent is not None:
                r.entities.append(ent)
                world.register(ent)
        f.add_room(r)

    f.start_room_id = "r1_intake"
    f.current_room_id = f.start_room_id
    f.exit_room_ids = ["r1_exit"]

    # Seed a content-template encounter into one Floor 1 combat room (Prompt 1)
    from ..content import content_loader
    combat_rooms = [rm for rm in f.rooms.values() if rm.actual_type == "combat"]
    if combat_rooms:
        picked_room = combat_rooms[0]
        enc_pick = content_loader.random_encounter_template(floor_num=1,
                                                            required_tags=["monster"])
        if enc_pick is None:
            enc_pick = content_loader.random_encounter_template(floor_num=1)
        if enc_pick is not None:
            ekey, etmpl = enc_pick
            picked_room.encounter_key = ekey
            intro = content_loader.encounter_intro_line(etmpl)
            if intro:
                picked_room.encounter_intro_fallback = intro

    # Pick a Floor 1 exit objective from content templates (Prompt 1)
    from ..content import content_loader
    picked = content_loader.random_floor_objective()
    if picked is not None:
        key, obj = picked
        f.exit_conditions = [key]
        # Stash human-readable objective on the floor for UI/log
        f.objective_key = key
        f.objective_title_fallback = obj.get("fallback_title", "")
        f.objective_description_fallback = obj.get("description", "")
        f.objective_solution_paths = list(obj.get("solution_paths", []))
    else:
        f.exit_conditions = ["defeat_boss_or_bribe"]
        f.objective_key = ""
        f.objective_title_fallback = ""
        f.objective_description_fallback = ""
        f.objective_solution_paths = []

    # Mark start as visited/discovered
    start = f.rooms[f.start_room_id]
    start.visited = True
    start.last_visited_minute = 0
    f.discovered_room_ids.add(f.start_room_id)
    f.known_room_ids.add(f.start_room_id)
    # Adjacent rooms become "hinted"
    for label, ed in start.exits.items():
        f.known_room_ids.add(ed.get("target",""))

    # Deadline (14 days from cfg)
    from ..config import MINUTES_PER_DAY, FLOOR1_DEADLINE_DAYS
    f.deadline_minute = MINUTES_PER_DAY * FLOOR1_DEADLINE_DAYS

    return f


def _instantiate_seed(seed, room_id: str, world, floor_num: int):
    kind = seed[0]
    if kind == "env":
        return _from_template(ENV, seed[1], room_id, T_OBJECT)
    if kind == "haz":
        return _from_template(HAZ, seed[1], room_id, T_HAZARD)
    if kind == "term":
        return _from_template(TERM, seed[1], room_id, T_TERMINAL)
    if kind == "svc":
        return _from_template(SVC, seed[1], room_id, T_SERVICE)
    if kind == "mon":
        ent = _from_template(MON, seed[1], room_id, T_MONSTER)
        return ent
    if kind == "item":
        item = make_item(seed[1], location_id=room_id)
        return item
    if kind == "npc":
        _, archetype, dispo = seed
        crawler = make_random_crawler(floor_num, room_id, disposition=dispo)
        # Tag the archetype on the crawler entity for parser/look output
        crawler.tags.append(archetype)
        return crawler
    return None


def _from_template(table, key: str, room_id: str, etype: str):
    proto = table.get(key)
    if proto is None:
        return None
    e = Entity(
        key=key,
        entity_type=etype,
        name_key=proto.get("name_key", ""),
        fallback_name=proto.get("fallback_name", key.replace("_"," ")),
        desc_key=proto.get("desc_key", ""),
        fallback_desc=proto.get("fallback_desc", ""),
        tags=list(proto.get("tags", [])),
        affordances=list(proto.get("affordances", ["inspect"])),
        location_id=room_id,
        hp=proto.get("hp", 0),
        max_hp=proto.get("max_hp", 0),
        ac=proto.get("ac", 10),
        attack_bonus=proto.get("attack_bonus", 0),
        damage_dice=proto.get("damage_dice", "1d4"),
    )
    return e
