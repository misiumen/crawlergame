class_name Encounters
extends RefCounted
## Single source for encounter setups, shared by the sim tests and the live
## scene so they can never drift. Each returns {board, entities, player_id}.

## The vertical-slice "thinking encounter": a thick-hided, shock-weak rat near a
## water+wire conductive trap. Brute works (slow, costly); luring/shoving the rat
## onto the wet tiles by the sparking wire kills it fast and takes no counter-hit.
static func intake() -> Dictionary:
	var board := Board.from_ascii([
		"#############",
		"#...........#",
		"#.....@.....#",
		"#...........#",
		"#..~~.......#",
		"#..~|.......#",
		"#.........r.#",
		"#############",
	])
	var ents := {}
	var player := CombatEntity.new(1, "Bezimienny", 100, 14, ["humanoid"])
	player.faction = "player"
	player.cell = Vector2i(6, 2)
	var rat := CombatEntity.new(2, "Tunelowy Szczur", 22, 13,
		["organic", "quadruped", "thick_hide", "shock_weak"])
	rat.faction = "enemy"
	rat.cell = Vector2i(10, 6)
	ents[1] = player
	ents[2] = rat
	board.place(1, player.cell)
	board.place(2, rat.cell)
	return {"board": board, "entities": ents, "player_id": 1}
