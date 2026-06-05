class_name Board
extends RefCounted
## Pure tile-grid model shared by explore + combat. No nodes, no rendering.
## This is the spatial substrate that replaces the old abstract engaged/at_range
## bands: positions are real cells, so push-into-hazard / fire-spread / lure are
## literal geometry. See docs/GODOT_PORT_PLAN.md.

var w: int = 0
var h: int = 0
var walls: Dictionary = {}      # Vector2i -> true
var hazards: Dictionary = {}    # Vector2i -> String  ("water","wire","gas","fire")
var occupants: Dictionary = {}  # Vector2i -> int (entity id)

func _init(width: int = 0, height: int = 0) -> void:
	w = width
	h = height

func in_bounds(c: Vector2i) -> bool:
	return c.x >= 0 and c.y >= 0 and c.x < w and c.y < h

func is_wall(c: Vector2i) -> bool:
	return walls.has(c)

func set_wall(c: Vector2i, on: bool = true) -> void:
	if on: walls[c] = true
	else: walls.erase(c)

func set_hazard(c: Vector2i, kind: String) -> void:
	if kind == "": hazards.erase(c)
	else: hazards[c] = kind

func hazard_at(c: Vector2i) -> String:
	return hazards.get(c, "")

func occupant_at(c: Vector2i) -> int:
	return occupants.get(c, -1)

func is_free(c: Vector2i) -> bool:
	return in_bounds(c) and not is_wall(c) and not occupants.has(c)

func place(id: int, c: Vector2i) -> void:
	occupants[c] = id

func move(frm: Vector2i, to: Vector2i) -> void:
	var id: int = occupants.get(frm, -1)
	occupants.erase(frm)
	if id != -1:
		occupants[to] = id

func clear(c: Vector2i) -> void:
	occupants.erase(c)

func is_adjacent(a: Vector2i, b: Vector2i) -> bool:
	if a == b: return false
	var d: Vector2i = (a - b).abs()
	return max(d.x, d.y) == 1   # 8-directional (Chebyshev) adjacency

## Build a board from ASCII rows. Legend: # wall, ~ water, | wire, G gas.
static func from_ascii(rows: Array) -> Board:
	var b := Board.new((rows[0] as String).length(), rows.size())
	for y in rows.size():
		var line: String = rows[y]
		for x in line.length():
			match line[x]:
				"#": b.set_wall(Vector2i(x, y))
				"~": b.set_hazard(Vector2i(x, y), "water")
				"|": b.set_hazard(Vector2i(x, y), "wire")
				"G": b.set_hazard(Vector2i(x, y), "gas")
	return b
