class_name Floor
extends RefCounted
## A floor = several rooms connected by doors. Holds the shared player + run
## inventory and swaps the active CombatSim when you step through a door. Room
## state (dismantled objects, enemy HP/awareness) persists because each room's
## board + entities are long-lived objects, mutated in place.

var rooms: Array = []             # [{name, board, entities(no player), exits, ...}]
var player: CombatEntity
var inv: Dictionary = {}          # run materials, shared across rooms
var current: int = -1
var sim: CombatSim
var descended: bool = false

func _init(data: Dictionary) -> void:
	rooms = data["rooms"]
	player = data["player"]
	inv = data.get("inv", {})
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
	board.place(player.id, entry)
	var ents: Dictionary = {player.id: player}
	for id in room["entities"]:
		ents[id] = room["entities"][id]
	sim = CombatSim.new(board, ents, player.id, 1337 + idx, inv)

## Returns true if the player is standing on a door, and performs the move.
## "descend" exits set `descended` and do not change rooms.
func try_transition() -> Variant:
	var ex = exit_at(player.cell)
	if ex == null:
		return null
	if ex.get("descend", false):
		descended = true
		return {"descend": true}
	enter(int(ex["to"]), ex["at"])
	return {"to": current, "name": current_name()}
