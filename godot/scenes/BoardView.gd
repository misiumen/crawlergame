extends Node2D
## The playable tactical board: renders the sim, takes one-key input, glides
## tokens, and plays the juice (hit-flash, damage floaters, screen shake) + the
## consequence preview drawn ON the board. Visual target = the _mockup_*.png
## frames. All game logic lives in CombatSim; this node only draws + animates.

const TILE := 48
const COL_BG := Color("0b0d12")
const COL_FLOOR := Color("161a23")
const COL_FLOOR2 := Color("1b202b")
const COL_GRID := Color("282e3c")
const COL_WALL := Color("343c4e")
const COL_WALLHI := Color("545e7a")
const COL_WATER := Color("16384a")
const COL_WIRE := Color("f4c260")
const COL_GAS := Color("f08a46")
const COL_PLAYER := Color("60cee9")
const COL_RAT := Color("6c5654")
const COL_RED := Color("e45656")
const COL_CYAN := Color("60cee9")
const COL_AMBER := Color("f4c260")
const COL_DIM := Color("768092")
const COL_BRIGHT := Color("f0f6ff")

var sim: CombatSim
var _origin: Vector2 = Vector2(40, 40)
var _vpos: Dictionary = {}        # id -> current visual pixel center
var _vtarget: Dictionary = {}     # id -> goal pixel center
var _flash: Dictionary = {}       # id -> seconds of red flash remaining
var _dying: Dictionary = {}       # id -> fade 1..0
var _floaters: Array = []         # {pos, text, color, age, ttl}
var _shake := 0.0
var _font: Font
var _log: Array = []              # recent narration lines (Polish)
var _hint := ""
var _craft_open := false

func _ready() -> void:
	_font = ThemeDB.fallback_font
	_build()
	set_process(true)

func _build() -> void:
	var enc := Encounters.intake()
	sim = CombatSim.new(enc["board"], enc["entities"], enc["player_id"], 1337)
	_hint = enc.get("hint", "")
	_log = ["Wchodzisz do hali. Coś tu śpi."]
	var bw: int = sim.board.w * TILE
	_origin = Vector2((1280 - bw) / 2.0 - 140, 110)   # leave room for the log on the right
	for id in sim.entities:
		var c: Vector2 = _cell_px(sim.entities[id].cell)
		_vpos[id] = c
		_vtarget[id] = c
	queue_redraw()

func _cell_px(c: Vector2i) -> Vector2:
	return _origin + Vector2(c.x * TILE + TILE / 2.0, c.y * TILE + TILE / 2.0)

# ---------- input (one key = one action) ----------
func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	var kc: int = (event as InputEventKey).keycode
	if kc == KEY_Z:
		_craft_open = not _craft_open
		queue_redraw(); return
	if _craft_open:
		if kc == KEY_ESCAPE:
			_craft_open = false; queue_redraw(); return
		var idx: int = kc - KEY_1
		if idx >= 0 and idx <= 8:
			_do_craft(idx)
		return
	var shove := Input.is_key_pressed(KEY_SHIFT)
	var dir := Vector2i.ZERO
	match kc:
		KEY_LEFT, KEY_A: dir = Vector2i.LEFT
		KEY_RIGHT, KEY_D: dir = Vector2i.RIGHT
		KEY_UP, KEY_W: dir = Vector2i.UP
		KEY_DOWN, KEY_S: dir = Vector2i.DOWN
		KEY_PERIOD: handle_wait(); return
		KEY_E: handle_interact(); return
		_: return
	if shove: handle_shove(dir)
	else: handle_dir(dir)

func _do_craft(idx: int) -> void:
	var list := sim.craftables()
	if idx < list.size():
		_animate(sim.craft(list[idx]["recipe"]["id"]))
		_craft_open = false
		queue_redraw()

# ---------- public action drivers (also called by headless tests) ----------
func handle_dir(dir: Vector2i) -> void:
	_animate(sim.player_move(dir))

func handle_shove(dir: Vector2i) -> void:
	_animate(sim.player_shove(dir))

func handle_wait() -> void:
	_animate(sim.player_wait())

func handle_interact() -> void:
	_animate(sim.player_interact())

# ---------- event -> animation ----------
func _animate(evs: Array) -> void:
	for e in evs:
		match e.get("type"):
			"move":
				_vtarget[e["id"]] = _cell_px(e["to"])
			"damage":
				var tid: int = e["target"]
				_flash[tid] = 0.24
				var col: Color = COL_CYAN if e.get("dmg_type") == "electric" else COL_RED
				_add_floater(tid, "-%d" % e["amount"], col)
				_shake = maxf(_shake, 5.0 if e["amount"] >= 12 else 2.5)
			"systemic":
				if e.get("element") == "electric":
					_add_floater(e["target"], "PRĄD!", COL_CYAN)
					_shake = maxf(_shake, 6.0)
			"death":
				_dying[e["target"]] = 1.0
			"miss":
				_add_floater(e["target"], "pudło", COL_DIM)
			"salvage":
				_dying[e["target"]] = 1.0
				_add_floater(e["target"], "+złom", COL_AMBER)
				_shake = maxf(_shake, 2.0)
			"notice":
				_add_floater(e["id"], "!", COL_RED)
				_shake = maxf(_shake, 3.0)
			"craft":
				_add_floater(sim.player_id, "+" + str(e["name"]), COL_CYAN)
			"combat_end":
				_add_banner("ZWYCIĘSTWO" if e["outcome"] == "win" else "KONIEC")
		var ln := _event_line(e)
		if ln != "":
			_log_push(ln)
	queue_redraw()

func _name(id: int) -> String:
	var e = sim.entities.get(id)
	return e.name_pl if e != null else "?"

func _log_push(line: String) -> void:
	_log.append(line)
	if _log.size() > 9:
		_log = _log.slice(_log.size() - 9)

func _event_line(e: Dictionary) -> String:
	match e.get("type"):
		"damage":
			var nm := _name(e["target"])
			if e.get("dmg_type") == "electric":
				return "Prąd razi %s: -%d!" % [nm, e["amount"]]
			var tgt = sim.entities.get(e["target"])
			if tgt != null and tgt.has_property("thick_hide"):
				return "Tniesz %s: -%d (gruba skóra tłumi cios)." % [nm, e["amount"]]
			return "Trafienie w %s: -%d." % [nm, e["amount"]]
		"systemic":
			if e.get("element") == "electric":
				return "Iskra z kabla skacze przez wodę — PRĄD!"
		"miss":
			return "Pudło." if e["attacker"] == sim.player_id else "%s chybia." % _name(e["attacker"])
		"death":
			return "%s pada." % _name(e["target"])
		"notice":
			return "%s się budzi i cię widzi!" % _name(e["id"])
		"salvage":
			var parts: Array = []
			for k in e["gained"]:
				parts.append("%s x%d" % [k, e["gained"][k]])
			return "Rozbierasz na: " + ", ".join(parts) + "."
		"shove":
			return "Pchasz %s." % _name(e["target"])
		"skip":
			return "%s drga — traci turę." % _name(e["id"])
		"combat_end":
			return "Wszyscy wrogowie pokonani." if e["outcome"] == "win" else "Giniesz."
		"blocked":
			if e.get("reason") == "object":
				return "(Sprzęt blokuje przejście — [E] rozbierz.)"
		"craft":
			return "Tworzysz: %s." % e["name"]
		"craft_fail":
			var need: Array = []
			for k in e["cost"]:
				need.append("%s x%d" % [k, e["cost"][k]])
			return "Brakuje materiałów: " + ", ".join(need) + "."
		"none":
			match e.get("action"):
				"shove": return "Nie ma kogo pchnąć — stań tuż obok wroga."
				"salvage": return "Nie ma czego rozebrać w pobliżu."
	return ""

var _banner := ""
func _add_banner(txt: String) -> void:
	_banner = txt

func _add_floater(id: int, text: String, color: Color) -> void:
	var pos: Vector2 = _vpos.get(id, _cell_px(Vector2i.ZERO))
	_floaters.append({"pos": pos, "text": text, "color": color, "age": 0.0, "ttl": 0.95})

# ---------- per-frame anim ----------
func _process(dt: float) -> void:
	for id in _vpos:
		_vpos[id] = (_vpos[id] as Vector2).lerp(_vtarget[id], minf(1.0, dt * 12.0))
	for id in _flash.keys():
		_flash[id] = _flash[id] - dt
		if _flash[id] <= 0: _flash.erase(id)
	for id in _dying.keys():
		_dying[id] = _dying[id] - dt * 1.5
		if _dying[id] <= 0: _dying.erase(id)
	for f in _floaters:
		f["age"] += dt
	_floaters = _floaters.filter(func(f): return f["age"] < f["ttl"])
	_shake = maxf(0.0, _shake - dt * 24.0)
	queue_redraw()

# ---------- drawing ----------
func _draw() -> void:
	if sim == null: return
	draw_rect(Rect2(0, 0, 1280, 720), COL_BG)   # backdrop (identity transform)
	var sh := Vector2(randf_range(-_shake, _shake), randf_range(-_shake, _shake))
	draw_set_transform(sh, 0.0, Vector2.ONE)
	var b: Board = sim.board
	# tiles
	for y in b.h:
		for x in b.w:
			var c := Vector2i(x, y)
			var r := Rect2(_origin + Vector2(x * TILE, y * TILE), Vector2(TILE - 1, TILE - 1))
			if b.is_wall(c):
				draw_rect(r, COL_WALL)
				draw_line(r.position, r.position + Vector2(TILE - 1, 0), COL_WALLHI, 1.0)
				continue
			draw_rect(r, COL_FLOOR2 if (x + y) % 2 == 0 else COL_FLOOR)
			draw_rect(r, COL_GRID, false, 1.0)
			match b.hazard_at(c):
				"water": draw_rect(Rect2(r.position + Vector2(3, 3), Vector2(TILE - 7, TILE - 7)), COL_WATER)
				"wire": _draw_glyph("|", c, COL_WIRE)
				"gas": _draw_glyph("G", c, COL_GAS)
	# reachable dots around player
	var p := sim.player()
	for d in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN,
			Vector2i(1,1), Vector2i(-1,1), Vector2i(1,-1), Vector2i(-1,-1)]:
		if b.is_free(p.cell + d):
			draw_circle(_cell_px(p.cell + d), 3.0, Color(0.29, 0.38, 0.47))
	_draw_intent()
	_draw_preview()
	# tokens
	for id in sim.entities:
		var e: CombatEntity = sim.entities[id]
		if not e.is_alive() and not _dying.has(id):
			continue
		var pos: Vector2 = _vpos.get(id, _cell_px(e.cell))
		var fade: float = _dying.get(id, 1.0)
		var flashing := _flash.has(id)
		if e.faction == "player":
			_draw_player(pos, fade)
		elif e.faction == "object":
			_draw_object(e, pos, fade)
		else:
			_draw_rat(pos, fade, flashing)
	# floaters
	for f in _floaters:
		var a: float = 1.0 - float(f["age"]) / float(f["ttl"])
		var col: Color = f["color"]; col.a = a
		var fp: Vector2 = f["pos"] + Vector2(-10, -20 - f["age"] * 36.0)
		draw_string(_font, fp, f["text"], HORIZONTAL_ALIGNMENT_LEFT, -1, 18, col)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	_draw_hud()

func _draw_glyph(s: String, c: Vector2i, col: Color) -> void:
	draw_string(_font, _cell_px(c) + Vector2(-6, 8), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 26, col)

func _draw_player(pos: Vector2, fade: float) -> void:
	var col := COL_PLAYER; col.a = fade
	draw_circle(pos, 16, Color(0.11, 0.20, 0.25, fade))
	draw_arc(pos, 16, 0, TAU, 24, col, 2.0)
	draw_circle(pos + Vector2(0, -3), 9, Color(0.23, 0.70, 0.82, fade))
	draw_line(pos + Vector2(-11, 6), pos + Vector2(-18, -10), Color(COL_BRIGHT, fade), 3.0)

func _draw_rat(pos: Vector2, fade: float, flashing: bool) -> void:
	var body := COL_RED if flashing else COL_RAT
	body.a = fade
	draw_line(pos + Vector2(11, 2), pos + Vector2(22, -8), body, 4.0)   # tail
	_draw_ellipse(pos, 15, 9, body)                                     # body
	draw_circle(pos + Vector2(-13, 0), 7, body)                         # head

func _draw_object(e: CombatEntity, pos: Vector2, fade: float) -> void:
	var col := Color("8a6a3a") if "wood" in e.tags else Color("6a7280")
	col.a = fade
	draw_rect(Rect2(pos - Vector2(15, 12), Vector2(30, 24)), col)
	draw_rect(Rect2(pos - Vector2(15, 12), Vector2(30, 24)), Color(0, 0, 0, 0.45 * fade), false, 1.0)

func _draw_ellipse(center: Vector2, rx: float, ry: float, col: Color) -> void:
	var pts := PackedVector2Array()
	for i in 20:
		var a := TAU * i / 20.0
		pts.append(center + Vector2(cos(a) * rx, sin(a) * ry))
	draw_colored_polygon(pts, col)

func _draw_intent() -> void:
	# perfect-information telegraph: show what each enemy will do this turn
	var p := sim.player()
	for id in sim.entities:
		var e: CombatEntity = sim.entities[id]
		if e.faction != "enemy" or not e.is_alive():
			continue
		var ep: Vector2 = _vpos.get(id, _cell_px(e.cell))
		if not e.aware:
			draw_string(_font, ep + Vector2(-10, -20), "Zzz", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
			continue
		if sim.board.is_adjacent(e.cell, p.cell):
			draw_string(_font, ep + Vector2(-16, -20), "ugryzie", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_RED)
		else:
			var step: Vector2i = e.cell + Vector2i(signi(p.cell.x - e.cell.x), signi(p.cell.y - e.cell.y))
			var sp := _cell_px(step)
			draw_rect(Rect2(sp - Vector2(TILE / 2.0 - 2, TILE / 2.0 - 2), Vector2(TILE - 5, TILE - 5)), Color(COL_RED, 0.16))
			draw_line(ep, sp, Color(COL_RED, 0.7), 2.0)

func _draw_preview() -> void:
	# if shoving the adjacent rat in some dir would land it on a live trap, show it
	var p := sim.player()
	for dir in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var occ := sim.board.occupant_at(p.cell + dir)
		if occ == -1 or occ == sim.player_id:
			continue
		var land: Vector2i = p.cell + dir + dir
		if sim.would_shock_at(land):
			var rp := _cell_px(p.cell + dir)
			var lp := _cell_px(land)
			draw_line(rp, lp, COL_CYAN, 3.0)
			draw_rect(Rect2(lp - Vector2(TILE/2.0-2, TILE/2.0-2), Vector2(TILE-5, TILE-5)), COL_CYAN, false, 2.0)
			draw_string(_font, lp + Vector2(-TILE, TILE/2.0 + 6),
				"Shift+ruch: w kałużę → prąd", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
			return

func _draw_hud() -> void:
	var p := sim.player()
	draw_string(_font, Vector2(40, 36), "SORTOWNIA — Hala  ·  Runda %d  ·  tura: %s"
		% [sim.round_num, "TY" if sim.side == "player" else "wrogowie"],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, COL_CYAN)
	draw_string(_font, Vector2(40, 60),
		"HP %d/%d   ·   strzałki/WSAD ruch (wejście=atak)   ·   Shift+ruch pchnij   ·   E rozbierz   ·   Z warsztat   ·   . czekaj"
		% [p.hp, p.max_hp], HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
	# weapon / coating
	var wln := "Broń: nóż"
	if p.coating == "electric":
		wln += "  [PRĄD x%d]" % p.coating_charges
	if p.bonus_damage > 0:
		wln += "  +%d obr." % p.bonus_damage
	draw_string(_font, Vector2(40, 82), wln, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
	# materials
	var mats: Array = []
	for k in sim.materials:
		mats.append("%s x%d" % [k, sim.materials[k]])
	draw_string(_font, Vector2(40, 104), "Materiały: " + ("—" if mats.is_empty() else ", ".join(mats)),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_AMBER)
	# objective hint
	if _hint != "":
		draw_string(_font, Vector2(40, 700), "Cel: " + _hint, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
	# target readout
	var rat: CombatEntity = sim.entities.get(2)
	if rat != null and rat.is_alive():
		var st := "śpi" if not rat.aware else "ściga cię"
		draw_string(_font, Vector2(40, 676),
			"%s  HP %d/%d  [%s]  ·  gruba skóra (ciosy się ślizgają), słaby na PRĄD"
			% [rat.name_pl, rat.hp, rat.max_hp, st], HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_AMBER)
	# log panel (DZIENNIK) on the right
	var lx := _origin.x + sim.board.w * TILE + 24
	var lw := 1280 - lx - 24
	draw_rect(Rect2(lx, 110, lw, 360), Color(0.08, 0.10, 0.13, 0.9))
	draw_rect(Rect2(lx, 110, lw, 360), COL_GRID, false, 1.0)
	draw_string(_font, Vector2(lx + 12, 132), "DZIENNIK", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
	for i in _log.size():
		var alpha := 0.5 + 0.5 * float(i + 1) / _log.size()
		draw_string(_font, Vector2(lx + 12, 158 + i * 22), _log[i],
			HORIZONTAL_ALIGNMENT_LEFT, lw - 24, 14, Color(COL_BRIGHT, alpha))
	if _banner != "":
		draw_string(_font, Vector2(_origin.x + 120, _origin.y + 160), _banner,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 44, COL_BRIGHT)
	if _craft_open:
		_draw_craft_panel()

func _draw_craft_panel() -> void:
	var w := 540.0
	var h := 230.0
	var x := (1280 - w) / 2.0
	var y := (720 - h) / 2.0
	draw_rect(Rect2(x, y, w, h), Color(0.10, 0.12, 0.16, 0.97))
	draw_rect(Rect2(x, y, w, h), COL_CYAN, false, 2.0)
	draw_string(_font, Vector2(x + 16, y + 26), "WARSZTAT   (cyfra = stwórz · Z/Esc zamknij)",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, COL_CYAN)
	var list := sim.craftables()
	if list.is_empty():
		draw_string(_font, Vector2(x + 16, y + 60), "Brak receptur.", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
		return
	for i in list.size():
		var r: Dictionary = list[i]["recipe"]
		var afford: bool = list[i]["affordable"]
		var yy := y + 58 + i * 66
		var costs: Array = []
		for k in r["cost"]:
			costs.append("%s x%d" % [k, r["cost"][k]])
		var head := "[%d] %s  —  %s  %s" % [i + 1, r["name"], ", ".join(costs), "(OK)" if afford else "(brak)"]
		draw_string(_font, Vector2(x + 16, yy), head, HORIZONTAL_ALIGNMENT_LEFT, -1, 16,
			COL_BRIGHT if afford else COL_DIM)
		draw_string(_font, Vector2(x + 40, yy + 22), r["desc"], HORIZONTAL_ALIGNMENT_LEFT, w - 60, 13, COL_DIM)
