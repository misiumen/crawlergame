extends SceneTree
## NPC dialogue tests. Run:
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

func _initialize() -> void:
	print("=== dialogue tests ===")
	var rng := RandomNumberGenerator.new()
	rng.seed = 2

	# --- pool shape ---
	var d := Dialogue.random_npc(rng)
	_ck(d.has("speaker") and d.has("text") and d.has("options"), "a random NPC has speaker/text/options")
	_ck((d["options"] as Array).size() >= 2, "an NPC offers at least two options")

	# A floor to apply effects against.
	var floor = Floor.new(FloorGen.generate(2, 99, _content()))
	floor.inv = {"złom": 3}

	# --- the trader: spending option gated by materials ---
	var trader := {
		"speaker": "Handlarz",
		"text": "...",
		"options": [
			{"label": "Wymień 2 złom na przewód.", "material": "złom", "mat_qty": -2,
				"requires_mat": true, "give_material": "przewód", "give_qty": 1, "reply": "Masz."},
			{"label": "Pochwal towar.", "audience": 2, "sponsor_tag": "social", "reply": "Dzięki."},
		],
	}
	_ck(Dialogue.option_available(floor, trader, 0), "trade is available with 3 złom in pocket")
	var aud0: int = floor.audience.rating
	var res := Dialogue.choose(floor, trader, 0)
	_ck(int(floor.inv.get("złom", 0)) == 1, "the trade spent 2 złom (3 -> 1)")
	_ck(int(floor.inv.get("przewód", 0)) == 1, "the trade granted 1 przewód")
	_ck(res["reply"] == "Masz.", "choose returns the NPC reply")

	# now too poor to trade again
	floor.inv = {"złom": 1}
	_ck(not Dialogue.option_available(floor, trader, 0), "trade is gated when you can't pay")

	# --- audience + sponsor option ---
	var res2 := Dialogue.choose(floor, trader, 1)
	_ck(floor.audience.rating == aud0 + 2, "the praise option raised audience by 2")
	_ck(not res2.get("events", []).is_empty() or res2["reply"] != "", "praise resolves with a reply")

	# --- a give-only option adds a material ---
	var fan := {
		"speaker": "Widz",
		"text": "...",
		"options": [{"label": "Sprzedaj sławę.", "give_material": "złom", "give_qty": 1,
			"audience": 1, "reply": "Płaci."}],
	}
	floor.inv = {}
	Dialogue.choose(floor, fan, 0)
	_ck(int(floor.inv.get("złom", 0)) == 1, "a give-material option adds the material")

	# --- combat integration: bumping an NPC talks, doesn't attack ---
	var board := Board.from_ascii(["####", "#..#", "####"])
	var p := CombatEntity.new(1, "Ty", 100, 14, []); p.faction = "player"; p.cell = Vector2i(1, 1)
	var npc := CombatEntity.new(2, "Widz", 1, 10, ["npc"]); npc.faction = "npc"
	npc.cell = Vector2i(2, 1); npc.dialogue = Dialogue.random_npc(rng)
	var cs := CombatSim.new(board, {1: p, 2: npc}, 1, 3)
	board.place(1, p.cell); board.place(2, npc.cell)
	var ev := cs.player_move(Vector2i.RIGHT)
	var talked := false
	for e in ev:
		if e.get("type") == "talk" and int(e.get("npc_id", -1)) == 2:
			talked = true
	_ck(talked, "bumping an NPC emits a talk event")
	_ck(npc.is_alive() and npc.hp == 1, "the NPC is not attacked")
	_ck(p.cell == Vector2i(1, 1), "the player does not move into the NPC")
	# an NPC does not count as an enemy (won't block the room-clear logic)
	_ck(cs.enemies_alive().is_empty(), "NPCs are not enemies")

	# --- floorgen places talkable NPCs on deeper floors ---
	var saw_npc := false
	for fnum in range(2, 7):
		var data := FloorGen.generate(fnum, fnum * 31, _content())
		for room in data["rooms"]:
			for id in room["entities"]:
				var e: CombatEntity = room["entities"][id]
				if e.faction == "npc":
					saw_npc = true
					_ck(not e.dialogue.is_empty(), "a generated NPC carries a dialogue")
	_ck(saw_npc, "floors spawn NPCs to talk to")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
