class_name CombatEntity
extends RefCounted
## A combatant / actor in the sim. No nodes. Tags drive systemic properties
## (the same tag data the Python game uses), so behaviour and — later — the
## procedural body rig both read from one source.

var id: int = 0
var name_pl: String = ""
var tags: Array = []
var max_hp: int = 1
var hp: int = 1
var ac: int = 10
var cell: Vector2i = Vector2i.ZERO
var statuses: Dictionary = {}    # status name -> turns remaining
var faction: String = "enemy"    # "player" | "enemy" | "neutral"
var alive: bool = true

func _init(_id: int = 0, _name: String = "", _hp: int = 1, _ac: int = 10, _tags: Array = []) -> void:
	id = _id
	name_pl = _name
	max_hp = _hp
	hp = _hp
	ac = _ac
	tags = _tags.duplicate()

func is_alive() -> bool:
	return alive and hp > 0

func properties() -> Dictionary:
	return Tags.properties_for(tags)

func has_property(p: String) -> bool:
	return properties().has(p)

func add_status(s: String, turns: int) -> void:
	statuses[s] = max(int(statuses.get(s, 0)), turns)

func has_status(s: String) -> bool:
	return int(statuses.get(s, 0)) > 0

func tick_statuses() -> void:
	for s in statuses.keys():
		statuses[s] = int(statuses[s]) - 1
		if statuses[s] <= 0:
			statuses.erase(s)

func take_damage(amount: int) -> void:
	hp = max(0, hp - amount)
	if hp <= 0:
		alive = false
