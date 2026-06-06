extends SceneTree
## Tests for the RPG progression + fixes added with leveling:
##   - XP / levels / skill points (entity)
##   - armor categorization + equipment AC (item + combat)
##   - line-of-sight awareness (board)
##   - the room-transition "door bounce" fix (floor + floorgen)
## Run: godot --headless --path . -s res://tests/test_progression.gd

var _f := 0
var _n := 0
func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c: _f += 1

func _content() -> Dictionary:
	return {
		"MON": {
			"szczur": {"fallback_name": "Szczur", "tags": ["monster", "small", "organic"], "floor_min": 1, "floor_max": 9},
		},
		"ENV": {
			"stol": {"fallback_name": "Stół", "tags": ["furniture", "wood", "salvageable"], "affordances": ["inspect", "salvage"]},
		},
		"MOB_COMBAT_STATS": {"szczur": [10, "1d4", 1, 11]},
	}

func _initialize() -> void:
	print("=== progression tests ===")

	# ── XP / levels / skill points ───────────────────────────────────────────
	var p := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"])
	_ck(p.level == 1 and p.xp == 0, "a fresh player starts at level 1, 0 XP")
	var need := p.xp_to_next()
	_ck(need == 20, "level 1 needs 20 XP to advance")
	_ck(p.gain_xp(5) == 0 and p.level == 1, "partial XP does not level you up")
	var gained := p.gain_xp(need)            # 5 + 20 = 25 >= 20 -> level 2, 5 left
	_ck(gained == 1 and p.level == 2, "crossing the threshold grants a level")
	_ck(p.xp == 5, "leftover XP carries into the next level")
	_ck(p.xp_to_next() == 45, "the curve escalates (level 2 needs 45)")
	_ck(p.gain_xp(1000) >= 2, "a big haul can grant multiple levels at once")

	# ── Armor categorization + equipment AC ──────────────────────────────────
	_ck(GameItem.category_from_type("wearable") == GameItem.CAT_ARMOR, "wearable -> armor")
	_ck(GameItem.category_from_type("weapon") == GameItem.CAT_WEAPON, "weapon -> weapon")
	_ck(GameItem.category_from_type("oddity") == GameItem.CAT_TOOL, "unknown types fall back to tool, not weapon")
	var hat := GameItem.new("czapka", GameItem.CAT_ARMOR)
	hat.tags = ["slot:head"]
	_ck(hat.armor_slot() == "head", "the slot is read from a slot:* tag")

	var pl := CombatEntity.new(1, "Ty", 100, 12, ["humanoid"])
	pl.faction = "player"
	_ck(pl.armor_bonus() == 0, "no armor worn -> no AC bonus")
	hat.effect = {"slot": "head", "ac_bonus": 2}
	pl.equipment["head"] = hat
	_ck(pl.armor_bonus() == 2, "worn armor contributes to armor_bonus()")

	# equipping through the sim moves it into the slot and out of the pocket
	var board := Board.new(5, 5)
	var pl2 := CombatEntity.new(1, "Ty", 100, 12, ["humanoid"])
	pl2.faction = "player"; pl2.cell = Vector2i(2, 2)
	board.place(1, pl2.cell)
	var vest := GameItem.new("kamizelka", GameItem.CAT_ARMOR)
	vest.effect = {"slot": "body", "ac_bonus": 3}; vest.charges = 0
	var cs := CombatSim.new(board, {1: pl2}, 1, 1)
	cs.items = [vest]
	var ac0 := cs._eff_ac(pl2)
	cs.player_use_item(0)
	_ck(pl2.equipment.get("body") == vest, "using an armor item equips it into its slot")
	_ck(cs.items.is_empty(), "the equipped piece leaves the pocket")
	_ck(cs._eff_ac(pl2) == ac0 + 3, "worn armor raises effective AC")

	# ── XP awarded for a kill (sim path) ─────────────────────────────────────
	var b2 := Board.new(5, 5)
	var hero := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"])
	hero.faction = "player"; hero.cell = Vector2i(1, 1)
	var foe := CombatEntity.new(2, "Szczur", 1, 1, ["organic"])   # 1 HP: dies in one hit
	foe.faction = "enemy"; foe.cell = Vector2i(2, 1); foe.aware = true
	var cs3 := CombatSim.new(b2, {1: hero, 2: foe}, 1, 3)
	b2.place(1, hero.cell); b2.place(2, foe.cell)
	var lvl0 := hero.level
	var xp0 := hero.xp
	for i in 6:
		if foe.is_alive():
			cs3.player_move(Vector2i.RIGHT)   # bump-attack the rat
	_ck(not foe.is_alive(), "the rat dies")
	_ck(hero.level > lvl0 or hero.xp > xp0, "killing an enemy awards XP")

	# ── Line-of-sight on the board ────────────────────────────────────────────
	var los := Board.from_ascii(["#####", "#...#", "#.#.#", "#...#", "#####"])
	_ck(los.has_los(Vector2i(1, 1), Vector2i(3, 1)), "clear row -> line of sight")
	_ck(not los.has_los(Vector2i(1, 2), Vector2i(3, 2)), "a wall between blocks line of sight")

	# ── The door-bounce fix: entering a room must not instantly send you back ──
	var fl := Floor.new(FloorGen.generate(1, 4242, _content()))
	# walk east until we change rooms (or give up after a generous bound)
	var start_room := fl.current
	var hops := 0
	while fl.current == start_room and hops < 40:
		fl.sim.player_move(Vector2i.RIGHT)
		var t = fl.try_transition()
		hops += 1
	_ck(fl.current != start_room, "you can actually cross into the next room")
	# Immediately probing the exit you arrived on must NOT bounce you back.
	var entered := fl.current
	var bounced = fl.try_transition()
	_ck(bounced == null, "standing on the entry cell does not re-trigger the door")
	_ck(fl.current == entered, "you stay in the room you just entered")

	# ── Companion ally: fights enemies, follows you otherwise ─────────────────
	var ab := Board.new(6, 6)
	var ahero := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"]); ahero.faction = "player"; ahero.cell = Vector2i(1, 1)
	var pet := CombatEntity.new(999, "Suczka", 24, 12, ["ally"]); pet.faction = "ally"
	pet.dmg_dice = "1d6"; pet.to_hit = 8; pet.cell = Vector2i(2, 1)
	var afoe := CombatEntity.new(2, "Szczur", 30, 8, ["organic"]); afoe.faction = "enemy"
	afoe.cell = Vector2i(3, 1); afoe.aware = true
	var acs := CombatSim.new(ab, {1: ahero, 999: pet, 2: afoe}, 1, 5)
	for c in [ahero, pet, afoe]:
		ab.place(c.id, c.cell)
	_ck(acs.allies_alive().size() == 1, "the pet counts as an ally, not an enemy")
	_ck(acs.enemies_alive().size() == 1, "allies are excluded from enemies_alive()")
	var fhp := afoe.hp
	acs._ally_turn()                       # pet is adjacent to the foe → attacks
	_ck(afoe.hp < fhp, "the pet attacks an adjacent enemy on its turn")
	_ck(ahero.faction == "player" and ahero.hp == 100, "the pet never harms you")
	# with no enemies left, the pet trots back toward the player
	afoe.alive = false
	ab.clear(Vector2i(2, 1)); pet.cell = Vector2i(5, 5); ab.place(999, pet.cell)
	var pd0: int = maxi(absi(pet.cell.x - ahero.cell.x), absi(pet.cell.y - ahero.cell.y))
	acs._ally_turn()
	var pd1: int = maxi(absi(pet.cell.x - ahero.cell.x), absi(pet.cell.y - ahero.cell.y))
	_ck(pd1 < pd0, "with no enemies, the pet moves toward the player")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
