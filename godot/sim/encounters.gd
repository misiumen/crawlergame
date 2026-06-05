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

	var cabinet := CombatEntity.new(4, "Metalowa szafka", 8, 6, ["furniture", "metal", "salvageable"])
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
