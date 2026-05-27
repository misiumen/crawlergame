"""Procedural floor generator.

Public API:
    generate_floor(world, floor_number=1, seed=None, archetype=None) -> FloorState
    validate_floor(floor) -> list[str]

The generator is deterministic for a given seed and is the default code
path; the hand-built Floor 1 in revamp/data/room_templates.py is now an
opt-in debug fallback gated by config.USE_HANDMADE_FLOOR_1.
"""
from __future__ import annotations
import copy
import random
from typing import Dict, List, Optional, Tuple

from .floor import FloorState
from .room import RoomState
from .entity import Entity, T_OBJECT, T_HAZARD, T_TERMINAL, T_MONSTER, T_SERVICE
from ..systems.crawlers import make_random_crawler
from ..content.items import make_item
from ..content.data.entity_templates import ENV, HAZ, TERM, SVC, MON
from ..content.data.floor_archetypes import FLOOR_ARCHETYPES
from ..content import content_loader as cl


# ── Public entry points ──────────────────────────────────────────────────────

def generate_floor(world, floor_number: int = 1,
                   seed: Optional[int] = None,
                   archetype: Optional[str] = None) -> FloorState:
    """Build a procedural floor. Retries up to FLOOR_GEN_MAX_RETRIES times
    if validation fails. Always returns a FloorState (last attempt wins
    if all retries fail — better degraded than crashed)."""
    from ..config import FLOOR_GEN_MAX_RETRIES
    rng = random.Random(seed) if seed is not None else random
    last_floor = None
    last_errors: List[str] = ["never_built"]
    for attempt in range(FLOOR_GEN_MAX_RETRIES):
        floor = _build_floor_once(world, floor_number, rng, archetype)
        errors = validate_floor(floor)
        if not errors:
            return floor
        last_floor = floor
        last_errors = errors
    # All retries failed — return last attempt with errors recorded in flags
    if last_floor is not None:
        last_floor.active_events.append({
            "minute": 0, "kind": "gen_warning",
            "args": {"errors": last_errors},
        })
        return last_floor
    raise RuntimeError("floor generator produced no result")


def validate_floor(floor: FloorState) -> List[str]:
    """Run all validation rules. Return list of error keys (empty == OK)."""
    errs: List[str] = []
    if not floor.start_room_id or floor.start_room_id not in floor.rooms:
        errs.append("no_start")
    if not floor.exit_room_ids or not any(r in floor.rooms for r in floor.exit_room_ids):
        errs.append("no_exit_room")

    # Reachability from start
    reachable = _bfs_reachable(floor, floor.start_room_id)
    for rid in floor.rooms:
        if rid not in reachable:
            errs.append(f"unreachable:{rid}")

    # Safehouse exists & is reachable
    safe_rooms = [r for r in floor.rooms.values() if r.safehouse_subtype]
    if not safe_rooms:
        errs.append("no_safehouse")
    elif not any(r.room_id in reachable for r in safe_rooms):
        errs.append("safehouse_unreachable")

    # Backtracking: pick any non-start room; can we get back to start?
    if floor.start_room_id in floor.rooms:
        for rid, room in floor.rooms.items():
            if rid == floor.start_room_id or not room.visited and True:
                pass
        # Heuristic: if at least one room has 2+ exits, backtracking is possible
        if not any(len(r.exits) >= 2 for r in floor.rooms.values()):
            errs.append("no_backtracking")

    # Objective has at least 2 solution paths
    if len(floor.objective_solution_paths) < 2:
        errs.append("objective_too_few_paths")

    # Boss not adjacent to start (unless explicitly intended)
    if floor.start_room_id in floor.rooms:
        start = floor.rooms[floor.start_room_id]
        for ed in start.exits.values():
            target_id = ed.get("target", "")
            t = floor.rooms.get(target_id)
            if t and t.actual_type == "boss":
                errs.append("boss_adjacent_to_start")

    # Locked route shouldn't isolate the exit
    exit_id = floor.exit_room_ids[0] if floor.exit_room_ids else None
    if exit_id and exit_id in floor.rooms:
        unlocked_reach = _bfs_reachable_excluding_locked(floor, floor.start_room_id)
        # Don't require exit unlocked — but require AT LEAST one path through locks
        if exit_id not in reachable:
            errs.append("exit_unreachable_via_graph")

    # No clue should reveal a tag that no entity/room provides
    # (Soft check: just ensure clue rooms exist for placed clues)
    placed_clue_keys = set()
    for r in floor.rooms.values():
        for f in r.fragments:
            placed_clue_keys.add(f)
    for ck in placed_clue_keys:
        if cl.get_clue(ck) is None:
            errs.append(f"unknown_clue:{ck}")

    # Pure linear chain check (allowed for some archetypes; we tolerate this)
    if floor.objective_key:
        # at least one branch should exist somewhere
        if not any(len(r.exits) >= 2 for r in floor.rooms.values()):
            errs.append("graph_is_pure_linear")

    # Room visible_state isn't "combat"/"boss" on creation (type hidden)
    for r in floor.rooms.values():
        if r.visible_state in ("combat","boss","trap","loot","lore"):
            errs.append(f"type_leak:{r.room_id}")

    # At least one non-combat path must exist —
    # we treat the presence of any safehouse/secret/social/lore room as evidence
    non_combat_count = sum(1 for r in floor.rooms.values()
                           if r.actual_type in ("safehouse","secret","lore","loot"))
    if non_combat_count < 2:
        errs.append("no_non_combat_paths")

    # Prompt 06a, gap #4: objective.required_tags must be satisfiable
    if floor.objective_key:
        obj = cl.all_floor_objectives().get(floor.objective_key, {})
        required = list(obj.get("required_tags", []))
        if required:
            present = set()
            for r in floor.rooms.values():
                present.update(r.sensory_tags or [])
                present.add(r.actual_type)
                if r.safehouse_subtype:
                    present.update(["safehouse", r.safehouse_subtype])
                for e in r.entities:
                    present.update(e.tags or [])
                for ckey in r.fragments:
                    cd = cl.get_clue(ckey) if hasattr(cl, "get_clue") else None
                    if cd:
                        present.update(cd.get("reveals", []) or [])
                        present.update(cd.get("tags", []) or [])
            missing = [t for t in required if t not in present]
            if missing:
                errs.append("missing_required_tag:" + ",".join(missing))

    return errs


# ── Build pipeline ───────────────────────────────────────────────────────────

def _build_floor_once(world, floor_number: int, rng: random.Random,
                      archetype_key: Optional[str]) -> FloorState:
    """Run the full 13-step generation pipeline once."""
    # Step 1: archetype
    if archetype_key is None or archetype_key not in FLOOR_ARCHETYPES:
        archetype_key = rng.choice(list(FLOOR_ARCHETYPES.keys()))
    arch = FLOOR_ARCHETYPES[archetype_key]

    # Step 2: theme  (reuse procgen helper — keep theme simple for now)
    theme_label = arch.get("fallback_label", "Piętro 1")
    f = FloorState(
        floor_id=f"gen_floor_{floor_number}",
        floor_number=floor_number,
    )
    f.title_key = ""
    f.title_fallback = f"Piętro {floor_number} — {theme_label}"
    f.theme_fallback = theme_label
    # Prompt 18: pick floor sponsor from the sponsor catalog by
    # floor-number rotation. `sponsor_key` holds the *catalog* key (e.g.
    # "novachem_biotech") so engine.sponsors.current_floor_sponsor_key
    # can find the record; the top-bar `t(sponsor_key, fallback=...)`
    # call falls back to `sponsor_fallback` because catalog keys aren't
    # locale keys themselves.
    try:
        from ..content.data.sponsors import sponsor_for_floor, get_sponsor
        from ..ui.lang import t as _t
        skey = sponsor_for_floor(floor_number)
        sdata = get_sponsor(skey)
        name_pl = _t(sdata.get("name_key", ""),
                     fallback=sdata.get("name_fallback", skey))
        f.sponsor_key = skey
        f.sponsor_fallback = f"Sponsoruje: {name_pl}."
    except Exception:
        f.sponsor_key = "floor1_sponsor"
        f.sponsor_fallback = "Sponsoruje: NovaChem Biotech."

    # Stash archetype on floor for inspection / save
    f.active_events.append({
        "minute": 0, "kind": "gen_archetype",
        "args": {"archetype": archetype_key},
    })

    # Step 3: pick room count
    room_count = rng.randint(arch["min_rooms"], arch["max_rooms"])

    # Step 4: build the connected graph
    graph = _build_graph(arch, room_count, rng)

    # Step 5-12: place content. Pick role assignment per node, then instantiate.
    role_plan = _plan_roles(graph, arch, rng)
    _instantiate_rooms(f, world, graph, role_plan, rng, floor_number)

    # Step 6: pick objective and seed required hints
    _pick_objective(f, arch, rng)

    # Step 7: locks
    _place_locks(f, arch, rng)

    # Step 8: clue chain (place clues onto appropriate rooms as fragments)
    _place_clue_chain(f, rng)

    # Step 9: place encounters in combat rooms, weighted by objective tags
    # (and, when belief seeds exist on the world, by their target_tags too).
    _place_encounters(f, rng, world=world)

    # Step 10: ensure objective.required_tags are present somewhere on the floor
    _ensure_required_tags(f, rng)

    # Step 12 (rumors): seed one or two rumor keys onto the floor for safehouse chats
    _seed_initial_rumors(f, rng)

    # Step 13: mark start visited, populate known/discovered
    start = f.rooms[f.start_room_id]
    start.visited = True
    start.last_visited_minute = 0
    f.discovered_room_ids.add(f.start_room_id)
    f.known_room_ids.add(f.start_room_id)
    for label, ed in start.exits.items():
        if ed.get("target"):
            f.known_room_ids.add(ed["target"])

    # Deadline
    from ..config import MINUTES_PER_DAY, FLOOR1_DEADLINE_DAYS
    f.deadline_minute = MINUTES_PER_DAY * FLOOR1_DEADLINE_DAYS
    return f


# ── Graph generation ─────────────────────────────────────────────────────────

def _build_graph(arch: Dict, room_count: int,
                 rng: random.Random) -> Dict[str, List[str]]:
    """Return adjacency dict room_id -> list[neighbour room_ids].
    All edges are bidirectional unless explicitly locked/hidden later."""
    shape = arch.get("graph_shape", "wide_layered")
    if shape == "wide_layered":
        return _graph_layered(room_count, arch, rng, dense=True)
    if shape == "branching_dense":
        return _graph_layered(room_count, arch, rng, dense=True, extra_back=2)
    if shape == "hub_spokes":
        return _graph_hub(room_count, arch, rng)
    if shape == "linear_branchy":
        return _graph_layered(room_count, arch, rng, dense=False)
    if shape == "branching":
        return _graph_layered(room_count, arch, rng, dense=True)
    if shape == "narrow":
        return _graph_layered(room_count, arch, rng, dense=False, narrow=True)
    return _graph_layered(room_count, arch, rng, dense=True)


def _graph_layered(n: int, arch: Dict, rng: random.Random,
                   dense=True, narrow=False, extra_back=0):
    """Layered graph: layer 0 = start, layer N = exit area. Add cross-edges."""
    nodes = [f"gen_r{i}" for i in range(n)]
    adj: Dict[str, List[str]] = {x: [] for x in nodes}

    lo = arch.get("layer_size_min", 2)
    hi = arch.get("layer_size_max", 4)
    if narrow:
        lo, hi = 1, max(1, hi // 2)
    layers = [[nodes[0]]]   # layer 0: start
    cursor = 1
    while cursor < n - 1:
        size = rng.randint(lo, hi)
        size = min(size, n - 1 - cursor)
        if size <= 0: break
        layers.append(nodes[cursor:cursor + size])
        cursor += size
    layers.append([nodes[-1]])   # last layer = exit candidate

    # Connect consecutive layers
    for li in range(len(layers) - 1):
        curr = layers[li]; nxt = layers[li + 1]
        connected = set()
        for a in curr:
            count = rng.randint(1, max(1, len(nxt)) if dense else 1)
            count = min(count, len(nxt))
            picks = rng.sample(nxt, count)
            for b in picks:
                if b not in adj[a]:
                    adj[a].append(b); adj[b].append(a)
                    connected.add(b)
        # Ensure every node in nxt has at least one predecessor
        for b in nxt:
            if b not in connected:
                a = rng.choice(curr)
                if b not in adj[a]:
                    adj[a].append(b); adj[b].append(a)

    # Cross-edges (skips a layer) — produce backtracking shortcuts
    cross = arch.get("extra_cross_edges", 0) + extra_back
    for _ in range(cross):
        i = rng.randint(0, len(layers) - 3) if len(layers) >= 3 else 0
        if i + 2 >= len(layers): continue
        a = rng.choice(layers[i]); b = rng.choice(layers[i + 2])
        if b not in adj[a]:
            adj[a].append(b); adj[b].append(a)

    return {"adjacency": adj, "layers": layers, "nodes": nodes,
            "start": nodes[0], "exit": nodes[-1]}


def _graph_hub(n: int, arch: Dict, rng: random.Random):
    """Hub-and-spoke: central safe room with N branches off of it."""
    nodes = [f"gen_r{i}" for i in range(n)]
    adj: Dict[str, List[str]] = {x: [] for x in nodes}
    hub = nodes[1]   # second node is the safehouse hub
    adj[nodes[0]].append(hub); adj[hub].append(nodes[0])
    # Distribute remaining as 2-3 spoke chains
    remaining = nodes[2:]
    n_spokes = 3 if len(remaining) >= 6 else 2
    chunks = [remaining[i::n_spokes] for i in range(n_spokes)]
    for chunk in chunks:
        prev = hub
        for nd in chunk:
            adj[prev].append(nd); adj[nd].append(prev)
            prev = nd
    return {"adjacency": adj, "layers": [[nodes[0]], [hub]] + chunks,
            "nodes": nodes, "start": nodes[0], "exit": nodes[-1]}


# ── Role planning ────────────────────────────────────────────────────────────

def _plan_roles(graph: Dict, arch: Dict, rng: random.Random) -> Dict[str, str]:
    """Assign each node a role: safe/danger/loot/social/secret/lore/boss/start/exit."""
    plan: Dict[str, str] = {}
    plan[graph["start"]] = "start"
    plan[graph["exit"]] = "boss"

    middle = [n for n in graph["nodes"]
              if n not in (graph["start"], graph["exit"])]

    # Required: at least N safehouses
    safe_count = arch.get("safehouse_count", 1)
    secret_count = arch.get("secret_room_count", 1 if arch.get("secret_chance",0) >= 0.5 else 0)

    # Prompt 22 bug fix: previously safehouse picked uniformly from
    # `middle`. Layer-1 (directly adjacent to start) makes up 25-50%
    # of middle, so the safehouse landed there often enough that
    # 5 consecutive playthroughs hit room 2 every time. Now we EXCLUDE
    # start-neighbors from the candidate pool: safehouse must be at
    # least 2 rooms deep. Falls back to the full middle if there's no
    # deeper room available (tiny floors).
    start_neighbors = set(graph["adjacency"].get(graph["start"], []))
    deeper_middle = [n for n in middle if n not in start_neighbors]

    # Pick safehouse positions: prefer depth over proximity-to-start.
    picked = set()
    while sum(1 for r in plan.values() if r == "safe") < safe_count and middle:
        candidates_pool = (deeper_middle if deeper_middle
                           else middle)
        candidates = [n for n in candidates_pool if n not in picked]
        if not candidates:
            # Fall through to anything left in middle.
            candidates = [n for n in middle if n not in picked]
        if not candidates:
            break
        chosen = rng.choice(candidates)
        plan[chosen] = "safe"
        picked.add(chosen)
        if chosen in middle:
            middle = [m for m in middle if m != chosen]
        if chosen in deeper_middle:
            deeper_middle = [m for m in deeper_middle if m != chosen]

    # Secrets: usually deeper / off the main path
    for _ in range(secret_count):
        candidates = [n for n in graph["nodes"]
                      if n not in plan and len(graph["adjacency"][n]) == 1]
        if not candidates:
            candidates = [n for n in graph["nodes"] if n not in plan]
        if not candidates: break
        chosen = rng.choice(candidates)
        plan[chosen] = "secret"
        picked.add(chosen)

    # Encounter / danger
    remaining = [n for n in graph["nodes"] if n not in plan]
    n_enc = max(2, int(len(graph["nodes"]) * arch.get("encounter_density", 0.3)))
    for _ in range(min(n_enc, len(remaining))):
        chosen = rng.choice(remaining)
        plan[chosen] = "danger"
        remaining.remove(chosen)

    # Loot
    n_loot = max(1, int(len(graph["nodes"]) * 0.18))
    for _ in range(min(n_loot, len(remaining))):
        chosen = rng.choice(remaining); plan[chosen] = "loot"
        remaining.remove(chosen)

    # Lore
    n_lore = 1
    for _ in range(min(n_lore, len(remaining))):
        chosen = rng.choice(remaining); plan[chosen] = "lore"
        remaining.remove(chosen)

    # Anything left: social hubs
    for n in remaining:
        plan[n] = "social"

    return plan


# ── Room instantiation ───────────────────────────────────────────────────────

def _instantiate_rooms(f: FloorState, world, graph: Dict,
                       role_plan: Dict[str, str], rng: random.Random,
                       floor_num: int):
    """Pick a template per role + node, build RoomState, wire exits."""
    used_templates: List[str] = []
    for node_id, role in role_plan.items():
        tmpl = _pick_template_for_role(role, rng, used_templates,
                                       floor_num=floor_num)
        if tmpl is None:
            tmpl = _fallback_template(role)
        used_templates.append(tmpl.get("template_id", ""))
        r = _build_room_from_template(node_id, role, tmpl, rng, world, floor_num)
        f.add_room(r)

    # Wire exits from the adjacency
    for node_id, neighbours in graph["adjacency"].items():
        r = f.rooms.get(node_id)
        if r is None: continue
        # Pick exit labels from the template's exit_hints if available
        labels_pool = list(getattr(r, "_exit_hints", [])) or _generic_exit_labels()
        rng.shuffle(labels_pool)
        for nb in neighbours:
            if nb in r.exits.values() or any(ed.get("target") == nb for ed in r.exits.values()):
                continue
            # Prompt 22 bug fix: previous fallback used `f"przejście do {nb}"`
            # which leaked the procgen room_id (`gen_r2`) into the player-
            # facing exit label. Use the destination's display title
            # instead — falls back to a generic noun if neither is
            # set, never to an internal ID.
            if labels_pool:
                label = labels_pool.pop(0)
            else:
                tgt = f.rooms.get(nb)
                tgt_name = (tgt.display_short_title()
                            if tgt is not None else "")
                if not tgt_name or tgt_name == nb:
                    tgt_name = "korytarz"
                label = f"przejście do {tgt_name}"
            r.exits[label] = {
                "target": nb,
                "locked": False, "hidden": False,
                "hint_key": "", "fallback_hint": "",
            }

    f.start_room_id = graph["start"]
    f.current_room_id = f.start_room_id
    f.exit_room_ids = [graph["exit"]]


def _build_room_from_template(node_id: str, role: str, tmpl: Dict,
                              rng: random.Random, world, floor_num: int) -> RoomState:
    r = RoomState(room_id=node_id)
    # Pick one entry from each pool
    name = _pick_from_pool(tmpl.get("name_pool"), rng)
    fe   = _pick_from_pool(tmpl.get("first_enter_pool"), rng)
    lk   = _pick_from_pool(tmpl.get("look_pool"), rng)
    sr   = _pick_from_pool(tmpl.get("search_pool"), rng)
    ph   = _pick_from_pool(tmpl.get("public_hint_pool"), rng)

    r.fallback_short_title = name or role
    r.fallback_title = name or role
    r.fallback_first_enter = fe or ""
    r.fallback_look = lk or ""
    r.fallback_search = sr or ""
    r.fallback_public_hint = ph or ""

    r.actual_type = tmpl.get("actual_type", role)
    # Only safe-role rooms inherit the template's safehouse subtype — otherwise
    # social-role rooms picked from the lounge template would all become safehouses.
    if role == "safe":
        r.safehouse_subtype = tmpl.get("safehouse_subtype")
    else:
        r.safehouse_subtype = None
    r.sensory_tags = list(tmpl.get("sensory_tags", []))
    # Type stays HIDDEN until visited
    from .room import S_UNKNOWN
    r.visible_state = S_UNKNOWN

    # Instantiate seeded entities
    seeds_by_kind = tmpl.get("entity_seed_pools", {})
    for kind, keys in seeds_by_kind.items():
        for key in keys:
            ent = _seed_to_entity(kind, key, node_id, world, floor_num, rng)
            if ent is not None:
                r.entities.append(ent)
                world.register(ent)

    # Gap 3: safehouse ownership. Anything that spawns inside a safehouse-role
    # room (cafe / bathroom / clinic / armory / lounge / merchant) belongs to
    # the safehouse. Salvage validator will use these flags to apply social
    # consequences instead of treating it as free loot.
    if role == "safe":
        for e in r.entities:
            if e.state is None:
                e.state = {}
            e.state.setdefault("owned_by", "safehouse")
            e.state.setdefault("theft_sensitive", True)

    # Stash exit_hints for later wiring
    r._exit_hints = list(tmpl.get("exit_hints", []))

    if role == "start":
        r.actual_type = "start"
        # Start room is always immediately visible
        from .room import S_VISITED
        r.visible_state = S_VISITED

    if role == "boss":
        r.actual_type = "boss"

    return r


def _seed_to_entity(kind: str, key: str, room_id: str,
                    world, floor_num: int, rng: random.Random):
    if kind == "env":
        return _entity_from_table(ENV, key, room_id, T_OBJECT)
    if kind == "haz":
        return _entity_from_table(HAZ, key, room_id, T_HAZARD)
    if kind == "term":
        return _entity_from_table(TERM, key, room_id, T_TERMINAL)
    if kind == "svc":
        return _entity_from_table(SVC, key, room_id, T_SERVICE)
    if kind == "mon":
        return _entity_from_table(MON, key, room_id, T_MONSTER)
    if kind == "item":
        return make_item(key, location_id=room_id)
    if kind == "npc":
        # key can be a 2-tuple (archetype, disposition)
        if isinstance(key, (list, tuple)) and len(key) >= 2:
            arch_key, dispo = key[0], key[1]
        else:
            arch_key, dispo = key, None
        return make_random_crawler(floor_num, room_id,
                                   disposition=dispo, archetype_key=arch_key)
    return None


def _entity_from_table(table: Dict, key: str, room_id: str, etype: str):
    proto = table.get(key)
    if proto is None:
        return None
    return Entity(
        key=key, entity_type=etype,
        name_key=proto.get("name_key", ""),
        fallback_name=proto.get("fallback_name", key.replace("_"," ")),
        desc_key=proto.get("desc_key", ""),
        fallback_desc=proto.get("fallback_desc", ""),
        tags=list(proto.get("tags", [])),
        affordances=list(proto.get("affordances", ["inspect"])),
        location_id=room_id,
        hp=proto.get("hp", 0), max_hp=proto.get("max_hp", 0),
        ac=proto.get("ac", 10),
        attack_bonus=proto.get("attack_bonus", 0),
        damage_dice=proto.get("damage_dice", "1d4"),
    )


def _pick_template_for_role(role: str, rng: random.Random,
                            used: List[str],
                            floor_num: int = 1) -> Optional[Dict]:
    pool = cl.room_templates_for_role(role)
    # Avoid reusing unique-per-floor templates
    pool = [t for t in pool if not (t.get("unique_per_floor") and t.get("template_id") in used)]
    # P29.1 — floor_min / floor_max gate so e.g. pool_zaplecze_bar
    # (floor_min=6) can't be picked for a floor-3 combat slot.
    pool = [t for t in pool if t.get("floor_min", 1) <= floor_num]
    pool = [t for t in pool
            if t.get("floor_max") is None or t.get("floor_max") >= floor_num]
    if not pool:
        return None
    weights = [max(1, int(t.get("weight", 1))) for t in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def _fallback_template(role: str) -> Dict:
    """Minimal usable template if the pool is empty for a role."""
    return {
        "template_id": f"fallback_{role}",
        "actual_type": role,
        "name_pool": [f"Pomieszczenie ({role})"],
        "first_enter_pool": ["Wchodzisz do nieopisanego pokoju. Coś tu jest. Albo nic."],
        "look_pool": ["Pokój. Cztery ściany. Powietrze."],
        "search_pool": ["Nic ciekawego."],
        "public_hint_pool": ["Cisza."],
        "sensory_tags": [],
        "entity_seed_pools": {},
        "exit_hints": [],
    }


# ── Objective / locks / clues / rumors ───────────────────────────────────────

def _pick_objective(f: FloorState, arch: Dict, rng: random.Random):
    preferred = arch.get("preferred_objectives", [])
    available = cl.all_floor_objectives()
    candidates = [k for k in preferred if k in available] or list(available.keys())
    if not candidates:
        f.objective_key = ""; return
    key = rng.choice(candidates)
    obj = available[key]
    f.objective_key = key
    f.objective_title_fallback = obj.get("fallback_title", "")
    f.objective_description_fallback = obj.get("description", "")
    f.objective_solution_paths = list(obj.get("solution_paths", []))
    f.exit_conditions = [key]


def _place_locks(f: FloorState, arch: Dict, rng: random.Random):
    """Lock N random exits, preferring ones that don't isolate the start."""
    target_locks = arch.get("lock_count", 1)
    if target_locks <= 0: return
    # Find candidate exits: those that don't lead to start and have a counter-edge
    candidates = []
    for rid, room in f.rooms.items():
        if rid == f.start_room_id: continue
        for label, ed in room.exits.items():
            if ed.get("locked"): continue
            tgt = ed.get("target","")
            if tgt == f.start_room_id: continue
            candidates.append((rid, label))
    rng.shuffle(candidates)
    locked = 0
    for rid, label in candidates:
        if locked >= target_locks: break
        # Lock; check we don't isolate the exit
        room = f.rooms[rid]
        room.exits[label]["locked"] = True
        room.exits[label]["fallback_hint"] = "Zamknięte. Wymaga klucza albo sprytu."
        reachable_after = _bfs_reachable_excluding_locked(f, f.start_room_id)
        if f.exit_room_ids and f.exit_room_ids[0] not in reachable_after:
            # Undo — would isolate exit
            room.exits[label]["locked"] = False
            room.exits[label]["fallback_hint"] = ""
            continue
        locked += 1


def _place_clue_chain(f: FloorState, rng: random.Random):
    """Distribute clues from the objective's chain across appropriate rooms.

    Prompt 06a (gap #2): when a candidate room is a safehouse, prefer it
    only if its template's `possible_clue_sources` includes the clue's
    source. Plain actual_type fallback still applies."""
    if not f.objective_key:
        return
    chain = cl.clues_for_objective(f.objective_key)
    if not chain:
        return
    # Generic actual_type fallback (used when safehouse metadata doesn't match)
    source_pref = {
        "rumor":         {"safehouse"},
        "terminal":      {"loot", "lore"},
        "graffiti":      {"safehouse", "secret"},
        "corpse_note":   {"combat"},
        "npc_dialogue":  {"safehouse", "social"},
        "lore_fragment": {"lore"},
    }

    # Pull safehouse subtype -> possible_clue_sources from templates
    safehouse_sources = {}
    for subtype, tmpl in cl.all_safehouse_templates().items():
        srcs = tmpl.get("possible_clue_sources") or []
        if srcs:
            safehouse_sources[subtype] = set(srcs)

    rooms_list = list(f.rooms.values())
    for ckey, clue in chain:
        src = clue.get("source", "rumor")
        # Priority 1: safehouse rooms whose template declares this source
        prio_candidates = []
        for r in rooms_list:
            if ckey in r.fragments:
                continue
            sub = getattr(r, "safehouse_subtype", None)
            if sub and src in safehouse_sources.get(sub, set()):
                prio_candidates.append(r)
        # Priority 2: actual_type fallback
        if not prio_candidates:
            prefs = source_pref.get(src, set())
            prio_candidates = [r for r in rooms_list
                               if r.actual_type in prefs and ckey not in r.fragments]
        # Priority 3: anything non-start
        if not prio_candidates:
            prio_candidates = [r for r in rooms_list
                               if r.actual_type != "start" and ckey not in r.fragments]
        if not prio_candidates:
            continue
        chosen = rng.choice(prio_candidates)
        chosen.fragments.append(ckey)


def _seed_initial_rumors(f: FloorState, rng: random.Random):
    """Pre-seed 1-3 rumor keys on the floor so cafe chat has something.

    Prompt 07b: bias toward objective tags. Distribution target:
      ~50 percent relevant or partially relevant
      ~25 percent atmospheric / noisy
      ~15 percent misleading / biased
      ~10 percent rare / very useful (truth >= 0.9 AND objective overlap)
    Exact mix is approximate — we pick from weighted buckets per slot.
    """
    table = cl.all_rumor_categories()
    if not table:
        return

    # Pull objective tag set for biasing.
    obj_meta = cl.all_floor_objectives().get(f.objective_key, {}) if f.objective_key else {}
    obj_tags = set(obj_meta.get("tags", []) + obj_meta.get("required_tags", []))

    def _rumor_tag_pool(r):
        return set(r.get("tags") or []) | set(r.get("reveals_tags") or []) \
             | set(r.get("objective_tags") or [])

    relevant: list = []
    atmospheric: list = []
    misleading: list = []
    rare: list = []
    for cat, items in table.items():
        for r in items:
            truth = float(r.get("truth", 0.5))
            tags = _rumor_tag_pool(r)
            overlaps = bool(obj_tags & tags) if obj_tags else False
            if truth >= 0.9 and overlaps:
                rare.append(r)
            elif overlaps and truth >= 0.5:
                relevant.append(r)
            elif truth < 0.4:
                misleading.append(r)
            else:
                atmospheric.append(r)

    # Slot 1 (always): try rare → relevant → atmospheric
    def _pick(bucket):
        return rng.choice(bucket)["key"] if bucket else None

    picks = []
    for bucket in (rare, relevant, atmospheric):
        k = _pick(bucket)
        if k:
            picks.append(k); break

    # Slot 2: 60% another relevant, 25% atmospheric, 15% misleading
    r2 = rng.random()
    bucket2 = (relevant if r2 < 0.60 else
               atmospheric if r2 < 0.85 else
               misleading)
    k2 = _pick(bucket2)
    if k2 and k2 not in picks:
        picks.append(k2)

    # Optional slot 3 with low probability — extra noise.
    if rng.random() < 0.30:
        k3 = _pick(atmospheric or misleading or relevant)
        if k3 and k3 not in picks:
            picks.append(k3)

    for k in picks:
        if k not in f.rumors:
            f.rumors.append(k)


# ── Graph utilities ──────────────────────────────────────────────────────────

def _bfs_reachable(floor: FloorState, start_id: str) -> set:
    """All rooms reachable from start, ignoring locks (just connectivity)."""
    if start_id not in floor.rooms: return set()
    seen = {start_id}
    frontier = [start_id]
    while frontier:
        rid = frontier.pop()
        r = floor.rooms.get(rid)
        if r is None: continue
        for ed in r.exits.values():
            t = ed.get("target")
            if t and t in floor.rooms and t not in seen:
                seen.add(t); frontier.append(t)
    return seen


def _bfs_reachable_excluding_locked(floor: FloorState, start_id: str) -> set:
    if start_id not in floor.rooms: return set()
    seen = {start_id}
    frontier = [start_id]
    while frontier:
        rid = frontier.pop()
        r = floor.rooms.get(rid)
        if r is None: continue
        for ed in r.exits.values():
            if ed.get("locked"): continue
            t = ed.get("target")
            if t and t in floor.rooms and t not in seen:
                seen.add(t); frontier.append(t)
    return seen


def _pick_from_pool(pool, rng: random.Random):
    if not pool: return None
    return rng.choice(pool)


def _generic_exit_labels():
    return ["wschód","zachód","północ","południe","drzwi","korytarz","przejście"]


# ── Encounter placement (Prompt 06a, gap #3) ─────────────────────────────────

def _place_encounters(f: FloorState, rng: random.Random, world=None):
    """Pick one encounter per combat room.

    Tag scoring sources:
      - objective.tags + objective.required_tags
      - room.sensory_tags + actual_type
      - belief-seed target_tags returned by
        `memetics.encounter_modifiers_for(world, room)` if `world` is given
        (post-07b follow-up; small weight, never dominant).
    """
    obj = cl.all_floor_objectives().get(f.objective_key, {}) if f.objective_key else {}
    obj_tags = set(obj.get("tags", []) + obj.get("required_tags", []))

    combat_rooms = [r for r in f.rooms.values()
                    if r.actual_type == "combat" and not r.encounter_intro_fallback]
    if not combat_rooms:
        return

    pool = cl.all_encounter_templates()
    if not pool:
        return

    # Optional belief overlay — collected per-room because seeds may target
    # only a subset of rooms.
    _memetics = None
    if world is not None and getattr(world, "belief_seeds", None):
        try:
            from . import memetics as _memetics  # type: ignore
        except Exception:
            _memetics = None

    for room in combat_rooms:
        room_tags = set(room.sensory_tags or []) | {room.actual_type}

        belief_tags = set()
        if _memetics is not None:
            try:
                mods = _memetics.encounter_modifiers_for(world, room)
            except Exception:
                mods = []
            for m in mods or []:
                for tg in (m.get("target_tags") or []):
                    belief_tags.add(tg)

        scored = []
        for key, etmpl in pool.items():
            if etmpl.get("floor_min", 1) > f.floor_number:
                continue
            etags = set(etmpl.get("tags", []))
            overlap_obj    = len(etags & obj_tags)
            overlap_room   = len(etags & room_tags)
            overlap_belief = len(etags & belief_tags)
            base_w = max(1, int(etmpl.get("weight", 1)))
            # belief weight is intentionally small (×1) so memetics never
            # outrun objective weight (×3) or room weight (×2).
            score = base_w + overlap_obj * 3 + overlap_room * 2 + overlap_belief
            scored.append((key, etmpl, score))
        if not scored:
            continue
        keys = [(k, t) for k, t, _ in scored]
        weights = [w for _, _, w in scored]
        ekey, etmpl = rng.choices(keys, weights=weights, k=1)[0]
        intro = cl.encounter_intro_line(etmpl)
        room.encounter_key = ekey
        if intro:
            room.encounter_intro_fallback = intro
        # Record on room.state which belief tags nudged the pick — useful
        # for debugging and for resolution-time hooks. Empty unless beliefs
        # actually overlapped this template.
        if belief_tags:
            actual_overlap = list(set(etmpl.get("tags", [])) & belief_tags)
            if actual_overlap:
                room.state = room.state or {}
                room.state.setdefault("encounter_belief_tags", [])
                for tg in actual_overlap:
                    if tg not in room.state["encounter_belief_tags"]:
                        room.state["encounter_belief_tags"].append(tg)


# ── Required-tag guarantee (Prompt 06a, gap #4) ──────────────────────────────

def _ensure_required_tags(f: FloorState, rng: random.Random):
    """Make sure every tag listed in objective.required_tags is present
    somewhere on the floor. If not, plant a synthetic env entity carrying
    the missing tag in a non-start room."""
    if not f.objective_key:
        return
    obj = cl.all_floor_objectives().get(f.objective_key, {})
    required = list(obj.get("required_tags", []))
    if not required:
        return
    present = set()
    for r in f.rooms.values():
        present.update(r.sensory_tags or [])
        present.add(r.actual_type)
        if r.safehouse_subtype:
            present.update(["safehouse", r.safehouse_subtype])
        for e in r.entities:
            present.update(e.tags or [])
            present.add(e.entity_type)
        # Clue-revealed facts count too — for objective purposes
        for ckey in r.fragments:
            cd = cl.get_clue(ckey) if hasattr(cl, "get_clue") else None
            if cd:
                present.update(cd.get("reveals", []) or [])
                present.update(cd.get("tags", []) or [])

    missing = [t for t in required if t not in present]
    if not missing:
        return

    # Plant a synthetic env entity carrying the missing tag(s) in a non-start room
    candidates = [r for r in f.rooms.values() if r.room_id != f.start_room_id]
    if not candidates:
        return
    target_room = rng.choice(candidates)
    from .entity import Entity, T_OBJECT
    plant_key = "objective_relevant_object_" + "_".join(missing)[:24]
    plant = Entity(
        key=plant_key, entity_type=T_OBJECT,
        fallback_name="coś ważnego dla zadania",
        fallback_desc="Element, który wygląda na powiązany z celem piętra.",
        tags=list(missing) + ["objective_path"],
        affordances=["inspect", "use", "loot"],
        location_id=target_room.room_id,
    )
    target_room.entities.append(plant)
    # Record the repair in active_events so debugging is easy
    f.active_events.append({
        "minute": 0, "kind": "gen_required_tag_repair",
        "args": {"missing": missing, "planted_in": target_room.room_id},
    })


# ── Summary for debug printing ───────────────────────────────────────────────

def floor_summary(floor: FloorState) -> Dict:
    archetype = ""
    for ev in floor.active_events:
        if ev.get("kind") == "gen_archetype":
            archetype = ev["args"].get("archetype", "")
            break
    safehouses = [r.room_id for r in floor.rooms.values() if r.safehouse_subtype]
    secrets   = [r.room_id for r in floor.rooms.values() if r.actual_type == "secret"]
    locked_exits = sum(1 for r in floor.rooms.values()
                       for ed in r.exits.values() if ed.get("locked"))
    return {
        "rooms":         len(floor.rooms),
        "archetype":     archetype,
        "theme":         floor.theme_fallback,
        "safehouses":    safehouses,
        "secret_rooms":  secrets,
        "objective":     floor.objective_key,
        "objective_title": floor.objective_title_fallback,
        "solution_paths": list(floor.objective_solution_paths),
        "locked_exits":  locked_exits,
        "validation":    validate_floor(floor),
    }
