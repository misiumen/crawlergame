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

	# ── Species active traits ─────────────────────────────────────────────────
	# poison immunity: the status is refused entirely
	var pi := CombatEntity.new(1, "Mutant", 100, 14, ["humanoid"]); pi.faction = "player"
	pi.species_trait = "poison_immune"
	pi.add_status("poisoned", 3)
	_ck(not pi.has_status("poisoned"), "poison_immune refuses the poisoned status")
	pi.add_status("burning", 2)
	_ck(pi.has_status("burning"), "poison_immune does not block other statuses")

	# regen: a wounded player heals 1/round after an action
	var rb := Board.new(4, 4)
	var rp := CombatEntity.new(1, "Grzyb", 100, 14, ["humanoid"]); rp.faction = "player"
	rp.cell = Vector2i(1, 1); rp.species_trait = "regen"; rp.hp = 50
	var rcs := CombatSim.new(rb, {1: rp}, 1, 1); rb.place(1, rp.cell)
	rcs.player_move(Vector2i.RIGHT)              # one action → one round → +1 regen
	_ck(rp.hp == 51, "the regen trait heals 1 HP per round")

	# salvage_heal: recycling patches the cyborg
	var sb := Board.new(4, 4)
	var sp := CombatEntity.new(1, "Cyborg", 100, 14, ["humanoid"]); sp.faction = "player"
	sp.cell = Vector2i(1, 1); sp.species_trait = "salvage_heal"; sp.hp = 40
	var obj := CombatEntity.new(2, "Szafka", 6, 5, ["metal"]); obj.faction = "object"
	obj.affordances = ["salvage"]; obj.cell = Vector2i(2, 1)
	var scs := CombatSim.new(sb, {1: sp, 2: obj}, 1, 1)
	sb.place(1, sp.cell); sb.place(2, obj.cell)
	scs.player_interact()                         # dismantles the adjacent salvageable
	_ck(sp.hp > 40, "salvage_heal restores HP when you dismantle something")

	# audience floor (Bez Twarzy): rating never drops below the set minimum
	var aud := AudienceState.new()
	aud.min_rating = 10
	aud.change(5, "x")                            # clamps UP to the floor
	_ck(aud.rating >= 10, "audience floor lifts a low rating to the minimum")
	aud.change(-100, "x")
	_ck(aud.rating == 10, "audience floor blocks dropping below the minimum")

	# ── Companion abilities ───────────────────────────────────────────────────
	# find_scrap (dog): grants scrap, once per floor
	var cb := Board.new(6, 6)
	var chero := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"]); chero.faction = "player"; chero.cell = Vector2i(1, 1)
	var dog := CombatEntity.new(999, "Suczka", 24, 12, ["ally"]); dog.faction = "ally"
	dog.monster_key = "companion_suczka_recyklingu"; dog.cell = Vector2i(2, 1)
	var ccs := CombatSim.new(cb, {1: chero, 999: dog}, 1, 1)
	cb.place(1, chero.cell); cb.place(999, dog.cell)
	var z0c := int(ccs.materials.get("złom", 0))
	ccs.use_companion_ability(2)
	_ck(int(ccs.materials.get("złom", 0)) > z0c, "the dog's find-scrap ability grants scrap")
	var blocked := ccs.use_companion_ability(2)   # same floor → on cooldown
	_ck(blocked.size() == 1 and blocked[0]["type"] == "companion_blocked", "the ability is once-per-floor")
	# distract (cat): an enemy loses its next turn
	var kb := Board.new(6, 6)
	var khero := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"]); khero.faction = "player"; khero.cell = Vector2i(1, 1)
	var cat := CombatEntity.new(999, "Kot", 18, 12, ["ally"]); cat.faction = "ally"
	cat.monster_key = "companion_kot_ministerstwa"; cat.cell = Vector2i(2, 1)
	var kfoe := CombatEntity.new(2, "Szczur", 20, 10, ["organic"]); kfoe.faction = "enemy"; kfoe.cell = Vector2i(3, 1); kfoe.aware = true
	var kcs := CombatSim.new(kb, {1: khero, 999: cat, 2: kfoe}, 1, 1)
	for c2 in [khero, cat, kfoe]: kb.place(c2.id, c2.cell)
	kcs.use_companion_ability(1)
	_ck(kfoe.has_status("stunned"), "the cat's distract stuns the nearest enemy")

	# ── Magic / spells ────────────────────────────────────────────────────────
	var sbd := Board.new(7, 3)
	var mage := CombatEntity.new(1, "Mag", 100, 14, ["humanoid"]); mage.faction = "player"; mage.cell = Vector2i(1, 1)
	mage.stats["INT"] = 6                              # plenty of mana
	var sfoe := CombatEntity.new(2, "Szczur", 40, 8, ["organic"]); sfoe.faction = "enemy"
	sfoe.cell = Vector2i(4, 1); sfoe.aware = true
	var scs2 := CombatSim.new(sbd, {1: mage, 2: sfoe}, 1, 2)
	sbd.place(1, mage.cell); sbd.place(2, sfoe.cell)
	scs2.refill_mana()
	_ck(mage.mana >= 5, "mana refills and scales with INT")
	var fhp2 := sfoe.hp
	var m0 := mage.mana
	scs2.cast_spell("ogien")                          # fire bolt at the rat
	_ck(sfoe.hp < fhp2, "casting a fire bolt damages the enemy at range")
	_ck(mage.mana < m0, "casting spends mana (net of slow regen)")
	_ck(sfoe.has_status("burning"), "the fire spell applies burning")
	# telekinesis emits a shove (the enemy may walk back on its own turn after)
	var tk_evs := scs2.cast_spell("telekineza")
	var pushed := false
	for e in tk_evs:
		if e.get("type") == "move" and int(e.get("id", -1)) == sfoe.id:
			pushed = true
	_ck(pushed or not sfoe.is_alive(), "telekinesis shoves the enemy")
	# mana gating
	mage.mana = 0
	var blk := scs2.cast_spell("pustka")
	_ck(blk.size() == 1 and blk[0]["type"] == "cast_blocked", "no mana → cast is blocked")

	# ── Floor objectives ──────────────────────────────────────────────────────
	var rngo := RandomNumberGenerator.new(); rngo.seed = 7
	var fobj := Objectives.pick(3, rngo)
	_ck(fobj.has("key") and int(fobj["target"]) >= 1, "an objective rolls with a target")
	_ck(int(fobj["progress"]) == 0 and not bool(fobj["done"]), "a fresh objective starts unfinished")
	_ck(Objectives.describe(fobj) != "", "the objective describes itself for the HUD")
	_ck(Objectives.advance_for({"key": "kill", "done": false}, "kill") == 1, "a matching event advances it")
	_ck(Objectives.advance_for({"key": "kill", "done": false}, "salvage") == 0, "an unrelated event does not")
	_ck(Objectives.advance_for({"key": "kill", "done": true}, "kill") == 0, "a finished objective stops advancing")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
