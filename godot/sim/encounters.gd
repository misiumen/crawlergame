class_name Encounters
extends RefCounted
## Single source for encounter setups, shared by the sim tests and the live
## scene so they can never drift. Each returns {board, entities, player_id, hint}.

## The vertical-slice room: you enter a maintenance bay with dismantlable gear,
## a water+wire conductive trap, and a SLEEPING thick-hided, shock-weak rat.
## Choices: scavenge parts (loud — risks waking it), sneak to the exit, or lure
## the rat onto the wet tiles by the sparking wire. Brute works too (slow, costly).
static func intake() -> Dictionary:
	var board := Board.from_ascii([
		"#############",
		"#...........#",
		"#.@...T.....#",   # @ player (2,2), T wood table (6,2)
		"#...........#",
		"#.....C.....#",   # C metal cabinet (6,4)
		"#.......~~..#",   # water (8,5),(9,5)
		"#.......~|..#",   # water (8,6), wire (9,6)  -> live conductive trap
		"#############",
	])
	var ents := {}

	var player := CombatEntity.new(1, "Bezimienny", 100, 14, ["humanoid"])
	player.faction = "player"
	player.cell = Vector2i(2, 2)

	var rat := CombatEntity.new(2, "Tunelowy Szczur", 22, 13,
		["organic", "quadruped", "thick_hide", "shock_weak"])
	rat.faction = "enemy"
	rat.cell = Vector2i(10, 7)
	rat.aware = false                                   # asleep until it notices you

	var table := CombatEntity.new(3, "Drewniany stół", 6, 5, ["furniture", "wood", "salvageable"])
	table.faction = "object"
	table.affordances = ["inspect", "salvage", "break"]
	table.cell = Vector2i(6, 2)

	var cabinet := CombatEntity.new(4, "Szafka z elektroniką", 8, 6,
		["furniture", "metal", "electric", "salvageable"])
	cabinet.faction = "object"
	cabinet.affordances = ["inspect", "salvage", "break"]
	cabinet.cell = Vector2i(6, 4)

	for e in [player, rat, table, cabinet]:
		ents[e.id] = e
		board.place(e.id, e.cell)

	return {
		"board": board,
		"entities": ents,
		"player_id": 1,
		"hint": "Szczur śpi. Rozbierz sprzęt na złom (głośno!), zakradnij się, "
			+ "albo zwab go na kałużę przy iskrzącym kablu.",
	}

## A small two-room floor: a storage room (scavenge) connected by a door to a
## hall with the conductive trap, the sleeping rat, and the stairs down.
static func floor() -> Dictionary:
	var player := CombatEntity.new(1, "Bezimienny", 100, 14, ["humanoid"])

	# Room 0 — Magazyn (storage): furniture to dismantle, a door east.
	var ba := Board.from_ascii([
		"###########",
		"#.........#",
		"#..T......#",
		"#.........#",   # door east at (9,3) -> Hala
		"#.........#",
		"#..C......#",
		"###########",
	])
	var table := CombatEntity.new(3, "Drewniany stół", 6, 5, ["furniture", "wood", "salvageable"])
	table.faction = "object"; table.affordances = ["inspect", "salvage", "break"]; table.cell = Vector2i(3, 2)
	var cabinet := CombatEntity.new(4, "Szafka z elektroniką", 8, 6, ["furniture", "metal", "electric", "salvageable"])
	cabinet.faction = "object"; cabinet.affordances = ["inspect", "salvage", "break"]; cabinet.cell = Vector2i(3, 5)
	ba.place(3, table.cell); ba.place(4, cabinet.cell)
	var room_a := {
		"name": "Magazyn", "board": ba, "entities": {3: table, 4: cabinet},
		"exits": {Vector2i(9, 3): {"to": 1, "at": Vector2i(2, 3)}},
	}

	# Room 1 — Hala (hall): conductive trap, sleeping rat, stairs down.
	var bb := Board.from_ascii([
		"#############",
		"#...........#",
		"#...........#",
		"#...........#",   # entry from Magazyn at (2,3); door back at (1,3)
		"#.....~~....#",   # water (6,4),(7,4)
		"#.....~|....#",   # water (6,5), wire (7,5)
		"#...........#",   # stairs down at (11,6)
		"#############",
	])
	var rat := CombatEntity.new(2, "Tunelowy Szczur", 22, 13,
		["organic", "quadruped", "thick_hide", "shock_weak"])
	rat.faction = "enemy"; rat.cell = Vector2i(10, 3); rat.aware = false
	bb.place(2, rat.cell)
	var room_b := {
		"name": "Hala", "board": bb, "entities": {2: rat},
		"exits": {
			Vector2i(1, 3): {"to": 0, "at": Vector2i(8, 3)},
			Vector2i(11, 6): {"descend": true},
		},
	}

	return {
		"rooms": [room_a, room_b],
		"player": player,
		"inv": {},
		"start": 0,
		"start_cell": Vector2i(2, 3),
		"hint": "Rozbierz sprzęt w magazynie, potem przez drzwi (+) do hali po zejście (>). "
			+ "Szczur śpi — obejdź go, zwab na kałużę, albo skuj broń prądem.",
	}
