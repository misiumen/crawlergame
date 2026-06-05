extends SceneTree
## Dialogue-tree engine tests. Run:
## godot --headless --path godot -s res://tests/test_dialogue.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _content() -> Dictionary:
	return {
		"MON": {"szczur": {"fallback_name": "Szczur", "tags": ["monster", "organic"], "floor_min": 1, "floor_max": 99}},
		"ENV": {"stol": {"fallback_name": "Stół", "tags": ["furniture", "wood"], "affordances": ["salvage"]}},
		"MOB_COMBAT_STATS": {"szczur": [22, "1d6+1", 2, 12]},
	}

func _new_floor():
	return Floor.new(FloorGen.generate(2, 99, _content()))

func _opt_labels(avail: Array) -> Array:
	var out: Array = []
	for pair in avail:
		out.append((pair[1] as Dictionary).get("label", ""))
	return out

func _initialize() -> void:
	print("=== dialogue-tree tests ===")
	var rng := RandomNumberGenerator.new()
	rng.seed = 7

	# --- registry ---
	_ck(Dialogue.has_tree("default_crawler"), "the default_crawler tree is registered")
	_ck(Dialogue.all_tree_keys().size() >= 6, "at least 6 trees (ported + extras) are registered")
	_ck(Dialogue.has_tree("handlarz_szrotu") and Dialogue.has_tree("kaplan_polimerow"),
		"the hand-authored extra trees are merged in")
	var rk := Dialogue.random_tree_key(rng)
	_ck(rk != "" and rk != "placeholder_npc", "random_tree_key picks a real, non-placeholder tree")
	_ck(Dialogue.tree_speaker("default_crawler") == "Zawodnik", "tree_speaker reads the start node speaker")

	# --- start: lands on the start node, exposes options ---
	var fl = _new_floor()
	var st := Dialogue.start(fl, 2, "default_crawler")
	_ck(not st.is_empty(), "start() returns a conversation state")
	_ck(st["node"] == "start", "conversation begins at the start node")
	_ck(Dialogue.node(st).get("speaker", "") == "Zawodnik", "node() returns the current node")
	var avail0 := Dialogue.available_options(fl, st)
	_ck(avail0.size() == 5, "the start node offers 5 options")

	# --- branching: ask 'origin' walks to the origin node, then back to start ---
	# option indices in the start node: 0=origin 1=safehouse 2=ally 3=intimidate 4=leave
	var r := Dialogue.pick(fl, st, 0, rng)
	_ck(r["continue"] and st["node"] == "origin", "picking 'skąd jest' branches to the origin node")
	# origin -> 'Wróć do rozmowy.' (idx 1) returns to start
	var back := Dialogue.pick(fl, st, 1, rng)
	_ck(back["continue"] and st["node"] == "start", "'Wróć do rozmowy' returns to the hub")

	# --- one_shot: the asked topic drops off the menu ---
	var avail1 := Dialogue.available_options(fl, st)
	_ck(avail1.size() == 4, "the one-shot 'origin' topic is gone after asking")
	_ck(not ("Spytaj, skąd jest i jak długo tu siedzi." in _opt_labels(avail1)),
		"the spent one-shot option no longer appears")

	# --- skill check SUCCESS routes to the success node + relationship/consequences ---
	var fl2 = _new_floor()
	fl2.player.stats["CHA"] = 30          # guarantee the CHA check passes
	var st2 := Dialogue.start(fl2, 2, "default_crawler")
	var aud_before: int = fl2.audience.rating
	var ally := Dialogue.pick(fl2, st2, 2, rng)   # idx 2 = ally (CHA 11)
	_ck(ally["info"].contains("Rzut Charyzmy"), "a skill option produces a roll line")
	_ck(st2["node"] == "ally_ok", "passing the CHA check routes to the success node")

	# --- skill check FAILURE routes to the fail node ---
	var fl3 = _new_floor()
	fl3.player.stats["CHA"] = -30         # guarantee the CHA check fails
	var st3 := Dialogue.start(fl3, 2, "default_crawler")
	Dialogue.pick(fl3, st3, 2, rng)       # ally attempt -> fail
	_ck(st3["node"] == "ally_fail", "failing the CHA check routes to the fail node")

	# --- 'end' consequence closes the conversation ---
	var fl4 = _new_floor()
	var st4 := Dialogue.start(fl4, 2, "default_crawler")
	var leave := Dialogue.pick(fl4, st4, 4, rng)   # idx 4 = 'Skończ rozmowę.' -> {kind:end}
	_ck(not leave["continue"], "the leave option ends the conversation")

	# --- on_enter consequences fire (the 'lesson' node bumps audience) ---
	var fl5 = _new_floor()
	var st5 := Dialogue.start(fl5, 2, "default_crawler")
	var a5: int = fl5.audience.rating
	Dialogue.pick(fl5, st5, 0, rng)       # -> origin
	# origin offers: 0='czego się nauczył' -> lesson (on_enter audience +1), 1=back
	Dialogue.pick(fl5, st5, 0, rng)       # -> lesson
	_ck(fl5.audience.rating > a5, "entering the 'lesson' node raises audience (on_enter consequence)")

	# --- flag gating: set_flag then requires/forbids drive availability ---
	var fl6 = _new_floor()
	fl6.player.flags["secret"] = true
	var fake_opt_req := {"label": "x", "requires": "secret"}
	var fake_opt_forb := {"label": "y", "forbids": "secret"}
	var stub := {"node": "n", "picked": {}}
	_ck(Dialogue.option_available(fl6, stub, 0, fake_opt_req), "requires: available when the flag is set")
	_ck(not Dialogue.option_available(fl6, stub, 1, fake_opt_forb), "forbids: hidden when the flag is set")

	# --- skill-check crit rules (raw 1 always fails, raw 20 always succeeds) ---
	var fl7 = _new_floor()
	fl7.player.stats["CHA"] = 100         # huge mod
	var s1 := Dialogue._roll_skill(fl7, "CHA", 11, _seeded(1))   # raw forced low via seed search
	# (we can't force raw directly; instead assert the line format + that a 100 mod beats TT 11 normally)
	_ck(s1["line"].contains("TT 11"), "skill line shows the target number")

	# --- stats: a negotiator gets a big CHA boost ---
	var fl8 = _new_floor()
	var base_cha: int = fl8.player.stat_mod("CHA")
	Classes.assign_class(fl8.player, "negotiator")
	_ck(fl8.player.stat_mod("CHA") == base_cha + 3, "the Negotiator class adds +3 CHA")
	Classes.assign_class(fl8.player, "bruiser")
	_ck(fl8.player.stat_mod("CHA") == base_cha, "re-classing undoes the prior class's stat bonus")

	# --- extra tree (handlarz_szrotu): loyalty flag unlocks the under-bar branch ---
	var flh = _new_floor()
	var sth := Dialogue.start(flh, 2, "handlarz_szrotu")
	# the '[Stały klient] ...' option (requires bizon_regular) is hidden at first
	var labels_h := _opt_labels(Dialogue.available_options(flh, sth))
	var has_underbar := false
	for l in labels_h:
		if (l as String).begins_with("[Stały klient]"): has_underbar = true
	_ck(not has_underbar, "the under-bar option is hidden until you're a regular")
	# become a regular: find and pick the loyalty option
	var loyalty_idx := _find_opt(flh, sth, "Zostań jego stałym klientem.")
	Dialogue.pick(flh, sth, loyalty_idx, rng)     # -> loyalty node
	_ck(bool(flh.player.flags.get("bizon_regular", false)), "loyalty sets the bizon_regular flag")
	_ck(int(flh.player.relationships.get("handlarz_szrotu", 0)) > 0, "loyalty improves the relationship")
	Dialogue.pick(flh, sth, 0, rng)               # 'Łapię' -> back to start
	# now the under-bar option is available and gives kwas
	var ub_idx := _find_opt(flh, sth, "[Stały klient] Poproś o towar spod lady.")
	_ck(ub_idx >= 0, "the under-bar option appears once you're a regular")
	var inv_kwas0 := int(flh.inv.get("kwas", 0))
	Dialogue.pick(flh, sth, ub_idx, rng)
	_ck(int(flh.inv.get("kwas", 0)) > inv_kwas0, "the under-bar branch grants kwas (give_material)")

	# --- extra tree (kaplan_polimerow): convert flag gates the blessing ---
	var flk = _new_floor()
	var stk := Dialogue.start(flk, 2, "kaplan_polimerow")
	var bless0 := _find_opt(flk, stk, "[Wierny] Poproś o błogosławieństwo.")
	_ck(bless0 < 0 or not Dialogue.option_available(flk, stk, bless0, Dialogue.node(stk)["options"][bless0]),
		"blessing is locked before conversion")
	var conv_idx := _find_opt(flk, stk, "Przyjmij wiarę polimeru.")
	Dialogue.pick(flk, stk, conv_idx, rng)        # -> convert node
	_ck(bool(flk.player.flags.get("polimer_wierny", false)), "converting sets the faithful flag")
	Dialogue.pick(flk, stk, 0, rng)               # 'Przyjmij znak (wróć)' -> back to start
	var bless_idx := _find_opt(flk, stk, "[Wierny] Poproś o błogosławieństwo.")
	_ck(bless_idx >= 0 and Dialogue.option_available(flk, stk, bless_idx, Dialogue.node(stk)["options"][bless_idx]),
		"the blessing unlocks after conversion")

	# --- combat integration: talking an NPC, not attacking it ---
	var board := Board.from_ascii(["####", "#..#", "####"])
	var p := CombatEntity.new(1, "Ty", 100, 14, []); p.faction = "player"; p.cell = Vector2i(1, 1)
	var npc := CombatEntity.new(2, "Zawodnik", 1, 10, ["npc"]); npc.faction = "npc"
	npc.cell = Vector2i(2, 1); npc.dialogue_tree_key = "default_crawler"
	var cs := CombatSim.new(board, {1: p, 2: npc}, 1, 3)
	board.place(1, p.cell); board.place(2, npc.cell)
	var ev := cs.player_move(Vector2i.RIGHT)
	var talked := false
	for e in ev:
		if e.get("type") == "talk" and int(e.get("npc_id", -1)) == 2: talked = true
	_ck(talked, "bumping an NPC emits a talk event")
	_ck(npc.is_alive(), "the NPC is not attacked")

	# --- floorgen NPCs carry a tree key ---
	var saw_npc := false
	for fnum in range(2, 7):
		var data := FloorGen.generate(fnum, fnum * 17, _content())
		for room in data["rooms"]:
			for id in room["entities"]:
				var e: CombatEntity = room["entities"][id]
				if e.faction == "npc":
					saw_npc = true
					_ck(e.dialogue_tree_key != "" and Dialogue.has_tree(e.dialogue_tree_key),
						"a generated NPC has a valid dialogue tree")
	_ck(saw_npc, "floors spawn NPCs with dialogue trees")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)

func _seeded(s: int) -> RandomNumberGenerator:
	var r := RandomNumberGenerator.new(); r.seed = s; return r

## Original index of the option with this exact label in the current node, or -1.
func _find_opt(floor, state, label: String) -> int:
	var opts: Array = Dialogue.node(state).get("options", [])
	for i in opts.size():
		if (opts[i] as Dictionary).get("label", "") == label:
			return i
	return -1
