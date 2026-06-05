extends SceneTree
## Unit tests for the procedural breakable body (sim/body.gd) + combat integration.
## Run: godot --headless --path godot -s res://tests/test_body.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _has_event(evs: Array, type: String, key := "", val = null) -> bool:
	for e in evs:
		if e.get("type") == type and (key == "" or e.get(key) == val):
			return true
	return false

# A minimal quadruped plan (mirrors data/body_plans small_quadruped shape).
func _quad_plan() -> Dictionary:
	return {
		"head":  {"label_pl": "łeb", "hp_frac": 0.35, "to_hit_mod": -3, "damage_mul": 1.6,
				  "maim_status": "stunned", "display_order": 0,
				  "butcher_intact_bonus": [["tooth", 1]], "butcher_broken_bonus": [["bone_fragments", 1]]},
		"torso": {"label_pl": "tułów", "hp_frac": 0.7, "to_hit_mod": 0, "damage_mul": 1.0,
				  "maim_status": null, "display_order": 1,
				  "butcher_intact_bonus": [], "butcher_broken_bonus": [["meat_chunk", 1]]},
		"l_leg": {"label_pl": "lewa łapa", "hp_frac": 0.2, "to_hit_mod": -1, "damage_mul": 0.8,
				  "maim_status": "slowed", "display_order": 2,
				  "butcher_intact_bonus": [["claw", 1]], "butcher_broken_bonus": [["sinew", 1]]},
		"r_leg": {"label_pl": "prawa łapa", "hp_frac": 0.2, "to_hit_mod": -1, "damage_mul": 0.8,
				  "maim_status": "slowed", "display_order": 3,
				  "butcher_intact_bonus": [["claw", 1]], "butcher_broken_bonus": [["sinew", 1]]},
	}

func _initialize() -> void:
	print("=== body tests ===")
	var rng := RandomNumberGenerator.new()
	rng.seed = 7

	# --- construction: parts scale to total HP, ordered by display_order ---
	var body := BodyState.new("small_quadruped", _quad_plan(), 20)
	_ck(body.parts.size() == 4, "body builds 4 parts")
	_ck(body.order == ["head", "torso", "l_leg", "r_leg"], "parts ordered by display_order")
	_ck(int(body.part("torso")["max_hp"]) == 14, "torso max_hp = 0.7 * 20 = 14")
	_ck(int(body.part("head")["max_hp"]) == 7, "head max_hp = 0.35 * 20 = 7")
	_ck(body.severity_of("torso") == BodyState.SEV_INTACT, "fresh part is intact")

	# --- located hit: severity tiers ---
	var b2 := BodyState.new("q", _quad_plan(), 20)   # torso 14
	var h1 := b2.apply_hit("torso", 3, "physical", true, false)
	_ck(h1["severity"] == BodyState.SEV_DAMAGED, "11/14 hp -> damaged")
	_ck(h1["wound"] == BodyState.W_BLEED, "physical on a bleeder -> bleed wound")
	var h2 := b2.apply_hit("torso", 6, "physical", true, false)   # 14-3-6 = 5 / 14 = 0.36
	_ck(h2["severity"] == BodyState.SEV_CRIPPLED, "<=50% hp -> crippled")
	_ck(not h2["newly_broken"], "crippled is not yet broken")

	# --- wound typing by damage element ---
	var b3 := BodyState.new("q", _quad_plan(), 40)
	_ck(b3.apply_hit("torso", 1, "fire", true, false)["wound"] == BodyState.W_BURN, "fire -> burn")
	_ck(b3.apply_hit("torso", 1, "electric", true, false)["wound"] == BodyState.W_SHOCK, "electric -> shock")
	_ck(b3.apply_hit("torso", 1, "acid", true, false)["wound"] == BodyState.W_CORRODE, "acid -> corrode")
	_ck(b3.apply_hit("torso", 1, "cold", true, false)["wound"] == BodyState.W_FREEZE, "cold -> freeze")
	_ck(b3.apply_hit("torso", 1, "physical", false, false)["wound"] == "", "physical on non-bleeder -> no wound")

	# --- maim: breaking the head triggers its maim_status ---
	var b4 := BodyState.new("q", _quad_plan(), 20)   # head 7
	var hk := b4.apply_hit("head", 99, "physical", true, false)
	_ck(hk["newly_broken"], "head reduced to 0 is newly broken")
	_ck(hk["maim_status"] == "stunned", "broken head -> stunned maim")
	_ck(b4.severity_of("head") == BodyState.SEV_BROKEN, "head severity = broken")
	_ck("stunned" in b4.active_maims(), "active_maims includes stunned")

	# --- sever: a heavy blow that breaks a non-vital limb amputates it ---
	var b5 := BodyState.new("q", _quad_plan(), 20)
	var hs := b5.apply_hit("l_leg", 99, "physical", true, true)   # heavy
	_ck(hs["severed"], "heavy break of a limb severs it")
	_ck(b5.part("l_leg")["severed"], "severed flag set on the part")
	_ck(BodyState.W_SEVER in b5.part("l_leg")["wounds"], "severed part carries a sever wound")
	# a vital part never severs (that's just death)
	var b6 := BodyState.new("q", _quad_plan(), 20)
	var hv := b6.apply_hit("torso", 99, "physical", true, true)
	_ck(not hv["severed"], "vital torso is never severed")

	# --- mobility: one broken leg hobbles; both broken stops movement ---
	var b7 := BodyState.new("q", _quad_plan(), 20)
	_ck(b7.can_move() and not b7.is_hobbled(), "intact body moves freely")
	b7.apply_hit("l_leg", 99, "physical", true, false)
	_ck(b7.is_hobbled(), "one broken leg -> hobbled")
	_ck(b7.can_move(), "one broken leg still has the other -> can move")
	b7.apply_hit("r_leg", 99, "physical", true, false)
	_ck(not b7.can_move(), "both legs broken -> cannot move")

	# --- zone pick respects severed parts + aim ---
	var b8 := BodyState.new("q", _quad_plan(), 20)
	b8.apply_hit("l_leg", 99, "physical", true, true)   # sever it
	var seen_severed := false
	for i in 200:
		if b8.pick_zone(rng, "") == "l_leg":
			seen_severed = true
	_ck(not seen_severed, "pick_zone never returns a severed part")
	_ck(b8.pick_zone(rng, "head") == "head", "aimed zone is honored")
	_ck(b8.pick_zone(rng, "l_leg") != "l_leg", "aim at a severed part falls back to weighting")

	# --- butcher yields shift intact -> broken ---
	var b9 := BodyState.new("q", _quad_plan(), 20)
	var y_intact := b9.butcher_yields()
	_ck(int(y_intact.get("tooth", 0)) == 1, "intact head yields a tooth")
	b9.apply_hit("head", 99, "physical", true, false)
	var y_broken := b9.butcher_yields()
	_ck(int(y_broken.get("bone_fragments", 0)) == 1, "broken head yields bone fragments")
	_ck(int(y_broken.get("tooth", 0)) == 0, "broken head no longer yields a tooth")

	# --- plan resolution from tags / monster key ---
	var bundle := {
		"PLANS": {"small_quadruped": _quad_plan(), "humanoid": {"torso": {"hp_frac": 1.0}}},
		"PLANS_BY_MONSTER_KEY": {"tunnel_runt": "small_quadruped"},
		"PLAN_BY_TAG": [["humanoid", "humanoid"], ["small", "small_quadruped"]],
	}
	_ck(BodyState.plan_key_for([], "tunnel_runt", bundle) == "small_quadruped",
		"monster key resolves its plan first")
	_ck(BodyState.plan_key_for(["humanoid"], "", bundle) == "humanoid",
		"tag resolves a plan when no monster key")
	var resolved := BodyState.from_bundle(["small"], "", 20, bundle)
	_ck(resolved != null and resolved.plan_key == "small_quadruped", "from_bundle builds by tag")

	# --- combat integration: a located player hit emits body_hit + records wounds ---
	var board := Board.from_ascii(["####", "#..#", "####"])
	var pc := CombatEntity.new(1, "Ty", 100, 14, []); pc.faction = "player"; pc.cell = Vector2i(1, 1)
	var rc := CombatEntity.new(2, "Szczur", 60, 1, ["organic", "quadruped"])
	rc.faction = "enemy"; rc.cell = Vector2i(2, 1); rc.aware = true     # ac 1 = always hit
	rc.body = BodyState.new("small_quadruped", _quad_plan(), 60)
	var cs := CombatSim.new(board, {1: pc, 2: rc}, 1, 5); board.place(1, pc.cell); board.place(2, rc.cell)
	var ev := cs.player_move(Vector2i.RIGHT)
	_ck(_has_event(ev, "body_hit"), "a located hit on a bodied enemy emits body_hit")
	var any_wounded := false
	for pkey in rc.body.order:
		if rc.body.part(pkey)["severity"] != BodyState.SEV_INTACT:
			any_wounded = true
	_ck(any_wounded, "the enemy body actually records a wounded part")

	# --- aimed attack: aim_zone is consumed after the swing ---
	var board2 := Board.from_ascii(["####", "#..#", "####"])
	var pc2 := CombatEntity.new(1, "Ty", 100, 14, []); pc2.faction = "player"; pc2.cell = Vector2i(1, 1)
	var rc2 := CombatEntity.new(2, "Szczur", 200, 1, ["organic", "quadruped"])
	rc2.faction = "enemy"; rc2.cell = Vector2i(2, 1); rc2.aware = true
	rc2.body = BodyState.new("q", _quad_plan(), 200)
	var cs2 := CombatSim.new(board2, {1: pc2, 2: rc2}, 1, 9)
	board2.place(1, pc2.cell); board2.place(2, rc2.cell)
	cs2.aim_zone = "head"
	cs2.player_move(Vector2i.RIGHT)
	_ck(cs2.aim_zone == "", "aim_zone is spent after one attack")
	_ck(rc2.body.severity_of("head") != BodyState.SEV_INTACT, "aimed hit landed on the head")

	# --- crippled enemy cannot chase ---
	var board3 := Board.from_ascii(["######", "#....#", "######"])
	var pc3 := CombatEntity.new(1, "Ty", 100, 14, []); pc3.faction = "player"; pc3.cell = Vector2i(1, 1)
	var rc3 := CombatEntity.new(2, "Szczur", 50, 10, ["organic", "quadruped"])
	rc3.faction = "enemy"; rc3.cell = Vector2i(4, 1); rc3.aware = true
	rc3.body = BodyState.new("q", _quad_plan(), 50)
	rc3.body.apply_hit("l_leg", 99, "physical", true, false)
	rc3.body.apply_hit("r_leg", 99, "physical", true, false)   # both legs gone
	var cs3 := CombatSim.new(board3, {1: pc3, 2: rc3}, 1, 3)
	board3.place(1, pc3.cell); board3.place(2, rc3.cell)
	var before := rc3.cell
	cs3.player_wait()
	_ck(rc3.cell == before, "a legless enemy cannot close the distance")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
