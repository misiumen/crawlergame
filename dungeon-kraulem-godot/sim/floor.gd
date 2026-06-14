class_name Floor
extends RefCounted
## A floor = several rooms connected by doors. Holds the shared player + run
## inventory and swaps the active CombatSim when you step through a door. Room
## state (dismantled objects, enemy HP/awareness) persists because each room's
## board + entities are long-lived objects, mutated in place.

var rooms: Array = []             # [{name, board, entities(no player), exits, ...}]
var player: CombatEntity
var companion: CombatEntity = null  # meta-progression pet ally, carried like the player
var inv: Dictionary = {}          # run materials, shared across rooms
var items: Array = []             # GameItem list — crafted or found
var boxes: Array = []             # GameBox list — unopened lootboxes
var discovered_recipes: Array = []# [{tags, name, times}] — recipe book
var current: int = -1
var sim: CombatSim
var descended: bool = false
var audience: AudienceState
var sponsors: SponsorState
var turn: int = 0
var time_days: int = 5        # collapse budget, in dungeon days
var time_limit: int = 150     # collapse budget, in turns (30/day)
var schedule: Array = []      # the Director's RAMOWKA: [{turn, kind}]
var class_offered: bool = false   # once we've offered a class, don't nag again

var depth: int = 1                 # how many floors deep this run is (1-based)
var biome: String = ""             # the route-biome this floor was generated with
var objective: Dictionary = {}     # this floor's tracked side-goal (see Objectives)

# The cell the player was just placed on by a room transition. Exits on THIS cell
# are disarmed until the player steps off — otherwise you'd bounce straight back
# through the door you arrived from (the back-door sits on the entry cell).
var _entered_on: Vector2i = Vector2i(-9999, -9999)

func _init(data: Dictionary) -> void:
	rooms = data["rooms"]
	player = data["player"]
	inv = data.get("inv", {})
	depth = int(data.get("depth", data.get("floor_num", 1)))
	biome = data.get("biome", "")
	# Run state can be CARRIED FORWARD across floors (descent) or freshly made.
	items = data.get("items", [])
	boxes = data.get("boxes", [])
	discovered_recipes = data.get("discovered", [])
	audience = data.get("audience", null) if data.get("audience", null) is AudienceState else AudienceState.new()
	sponsors = data.get("sponsors", null) if data.get("sponsors", null) is SponsorState else SponsorState.new()
	class_offered = bool(data.get("class_offered", false))
	time_days = int(data.get("time_days", 5))
	time_limit = int(data.get("time_limit", 150))
	schedule = data.get("schedule", [])
	objective = data.get("objective", {}) if data.get("objective", {}) is Dictionary else {}
	companion = data.get("companion", null) if data.get("companion", null) is CombatEntity else null
	enter(int(data.get("start", 0)), data["start_cell"])

func current_name() -> String:
	return rooms[current].get("name", "?")

func exit_at(cell: Vector2i) -> Variant:
	return rooms[current]["exits"].get(cell, null)

func enter(idx: int, entry: Vector2i) -> void:
	# Converts/charmed-to-your-side allies FOLLOW you through doors: lift them out
	# of the room they were recruited in before switching (they're room entities,
	# unlike the companion which the Floor carries directly).
	var followers: Array = []
	if current >= 0:
		var old_board: Board = rooms[current]["board"]
		old_board.clear(player.cell)
		if companion != null:
			old_board.clear(companion.cell)
		var old_ents: Dictionary = rooms[current]["entities"]
		for fid in old_ents.keys():
			var fe = old_ents[fid]
			if fe is CombatEntity and fe.faction == "ally" and fe.is_alive() \
					and (companion == null or fe.id != companion.id):
				followers.append(fe)
				old_board.clear(fe.cell)
				old_ents.erase(fid)
	current = idx
	var room: Dictionary = rooms[idx]
	var board: Board = room["board"]
	player.cell = entry
	_entered_on = entry          # disarm exits on this cell until we step off it
	board.place(player.id, entry)
	var ents: Dictionary = {player.id: player}
	for id in room["entities"]:
		ents[id] = room["entities"][id]
	# The pet ally follows the player from room to room: drop it on a free cell next
	# to where the player just arrived.
	if companion != null and companion.is_alive():
		var spot := _free_cell_near(board, entry, ents)
		if spot != Vector2i(-1, -1):
			companion.cell = spot
			board.place(companion.id, spot)
			ents[companion.id] = companion
	# Recruited allies file in behind you and become entities of THIS room.
	for fe2 in followers:
		var fspot := _free_cell_near(board, entry, ents)
		if fspot == Vector2i(-1, -1):
			continue
		fe2.cell = fspot
		board.place(fe2.id, fspot)
		ents[fe2.id] = fe2
		room["entities"][fe2.id] = fe2
	sim = CombatSim.new(board, ents, player.id, 1337 + idx,
			inv, items, discovered_recipes, audience, sponsors)

## Attach a companion to an already-built floor (used on resume, where the floor
## was rebuilt before the companion existed). Injects it into the current sim.
func attach_companion(c: CombatEntity) -> void:
	companion = c
	if c == null or sim == null or current < 0:
		return
	var board: Board = rooms[current]["board"]
	var spot := _free_cell_near(board, player.cell, sim.entities)
	if spot != Vector2i(-1, -1):
		c.cell = spot
		board.place(c.id, spot)
		sim.entities[c.id] = c

## Inject a recruited ally (a convert) into the current room — used when the
## crusade follows you down a floor. Registers it as a room entity so it
## persists and keeps following through doors.
func attach_follower(f: CombatEntity) -> void:
	if f == null or sim == null or current < 0:
		return
	var board: Board = rooms[current]["board"]
	var spot := _free_cell_near(board, player.cell, sim.entities)
	if spot == Vector2i(-1, -1):
		return
	f.cell = spot
	board.place(f.id, spot)
	sim.entities[f.id] = f
	rooms[current]["entities"][f.id] = f

## A walkable, unoccupied cell adjacent (then near) `origin`, or (-1,-1) if none.
func _free_cell_near(board: Board, origin: Vector2i, ents: Dictionary) -> Vector2i:
	for r in [1, 2]:
		for dy in range(-r, r + 1):
			for dx in range(-r, r + 1):
				if dx == 0 and dy == 0:
					continue
				var c := origin + Vector2i(dx, dy)
				if board.in_bounds(c) and not board.is_wall(c) and board.occupant_at(c) == -1:
					return c
	return Vector2i(-1, -1)

## Advance one turn: tick audience idle decay, drain any sponsor boxes.
func advance_turn() -> Array:
	turn += 1
	audience.tick(1)
	var new_boxes := sponsors.drain_boxes()
	for b in new_boxes:
		boxes.append(b)
	return new_boxes   # caller can animate box-arrival notification

## If the player's playstyle now warrants a class, return 3 candidate keys to
## offer (once per run); else []. Presentation shows the picker.
func check_class_offer() -> Array:
	if class_offered or player.class_key != "":
		return []
	if Classes.should_offer(player, depth, turn):
		class_offered = true
		return Classes.suggest_classes(player, 3, sim.rng)
	return []

## Returns {to, name} or {descend: true} or {blocked: "boss"} or null.
func try_transition() -> Variant:
	# Don't fire the exit we were just placed on (prevents the door-bounce). Once
	# the player has moved off that cell, re-arm every exit on the floor.
	if player.cell == _entered_on:
		return null
	_entered_on = Vector2i(-9999, -9999)
	var ex = exit_at(player.cell)
	if ex == null:
		return null
	if ex.get("descend", false):
		# A gated exit (boss arena) won't open until the room is cleared.
		if ex.get("requires_clear", false) and not sim.enemies_alive().is_empty():
			return {"blocked": "boss"}
		# A guarded exit: the floor's Alfa must die first (HOW is your business —
		# blade, fire, bomb from another chamber... the gate only checks the pulse).
		if ex.get("guarded", false):
			for id in sim.entities:
				var ge = sim.entities[id]
				if ge is CombatEntity and ge.is_alive() and "miniboss" in ge.tags:
					return {"blocked": "guard"}
		descended = true
		return {"descend": true}
	enter(int(ex["to"]), ex["at"])
	return {"to": current, "name": current_name()}
