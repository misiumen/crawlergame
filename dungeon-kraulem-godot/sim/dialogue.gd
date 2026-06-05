class_name Dialogue
extends RefCounted
## Full dialogue-tree engine — port of engine/dialogue.py. NPCs speak a line, the
## player picks an option, we walk to the next node. Options can carry a skill
## check (d20 + player.stat_mod vs DC, crit on 20 / crit-fail on 1), flag gates
## (requires/forbids), one-shot (drops off the menu once taken), and consequences
## (audience / sponsor / set_flag / give / log / relationship / threat / end).
##
## Trees are authored in DialogueTrees (generated from the Python content). The
## conversation STATE is a small Dictionary the presentation holds across picks.

const STAT_PL := {
	"CHA": "Charyzmy", "INT": "Sprytu", "WIS": "Roztropności",
	"DEX": "Zręczności", "STR": "Siły",
}
const LEVEL_PL := {
	"critical_success": "Krytyczny sukces!", "success": "Sukces.",
	"failure": "Porażka.", "critical_failure": "Krytyczna porażka!",
}

# ── Registry (ported trees + hand-authored extras, merged once) ───────────────

static var _registry: Dictionary = {}

static func _trees() -> Dictionary:
	if _registry.is_empty():
		for k in DialogueTrees.TREES:
			_registry[k] = DialogueTrees.TREES[k]
		for k in DialogueTreesExtra.EXTRA:
			_registry[k] = DialogueTreesExtra.EXTRA[k]
	return _registry

static func tree(tree_key: String) -> Dictionary:
	return _trees().get(tree_key, {})

static func has_tree(tree_key: String) -> bool:
	return _trees().has(tree_key)

static func all_tree_keys() -> Array:
	return _trees().keys()

## A tree key for a random spawned NPC (excludes the boss-flavored ones).
static func random_tree_key(rng: RandomNumberGenerator) -> String:
	var pool: Array = []
	for k in _trees():
		if k == "placeholder_npc" or k == "intake_warden":
			continue
		pool.append(k)
	if pool.is_empty():
		pool = _trees().keys()
	return pool[rng.randi_range(0, pool.size() - 1)] if not pool.is_empty() else ""

## The speaker name a tree opens with (for the NPC's board label).
static func tree_speaker(tree_key: String) -> String:
	var t := tree(tree_key)
	var nodes: Dictionary = t.get("nodes", {})
	var start: String = t.get("start", "")
	return nodes.get(start, {}).get("speaker", "Ktoś") if nodes.has(start) else "Ktoś"

# ── Flow ──────────────────────────────────────────────────────────────────────

## Begin a conversation. Returns a state dict (empty if the tree is missing).
## `floor` supplies player.flags / audience / sponsors for consequences.
static func start(floor, npc_id: int, tree_key: String) -> Dictionary:
	var t := tree(tree_key)
	if t.is_empty():
		return {}
	var start_node: String = t.get("start", "")
	var nodes: Dictionary = t.get("nodes", {})
	if not nodes.has(start_node):
		return {}
	var state := {
		"npc_id": npc_id, "tree_key": tree_key, "node": start_node,
		"visited": {start_node: true}, "picked": {},
		"events": [],
	}
	var enter := _apply_cons(floor, state, (nodes[start_node] as Dictionary).get("on_enter", []))
	state["events"] = enter["events"]
	return state

static func node(state: Dictionary) -> Dictionary:
	var t := tree(state.get("tree_key", ""))
	return (t.get("nodes", {}) as Dictionary).get(state.get("node", ""), {})

## Options currently available, [[orig_idx, opt_dict], ...] (gates applied).
static func available_options(floor, state: Dictionary) -> Array:
	var opts: Array = node(state).get("options", [])
	var out: Array = []
	for i in opts.size():
		if option_available(floor, state, i, opts[i]):
			out.append([i, opts[i]])
	return out

static func option_available(floor, state: Dictionary, idx: int, opt: Dictionary) -> bool:
	if opt.get("one_shot", false) and state["picked"].has("%s:%d" % [state["node"], idx]):
		return false
	var req: String = opt.get("requires", "")
	if req != "" and not bool(floor.player.flags.get(req, false)):
		return false
	var forb: String = opt.get("forbids", "")
	if forb != "" and bool(floor.player.flags.get(forb, false)):
		return false
	return true

## Pick option `idx` (the ORIGINAL index in the node). Returns
## {continue: bool, info: String (skill-check line), events: Array}.
static func pick(floor, state: Dictionary, idx: int, rng: RandomNumberGenerator) -> Dictionary:
	var opts: Array = node(state).get("options", [])
	if idx < 0 or idx >= opts.size():
		return {"continue": false, "info": "", "events": []}
	var opt: Dictionary = opts[idx]
	if not option_available(floor, state, idx, opt):
		return {"continue": true, "info": "Ta opcja nie jest teraz dostępna.", "events": []}
	state["picked"]["%s:%d" % [state["node"], idx]] = true

	var success := true
	var info := ""
	if opt.has("skill"):
		var sk: Array = opt["skill"]
		var res := _roll_skill(floor, sk[0], int(sk[1]), rng)
		success = res["success"]
		info = res["line"]

	var fail_cons: Array = opt.get("fail_cons", [])
	var cons: Array = opt.get("cons", []) if success else (fail_cons if not fail_cons.is_empty() else opt.get("cons", []))
	var applied := _apply_cons(floor, state, cons)
	var events: Array = applied["events"]
	if not applied["keep_going"]:
		return {"continue": false, "info": info, "events": events}

	var next_id: String = ""
	if success:
		next_id = opt.get("next", "")
	else:
		next_id = opt.get("fail", "")
		if next_id == "":
			next_id = opt.get("next", "")
	if next_id == "":
		return {"continue": false, "info": info, "events": events}
	var nodes: Dictionary = tree(state["tree_key"]).get("nodes", {})
	if not nodes.has(next_id):
		return {"continue": false, "info": info, "events": events}
	state["node"] = next_id
	state["visited"][next_id] = true
	var enter := _apply_cons(floor, state, (nodes[next_id] as Dictionary).get("on_enter", []))
	events.append_array(enter["events"])
	return {"continue": true, "info": info, "events": events}

# ── Skill check ───────────────────────────────────────────────────────────────

static func _roll_skill(floor, stat: String, dc: int, rng: RandomNumberGenerator) -> Dictionary:
	var raw := rng.randi_range(1, 20)
	var mod: int = floor.player.stat_mod(stat)
	var total := raw + mod
	var success := raw != 1 and (raw == 20 or total >= dc)
	var level := "success" if success else "failure"
	if raw == 20: level = "critical_success"
	elif raw == 1: level = "critical_failure"
	var line := "Rzut %s: [%d] %+d = %d (TT %d). %s" % [
		STAT_PL.get(stat, stat), raw, mod, total, dc, LEVEL_PL.get(level, "")]
	return {"success": success, "raw": raw, "total": total, "level": level, "line": line}

# ── Consequence dispatch ──────────────────────────────────────────────────────

static func _apply_cons(floor, state: Dictionary, cons_list: Array) -> Dictionary:
	var events: Array = []
	var keep := true
	for c in cons_list:
		match c.get("kind"):
			"audience":
				if floor.audience != null:
					floor.audience.change(int(c.get("amount", 0)), "dialogue")
				events.append({"type": "dialogue_audience", "delta": int(c.get("amount", 0))})
			"sponsor":
				if floor.sponsors != null:
					var k: String = c.get("key", "")
					var amt: int = int(c.get("amount", 0))
					floor.sponsors.attention[k] = clampi(
						int(floor.sponsors.attention.get(k, 0)) + amt, -20, 20)
					events.append({"type": "dialogue_sponsor", "key": k, "delta": amt})
			"set_flag":
				floor.player.flags[c.get("flag", "")] = c.get("value", true)
			"clear_flag":
				floor.player.flags.erase(c.get("flag", ""))
			"give_item":
				var ik: String = c.get("item_key", "")
				floor.inv[ik] = int(floor.inv.get(ik, 0)) + 1
				events.append({"type": "dialogue_give", "item": ik, "log": c.get("log", "")})
			"give_material":
				var mk: String = c.get("material", "")
				var q: int = int(c.get("qty", 1))
				floor.inv[mk] = int(floor.inv.get(mk, 0)) + q
				events.append({"type": "dialogue_material", "material": mk, "qty": q})
			"log":
				events.append({"type": "dialogue_log", "text": c.get("text", ""),
					"severity": c.get("severity", "normal")})
			"relationship":
				var tk: String = state.get("tree_key", "")
				floor.player.relationships[tk] = int(floor.player.relationships.get(tk, 0)) + int(c.get("amount", 0))
				events.append({"type": "dialogue_relationship", "tree": tk, "delta": int(c.get("amount", 0))})
			"threat":
				if int(c.get("amount", 0)) > 0 and floor.sim != null:
					for e in floor.sim.enemies_alive():
						e.aware = true
				events.append({"type": "dialogue_threat", "amount": int(c.get("amount", 0))})
			"end":
				keep = false
	return {"keep_going": keep, "events": events}
