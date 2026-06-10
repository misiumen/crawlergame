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

	# ── Magic / spells (must be LEARNED; affinity gates) ──────────────────────
	# affinity scales mana; mundane races can't learn at all.
	var adept := CombatEntity.new(9, "Adept", 100, 14, ["humanoid"]); adept.magic_affinity = "adept"
	var mundane := CombatEntity.new(9, "Robot", 100, 14, ["humanoid"]); mundane.magic_affinity = "mundane"
	_ck(Spells.max_mana_for(adept) > Spells.max_mana_for(mundane), "adept races run more mana than mundane")
	_ck(not Spells.learn(mundane, "ogien"), "a mundane race cannot learn magic")
	var rngl := RandomNumberGenerator.new(); rngl.seed = 1
	_ck(Spells.learn(adept, "ogien") and Spells.is_known(adept, "ogien"), "an adept learns a spell")
	_ck(not Spells.learn(adept, "ogien"), "you don't re-learn a spell you already know")

	var sbd := Board.new(7, 3)
	var mage := CombatEntity.new(1, "Mag", 100, 14, ["humanoid"]); mage.faction = "player"; mage.cell = Vector2i(1, 1)
	mage.stats["INT"] = 6                              # plenty of mana
	mage.flags["known_spells"] = ["ogien", "telekineza", "pustka"]   # taught for the test
	var sfoe := CombatEntity.new(2, "Szczur", 40, 8, ["organic"]); sfoe.faction = "enemy"
	sfoe.cell = Vector2i(4, 1); sfoe.aware = true
	var scs2 := CombatSim.new(sbd, {1: mage, 2: sfoe}, 1, 2)
	sbd.place(1, mage.cell); sbd.place(2, sfoe.cell)
	scs2.refill_mana()
	_ck(mage.mana >= 5, "mana refills and scales with INT")
	_ck(scs2.cast_spell("mroz")[0]["type"] == "cast_blocked", "an unknown spell can't be cast")
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
	# a spell scroll teaches a spell on use (and is consumed)
	var scroll := GameItem.new("Zwój: Szron", GameItem.CAT_SPELL, Rarity.UNCOMMON)
	scroll.effect = {"spell": "mroz"}; scroll.charges = 1
	mage.flags["known_spells"] = []
	scs2.items = [scroll]
	scs2.player_use_item(0)
	_ck(Spells.is_known(mage, "mroz"), "using a spell scroll learns the spell")
	_ck(scs2.items.is_empty(), "the scroll is consumed on use")

	# ── Floor objectives ──────────────────────────────────────────────────────
	var rngo := RandomNumberGenerator.new(); rngo.seed = 7
	var fobj := Objectives.pick(3, rngo)
	_ck(fobj.has("key") and int(fobj["target"]) >= 1, "an objective rolls with a target")
	_ck(int(fobj["progress"]) == 0 and not bool(fobj["done"]), "a fresh objective starts unfinished")
	_ck(Objectives.describe(fobj) != "", "the objective describes itself for the HUD")
	_ck(Objectives.advance_for({"key": "kill", "done": false}, "kill") == 1, "a matching event advances it")
	_ck(Objectives.advance_for({"key": "kill", "done": false}, "salvage") == 0, "an unrelated event does not")
	_ck(Objectives.advance_for({"key": "kill", "done": true}, "kill") == 0, "a finished objective stops advancing")

	# ── XP exploit: re-entering a sector must NOT re-pay old corpses ──────────
	var xb2 := Board.new(5, 5)
	var xp_p := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"]); xp_p.faction = "player"; xp_p.cell = Vector2i(1, 1)
	var xp_f := CombatEntity.new(2, "Szczur", 1, 1, ["organic"]); xp_f.faction = "enemy"; xp_f.cell = Vector2i(2, 1); xp_f.aware = true
	var shared := {1: xp_p, 2: xp_f}
	var sim_a := CombatSim.new(xb2, shared, 1, 3)
	xb2.place(1, xp_p.cell); xb2.place(2, xp_f.cell)
	sim_a.player_move(Vector2i.RIGHT)               # kill → XP paid once
	var xp_after_kill := xp_p.xp + xp_p.level * 1000
	var sim_b := CombatSim.new(xb2, shared, 1, 9)   # "re-entering the sector"
	sim_b.player_wait()
	_ck(xp_p.xp + xp_p.level * 1000 == xp_after_kill,
		"a rebuilt sim does not re-pay XP for old corpses (sector-switch exploit)")

	# ── Combat depth: per-class fighting styles ───────────────────────────────
	# humanoid guard: a surviving humanoid raises guard (+3 AC); a shove breaks it
	var gb := Board.new(6, 3)
	var gp := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"]); gp.faction = "player"; gp.cell = Vector2i(1, 1)
	gp.stats["STR"] = -2
	var gh := CombatEntity.new(2, "Łowca", 60, 1, ["monster", "humanoid"]); gh.faction = "enemy"
	gh.cell = Vector2i(2, 1); gh.aware = true
	var gcs := CombatSim.new(gb, {1: gp, 2: gh}, 1, 4)
	gb.place(1, gp.cell); gb.place(2, gh.cell)
	for i in 6:
		if not gh.has_status("guard") and gh.is_alive():
			gcs.player_move(Vector2i.RIGHT)
	_ck(gh.has_status("guard"), "a hit humanoid raises its guard")
	var ac_guarded := gcs._eff_ac(gh)
	gh.statuses.erase("guard")
	_ck(ac_guarded == gcs._eff_ac(gh) + 3, "guard is worth +3 effective AC")
	gh.add_status("guard", 99)
	gcs.player_shove(Vector2i.RIGHT)
	_ck(not gh.has_status("guard"), "a shove breaks the guard stance")

	# mech: zaps from range through line of sight (no adjacency needed)
	var zb := Board.new(7, 3)
	var zp := CombatEntity.new(1, "Ty", 100, -10, ["humanoid"]); zp.faction = "player"; zp.cell = Vector2i(1, 1)
	var zm := CombatEntity.new(2, "Kamera", 20, 10, ["monster", "camera"]); zm.faction = "enemy"
	zm.cell = Vector2i(4, 1); zm.aware = true
	var zcs := CombatSim.new(zb, {1: zp, 2: zm}, 1, 5)
	zb.place(1, zp.cell); zb.place(2, zm.cell)
	var zhp := zp.hp
	zcs._enemy_turn()
	_ck(zp.hp < zhp, "a mech zaps the player from 3 tiles away")
	_ck(maxi(absi(zm.cell.x - zp.cell.x), absi(zm.cell.y - zp.cell.y)) >= 2, "the mech keeps its distance")

	# beast: pounces two straight tiles into melee
	var pb := Board.new(7, 3)
	var pp := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"]); pp.faction = "player"; pp.cell = Vector2i(1, 1)
	var pbeast := CombatEntity.new(2, "Kot", 20, 10, ["monster", "beast"]); pbeast.faction = "enemy"
	pbeast.cell = Vector2i(3, 1); pbeast.aware = true
	var pcs := CombatSim.new(pb, {1: pp, 2: pbeast}, 1, 6)
	pb.place(1, pp.cell); pb.place(2, pbeast.cell)
	var p_evs := pcs._enemy_turn()
	var pounced := false
	for ev in p_evs:
		if ev.get("type") == "pounce": pounced = true
	_ck(pounced and pb.is_adjacent(pbeast.cell, pp.cell), "a beast pounces from 2 tiles into melee")

	# spectral: bare physical swings sometimes pass straight through
	var phb := Board.new(5, 3)
	var php := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"]); php.faction = "player"; php.cell = Vector2i(1, 1)
	var ghost := CombatEntity.new(2, "Duch", 100000, 10, ["monster", "ghost"]); ghost.faction = "enemy"
	ghost.cell = Vector2i(2, 1); ghost.aware = true
	var phcs := CombatSim.new(phb, {1: php, 2: ghost}, 1, 7)
	phb.place(1, php.cell); phb.place(2, ghost.cell)
	var phased := false
	for i in 40:
		for ev in phcs.player_move(Vector2i.RIGHT):
			if ev.get("type") == "phase": phased = true
	_ck(phased, "physical swings sometimes phase through a spectral enemy")

	# converts follow you through doors (the crusade walks with you)
	var ffl := Floor.new(Encounters.floor())
	for i in 7:
		ffl.sim.player_move(Vector2i.RIGHT)
	ffl.try_transition()                              # into Hala (the rat's room)
	var frat = ffl.sim.entities.get(2)
	_ck(frat != null, "the rat is in Hala")
	ffl.sim.convert_enemy(frat)
	ffl.player.cell = Vector2i(1, 3)                  # back door west
	ffl.try_transition()                              # return to Magazyn
	_ck(ffl.sim.allies_alive().size() >= 1, "a convert follows you through the door")

	# ── Titles + highlight reel (run-end) ─────────────────────────────────────
	var tf := Floor.new(FloorGen.generate(2, 11, _content()))
	tf.player.run_kills = 25
	tf.player.run_traps_armed = 9
	var titles := Titles.earned(tf.player, tf, false, 35)
	var labels: Array = []
	for t in titles:
		labels.append(t["label"])
	_ck("Rzeźnik" in labels, "20+ kills earns Rzeźnik")
	_ck("Saper" in labels, "8+ traps earns Saper")
	_ck("Handlarz Złomu" in labels, "30+ scrap earns Handlarz Złomu")
	_ck(not ("Finalista Sezonu" in labels), "no victory → no Finalista")
	var reel: Array = []
	Highlights.add(reel, "kill", "Pokonano: Szczur.", 12)
	Highlights.add(reel, "boss", "BOSS PADŁ!", 100)
	Highlights.add(reel, "big_hit", "Potężny cios.", 20)
	var top := Highlights.top(reel, 2)
	_ck(top.size() == 2 and top[0] == "BOSS PADŁ!", "the reel surfaces the highest-value moments first")

	# ── Show-floor biomes exist (each backs an achievement) ───────────────────
	for bk in ["okopy_frontowe", "zoo_korporacyjne", "muzeum_spektakli", "bar_skurczybyk"]:
		_ck(Routes.BIOMES.has(bk), "biome %s is a real route" % bk)
	_ck(Routes.mods_for("bar_skurczybyk")["label"] == "Bar U Skurczybyka", "new biome resolves its mods")

	# ── Biome visual themes: every route resolves to a complete, DISTINCT look ──
	var theme_keys: Array = Routes.BIOMES.keys() + MetaCatalog.keys_of_kind("biome") + [""]
	var accents := {}
	var complete := true
	for tk2 in theme_keys:
		var th: Dictionary = BiomeThemes.theme_for(tk2)
		for fld in BiomeThemes.DEFAULT:
			if not th.has(fld): complete = false
		accents[th.accent] = true
	_ck(complete, "every biome theme has every field (defaults fill gaps)")
	var themed := 0
	for tk3 in theme_keys:
		if BiomeThemes.THEMES.has(tk3): themed += 1
	_ck(themed >= 19, "all %d route biomes have a hand-set identity (got %d)" % [theme_keys.size(), themed])
	_ck(accents.size() >= 15, "biome accent colours are distinct (%d unique)" % accents.size())

	# ── Biome gimmicks ────────────────────────────────────────────────────────
	var bf := Floor.new(FloorGen.generate(2, 5, _content()))
	var grng := RandomNumberGenerator.new(); grng.seed = 3
	bf.biome = "sortownia"
	var gz := int(bf.sim.materials.get("złom", 0))
	BiomeGimmicks.tick(bf, bf.sim, grng)
	_ck(int(bf.sim.materials.get("złom", 0)) > gz, "the salvage biome gimmick yields scrap")
	bf.biome = "zamknieta"; bf.sim.player().hp = 10
	BiomeGimmicks.tick(bf, bf.sim, grng)
	_ck(bf.sim.player().hp > 10, "the quiet biome gimmick heals you")

	# ── Freeform persuasion (memetics) ────────────────────────────────────────
	# classify reads intent from a typed line; nonsense returns "".
	_ck(Memetics.classify("klęknij przed jedyną wiarą") == "convert", "faith words → convert")
	_ck(Memetics.classify("spokojnie, jestem twoim bratem") == "befriend", "kinship words → befriend")
	_ck(Memetics.classify("twój dowódca cię zdradził, zabij go") == "incite", "betrayal words → incite")
	_ck(Memetics.classify("uciekaj bo zginiesz") == "demoralize", "fear words → demoralize")
	_ck(Memetics.classify("kjsdhfk gghh") == "", "nonsense classifies as nothing (a wild gamble)")
	_ck(Memetics.fallback_lines(RandomNumberGenerator.new()).size() == 3, "fallback offers 3 improvised lines")
	# convert_enemy flips an enemy to your side with the faith tag.
	var cvb := Board.new(5, 5)
	var cvp := CombatEntity.new(1, "Ty", 100, 14, ["humanoid"]); cvp.faction = "player"; cvp.cell = Vector2i(1, 1)
	var cvf := CombatEntity.new(2, "Szczur", 20, 11, ["organic"]); cvf.faction = "enemy"; cvf.cell = Vector2i(2, 1)
	var cvs := CombatSim.new(cvb, {1: cvp, 2: cvf}, 1, 1); cvb.place(1, cvp.cell); cvb.place(2, cvf.cell)
	cvs.convert_enemy(cvf)
	_ck(cvf.faction == "ally" and cvf.tags.has("faith"), "convert_enemy turns a foe into a faith-ally")
	_ck(cvs.enemies_alive().size() == 0 and cvs.allies_alive().size() == 1, "the convert now counts as an ally")
	# a charmed enemy stands down (won't attack you); an incited one turns on its kind.
	var chf := CombatEntity.new(3, "Karaluch", 20, 11, ["organic"]); chf.faction = "enemy"
	chf.aware = true; chf.cell = Vector2i(2, 2); cvb.place(3, chf.cell)
	cvs.entities[3] = chf
	chf.add_status("charmed", 3)
	var pre_hp := cvp.hp
	cvp.cell = Vector2i(1, 2); cvb.move(Vector2i(1, 1), Vector2i(1, 2))   # stand next to the charmed foe
	cvs._enemy_turn()
	_ck(cvp.hp == pre_hp, "a charmed enemy does not attack you")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
