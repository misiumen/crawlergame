extends SceneTree
## Emergent-classes tests: affinity tracking, offer thresholds, scoring,
## passives, and the per-floor active abilities. Run:
## godot --headless --path godot -s res://tests/test_classes.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _has_event(evs: Array, type: String) -> bool:
	for e in evs:
		if e.get("type") == type:
			return true
	return false

func _make_player(hp := 100, ac := 14) -> CombatEntity:
	var p := CombatEntity.new(1, "Ty", hp, ac, [])
	p.faction = "player"
	return p

func _initialize() -> void:
	print("=== classes tests ===")
	var rng := RandomNumberGenerator.new()
	rng.seed = 5

	# --- affinity scoring + suggestion ---
	var p := _make_player()
	p.affinity = {"melee": 9, "survival": 3, "tech": 1}
	_ck(Classes.class_score(p, "bruiser", rng) > Classes.class_score(p, "medic", rng),
		"a melee build scores bruiser over medic")
	var top3 := Classes.suggest_classes(p, 3, rng)
	_ck(top3.size() == 3, "suggest_classes returns 3 candidates")
	_ck("bruiser" in top3, "melee build's top suggestions include bruiser")
	# deterministic best-fit (no wildcard): same player -> same ranking, top is bruiser
	_ck(Classes.suggest_classes(p, 3, rng)[0] == "bruiser", "top suggestion is the best fit, every time")
	# legibility helpers
	_ck(Classes.style_summary(p, 2).begins_with("walka wręcz 9"), "style_summary leads with your top affinity")
	_ck(Classes.fit_reason(p, "bruiser").contains("walka wręcz 9"), "fit_reason explains why a class fits")

	# --- offer thresholds ---
	var q := _make_player()
	q.affinity = {"melee": 2, "tech": 1}
	_ck(not Classes.should_offer(q, 1, 20), "weak/spread affinity does not trigger an offer")
	q.affinity = {"melee": 9, "tech": 1}
	_ck(Classes.should_offer(q, 1, 10), "dominant melee (9 vs 1, total 10) past turn 8 triggers an offer")
	# A heavily-invested run with a lead (not 2x) still offers — but only past the
	# turn gate, and only when there's a genuine TOP style.
	var r := _make_player()
	r.affinity = {"melee": 7, "tech": 5, "survival": 5}   # total 17, melee leads
	_ck(not Classes.should_offer(r, 1, 4), "no offer before the turn gate even at high total")
	_ck(Classes.should_offer(r, 1, 10), "high total + a clear lead offers past the turn gate")
	var rg := _make_player()
	rg.affinity = {"melee": 5, "tech": 5, "survival": 4}  # tied top — no real style
	_ck(not Classes.should_offer(rg, 1, 12), "a tied generalist with no top style is NOT offered")
	var s := _make_player()
	s.class_key = "bruiser"
	s.affinity = {"melee": 30}
	_ck(not Classes.should_offer(s, 1, 20), "a player who already has a class is never offered")

	# --- assignment applies the hp_max passive ---
	var a := _make_player(100, 14)
	_ck(Classes.assign_class(a, "bruiser"), "assign_class succeeds for a real class")
	_ck(a.class_key == "bruiser", "class_key set")
	_ck(a.max_hp == 120 and a.hp == 120, "bruiser passive adds +20 max HP")
	# re-assignment undoes the prior bump
	Classes.assign_class(a, "survivor")
	_ck(a.max_hp == 110, "re-classing to survivor (+10) undoes bruiser's +20 first")
	_ck(not Classes.assign_class(a, "nonexistent"), "assigning an unknown class fails")

	# --- passive lookups ---
	_ck(ClassFeatures.passive_bonus_for("bruiser", "unarmed_dmg") == 2, "bruiser unarmed_dmg passive = 2")
	var sh := _make_player(); Classes.assign_class(sh, "showman")
	_ck(abs(ClassFeatures.audience_multiplier(sh) - 2.0) < 0.001, "showman doubles audience (x2)")
	var md := _make_player(); Classes.assign_class(md, "medic")
	_ck(abs(ClassFeatures.heal_multiplier(md) - 2.0) < 0.001, "medic doubles healing (x2)")

	# --- combat wiring: actions bump affinity ---
	var board := Board.from_ascii(["#####", "#...#", "#####"])
	var pc := _make_player(100, 14); pc.cell = Vector2i(1, 1)
	var rc := CombatEntity.new(2, "Szczur", 200, 1, ["organic"])
	rc.faction = "enemy"; rc.cell = Vector2i(2, 1); rc.aware = true
	var cs := CombatSim.new(board, {1: pc, 2: rc}, 1, 7)
	board.place(1, pc.cell); board.place(2, rc.cell)
	cs.player_move(Vector2i.RIGHT)   # bump-attack
	_ck(int(pc.affinity.get("melee", 0)) >= 1, "attacking bumps melee affinity")

	# salvage bumps tech
	var b2 := Board.from_ascii(["#####", "#...#", "#####"])
	var pc2 := _make_player(100, 14); pc2.cell = Vector2i(1, 1)
	var obj := CombatEntity.new(3, "Stół", 6, 5, ["furniture", "wood", "salvageable"])
	obj.faction = "object"; obj.affordances = ["salvage"]; obj.cell = Vector2i(2, 1)
	var cs2 := CombatSim.new(b2, {1: pc2, 3: obj}, 1, 2)
	b2.place(1, pc2.cell); b2.place(3, obj.cell)
	cs2.player_interact()
	_ck(int(pc2.affinity.get("tech", 0)) >= 1, "salvage bumps tech affinity")
	_ck(int(pc2.affinity.get("environment", 0)) >= 1, "salvaging furniture bumps environment too")

	# --- bruiser active doubles the next hit ---
	var bb := Board.from_ascii(["#####", "#...#", "#####"])
	var pb := _make_player(100, 14); pb.cell = Vector2i(1, 1)
	Classes.assign_class(pb, "bruiser")
	var eb := CombatEntity.new(2, "Wróg", 500, 1, ["organic"])
	eb.faction = "enemy"; eb.cell = Vector2i(3, 1); eb.aware = true   # not adjacent, won't counter
	var csb := CombatSim.new(bb, {1: pb, 2: eb}, 1, 3)
	bb.place(1, pb.cell); bb.place(2, eb.cell)
	var act := csb.use_class_active(0)
	_ck(_has_event(act, "class_active"), "use_class_active emits a class_active event")
	_ck(pb.next_attack_mult == 2, "bruiser charge sets next_attack_mult = 2")
	# cooldown: second use on same floor blocked
	var act2 := csb.use_class_active(0)
	_ck(_has_event(act2, "class_active_blocked"), "active is once-per-floor (second use blocked)")

	# --- demolitionist active hits all enemies ---
	var bd := Board.from_ascii(["#######", "#.....#", "#######"])
	var pd := _make_player(100, 14); pd.cell = Vector2i(1, 1)
	Classes.assign_class(pd, "demolitionist")
	var e1 := CombatEntity.new(2, "A", 40, 10, ["organic"]); e1.faction = "enemy"; e1.cell = Vector2i(4, 1); e1.aware = true
	var e2 := CombatEntity.new(3, "B", 40, 10, ["organic"]); e2.faction = "enemy"; e2.cell = Vector2i(5, 1); e2.aware = true
	var csd := CombatSim.new(bd, {1: pd, 2: e1, 3: e2}, 1, 4)
	bd.place(1, pd.cell); bd.place(2, e1.cell); bd.place(3, e2.cell)
	csd.use_class_active(0)
	_ck(e1.hp <= 25 and e2.hp <= 25, "demolitionist Wybuch deals 15 to every enemy")

	# --- showman active feeds audience (x2 via own passive) ---
	var aud := AudienceState.new()
	var bs := Board.from_ascii(["#####", "#...#", "#####"])
	var ps := _make_player(100, 14); ps.cell = Vector2i(1, 1)
	Classes.assign_class(ps, "showman")
	var es := CombatEntity.new(2, "W", 50, 10, ["organic"]); es.faction = "enemy"; es.cell = Vector2i(3, 1); es.aware = true
	var css := CombatSim.new(bs, {1: ps, 2: es}, 1, 6, {}, [], [], aud, null)
	bs.place(1, ps.cell); bs.place(2, es.cell)
	css.use_class_active(0)
	_ck(aud.rating >= 16, "showman Hype gives +8, doubled by passive to +16")

	# --- occultist curse makes the player harder to hit ---
	var bo := Board.from_ascii(["#####", "#...#", "#####"])
	var po := _make_player(100, 14); po.cell = Vector2i(1, 1)
	Classes.assign_class(po, "occultist")
	var eo := CombatEntity.new(2, "W", 50, 10, ["organic"]); eo.faction = "enemy"; eo.cell = Vector2i(3, 1); eo.aware = true
	var cso := CombatSim.new(bo, {1: po, 2: eo}, 1, 8)
	bo.place(1, po.cell); bo.place(2, eo.cell)
	cso.use_class_active(0)
	_ck(cso._curse_to_hit == 2 and cso._curse_rounds <= 3 and cso._curse_rounds >= 2,
		"occultist Curse sets +2 player AC for ~3 rounds (one ticked by the active's own turn)")

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
