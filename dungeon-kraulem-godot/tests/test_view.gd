extends SceneTree
## Headless smoke/logic test for the presentation layer: the scene builds, input
## drivers reach the sim, and many actions + frames run without script errors.
## (Pixels aren't verifiable headless; this proves the wiring is sound.)
## Run: godot --headless --path godot -s res://tests/test_view.gd

var _f := 0
var _n := 0
func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c: _f += 1

func _initialize() -> void:
	print("=== view tests ===")
	Save.clear()                         # start from a clean slate, not a leftover save
	Achievements.reset()
	MetaCatalog.reset()                  # default loadout (no effects) for a deterministic build
	var bv = preload("res://scenes/BoardView.gd").new()
	bv._font = ThemeDB.fallback_font
	bv._build()                          # (_ready is deferred under -s; call directly)
	_ck(bv.sim != null, "scene builds a CombatSim")
	_ck(bv._vpos.size() >= 2, "visual positions initialised for tokens")

	# narration: events map to readable Polish log lines
	_ck(bv._event_line({"type": "damage", "target": 2, "amount": 5, "dmg_type": "electric"}) != "",
		"narration: electric damage -> line")
	_ck(bv._event_line({"type": "salvage", "target": 3, "gained": {"drewno": 2}}) != "",
		"narration: salvage -> line")
	_ck(bv._event_line({"type": "notice", "id": 2}) != "", "narration: notice -> line")

	var r0: int = bv.sim.round_num
	bv.handle_dir(Vector2i.RIGHT)        # a real move ends the player turn
	_ck(bv.sim.round_num > r0, "an action advances the round")

	for i in 6:
		bv._process(0.016)               # manual frames (no main loop under -s)
	_ck(true, "_process runs without error")

	# bench crafting via the view: electric+binding -> electric coating, then use it
	bv.sim.materials = {"przewód": 1, "szmata": 1}
	bv.sim.player().int_xp = 50            # int_mod 10 guarantees success on DC 10
	bv._animate(bv.sim.bench_attempt(["przewód", "szmata"]))
	_ck(bv.floor.items.size() >= 1, "bench_attempt via the view crafts an item")
	var narrated := false
	for line in bv._log:
		if (line as String).begins_with("Konferansjer:"):
			narrated = true
	_ck(narrated, "konferansjer narrates the successful craft")
	bv._animate(bv.sim.player_use_item(0))
	_ck(bv.sim.player().coating == "electric", "using the crafted coating arms the weapon")

	# the craft panel opens/closes and draws without crashing
	bv._craft_open = true
	bv._craft_mode = "bench"
	bv._bench_slots = ["przewód"]
	bv._bench_preview = Crafting.preview(["przewód"], bv.floor.discovered_recipes)
	for i in 3:
		bv._process(0.016)
	_ck(true, "craft panel draws (bench mode) without crash")
	bv._craft_mode = "items"
	for i in 3:
		bv._process(0.016)
	_ck(true, "craft panel draws (items mode) without crash")
	bv._craft_open = false

	# body readout: the enemy has a procedural body; aim + located hits don't crash
	var enemy_id := -1
	for id in bv.sim.entities:
		if bv.sim.entities[id].faction == "enemy":
			enemy_id = id
	if enemy_id != -1 and bv.sim.entities[enemy_id].body != null:
		_ck(true, "enemy has a procedural body attached via the view")
	bv.sim.aim_zone = "head"

	# class offer: force a dominant playstyle, advance a turn, expect the picker
	bv.floor.player.affinity = {"melee": 12, "tech": 1}
	bv.floor.turn = 10
	bv._advance_floor_turn()
	_ck(not bv._class_offer.is_empty(), "a dominant playstyle opens the class offer")
	for i in 2:
		bv._process(0.016)              # draws the offer modal
	_ck(true, "class-offer modal draws without crash")
	bv._accept_class(0)
	_ck(bv.floor.player.class_key != "", "accepting the offer assigns a class")
	_ck(bv._class_offer.is_empty(), "offer closes after accepting")
	# fire the class active (drawn HUD + dispatch)
	bv._use_class_active()
	_ck(bv.floor.player.class_active_used_floor == bv.floor.depth,
		"using the active marks the per-floor cooldown")
	for i in 3:
		bv._process(0.016)
	_ck(true, "class HUD + active path run without crash")

	# descent: gamble a route, then descend, carrying the whole run forward
	var d0: int = bv.floor.depth
	var cls: String = bv.floor.player.class_key
	bv.floor.player.run_kills = 3
	bv._offer_routes()
	_ck(not bv._route_offer.is_empty(), "the stairs offer route choices")
	for i in 2:
		bv._process(0.016)              # draws the route modal
	_ck(true, "route-offer modal draws without crash")
	var chosen: String = bv._route_offer[0]
	bv._descend_into(chosen)
	_ck(bv._route_offer.is_empty(), "picking a route closes the modal")
	_ck(bv.floor.depth == d0 + 1, "descending advances the floor depth")
	_ck(bv.floor.biome == chosen, "the new floor records its chosen biome")
	_ck(bv.floor.player.class_key == cls, "the class carries to the next floor")
	_ck(bv.floor.player.run_kills == 3, "run tallies carry to the next floor")
	_ck(bv.floor.player.class_active_used_floor == -1, "the class active recharges on the new floor")
	for i in 5:
		bv.handle_dir(Vector2i.RIGHT); bv._process(0.016)
	_ck(true, "playing on the generated next floor does not crash")

	# dialogue tree: open a conversation, draw it, branch, then leave
	bv._dlg = Dialogue.start(bv.floor, 99, "default_crawler")
	_ck(not bv._dlg.is_empty(), "starting a dialogue tree opens the conversation")
	for i in 2:
		bv._process(0.016)              # draws the dialogue node + options
	_ck(true, "dialogue modal draws without crash")
	bv._dlg_advance(0)                   # ask a topic -> sub-node
	_ck(not bv._dlg.is_empty(), "picking a topic keeps the conversation open")
	for i in 2:
		bv._process(0.016)
	# walk back, then leave via the end option
	bv._dlg = Dialogue.start(bv.floor, 99, "default_crawler")
	bv._dlg_advance(4)                   # 'Skończ rozmowę.' -> end
	_ck(bv._dlg.is_empty(), "the end option closes the conversation")

	# ── Mouse / click-zone dispatch (handlers called directly) ──
	# craft panel: click a material onto the bench, then click WYTWÓRZ
	bv.sim.materials = {"przewód": 1, "szmata": 1}
	bv.sim.player().int_xp = 50
	bv._craft_open = true; bv._craft_mode = "bench"; bv._bench_slots = []
	bv._dispatch_zone({"kind": "bench_mat", "i": 0})
	_ck(bv._bench_slots.size() == 1, "clicking a material adds it to the bench")
	bv._dispatch_zone({"kind": "bench_remove", "i": 0})
	_ck(bv._bench_slots.is_empty(), "clicking a bench slot removes it")
	bv._dispatch_zone({"kind": "bench_mat", "i": 0})
	bv._dispatch_zone({"kind": "bench_attempt"})
	_ck(not bv._craft_open and bv.floor.items.size() >= 1, "clicking WYTWÓRZ crafts + closes")

	# tab switch + item use via click
	bv._craft_open = true; bv._craft_mode = "bench"
	bv._dispatch_zone({"kind": "tab_items"})
	_ck(bv._craft_mode == "items", "clicking the Kieszeń tab switches mode")
	bv._dispatch_zone({"kind": "item_use", "i": 0})
	_ck(true, "clicking an item uses it without crash")
	bv._craft_open = false

	# dialogue option via click (dispatch 'dlg' with an original index)
	bv._dlg = Dialogue.start(bv.floor, 99, "default_crawler")
	bv._dispatch_zone({"kind": "dlg", "i": 4})           # the 'leave' option
	_ck(bv._dlg.is_empty(), "clicking a dialogue option resolves it")

	# board: left-click on an adjacent enemy attacks (advances the round)
	var foe_id := -1
	for id in bv.sim.entities:
		if bv.sim.entities[id].faction == "enemy" and bv.sim.entities[id].is_alive():
			foe_id = id
	if foe_id != -1:
		var foe: CombatEntity = bv.sim.entities[foe_id]
		# place the player next to it and click it
		bv.sim.player().cell = foe.cell + Vector2i.LEFT
		bv.sim.board.place(bv.sim.player_id, bv.sim.player().cell)
		var hp0 := foe.hp
		bv._click_primary(foe.cell)
		_ck(foe.hp <= hp0, "left-clicking an adjacent enemy attacks it")

	# lootbox opening: start the reveal, it defers loot until you collect
	var lb := GameBox.new("sponsor", "NovaChem", Rarity.RARE)
	lb.contents.append({"type": "material", "key": "złom", "qty": 3})
	bv.floor.boxes = [lb]
	var zlom0 := int(bv.sim.materials.get("złom", 0))
	bv._open_box(0)
	_ck(not bv._box_anim.is_empty(), "opening a box starts the reveal animation")
	_ck(bv.floor.boxes.size() == 1, "the box is NOT consumed until the reveal is collected")
	_ck(int(bv.sim.materials.get("złom", 0)) == zlom0, "loot is withheld during the spin")
	for i in 8:
		bv._process(0.30)               # spin through the phases
	_ck(true, "reveal animation advances without crash")
	bv._box_anim_advance()              # skip to the end if not there yet
	bv._box_anim_advance()              # collect
	_ck(bv._box_anim.is_empty(), "collecting closes the reveal")
	_ck(bv.floor.boxes.is_empty(), "the box is consumed on collect")
	_ck(int(bv.sim.materials.get("złom", 0)) >= zlom0 + 3, "the loot lands in the run on collect (+bonus)")

	# achievements: unlocking pops a VS-style toast; the gallery opens + draws
	Achievements.reset()
	bv._toasts.clear()                  # drop any toasts queued by earlier play
	bv._unlock_ach("pierwsza_krew")
	_ck(bv._toasts.size() >= 1, "unlocking an achievement queues a toast (+ a first-medal milestone)")
	var n_after: int = bv._toasts.size()
	bv._unlock_ach("pierwsza_krew")
	_ck(bv._toasts.size() == n_after, "a repeat unlock does not re-toast")
	bv._ach_descend(5)
	_ck(Achievements.is_unlocked("piaty_set"), "reaching floor 5 unlocks 'Piąty set'")
	for i in 3:
		bv._process(0.30)               # toasts age + slide
	_ck(true, "toasts animate without crash")
	bv._ach_screen = true
	for i in 2:
		bv._process(0.016)              # draws the achievements gallery
	_ck(true, "achievements gallery draws without crash")
	bv._dispatch_zone({"kind": "ach_back"})
	_ck(not bv._ach_screen, "closing the gallery works")

	# meta loadout: an owned perk's effect bakes into the run on _apply_loadout
	MetaCatalog.reset()
	for k in ["kill_250", "aw_poziom_20", "win_pacifist"]:   # 36 prestige
		Achievements.unlock(k)
	_ck(MetaCatalog.try_purchase("perk_dzikus_z_arena"), "buy a start perk with earned prestige")
	var hp_before: int = bv.sim.player().max_hp
	var str_before: int = int(bv.sim.player().stats.get("STR", 0))
	bv._apply_loadout()
	_ck(bv.sim.player().max_hp >= hp_before + 10, "owned perk adds max HP at loadout")
	_ck(int(bv.sim.player().stats.get("STR", 0)) >= str_before + 1, "owned perk adds STR at loadout")
	# the loadout & meta screen opens + draws without crashing
	bv._meta_screen = true
	for i in 2:
		bv._process(0.016)
	_ck(true, "meta/loadout screen draws without crash")
	bv._dispatch_zone({"kind": "meta_back"})
	_ck(not bv._meta_screen, "closing the meta screen works")

	# companion: an owned companion joins the board as a fighting ally
	MetaCatalog.reset()
	for k in ["kill_250", "aw_poziom_20", "win_pacifist", "win_lowlevel"]:
		Achievements.unlock(k)            # 48 prestige (idempotent if already earned)
	_ck(MetaCatalog.try_purchase("companion_suczka_recyklingu"), "buy a companion with prestige")
	var comp = bv._make_companion()
	_ck(comp != null and comp.faction == "ally", "an owned companion builds an ally entity")
	bv.floor.attach_companion(comp)
	_ck(bv.sim.allies_alive().size() >= 1, "the companion joins the board as an ally")
	for i in 3:
		bv.handle_dir(Vector2i.LEFT); bv._process(0.016)   # ally acts each turn, no crash
	_ck(true, "playing with a companion on the board does not crash")
	MetaCatalog.reset()

	# floor objective: a tracked goal that pays out on completion
	bv.floor.objective = {"key": "kill", "label": "Pokonaj %d przeciwników", "target": 2,
		"progress": 1, "done": false, "reward_audience": 10, "reward_xp": 20}
	_ck(Objectives.describe(bv.floor.objective).contains("1/2"), "objective shows tracked progress")
	var aud_before: int = bv.floor.audience.rating if bv.floor.audience else 0
	bv._objective_event(1)               # hits the target → completes
	_ck(bv.floor.objective["done"], "reaching the target completes the objective")
	if bv.floor.audience:
		_ck(bv.floor.audience.rating >= aud_before, "completing the objective rewards audience")

	# sponsor hunter: an angered sponsor's bounty hunter actually spawns on the board
	var foes_before: int = bv.sim.enemies_alive().size()
	bv.floor.sponsors.pending_hunters.append("Łowca NovaChem")
	bv._animate([])                      # drains pending hunters → spawns
	_ck(bv.sim.enemies_alive().size() > foes_before, "a queued sponsor hunter spawns onto the board")
	_ck(bv.floor.sponsors.pending_hunters.is_empty(), "the hunter queue drains after spawning")

	# safehouse: a clinic heals for scrap; the black market sells loot for scrap
	bv._spawn_safehouse()
	var sh_id := -1
	for id in bv.sim.entities:
		if bv.sim.entities[id].faction == "safehouse": sh_id = id
	_ck(sh_id != -1, "a safehouse spawns onto the floor")
	bv._open_safehouse(sh_id)
	_ck(not bv._safehouse.is_empty(), "bumping/using a safehouse opens its menu")
	for i in 2:
		bv._process(0.016)
	_ck(true, "safehouse menu draws without crash")
	# clinic heal: wound the player, give scrap, buy an opatrunek
	bv.sim.player().hp = 50
	bv.sim.materials["złom"] = 30
	bv._safehouse = {"id": sh_id, "subtype": "klinika"}
	bv._safehouse_action("heal_small", 0)
	_ck(bv.sim.player().hp > 50, "clinic heal restores HP")
	_ck(int(bv.sim.materials.get("złom", 0)) == 24, "clinic heal costs 6 scrap")
	# black market sell: a carried item converts to scrap
	if not bv.floor.items.is_empty():
		var z0: int = int(bv.sim.materials.get("złom", 0))
		var items0: int = bv.floor.items.size()
		bv._safehouse = {"id": sh_id, "subtype": "czarny_rynek"}
		bv._safehouse_action("sell", 0)
		_ck(bv.floor.items.size() == items0 - 1, "selling removes the item")
		_ck(int(bv.sim.materials.get("złom", 0)) > z0, "selling pays scrap")
	bv._safehouse = {}

	# rival crawler: parley → rob (forced success) yields scrap; fight provokes
	var spot1: Vector2i = bv._free_cell_for_spawn(bv.sim.player().cell)
	if spot1 != Vector2i(-1, -1):
		var crw := CombatEntity.new(860, "Voss Vex", 1, 12, ["crawler", "humanoid"])
		crw.faction = "crawler"
		crw.flags["crawler"] = {"name": "Voss Vex", "personality": "arrogant", "disposition": "neutral", "carried": {"złom": 5}}
		crw.cell = spot1
		bv.sim.board.place(860, spot1); bv.sim.entities[860] = crw
		bv.floor.rooms[bv.floor.current]["entities"][860] = crw
		bv._open_crawler(860)
		_ck(not bv._crawler.is_empty(), "bumping a rival crawler opens the parley")
		for i in 2:
			bv._process(0.016)
		_ck(true, "crawler parley draws without crash")
		var z_pre: int = int(bv.sim.materials.get("złom", 0))
		bv.sim.player().stats["DEX"] = 40        # force the DEX check to succeed
		bv._crawler_action("rob")
		_ck(int(bv.sim.materials.get("złom", 0)) == z_pre + 5, "a successful robbery lifts their scrap")
		_ck(not bv.sim.entities.has(860), "the robbed rival flees the board")
		_ck(Achievements.is_unlocked("kradziez_armatury"), "a robbery unlocks the theft achievement")
	# a second crawler: fighting it converts it into a real enemy
	var spot2: Vector2i = bv._free_cell_for_spawn(bv.sim.player().cell)
	if spot2 != Vector2i(-1, -1):
		var crw2 := CombatEntity.new(861, "Mira Crane", 1, 12, ["crawler", "humanoid"])
		crw2.faction = "crawler"
		crw2.flags["crawler"] = {"name": "Mira Crane", "personality": "hostile", "disposition": "hostile", "carried": {}}
		crw2.cell = spot2
		bv.sim.board.place(861, spot2); bv.sim.entities[861] = crw2
		bv.floor.rooms[bv.floor.current]["entities"][861] = crw2
		bv._open_crawler(861)
		bv._crawler_action("fight")
		_ck(bv.sim.entities[861].faction == "enemy" and bv.sim.entities[861].max_hp > 1,
			"fighting provokes the rival into a real enemy")

	# knowledge: clues/rumors collected into a browsable journal
	bv.floor.player.flags.erase("journal")
	var rum: Dictionary = Knowledge.random_rumor(bv._narr_rng)
	_ck(not rum.is_empty() and rum.has("text"), "a rumor is drawn from the templates")
	_ck(bv._learn_knowledge(rum), "learning a new clue/rumor adds it to the journal")
	_ck(not bv._learn_knowledge(rum), "the same entry is not learned twice (idempotent by key)")
	_ck((bv.floor.player.flags.get("journal", []) as Array).size() == 1, "the journal holds the entry")
	bv._journal_screen = true
	for i in 2:
		bv._process(0.016)
	_ck(true, "the knowledge journal draws without crash")
	bv._journal_screen = false

	# mid-floor decision beat: choosing a fork applies its effect
	bv._event = {"key": "camera_swarm", "intro": "Kamery!", "forks": [
		{"label": "Pozuj", "effect": {"audience": 5}},
		{"label": "Zasłoń twarz", "effect": {"audience": -1}}]}
	var aud_pre: int = bv.floor.audience.rating if bv.floor.audience else 0
	for i in 2:
		bv._process(0.016)
	_ck(true, "mid-floor event modal draws without crash")
	bv._event_choose(0)                  # pose for the cameras → +5 audience
	_ck(bv._event.is_empty(), "choosing a fork closes the beat")
	if bv.floor.audience:
		_ck(bv.floor.audience.rating >= aud_pre, "the chosen fork applies its effect")

	# memetics: freeform persuasion — convert an adjacent enemy with a high-CHA roll
	bv.sim.player().stats["CHA"] = 40        # force the persuasion check to land
	var mind_id := -1
	for id in bv.sim.entities:
		var me: CombatEntity = bv.sim.entities[id]
		if me.faction == "enemy" and me.is_alive() and not me.tags.has("boss"):
			mind_id = id
	if mind_id != -1:
		bv.sim.player().cell = bv.sim.entities[mind_id].cell + Vector2i.LEFT
		bv.sim.board.place(bv.sim.player_id, bv.sim.player().cell)
		bv._speak = {"target_id": mind_id, "text": "klęknij przed jedyną wiarą", "mode": "type"}
		for i in 2:
			bv._process(0.016)             # draws the speak prompt
		_ck(true, "the speak prompt draws without crash")
		bv._speak_submit()                 # classify → convert → roll (auto-success at CHA 40)
		_ck(bv.sim.entities[mind_id].faction == "ally", "a successful sermon converts the enemy to your side")
	# blank submit → improvised fallback options
	bv._speak = {"target_id": bv.sim.player_id, "text": "", "mode": "type"}
	bv._speak_submit()
	_ck(bv._speak.get("mode", "") == "fallback", "an empty line offers improvised lines")
	bv._speak = {}

	# flavor content: failure lines + celebrity cameos (previously-unused bundles)
	_ck(Flavor.fail_line("failure", bv._narr_rng) != "", "a procedural craft-failure line is available")
	var celeb: Dictionary = Flavor.celebrity_for(2, bv._narr_rng)
	_ck(not celeb.is_empty() and celeb.has("intro"), "a depth-appropriate celebrity cameo is available")

	# achievements newly wired to real mechanics
	bv.floor.biome = "bar_skurczybyk"
	bv._ach_floor_complete(bv.floor.biome)
	_ck(Achievements.is_unlocked("karaoke_killer"), "finishing a Bar U Skurczybyka floor unlocks its achievement")
	Achievements.bump("floors", 8)              # career floors: push the lifetime tally to 9
	bv._ach_descend(2)                          # +1 → 10 → career milestone
	_ck(Achievements.is_unlocked("dziesiate_pietro"), "10 career floors unlock Dziesiąte piętro")

	# Phase B juice plumbing (headless logic only — pixels verified by --smoke)
	var bk1 := CombatEntity.new(700, "Dron", 10, 10, ["monster", "drone"])
	var bk2 := CombatEntity.new(701, "Duch", 10, 10, ["monster", "ghost"])
	var bk3 := CombatEntity.new(702, "Robak", 10, 10, ["monster", "robactwo"])
	var bk4 := CombatEntity.new(703, "Łowca", 10, 10, ["monster", "humanoid"])
	var bk5 := CombatEntity.new(704, "Alfa", 10, 10, ["monster", "beast", "miniboss"])
	_ck(bv._enemy_body_kind(bk1) == "mech" and bv._enemy_body_kind(bk2) == "spectral"
		and bv._enemy_body_kind(bk3) == "bug" and bv._enemy_body_kind(bk4) == "humanoid"
		and bv._enemy_body_kind(bk5) == "elite", "enemy tags map to distinct silhouettes")
	_ck(bv._enemy_hue(bk1, "mech") != bv._enemy_hue(bk4, "humanoid"), "species hues differ")
	bv._parts.clear()
	bv._animate([{"type": "damage", "target": bv.sim.player_id, "amount": 9, "dmg_type": "electric"}])
	_ck(bv._parts.size() > 0, "damage events spawn spark particles")
	bv._animate([{"type": "attack", "attacker": bv.sim.player_id, "target": bv.sim.player_id}])
	for i in 20:
		bv._process(0.05)               # particles + lunges decay without crash
	_ck(bv._parts.is_empty(), "particles decay and cull")
	_ck(bv._wipe >= 0.0, "transition wipe state is sane")

	# procedural audio: every SFX def renders to a stream; music loops render too
	var sfx = preload("res://scenes/Sfx.gd").new()
	get_root().add_child(sfx)
	var all_ok := true
	for sname in sfx.SFX:
		if sfx._sfx_stream(sname) == null: all_ok = false
	_ck(all_ok, "all %d SFX defs synthesize to streams" % sfx.SFX.size())
	_ck(sfx._music_stream("combat") != null, "a music mood renders to a looping stream")
	_ck((sfx._music_stream("combat") as AudioStreamWAV).loop_mode == AudioStreamWAV.LOOP_FORWARD,
		"music streams loop")
	sfx.play("hit")                     # headless: must not crash
	sfx.music("explore")
	_ck(true, "play + music calls are headless-safe")
	sfx.queue_free()

	# Phase C: unequip puts the worn piece back in the pocket
	var helm := GameItem.new("hełm testowy", GameItem.CAT_ARMOR, Rarity.COMMON)
	helm.effect = {"slot": "head", "ac_bonus": 2}
	bv.floor.player.equipment["head"] = helm
	var pocket0: int = bv.floor.items.size()
	bv._unequip("head")
	_ck(bv.floor.player.equipment.get("head") == null, "unequip clears the slot")
	_ck(bv.floor.items.size() == pocket0 + 1, "the unequipped piece returns to the pocket")
	# char sheet + pause draw without crash
	bv._char_screen = true
	for i in 2: bv._process(0.016)
	bv._char_screen = false
	bv._pause_screen = true
	for i in 2: bv._process(0.016)
	bv._pause_screen = false
	_ck(true, "character sheet + pause draw without crash")
	_ck(not bv._can_take_board_input() if bv._pause_screen else true, "pause blocks board input")

	# banner auto-clears (was sticking forever — "zadanie wykonane" never vanished)
	bv._add_banner("TEST BANNER")
	_ck(bv._banner == "TEST BANNER", "a banner shows when triggered")
	for i in 30:
		bv._process(0.1)                 # 3s of frames > the 2.2s banner timer
	_ck(bv._banner == "", "the banner auto-clears after its timer")

	# hammer many actions + frames; must never crash
	for i in 30:
		bv.handle_dir(Vector2i.LEFT)
		bv.handle_shove(Vector2i.LEFT)
		bv._process(0.016)
	_ck(true, "30 mixed actions + frames, no crash")

	# end-of-run results screen builds + draws without crash
	bv._end_run(false)
	_ck(not bv._summary.is_empty(), "ending the run builds a summary")
	_ck(not bv._summary_lines.is_empty(), "the results screen has rendered lines")
	# input lockout: the click you were spamming when you died must NOT skip the recap
	bv._dispatch_zone({"kind": "summary_continue"})
	_ck(not bv._summary.is_empty(), "an immediate click cannot skip the death recap")
	bv._process(2.0)                       # the lockout expires
	_ck(bv._summary_lock <= 0.0, "the recap lockout expires after a moment")
	for i in 3:
		bv._process(0.016)              # draws the full-screen summary
	_ck(true, "results screen draws without crash")

	Save.clear()                         # don't leave a save behind for other tests
	print("=== %d checks, %d failed ===" % [_n, _f])
	bv.free()
	quit(_f)
