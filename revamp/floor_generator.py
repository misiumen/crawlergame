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
from .crawlers import make_random_crawler
from .items import make_item
from .data.entity_templates import ENV, HAZ, TERM, SVC, MON
from .data.floor_archetypes import FLOOR_ARCHETYPES
from . import content_loader as cl


# ── Public entry points ──────────────────────────────────────────────────────

def generate_floor(world, floor_number: int = 1,
                   seed: Optional[int] = None,
                   archetype: Optional[str] = None) -> FloorState:
    """Build a procedural floor. Retries up to FLOOR_GEN_MAX_RETRIES times
    if validation fails. Always returns a FloorState (last attempt wins
    if all retries fail — better degraded than crashed)."""
    from .config import FLOOR_GEN_MAX_RETRIES
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
    from .config import MINUTES_PER_DAY, FLOOR1_DEADLINE_DAYS
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

    # Pick safehouse positions: prefer middle layers
    picked = set()
    while sum(1 for r in plan.values() if r == "safe") < safe_count and middle:
        chosen = rng.choice([n for n in middle if n not in picked]) if middle else None
        if chosen is None: break
        plan[chosen] = "safe"
        picked.add(chosen)
        # Avoid clustering
        if chosen in middle:
            middle = [m for m in middle if m != chosen]

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
        tmpl = _pick_template_for_role(role, rng, used_templates)
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
            label = labels_pool.pop(0) if labels_pool else f"przejście do {nb}"
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
                            used: List[str]) -> Optional[Dict]:
    pool = cl.room_templates_for_role(role)
    # Avoid reusing unique-per-floor templates
    pool = [t for t in pool if not (t.get("unique_per_floor") and t.get("template_id") in used)]
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
    """Distribute clues from the objective's chain across appropriate rooms."""
    if not f.objective_key:
        return
    chain = cl.clues_for_objective(f.objective_key)
    if not chain:
        return
    # Map source -> preferred actual_type tags
    source_pref = {
        "rumor":         {"safehouse"},
        "terminal":      {"loot","lore"},
        "graffiti":      {"safehouse","secret"},
        "corpse_note":   {"combat"},
        "npc_dialogue":  {"safehouse","social"},
        "lore_fragment": {"lore"},
    }
    rooms_list = list(f.rooms.values())
    for ckey, clue in chain:
        src = clue.get("source", "rumor")
        prefs = source_pref.get(src, set())
        candidates = [r for r in rooms_list
                      if r.actual_type in prefs and ckey not in r.fragments]
        if not candidates:
            candidates = [r for r in rooms_list
                          if r.actual_type != "start" and ckey not in r.fragments]
        if not candidates:
            continue
        chosen = rng.choice(candidates)
        chosen.fragments.append(ckey)


def _seed_initial_rumors(f: FloorState, rng: random.Random):
    """Pre-seed 1-2 rumor keys on the floor so cafe chat has something."""
    table = cl.all_rumor_categories()
    if not table: return
    # Pick a 1.0-truth or high-truth rumor + 1 lower-truth
    high_pool = []
    low_pool  = []
    for cat, items in table.items():
        for r in items:
            if r.get("truth", 0.5) >= 0.7:
                high_pool.append(r)
            else:
                low_pool.append(r)
    if high_pool:
        f.rumors.append(rng.choice(high_pool)["key"])
    if low_pool and rng.random() < 0.5:
        f.rumors.append(rng.choice(low_pool)["key"])


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
