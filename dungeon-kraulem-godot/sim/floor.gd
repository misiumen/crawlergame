class_name Floor
extends RefCounted
## A floor = several rooms connected by doors. Holds the shared player + run
## inventory and swaps the active CombatSim when you step through a door. Room
## state (dismantled objects, enemy HP/awareness) persists because each room's
## board + entities are long-lived objects, mutated in place.

var rooms: Array = []             # [{name, board, entities(no player), exits, ...}]
var player: CombatEntity
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
var class_offered: bool = false   # once we've offered a class, don't nag again

var depth: int = 1                 # how many floors deep this run is (1-based)
var biome: String = ""             # the route-biome this floor was generated with

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
	enter(int(data.get("start", 0)), data["start_cell"])

func current_name() -> String:
	return rooms[current].get("name", "?")

func exit_at(cell: Vector2i) -> Variant:
	return rooms[current]["exits"].get(cell, null)

func enter(idx: int, entry: Vector2i) -> void:
	if current >= 0:
		(rooms[current]["board"] as Board).clear(player.cell)
	current = idx
	var room: Dictionary = rooms[idx]
	var board: Board = room["board"]
	player.cell = entry
	_entered_on = entry          # disarm exits on this cell until we step off it
	board.place(player.id, entry)
	var ents: Dictionary = {player.id: player}
	for id in room["entities"]:
		ents[id] = room["entities"][id]
	sim = CombatSim.new(board, ents, player.id, 1337 + idx,
			inv, items, discovered_recipes, audience, sponsors)

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
		descended = true
		return {"descend": true}
	enter(int(ex["to"]), ex["at"])
	return {"to": current, "name": current_name()}
