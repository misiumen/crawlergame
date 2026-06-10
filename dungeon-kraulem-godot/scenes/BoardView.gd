extends Node2D
## Playable tactical board: renders the sim, takes one-key input, animates
## events, and draws the crafting bench + inventory panel.

const TILE := 48
const COL_BG      := Color("0b0d12")
const COL_FLOOR   := Color("161a23")
const COL_FLOOR2  := Color("1b202b")
const COL_GRID    := Color("282e3c")
const COL_WALL    := Color("343c4e")
const COL_WALLHI  := Color("545e7a")
const COL_WATER   := Color("16384a")
const COL_WIRE    := Color("f4c260")
const COL_GAS     := Color("f08a46")
const COL_PLAYER  := Color("60cee9")
const COL_RAT     := Color("6c5654")
const COL_RED     := Color("e45656")
const COL_GREEN   := Color("76ce8a")
const COL_CYAN    := Color("60cee9")
const COL_AMBER   := Color("f4c260")
const COL_DIM     := Color("768092")
const COL_BRIGHT  := Color("f0f6ff")
const COL_PURPLE  := Color("b462dc")

var sim: CombatSim
var _origin: Vector2 = Vector2(40, 40)
var _vpos: Dictionary = {}
var _vtarget: Dictionary = {}
var _flash: Dictionary = {}
var _dying: Dictionary = {}
var _floaters: Array = []
var _shake := 0.0
var _font: Font
var _log: Array = []
var _hint := ""
var _done := false
var floor: Floor

# Craft panel state
var _craft_open := false
var _craft_mode := "bench"          # "bench" | "items"
var _bench_slots: Array = []        # material names on the bench
var _bench_preview: Dictionary = {} # last Crafting.preview result

# Body targeting
var _aim_zone := ""                  # "" = body (no chosen zone); else a part key
var _part_flash: Dictionary = {}     # "enemyid:zone" -> seconds left, for hit pulse

# Emergent-class offer
var _class_offer: Array = []         # candidate class keys; non-empty = modal open
var _narr_rng := RandomNumberGenerator.new()   # seeded narrator line picker
var _summary: Dictionary = {}        # non-empty = end-of-run results screen
var _summary_lines: Array = []       # rendered Polish lines for the screen
var _route_offer: Array = []         # candidate biome keys at the stairs; non-empty = modal
var _dlg: Dictionary = {}            # active dialogue-tree conversation state; non-empty = open
var _dlg_info := ""                   # last skill-check result line
var _title := true                   # title screen shown before a run starts
var _click_zones: Array = []         # per-frame clickable UI rects (rebuilt in _draw)
var _mouse: Vector2 = Vector2.ZERO   # last known mouse position (for hover)
var _sponsor_noticed: Dictionary = {} # sponsors whose "took interest" line already fired
var _box_anim: Dictionary = {}       # active lootbox-opening reveal (non-empty = overlay)
var _toasts: Array = []              # achievement-unlock toasts (VS-style)
var _ach_screen := false             # achievements gallery overlay (from title)
var _env_kills := 0                  # environment kills this run (for an achievement)
var _levelup: Dictionary = {}        # pending level-up: spend skill points (non-empty = modal)
var _ach_flash := 0.0                # golden screen-edge burst on a gold/platinum unlock
var _ach_scroll := 0.0               # achievements gallery scroll offset (px)
var _ach_recipes_seen := 0           # discovered-recipe count, to detect new ones for goals
var _meta_screen := false            # loadout & meta-unlocks screen (from the title)
var _meta_scroll := 0.0
var _safehouse: Dictionary = {}      # open safehouse modal: {id, subtype} (non-empty = open)
var _crawler: Dictionary = {}        # open rival-crawler parley modal: {id} (non-empty = open)
var _spellbook := false               # spell list overlay (cast with mana)
var _event: Dictionary = {}           # active mid-floor decision beat (non-empty = modal)
var _speak: Dictionary = {}           # freeform persuasion prompt: {target_id, text, mode, options}
var _journal_screen := false          # knowledge journal overlay (clues + rumors)
var _journal_scroll := 0.0
const META_KIND_COL := {
	"species":    Color(0.55, 0.92, 0.98),
	"origin":     Color(1.00, 0.84, 0.27),
	"start_perk": Color(0.62, 0.86, 0.55),
	"item":       Color(0.80, 0.66, 0.95),
	"companion":  Color(0.95, 0.72, 0.45),
	"biome":      Color(0.55, 0.80, 0.70),
}
const ACH_TIER_COL := {              # Vampire-Survivors tier frames
	"bronze":   Color(0.80, 0.52, 0.28),
	"silver":   Color(0.78, 0.82, 0.86),
	"gold":     Color(1.00, 0.84, 0.27),
	"platinum": Color(0.55, 0.92, 0.98),
}
const SKILL_STATS := [["STR", "siła — obrażenia w walce"], ["DEX", "zręczność — celność"],
	["INT", "spryt — majsterkowanie i dialogi"], ["WIS", "spostrzegawczość — czujność i dialogi"],
	["CHA", "charyzma — perswazja i widownia"]]
const BOX_SPIN := 1.8                 # reel spin seconds
const BOX_POP := 0.55                 # snap-flash seconds
const BOX_REVEAL_STEP := 0.30         # seconds between each loot piece popping in
const BOX_BONUS_MATS := ["złom", "drewno", "szmata", "przewód", "plastik", "bateria", "rurka"]

var _cam: Camera2D = null            # world camera (smooth follow + shake)
var _ui: Control = null              # screen-fixed UI painter on a CanvasLayer
var _cmod: CanvasModulate = null     # biome ambient colour grade (world only)
var _plight: PointLight2D = null     # soft light following the player
var _sfx: Node = null               # procedural audio (SFX + music)
var _light_tex: Texture2D = null     # shared radial gradient for all 2D lights
var _lights_root: Node2D = null      # pooled hazard/safehouse lights
var _lunge: Dictionary = {}          # id -> {dir: Vector2, t: float} attack lunges
var _parts: Array = []               # particles: {pos, vel, life, ttl, size, col, grav}
var _wipe := 0.0                     # floor/room transition fade (1 → 0)
var _summary_lock := 0.0             # results-screen input lockout (no accidental restart)
var _char_screen := false            # character sheet overlay [C]
var _pause_screen := false           # pause + settings overlay [Esc]
var _ember_cd := 0.0                 # fire-hazard ember spawn cooldown
var _smoke := false                  # --smoke: scripted draw-path autotest, then quit
var _smoke_frames := 0

func _ready() -> void:
	# Phase C: a monospace system font — crisp terminal aesthetic that matches the
	# vector-neon look, with full Polish diacritics (Windows ships all of these).
	var sysf := SystemFont.new()
	sysf.font_names = PackedStringArray(["Cascadia Mono", "Consolas", "Lucida Console"])
	_font = sysf
	RenderingServer.set_default_clear_color(COL_BG)
	# World camera: the board lives in world space; the camera frames it (and will
	# follow the player on bigger boards in Phase B).
	_cam = Camera2D.new()
	_cam.position_smoothing_enabled = true
	_cam.position_smoothing_speed = 8.0
	add_child(_cam)
	_cam.make_current()
	# Screen-fixed UI on a CanvasLayer above the world.
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	_ui = preload("res://scenes/UIView.gd").new()
	_ui.controller = self
	layer.add_child(_ui)
	# Biome mood: a world-only colour grade + a soft light following the player
	# (dark biomes like Lawowe Tunele lean on it; bright ones barely use it).
	_cmod = CanvasModulate.new()
	_cmod.color = Color(1, 1, 1)
	add_child(_cmod)
	var grad := Gradient.new()
	grad.colors = PackedColorArray([Color(1, 0.95, 0.85, 0.5), Color(1, 1, 1, 0.0)])
	var ltex := GradientTexture2D.new()
	ltex.gradient = grad
	ltex.fill = GradientTexture2D.FILL_RADIAL
	ltex.fill_from = Vector2(0.5, 0.5)
	ltex.fill_to = Vector2(0.5, 0.0)
	ltex.width = 512
	ltex.height = 512
	_light_tex = ltex
	_plight = PointLight2D.new()
	_plight.texture = ltex
	_plight.energy = 0.0
	add_child(_plight)
	_lights_root = Node2D.new()
	add_child(_lights_root)
	_sfx = preload("res://scenes/Sfx.gd").new()
	add_child(_sfx)
	_load_settings.call_deferred()   # after the Sfx buses exist
	if "--smoke" in OS.get_cmdline_user_args():
		_smoke = true
	set_process(true)
	queue_redraw()                   # show the title; a run starts on a keypress

const FINAL_FLOOR := 6   # descending from here wins the run
var _run_seed: int = 20260605

func _build() -> void:
	_title = false
	_sponsor_noticed.clear()
	_env_kills = 0
	var content := _content_bundle()
	_narr_rng.seed = 9001
	_register_loadout_biomes()           # owned biomes join the route pool (fresh OR resumed)
	# Resume from a checkpoint if one exists.
	if Save.has_save():
		var sd := Save.read()
		var fl = Save.rebuild_floor(sd, content)
		if fl != null:
			floor = fl
			_run_seed = int(sd.get("seed", _run_seed))
			sim = floor.sim
			_hint = floor.rooms[floor.current].get("name", "")
			_log = ["Wczytano zapis. Kontynuujesz zjazd — piętro %d." % floor.depth]
			floor.attach_companion(_make_companion())   # the pet rejoins on resume
			_arm_floor_traits()
			sim.refill_mana()
			if floor.objective.is_empty():               # older save / first time → roll one
				floor.objective = Objectives.pick(floor.depth, _narr_rng)
			_attach_bodies(); _recenter(); _reset_visuals()
			_spawn_safehouse()
			_maybe_spawn_crawler()
			return
	# Fresh run.
	_run_seed = _new_seed()
	var data := FloorGen.generate(1, _run_seed, content)
	data["companion"] = _make_companion()    # pet ally from the loadout, if any
	floor = Floor.new(data)
	sim = floor.sim
	_hint = data.get("hint", "")
	_log = ["Piętro 1. Zaczynasz zjazd. Rozbieraj, kuj, walcz — i schodź głębiej."]
	_apply_loadout()               # bake the meta-progression loadout into this fresh run
	_arm_floor_traits()
	sim.refill_mana()
	floor.objective = Objectives.pick(floor.depth, _narr_rng)   # this floor's tracked goal
	_attach_bodies()
	_recenter()
	_reset_visuals()
	_spawn_safehouse()
	_maybe_spawn_crawler()
	Save.write(floor, _run_seed)   # checkpoint at the start (loadout now baked into the save)

func _new_seed() -> int:
	# Varies per launch (Math.random/argless Date are unavailable in this harness).
	return int(Time.get_ticks_usec()) & 0x7fffffff

## Entity content pulled from the Data autoload (empty -> FloorGen fallback).
func _content_bundle() -> Dictionary:
	var mon: Variant = _data_group("entity_templates", "MON")
	var env: Variant = _data_group("entity_templates", "ENV")
	var stats: Variant = _data_group("entity_templates", "MOB_COMBAT_STATS")
	var out: Dictionary = {}
	if mon is Dictionary: out["MON"] = mon
	if env is Dictionary: out["ENV"] = env
	if stats is Dictionary: out["MOB_COMBAT_STATS"] = stats
	return out

## At the stairs you GAMBLE A ROUTE: pick one of a few biomes for the next floor
## (or win if the next floor is past the finale).
func _offer_routes() -> void:
	if floor.depth + 1 > FINAL_FLOOR:
		_end_run(true)
		return
	_route_offer = Routes.offer(_narr_rng, 3)
	_log_push("Stoisz przy schodach. Którędy w dół?")
	queue_redraw()

## Descend into the chosen route's biome, carrying the whole run forward (player,
## kit, audience, sponsors, recipes). Death is the only thing that ends a run early.
func _descend_into(biome_key: String) -> void:
	_route_offer = []
	_ach_floor_complete(floor.biome)   # judge the floor being LEFT (biome, restraint…)
	# The crusade follows you down: up to 3 of your converts take the stairs too.
	var crusade: Array = []
	if sim != null:
		for aid in sim.entities:
			var ae: CombatEntity = sim.entities[aid]
			if ae.faction == "ally" and ae.is_alive() and ae.tags.has("convert") \
					and crusade.size() < 3:
				crusade.append(ae)
	var next_depth: int = floor.depth + 1
	var mods := Routes.mods_for(biome_key)
	var is_boss: bool = next_depth == FINAL_FLOOR    # the finale floor is a boss arena
	var data := FloorGen.generate(next_depth, _run_seed, _content_bundle(), mods, is_boss)
	# Carry the run forward: keep the same player + accumulated state.
	floor.player.cell = data["start_cell"]
	floor.player.class_active_used_floor = -1   # active recharges each floor
	# A breather between floors: heal 15% max HP (keeps a 6-floor run winnable).
	var rest := int(round(floor.player.max_hp * 0.15))
	var healed := mini(rest, floor.player.max_hp - floor.player.hp)
	floor.player.hp = mini(floor.player.max_hp, floor.player.hp + rest)
	if healed > 0:
		_log_push("Łapiesz oddech na schodach: +%d HP." % healed)
	data["player"] = floor.player
	data["inv"] = floor.inv
	data["items"] = floor.items
	data["boxes"] = floor.boxes
	data["discovered"] = floor.discovered_recipes
	data["audience"] = floor.audience
	data["sponsors"] = floor.sponsors
	data["class_offered"] = floor.class_offered
	data["companion"] = _make_companion()   # a fresh mascot is sent down each floor
	floor = Floor.new(data)
	sim = floor.sim
	# Re-seat the crusade on the new floor (fresh ids clear of the new floor's range).
	for ci in crusade.size():
		var conv: CombatEntity = crusade[ci]
		conv.id = 900 + ci
		floor.attach_follower(conv)
	if not crusade.is_empty():
		_log_push("Twoja krucjata schodzi z tobą: %d wyznawców." % crusade.size())
	_hint = data.get("hint", "")
	_aim_zone = ""; sim.aim_zone = ""
	_attach_bodies()
	_recenter()
	_reset_visuals()
	_spawn_safehouse()
	_maybe_spawn_crawler()
	_wipe = 1.0                    # descent fade-in
	_play("descend")
	_arm_floor_traits()            # re-arm per-floor species traits (e.g. first strike)
	sim.refill_mana()              # mana tops up each floor
	floor.objective = Objectives.pick(next_depth, _narr_rng)   # a fresh segment goal
	_log_push("Piętro %d — %s." % [next_depth, Routes.label_of(biome_key)])
	# A celebrity sometimes headlines the floor (celebrities.json) — pure spectacle.
	if _narr_rng.randf() < 0.35:
		var celeb := Flavor.celebrity_for(next_depth, _narr_rng)
		if not celeb.is_empty():
			_log_push("Konferansjer: " + celeb["intro"])
			if floor.audience != null: floor.audience.change(2, "celebrity")
	_ach_descend(next_depth)
	if next_depth >= FINAL_FLOOR: _unlock_ach("reach_final")
	# NB: descending does NOT grant XP — otherwise you could level up just by
	# walking floor-to-floor without fighting. XP is earned from kills, salvage and
	# completing the floor objective. The descent reward is the heal + the loot box.
	Save.write(floor, _run_seed)   # checkpoint at each new floor

## Reach the Data autoload via /root (BoardView is a Node, so this is safe and
## avoids the bare `Data` identifier that won't compile under headless -s/--import).
func _data_group(bundle: String, name: String) -> Variant:
	# Via the main-loop root (works even before this node is in the tree, e.g.
	# under headless -s), not an absolute get_node path.
	var loop := Engine.get_main_loop()
	if not (loop is SceneTree):
		return null
	var node := (loop as SceneTree).root.get_node_or_null("Data")
	if node == null or not node.has_method("group"):
		return null
	return node.call("group", bundle, name)

## Give every enemy in the current room a procedural body from body_plans.json.
func _attach_bodies() -> void:
	var bundle: Variant = _data_group("body_plans", "PLANS")
	if not (bundle is Dictionary):
		return
	# from_bundle wants the WHOLE body_plans bundle (PLANS + PLAN_BY_TAG + ...).
	# NB: `x or {}` returns a BOOL in GDScript — must use explicit type guards.
	var by_key: Variant = _data_group("body_plans", "PLANS_BY_MONSTER_KEY")
	var by_tag: Variant = _data_group("body_plans", "PLAN_BY_TAG")
	var full := {
		"PLANS": bundle,
		"PLANS_BY_MONSTER_KEY": by_key if by_key is Dictionary else {},
		"PLAN_BY_TAG": by_tag if by_tag is Array else [],
	}
	for id in sim.entities:
		var e: CombatEntity = sim.entities[id]
		if e.faction == "enemy" and e.body == null:
			e.attach_body(full)

func _recenter() -> void:
	# The board sits at world origin; the camera frames it centred in the playfield
	# (the area left of the fixed log panel at x=830 → playfield centre ≈ 415).
	_origin = Vector2.ZERO
	if _cam != null:
		var bw: int = sim.board.w * TILE
		var bh: int = sim.board.h * TILE
		_cam.position = Vector2(bw / 2.0 + (640.0 - 415.0), bh / 2.0 - 10.0)
		_cam.reset_smoothing()

func _reset_visuals() -> void:
	if floor != null:
		_ach_recipes_seen = floor.discovered_recipes.size()   # baseline for recipe-goal tracking
	_vpos.clear(); _vtarget.clear(); _flash.clear(); _dying.clear(); _floaters.clear()
	_parts.clear(); _lunge.clear()
	for id in sim.entities:
		var c: Vector2 = _cell_px(sim.entities[id].cell)
		_vpos[id] = c
		_vtarget[id] = c
	_rebuild_world_lights()
	queue_redraw()

func _check_transition() -> void:
	if floor == null:
		return
	var r = floor.try_transition()
	if r == null:
		return
	if r.get("blocked", "") == "boss":
		_log_push("Boss blokuje wyjście. Najpierw go pokonaj.")
		return
	if r.get("descend", false):
		_add_banner("ZEJŚCIE NIŻEJ")
		_offer_routes()
		return
	sim = floor.sim
	_attach_bodies()
	_aim_zone = ""; sim.aim_zone = ""
	_recenter()
	_reset_visuals()
	_wipe = 1.0   # quick fade-in as you step through the door
	_play("door")
	_log_push("Przechodzisz do: %s." % r.get("name", "?"))

func _cell_px(c: Vector2i) -> Vector2:
	return _origin + Vector2(c.x * TILE + TILE / 2.0, c.y * TILE + TILE / 2.0)

# ── Input ─────────────────────────────────────────────────────────────────────

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_mouse = (event as InputEventMouseMotion).position
		queue_redraw()
		return
	# [F11] fullscreen toggle — available everywhere.
	if event is InputEventKey and event.pressed and not event.echo \
			and (event as InputEventKey).keycode == KEY_F11:
		var wm := DisplayServer.window_get_mode()
		DisplayServer.window_set_mode(
			DisplayServer.WINDOW_MODE_WINDOWED if wm == DisplayServer.WINDOW_MODE_FULLSCREEN
			else DisplayServer.WINDOW_MODE_FULLSCREEN)
		return
	# Freeform persuasion prompt: while typing, capture text directly (unicode), so
	# this must intercept BEFORE the generic keycode handling below.
	if not _speak.is_empty() and _speak.get("mode", "") == "type" \
			and event is InputEventKey and event.pressed and not event.echo:
		var sk: int = (event as InputEventKey).keycode
		if sk == KEY_ESCAPE:
			_speak = {}; queue_redraw()
		elif sk == KEY_ENTER or sk == KEY_KP_ENTER:
			_speak_submit()
		elif sk == KEY_BACKSPACE:
			var t: String = _speak.get("text", "")
			_speak["text"] = t.substr(0, maxi(0, t.length() - 1)); queue_redraw()
		else:
			var ch: int = (event as InputEventKey).unicode
			if ch >= 32 and str(_speak.get("text", "")).length() < 64:
				_speak["text"] = str(_speak.get("text", "")) + String.chr(ch); queue_redraw()
		return
	# Controller: dpad moves, A interact, B wait, X craft, Y spellbook, Start pause.
	if event is InputEventJoypadButton and event.pressed:
		var jb := (event as InputEventJoypadButton).button_index
		if _pause_screen and jb == JOY_BUTTON_START:
			_pause_screen = false; _play("close"); queue_redraw(); return
		if _can_take_board_input():
			match jb:
				JOY_BUTTON_START:
					_pause_screen = true; _play("open"); queue_redraw(); return
				JOY_BUTTON_DPAD_LEFT: handle_dir(Vector2i.LEFT); return
				JOY_BUTTON_DPAD_RIGHT: handle_dir(Vector2i.RIGHT); return
				JOY_BUTTON_DPAD_UP: handle_dir(Vector2i.UP); return
				JOY_BUTTON_DPAD_DOWN: handle_dir(Vector2i.DOWN); return
				JOY_BUTTON_A: handle_interact(); return
				JOY_BUTTON_B: handle_wait(); return
				JOY_BUTTON_X:
					_craft_open = true; _craft_mode = "bench"; _play("open"); queue_redraw(); return
				JOY_BUTTON_Y:
					_spellbook = true; _play("open"); queue_redraw(); return
				JOY_BUTTON_RIGHT_SHOULDER: _use_class_active(); return
				JOY_BUTTON_LEFT_SHOULDER: _use_companion_ability(); return
	# Lootbox reveal grabs all input: a click/key skips the spin or collects the loot.
	if not _box_anim.is_empty():
		if (event is InputEventMouseButton and event.pressed) \
				or (event is InputEventKey and event.pressed and not event.echo):
			_box_anim_advance()
		return
	# ── Mouse: LMB acts (UI option, or board attack/talk/move), RMB shoves ──
	if event is InputEventMouseButton and event.pressed:
		var mb := event as InputEventMouseButton
		# Wheel scrolls the achievements gallery / meta screen.
		if _ach_screen:
			if mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				_ach_scroll += 56.0; queue_redraw(); return
			elif mb.button_index == MOUSE_BUTTON_WHEEL_UP:
				_ach_scroll = maxf(0.0, _ach_scroll - 56.0); queue_redraw(); return
		if _meta_screen:
			if mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				_meta_scroll += 56.0; queue_redraw(); return
			elif mb.button_index == MOUSE_BUTTON_WHEEL_UP:
				_meta_scroll = maxf(0.0, _meta_scroll - 56.0); queue_redraw(); return
		if _journal_screen:
			if mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				_journal_scroll += 56.0; queue_redraw(); return
			elif mb.button_index == MOUSE_BUTTON_WHEEL_UP:
				_journal_scroll = maxf(0.0, _journal_scroll - 56.0); queue_redraw(); return
		if mb.button_index == MOUSE_BUTTON_LEFT:
			# On-screen buttons/options first. Reverse order so panels drawn LAST
			# (modals on top) win over board-HUD zones underneath them.
			for j in range(_click_zones.size() - 1, -1, -1):
				if (_click_zones[j]["rect"] as Rect2).has_point(mb.position):
					_dispatch_zone(_click_zones[j])
					return
			if _can_take_board_input():
				_click_primary(_cell_from_mouse(mb.position))
		elif mb.button_index == MOUSE_BUTTON_RIGHT:
			if _can_take_board_input():
				_click_shove(_cell_from_mouse(mb.position))
		return
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	var kc: int = (event as InputEventKey).keycode

	# Loadout & meta-unlocks screen (from the title): scroll + Esc returns.
	if _meta_screen:
		if kc == KEY_ESCAPE or kc == KEY_M:
			_meta_screen = false; queue_redraw()
		elif kc == KEY_DOWN: _meta_scroll += 84.0; queue_redraw()
		elif kc == KEY_UP:   _meta_scroll = maxf(0.0, _meta_scroll - 84.0); queue_redraw()
		elif kc == KEY_PAGEDOWN: _meta_scroll += 480.0; queue_redraw()
		elif kc == KEY_PAGEUP:   _meta_scroll = maxf(0.0, _meta_scroll - 480.0); queue_redraw()
		elif kc == KEY_ENTER or kc == KEY_KP_ENTER:
			_start_run_from_meta()
		return

	# Achievements gallery (opened from the title): scroll + Esc/back returns.
	if _ach_screen:
		if kc == KEY_ESCAPE or kc == KEY_A or kc == KEY_O:
			_ach_screen = false; queue_redraw()
		elif kc == KEY_DOWN: _ach_scroll += 84.0; queue_redraw()
		elif kc == KEY_UP:   _ach_scroll = maxf(0.0, _ach_scroll - 84.0); queue_redraw()
		elif kc == KEY_PAGEDOWN: _ach_scroll += 480.0; queue_redraw()
		elif kc == KEY_PAGEUP:   _ach_scroll = maxf(0.0, _ach_scroll - 480.0); queue_redraw()
		return

	# Title screen: Enter continues a save (or starts fresh), N forces a new run,
	# A opens the achievements gallery.
	if _title:
		if kc == KEY_A:
			_open_ach_screen(); return
		if kc == KEY_M:
			_meta_screen = true; _meta_scroll = 0.0; queue_redraw(); return
		if kc == KEY_N:
			Save.clear()
		if kc == KEY_ENTER or kc == KEY_KP_ENTER or kc == KEY_N or kc == KEY_SPACE:
			_build()
		return

	# Results screen: Enter starts a fresh run (after the read-your-death lockout).
	if not _summary.is_empty():
		if _summary_lock <= 0.0 and (kc == KEY_ENTER or kc == KEY_KP_ENTER):
			_summary = {}; _summary_lines = []; _done = false
			_build()
		return

	# Character sheet: Esc/C closes.
	if _char_screen:
		if kc == KEY_ESCAPE or kc == KEY_C:
			_char_screen = false; _play("close"); queue_redraw()
		return

	# Pause + settings: Esc resumes.
	if _pause_screen:
		if kc == KEY_ESCAPE:
			_pause_screen = false; _play("close"); queue_redraw()
		return

	# Safehouse menu grabs input until you leave (Esc).
	if not _safehouse.is_empty():
		if kc == KEY_ESCAPE:
			_safehouse = {}; queue_redraw()
		return

	# Rival-crawler parley grabs input until you choose (Esc = leave).
	if not _crawler.is_empty():
		if kc == KEY_ESCAPE:
			_crawler = {}; queue_redraw()
		return

	# Mid-floor decision beat grabs input until a fork is chosen (1/2).
	if not _event.is_empty():
		var ei := kc - KEY_1
		if ei >= 0 and ei < (_event.get("forks", []) as Array).size():
			_event_choose(ei)
		return

	# Knowledge journal: scroll + close.
	if _journal_screen:
		if kc == KEY_ESCAPE or kc == KEY_J:
			_journal_screen = false; queue_redraw()
		elif kc == KEY_DOWN: _journal_scroll += 80.0; queue_redraw()
		elif kc == KEY_UP:   _journal_scroll = maxf(0.0, _journal_scroll - 80.0); queue_redraw()
		return

	# Persuasion prompt in fallback mode: number keys pick an improvised line.
	if not _speak.is_empty() and _speak.get("mode", "") == "fallback":
		if kc == KEY_ESCAPE or kc == KEY_K:
			_speak = {}; queue_redraw(); return
		var mi := kc - KEY_1
		if mi >= 0 and mi < (_speak.get("options", []) as Array).size():
			_speak_pick(mi)
		return

	# Spellbook grabs input: number keys cast a KNOWN spell, Esc closes.
	if _spellbook:
		if kc == KEY_ESCAPE or kc == KEY_Z:
			_spellbook = false; queue_redraw(); return
		var ks: Array = Spells.known(sim.player())
		var si := kc - KEY_1
		if si >= 0 and si < ks.size():
			_cast_spell(ks[si])
		return

	# NPC dialogue grabs input until you choose or walk away (Esc).
	if not _dlg.is_empty():
		if kc == KEY_ESCAPE:
			_dlg = {}; _dlg_info = ""; queue_redraw(); return
		var dpick := kc - KEY_1
		var avail := Dialogue.available_options(floor, _dlg)
		if dpick >= 0 and dpick < avail.size():
			_dlg_advance(int(avail[dpick][0]))
		return

	# Route-gamble modal at the stairs grabs input until a route is chosen.
	if not _route_offer.is_empty():
		var rpick := kc - KEY_1
		if rpick >= 0 and rpick < _route_offer.size():
			_descend_into(_route_offer[rpick])
		return

	# Class-offer modal grabs input until a choice is made.
	if not _class_offer.is_empty():
		var pick := kc - KEY_1
		if pick >= 0 and pick < _class_offer.size():
			_accept_class(pick)
		return

	# Level-up modal: spend banked skill points on a stat (1-5), Esc to bank them.
	if not _levelup.is_empty():
		if kc == KEY_ESCAPE:
			_levelup = {}; queue_redraw(); return
		var spick := kc - KEY_1
		if spick >= 0 and spick < SKILL_STATS.size():
			_spend_skill_point(SKILL_STATS[spick][0])
		return

	# [F] fire the emergent-class active ability
	if kc == KEY_F:
		_use_class_active(); return

	# [G] fire the companion's ability
	if kc == KEY_G:
		_use_companion_ability(); return

	# [Z] open/close the spellbook
	if kc == KEY_Z:
		_spellbook = not _spellbook; queue_redraw(); return

	# [J] open/close the knowledge journal
	if kc == KEY_J:
		_journal_screen = not _journal_screen; _journal_scroll = 0.0; queue_redraw(); return

	# [K] speak to the nearest mind — freeform social engineering (hidden road)
	if kc == KEY_K:
		_open_speak(); return

	# [O] view achievements mid-run ([A] is taken by movement; on the title it's [A])
	if kc == KEY_O:
		_open_ach_screen(); return

	# [C] character sheet (stats, equipment with unequip, traits, spells)
	if kc == KEY_C:
		_char_screen = not _char_screen
		_play("open" if _char_screen else "close")
		queue_redraw(); return

	# [Esc] pause + settings (only when nothing else holds the input)
	if kc == KEY_ESCAPE and _can_take_board_input():
		_pause_screen = true; _play("open"); queue_redraw(); return

	# [L] open the skill-point allocation modal (if you've banked any)
	if kc == KEY_L:
		if sim != null and sim.player().skill_points > 0:
			_levelup = {"open": true}; queue_redraw()
		return

	# [I] toggles the craft panel
	if kc == KEY_I:
		_craft_open = not _craft_open
		if _craft_open:
			_craft_mode = "bench"
			_bench_slots.clear()
			_bench_preview = {}
		queue_redraw(); return

	if _craft_open:
		_handle_craft_input(kc); return

	# [T] cycle the aimed body zone of the focused enemy (-> harder hit, your pick)
	if kc == KEY_T:
		_cycle_aim(); return

	var shove := Input.is_key_pressed(KEY_SHIFT)
	var dir := Vector2i.ZERO
	match kc:
		KEY_LEFT,  KEY_A: dir = Vector2i.LEFT
		KEY_RIGHT, KEY_D: dir = Vector2i.RIGHT
		KEY_UP,    KEY_W: dir = Vector2i.UP
		KEY_DOWN,  KEY_S: dir = Vector2i.DOWN
		KEY_SPACE, KEY_PERIOD: handle_wait(); return   # Space = pass the turn
		KEY_E:      handle_interact(); return
		_: return
	if shove: handle_shove(dir)
	else:     handle_dir(dir)

# ── Mouse + dedicated-attack helpers ──────────────────────────────────────────

## True only during normal board play (no modal/overlay grabbing input).
func _can_take_board_input() -> bool:
	return not _title and not _done and sim != null \
		and _summary.is_empty() and _dlg.is_empty() and _box_anim.is_empty() \
		and _route_offer.is_empty() and _class_offer.is_empty() and not _craft_open \
		and _levelup.is_empty() and not _ach_screen and not _meta_screen \
		and _safehouse.is_empty() and _crawler.is_empty() and not _spellbook \
		and not _journal_screen and _event.is_empty() and _speak.is_empty() \
		and not _char_screen and not _pause_screen

## Mouse -> board cell, through the camera (the board lives in world space now).
func _cell_from_mouse(_pos: Vector2) -> Vector2i:
	var local := get_global_mouse_position() - _origin
	return Vector2i(int(floor(local.x / TILE)), int(floor(local.y / TILE)))

## LMB on the board is fully contextual: an adjacent enemy → attack (honoring the
## aimed zone), an adjacent NPC → talk, an adjacent salvageable object → dismantle,
## an empty adjacent tile → move, a distant tile → step toward it, yourself → wait.
func _click_primary(cell: Vector2i) -> void:
	if sim == null or not sim.board.in_bounds(cell):
		return
	var p := sim.player()
	var d: Vector2i = cell - p.cell
	var cheb: int = maxi(absi(d.x), absi(d.y))
	if cheb == 0:
		handle_wait()
	elif cheb == 1:
		var occ: int = sim.board.occupant_at(cell)
		if occ != -1 and occ != p.id:
			var t: CombatEntity = sim.entities[occ]
			if t.faction == "object" and "salvage" in t.affordances:
				handle_interact()   # dismantle the gear you clicked
				return
		handle_dir(d)               # enemy attack / npc talk / move / blocked
	else:
		handle_dir(Vector2i(signi(d.x), signi(d.y)))   # click-to-move one step

## RMB: shove the clicked adjacent enemy (push it — best used into a hazard).
func _click_shove(cell: Vector2i) -> void:
	if sim == null:
		return
	var d: Vector2i = cell - sim.player().cell
	if maxi(absi(d.x), absi(d.y)) == 1:
		handle_shove(d)

# ── Clickable UI zones (registered by _draw_* each frame, hit-tested on LMB) ───

func _zone(r: Rect2, kind: String, i: int = 0, s: String = "") -> void:
	_click_zones.append({"rect": r, "kind": kind, "i": i, "s": s})

## Phase C panel chrome: drop shadow, header strip, accent spine + border — one
## consistent frame for every modal instead of ad-hoc rectangles.
func _panel(c: CanvasItem, r: Rect2, accent: Color, title: String = "") -> void:
	c.draw_rect(Rect2(r.position + Vector2(5, 6), r.size), Color(0, 0, 0, 0.45))
	c.draw_rect(r, Color(0.055, 0.075, 0.095, 0.985))
	c.draw_rect(Rect2(r.position, Vector2(r.size.x, 40.0)), Color(accent, 0.10))
	c.draw_rect(r, accent, false, 2.0)
	c.draw_rect(Rect2(r.position, Vector2(5, r.size.y)), Color(accent, 0.8))
	if title != "":
		c.draw_string(_font, r.position + Vector2(20, 27), title,
			HORIZONTAL_ALIGNMENT_LEFT, r.size.x - 36, 20, accent)

## Tiny vector icons (Phase C): materials, item categories, spells, coin.
func _draw_icon(c: CanvasItem, kind: String, pos: Vector2, col: Color) -> void:
	match kind:
		"złom":
			c.draw_arc(pos, 5.0, 0, TAU, 10, col, 1.6)
			for k in 4:
				var a := TAU * k / 4.0
				c.draw_line(pos + Vector2(cos(a), sin(a)) * 5.0, pos + Vector2(cos(a), sin(a)) * 7.5, col, 1.6)
		"drewno":
			c.draw_rect(Rect2(pos + Vector2(-6, -4), Vector2(12, 3)), col)
			c.draw_rect(Rect2(pos + Vector2(-6, 1), Vector2(12, 3)), Color(col, 0.6))
		"szmata":
			c.draw_polyline(PackedVector2Array([pos + Vector2(-6, -3), pos + Vector2(-2, 1),
				pos + Vector2(2, -3), pos + Vector2(6, 1)]), col, 1.8)
		"przewód":
			c.draw_arc(pos + Vector2(-3, 0), 3.0, 0, TAU, 8, col, 1.4)
			c.draw_arc(pos + Vector2(3, 0), 3.0, 0, TAU, 8, col, 1.4)
		"plastik":
			c.draw_rect(Rect2(pos + Vector2(-5, -5), Vector2(10, 10)), col, false, 1.6)
		"bateria":
			c.draw_rect(Rect2(pos + Vector2(-4, -6), Vector2(8, 12)), col, false, 1.6)
			c.draw_rect(Rect2(pos + Vector2(-2, -8), Vector2(4, 2)), col)
		"rurka":
			c.draw_line(pos + Vector2(-6, 2), pos + Vector2(6, -2), col, 3.0)
		"weapon":
			c.draw_line(pos + Vector2(-5, 5), pos + Vector2(5, -5), col, 2.0)
			c.draw_line(pos + Vector2(-2, 0), pos + Vector2(0, 2), col, 2.0)
		"armor":
			c.draw_polyline(PackedVector2Array([pos + Vector2(-5, -5), pos + Vector2(5, -5),
				pos + Vector2(5, 1), pos + Vector2(0, 6), pos + Vector2(-5, 1), pos + Vector2(-5, -5)]), col, 1.6)
		"medical":
			c.draw_rect(Rect2(pos + Vector2(-2, -6), Vector2(4, 12)), col)
			c.draw_rect(Rect2(pos + Vector2(-6, -2), Vector2(12, 4)), col)
		"spell":
			for k in 4:
				var a2 := TAU * k / 4.0 + PI / 4.0
				c.draw_line(pos, pos + Vector2(cos(a2), sin(a2)) * 6.0, col, 1.6)
			c.draw_circle(pos, 2.0, col)
		"coin":
			c.draw_arc(pos, 5.5, 0, TAU, 12, col, 1.6)
			c.draw_line(pos + Vector2(0, -3), pos + Vector2(0, 3), col, 1.6)
		_:
			c.draw_circle(pos, 3.0, col)

func _hover(r: Rect2) -> bool:
	return r.has_point(_mouse)

## Surface a sponsor's shifting attention (throttled): the first time one warms to
## you, say so + what it likes — so the gift box later reads as EARNED, not random.
func _sponsor_reaction(e: Dictionary) -> void:
	var key: String = e.get("key", "")
	var val: int = int(e.get("val", 0))
	var prev: int = val - int(e.get("delta", 0))
	if prev < 1 and val >= 1 and not _sponsor_noticed.has(key):
		_sponsor_noticed[key] = true
		var nm: String = e.get("name", key)
		_add_floater(sim.player_id, nm + " patrzy", COL_PURPLE)
		var likes := floor.sponsors.likes_summary(key)
		if likes != "":
			_log_push("%s zaczyna cię obserwować (lubi: %s)." % [nm, likes])
		else:
			_log_push("%s zaczyna cię obserwować." % nm)
	elif prev > -3 and val <= -3 and not _sponsor_noticed.has("h_" + key):
		_sponsor_noticed["h_" + key] = true
		_log_push("%s ma cię na oku — i nie w dobrym sensie." % e.get("name", key))

func _dispatch_zone(z: Dictionary) -> void:
	_play("click")
	var i: int = int(z.get("i", 0))
	match z.get("kind", ""):
		"title_continue", "title_start": _build()
		"title_new":         Save.clear(); _build()
		"summary_continue":
			if _summary_lock <= 0.0:
				_summary = {}; _summary_lines = []; _done = false; _build()
		"dlg":               _dlg_advance(i)
		"route":             if i < _route_offer.size(): _descend_into(_route_offer[i])
		"class":             _accept_class(i)
		"tab_bench":         _craft_mode = "bench"; queue_redraw()
		"tab_items":         _craft_mode = "items"; queue_redraw()
		"craft_close":       _craft_open = false; queue_redraw()
		"bench_mat":         _bench_add_material(i)
		"bench_remove":      _bench_remove_at(i)
		"bench_attempt":     _bench_attempt_now()
		"item_use":          _item_use(i)
		"box_open":          _open_box(i); queue_redraw()
		"aim_part":          _set_aim(z.get("s", ""))
		"ach_open":          _open_ach_screen()
		"ach_back":          _ach_screen = false; queue_redraw()
		"meta_open":         _meta_screen = true; _meta_scroll = 0.0; queue_redraw()
		"meta_back":         _meta_screen = false; queue_redraw()
		"meta_buy":          _meta_buy(z.get("s", ""))
		"meta_pick":         _meta_pick(z.get("s", ""))
		"meta_start":        _start_run_from_meta()
		"safe_action":       _safehouse_action(z.get("s", ""), i)
		"safe_close":        _safehouse = {}; queue_redraw()
		"crawler_action":    _crawler_action(z.get("s", ""))
		"cast":              _cast_spell(z.get("s", ""))
		"event_fork":        _event_choose(i)
		"speak_pick":        _speak_pick(i)
		"char_unequip":      _unequip(z.get("s", ""))
		"pause_resume":      _pause_screen = false; _play("close"); queue_redraw()
		"pause_full":
			var wm2 := DisplayServer.window_get_mode()
			DisplayServer.window_set_mode(
				DisplayServer.WINDOW_MODE_WINDOWED if wm2 == DisplayServer.WINDOW_MODE_FULLSCREEN
				else DisplayServer.WINDOW_MODE_FULLSCREEN)
			_save_settings()
		"pause_quit":
			_pause_screen = false
			if floor != null:
				Save.write(floor, _run_seed)
			_title = true
			queue_redraw()
		"vol":
			if _sfx != null:
				var vbus: String = z.get("s", "Master")
				_sfx.set_volume(vbus, clampf(_sfx.get_volume(vbus) + float(i) * 4.0, -40.0, 0.0))
				_save_settings()
		"levelup_stat":      _spend_skill_point(z.get("s", ""))
		"levelup_close":     _levelup = {}; queue_redraw()

## Award XP from a non-combat source (descending, etc.) and animate the result,
## applying the same per-level rewards the combat path uses.
func _award_xp(amount: int) -> void:
	if amount <= 0 or sim == null:
		return
	var p := sim.player()
	var lv := p.gain_xp(amount)
	var evs: Array = [{"type": "xp", "amount": amount, "level": p.level,
		"xp": p.xp, "to_next": p.xp_to_next()}]
	for _i in lv:
		p.max_hp += 5
		p.hp = mini(p.max_hp, p.hp + 5)
		p.skill_points += 1
	if lv > 0:
		evs.append({"type": "level_up", "level": p.level, "levels": lv,
			"skill_points": p.skill_points, "max_hp": p.max_hp})
	_animate(evs)

## Level-up payoff: a banner + log, a guaranteed reward lootbox (DCC always pays
## out on a level), and the skill-point allocation modal opens.
func _on_level_up(e: Dictionary) -> void:
	var lv: int = int(e.get("level", sim.player().level))
	_add_floater(sim.player_id, "AWANS! POZIOM %d" % lv, COL_AMBER)
	_play("fanfare")
	_add_banner("POZIOM %d" % lv)
	_shake = maxf(_shake, 6.0)
	_log_push("Awans na poziom %d! +5 HP, +%d pkt umiejętności." % [lv, int(e.get("levels", 1))])
	_highlight("level", "Awans na poziom %d." % lv, 5 + lv)
	if lv >= 2:  _unlock_ach("aw_poziom_2")
	if lv >= 5:  _unlock_ach("aw_poziom_5")
	if lv >= 10: _unlock_ach("aw_poziom_10")
	if lv >= 15: _unlock_ach("aw_poziom_15")
	if lv >= 20: _unlock_ach("aw_poziom_20")
	_grant_level_box(lv)
	_levelup = {"open": true}
	queue_redraw()

## Hand the player a reward box for leveling: a couple of bonus materials plus a
## piece of gear, fatter on milestone levels (every 5th).
func _grant_level_box(lv: int) -> void:
	var milestone := lv % 5 == 0
	var box := GameBox.new("level", "Awans", Rarity.RARE if milestone else Rarity.UNCOMMON)
	for _i in (3 if milestone else 2):
		var mat: String = BOX_BONUS_MATS[_narr_rng.randi_range(0, BOX_BONUS_MATS.size() - 1)]
		box.contents.append({"type": "material", "key": mat, "qty": _narr_rng.randi_range(1, 3)})
	var tpl: Variant = _data_group("item_templates", "ITEM_TEMPLATES")
	if tpl is Dictionary and not (tpl as Dictionary).is_empty():
		var keys: Array = (tpl as Dictionary).keys()
		box.contents.append({"type": "item_key", "key": keys[_narr_rng.randi_range(0, keys.size() - 1)]})
	# A chance at a spell scroll — how a non-adept can stumble into the arcane.
	if Spells.can_learn(floor.player) and _narr_rng.randf() < (0.5 if milestone else 0.25):
		box.contents.append({"type": "spell_scroll", "key": ""})
	floor.boxes.append(box)
	_log_push("Awans nagradza skrzynką — odbierz ją na planszy.")

## Register every owned meta biome into the route pool (so it can appear at the
## stairs). Safe to call on both fresh and resumed runs.
func _register_loadout_biomes() -> void:
	Routes.clear_extra()
	for ent in MetaCatalog.active_effects():
		var eff: Dictionary = ent["effect"]
		if eff.has("biome"):
			Routes.register(ent["key"], eff["biome"])

## Build the on-board pet ally for the run from the first owned companion in the
## loadout (or null if none owned). Each companion fights with its own dice.
func _make_companion() -> CombatEntity:
	var key := ""
	for k in MetaCatalog.keys_of_kind("companion"):
		if MetaCatalog.is_owned(k):
			key = k; break
	if key == "":
		return null
	var defs := {
		"companion_papuga_anty_host":  {"name": "Papuga Konferansjera", "dice": "1d3", "hp": 14},
		"companion_suczka_recyklingu": {"name": "Suczka Recyklingu", "dice": "1d6", "hp": 24},
		"companion_kot_ministerstwa":  {"name": "Kot Ministerstwa", "dice": "1d4", "hp": 18},
		"companion_dron_sponsorski":   {"name": "Dron Sponsorski", "dice": "1d4", "hp": 16},
	}
	var d: Dictionary = defs.get(key, {"name": "Towarzysz", "dice": "1d4", "hp": 18})
	var c := CombatEntity.new(999, d["name"], int(d["hp"]), 12, ["ally", "companion"])
	c.faction = "ally"
	c.dmg_dice = d["dice"]
	c.to_hit = 3
	c.monster_key = key
	return c

## Bake the meta-progression loadout (chosen species + origin + all owned passives)
## into the fresh-run player + run state. The faithful "menu of choices" payoff.
func _apply_loadout() -> void:
	var p := floor.player
	var lo := MetaCatalog.loadout()
	p.species_key = lo["species"]
	p.origin_key = lo["origin"]
	# Magic aptitude of the chosen race: adepts start knowing spells + run more mana,
	# mundane races can't learn magic at all. Everyone else starts with none to learn.
	var sp_eff: Dictionary = MetaCatalog.def_of(lo["species"]).get("effect", {})
	p.magic_affinity = str(sp_eff.get("magic", ""))
	p.flags["known_spells"] = (sp_eff.get("start_spells", []) as Array).duplicate()
	var applied: Array = []
	for ent in MetaCatalog.active_effects():
		var eff: Dictionary = ent["effect"]
		if eff.is_empty():
			continue
		applied.append(ent["label"])
		for st in (eff.get("stats", {}) as Dictionary):
			p.stats[st] = int(p.stats.get(st, 0)) + int(eff["stats"][st])
		if eff.has("hp"):
			p.max_hp += int(eff["hp"]); p.hp = p.max_hp
		if eff.has("bonus_damage"):
			p.bonus_damage += int(eff["bonus_damage"])
		for t in (eff.get("tags", []) as Array):
			if t not in p.tags: p.tags.append(t)
		if eff.has("coating"):
			p.coating = str(eff["coating"].get("type", "")); p.coating_charges = int(eff["coating"].get("charges", 0))
		for mk in (eff.get("materials", {}) as Dictionary):
			floor.inv[mk] = int(floor.inv.get(mk, 0)) + int(eff["materials"][mk])
		for ik in (eff.get("items", []) as Array):
			var it := _item_from_template(str(ik))
			if it != null: floor.items.append(it)
		if eff.has("trait"):
			p.species_trait = str(eff["trait"])
		if eff.has("audience_min") and floor.audience != null:
			floor.audience.min_rating = int(eff["audience_min"])
		if eff.has("audience") and floor.audience != null:
			floor.audience.change(int(eff["audience"]), "loadout")
		if eff.has("sponsor_all") and floor.sponsors != null:
			for sk in floor.sponsors.all_keys():
				floor.sponsors.attention[sk] = floor.sponsors.get_attention(sk) + int(eff["sponsor_all"])
	if not applied.is_empty():
		_log_push("Ekwipunek sezonu: " + ", ".join(applied) + ".")

## Drop a sponsor's bounty hunter onto the board: a tough, already-aware enemy
## that scales with depth. It persists in the room and reads as a real threat.
func _spawn_hunter(hunter_name: String) -> void:
	if sim == null or floor == null:
		return
	var id := 700
	while sim.entities.has(id):
		id += 1
	var hp := 16 + floor.depth * 5
	var h := CombatEntity.new(id, hunter_name, hp, 13, ["monster", "hunter", "humanoid", "bounty"])
	h.faction = "enemy"
	h.aware = true
	h.monster_key = "hunter"
	h.dmg_dice = "1d6+%d" % (1 + floor.depth / 2)
	h.to_hit = 4
	var spot := _free_cell_for_spawn(sim.player().cell)
	if spot == Vector2i(-1, -1):
		return
	h.cell = spot
	sim.board.place(id, spot)
	sim.entities[id] = h
	floor.rooms[floor.current]["entities"][id] = h   # persists within the floor
	_attach_bodies()                                  # only the new (body-less) hunter
	var px := _cell_px(spot)
	_vpos[id] = px; _vtarget[id] = px
	_play("sting")
	_log_push("%s wpada na planszę — sponsor wysłał łowcę nagród!" % hunter_name)
	_add_banner("ŁOWCA SPONSORA")
	_shake = maxf(_shake, 7.0)
	queue_redraw()

## Place this floor's safehouse in the starting room (always reachable). The
## subtype is deterministic per depth, so a reloaded floor shows the same one.
func _spawn_safehouse() -> void:
	if sim == null or floor == null:
		return
	# Don't double-spawn if one is already on this room's board.
	for id in sim.entities:
		if sim.entities[id].faction == "safehouse":
			return
	var sub := Safehouse.subtype_for(floor.depth)
	var id := 800
	while sim.entities.has(id):
		id += 1
	var sh := CombatEntity.new(id, Safehouse.name_of(sub), 1, 10, ["safehouse"])
	sh.faction = "safehouse"
	sh.monster_key = sub                       # stash the subtype on the entity
	var spot := _free_cell_for_spawn(sim.player().cell)
	if spot == Vector2i(-1, -1):
		return
	sh.cell = spot
	sim.board.place(id, spot)
	sim.entities[id] = sh
	floor.rooms[floor.current]["entities"][id] = sh   # persists within the floor
	var px := _cell_px(spot)
	_vpos[id] = px; _vtarget[id] = px

## Maybe drop a rival crawler on the floor (deterministic per depth, ~55% chance).
func _maybe_spawn_crawler() -> void:
	if sim == null or floor == null:
		return
	for id in sim.entities:
		if sim.entities[id].faction == "crawler":
			return
	var rng := RandomNumberGenerator.new()
	rng.seed = _run_seed + floor.depth * 977
	if rng.randi_range(0, 99) >= 55:
		return
	var desc := Crawlers.make(floor.depth, rng)
	var id := 850
	while sim.entities.has(id):
		id += 1
	var cr := CombatEntity.new(id, desc["name"], 1, 12, ["crawler", "humanoid", "non_combat"])
	cr.faction = "crawler"
	cr.monster_key = desc.get("archetype", "")
	cr.flags["crawler"] = desc
	var spot := _free_cell_for_spawn(sim.player().cell)
	if spot == Vector2i(-1, -1):
		return
	cr.cell = spot
	sim.board.place(id, spot)
	sim.entities[id] = cr
	floor.rooms[floor.current]["entities"][id] = cr
	var px := _cell_px(spot)
	_vpos[id] = px; _vtarget[id] = px

## A walkable, unoccupied cell within a few tiles of `origin` (for dynamic spawns).
func _free_cell_for_spawn(origin: Vector2i) -> Vector2i:
	for r in [2, 3, 4]:
		for dy in range(-r, r + 1):
			for dx in range(-r, r + 1):
				if maxi(absi(dx), absi(dy)) != r:
					continue
				var c := origin + Vector2i(dx, dy)
				if sim.board.in_bounds(c) and not sim.board.is_wall(c) and sim.board.occupant_at(c) == -1:
					return c
	return Vector2i(-1, -1)

## Per-floor trait arming: "Pamiętający" lands its first blow of every floor.
func _arm_floor_traits() -> void:
	if floor != null and floor.player.species_trait == "first_strike":
		floor.player.next_attack_autohit = true

## Build a GameItem from an item_templates entry (shared by loadout + level boxes).
func _item_from_template(key: String) -> GameItem:
	var tpl: Variant = _data_group("item_templates", "ITEM_TEMPLATES")
	if not (tpl is Dictionary) or not (tpl as Dictionary).has(key):
		return null
	var t: Dictionary = tpl[key]
	var cat := GameItem.category_from_type(t.get("type", "tool"))
	var it := GameItem.new(t.get("fallback_name", key), cat, t.get("rarity", Rarity.COMMON))
	var tg: Variant = t.get("tags", [])
	it.tags = (tg if tg is Array else []).duplicate()
	it.origin = "meta"
	if cat == GameItem.CAT_ARMOR:
		it.effect = {"slot": it.armor_slot(), "ac_bonus": 1 + Rarity.order(it.rarity) / 2}
		it.charges = 0
	return it

## Spend one banked skill point raising `stat` by 1 (closes when the bank is dry).
func _spend_skill_point(stat: String) -> void:
	var p := sim.player()
	if p.skill_points <= 0 or stat == "":
		return
	p.skill_points -= 1
	p.stats[stat] = int(p.stats.get(stat, 0)) + 1
	if stat == "INT":
		p.int_xp += 5     # keep the tinkering track in step with raw INT
	_add_floater(sim.player_id, "+1 %s" % stat, COL_GAS)
	_log_push("Punkt umiejętności: %s teraz %d." % [stat, int(p.stats[stat])])
	_ach_bump("skill_spent", 1)
	if int(p.stats.get("STR", 0)) >= 8: _unlock_ach("cecha_str")
	if int(p.stats.get("DEX", 0)) >= 8: _unlock_ach("cecha_dex")
	if int(p.stats.get("INT", 0)) >= 8: _unlock_ach("cecha_int")
	if p.skill_points <= 0:
		_levelup = {}
	Save.write(floor, _run_seed)         # persist the new stats immediately
	queue_redraw()

## The enemy whose body we read out + aim at: the nearest aware living enemy,
## else the nearest living enemy.
func _focused_enemy() -> CombatEntity:
	var p := sim.player()
	var best: CombatEntity = null
	var best_d := 1 << 30
	for id in sim.entities:
		var e: CombatEntity = sim.entities[id]
		if e.faction != "enemy" or not e.is_alive():
			continue
		var d: int = maxi(absi(e.cell.x - p.cell.x), absi(e.cell.y - p.cell.y))
		if e.aware:
			d -= 1000   # strongly prefer aware enemies
		if d < best_d:
			best_d = d; best = e
	return best

## Cycle aim through the focused enemy's intact parts, then back to "" (body).
func _cycle_aim() -> void:
	var e := _focused_enemy()
	if e == null or e.body == null:
		_aim_zone = ""; sim.aim_zone = ""; queue_redraw(); return
	var choices: Array = [""]
	for pkey in e.body.order:
		if not e.body.part(pkey)["severed"]:
			choices.append(pkey)
	var i := choices.find(_aim_zone)
	_aim_zone = choices[(i + 1) % choices.size()]
	sim.aim_zone = _aim_zone
	if _aim_zone != "":
		var lbl: String = e.body.part(_aim_zone)["label_pl"]
		_log_push("Bierzesz na cel: %s." % lbl)
	else:
		_log_push("Celujesz w korpus (bez wyboru strefy).")
	queue_redraw()

func _handle_craft_input(kc: int) -> void:
	if kc == KEY_ESCAPE:
		_craft_open = false; queue_redraw(); return
	if kc == KEY_TAB:
		_craft_mode = "items" if _craft_mode == "bench" else "bench"
		queue_redraw(); return
	if _craft_mode == "bench":
		if kc == KEY_BACKSPACE:
			_bench_remove_at(_bench_slots.size() - 1); return
		if kc == KEY_ENTER or kc == KEY_KP_ENTER:
			_bench_attempt_now(); return
		var idx: int = kc - KEY_1
		if idx >= 0 and idx <= 8:
			_bench_add_material(idx); return
	elif _craft_mode == "items":
		if kc == KEY_ENTER or kc == KEY_KP_ENTER:
			if not floor.boxes.is_empty():
				_open_box(0)
			queue_redraw(); return
		var idx: int = kc - KEY_1
		if idx >= 0:
			if idx < floor.items.size():
				_item_use(idx)
			elif idx - floor.items.size() < floor.boxes.size():
				_open_box(idx - floor.items.size()); queue_redraw()

# Shared bench/item actions — used by BOTH keyboard and mouse so they never drift.
func _bench_add_material(idx: int) -> void:
	if _bench_slots.size() >= 6:
		return
	var mat_keys := sim.materials.keys()
	if idx >= 0 and idx < mat_keys.size():
		_bench_slots.append(mat_keys[idx])
		_bench_preview = Crafting.preview(_bench_slots, floor.discovered_recipes)
	queue_redraw()

func _bench_remove_at(i: int) -> void:
	if i >= 0 and i < _bench_slots.size():
		_bench_slots.remove_at(i)
		_bench_preview = Crafting.preview(_bench_slots, floor.discovered_recipes) if not _bench_slots.is_empty() else {}
	queue_redraw()

func _bench_attempt_now() -> void:
	if _bench_slots.is_empty():
		return
	var used_rag := "szmata" in _bench_slots
	var evs := sim.bench_attempt(_bench_slots)
	_animate(evs)
	# Serious results from the cheapest junk: a success that ran on a rag.
	if used_rag:
		for e in evs:
			if e.get("type") == "craft_attempt" and str(e.get("outcome", "")) in ["sukces", "krytyk"]:
				_unlock_ach("smiec_wartosciowy")
	for b in floor.sponsors.drain_boxes():
		floor.boxes.append(b)
		_log_push("Sponsor wysłał paczkę: " + b.display_name() + "!")
	_bench_slots.clear()
	_bench_preview = {}
	_craft_open = false
	queue_redraw()

func _item_use(idx: int) -> void:
	if idx >= 0 and idx < floor.items.size():
		_animate(sim.player_use_item(idx))
		_craft_open = false
	queue_redraw()

func _set_aim(pkey: String) -> void:
	_aim_zone = pkey
	sim.aim_zone = pkey
	var e := _focused_enemy()
	if e != null and e.body != null and e.body.parts.has(pkey):
		_log_push("Bierzesz na cel: %s." % e.body.part(pkey)["label_pl"])

## Click/key during the lootbox reveal: skip the spin, then collect the loot.
func _box_anim_advance() -> void:
	if _box_anim.is_empty():
		return
	if _box_anim["phase"] != "done":
		_box_anim["phase"] = "done"; _box_anim["t"] = 0.0
		_box_anim["reveal_n"] = (_box_anim["entries"] as Array).size()
	else:
		var box: GameBox = _box_anim["box"]
		var entries: Array = _box_anim["entries"]
		_box_anim = {}
		_commit_box_entries(box, entries)
	queue_redraw()

# ── Achievements ──────────────────────────────────────────────────────────────

## Try to unlock an achievement; on a NEW unlock, pop a toast + log + floater.
## Push one earned achievement as a VS-style toast (tier-colored, points), with a
## golden screen burst for the rare ones.
func _push_ach_toast(d: Dictionary) -> void:
	var tier := str(d.get("tier", "bronze"))
	_play("chime")
	_toasts.append({"name": d.get("name", "?"), "desc": d.get("desc", ""),
		"category": d.get("category", "general"), "tier": tier,
		"points": int(Achievements.TIER_POINTS.get(tier, 1)), "t": 0.0, "ttl": 5.2})
	_log_push("OSIĄGNIĘCIE: " + d.get("name", "?") + "!")
	if sim != null:
		_add_floater(sim.player_id, "★ " + d.get("name", "?"), _ach_tier_color(tier))
	_shake = maxf(_shake, 4.0 if (tier == "gold" or tier == "platinum") else 2.0)
	if tier == "gold" or tier == "platinum":
		_ach_flash = maxf(_ach_flash, 0.7)

func _ach_tier_color(tier: String) -> Color:
	return ACH_TIER_COL.get(tier, COL_BRIGHT)

## Buy a meta unlock with prestige points; a confirming log line + a small flash.
func _meta_buy(key: String) -> void:
	if key == "":
		return
	if MetaCatalog.try_purchase(key):
		_log_push("Odblokowano: %s." % MetaCatalog.def_of(key).get("label", key))
		_ach_flash = maxf(_ach_flash, 0.5)
	queue_redraw()

## Select an owned species/origin for the next run.
func _meta_pick(key: String) -> void:
	if MetaCatalog.kind_of(key) == "species":
		MetaCatalog.set_species(key)
	elif MetaCatalog.kind_of(key) == "origin":
		MetaCatalog.set_origin(key)
	queue_redraw()

## Start a fresh run from the loadout screen (abandons any in-progress save).
func _start_run_from_meta() -> void:
	_meta_screen = false
	Save.clear()
	_build()

## Open the achievements gallery. Looking at your own trophies is, itself, an
## achievement (a hidden one).
func _open_ach_screen() -> void:
	_ach_screen = true
	_ach_scroll = 0.0
	_unlock_ach("narcyz")
	queue_redraw()

func _unlock_ach(key: String) -> void:
	var d := Achievements.unlock(key)
	if d.is_empty():
		return
	_push_ach_toast(d)
	_ach_milestones()

## Toast a batch of just-unlocked defs (e.g. from a lifetime-counter bump).
func _ach_unlock_defs(defs: Array) -> void:
	for d in defs:
		_push_ach_toast(d)
		_ach_milestones()

## Add to a lifetime counter; toast anything it auto-unlocks.
func _ach_bump(stat_key: String, n: int = 1) -> void:
	_ach_unlock_defs(Achievements.bump(stat_key, n))

## Collector milestones: a medal for the first, then 10/25/50, then 100%.
func _ach_milestones() -> void:
	var c := Achievements.count_unlocked()
	_ach_meta_if(c >= 1, "first_ach")
	_ach_meta_if(c >= 10, "collector_10")
	_ach_meta_if(c >= 25, "collector_25")
	_ach_meta_if(c >= 50, "collector_50")
	_ach_meta_if(Achievements.count_unlocked() >= Achievements.total() - 1, "platinum_all")

func _ach_meta_if(cond: bool, key: String) -> void:
	if cond and not Achievements.is_unlocked(key):
		var d := Achievements.unlock(key)
		if not d.is_empty():
			_push_ach_toast(d)   # not _unlock_ach: avoid re-entering the milestone scan

func _ach_cat_color(cat: String) -> Color:
	match cat:
		"combat":      return COL_RED
		"salvage", "harvest": return COL_AMBER
		"craft":       return COL_CYAN
		"loot":        return COL_PURPLE
		"audience", "sponsor": return COL_GAS
		"floor", "exploration": return COL_GREEN
	return COL_BRIGHT

## Scan an event batch + current run state for achievement conditions.
func _ach_scan(evs: Array) -> void:
	var p := floor.player
	var sys_electric := false
	var enemy_died := false
	for e in evs:
		match e.get("type"):
			"salvage":
				if p.run_corpses_salvaged >= 1: _unlock_ach("wszystko_jest_surowcem")
				if p.run_corpses_salvaged >= 5: _unlock_ach("recykling_agresywny")
				if p.run_corpses_salvaged >= 10: _unlock_ach("ekonomia_przetrwania")
				var g: Dictionary = e.get("gained", {})
				if g.has("drewno"): _unlock_ach("meble_tez_krwawia")
				if g.has("przewód") or g.has("złom"): _unlock_ach("technicznie_to_loot")
				# the battlefield as a parts bin: salvaging after you've made corpses
				if p.run_kills >= 1: _unlock_ach("rozbiorka_zwlok")
				# tech strip-mining: 5 electronics-bearing wrecks in one run
				if g.has("przewód") or g.has("bateria"):
					p.flags["run_tech_salv"] = int(p.flags.get("run_tech_salv", 0)) + 1
					if int(p.flags["run_tech_salv"]) >= 5: _unlock_ach("kompletny_hacker")
			"craft_attempt":
				var oc: String = e.get("outcome", "")
				if oc == "sukces" or oc == "krytyk": _unlock_ach("rzemieslnik_z_paniki")
				if oc == "krytyk": _unlock_ach("dzielo_mistrzowskie")
				if oc == "backfire": _unlock_ach("inzynieria_odwagi")
				if oc == "czesciowy": _unlock_ach("obrzydliwe_ale_dziala")
				if oc == "sukces" or oc == "krytyk" or oc == "czesciowy":
					p.flags["run_crafts"] = int(p.flags.get("run_crafts", 0)) + 1
					if int(p.flags["run_crafts"]) >= 10: _unlock_ach("zlota_raczka_lochu")
			"trap_armed":
				_unlock_ach("pulapka_z_niczego")
			"damage":
				# a brutal hit landed on a public shot (the crowd is HOT) = the finisher cam
				var dv = sim.entities.get(int(e.get("target", -1)))
				if dv != null and dv.faction == "enemy" and int(e.get("amount", 0)) >= 12 \
						and floor.audience != null and floor.audience.band() in ["hot", "viral"]:
					_unlock_ach("finiszer_kanalu")
			"death":
				if p.run_kills >= 1: _unlock_ach("pierwsza_krew")
				if p.run_kills >= 50: _unlock_ach("rzeznia_kontrolowana")
				var t = sim.entities.get(e.get("target"))
				if t != null and t.faction == "enemy":
					enemy_died = true
					if "boss" in t.tags: _unlock_ach("boss_padl_pierwszy")
					elif "miniboss" in t.tags: _unlock_ach("klepacz_minibossow")
			"systemic":
				if e.get("element") == "electric": sys_electric = true
				# a hazard bit YOU: that clip plays forever (and marks the floor dirty)
				if int(e.get("target", -1)) == sim.player_id:
					p.flags["floor_hazard"] = true
					_unlock_ach("samo_sie_rozstawilo")
			"audience_band_crossed":
				if e.get("to_band") == "hot": _unlock_ach("widownia_gorzej_bije")
				if e.get("to_band") == "viral": _unlock_ach("kult_jednostki")
			"sponsor_gift":
				_unlock_ach("pakiet_z_sufitu")
	if sys_electric and enemy_died:
		_env_kills += 1
		_unlock_ach("czystka_srodowiska")
	if not floor.discovered_recipes.is_empty():
		_unlock_ach("przepis_jaki_przepis")
	# loot in your pocket
	var rarities := {}
	for it in floor.items:
		rarities[(it as GameItem).rarity] = true
		if (it as GameItem).rarity == Rarity.LEGENDARY: _unlock_ach("widzialem_legende")
		elif (it as GameItem).rarity == Rarity.EPIC: _unlock_ach("niezwykly_zbieracz")
		if (it as GameItem).category == GameItem.CAT_MEDICAL: _unlock_ach("apteka_w_plecaku")
	for slot in p.equipment:
		if p.equipment[slot] != null:
			rarities[(p.equipment[slot] as GameItem).rarity] = true
	if rarities.size() >= Rarity.ALL.size():
		_unlock_ach("cala_paleta")
	# the last stand: down to exactly 1 HP and still breathing
	if p.is_alive() and p.hp == 1:
		_unlock_ach("anty_host_warknal")
	# a sponsor really likes you
	if floor.sponsors != null:
		for k in floor.sponsors.all_keys():
			if floor.sponsors.get_attention(k) >= 10:
				_unlock_ach("markowy_uczestnik"); break

func _ach_descend(depth: int) -> void:
	if depth >= 2: _unlock_ach("dno_jeszcze_dalej")
	if depth >= 5: _unlock_ach("piaty_set")
	# A 6-floor season can't reach depth 10 — "Dziesiąte piętro" is a CAREER tally.
	_ach_bump("floors", 1)
	if Achievements.stat("floors") >= 10: _unlock_ach("dziesiate_pietro")

## Achievements judged when you COMPLETE a floor (called just before the descent
## swaps the floor out). `done_biome` is the biome of the floor being left.
func _ach_floor_complete(done_biome: String) -> void:
	var p := floor.player
	var depth := floor.depth
	match done_biome:
		"okopy_frontowe":   _unlock_ach("okopowiec")
		"zoo_korporacyjne": _unlock_ach("zoofobia_skonczona")
		"muzeum_spektakli": _unlock_ach("archiwista")
		"bar_skurczybyk":   _unlock_ach("karaoke_killer")
	# globtroter: five distinct biomes toured in one season
	if done_biome != "":
		var seen: Array = p.flags.get("biomes_seen", [])
		if done_biome not in seen:
			seen.append(done_biome)
			p.flags["biomes_seen"] = seen
		if seen.size() >= 5: _unlock_ach("globtroter")
	if depth >= 2:
		# danced around every hazard on the floor
		if not p.flags.get("floor_hazard", false): _unlock_ach("taneczny_krok")
		# a full wallet and iron discipline: spent nothing while holding 20+ scrap
		if int(p.flags.get("floor_zlom_spent", 0)) == 0 and _zlom() >= 20:
			_unlock_ach("nadzwyczajne_oszczednosci")
		# no armor, all scars
		var bare := true
		for slot in p.equipment:
			if p.equipment[slot] != null: bare = false
		if bare: _unlock_ach("bez_zbroi_bez_smutku")
	# every kill stripped for parts
	if p.run_kills >= 3 and p.run_corpses_salvaged >= p.run_kills:
		_unlock_ach("kazdy_ma_imie")
	# per-floor trackers reset for the next floor
	p.flags["floor_hazard"] = false
	p.flags["floor_zlom_spent"] = 0

## Event-driven achievements + lifetime counters from a batch of sim events.
## (Kept separate from _ach_scan so the wiring stays legible.)
func _ach_events(evs: Array) -> void:
	if sim == null:
		return
	var sneak: Dictionary = {}
	for e in evs:
		if e.get("type") == "attack" and e.get("target_unaware", false):
			sneak[int(e.get("target", -1))] = true
	for e in evs:
		match e.get("type"):
			"salvage":
				if _narr_rng.randf() < 0.18:          # dismantling sometimes turns up a clue
					_learn_knowledge(Knowledge.random_clue(_narr_rng))
			"damage":
				var v = sim.entities.get(int(e.get("target", -1)))
				if v != null and v.faction == "enemy":
					var amt := int(e.get("amount", 0))
					_ach_bump("damage", amt)
					if amt >= 30:
						_unlock_ach("overkill")
					if amt >= 14:
						_highlight("big_hit", "Potężny cios — %d obrażeń." % amt, amt)
			"death":
				var d = sim.entities.get(int(e.get("target", -1)))
				if d != null and d.faction == "enemy":
					_ach_bump("kills", 1)
					if d.tags.has("boss"):
						_ach_bump("bosses", 1)
						_highlight("boss", "BOSS PADŁ: %s!" % d.name_pl, 100)
					else:
						_highlight("kill", "Pokonano: %s." % d.name_pl, 10 + d.max_hp)
					if sneak.has(int(e.get("target", -1))):
						_unlock_ach("sneak_kill")
						_highlight("sneak", "Cichy montaż: %s nie zdążył się obudzić." % d.name_pl, 25)
			"maim":
				if e.get("severed", false): _unlock_ach("sever")
			"body_hit":
				if e.get("severed", false): _unlock_ach("sever")
			"armor_equipped":
				_unlock_ach("gear_first")
				var eq: Dictionary = sim.player().equipment
				if eq.has("head") and eq.has("body") and eq.has("legs"):
					_unlock_ach("gear_full")
				if sim.player().ac + sim.player().armor_bonus() >= 18:
					_unlock_ach("gear_ac")
			"weapon_upgrade":
				if sim.player().bonus_damage >= 6: _unlock_ach("gear_dmg")
			"craft_attempt":
				var oc := str(e.get("outcome", ""))
				if oc == "krytyk" or oc == "sukces" or oc == "czesciowy":
					_ach_bump("crafts", 1)
				if oc == "krytyk": _unlock_ach("craft_crit")
				if oc == "backfire": _unlock_ach("backfire")
			"audience_band_crossed":
				if e.get("to_band", "") == "viral": _unlock_ach("viral")
	# lifetime recipe discoveries
	var rc := floor.discovered_recipes.size()
	if rc > _ach_recipes_seen:
		_ach_bump("recipes", rc - _ach_recipes_seen)
		_ach_recipes_seen = rc
	# three sponsors all maxed out on you
	if floor.sponsors != null:
		var loyal := 0
		for k in floor.sponsors.all_keys():
			if floor.sponsors.get_attention(k) >= 10: loyal += 1
		if loyal >= 3: _unlock_ach("sponsor_loyal")

## Advance this floor's tracked objective from a batch of events (+ scrap is
## state-based: it checks your current złom count).
func _objective_track(evs: Array) -> void:
	if floor == null or floor.objective.is_empty() or bool(floor.objective.get("done", false)):
		return
	var k: String = floor.objective.get("key", "")
	if k == "scrap":
		var z := int(sim.materials.get("złom", 0))
		if z > int(floor.objective["progress"]):
			floor.objective["progress"] = z
			if z >= int(floor.objective["target"]):
				_complete_objective()
		return
	for e in evs:
		match e.get("type"):
			"salvage":
				if k == "salvage": _objective_event(1)
			"death":
				var v = sim.entities.get(int(e.get("target", -1)))
				if k == "kill" and v != null and v.faction == "enemy": _objective_event(1)
			"craft_attempt":
				var oc := str(e.get("outcome", ""))
				if k == "craft" and (oc == "krytyk" or oc == "sukces" or oc == "czesciowy"):
					_objective_event(1)

## Advance the current objective by `amount`; complete it when the target is hit.
func _objective_event(amount: int) -> void:
	if floor.objective.is_empty() or bool(floor.objective.get("done", false)):
		return
	floor.objective["progress"] = int(floor.objective["progress"]) + amount
	if int(floor.objective["progress"]) >= int(floor.objective["target"]):
		_complete_objective()

## Pay out the objective: audience + XP, a toast-ish floater, and a log line.
func _complete_objective() -> void:
	var obj := floor.objective
	obj["done"] = true
	obj["progress"] = int(obj["target"])
	if floor.audience != null:
		floor.audience.change(int(obj.get("reward_audience", 0)), "objective")
	_award_xp(int(obj.get("reward_xp", 0)))
	_add_floater(sim.player_id, "ZADANIE ✓", COL_GREEN)
	_add_banner("ZADANIE WYKONANE")
	_shake = maxf(_shake, 4.0)
	_log_push("Zadanie piętra wykonane! +%d widowni, +%d XP." % [
		int(obj.get("reward_audience", 0)), int(obj.get("reward_xp", 0))])
	queue_redraw()

func _ach_run_end(victory: bool) -> void:
	if victory: _unlock_ach("finalista_sezonu")
	if floor.player.run_kills == 0: _unlock_ach("brak_zwlok_brak_problemu")
	if floor.audience != null and floor.audience.peak >= 80: _unlock_ach("kult_jednostki")
	# Godot-only finale + infamy achievements
	if victory:
		_unlock_ach("win")
		if floor.player.run_kills == 0: _unlock_ach("win_pacifist")
		if floor.player.level < 8: _unlock_ach("win_lowlevel")
	else:
		_ach_bump("deaths", 1)
		_unlock_ach("die_1")
		if floor.depth <= 1: _unlock_ach("die_floor1")
		if not floor.boxes.is_empty(): _unlock_ach("die_rich")
		# pożarty przez statystę: a weak enemy was alive next to you when you fell
		for id in sim.entities:
			var en: CombatEntity = sim.entities[id]
			if en.faction == "enemy" and en.is_alive() and en.max_hp <= 16 \
					and sim.board.is_adjacent(en.cell, floor.player.cell):
				_unlock_ach("die_rat"); break
	queue_redraw()

## Resolve a box's contents into reveal entries WITHOUT adding them to the run
## (so the opening animation can show them, then commit on the payoff beat).
func _resolve_box(box: GameBox) -> Array:
	var out: Array = []
	for entry in box.contents:
		match entry.get("type"):
			"item_key":
				var templates: Variant = _data_group("item_templates", "ITEM_TEMPLATES")
				if templates is Dictionary and templates.has(entry["key"]):
					var t: Dictionary = templates[entry["key"]]
					var it := GameItem.new(t.get("fallback_name", entry["key"]),
						GameItem.category_from_type(t.get("type", "tool")), t.get("rarity", Rarity.COMMON))
					var tg: Variant = t.get("tags", [])
					it.tags = (tg if tg is Array else []).duplicate()
					it.origin = box.source
					if it.category == GameItem.CAT_ARMOR:
						it.effect = {"slot": it.armor_slot(), "ac_bonus": 1 + Rarity.order(it.rarity) / 2}
						it.charges = 0
					elif it.category == GameItem.CAT_WEAPON and it.effect.is_empty():
						it.effect = {"damage_bonus": 1 + Rarity.order(it.rarity) / 2}
						it.charges = 1   # applied once as a permanent +dmg upgrade
					out.append({"type": "item", "item": it, "label": it.display_name(),
						"color": it.rarity_color()})
			"material":
				var mat: String = entry.get("key", "")
				var qty: int = int(entry.get("qty", 1))
				if mat != "":
					out.append({"type": "material", "key": mat, "qty": qty,
						"label": "%s x%d" % [mat, qty], "color": COL_AMBER})
			"spell_scroll":
				var sc := _spell_scroll_item(entry.get("key", ""))
				out.append({"type": "item", "item": sc, "label": sc.display_name(), "color": COL_PURPLE})
	return out

## Build a spell-scroll item (teaches a spell on use). Blank key = a random spell.
func _spell_scroll_item(spell_key: String = "") -> GameItem:
	var nm := "Zwój zaklęć"
	if spell_key != "":
		nm = "Zwój: %s" % Spells.def_of(spell_key).get("name", spell_key)
	var it := GameItem.new(nm, GameItem.CAT_SPELL, Rarity.UNCOMMON)
	it.effect = {"spell": spell_key}
	it.charges = 1
	it.origin = "scroll"
	return it

## Add resolved entries to the run, drop the box, and log the reveal flavor.
func _commit_box_entries(box: GameBox, entries: Array) -> void:
	var spawned: Array = []
	for e in entries:
		if e["type"] == "item":
			floor.items.append(e["item"])
			spawned.append(e["item"].name_pl)
			if (e["item"] as GameItem).rarity == Rarity.LEGENDARY:
				_unlock_ach("legend_loot")
		else:
			sim.materials[e["key"]] = int(sim.materials.get(e["key"], 0)) + int(e["qty"])
			spawned.append(e["label"])
	box.opened = true
	floor.boxes.erase(box)
	_ach_bump("boxes", 1)
	if not floor.objective.is_empty() and floor.objective.get("key", "") == "box":
		_objective_event(1)
	var contents_line := "  → " + (", ".join(spawned) if not spawned.is_empty() else "(pusto)")
	for line in box.reveal_lines(contents_line):
		_log_push(line)

## Kick off the animated, Vampire-Survivors-style opening of box `idx`.
func _open_box(idx: int) -> void:
	if idx < 0 or idx >= floor.boxes.size():
		return
	var box: GameBox = floor.boxes[idx]
	_craft_open = false
	var entries := _resolve_box(box)

	# ── Lucky multiplier: like Vampire Survivors' 1/3/5 chests, roll for bonus
	# pieces. Better box tiers roll fatter. Tier 3/5 add extra scrap + more flash.
	var ro := Rarity.order(box.rarity)             # 0..4
	var roll := _narr_rng.randf()
	var tier := 1
	if roll < 0.10 + ro * 0.05: tier = 5
	elif roll < 0.34 + ro * 0.07: tier = 3
	if tier >= 5: _unlock_ach("jackpot")
	var bonus := tier - 1                           # 0 / 2 / 4 extra pieces
	for _i in bonus:
		var mat: String = BOX_BONUS_MATS[_narr_rng.randi_range(0, BOX_BONUS_MATS.size() - 1)]
		var qty := _narr_rng.randi_range(1, 3)
		entries.append({"type": "material", "key": mat, "qty": qty,
			"label": "%s x%d  (bonus)" % [mat, qty], "color": COL_GREEN})

	# Build a slot reel of rarity-colored tiles that lands on the box's tier, with a
	# near-miss tease: a higher tier sits just past the marker so the reel "almost"
	# hits it before settling.
	var n := 26
	var strip: Array = []
	for i in n:
		strip.append(Rarity.ALL[mini(_narr_rng.randi_range(0, 5), Rarity.ALL.size() - 1)])
	var land := n - 4
	strip[land] = box.rarity                        # the SNAP target
	if land + 1 < n:
		strip[land + 1] = Rarity.ALL[mini(ro + 1, Rarity.ALL.size() - 1)]   # the tease
	_box_anim = {
		"box": box, "entries": entries, "strip": strip, "land": land, "tier": tier,
		"t": 0.0, "phase": "spin", "reveal_n": 0, "committed": false,
	}
	_shake = maxf(_shake, 1.0)
	queue_redraw()

# ── Public action drivers ─────────────────────────────────────────────────────

func handle_dir(dir: Vector2i) -> void:
	if _done: return
	floor.player.flags["consec_waits"] = 0
	_animate(sim.player_move(dir))
	_advance_floor_turn()
	_check_transition()

func handle_shove(dir: Vector2i) -> void:
	floor.player.flags["consec_waits"] = 0
	_play("shove")
	_animate(sim.player_shove(dir))
	_advance_floor_turn()

func handle_wait() -> void:
	# Stalling on camera: five turtled rounds in a live fight forces an ad break.
	var cw := int(floor.player.flags.get("consec_waits", 0)) + 1
	floor.player.flags["consec_waits"] = cw
	var fight := false
	for e in sim.enemies_alive():
		if e.aware: fight = true
	if fight and cw >= 5:
		_unlock_ach("reklama_przerywa_walke")
	_animate(sim.player_wait())
	_advance_floor_turn()

func handle_interact() -> void:
	floor.player.flags["consec_waits"] = 0
	_animate(sim.player_interact())
	_advance_floor_turn()

## Build the end-of-run results, record meta unlocks, and switch to the screen.
func _end_run(victory: bool) -> void:
	if not _summary.is_empty():
		return
	_ach_run_end(victory)
	_summary = RunSummary.build(floor, victory, _narr_rng)
	_summary["new_unlocks"] = Meta.record_run(_summary)
	_summary_lines = RunSummary.render_lines(_summary)
	Save.clear()   # the run is over; next launch starts fresh
	_done = true
	# Input lockout: you were probably mid-click when you died — without this the
	# next click instantly restarted the run and you never saw the death recap.
	_summary_lock = 1.2
	queue_redraw()

func _advance_floor_turn() -> void:
	if floor == null: return
	# Death ends the run -> results screen.
	if sim.over and sim.outcome == "lose" and _summary.is_empty():
		_end_run(false)
		return
	var new_boxes := floor.advance_turn()
	for b in new_boxes:
		_log_push("Sponsor wysłał paczkę: " + b.display_name() + "!")
		_add_floater(sim.player_id, "PACZKA!", COL_AMBER)
	# Biome gimmick: an occasional flavor quirk with a tiny mechanical nudge (not
	# right at the start of a floor — let the player settle in first).
	if floor.turn >= 8 and floor.turn % 8 == 0:
		_animate(BiomeGimmicks.tick(floor, sim, _narr_rng))
	# Mid-floor decision beat: at most once per floor, and only well INTO a floor
	# you've actually been playing (not on floor 1, not turn 5, and only after
	# you've done something the show could react to). The beat must also fit the
	# current audience — no sponsor interview for a nobody.
	var engaged: bool = (floor.player.run_kills + floor.player.run_corpses_salvaged) >= 2
	if _event.is_empty() and floor.depth >= 2 and floor.turn >= 14 and engaged \
			and int(floor.player.flags.get("event_floor", -1)) != floor.depth \
			and _narr_rng.randf() < 0.35:
		floor.player.flags["event_floor"] = floor.depth   # one attempt per floor regardless
		var aud := floor.audience.rating if floor.audience != null else 0
		var beat := MidFloorEvents.pick(_narr_rng, aud)
		if not beat.is_empty():
			_event = beat
			_log_push("Przerwa w akcji: %s" % _event.get("intro", ""))
			queue_redraw()
	# The Syndicate may now read your style and offer a class.
	if _class_offer.is_empty():
		var offer := floor.check_class_offer()
		if not offer.is_empty():
			_class_offer = offer
			_narrate("class_offer")
			var tt := Classes.top_two(floor.player)
			_log_push("Syndykat patrzy na twój styl (%s) i ma propozycję." %
				Classes.affinity_label(tt[0]))
			queue_redraw()

func _accept_class(idx: int) -> void:
	if idx < 0 or idx >= _class_offer.size():
		return
	var key: String = _class_offer[idx]
	Classes.assign_class(floor.player, key)
	_class_offer = []
	_log_push("Zostajesz klasą: %s. %s" % [Classes.name_of(key),
		ClassFeatures.active_name(key) + " — [F]."])
	_add_floater(sim.player_id, Classes.name_of(key).to_upper(), COL_AMBER)
	_ach_bump("classes", 1)
	queue_redraw()

func _use_class_active() -> void:
	if floor == null or floor.player.class_key == "":
		return
	_animate(sim.use_class_active(floor.depth))
	_advance_floor_turn()
	_check_transition()

## Cast a spell from the book at the nearest enemy; closes the book + takes a turn.
func _cast_spell(key: String) -> void:
	if floor == null:
		return
	_spellbook = false
	_animate(sim.cast_spell(key))
	_check_transition()
	queue_redraw()

## ── Freeform persuasion: say a line to a mind; the System judges + rolls CHA ─
## The nearest enemy/crawler/npc within earshot, or null.
func _nearest_mind() -> CombatEntity:
	if sim == null: return null
	var p := sim.player()
	var best: CombatEntity = null
	var bd := 1 << 30
	for id in sim.entities:
		var e: CombatEntity = sim.entities[id]
		if not e.is_alive(): continue
		if e.faction != "enemy" and e.faction != "crawler" and e.faction != "npc": continue
		var d: int = maxi(absi(e.cell.x - p.cell.x), absi(e.cell.y - p.cell.y))
		if d <= 6 and d < bd:
			bd = d; best = e
	return best

func _open_speak() -> void:
	if floor == null: return
	var t := _nearest_mind()
	if t == null:
		_log_push("Nie ma kogo przekonywać — nikt nie jest w zasięgu głosu.")
		queue_redraw(); return
	_speak = {"target_id": t.id, "text": "", "mode": "type"}
	_play("speak")
	queue_redraw()

func _speak_submit() -> void:
	var txt := str(_speak.get("text", "")).strip_edges()
	if txt == "":
		_speak["mode"] = "fallback"
		_speak["options"] = Memetics.fallback_lines(_narr_rng)
		queue_redraw(); return
	var intent := Memetics.classify(txt)
	if intent == "":
		# Unreadable nonsense — a pure gamble (peak DCC). Random intent, harder DC.
		var keys := Memetics.INTENTS.keys()
		_resolve_speak(keys[_narr_rng.randi_range(0, keys.size() - 1)], txt, true)
	else:
		_resolve_speak(intent, txt, false)

func _speak_pick(i: int) -> void:
	var opts: Array = _speak.get("options", [])
	if i < 0 or i >= opts.size(): return
	_resolve_speak(opts[i]["intent"], opts[i]["text"], false)

## DC = base + how implausible the claim is vs reality. Bosses / mindless = immune.
func _persuasion_dc(intent: String, t: CombatEntity) -> int:
	if t.tags.has("boss"): return 999
	if Memetics.kind_of(intent) == "convert":
		for mind in ["construct", "robot", "mechanical", "metal", "undead", "machine", "drone"]:
			if t.tags.has(mind): return 999
	var dc := Memetics.base_dc(intent)
	if t.aware: dc += 3
	if t.max_hp > 0: dc += int(4.0 * float(t.hp) / float(t.max_hp))
	dc += int(t.max_hp / 14)
	return dc

func _resolve_speak(intent: String, line: String, wild: bool) -> void:
	var t = sim.entities.get(int(_speak.get("target_id", -1)))
	_speak = {}
	if t == null:
		queue_redraw(); return
	var p := sim.player()
	var kind := Memetics.kind_of(intent)
	_log_push("Mówisz do %s: %s" % [t.name_pl, line])
	var dc := _persuasion_dc(intent, t)
	if dc >= 900:
		_log_push("%s nie ma umysłu, który dałoby się przekonać." % t.name_pl)
		_add_floater(t.id, "ODPORNY", COL_DIM)
		_advance_floor_turn(); queue_redraw(); return
	if wild: dc += 4
	var roll := _narr_rng.randi_range(1, 20) + p.stat_mod("CHA")
	var crit := roll >= dc + 8 or (dc >= 16 and roll >= dc)
	var ok := roll >= dc
	var partial := roll >= dc - 4
	var fumble := roll <= dc - 8
	if ok:
		_persuade_apply(kind, t, crit, false)
	elif partial:
		_persuade_apply(kind, t, false, true)
	else:
		t.aware = true
		if fumble:
			_log_push("%s przejrzał cię na wylot — i jest wściekły." % t.name_pl)
			_add_floater(t.id, "WPADKA", COL_RED)
			for e in sim.enemies_alive():
				if maxi(absi(e.cell.x - t.cell.x), absi(e.cell.y - t.cell.y)) <= 3:
					e.aware = true
		else:
			_log_push("%s nie kupił tego." % t.name_pl)
			_add_floater(t.id, "NIE KUPUJE", COL_DIM)
	_advance_floor_turn()
	queue_redraw()

## Apply the social outcome. `partial` = a weaker, shorter version.
func _persuade_apply(kind: String, t: CombatEntity, crit: bool, partial: bool) -> void:
	var dur := (1 if partial else (5 if crit else 3))
	match kind:
		"charm":
			t.add_status("charmed", dur); t.flags.erase("incited")
			_log_push("%s ci uwierzył — przestaje cię atakować." % t.name_pl)
			_add_floater(t.id, "PRZEKONANY", COL_GAS)
		"incite":
			t.add_status("charmed", dur); t.flags["incited"] = true
			_log_push("%s zwraca się przeciw swoim!" % t.name_pl)
			_add_floater(t.id, "PODBURZONY", COL_AMBER)
		"fear":
			t.add_status("stunned", dur)
			_log_push("%s łamie się ze strachu." % t.name_pl)
			_add_floater(t.id, "ZŁAMANY", COL_GAS)
		"convert":
			if partial:
				t.add_status("charmed", 2)
				_log_push("%s waha się w wierze, ale jeszcze nie klęka." % t.name_pl)
				_add_floater(t.id, "WAHA SIĘ", COL_GAS)
			else:
				sim.convert_enemy(t)
				_log_push("%s przyjmuje Jedyną Wiarę i staje u twego boku!" % t.name_pl)
				_add_floater(t.id, "NAWRÓCONY", COL_GREEN)
				_shake = maxf(_shake, 4.0)

## Fire the companion's signature ability ([G]); free action, per-floor cooldown.
func _use_companion_ability() -> void:
	if floor == null or floor.companion == null or not floor.companion.is_alive():
		_log_push("Nie masz towarzysza na planszy."); queue_redraw(); return
	_animate(sim.use_companion_ability(floor.depth))
	queue_redraw()

## ── Safehouse: spend scrap to heal / buy / sell / get a sponsor package ──────
func _zlom() -> int:
	return int(sim.materials.get("złom", 0))

func _spend_zlom(n: int) -> bool:
	if _zlom() < n:
		_log_push("Za mało złomu (masz %d, trzeba %d)." % [_zlom(), n])
		return false
	sim.materials["złom"] = _zlom() - n   # sim.materials is the live run-inventory ref
	floor.player.flags["floor_zlom_spent"] = int(floor.player.flags.get("floor_zlom_spent", 0)) + n
	return true

func _open_safehouse(id: int) -> void:
	var sh = sim.entities.get(id)
	if sh == null or sh.faction != "safehouse":
		return
	_safehouse = {"id": id, "subtype": sh.monster_key}
	_log_push("%s: %s" % [Safehouse.name_of(sh.monster_key), Safehouse.blurb_of(sh.monster_key)])
	queue_redraw()

## Resolve a clicked safehouse row. `arg` carries the item index for buy/sell.
func _safehouse_action(action: String, arg: int) -> void:
	if _safehouse.is_empty():
		return
	var p := sim.player()
	match action:
		"heal_small":
			if p.hp >= p.max_hp:
				_log_push("Jesteś już w pełni zdrowia."); queue_redraw(); return
			if _spend_zlom(6):
				var got := mini(12, p.max_hp - p.hp)
				p.hp += got
				_add_floater(sim.player_id, "+%d HP" % got, COL_GREEN)
				_log_push("Klinika cię zszywa: +%d HP (−6 złomu)." % got)
		"heal_full":
			if p.hp >= p.max_hp:
				_log_push("Jesteś już w pełni zdrowia."); queue_redraw(); return
			if _spend_zlom(20):
				var got := p.max_hp - p.hp
				p.hp = p.max_hp
				_add_floater(sim.player_id, "+%d HP" % got, COL_GREEN)
				_log_push("Pełne leczenie. Rachunek boli bardziej niż rany. (−20 złomu)")
		"ad":
			if _spend_zlom(4) and floor.audience != null:
				floor.audience.change(6, "kiosk")
				_log_push("Reklama sponsora. Głośna, idiotyczna — widownia klaszcze. (−4 złomu)")
		"box":
			if _spend_zlom(18):
				var box := GameBox.new("kiosk", "Kiosk sponsora", Rarity.UNCOMMON)
				box.contents.append({"type": "material", "key": "złom", "qty": _narr_rng.randi_range(3, 6)})
				var tpl: Variant = _data_group("item_templates", "ITEM_TEMPLATES")
				if tpl is Dictionary and not (tpl as Dictionary).is_empty():
					var keys: Array = (tpl as Dictionary).keys()
					box.contents.append({"type": "item_key", "key": keys[_narr_rng.randi_range(0, keys.size() - 1)]})
				floor.boxes.append(box)
				_log_push("Kupujesz paczkę sponsora — odbierz skrzynkę na planszy. (−18 złomu)")
		"scroll":
			if not Spells.can_learn(sim.player()):
				_log_push("Twój gatunek nie pojmuje magii — zwój na nic ci się nie zda.")
			elif _spend_zlom(14):
				floor.items.append(_spell_scroll_item(""))
				_log_push("Kupujesz zwój zaklęć — użyj go z kieszeni [I], by się nauczyć.")
		"read":
			if floor.audience != null:
				floor.audience.change(3, "tablica")
			var learned := 0
			for _i in 2:                          # pull a couple of rumors into the journal
				if _learn_knowledge(Knowledge.random_rumor(_narr_rng)):
					learned += 1
			var obj_line := Objectives.describe(floor.objective) if not floor.objective.is_empty() else "brak"
			_log_push("Tablica: %d nowych plotek. Cel piętra: %s. (+3 widowni)" % [learned, obj_line])
		"buy":
			if arg >= 0 and arg < Safehouse.BUY_MATS.size():
				var entry: Dictionary = Safehouse.BUY_MATS[arg]
				if _spend_zlom(int(entry["price"])):
					var mk: String = entry["mat"]
					sim.materials[mk] = int(sim.materials.get(mk, 0)) + 1
					_log_push("Kupujesz: %s. (−%d złomu)" % [mk, int(entry["price"])])
		"sell":
			if arg >= 0 and arg < floor.items.size():
				var it := floor.items[arg] as GameItem
				var price := Safehouse.sell_price(it.rarity)
				floor.items.remove_at(arg)
				sim.materials["złom"] = _zlom() + price
				_log_push("Sprzedajesz: %s. (+%d złomu)" % [it.name_pl, price])
	queue_redraw()

## ── Knowledge: clues + rumors collected into a browsable journal ─────────────
## Add an intel entry to the run journal if it's new (idempotent by key).
func _learn_knowledge(entry: Dictionary) -> bool:
	if entry.is_empty() or entry.get("text", "") == "":
		return false
	var journal: Array = floor.player.flags.get("journal", [])
	for j in journal:
		if (j as Dictionary).get("key", "") == entry["key"]:
			return false
	journal.append(entry)
	floor.player.flags["journal"] = journal
	var t: String = entry["text"]
	_log_push("Notujesz [%s]: %s" % [Knowledge.reliability_label(float(entry.get("truth", 0.5))),
		(t.substr(0, 72) + "…") if t.length() > 72 else t])
	_add_floater(sim.player_id, "✎ notatka", COL_CYAN)
	return true

## Record a standout moment for the end-of-run highlight reel (stored on the player).
func _highlight(kind: String, line: String, value: int = 1) -> void:
	if floor == null:
		return
	var reel: Array = floor.player.flags.get("highlight_reel", [])
	Highlights.add(reel, kind, line, value)
	floor.player.flags["highlight_reel"] = reel

## ── Rival crawlers: talk / rob (DEX gamble) / fight ──────────────────────────
func _open_crawler(id: int) -> void:
	var cr = sim.entities.get(id)
	if cr == null or cr.faction != "crawler":
		return
	_crawler = {"id": id}
	var desc: Dictionary = cr.flags.get("crawler", {})
	_log_push("Inny zawodnik: %s (%s)." % [cr.name_pl, desc.get("personality", "?")])
	queue_redraw()

func _crawler_action(action: String) -> void:
	if _crawler.is_empty():
		return
	var id: int = _crawler["id"]
	var cr = sim.entities.get(id)
	if cr == null:
		_crawler = {}; queue_redraw(); return
	var desc: Dictionary = cr.flags.get("crawler", {})
	match action:
		"talk":
			if floor.audience != null:
				floor.audience.change(3, "crawler")
			_learn_knowledge(Knowledge.random_rumor(_narr_rng))   # rivals trade gossip
			_log_push("%s gada chwilę. Widownia lubi rywalizację. (+3 widowni)" % cr.name_pl)
			_crawler = {}
		"rob":
			# A DEX gamble: win and you lift their scrap + they flee; lose and they turn hostile.
			var roll := _narr_rng.randi_range(1, 20) + sim.player().stat_mod("DEX")
			if roll >= 12:
				var carried: Dictionary = desc.get("carried", {})
				var parts: Array = []
				for mk in carried:
					sim.materials[mk] = int(sim.materials.get(mk, 0)) + int(carried[mk])
					parts.append("%s x%d" % [mk, int(carried[mk])])
				_log_push("Okradasz %s i znika w mroku. Łup: %s." % [cr.name_pl, ", ".join(parts) if not parts.is_empty() else "nic"])
				_add_floater(sim.player_id, "OKRADZIONY", COL_AMBER)
				_unlock_ach("kradziez_armatury")
				# robbing while a sponsor is invested = a compliance incident
				if floor.sponsors != null:
					for sk in floor.sponsors.all_keys():
						if floor.sponsors.get_attention(sk) >= 5:
							_unlock_ach("sponsor_nie_pochwala"); break
				sim.board.clear(cr.cell)
				cr.alive = false
				sim.entities.erase(id)
				floor.rooms[floor.current]["entities"].erase(id)
			else:
				_log_push("%s łapie cię za rękę — robi się gorąco!" % cr.name_pl)
				_provoke_crawler(id)
			_crawler = {}
		"fight":
			_provoke_crawler(id)
			_crawler = {}
		_:
			_crawler = {}
	queue_redraw()

## Resolve a mid-floor decision beat: apply the chosen fork's effect, then close.
func _event_choose(idx: int) -> void:
	if _event.is_empty():
		return
	var forks: Array = _event.get("forks", [])
	if idx < 0 or idx >= forks.size():
		_event = {}; queue_redraw(); return
	var fx: Dictionary = (forks[idx] as Dictionary).get("effect", {})
	if fx.has("audience") and floor.audience != null:
		floor.audience.change(int(fx["audience"]), "event")
	if fx.has("zlom"):
		sim.materials["złom"] = maxi(0, _zlom() + int(fx["zlom"]))
	if fx.has("hp"):
		var p := sim.player()
		if int(fx["hp"]) >= 0:
			p.hp = mini(p.max_hp, p.hp + int(fx["hp"]))
		else:
			p.hp = maxi(1, p.hp + int(fx["hp"]))
	_log_push("→ " + str((forks[idx] as Dictionary).get("label", "")))
	_event = {}
	queue_redraw()

## Turn a crawler into a real, aware enemy on the board.
func _provoke_crawler(id: int) -> void:
	var cr = sim.entities.get(id)
	if cr == null:
		return
	var st := Crawlers.combat_stats(floor.depth)
	cr.faction = "enemy"
	cr.aware = true
	cr.max_hp = int(st["hp"]); cr.hp = cr.max_hp
	cr.ac = int(st["ac"]); cr.to_hit = int(st["to_hit"]); cr.dmg_dice = st["dice"]
	if "monster" not in cr.tags: cr.tags.append("monster")
	cr.flags.erase("crawler")
	_attach_bodies()
	_log_push("%s rzuca się do walki!" % cr.name_pl)
	_add_banner("RYWAL ATAKUJE")
	_shake = maxf(_shake, 5.0)

func _open_dialogue(npc_id: int) -> void:
	var npc = sim.entities.get(npc_id)
	if npc == null or npc.dialogue_tree_key == "":
		return
	_dlg = Dialogue.start(floor, npc_id, npc.dialogue_tree_key)
	_dlg_info = ""
	if _dlg.is_empty():
		return
	_dlg_events(_dlg.get("events", []))
	queue_redraw()

## Advance the conversation by picking option `orig_idx`; route events to the log.
func _dlg_advance(orig_idx: int) -> void:
	if _dlg.is_empty():
		return
	var res := Dialogue.pick(floor, _dlg, orig_idx, _narr_rng)
	_dlg_info = res.get("info", "")
	if _dlg_info != "":
		_log_push(_dlg_info)
		if _dlg_info.begins_with("Krytyczny"):
			_unlock_ach("skillcheck")           # a critical success in a skill check
	_dlg_events(res.get("events", []))
	if not res.get("continue", false):
		_dlg = {}
		_ach_bump("dialogues", 1)               # a conversation reached its end
	queue_redraw()

## Surface dialogue consequence-events into the log / floaters.
func _dlg_events(evs: Array) -> void:
	for e in evs:
		match e.get("type"):
			"dialogue_audience":
				_add_floater(sim.player_id, "widownia %+d" % int(e["delta"]), COL_AMBER)
			"dialogue_sponsor":
				_log_push("%s: uwaga %+d." % [e.get("key", "sponsor"), int(e.get("delta", 0))])
			"dialogue_material", "dialogue_give":
				var what: String = e.get("material", e.get("item", "?"))
				_log_push("Dostajesz: %s." % what)
			"dialogue_log":
				_log_push(str(e.get("text", "")))
			"dialogue_relationship":
				var d: int = int(e.get("delta", 0))
				_log_push("Relacja %s." % ("poprawia się" if d >= 0 else "psuje się"))
				for tk in floor.player.relationships:
					if int(floor.player.relationships[tk]) >= 3:
						_unlock_ach("relationship"); break
			"dialogue_threat":
				if int(e.get("amount", 0)) > 0:
					_log_push("Hałas budzi wrogów w pobliżu.")

# ── Event → animation ─────────────────────────────────────────────────────────

func _animate(evs: Array) -> void:
	_narrate_batch(evs)
	_ach_scan(evs)
	_ach_events(evs)
	_objective_track(evs)
	for e in evs:
		match e.get("type"):
			"move":
				_vtarget[e["id"]] = _cell_px(e["to"])
			"attack":
				# the attacker darts toward its victim — combat reads as motion
				var aid: int = int(e.get("attacker", -1))
				var avictim = sim.entities.get(int(e.get("target", -1)))
				if aid != -1 and avictim != null:
					var afrom: Vector2 = _vpos.get(aid, _cell_px(avictim.cell))
					var dirv: Vector2 = (_cell_px(avictim.cell) - afrom)
					if dirv.length() > 0.5:
						_lunge[aid] = {"dir": dirv.normalized(), "t": 0.18}
			"damage":
				var tid: int = e["target"]
				_flash[tid] = 0.24
				var col: Color = COL_CYAN if e.get("dmg_type") == "electric" else COL_RED
				_add_floater(tid, "-%d" % e["amount"], col)
				_play("crit" if int(e["amount"]) >= 12 else "hit")
				_shake = maxf(_shake, 5.0 if e["amount"] >= 12 else 2.5)
				_spawn_parts(_vpos.get(tid, _cell_px(Vector2i.ZERO)),
					mini(4 + int(e["amount"]) / 3, 12), _dmg_spark_color(str(e.get("dmg_type", ""))))
				if e.get("zone", "") != "":
					_part_flash["%d:%s" % [tid, e["zone"]]] = 0.4
			"body_hit":
				var wound: String = e.get("wound", "")
				if e.get("severed", false):
					_add_floater(e["target"], "AMPUTACJA: " + e.get("label", ""), COL_RED)
					_shake = maxf(_shake, 7.0)
					_spawn_parts(_vpos.get(int(e["target"]), Vector2.ZERO), 12, COL_RED, 110.0, 220.0)
				elif wound != "":
					_add_floater(e["target"],
						BodyState.WOUND_PL.get(wound, wound) + " — " + e.get("label", ""),
						_wound_color(wound))
			"maim":
				var verb := "ODCIĘTA" if e.get("severed", false) else "ZNISZCZONA"
				_add_floater(e["target"], (e.get("label", "") + " " + verb).to_upper(), COL_RED)
				_shake = maxf(_shake, 5.0)
				_log_push(_maim_line(e))
			"systemic":
				if e.get("element") == "electric":
					_add_floater(e["target"], "PRĄD!", COL_CYAN)
					_play("zap")
					_shake = maxf(_shake, 6.0)
			"death":
				_dying[e["target"]] = 1.0
				_play("death")
				var dent = sim.entities.get(int(e["target"]))
				if dent != null:
					var dcol := _enemy_hue(dent, _enemy_body_kind(dent)) \
						if dent.faction == "enemy" else COL_RED
					_spawn_parts(_vpos.get(int(e["target"]), _cell_px(dent.cell)), 14, dcol, 95.0)
			"miss":
				_add_floater(e["target"], "pudło", COL_DIM)
				_play("whoosh")
			"guard":
				_add_floater(int(e["id"]), "GARDA", COL_CYAN)
				_play("clang")
				_log_push("%s podnosi gardę — pchnięcie ją łamie." % e.get("name", "Wróg"))
			"guard_break":
				_add_floater(int(e["id"]), "GARDA PĘKA", COL_AMBER)
			"enrage":
				_add_floater(int(e["id"]), "SZAŁ!", COL_RED)
				_play("growl")
				_log_push("%s wpada w szał!" % e.get("name", "Wróg"))
				_shake = maxf(_shake, 4.0)
			"pounce":
				_add_floater(int(e["id"]), "SKOK!", COL_AMBER)
				_play("pounce")
			"phase":
				_add_floater(int(e["id"]), "PRZENIKA", COL_DIM)
				_play("phase")
				_log_push("Ostrze przechodzi przez %s — to nie jest ciało." % e.get("name", "zjawę"))
			"salvage":
				_dying[e["target"]] = 1.0
				_play("crunch")
				var parts: Array = []
				for k in e["gained"]:
					parts.append("+%s" % k)
				_add_floater(e["target"], ", ".join(parts), COL_AMBER)
				_shake = maxf(_shake, 2.0)
				if e["gained"].has("drewno"):
					_narrate("furniture_salvage")
				elif e["gained"].has("przewód") or e["gained"].has("złom"):
					_narrate("tech_salvage")
				else:
					_narrate("salvage_success")
			"notice":
				_add_floater(e["id"], "!", COL_RED)
				_shake = maxf(_shake, 3.0)
			"craft_attempt":
				var outcome: String = e.get("outcome", "")
				var col: Color = COL_CYAN
				match outcome:
					"krytyk":    col = Rarity.color(Rarity.UNCOMMON)
					"czesciowy": col = COL_AMBER
					"porazka":   col = COL_DIM
					"backfire":  col = COL_RED
				_add_floater(sim.player_id, outcome.to_upper(), col)
				if e.get("item_name", "") != "":
					_add_floater(sim.player_id, "+" + e["item_name"], COL_GREEN)
				match outcome:
					"krytyk":    _narrate("clever_craft"); _play("craft_ok")
					"sukces":    _narrate("craft_success"); _play("craft_ok")
					"czesciowy": _narrate("craft_partial"); _play("craft_bad")
					"porazka":   _narrate("craft_fail"); _play("craft_bad")
					"backfire":  _narrate("craft_critical_fail"); _play("explode")
				# A procedural failure line (from failure_templates.json) on a botch.
				var flvl: String = {"czesciowy": "partial", "porazka": "failure", "backfire": "critical_failure"}.get(outcome, "")
				if flvl != "":
					var fl := Flavor.fail_line(flvl, _narr_rng)
					if fl != "":
						_log_push(fl)
			"backfire_desc":
				_add_floater(sim.player_id, e.get("desc", "backfire"), COL_RED)
				_shake = maxf(_shake, 4.0)
			"coating_applied":
				_add_floater(sim.player_id, "+powłoka x%d" % e["charges"], COL_CYAN)
			"heal":
				_add_floater(sim.player_id, "+%d HP" % e["amount"], COL_GREEN)
				_play("heal")
				_spawn_parts(_vpos.get(sim.player_id, Vector2.ZERO), 5, COL_GREEN, 38.0, -70.0, 0.7, 2.0)
			"weapon_upgrade":
				_add_floater(sim.player_id, "+%d obr." % e["bonus"], COL_AMBER)
			"xp":
				_add_floater(sim.player_id, "+%d XP" % e["amount"], COL_GAS)
			"level_up":
				_on_level_up(e)
			"armor_equipped":
				_add_floater(sim.player_id, "+%d AC" % e.get("ac_bonus", 1), COL_CYAN)
				_play("clang")
				_log_push("Zakładasz: %s. Pancerz +%d AC (%s)." % [
					e.get("name", "?"), e.get("ac_bonus", 1), e.get("slot", "ciało")])
			"recipe_learned":
				if not e.get("known", false):
					_add_floater(sim.player_id, "+przepis", COL_GREEN)
					_log_push("Nowy przepis: %s." % e.get("name", "?"))
			"spell_learned":
				_play("chime")
				if e.get("fizzle", false):
					_add_floater(sim.player_id, "ZWÓJ ROZSYPUJE SIĘ", COL_DIM)
					_log_push("Litery rozpływają ci się przed oczami. Magia nie dla ciebie.")
				else:
					_add_floater(sim.player_id, "✦ +zaklęcie", COL_PURPLE)
					_log_push("Uczysz się zaklęcia: %s. (otwórz księgę [Z])" % e.get("name", "?"))
					_shake = maxf(_shake, 3.0)
			"class_active":
				_add_floater(sim.player_id, str(e.get("name", "")).to_upper(), COL_AMBER)
				_log_push("Umiejetnosc: %s." % e.get("name", "?"))
				_shake = maxf(_shake, 3.0)
			"buff":
				_log_push(str(e.get("label", "")))
			"class_active_blocked":
				_log_push(str(e.get("reason", "Nie mozna uzyc umiejetnosci.")))
			"companion_ability":
				_add_floater(sim.player_id, str(e.get("name", "Towarzysz")).to_upper(), COL_GREEN)
				_log_push("Towarzysz działa: %s." % e.get("name", "?"))
				_shake = maxf(_shake, 3.0)
			"companion_blocked":
				_log_push(str(e.get("reason", "Towarzysz nie może teraz pomóc.")))
			"spell_cast":
				_add_floater(sim.player_id, "✦ " + str(e.get("name", "Zaklęcie")), COL_PURPLE)
				_play("cast")
				_log_push("Rzucasz: %s." % e.get("name", "?"))
				_shake = maxf(_shake, 3.0)
				_spawn_parts(_vpos.get(sim.player_id, Vector2.ZERO), 8, COL_PURPLE, 60.0, -30.0, 0.6)
			"cast_blocked":
				_log_push(str(e.get("reason", "Nie możesz teraz rzucić.")))
			"scrap_found":
				_add_floater(sim.player_id, "+%d złom" % int(e.get("amount", 0)), COL_AMBER)
			"marked":
				if int(e.get("id", -1)) != -1:
					_add_floater(int(e["id"]), "CEL!", COL_CYAN)
			"convert":
				# a zealot spread the faith on its own — the crusade chains
				_add_floater(int(e.get("id", sim.player_id)), "NAWRÓCONY", COL_GREEN)
				_play("holy")
				_spawn_parts(_vpos.get(int(e.get("id", -1)), Vector2.ZERO), 10,
					Color("ffd24a"), 70.0, -40.0, 0.7)
				_log_push("%s przyjmuje wiarę od współwyznawcy!" % e.get("name", "Ktoś"))
			"distract":
				_add_floater(int(e.get("id", sim.player_id)), "ROZPROSZONY", COL_GAS)
				_log_push("%s traci kolejną turę — rozproszony." % e.get("name", "Wróg"))
			"ally_down":
				_add_floater(int(e.get("id", 999)), "TOWARZYSZ PADŁ", COL_RED)
				_log_push("%s pada! Wróci na następnym piętrze." % e.get("name", "Towarzysz"))
				_shake = maxf(_shake, 5.0)
			"talk":
				_open_dialogue(int(e.get("npc_id", -1)))
			"safehouse":
				_open_safehouse(int(e.get("id", -1)))
			"crawler":
				_open_crawler(int(e.get("id", -1)))
			"throw":
				_add_floater(sim.player_id, "RZUT", COL_AMBER)
				_log_push("Rzucasz: %s!" % e.get("name", "?"))
				_shake = maxf(_shake, 3.0)
			"status_tick":
				_add_floater(int(e.get("target", 0)), str(e.get("status", "")), COL_GAS)
			"hazard_placed":
				_log_push("Rozlewa się: %s." % e.get("kind", "?"))
				_rebuild_world_lights()
			"biome_gimmick":
				_log_push(str(e.get("text", "")))
			"trap_armed":
				_log_push("Pułapka rozstawiona (%s)." % e.get("kind", "?"))
			"item_used":
				_add_floater(sim.player_id, "użyto: " + e["name"], COL_BRIGHT)
			"audience_change":
				if e.get("crossed", false):
					_log_push("Widownia — %s!" % e.get("band", "").to_upper())
			"sponsor_attention":
				_sponsor_reaction(e)
			"sponsor_gift":
				_play("gift")
				_log_push("%s zauważył cię. Paczka!" % e.get("name", "Sponsor"))
			"combat_end":
				_add_banner("ZWYCIĘSTWO" if e["outcome"] == "win" else "KONIEC")
		var ln := _event_line(e)
		if ln != "":
			_log_push(ln)
	# A sponsor you've angered may have queued a bounty hunter this batch — drop it
	# onto the board now (negative sponsor attention finally MEANS something).
	if floor != null and floor.sponsors != null and not floor.sponsors.pending_hunters.is_empty():
		for hn in floor.sponsors.drain_hunters():
			_spawn_hunter(str(hn))
	queue_redraw()

## Konferansjer reads the whole event batch for show-worthy moments: an
## environment kill (shock + a dead enemy) and audience band crossings.
func _narrate_batch(evs: Array) -> void:
	var systemic_electric := false
	var enemy_died := false
	for e in evs:
		match e.get("type"):
			"systemic":
				if e.get("element") == "electric":
					systemic_electric = true
			"death":
				var t = sim.entities.get(e.get("target"))
				if t != null and t.faction == "enemy":
					enemy_died = true
			"audience_change":
				if e.get("crossed", false):
					_narrate("audience_rise" if int(e.get("delta", 0)) > 0 else "audience_drop")
	if systemic_electric and enemy_died:
		_narrate("env_kill")

func _name(id: int) -> String:
	var e = sim.entities.get(id)
	return e.name_pl if e != null else "?"

func _wound_color(wound: String) -> Color:
	match wound:
		"burn":    return COL_GAS
		"shock":   return COL_CYAN
		"corrode": return COL_GREEN
		"freeze":  return Color(0.6, 0.85, 1.0)
		"bleed":   return COL_RED
		"sever":   return COL_RED
	return COL_DIM

## Polish label of a target's body zone (or "" if it has no body / no zone).
func _zone_label(id: int, zone: String) -> String:
	var e = sim.entities.get(id)
	if e == null or e.body == null or zone == "":
		return ""
	var p: Dictionary = e.body.part(zone)
	return p.get("label_pl", "") if not p.is_empty() else ""

## Build the dramatic Polish line for a maim event (ASCII-safe content).
func _maim_line(e: Dictionary) -> String:
	var nm := _name(e["target"])
	var lbl: String = e.get("label", "?")
	if e.get("severed", false):
		return "Odcinasz %s u %s!" % [lbl, nm]
	match e.get("status"):
		"stunned":  return "Roztrzaskujesz %s — %s oszolomiony, traci ture!" % [lbl, nm]
		"slowed":   return "Lamiesz %s — %s kuleje i nie dogoni cie." % [lbl, nm]
		"disarmed": return "Miazdzysz %s — %s slabiej uderza." % [lbl, nm]
		"blinded":  return "Niszczysz %s — %s oslepiony." % [lbl, nm]
	return "%s u %s peka." % [lbl, nm]

## Fire a konferansjer line for a category (if one exists) into the log.
func _narrate(category: String) -> void:
	var line := Narrator.say(category, _narr_rng)
	if line != "":
		_log_push("Konferansjer: " + line)
		_play("blip")   # the host's voice, Animal-Crossing style

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
				return "(Sprzęt blokuje — [E] rozbierz.)"
		"craft_attempt":
			match e.get("outcome"):
				"krytyk":    return "KRYTYK! Tworzysz: %s." % e.get("item_name", "?")
				"sukces":    return "Sukces. Tworzysz: %s." % e.get("item_name", "?")
				"czesciowy": return "Częściowy sukces — wadliwa wersja: %s." % e.get("item_name", "?")
				"porazka":   return "Porażka. Tracisz materiały."
				"backfire":  return "BACKFIRE!"
		"backfire_desc":
			return e.get("desc", "")
		"craft_fail":
			return "Brakuje materiałów: " + e.get("reason", "") + "."
		"none":
			match e.get("action"):
				"shove":    return "Nie ma kogo pchnąć — stań tuż obok wroga."
				"salvage":  return "Nie ma czego rozebrać w pobliżu."
				"use_item": return "Brak przedmiotu o tym numerze."
	return ""

var _banner := ""
var _banner_t := 0.0          # seconds the current banner stays before fading out
func _add_banner(txt: String) -> void:
	_banner = txt
	_banner_t = 2.2

## Play a synthesized sound if the audio node exists (it doesn't in headless tests).
func _play(sname: String) -> void:
	if _sfx != null:
		_sfx.play(sname)

func _add_floater(id: int, text: String, color: Color) -> void:
	var pos: Vector2 = _vpos.get(id, _cell_px(Vector2i.ZERO))
	_floaters.append({"pos": pos, "text": text, "color": color, "age": 0.0, "ttl": 0.95})

## Burst `n` particles at a world position (capped pool; cheap circles).
func _spawn_parts(pos: Vector2, n: int, col: Color, speed: float = 70.0,
		grav: float = 160.0, ttl: float = 0.55, size: float = 2.6) -> void:
	for _i in n:
		if _parts.size() >= 240:
			return
		var ang := randf() * TAU
		_parts.append({"pos": pos, "vel": Vector2(cos(ang), sin(ang)) * speed * randf_range(0.4, 1.0),
			"life": ttl, "ttl": ttl, "size": size * randf_range(0.7, 1.3), "col": col, "grav": grav})

## Spark colour per damage type (the elements keep their identity in the air).
func _dmg_spark_color(t: String) -> Color:
	match t:
		"electric": return COL_CYAN
		"fire":     return Color("ff6a2a")
		"acid":     return COL_GREEN
		"cold":     return Color("9fd4ff")
		"void":     return COL_PURPLE
	return Color("e88a8a")

## Rebuild the pooled world lights: fire hazards flicker orange, the safehouse
## glows warm. Called on floor/room changes and when a hazard appears.
func _rebuild_world_lights() -> void:
	if _lights_root == null or sim == null:
		return
	for ch in _lights_root.get_children():
		ch.queue_free()
	var made := 0
	for cell in sim.board.hazards:
		if made >= 12: break
		if str(sim.board.hazards[cell]) != "fire": continue
		var fl := PointLight2D.new()
		fl.texture = _light_tex
		fl.color = Color("ff8a3a")
		fl.energy = 0.9
		fl.texture_scale = 0.45
		fl.position = _cell_px(cell)
		_lights_root.add_child(fl)
		made += 1
	for id in sim.entities:
		if sim.entities[id].faction == "safehouse":
			var sl := PointLight2D.new()
			sl.texture = _light_tex
			sl.color = Color("ffd9a0")
			sl.energy = 0.7
			sl.texture_scale = 0.7
			sl.position = _cell_px(sim.entities[id].cell)
			_lights_root.add_child(sl)

# ── Per-frame animation ───────────────────────────────────────────────────────

func _process(dt: float) -> void:
	for id in _vpos:
		_vpos[id] = (_vpos[id] as Vector2).lerp(_vtarget[id], minf(1.0, dt * 12.0))
	for id in _flash.keys():
		_flash[id] = _flash[id] - dt
		if _flash[id] <= 0: _flash.erase(id)
	for id in _dying.keys():
		_dying[id] = _dying[id] - dt * 1.5
		if _dying[id] <= 0: _dying.erase(id)
	for k in _part_flash.keys():
		_part_flash[k] = _part_flash[k] - dt
		if _part_flash[k] <= 0: _part_flash.erase(k)
	for f in _floaters:
		f["age"] += dt
	_floaters = _floaters.filter(func(f): return f["age"] < f["ttl"])
	_shake = maxf(0.0, _shake - dt * 24.0)
	_tick_box_anim(dt)
	for to in _toasts:
		to["t"] = float(to["t"]) + dt
	_toasts = _toasts.filter(func(x): return float(x["t"]) < float(x["ttl"]))
	if _ach_flash > 0.0:
		_ach_flash = maxf(0.0, _ach_flash - dt)
	if _banner_t > 0.0:
		_banner_t = maxf(0.0, _banner_t - dt)
		if _banner_t == 0.0:
			_banner = ""
	# Screen-shake rides the camera now (the world no longer redraws transformed).
	if _cam != null:
		_cam.offset = Vector2(randf_range(-_shake, _shake), randf_range(-_shake, _shake)) \
			if _shake > 0.0 else Vector2.ZERO
	# Particles: integrate, gravity, cull.
	for pt in _parts:
		pt.life = float(pt.life) - dt
		pt.vel = (pt.vel as Vector2) + Vector2(0, float(pt.grav)) * dt
		pt.pos = (pt.pos as Vector2) + (pt.vel as Vector2) * dt
	_parts = _parts.filter(func(pt2): return float(pt2.life) > 0.0)
	# Attack lunges decay quickly.
	for id in _lunge.keys():
		_lunge[id]["t"] = float(_lunge[id]["t"]) - dt
		if float(_lunge[id]["t"]) <= 0.0:
			_lunge.erase(id)
	# Floor-transition wipe.
	if _wipe > 0.0:
		_wipe = maxf(0.0, _wipe - dt * 2.2)
	if _summary_lock > 0.0:
		_summary_lock = maxf(0.0, _summary_lock - dt)
	# Fire hazards exhale embers (only while playing, and only a few at a time).
	if sim != null and not _title and _summary.is_empty():
		_ember_cd -= dt
		if _ember_cd <= 0.0:
			_ember_cd = 0.22
			for cell in sim.board.hazards:
				if str(sim.board.hazards[cell]) == "fire" and _parts.size() < 200:
					_spawn_parts(_cell_px(cell) + Vector2(randf_range(-12, 12), 8),
						1, Color("ff9a4a"), 14.0, -55.0, 1.1, 2.2)
	# Soundtrack mood: title / explore / combat / boss, crossfaded.
	if _sfx != null:
		var mood := "title"
		if not _title and _summary.is_empty() and sim != null:
			if floor != null and floor.depth >= FINAL_FLOOR:
				mood = "boss"
			else:
				mood = "explore"
				for me in sim.enemies_alive():
					if me.aware:
						mood = "combat"
						break
		_sfx.music(mood)
	# Biome mood: ambient grade + the player light track the active theme.
	if _cmod != null and sim != null and not _title:
		var th := BiomeThemes.theme_for(floor.biome if floor != null else "")
		_cmod.color = th.ambient
		if _plight != null:
			_plight.energy = th.light
			_plight.position = _vpos.get(sim.player_id, _cell_px(sim.player().cell))
	if _smoke:
		_smoke_tick()
	queue_redraw()
	if _ui != null:
		_ui.queue_redraw()

## --smoke: a scripted pass through the real draw paths (title → run → panels)
## with rendering ON, then quit. Catches draw-time errors headless tests can't.
func _smoke_tick() -> void:
	_smoke_frames += 1
	match _smoke_frames:
		20: _build()
		50: handle_dir(Vector2i.RIGHT)
		60:
			# light + particle paths: a burning tile next to the player
			sim.board.set_hazard(sim.player().cell + Vector2i(0, 1), "fire")
			_rebuild_world_lights()
			_spawn_parts(_vpos.get(sim.player_id, Vector2.ZERO), 10, COL_RED)
		70: _spellbook = true
		90: _spellbook = false; _journal_screen = true
		110: _journal_screen = false; _craft_open = true; _craft_mode = "bench"
		130: _craft_open = false; _open_ach_screen()
		150: _ach_screen = false; _meta_screen = true
		170: _meta_screen = false
		# Cycle the most distinct biome themes so every set-dressing path paints.
		185: floor.biome = "bar_skurczybyk"
		200: floor.biome = "biome_lawowe_tunele"
		215: floor.biome = "muzeum_spektakli"
		230: floor.biome = "biome_siec_kanalizacyjna"
		245: floor.biome = "okopy_frontowe"
		255: _char_screen = true
		270: _char_screen = false; _pause_screen = true
		285: _pause_screen = false
		300:
			print("SMOKE OK")
			get_tree().quit(0)

## Advance the lootbox-opening reveal through its phases.
func _tick_box_anim(dt: float) -> void:
	if _box_anim.is_empty():
		return
	var t_prev: float = float(_box_anim["t"])
	_box_anim["t"] = t_prev + dt
	var t: float = _box_anim["t"]
	match _box_anim["phase"]:
		"spin":
			# reel ticks ratchet the tension (one per notch passed)
			if int(t * 10.0) != int(t_prev * 10.0):
				_play("tick")
			if t >= BOX_SPIN:
				_box_anim["phase"] = "pop"; _box_anim["t"] = 0.0
				_shake = maxf(_shake, 9.0)        # the SNAP
				_play("snap")
				if int(_box_anim.get("tier", 1)) >= 3:
					_play("jackpot")
		"pop":
			if t >= BOX_POP:
				_box_anim["phase"] = "reveal"; _box_anim["t"] = 0.0
		"reveal":
			var entries: Array = _box_anim["entries"]
			_box_anim["reveal_n"] = mini(int(t / BOX_REVEAL_STEP) + 1, entries.size())
			if int(_box_anim["reveal_n"]) >= entries.size() and t > entries.size() * BOX_REVEAL_STEP + 0.3:
				_box_anim["phase"] = "done"; _box_anim["t"] = 0.0
		"done":
			pass

# ── Drawing ───────────────────────────────────────────────────────────────────

## WORLD pass: the board + entities, drawn in world space under the Camera2D.
## All screen-fixed UI (HUD, modals, menus) is painted by UIView on a CanvasLayer
## via _draw_ui — this split is what lets Phase B swap these rects for tilemaps
## and sprites without touching any interface code.
func _draw() -> void:
	if _title or _meta_screen or _ach_screen or _journal_screen or sim == null \
			or not _summary.is_empty():
		return   # a full-screen menu owns the frame; the UI layer paints it
	var b: Board = sim.board
	var th := BiomeThemes.theme_for(floor.biome if floor != null else "")
	# Biome signature frame around the arena.
	draw_rect(Rect2(-4, -4, b.w * TILE + 7, b.h * TILE + 7), Color(th.accent, 0.55), false, 2.0)
	for y in b.h:
		for x in b.w:
			var c := Vector2i(x, y)
			var r := Rect2(_origin + Vector2(x * TILE, y * TILE), Vector2(TILE - 1, TILE - 1))
			if b.is_wall(c):
				draw_rect(r, th.wall)
				draw_line(r.position, r.position + Vector2(TILE - 1, 0), th.wall_hi, 1.0)
				_draw_wall_prop(r, c, th)
				continue
			draw_rect(r, th.floor_b if (x + y) % 2 == 0 else th.floor_a)
			draw_rect(r, th.grid, false, 1.0)
			_draw_floor_pattern(r, c, th)
			_draw_floor_prop(r, c, th)
			match b.hazard_at(c):
				"water": draw_rect(Rect2(r.position + Vector2(3, 3), Vector2(TILE - 7, TILE - 7)), COL_WATER)
				"wire":  _draw_glyph("|", c, COL_WIRE)
				"gas":   _draw_glyph("G", c, COL_GAS)
				"fire":
					draw_rect(Rect2(r.position + Vector2(4, 4), Vector2(TILE - 9, TILE - 9)), Color(0.55, 0.18, 0.06, 0.6))
					_draw_glyph("^", c, COL_RED)
	_draw_exits()
	var p := sim.player()
	for d in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN,
			Vector2i(1,1), Vector2i(-1,1), Vector2i(1,-1), Vector2i(-1,-1)]:
		if b.is_free(p.cell + d):
			draw_circle(_cell_px(p.cell + d), 3.0, Color(0.29, 0.38, 0.47))
	_draw_intent()
	_draw_preview()
	for id in sim.entities:
		var e: CombatEntity = sim.entities[id]
		if not e.is_alive() and not _dying.has(id):
			continue
		var pos: Vector2 = _vpos.get(id, _cell_px(e.cell))
		# Attack lunge: a quick dart toward the victim, decaying in _process.
		if _lunge.has(id):
			var lg: Dictionary = _lunge[id]
			pos += (lg.dir as Vector2) * 12.0 * (float(lg.t) / 0.18)
		# Movement bob: a light step rhythm while gliding between cells.
		elif pos.distance_to(_vtarget.get(id, pos)) > 2.0:
			pos.y += sin(Time.get_ticks_msec() * 0.025 + id * 1.7) * 2.0
		var fade: float = _dying.get(id, 1.0)
		var flashing := _flash.has(id)
		if e.faction == "player":      _draw_player(e, pos, fade)
		elif e.faction == "safehouse": _draw_safehouse_token(pos, fade)
		elif e.faction == "crawler":   _draw_crawler_token(pos, fade)
		elif e.faction == "ally":      _draw_ally(e, pos, fade)
		elif e.faction == "object":    _draw_object(e, pos, fade)
		elif e.faction == "npc":       _draw_npc(pos, fade)
		else:                          _draw_enemy(e, pos, fade, flashing)
	# Particles ride above entities.
	for pt in _parts:
		var pa: float = clampf(float(pt.life) / float(pt.ttl), 0.0, 1.0)
		draw_circle(pt.pos, float(pt.size) * (0.5 + 0.5 * pa), Color(pt.col, pa))
	for f in _floaters:
		var a: float = 1.0 - float(f["age"]) / float(f["ttl"])
		var col: Color = f["color"]; col.a = a
		var fp: Vector2 = f["pos"] + Vector2(-10, -20 - f["age"] * 36.0)
		draw_string(_font, fp, f["text"], HORIZONTAL_ALIGNMENT_LEFT, -1, 18, col)

## UI pass: everything screen-fixed, painted into the UIView CanvasItem. Click
## zones are rebuilt here so they always match exactly what is on screen.
func _draw_ui(c: CanvasItem) -> void:
	_click_zones.clear()
	# Full-screen content menus own the whole screen — no toasts layered over them.
	if _meta_screen:
		_draw_meta_screen(c)
		return
	if _journal_screen and sim != null:
		_draw_journal(c)
		return
	if _char_screen and sim != null:
		_draw_char(c)
		return
	if _ach_screen:
		_draw_ach_screen(c)
		return
	if _title:
		_draw_title(c)
		_draw_toasts(c)
		return
	if sim == null: return
	if not _summary.is_empty():
		_draw_run_summary(c)
		return
	_draw_hud(c)
	if _pause_screen:
		_draw_pause(c)
	# Floor/room transition: a quick fade-in from black over everything.
	if _wipe > 0.0:
		c.draw_rect(Rect2(0, 0, 1280, 720), Color(0, 0, 0, clampf(_wipe, 0.0, 1.0)))

## Take a worn piece off and put it back in the pocket (Phase C gap-fix).
func _unequip(slot: String) -> void:
	if floor == null:
		return
	var it = floor.player.equipment.get(slot)
	if it == null:
		return
	floor.player.equipment.erase(slot)
	floor.items.append(it)
	_play("clang")
	_log_push("Zdejmujesz: %s." % (it as GameItem).name_pl)
	queue_redraw()

const SETTINGS_PATH := "user://settings.json"

func _save_settings() -> void:
	if _sfx == null:
		return
	var f := FileAccess.open(SETTINGS_PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify({
			"master": _sfx.get_volume("Master"), "music": _sfx.get_volume("Music"),
			"sfx": _sfx.get_volume("SFX"),
			"fullscreen": DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN}))

func _load_settings() -> void:
	if _sfx == null or not FileAccess.file_exists(SETTINGS_PATH):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(SETTINGS_PATH))
	if not (parsed is Dictionary):
		return
	_sfx.set_volume("Master", float(parsed.get("master", 0.0)))
	_sfx.set_volume("Music", float(parsed.get("music", -8.0)))
	_sfx.set_volume("SFX", float(parsed.get("sfx", 0.0)))
	if bool(parsed.get("fullscreen", false)):
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)

## Character sheet: who you are, what you wear (with unequip), what you know.
func _draw_char(c: CanvasItem) -> void:
	c.draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	var p := sim.player()
	_panel(c, Rect2(50, 40, 1180, 640), COL_CYAN, "KARTA POSTACI — %s  ·  POZIOM %d" % [
		MetaCatalog.def_of(p.species_key).get("label", "Bezimienny"), p.level])
	var x := 80.0
	var y := 110.0
	c.draw_string(_font, Vector2(x, y), "HP %d/%d   ·   Mana %d/%d   ·   AC %d   ·   XP %d/%d" % [
		p.hp, p.max_hp, p.mana, p.max_mana, p.ac + p.armor_bonus(), p.xp, p.xp_to_next()],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, COL_BRIGHT)
	y += 34.0
	for st in ["STR", "DEX", "INT", "WIS", "CHA"]:
		c.draw_string(_font, Vector2(x, y), "%s  %d  (mod %+d)" % [st, int(p.stats.get(st, 0)), p.stat_mod(st)],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 15, COL_AMBER)
		y += 24.0
	y += 10.0
	c.draw_string(_font, Vector2(x, y), "Pochodzenie: %s   ·   Cecha: %s   ·   Magia: %s" % [
		MetaCatalog.def_of(p.origin_key).get("label", "Debiutant"),
		p.species_trait if p.species_trait != "" else "—",
		p.magic_affinity if p.magic_affinity != "" else "zwykła"],
		HORIZONTAL_ALIGNMENT_LEFT, 520, 13, COL_DIM)
	y += 30.0
	c.draw_string(_font, Vector2(x, y), "Bieg: zabójstwa %d · rozbiórki %d · pułapki %d" % [
		p.run_kills, p.run_corpses_salvaged, p.run_traps_armed],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	var ex := 560.0
	var ey := 110.0
	c.draw_string(_font, Vector2(ex, ey), "EKWIPUNEK", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, COL_CYAN)
	ey += 28.0
	var slot_pl := {"head": "Głowa", "body": "Tułów", "legs": "Nogi"}
	for slot in ["head", "body", "legs"]:
		var worn = p.equipment.get(slot)
		_draw_icon(c, "armor", Vector2(ex + 8, ey - 5), COL_CYAN if worn != null else COL_DIM)
		c.draw_string(_font, Vector2(ex + 22, ey), "%s: %s" % [slot_pl[slot],
			(worn as GameItem).name_pl if worn != null else "—"],
			HORIZONTAL_ALIGNMENT_LEFT, 280, 14, COL_BRIGHT if worn != null else COL_DIM)
		if worn != null:
			var ub := Rect2(ex + 310, ey - 16, 110, 24)
			var uh := _hover(ub)
			c.draw_rect(ub, Color(COL_RED, 0.25 if uh else 0.1))
			c.draw_rect(ub, COL_RED if uh else COL_GRID, false, 1.0)
			c.draw_string(_font, Vector2(ub.position.x + 10, ub.position.y + 17), "ZDEJMIJ",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_BRIGHT)
			_zone(ub, "char_unequip", 0, slot)
		ey += 32.0
	ey += 12.0
	c.draw_string(_font, Vector2(ex, ey), "Klasa: %s   ·   Styl: %s" % [
		Classes.name_of(p.class_key) if p.class_key != "" else "—",
		Classes.style_summary(p, 2)],
		HORIZONTAL_ALIGNMENT_LEFT, 420, 13, COL_DIM)
	var sx := 980.0
	var sy := 110.0
	c.draw_string(_font, Vector2(sx, sy), "ZAKLĘCIA", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, COL_PURPLE)
	sy += 26.0
	var ks2: Array = Spells.known(p)
	if ks2.is_empty():
		c.draw_string(_font, Vector2(sx, sy), "— żadnych —", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
		sy += 22.0
	for sk in ks2:
		_draw_icon(c, "spell", Vector2(sx + 7, sy - 5), COL_PURPLE)
		c.draw_string(_font, Vector2(sx + 20, sy), Spells.def_of(sk).get("name", sk),
			HORIZONTAL_ALIGNMENT_LEFT, 220, 14, COL_BRIGHT)
		sy += 24.0
	sy += 14.0
	c.draw_string(_font, Vector2(sx, sy), "KIESZEŃ (%d)" % floor.items.size(),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, COL_AMBER)
	sy += 26.0
	for ii in mini(floor.items.size(), 14):
		var itx := floor.items[ii] as GameItem
		c.draw_string(_font, Vector2(sx, sy), "• " + itx.name_pl,
			HORIZONTAL_ALIGNMENT_LEFT, 240, 12, itx.rarity_color())
		sy += 20.0
	c.draw_string(_font, Vector2(80, 660), "[C]/[Esc] zamknij",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)

## Pause + settings: volumes (the Sfx buses), fullscreen, quit to title.
func _draw_pause(c: CanvasItem) -> void:
	c.draw_rect(Rect2(0, 0, 1280, 720), Color(0, 0, 0, 0.6))
	var r := Rect2(440, 180, 400, 372)
	_panel(c, r, COL_CYAN, "PAUZA")
	var y := r.position.y + 72.0
	for row in [["Master", "Głośność"], ["Music", "Muzyka"], ["SFX", "Efekty"]]:
		var vol: float = _sfx.get_volume(row[0]) if _sfx != null else 0.0
		c.draw_string(_font, Vector2(r.position.x + 24, y), "%s:  %d dB" % [row[1], int(vol)],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_BRIGHT)
		for pair in [[-1, "-", 270.0], [1, "+", 312.0]]:
			var vb := Rect2(r.position.x + float(pair[2]), y - 16, 32, 24)
			var vh := _hover(vb)
			c.draw_rect(vb, Color(COL_CYAN, 0.25 if vh else 0.1))
			c.draw_rect(vb, COL_CYAN if vh else COL_GRID, false, 1.0)
			c.draw_string(_font, Vector2(vb.position.x + 12, vb.position.y + 17), str(pair[1]),
				HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_BRIGHT)
			_zone(vb, "vol", int(pair[0]), str(row[0]))
		y += 42.0
	for r2 in [["Pełny ekran [F11]", "pause_full"], ["Wznów [Esc]", "pause_resume"],
			["Wyjdź do tytułu (zapis zostaje)", "pause_quit"]]:
		var b2 := Rect2(r.position.x + 24, y - 16, r.size.x - 48, 30)
		var h2 := _hover(b2)
		c.draw_rect(b2, Color(COL_CYAN, 0.18 if h2 else 0.07))
		c.draw_rect(b2, COL_CYAN if h2 else COL_GRID, false, 1.0)
		c.draw_string(_font, Vector2(b2.position.x + 12, b2.position.y + 21), str(r2[0]),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_BRIGHT)
		_zone(b2, str(r2[1]))
		y += 40.0

func _draw_glyph(s: String, c: Vector2i, col: Color) -> void:
	draw_string(_font, _cell_px(c) + Vector2(-6, 8), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 26, col)

# ── Biome set-dressing (Phase B.1) ───────────────────────────────────────────
# Everything below is DETERMINISTIC per (run seed, depth, cell) so a floor's
# look is stable across frames, saves and resumes — décor, not noise.

func _chash(cx: int, cy: int) -> int:
	var h: int = cx * 374761393 + cy * 668265263 + _run_seed * 31 \
		+ (floor.depth if floor != null else 0) * 97
	h = (h ^ (h >> 13)) * 1274126177
	return absi(h ^ (h >> 16))

## Floor motif: a per-biome texture stamped on cells (cheap primitives).
func _draw_floor_pattern(r: Rect2, c: Vector2i, th: Dictionary) -> void:
	var h := _chash(c.x, c.y)
	var col: Color = th.pattern_col
	match th.pattern:
		"tiles":
			draw_rect(r.grow(-8), col, false, 1.0)
		"planks":
			draw_line(r.position + Vector2(0, TILE / 3.0), r.position + Vector2(TILE - 1, TILE / 3.0), col, 1.0)
			draw_line(r.position + Vector2(0, TILE * 2 / 3.0), r.position + Vector2(TILE - 1, TILE * 2 / 3.0), col, 1.0)
			if h % 3 == 0:
				draw_line(r.position + Vector2(TILE * 0.5, TILE / 3.0), r.position + Vector2(TILE * 0.5, TILE * 2 / 3.0), col, 1.0)
		"hatch":
			draw_line(r.position + Vector2(2, TILE - 4), r.position + Vector2(TILE - 4, 2), col, 1.0)
			if h % 2 == 0:
				draw_line(r.position + Vector2(2, TILE * 0.5), r.position + Vector2(TILE * 0.5, 2), col, 1.0)
		"rubble":
			if h % 10 < 3:
				var p1 := r.position + Vector2(6 + h % 24, 8 + (h / 7) % 24)
				draw_colored_polygon(PackedVector2Array([p1, p1 + Vector2(7, 2), p1 + Vector2(3, 7)]), col)
			if h % 7 == 0:
				draw_circle(r.position + Vector2(10 + (h / 3) % 26, 30), 2.0, col)
		"cracks":
			if h % 10 < 4:
				var a := r.position + Vector2(4 + h % 12, 4 + (h / 5) % 14)
				var m := a + Vector2(10 + h % 8, 8 + (h / 11) % 10)
				var z := m + Vector2(8 - (h % 16), 10)
				draw_polyline(PackedVector2Array([a, m, z]), col, 1.6)
		"dots":
			if h % 10 < 4:
				for k in 3:
					var dh := _chash(c.x * 5 + k, c.y * 3 + k)
					draw_circle(r.position + Vector2(5 + dh % 38, 5 + (dh / 9) % 38), 1.4, col)
		"stripes":
			if (c.x + c.y) % 2 == 0:
				draw_line(r.position + Vector2(0, TILE - 2), r.position + Vector2(TILE - 2, 0), col, 5.0)
		"puddles":
			if h % 10 < 2:
				_draw_ellipse(r.position + Vector2(TILE * 0.5, TILE * 0.6), 12, 6, col)

## Scattered floor props — the biome's furniture (drawn under entities).
func _draw_floor_prop(r: Rect2, c: Vector2i, th: Dictionary) -> void:
	var props: Array = th.props
	if props.is_empty():
		return
	var h := _chash(c.x * 13, c.y * 17)
	var pick: Dictionary = props[h % props.size()]
	if h % 100 >= int(pick.chance):
		return
	var col: Color = pick.col
	var col2: Color = pick.get("col2", col)
	var ctr := r.position + Vector2(TILE * 0.5, TILE * 0.5)
	match pick.kind:
		"scrap":
			draw_rect(Rect2(ctr + Vector2(-9, 0), Vector2(11, 7)), col)
			draw_rect(Rect2(ctr + Vector2(-3, -6), Vector2(9, 6)), col2)
		"scorch":
			draw_circle(ctr, 9.0, Color(col, 0.8))
			draw_arc(ctr, 11.0, 0, TAU, 14, Color(col, 0.4), 2.0)
		"sandbag":
			draw_rect(Rect2(ctr + Vector2(-10, -1), Vector2(20, 7)), col)
			draw_rect(Rect2(ctr + Vector2(-7, -7), Vector2(14, 6)), col2)
		"paw":
			draw_circle(ctr, 2.6, col)
			draw_circle(ctr + Vector2(-4, -5), 1.5, col)
			draw_circle(ctr + Vector2(4, -5), 1.5, col)
		"pedestal":
			draw_rect(Rect2(ctr + Vector2(-6, -10), Vector2(12, 20)), col)
			draw_rect(Rect2(ctr + Vector2(-9, -13), Vector2(18, 4)), col2)
		"bottle":
			draw_rect(Rect2(ctr + Vector2(-2, -4), Vector2(5, 10)), col)
			draw_rect(Rect2(ctr + Vector2(-1, -8), Vector2(3, 4)), col2)
		"candle":
			draw_circle(ctr + Vector2(0, -4), 7.0, Color(col, 0.18))
			draw_rect(Rect2(ctr + Vector2(-2, -2), Vector2(4, 8)), Color("d8d0c0"))
			draw_circle(ctr + Vector2(0, -4), 2.2, col)
		"puddle":
			_draw_ellipse(ctr + Vector2(0, 4), 13, 6, col)
		"leaf":
			draw_circle(ctr + Vector2(-3, 1), 2.4, col)
			draw_circle(ctr + Vector2(3, -2), 2.0, col)
		"tree":
			draw_rect(Rect2(ctr + Vector2(-2, 0), Vector2(5, 10)), col2)
			draw_circle(ctr + Vector2(0, -5), 8.0, col)
		"vat":
			draw_arc(ctr, 9.0, 0, TAU, 16, col, 2.0)
			draw_circle(ctr, 6.0, Color(col2, 0.5))
		"desk":
			draw_rect(Rect2(ctr + Vector2(-11, -3), Vector2(22, 5)), col)
			draw_rect(Rect2(ctr + Vector2(-5, -9), Vector2(10, 6)), col2)
		"confetti":
			for k in 4:
				var dh := _chash(c.x * 7 + k, c.y * 11 + k)
				draw_circle(r.position + Vector2(6 + dh % 36, 6 + (dh / 13) % 36),
					1.6, col if k % 2 == 0 else col2)
		"ember":
			draw_circle(ctr, 6.0, Color(col, 0.16))
			draw_circle(ctr, 2.0, col)
		"cable":
			draw_polyline(PackedVector2Array([r.position + Vector2(2, TILE - 8),
				ctr + Vector2(-4, 2), r.position + Vector2(TILE - 4, 10)]), col, 1.6)
		"tape":
			draw_line(r.position + Vector2(2, 6), r.position + Vector2(TILE - 4, 6), col, 2.5)
		"bone":
			draw_line(ctr + Vector2(-5, 3), ctr + Vector2(5, -3), col, 2.0)
			draw_circle(ctr + Vector2(-5, 3), 1.8, col)
			draw_circle(ctr + Vector2(5, -3), 1.8, col)

## Wall décor — frames, pipes, neon, cage bars, posters.
func _draw_wall_prop(r: Rect2, c: Vector2i, th: Dictionary) -> void:
	var props: Array = th.wall_props
	if props.is_empty():
		return
	var h := _chash(c.x * 29, c.y * 23)
	var pick: Dictionary = props[h % props.size()]
	if h % 100 >= int(pick.chance):
		return
	var col: Color = pick.col
	var col2: Color = pick.get("col2", col)
	match pick.kind:
		"frame":
			draw_rect(Rect2(r.position + Vector2(10, 10), Vector2(TILE - 21, TILE - 24)), col, false, 2.0)
			draw_rect(Rect2(r.position + Vector2(15, 15), Vector2(TILE - 31, TILE - 34)), Color(col, 0.35))
		"pipe":
			draw_line(r.position + Vector2(0, 14), r.position + Vector2(TILE - 1, 14), col, 3.0)
			draw_circle(r.position + Vector2(TILE * 0.5, 14), 3.0, col)
		"neon":
			draw_rect(Rect2(r.position + Vector2(4, TILE - 10), Vector2(TILE - 9, 4)), col)
			draw_rect(Rect2(r.position + Vector2(4, TILE - 14), Vector2(TILE - 9, 10)), Color(col2, 0.18))
		"bars":
			for k in 3:
				var bx := r.position.x + 10 + k * 12
				draw_line(Vector2(bx, r.position.y + 8), Vector2(bx, r.position.y + TILE - 9), col, 2.0)
		"poster":
			draw_rect(Rect2(r.position + Vector2(12, 9), Vector2(TILE - 25, TILE - 19)), col)
			draw_rect(Rect2(r.position + Vector2(16, 13), Vector2(TILE - 33, 8)), Color(col2, 0.7))

func _draw_player(e: CombatEntity, pos: Vector2, fade: float) -> void:
	var col := COL_PLAYER; col.a = fade
	draw_circle(pos, 16, Color(0.11, 0.20, 0.25, fade))
	draw_arc(pos, 16, 0, TAU, 24, col, 2.0)
	draw_circle(pos + Vector2(0, -3), 9, Color(0.23, 0.70, 0.82, fade))
	draw_line(pos + Vector2(-11, 6), pos + Vector2(-18, -10), Color(COL_BRIGHT, fade), 3.0)
	# HP bar under your own token (green→amber→red) so danger reads at a glance.
	if e.max_hp > 0:
		var frac: float = clampf(float(e.hp) / float(e.max_hp), 0.0, 1.0)
		var hpc := COL_GREEN if frac > 0.5 else (COL_AMBER if frac > 0.25 else COL_RED)
		draw_rect(Rect2(pos.x - 17, pos.y + 18, 34, 5), Color(0.1, 0.1, 0.1, fade))
		draw_rect(Rect2(pos.x - 17, pos.y + 18, 34 * frac, 5), Color(hpc, fade))

func _draw_title(c: CanvasItem) -> void:
	c.draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	# Title
	c.draw_string(_font, Vector2(180, 230), "DUNGEON KRAULEM",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 72, COL_CYAN)
	c.draw_string(_font, Vector2(184, 274), "galaktyczne reality show z lochów",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_DIM)
	# Options (click them, or press the key)
	var has_save := Save.has_save()
	var y := 380.0
	if has_save:
		c.draw_string(_font, Vector2(184, y), "▶  Kontynuuj zjazd   [Enter]",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_BRIGHT)
		_zone(Rect2(176, y - 24, 520, 34), "title_continue")
		c.draw_string(_font, Vector2(184, y + 38), "▶  Nowy bieg (porzuca zapis)   [N]",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_AMBER)
		_zone(Rect2(176, y + 14, 520, 34), "title_new")
		y += 76
	else:
		c.draw_string(_font, Vector2(184, y), "▶  Zacznij bieg   [Enter]",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_BRIGHT)
		_zone(Rect2(176, y - 24, 520, 34), "title_start")
		y += 38
	# Achievements gallery entry
	c.draw_string(_font, Vector2(184, y + 22),
		"🏆  Osiągnięcia  (%d / %d)   [A]" % [Achievements.count_unlocked(), Achievements.total()],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_AMBER)
	_zone(Rect2(176, y - 2, 520, 32), "ach_open")
	# Loadout & meta-progression entry
	var lo := MetaCatalog.loadout()
	c.draw_string(_font, Vector2(184, y + 54),
		"🧬  Ekwipunek sezonu  (%s · %s)   [M]" % [
			MetaCatalog.def_of(lo["species"]).get("label", "?"),
			MetaCatalog.def_of(lo["origin"]).get("label", "?")],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_GREEN)
	_zone(Rect2(176, y + 32, 520, 30), "meta_open")
	c.draw_string(_font, Vector2(184, y + 82),
		"Prestiż: %d / %d pkt    ·    odblokowane opcje: %d" % [
			MetaCatalog.available_prestige(), Achievements.points_total(), Meta.unlocked_count()],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 15, ACH_TIER_COL["gold"])
	# Controls primer (mouse-first)
	c.draw_string(_font, Vector2(184, 632),
		"MYSZ:  lewy = atak / rozmowa / ruch / wybór opcji      prawy = pchnięcie wroga",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
	c.draw_string(_font, Vector2(184, 658),
		"KLAWISZE:  WSAD/strzałki ruch · Shift pchnij · Spacja czekaj · E rozbierz/rozmawiaj",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	c.draw_string(_font, Vector2(184, 678),
		"           I warsztat · T celuj w strefę · F umiejętność · 1–9 wybór · Esc zamknij",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)

func _draw_boss(pos: Vector2, fade: float, flashing: bool) -> void:
	var body := COL_RED if flashing else COL_PURPLE
	body.a = fade
	# bigger, menacing, with a crown
	draw_circle(pos, 21, Color(0.20, 0.06, 0.10, fade))
	draw_arc(pos, 21, 0, TAU, 28, body, 3.0)
	draw_circle(pos + Vector2(0, -2), 12, Color(0.62, 0.20, 0.28, fade))
	draw_string(_font, pos + Vector2(-8, -20), "♛", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_AMBER)

func _draw_npc(pos: Vector2, fade: float) -> void:
	var col := COL_PURPLE; col.a = fade
	draw_circle(pos, 15, Color(0.16, 0.10, 0.20, fade))
	draw_arc(pos, 15, 0, TAU, 22, col, 2.0)
	draw_circle(pos + Vector2(0, -3), 8, Color(0.55, 0.36, 0.66, fade))
	# a little speech-bubble dot above the head
	draw_string(_font, pos + Vector2(-4, -18), "?", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, col)

## Your pet ally: a friendly green token with a HP pip and a heart, clearly NOT
## an enemy. Distinct silhouette so the board reads at a glance.
func _draw_ally(e: CombatEntity, pos: Vector2, fade: float) -> void:
	var col := Color(0.45, 0.90, 0.55, fade)
	draw_circle(pos, 14, Color(0.08, 0.18, 0.10, fade))
	draw_arc(pos, 14, 0, TAU, 22, col, 2.0)
	draw_circle(pos + Vector2(0, -2), 7, Color(0.30, 0.70, 0.40, fade))
	draw_string(_font, pos + Vector2(-5, -16), "♥", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, col)
	# tiny HP bar so you can see when the mascot is hurting
	if e.max_hp > 0:
		var frac: float = clampf(float(e.hp) / float(e.max_hp), 0.0, 1.0)
		draw_rect(Rect2(pos.x - 14, pos.y + 16, 28, 4), Color(0.1, 0.1, 0.1, fade))
		draw_rect(Rect2(pos.x - 14, pos.y + 16, 28 * frac, 4), Color(col, fade))

## A safehouse on the board: a calm cyan tent/booth with a '+' so it reads as a
## safe spot to step into (bump it to open the menu).
func _draw_safehouse_token(pos: Vector2, fade: float) -> void:
	var col := COL_CYAN; col.a = fade
	draw_rect(Rect2(pos.x - 15, pos.y - 12, 30, 26), Color(0.10, 0.20, 0.24, fade))
	draw_rect(Rect2(pos.x - 15, pos.y - 12, 30, 26), col, false, 2.0)
	# little roof
	draw_line(pos + Vector2(-17, -12), pos + Vector2(0, -22), col, 2.0)
	draw_line(pos + Vector2(17, -12), pos + Vector2(0, -22), col, 2.0)
	draw_string(_font, pos + Vector2(-5, 8), "✚", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, col)

## A rival crawler: an amber humanoid with a star (a fellow contestant, not an NPC).
func _draw_crawler_token(pos: Vector2, fade: float) -> void:
	var col := COL_AMBER; col.a = fade
	draw_circle(pos, 15, Color(0.20, 0.15, 0.06, fade))
	draw_arc(pos, 15, 0, TAU, 22, col, 2.0)
	draw_circle(pos + Vector2(0, -3), 8, Color(0.66, 0.50, 0.20, fade))
	draw_string(_font, pos + Vector2(-5, -16), "☆", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, col)

func _draw_rat(pos: Vector2, fade: float, flashing: bool) -> void:
	var body := COL_RED if flashing else COL_RAT
	body.a = fade
	draw_line(pos + Vector2(11, 2), pos + Vector2(22, -8), body, 4.0)
	_draw_ellipse(pos, 15, 9, body)
	draw_circle(pos + Vector2(-13, 0), 7, body)

# ── Enemy silhouettes (Phase B): each template class reads at a glance ────────

## Body class from tags — shared source of truth lives on CombatEntity, since it
## drives both the silhouette here and the fighting style in the sim AI.
func _enemy_body_kind(e: CombatEntity) -> String:
	return e.body_kind()

## The counterplay line for each fighting style (shown in the target readout).
func _kind_hint(kind: String) -> String:
	match kind:
		"humanoid": return "podnosi gardę po ciosie — pchnięcie [PPM] ją łamie"
		"mech":     return "razi prądem z dystansu — zerwij linię wzroku lub doskocz"
		"spectral": return "fizyczne ciosy przenikają — żywioły i powłoki działają"
		"beast":    return "doskakuje z 2 pól — nie stój w jego linii"
		"bug":      return "gryzie mocniej w stadzie — rozdzielaj je"
		"elite":    return "poniżej połowy HP wpada w SZAŁ (+obrażenia)"
		"boss":     return "finał piętra — pełna uwaga"
	return "obserwuj i ucz się"

## Species colour: a stable hue from the monster key, around a per-class base —
## same species always matches, different species always differ.
func _enemy_hue(e: CombatEntity, kind: String) -> Color:
	var base_h := 0.0
	match kind:
		"humanoid": base_h = 0.99   # red family
		"beast":    base_h = 0.07   # brown-orange
		"bug":      base_h = 0.16   # olive
		"mech":     base_h = 0.55   # steel-cyan
		"spectral": base_h = 0.45   # pale teal
		_:          base_h = 0.99
	var h := 0
	for ch in (e.monster_key if e.monster_key != "" else e.name_pl):
		h = (h * 31 + ch.unicode_at(0)) % 1000
	var hue := fposmod(base_h + (float(h) / 1000.0 - 0.5) * 0.12, 1.0)
	return Color.from_hsv(hue, 0.55, 0.78)

func _draw_enemy(e: CombatEntity, pos: Vector2, fade: float, flashing: bool) -> void:
	var kind := _enemy_body_kind(e)
	if kind == "boss":
		_draw_boss(pos, fade, flashing)
		return
	var body := COL_RED if flashing else _enemy_hue(e, kind)
	body.a = fade
	var dark := Color(body.r * 0.45, body.g * 0.45, body.b * 0.45, fade)
	match kind:
		"humanoid":
			draw_circle(pos + Vector2(0, 2), 12, dark)
			draw_arc(pos + Vector2(0, 2), 12, 0, TAU, 18, body, 2.0)
			draw_circle(pos + Vector2(0, -9), 7, body)
			draw_line(pos + Vector2(9, 0), pos + Vector2(18, -9), body, 3.0)   # weapon
			draw_line(pos + Vector2(-10, -2), pos + Vector2(10, -2), dark, 2.0)
		"bug":
			_draw_ellipse(pos + Vector2(0, 2), 10, 6, body)
			for k in 3:
				var lx := -6.0 + k * 6.0
				draw_line(pos + Vector2(lx, 4), pos + Vector2(lx - 4, 12), body, 1.5)
				draw_line(pos + Vector2(lx, 4), pos + Vector2(lx + 4, 12), body, 1.5)
			draw_line(pos + Vector2(-3, -3), pos + Vector2(-7, -10), body, 1.2)  # antennae
			draw_line(pos + Vector2(3, -3), pos + Vector2(7, -10), body, 1.2)
		"mech":
			draw_rect(Rect2(pos + Vector2(-11, -8), Vector2(22, 18)), dark)
			draw_rect(Rect2(pos + Vector2(-11, -8), Vector2(22, 18)), body, false, 2.0)
			draw_circle(pos + Vector2(0, -2), 3.5, Color("60e0ff", fade))        # sensor eye
			draw_line(pos + Vector2(0, -8), pos + Vector2(0, -16), body, 2.0)    # antenna
			draw_line(pos + Vector2(-11, 12), pos + Vector2(11, 12), body, 3.0)  # tread
		"spectral":
			var gh := Color(body, fade * 0.55)
			var hover := sin(Time.get_ticks_msec() * 0.004 + pos.x) * 2.0
			draw_arc(pos + Vector2(0, hover), 12, PI, TAU, 14, gh, 3.0)
			_draw_ellipse(pos + Vector2(0, -4 + hover), 11, 9, gh)
			draw_circle(pos + Vector2(-4, -6 + hover), 2.0, Color(0.05, 0.05, 0.1, fade))
			draw_circle(pos + Vector2(4, -6 + hover), 2.0, Color(0.05, 0.05, 0.1, fade))
		"elite":
			_draw_ellipse(pos, 14, 10, body)
			draw_circle(pos + Vector2(-10, -4), 7, body)
			for k in 5:                                   # spiked elite ring
				var ang := -PI * 0.9 + k * (PI * 0.8 / 4.0)
				var tip := pos + Vector2(cos(ang), sin(ang)) * 20.0
				draw_line(pos + Vector2(cos(ang), sin(ang)) * 13.0, tip, COL_AMBER, 2.0)
			draw_arc(pos, 17, 0, TAU, 22, Color(COL_AMBER, fade * 0.7), 1.5)
		_:   # beast
			draw_line(pos + Vector2(11, 2), pos + Vector2(22, -8), body, 4.0)   # tail
			_draw_ellipse(pos, 15, 9, body)
			draw_circle(pos + Vector2(-13, 0), 7, body)
			draw_line(pos + Vector2(-16, -5), pos + Vector2(-13, -10), body, 2.0)  # ear
	# A damage bar appears once the enemy is hurt (mirrors the ally readout).
	if e.max_hp > 0 and e.hp < e.max_hp:
		var frac: float = clampf(float(e.hp) / float(e.max_hp), 0.0, 1.0)
		draw_rect(Rect2(pos.x - 14, pos.y + 16, 28, 4), Color(0.1, 0.1, 0.1, fade))
		draw_rect(Rect2(pos.x - 14, pos.y + 16, 28 * frac, 4), Color(COL_RED, fade))

func _draw_exits() -> void:
	if floor == null: return
	for cell in floor.rooms[floor.current]["exits"]:
		var ex: Dictionary = floor.rooms[floor.current]["exits"][cell]
		if ex.get("descend", false):
			draw_rect(Rect2(_cell_px(cell) - Vector2(TILE/2.0-3, TILE/2.0-3), Vector2(TILE-7,TILE-7)),
				Color(COL_GREEN, 0.18))
			_draw_glyph(">", cell, COL_GREEN)
		else:
			_draw_glyph("+", cell, COL_AMBER)

func _draw_minimap(c: CanvasItem) -> void:
	if floor == null: return
	var n: int = floor.rooms.size()
	var bx: float = 1280 - 28 - n * 46
	# Biome badge in its signature colour, left of the sector chips.
	if floor.biome != "":
		var th := BiomeThemes.theme_for(floor.biome)
		var lbl: String = "▌" + Routes.label_of(floor.biome)
		var lw2: float = _font.get_string_size(lbl, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
		c.draw_string(_font, Vector2(bx - lw2 - 18, 44), lbl,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 15, th.accent)
	for i in n:
		var rx: float = bx + i * 46
		var col: Color = COL_CYAN if i == floor.current else COL_DIM
		c.draw_rect(Rect2(rx, 24, 34, 30), Color(0.10, 0.12, 0.16, 0.92))
		c.draw_rect(Rect2(rx, 24, 34, 30), col, false, 2.0)
		c.draw_string(_font, Vector2(rx + 12, 45), str(i + 1),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, col)
		if i < n - 1:
			c.draw_line(Vector2(rx + 34, 39), Vector2(rx + 46, 39), COL_DIM, 1.0)

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
	var p := sim.player()
	for id in sim.entities:
		var e: CombatEntity = sim.entities[id]
		if e.faction != "enemy" or not e.is_alive(): continue
		var ep: Vector2 = _vpos.get(id, _cell_px(e.cell))
		if not e.aware:
			draw_string(_font, ep + Vector2(-10, -20), "Zzz",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
			continue
		if sim.board.is_adjacent(e.cell, p.cell):
			draw_string(_font, ep + Vector2(-16, -20), "ugryzie",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_RED)
		else:
			var step: Vector2i = e.cell + Vector2i(signi(p.cell.x-e.cell.x), signi(p.cell.y-e.cell.y))
			var sp := _cell_px(step)
			draw_rect(Rect2(sp - Vector2(TILE/2.0-2, TILE/2.0-2), Vector2(TILE-5,TILE-5)),
				Color(COL_RED, 0.16))
			draw_line(ep, sp, Color(COL_RED, 0.7), 2.0)

func _draw_preview() -> void:
	var p := sim.player()
	for dir in [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]:
		var occ := sim.board.occupant_at(p.cell + dir)
		if occ == -1 or occ == sim.player_id: continue
		var land: Vector2i = p.cell + dir + dir
		if sim.would_shock_at(land):
			var rp := _cell_px(p.cell + dir)
			var lp := _cell_px(land)
			draw_line(rp, lp, COL_CYAN, 3.0)
			draw_rect(Rect2(lp - Vector2(TILE/2.0-2, TILE/2.0-2), Vector2(TILE-5,TILE-5)),
				COL_CYAN, false, 2.0)
			draw_string(_font, lp + Vector2(-TILE, TILE/2.0+6),
				"Shift+ruch: w kałużę → prąd", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
			return

func _draw_hud(c: CanvasItem) -> void:
	var p := sim.player()
	_draw_minimap(c)
	# Title bar
	c.draw_string(_font, Vector2(40, 36),
		"PIĘTRO %d — %s  ·  Runda %d  ·  tura: %s"
		% [floor.depth if floor else 1, floor.current_name() if floor else "?", sim.round_num,
		   "TY" if sim.side == "player" else "wrogowie"],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, COL_CYAN)
	# Level + XP bar (top-right of the title row)
	var xb := Rect2(640, 24, 260, 16)
	c.draw_rect(xb, Color(0.08, 0.10, 0.13, 0.9))
	var frac: float = clampf(float(p.xp) / maxf(1.0, float(p.xp_to_next())), 0.0, 1.0)
	c.draw_rect(Rect2(xb.position, Vector2(xb.size.x * frac, xb.size.y)), COL_GAS)
	c.draw_rect(xb, COL_GRID, false, 1.0)
	var lvl_txt := "POZIOM %d   XP %d/%d" % [p.level, p.xp, p.xp_to_next()]
	if p.skill_points > 0:
		lvl_txt += "   ·   %d pkt [L]" % p.skill_points
	c.draw_string(_font, Vector2(xb.position.x, 20), lvl_txt,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_AMBER if p.skill_points > 0 else COL_DIM)
	# Who you are this run (the meta loadout)
	if p.species_key != "" and p.species_key != "species_bezimienny":
		var spn: String = MetaCatalog.def_of(p.species_key).get("label", "?")
		var ogn: String = MetaCatalog.def_of(p.origin_key).get("label", "?")
		c.draw_string(_font, Vector2(xb.position.x, 56), "Jesteś: %s  ·  %s" % [spn, ogn],
			HORIZONTAL_ALIGNMENT_LEFT, 320, 12, META_KIND_COL["species"])
	# Controls hint (mouse-first) — clipped to 580px so it can't run under the
	# top-right level/species readout.
	c.draw_string(_font, Vector2(40, 60),
		"Ruch: WSAD / LPM  ·  PPM pchnij  ·  E rozbierz  ·  I warsztat  ·  K/J/Z/O panele",
		HORIZONTAL_ALIGNMENT_LEFT, 580, 13, COL_DIM)
	# Weapon / coating / armor — led by your own HP so it's always on screen.
	var wln := "HP %d/%d   ·   Broń: nóż" % [p.hp, p.max_hp]
	if p.coating == "electric": wln += "  [PRĄD x%d]" % p.coating_charges
	elif p.coating == "poison": wln += "  [TRUCIZNA x%d]" % p.coating_charges
	if p.bonus_damage > 0:      wln += "  +%d obr." % p.bonus_damage
	wln += "   ·   AC %d" % (p.ac + p.armor_bonus())
	var worn: Array = []
	for slot in p.equipment:
		if p.equipment[slot] != null:
			worn.append((p.equipment[slot] as GameItem).name_pl)
	if not worn.is_empty():
		wln += "   ·   Pancerz: " + ", ".join(worn)
	wln += "   ·   Mana %d/%d [Z]" % [p.mana, p.max_mana]
	c.draw_string(_font, Vector2(40, 80), wln, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
	# INT stat
	var int_str := "INT %d (+%d)" % [p.int_xp, p.int_mod()]
	c.draw_string(_font, Vector2(40, 98), int_str, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	# Class + active readiness — or, before you have one, your building playstyle
	# (so the eventual class offer is visibly EARNED, not a random pop-up).
	if p.class_key != "":
		var gate := ClassFeatures.can_use_active(p, floor.depth)
		var ready := "gotowa" if bool(gate[0]) else "użyta"
		var cstr := "Klasa: %s   ·   [F] %s (%s)" % [Classes.name_of(p.class_key),
			ClassFeatures.active_name(p.class_key), ready]
		var ccol := COL_AMBER if bool(gate[0]) else COL_DIM
		c.draw_string(_font, Vector2(220, 98), cstr, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, ccol)
	else:
		c.draw_string(_font, Vector2(220, 98),
			"Styl: %s   (→ klasa)" % Classes.style_summary(p, 3),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	# Materials — icon chips instead of a text wall
	c.draw_string(_font, Vector2(40, 116), "Materiały:", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_AMBER)
	var mx := 130.0
	if sim.materials.is_empty():
		c.draw_string(_font, Vector2(mx, 116), "—", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
	for k in sim.materials:
		if mx > 760.0: break
		_draw_icon(c, str(k), Vector2(mx + 7, 111), COL_AMBER)
		var cnt := "x%d" % int(sim.materials[k])
		c.draw_string(_font, Vector2(mx + 17, 116), cnt, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_BRIGHT)
		mx += 24.0 + _font.get_string_size(cnt, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x
	# Inventory: list the actual item names (not just a count) so you can see what
	# you're carrying without opening the workshop.
	var inv_parts: Array = []
	if not floor.items.is_empty():
		var names: Array = []
		for it in floor.items:
			names.append((it as GameItem).name_pl)
		var shown: String = ", ".join(names.slice(0, 4))
		if names.size() > 4:
			shown += " +%d" % (names.size() - 4)
		inv_parts.append("Przedmioty (%d): %s" % [floor.items.size(), shown])
	if not floor.boxes.is_empty():
		inv_parts.append("Skrzynki: %d" % floor.boxes.size())
	# Companion + its ability readiness
	if floor.companion != null and floor.companion.is_alive():
		var comp: CombatEntity = floor.companion
		var ready: bool = int(comp.flags.get("ability_floor", -1)) != floor.depth
		inv_parts.append("Towarzysz: %s  [G] %s" % [comp.name_pl, "gotów" if ready else "użyty"])
	if not inv_parts.is_empty():
		c.draw_string(_font, Vector2(40, 134), " | ".join(inv_parts),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_GREEN)
	# Audience + top sponsors
	if floor.audience:
		var aud := floor.audience
		var band_col := COL_DIM
		match aud.band():
			"warming": band_col = COL_AMBER
			"hot":     band_col = COL_RED
			"viral":   band_col = COL_CYAN
		c.draw_string(_font, Vector2(40, 152),
			"Widownia: %d  [%s]" % [aud.rating, aud.band_label()],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, band_col)
	if floor.sponsors:
		var top := floor.sponsors.top_ranked(2)
		if not top.is_empty():
			var parts2: Array = []
			for skey in top:
				var sdata := floor.sponsors.get_sponsor(skey)
				var nm: String = sdata.get("name_fallback", skey).substr(0, 12)
				var gp := floor.sponsors.gift_progress(skey)
				# Show attention + progress to next gift, so you SEE the box coming.
				var prog := "  %d→%d📦" % [int(gp[0]), int(gp[1])] if int(gp[1]) > 0 else "  (max)"
				parts2.append("%s %s%s" % [nm, floor.sponsors.mood(skey), prog])
			c.draw_string(_font, Vector2(40, 168), "Sponsorzy: " + " | ".join(parts2),
				HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)
	# Focused-target readout: who you're fighting + HOW to fight it. The hint is
	# the counterplay for its body class — combat depth has to be legible.
	var foe := _focused_enemy()
	if foe != null and foe.is_alive():
		var st := "śpi" if not foe.aware else ("GARDA" if foe.has_status("guard") else "ściga cię")
		c.draw_string(_font, Vector2(40, 676),
			"%s  HP %d/%d  [%s]  ·  %s"
			% [foe.name_pl, foe.hp, foe.max_hp, st, _kind_hint(foe.body_kind())],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_AMBER)
	# Tracked floor objective (real, with progress + payout) — and a nav hint below.
	if floor != null and not floor.objective.is_empty():
		var done: bool = bool(floor.objective.get("done", false))
		c.draw_string(_font, Vector2(40, 700), "Zadanie: " + Objectives.describe(floor.objective),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_GREEN if done else COL_AMBER)
	elif _hint != "":
		c.draw_string(_font, Vector2(40, 700), "Wskazówka: " + _hint,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	# DZIENNIK log panel — screen-fixed on the right (the board no longer defines
	# screen positions; the camera frames it left of this panel).
	var lx := 830.0
	var lw := 1280 - lx - 24
	c.draw_rect(Rect2(lx, 110, lw, 360), Color(0.08, 0.10, 0.13, 0.9))
	c.draw_rect(Rect2(lx, 110, lw, 360), COL_GRID, false, 1.0)
	c.draw_string(_font, Vector2(lx + 12, 132), "DZIENNIK",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
	for i in _log.size():
		var alpha := 0.5 + 0.5 * float(i + 1) / _log.size()
		c.draw_string(_font, Vector2(lx + 12, 158 + i * 22), _log[i],
			HORIZONTAL_ALIGNMENT_LEFT, lw - 24, 14, Color(COL_BRIGHT, alpha))
	if _banner != "" and _banner_t > 0.0:
		var ba: float = clampf(_banner_t / 0.6, 0.0, 1.0)   # fade out over the last 0.6s
		c.draw_string(_font, Vector2(260, 330), _banner,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 44, Color(COL_BRIGHT, ba))
	_draw_body_readout(c, lx, lw)
	# Exactly ONE in-game modal at a time (priority order), so nothing ever stacks.
	if not _box_anim.is_empty():
		_draw_box_open(c)
	elif not _levelup.is_empty():
		_draw_levelup(c)
	elif not _event.is_empty():
		_draw_event_modal(c)
	elif not _route_offer.is_empty():
		_draw_route_offer(c)
	elif not _class_offer.is_empty():
		_draw_class_offer(c)
	elif not _dlg.is_empty():
		_draw_dialogue(c)
	elif not _safehouse.is_empty():
		_draw_safehouse(c)
	elif not _crawler.is_empty():
		_draw_crawler_modal(c)
	elif _spellbook:
		_draw_spellbook(c)
	elif not _speak.is_empty():
		_draw_speak(c)
	elif _craft_open:
		_draw_craft_panel(c)
	_draw_toasts(c)

## VS-style achievement toasts: tier-framed panels that slide in from the right,
## stack, and slide back out, with a ray-burst on entry. Gold/platinum unlocks
## also paint a brief golden vignette over the whole screen.
func _draw_toasts(c: CanvasItem) -> void:
	# Rare-unlock screen-edge burst.
	if _ach_flash > 0.0:
		var fa := _ach_flash / 0.7
		var gold := Color(1.0, 0.85, 0.3)
		c.draw_rect(Rect2(0, 0, 1280, 14), Color(gold, 0.7 * fa))
		c.draw_rect(Rect2(0, 706, 1280, 14), Color(gold, 0.7 * fa))
		c.draw_rect(Rect2(0, 0, 14, 720), Color(gold, 0.7 * fa))
		c.draw_rect(Rect2(1266, 0, 14, 720), Color(gold, 0.7 * fa))
	var W := 400.0; var H := 64.0
	for i in _toasts.size():
		var to: Dictionary = _toasts[i]
		var t: float = to["t"]; var ttl: float = to["ttl"]
		var s := 1.0
		if t < 0.35: s = t / 0.35
		elif t > ttl - 0.45: s = (ttl - t) / 0.45
		s = clampf(s, 0.0, 1.0)
		var ease := 1.0 - pow(1.0 - s, 3.0)
		var x := 1280.0 - (W + 16.0) * ease
		var y := 92.0 + i * (H + 10.0)
		var tier := str(to.get("tier", "bronze"))
		var tcol := _ach_tier_color(tier)
		# ray-burst behind the panel during the first ~0.45s
		if t < 0.45:
			var ra := (1.0 - t / 0.45)
			var cxp := Vector2(x + 30, y + H * 0.5)
			for k in 10:
				var ang := TAU * k / 10.0 + t * 2.0
				var p2 := cxp + Vector2(cos(ang), sin(ang)) * (24.0 + (1.0 - ra) * 40.0)
				c.draw_line(cxp, p2, Color(tcol, 0.5 * ra), 2.0)
		c.draw_rect(Rect2(x, y, W, H), Color(0.05, 0.05, 0.08, 0.96 * s))
		c.draw_rect(Rect2(x, y, W, H), Color(tcol, s), false, 2.5)
		# tier chip
		c.draw_rect(Rect2(x + 8, y + 8, 6, H - 16), Color(tcol, s))
		var hdr := "🏆 OSIĄGNIĘCIE — %s  ·  +%d pkt" % [_tier_label(tier), int(to.get("points", 1))]
		c.draw_string(_font, Vector2(x + 22, y + 22), hdr,
			HORIZONTAL_ALIGNMENT_LEFT, W - 30, 12, Color(tcol, s))
		c.draw_string(_font, Vector2(x + 22, y + 46), to["name"],
			HORIZONTAL_ALIGNMENT_LEFT, W - 36, 17, Color(COL_BRIGHT, s))

func _tier_label(tier: String) -> String:
	match tier:
		"bronze":   return "BRĄZ"
		"silver":   return "SREBRO"
		"gold":     return "ZŁOTO"
		"platinum": return "PLATYNA"
	return tier.to_upper()

## The achievements gallery (DCC-style list to chase): tiered frames, lifetime
## progress bars, a prestige-points header + completion bar, and scrolling.
func _draw_ach_screen(c: CanvasItem) -> void:
	c.draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	var got_n := Achievements.count_unlocked()
	var tot_n := Achievements.total()
	c.draw_string(_font, Vector2(60, 64), "OSIĄGNIĘCIA  —  %d / %d" % [got_n, tot_n],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 32, COL_AMBER)
	c.draw_string(_font, Vector2(640, 50),
		"Punkty prestiżu: %d / %d" % [Achievements.points(), Achievements.points_total()],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, ACH_TIER_COL["gold"])
	# completion bar
	var pf: float = float(got_n) / maxf(1.0, float(tot_n))
	c.draw_rect(Rect2(640, 60, 560, 14), Color(0.08, 0.10, 0.13, 0.9))
	c.draw_rect(Rect2(640, 60, 560 * pf, 14), ACH_TIER_COL["gold"])
	c.draw_rect(Rect2(640, 60, 560, 14), COL_GRID, false, 1.0)

	# ── Scrollable grid, clipped to a viewport ──
	var cols := 3
	var cw := 372.0; var ch := 74.0; var gap := 10.0
	var x0 := 60.0; var top := 96.0; var bottom := 680.0
	var order := Achievements.order()
	var rows: int = int(ceil(order.size() / float(cols)))
	var content_h := rows * (ch + gap)
	var view_h := bottom - top
	var max_scroll := maxf(0.0, content_h - view_h)
	_ach_scroll = clampf(_ach_scroll, 0.0, max_scroll)
	var cat := catalog_for_gallery()
	for i in order.size():
		var key: String = order[i]
		var a: Dictionary = cat.get(key, {})
		var got := Achievements.is_unlocked(key)
		var col := i % cols; var row := i / cols
		var x := x0 + col * (cw + gap)
		var y := top + row * (ch + gap) - _ach_scroll
		if y + ch < top or y > bottom:
			continue                       # cull rows outside the viewport
		var tier := Achievements.tier_of(key)
		var tcol := _ach_tier_color(tier)
		c.draw_rect(Rect2(x, y, cw, ch), Color(0.10, 0.11, 0.14, 0.96) if got else Color(0.05, 0.05, 0.07, 0.9))
		c.draw_rect(Rect2(x, y, cw, ch), tcol if got else COL_GRID, false, 2.0 if got else 1.0)
		c.draw_rect(Rect2(x, y, 5, ch), Color(tcol, 1.0 if got else 0.35))   # tier spine
		var hidden: bool = a.get("hidden", false)
		if got:
			c.draw_string(_font, Vector2(x + 14, y + 22), "★ " + a.get("name", key),
				HORIZONTAL_ALIGNMENT_LEFT, cw - 70, 15, COL_BRIGHT)
			c.draw_string(_font, Vector2(x + cw - 58, y + 22), _tier_label(tier),
				HORIZONTAL_ALIGNMENT_LEFT, 54, 10, tcol)
			c.draw_string(_font, Vector2(x + 14, y + 44), a.get("desc", ""),
				HORIZONTAL_ALIGNMENT_LEFT, cw - 24, 12, COL_DIM)
		else:
			var nm: String = "???" if hidden else a.get("name", key)
			c.draw_string(_font, Vector2(x + 14, y + 22), "☐ " + nm,
				HORIZONTAL_ALIGNMENT_LEFT, cw - 24, 15, COL_DIM)
			if not hidden:
				c.draw_string(_font, Vector2(x + 14, y + 44), a.get("desc", ""),
					HORIZONTAL_ALIGNMENT_LEFT, cw - 24, 12, Color(COL_DIM, 0.5))
			# progress bar for lifetime-goal achievements
			var pr := Achievements.progress(key)
			if not pr.is_empty() and not hidden:
				var frac: float = float(pr[0]) / maxf(1.0, float(pr[1]))
				c.draw_rect(Rect2(x + 14, y + ch - 14, cw - 90, 7), Color(0.08, 0.10, 0.13, 0.9))
				c.draw_rect(Rect2(x + 14, y + ch - 14, (cw - 90) * frac, 7), Color(tcol, 0.8))
				c.draw_string(_font, Vector2(x + cw - 70, y + ch - 8), "%d/%d" % [int(pr[0]), int(pr[1])],
					HORIZONTAL_ALIGNMENT_LEFT, 60, 11, COL_DIM)
	# scrollbar hint
	if max_scroll > 0.0:
		var bar_h := view_h * (view_h / content_h)
		var bar_y := top + (view_h - bar_h) * (_ach_scroll / max_scroll)
		c.draw_rect(Rect2(1240, bar_y, 5, bar_h), Color(COL_AMBER, 0.6))
	c.draw_string(_font, Vector2(60, 702), "[Esc] / klik — powrót   ·   kółko myszy / [↑][↓] — przewijaj",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
	_zone(Rect2(40, 692, 420, 26), "ach_back")

## Merged catalog accessor for the gallery (kept tiny so the draw loop reads clean).
func catalog_for_gallery() -> Dictionary:
	return Achievements.catalog()

## Loadout & meta-progression screen: pick an owned species + origin, spend
## achievement prestige to unlock more, and launch a fresh run with it all baked in.
func _draw_meta_screen(c: CanvasItem) -> void:
	c.draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	var lo := MetaCatalog.loadout()
	c.draw_string(_font, Vector2(60, 58), "EKWIPUNEK SEZONU", HORIZONTAL_ALIGNMENT_LEFT, -1, 32, COL_AMBER)
	c.draw_string(_font, Vector2(60, 86),
		"Wybrane:  %s  ·  %s" % [MetaCatalog.def_of(lo["species"]).get("label", "?"),
			MetaCatalog.def_of(lo["origin"]).get("label", "?")],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, COL_BRIGHT)
	c.draw_string(_font, Vector2(700, 58),
		"Prestiż do wydania: %d / %d" % [MetaCatalog.available_prestige(), Achievements.points_total()],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, ACH_TIER_COL["gold"])
	c.draw_string(_font, Vector2(700, 84),
		"Zdobywaj punkty osiągnięciami, wydawaj na gatunki, atuty i biomy.",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)

	# Start button
	var start := Rect2(700, 110, 300, 36)
	var shot := _hover(start)
	c.draw_rect(start, Color(0.10, 0.20, 0.12, 0.96) if shot else Color(0.08, 0.13, 0.10, 0.9))
	c.draw_rect(start, COL_GREEN, false, 2.0 if shot else 1.5)
	c.draw_string(_font, Vector2(start.position.x + 16, start.position.y + 26),
		"▶  ROZPOCZNIJ BIEG  [Enter]", HORIZONTAL_ALIGNMENT_LEFT, -1, 18, COL_GREEN)
	_zone(start, "meta_start")

	# ── Scrollable two-column list of every catalog entry ──
	var cols := 2
	var cw := 568.0; var rh := 66.0; var gap := 8.0
	var x0 := 60.0; var top := 150.0; var bottom := 686.0
	var order: Array = MetaCatalog.ORDER
	var rows: int = int(ceil(order.size() / float(cols)))
	var content_h := rows * (rh + gap)
	var max_scroll := maxf(0.0, content_h - (bottom - top))
	_meta_scroll = clampf(_meta_scroll, 0.0, max_scroll)
	for i in order.size():
		var key: String = order[i]
		var d: Dictionary = MetaCatalog.CATALOG[key]
		var kind: String = d["kind"]
		var col := i % cols; var row := i / cols
		var x := x0 + col * (cw + 16)
		var y := top + row * (rh + gap) - _meta_scroll
		if y + rh < top or y > bottom:
			continue
		var owned := MetaCatalog.is_owned(key)
		var selected: bool = (key == lo["species"] or key == lo["origin"])
		var kc: Color = META_KIND_COL.get(kind, COL_BRIGHT)
		c.draw_rect(Rect2(x, y, cw, rh), Color(0.10, 0.11, 0.14, 0.96) if owned else Color(0.05, 0.05, 0.07, 0.92))
		var frame := COL_GREEN if selected else (kc if owned else COL_GRID)
		c.draw_rect(Rect2(x, y, cw, rh), frame, false, 2.0 if (owned or selected) else 1.0)
		c.draw_rect(Rect2(x, y, 5, rh), kc)
		c.draw_string(_font, Vector2(x + 14, y + 13), MetaCatalog.KIND_LABELS.get(kind, kind),
			HORIZONTAL_ALIGNMENT_LEFT, 200, 10, kc)
		c.draw_string(_font, Vector2(x + 14, y + 32), d.get("label", key),
			HORIZONTAL_ALIGNMENT_LEFT, cw - 150, 16, COL_BRIGHT if owned else COL_DIM)
		c.draw_string(_font, Vector2(x + 14, y + 52), d.get("reward", ""),
			HORIZONTAL_ALIGNMENT_LEFT, cw - 150, 11, COL_DIM)
		# right-side action / status
		var ax := x + cw - 132
		var btn := Rect2(ax, y + 16, 120, 34)
		if owned:
			if kind == "species" or kind == "origin":
				if selected:
					c.draw_string(_font, Vector2(ax, y + 30), "✓ WYBRANY", HORIZONTAL_ALIGNMENT_LEFT, 120, 13, COL_GREEN)
				else:
					var ph := _hover(btn)
					c.draw_rect(btn, Color(kc, 0.25 if ph else 0.12))
					c.draw_rect(btn, kc, false, 1.0)
					c.draw_string(_font, Vector2(ax + 14, y + 38), "WYBIERZ", HORIZONTAL_ALIGNMENT_LEFT, 120, 13, COL_BRIGHT)
					_zone(btn, "meta_pick", 0, key)
			else:
				c.draw_string(_font, Vector2(ax, y + 30), "✓ aktywne", HORIZONTAL_ALIGNMENT_LEFT, 120, 13, kc)
		else:
			var cost := MetaCatalog.cost_of(key)
			var afford := cost <= MetaCatalog.available_prestige()
			if afford:
				var bh := _hover(btn)
				c.draw_rect(btn, Color(ACH_TIER_COL["gold"], 0.25 if bh else 0.12))
				c.draw_rect(btn, ACH_TIER_COL["gold"], false, 1.0)
				c.draw_string(_font, Vector2(ax + 8, y + 38), "KUP: %d" % cost, HORIZONTAL_ALIGNMENT_LEFT, 120, 13, ACH_TIER_COL["gold"])
				_zone(btn, "meta_buy", 0, key)
			else:
				c.draw_string(_font, Vector2(ax, y + 30), "🔒 %d pkt" % cost, HORIZONTAL_ALIGNMENT_LEFT, 120, 13, COL_DIM)
	if max_scroll > 0.0:
		var bar_h := (bottom - top) * ((bottom - top) / content_h)
		var bar_y := top + ((bottom - top) - bar_h) * (_meta_scroll / max_scroll)
		c.draw_rect(Rect2(1244, bar_y, 5, bar_h), Color(COL_AMBER, 0.6))
	# Back button (top-right, clear of the list)
	var back := Rect2(1040, 110, 120, 36)
	var bkh := _hover(back)
	c.draw_rect(back, Color(0.14, 0.10, 0.10, 0.95) if bkh else Color(0.09, 0.07, 0.07, 0.9))
	c.draw_rect(back, COL_RED if bkh else COL_GRID, false, 1.5)
	c.draw_string(_font, Vector2(back.position.x + 12, back.position.y + 26), "← powrót",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 15, COL_BRIGHT)
	_zone(back, "meta_back")
	c.draw_string(_font, Vector2(60, 706),
		"[Esc]/[M] powrót   ·   kółko / [↑][↓] przewijaj   ·   kliknij KUP by odblokować, WYBIERZ by założyć",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)

## Vampire-Survivors-style lootbox reveal: a slot reel of rarity tiles spins and
## decelerates, SNAPS onto the box's tier with a flash, then the loot pops in.
func _draw_box_open(c: CanvasItem) -> void:
	# Dim everything behind the reveal.
	c.draw_rect(Rect2(0, 0, 1280, 720), Color(0.02, 0.02, 0.04, 0.82))
	var box: GameBox = _box_anim["box"]
	var phase: String = _box_anim["phase"]
	var t: float = _box_anim["t"]
	var strip: Array = _box_anim["strip"]
	var land: int = _box_anim["land"]
	var rcol := Rarity.color(box.rarity)
	var cx := 640.0
	var reel_y := 250.0
	var tile_w := 92.0
	var tile_h := 92.0

	# Header
	c.draw_string(_font, Vector2(cx - 200, 150), box.tier_label(),
		HORIZONTAL_ALIGNMENT_CENTER, 400, 30, rcol)
	c.draw_string(_font, Vector2(cx - 200, 182), "od: " + box.source_name,
		HORIZONTAL_ALIGNMENT_CENTER, 400, 14, COL_DIM)

	# ── The reel ──
	# Ease-out cubic so it screams in then crawls to a stop on `land`.
	var p := clampf(t / BOX_SPIN, 0.0, 1.0) if phase == "spin" else 1.0
	var ease := 1.0 - pow(1.0 - p, 3.0)
	var off := land * tile_w * ease
	# light "settle" wobble at the very end of the spin
	if phase == "spin" and p > 0.93:
		off += sin(t * 40.0) * 3.0 * (1.0 - p) * 30.0
	for i in strip.size():
		var x := cx - off + i * tile_w
		if x < -tile_w or x > 1280:
			continue
		var col := Rarity.color(strip[i])
		var centered: bool = absf(x - cx) < tile_w * 0.5
		var th := tile_h * (1.12 if centered else 0.9)
		var r := Rect2(x - tile_w * 0.5 + 6, reel_y - th * 0.5, tile_w - 12, th)
		c.draw_rect(r, Color(col, 0.9 if centered else 0.5))
		c.draw_rect(r, COL_BRIGHT if centered else Color(col, 0.7), false, 3.0 if centered else 1.0)
		c.draw_string(_font, Vector2(r.position.x, reel_y + 4),
			Rarity.label(strip[i]).substr(0, 3), HORIZONTAL_ALIGNMENT_CENTER, r.size.x, 14,
			COL_BG if centered else Color(0, 0, 0, 0.5))
	# centre marker
	c.draw_rect(Rect2(cx - 52, reel_y - 60, 104, 120), Color(rcol, 0.0), false, 2.0)
	c.draw_string(_font, Vector2(cx - 10, reel_y - 66), "▼", HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_BRIGHT)

	# ── The snap flash (bigger for a lucky 3/5) ──
	var tier: int = int(_box_anim.get("tier", 1))
	if phase == "pop":
		var a := clampf(1.0 - t / BOX_POP, 0.0, 1.0)
		var flash_mul := 0.55 + (0.2 if tier >= 3 else 0.0) + (0.2 if tier >= 5 else 0.0)
		c.draw_rect(Rect2(0, 0, 1280, 720), Color(rcol, a * flash_mul))
		var sc := 30 + int((1.0 - a) * 26)
		c.draw_string(_font, Vector2(cx - 300, reel_y + 8), Rarity.label(box.rarity).to_upper(),
			HORIZONTAL_ALIGNMENT_CENTER, 600, sc, rcol)

	# ── The loot ──
	if phase == "reveal" or phase == "done":
		var entries: Array = _box_anim["entries"]
		var shown: int = int(_box_anim["reveal_n"])
		var header := "ZDOBYWASZ:"
		if tier >= 3:
			var tcol := COL_AMBER if tier == 3 else COL_GAS
			c.draw_string(_font, Vector2(cx - 300, 322),
				"SZCZĘŚCIE! ×%d" % tier, HORIZONTAL_ALIGNMENT_CENTER, 600, 30, tcol)
		c.draw_string(_font, Vector2(cx - 300, 360), header,
			HORIZONTAL_ALIGNMENT_CENTER, 600, 20, COL_BRIGHT)
		var y := 400.0
		for i in mini(shown, entries.size()):
			var e: Dictionary = entries[i]
			# pop-in scale for the most-recent piece
			var age := t - i * BOX_REVEAL_STEP
			var pop := clampf(age / 0.2, 0.0, 1.0)
			var ecol: Color = e["color"]; ecol.a = pop
			var rowy := y + i * 34
			c.draw_rect(Rect2(cx - 250, rowy - 16, 500 * pop, 28), Color(e["color"], 0.14 * pop))
			c.draw_string(_font, Vector2(cx - 240, rowy + 4), "✦  " + str(e["label"]),
				HORIZONTAL_ALIGNMENT_LEFT, 480, 18, ecol)
		if entries.is_empty():
			c.draw_string(_font, Vector2(cx - 200, 410), "(pusto — pech)",
				HORIZONTAL_ALIGNMENT_CENTER, 400, 16, COL_DIM)
	if phase == "done":
		c.draw_string(_font, Vector2(cx - 200, 660), "kliknij — odbierz",
			HORIZONTAL_ALIGNMENT_CENTER, 400, 16, COL_AMBER)
	else:
		c.draw_string(_font, Vector2(cx - 200, 660), "(kliknij — pomiń)",
			HORIZONTAL_ALIGNMENT_CENTER, 400, 13, COL_DIM)

## A dialogue-tree conversation: speaker + the node's line + the AVAILABLE options
## (numbered 1..N; skill options show your modifier vs the TT), plus the last
## skill-check result line.
func _draw_dialogue(c: CanvasItem) -> void:
	var W := 1040.0; var H := 440.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	_panel(c, Rect2(px, py, W, H), COL_PURPLE)
	var n := Dialogue.node(_dlg)
	# Speaker + relationship standing
	var tk: String = _dlg.get("tree_key", "")
	var rel: int = int(floor.player.relationships.get(tk, 0))
	var head: String = n.get("speaker", "Ktoś")
	if rel != 0:
		head += "   (%s)" % ("przyjazny" if rel > 0 else "wrogi")
	c.draw_string(_font, Vector2(px + 22, py + 32), head,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_PURPLE)
	# NPC line
	c.draw_string(_font, Vector2(px + 22, py + 64), n.get("text", ""),
		HORIZONTAL_ALIGNMENT_LEFT, W - 44, 16, COL_BRIGHT)
	# Available options (numbered by availability), skill ones annotated
	var avail := Dialogue.available_options(floor, _dlg)
	var cy := py + 150.0
	for i in avail.size():
		var opt: Dictionary = avail[i][1]
		var label: String = opt.get("label", "")
		var col := COL_AMBER
		if opt.has("skill"):
			var sk: Array = opt["skill"]
			var mod: int = floor.player.stat_mod(sk[0])
			label += "   [%s %+d vs TT %d]" % [Dialogue.STAT_PL.get(sk[0], sk[0]), mod, int(sk[1])]
			col = COL_CYAN
		var hot := _hover(Rect2(px + 20, cy - 18, W - 40, 28))
		if hot:
			c.draw_rect(Rect2(px + 20, cy - 18, W - 40, 28), Color(col, 0.12))
		c.draw_string(_font, Vector2(px + 28, cy), "%d.  %s" % [i + 1, label],
			HORIZONTAL_ALIGNMENT_LEFT, W - 56, 16, COL_BRIGHT if hot else col)
		_zone(Rect2(px + 20, cy - 18, W - 40, 28), "dlg", int(avail[i][0]))
		cy += 32.0
	# Last skill-check result
	if _dlg_info != "":
		c.draw_string(_font, Vector2(px + 22, py + H - 44), _dlg_info,
			HORIZONTAL_ALIGNMENT_LEFT, W - 44, 14, COL_GREEN)
	c.draw_string(_font, Vector2(px + 22, py + H - 18),
		"kliknij lub [1–9] wybierz   ·   [Esc] odejdź", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)

## The route gamble at the stairs: pick which biome to descend into.
func _draw_route_offer(c: CanvasItem) -> void:
	var W := 1000.0; var H := 360.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	_panel(c, Rect2(px, py, W, H), COL_GREEN)
	c.draw_string(_font, Vector2(px + 20, py + 30), "SCHODY W DÓŁ — WYBIERZ TRASĘ",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_GREEN)
	c.draw_string(_font, Vector2(px + 20, py + 54),
		"Każda trasa to inne piętro. Wybierasz raz — i schodzisz.",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	var cy := py + 84.0
	for i in _route_offer.size():
		var key: String = _route_offer[i]
		var box := Rect2(px + 16, cy, W - 32, 76)
		var hot := _hover(box)
		c.draw_rect(box, Color(0.14, 0.18, 0.13, 0.95) if hot else Color(0.10, 0.13, 0.17, 0.9))
		c.draw_rect(box, COL_GREEN if hot else COL_GRID, false, 2.0 if hot else 1.0)
		c.draw_string(_font, Vector2(px + 28, cy + 28),
			"%d.  %s" % [i + 1, Routes.label_of(key)],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 19, COL_BRIGHT)
		c.draw_string(_font, Vector2(px + 28, cy + 52), Routes.blurb_of(key),
			HORIZONTAL_ALIGNMENT_LEFT, W - 60, 14, COL_AMBER)
		_zone(box, "route", i)
		cy += 84.0

## Level-up: spend banked skill points on a stat. Click a row (or press its
## number); the modal closes when the bank runs dry, or [Esc]/the button banks it.
## Knowledge journal: every clue + rumor you've collected, with a reliability read.
func _draw_journal(c: CanvasItem) -> void:
	c.draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	var journal: Array = floor.player.flags.get("journal", [])
	c.draw_string(_font, Vector2(60, 60), "DZIENNIK — wiedza i plotki  (%d)" % journal.size(),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 30, COL_CYAN)
	if journal.is_empty():
		c.draw_string(_font, Vector2(60, 120),
			"Pusto. Czytaj tablice ogłoszeń, gadaj z rywalami, rozbieraj sprzęt — wiedza sama nie przyjdzie.",
			HORIZONTAL_ALIGNMENT_LEFT, 1100, 16, COL_DIM)
	var top := 100.0; var bottom := 680.0
	var rh := 60.0
	var content_h := journal.size() * rh
	var max_scroll := maxf(0.0, content_h - (bottom - top))
	_journal_scroll = clampf(_journal_scroll, 0.0, max_scroll)
	for i in journal.size():
		var e: Dictionary = journal[i]
		var y := top + i * rh - _journal_scroll
		if y + rh < top or y > bottom:
			continue
		var truth := float(e.get("truth", 0.5))
		var tcol := COL_GREEN if truth >= 0.8 else (COL_AMBER if truth >= 0.5 else COL_DIM)
		var kind := "ślad" if e.get("kind", "") == "clue" else "plotka"
		c.draw_rect(Rect2(60, y, 1160, rh - 6), Color(0.08, 0.10, 0.13, 0.92))
		c.draw_rect(Rect2(60, y, 1160, rh - 6), Color(tcol, 0.6), false, 1.0)
		c.draw_string(_font, Vector2(74, y + 18), "[%s · %s]" % [kind, Knowledge.reliability_label(truth)],
			HORIZONTAL_ALIGNMENT_LEFT, 300, 12, tcol)
		c.draw_string(_font, Vector2(74, y + 42), e.get("text", ""),
			HORIZONTAL_ALIGNMENT_LEFT, 1130, 14, COL_BRIGHT)
	if max_scroll > 0.0:
		c.draw_string(_font, Vector2(1160, 64), "▲▼", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
	c.draw_string(_font, Vector2(60, 702), "[J]/[Esc] zamknij   ·   kółko / [↑][↓] przewijaj",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)

## Freeform persuasion prompt: type a line at a mind, or pick an improvised one.
func _draw_speak(c: CanvasItem) -> void:
	var t = sim.entities.get(int(_speak.get("target_id", -1)))
	var tname: String = t.name_pl if t != null else "?"
	var W := 760.0; var H := 280.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	_panel(c, Rect2(px, py, W, H), COL_GAS)
	c.draw_string(_font, Vector2(px + 20, py + 32), "MÓWISZ DO: %s" % tname,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_GAS)
	if _speak.get("mode", "") == "fallback":
		c.draw_string(_font, Vector2(px + 20, py + 58), "Nic nie przychodzi do głowy? Spróbuj tak:",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
		var opts: Array = _speak.get("options", [])
		var cy := py + 84.0
		for i in opts.size():
			var box := Rect2(px + 16, cy, W - 32, 44)
			var hot := _hover(box)
			c.draw_rect(box, Color(0.10, 0.16, 0.13, 0.95) if hot else Color(0.09, 0.12, 0.10, 0.9))
			c.draw_rect(box, COL_GAS if hot else COL_GRID, false, 1.0)
			c.draw_string(_font, Vector2(px + 28, cy + 28), "%d.  %s" % [i + 1, opts[i]["text"]],
				HORIZONTAL_ALIGNMENT_LEFT, W - 50, 15, COL_BRIGHT)
			_zone(box, "speak_pick", i)
			cy += 50.0
	else:
		c.draw_string(_font, Vector2(px + 20, py + 60),
			"Powiedz coś. Cokolwiek. System sam oceni, w co celujesz.",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
		# the input line + a blinking caret
		var typed: String = _speak.get("text", "")
		var caret := "_" if (int(Time.get_ticks_msec() / 400) % 2 == 0) else " "
		c.draw_rect(Rect2(px + 20, py + 92, W - 40, 40), Color(0.03, 0.05, 0.04, 0.95))
		c.draw_rect(Rect2(px + 20, py + 92, W - 40, 40), COL_GRID, false, 1.0)
		c.draw_string(_font, Vector2(px + 30, py + 118), "> " + typed + caret,
			HORIZONTAL_ALIGNMENT_LEFT, W - 60, 17, COL_BRIGHT)
		c.draw_string(_font, Vector2(px + 20, py + H - 18),
			"[Enter] mówisz   ·   puste [Enter] = podpowiedzi   ·   [Esc] cofnij",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)

## Spellbook: cast at the nearest enemy for mana. Rows greyed when you can't pay.
func _draw_spellbook(c: CanvasItem) -> void:
	var p := sim.player()
	var W := 640.0; var H := 470.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	_panel(c, Rect2(px, py, W, H), COL_PURPLE)
	c.draw_string(_font, Vector2(px + 20, py + 32), "KSIĘGA ZAKLĘĆ", HORIZONTAL_ALIGNMENT_LEFT, -1, 24, COL_PURPLE)
	c.draw_string(_font, Vector2(px + W - 180, py + 32), "Mana: %d / %d" % [p.mana, p.max_mana],
		HORIZONTAL_ALIGNMENT_LEFT, 170, 18, COL_CYAN)
	var ks: Array = Spells.known(p)
	if ks.is_empty():
		var msg := "Maszyna nie pojmuje magii." if p.magic_affinity == "mundane" \
			else "Nie znasz jeszcze żadnych zaklęć. Znajdź zwój i naucz się go."
		c.draw_string(_font, Vector2(px + 24, py + 80), msg, HORIZONTAL_ALIGNMENT_LEFT, W - 48, 15, COL_DIM)
	var cy := py + 60.0
	var rh := 38.0
	for i in ks.size():
		var key: String = ks[i]
		var sp: Dictionary = Spells.SPELLS[key]
		var cost: int = int(sp.get("mana", 0))
		var hp_cost: int = int(sp.get("hp_cost", 0))
		var castable: bool = p.mana >= cost and (hp_cost == 0 or p.hp > hp_cost)
		var box := Rect2(px + 16, cy, W - 32, rh - 4)
		var hot := _hover(box) and castable
		c.draw_rect(box, Color(0.16, 0.12, 0.22, 0.95) if hot else Color(0.10, 0.08, 0.14, 0.9))
		c.draw_rect(box, COL_PURPLE if hot else (COL_GRID if castable else Color(COL_GRID, 0.5)), false, 1.0)
		var lcol := COL_BRIGHT if castable else COL_DIM
		var costtxt := "%d many" % cost if hp_cost == 0 else "%d HP" % hp_cost
		_draw_icon(c, "spell", Vector2(px + 30, cy + 12), Color(COL_PURPLE, 1.0 if castable else 0.4))
		c.draw_string(_font, Vector2(px + 44, cy + 16), "%d. %s  —  %s" % [i + 1, sp.get("name", key), costtxt],
			HORIZONTAL_ALIGNMENT_LEFT, W - 60, 15, lcol)
		c.draw_string(_font, Vector2(px + 28, cy + 31), sp.get("desc", ""),
			HORIZONTAL_ALIGNMENT_LEFT, W - 60, 11, COL_DIM)
		if castable:
			_zone(box, "cast", 0, key)
		cy += rh
	c.draw_string(_font, Vector2(px + 20, py + H - 16), "Klik / 1–9 rzuca w najbliższego wroga   ·   [Z]/[Esc] zamknij",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)

## Mid-floor decision beat: an intro line + two clickable forks.
func _draw_event_modal(c: CanvasItem) -> void:
	var W := 720.0; var H := 280.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	_panel(c, Rect2(px, py, W, H), COL_GAS)
	c.draw_string(_font, Vector2(px + 20, py + 32), "PRZERWA W AKCJI", HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_GAS)
	c.draw_string(_font, Vector2(px + 20, py + 60), _event.get("intro", ""),
		HORIZONTAL_ALIGNMENT_LEFT, W - 40, 15, COL_BRIGHT)
	var forks: Array = _event.get("forks", [])
	var cy := py + 96.0
	for i in forks.size():
		var box := Rect2(px + 16, cy, W - 32, 54)
		var hot := _hover(box)
		c.draw_rect(box, Color(0.10, 0.16, 0.20, 0.95) if hot else Color(0.09, 0.12, 0.15, 0.9))
		c.draw_rect(box, COL_GAS if hot else COL_GRID, false, 2.0 if hot else 1.0)
		c.draw_string(_font, Vector2(px + 28, cy + 32), "%d.  %s" % [i + 1, (forks[i] as Dictionary).get("label", "")],
			HORIZONTAL_ALIGNMENT_LEFT, W - 60, 15, COL_BRIGHT)
		_zone(box, "event_fork", i)
		cy += 62.0

## Rival-crawler parley: talk / rob / fight. Robbing is a DEX gamble; a hostile
## crawler only offers a fight.
func _draw_crawler_modal(c: CanvasItem) -> void:
	var cr = sim.entities.get(int(_crawler.get("id", -1)))
	if cr == null:
		_crawler = {}; return
	var desc: Dictionary = cr.flags.get("crawler", {})
	var hostile: bool = desc.get("disposition", "neutral") == "hostile"
	var W := 620.0; var H := 300.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	_panel(c, Rect2(px, py, W, H), COL_AMBER)
	c.draw_string(_font, Vector2(px + 20, py + 32), "RYWAL: " + cr.name_pl,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 24, COL_AMBER)
	c.draw_string(_font, Vector2(px + 20, py + 58),
		"Charakter: %s%s" % [desc.get("personality", "?"), "   ·   WROGI" if hostile else ""],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_RED if hostile else COL_DIM)
	var rows: Array = []
	if hostile:
		rows.append({"label": "Walcz (rzuca się na ciebie)", "action": "fight"})
	else:
		rows.append({"label": "Pogadaj  (+widownia)", "action": "talk"})
		rows.append({"label": "Okradnij  (ZRĘ vs 12 — albo łup, albo bójka)", "action": "rob"})
	rows.append({"label": "Zostaw go", "action": "leave"})
	var cy := py + 92.0
	for r in rows:
		var box := Rect2(px + 16, cy, W - 32, 44)
		var hot := _hover(box)
		c.draw_rect(box, Color(0.18, 0.14, 0.07, 0.95) if hot else Color(0.12, 0.10, 0.07, 0.9))
		c.draw_rect(box, COL_AMBER if hot else COL_GRID, false, 2.0 if hot else 1.0)
		c.draw_string(_font, Vector2(px + 28, cy + 28), r["label"],
			HORIZONTAL_ALIGNMENT_LEFT, W - 50, 16, COL_BRIGHT)
		_zone(box, "crawler_action", 0, r["action"])
		cy += 52.0

## Safehouse menu: spend scrap on heal / buy materials / sell loot / sponsor
## package / intel. Rows are clickable; cost shown + greyed if unaffordable.
func _draw_safehouse(c: CanvasItem) -> void:
	var sub: String = _safehouse.get("subtype", "")
	var W := 760.0; var H := 460.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	_panel(c, Rect2(px, py, W, H), COL_CYAN)
	c.draw_string(_font, Vector2(px + 20, py + 32), Safehouse.name_of(sub).to_upper(),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 24, COL_CYAN)
	c.draw_string(_font, Vector2(px + 20, py + 56), Safehouse.blurb_of(sub),
		HORIZONTAL_ALIGNMENT_LEFT, W - 40, 13, COL_DIM)
	c.draw_string(_font, Vector2(px + W - 200, py + 32), "Złom: %d" % _zlom(),
		HORIZONTAL_ALIGNMENT_LEFT, 190, 18, COL_AMBER)

	# Build the row list: fixed services + (for the black market) buy + sell rows.
	var rows: Array = []
	for s in Safehouse.services(sub):
		rows.append({"label": s["label"], "cost": int(s["cost"]), "action": s["action"], "arg": 0})
	if sub == "czarny_rynek":
		for i in Safehouse.BUY_MATS.size():
			var e: Dictionary = Safehouse.BUY_MATS[i]
			rows.append({"label": "Kup: %s" % e["mat"], "cost": int(e["price"]), "action": "buy", "arg": i})
		for i in floor.items.size():
			var it := floor.items[i] as GameItem
			rows.append({"label": "Sprzedaj: %s" % it.display_name(), "cost": -Safehouse.sell_price(it.rarity),
				"action": "sell", "arg": i})

	var cy := py + 84.0
	var rh := 34.0
	for r in rows:
		if cy > py + H - 80:
			break                                  # don't overflow the panel
		var box := Rect2(px + 16, cy, W - 32, rh - 4)
		var cost: int = int(r["cost"])
		var affordable: bool = cost <= 0 or _zlom() >= cost
		var hot := _hover(box) and affordable
		c.draw_rect(box, Color(0.12, 0.16, 0.18, 0.95) if hot else Color(0.09, 0.11, 0.13, 0.9))
		c.draw_rect(box, COL_CYAN if hot else (COL_GRID if affordable else Color(COL_GRID, 0.5)), false, 1.0)
		var lcol := COL_BRIGHT if affordable else COL_DIM
		c.draw_string(_font, Vector2(px + 28, cy + 21), r["label"], HORIZONTAL_ALIGNMENT_LEFT, W - 200, 15, lcol)
		var ctxt := "za darmo" if cost == 0 else ("+%d" % (-cost) if cost < 0 else "−%d" % cost)
		var ccol := COL_GREEN if cost < 0 else (COL_AMBER if affordable else COL_DIM)
		if cost != 0:
			_draw_icon(c, "coin", Vector2(px + W - 158, cy + 16), ccol)
		c.draw_string(_font, Vector2(px + W - 146, cy + 21), ctxt, HORIZONTAL_ALIGNMENT_LEFT, 130, 14, ccol)
		if affordable:
			_zone(box, "safe_action", int(r["arg"]), r["action"])
		cy += rh

	var close := Rect2(px + W - 150, py + H - 42, 130, 30)
	var chot := _hover(close)
	c.draw_rect(close, COL_GRID if chot else Color(0.10, 0.13, 0.17, 0.9))
	c.draw_rect(close, COL_CYAN if chot else COL_GRID, false, 1.0)
	c.draw_string(_font, Vector2(close.position.x + 14, close.position.y + 21), "Wyjdź [Esc]",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_BRIGHT)
	_zone(close, "safe_close")

func _draw_levelup(c: CanvasItem) -> void:
	var p := sim.player()
	var W := 720.0; var H := 420.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	_panel(c, Rect2(px, py, W, H), COL_AMBER)
	c.draw_string(_font, Vector2(px + 20, py + 32),
		"AWANS — POZIOM %d" % p.level, HORIZONTAL_ALIGNMENT_LEFT, -1, 24, COL_AMBER)
	c.draw_string(_font, Vector2(px + 20, py + 58),
		"Punkty do rozdania: %d   ·   wybierz cechę, którą wzmocnisz." % p.skill_points,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_BRIGHT)
	var cy := py + 84.0
	for i in SKILL_STATS.size():
		var stat: String = SKILL_STATS[i][0]
		var desc: String = SKILL_STATS[i][1]
		var box := Rect2(px + 16, cy, W - 32, 52)
		var hot := _hover(box)
		c.draw_rect(box, Color(0.18, 0.15, 0.07, 0.95) if hot else Color(0.12, 0.11, 0.08, 0.9))
		c.draw_rect(box, COL_AMBER if hot else COL_GRID, false, 2.0 if hot else 1.0)
		c.draw_string(_font, Vector2(px + 28, cy + 22),
			"%d.  %s  —  %d" % [i + 1, desc, int(p.stats.get(stat, 0))],
			HORIZONTAL_ALIGNMENT_LEFT, W - 60, 16, COL_BRIGHT)
		c.draw_string(_font, Vector2(px + 28, cy + 42),
			"obecny modyfikator: +%d" % p.stat_mod(stat),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)
		_zone(box, "levelup_stat", i, stat)
		cy += 58.0
	var done := Rect2(px + W - 180, py + H - 44, 160, 30)
	var dhot := _hover(done)
	c.draw_rect(done, COL_GRID if dhot else Color(0.10, 0.13, 0.17, 0.9))
	c.draw_rect(done, COL_AMBER if dhot else COL_GRID, false, 1.0)
	c.draw_string(_font, Vector2(done.position.x + 14, done.position.y + 21),
		"Zachowaj punkty [Esc]", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_BRIGHT)
	_zone(done, "levelup_close")

## End-of-run results screen: victory/death header, run tallies, sponsors, and
## any meta options the season unlocked.
func _draw_run_summary(c: CanvasItem) -> void:
	c.draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	var victory: bool = _summary.get("victory", false)
	var title := "FINAŁ ODCINKA" if victory else "KONIEC TRANSMISJI"
	var tcol := COL_GREEN if victory else COL_RED
	c.draw_string(_font, Vector2(120, 96), title, HORIZONTAL_ALIGNMENT_LEFT, -1, 46, tcol)
	var y := 168.0
	for line in _summary_lines:
		var col := COL_BRIGHT
		var ls := str(line)
		if ls.begins_with("  + "):
			col = COL_AMBER
		elif ls.begins_with("Sezon otwiera") or ls.begins_with("Sponsorzy") or ls.begins_with("Klasa"):
			col = COL_CYAN
		elif ls.begins_with("Konferansjer") or ls.begins_with("FINAŁ"):
			col = COL_GREEN if victory else COL_DIM
		c.draw_string(_font, Vector2(140, y), ls, HORIZONTAL_ALIGNMENT_LEFT, 1000, 18, col)
		y += 26.0
	c.draw_string(_font, Vector2(140, 690),
		"Odblokowano łącznie opcji: %d   ·   kliknij lub [Enter] — od nowa" % Meta.unlocked_count(),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
	_zone(Rect2(0, 0, 1280, 720), "summary_continue")   # click anywhere to restart

## The Syndicate's class pitch: 3 candidates, pick with number keys.
func _draw_class_offer(c: CanvasItem) -> void:
	var W := 980.0; var H := 500.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	_panel(c, Rect2(px, py, W, H), COL_AMBER)
	c.draw_string(_font, Vector2(px + 20, py + 30), "SYNDYKAT MA PROPOZYCJĘ",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_AMBER)
	c.draw_string(_font, Vector2(px + 20, py + 54),
		"Tak grałeś: %s.  Te klasy pasują najlepiej — wybierz:" %
		Classes.style_summary(floor.player, 3),
		HORIZONTAL_ALIGNMENT_LEFT, W - 40, 14, COL_DIM)
	var cy := py + 84.0
	for i in _class_offer.size():
		var key: String = _class_offer[i]
		var box := Rect2(px + 16, cy, W - 32, 118)
		var hot := _hover(box)
		c.draw_rect(box, Color(0.16, 0.14, 0.10, 0.95) if hot else Color(0.10, 0.12, 0.17, 0.9))
		c.draw_rect(box, COL_AMBER if hot else COL_GRID, false, 2.0 if hot else 1.0)
		c.draw_string(_font, Vector2(px + 28, cy + 26),
			"%d.  %s" % [i + 1, Classes.name_of(key)],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 19, COL_BRIGHT)
		c.draw_string(_font, Vector2(px + 28, cy + 48), Classes.desc_of(key),
			HORIZONTAL_ALIGNMENT_LEFT, W - 80, 14, COL_DIM)
		c.draw_string(_font, Vector2(px + 28, cy + 70),
			"Pasuje, bo: %s" % Classes.fit_reason(floor.player, key),
			HORIZONTAL_ALIGNMENT_LEFT, W - 80, 13, COL_GREEN)
		var pas := _passive_summary(key)
		c.draw_string(_font, Vector2(px + 28, cy + 92),
			"Pasywka: %s    Umiejętność: %s" % [pas, ClassFeatures.active_name(key)],
			HORIZONTAL_ALIGNMENT_LEFT, W - 80, 13, COL_CYAN)
		_zone(box, "class", i)
		cy += 126.0

func _passive_summary(key: String) -> String:
	var parts: Array = []
	var tbl: Dictionary = ClassFeatures.PASSIVES.get(key, {})
	for k in tbl:
		parts.append("%s +%d" % [k, int(tbl[k])])
	return ", ".join(parts) if not parts.is_empty() else "—"

## The large combat readout: the focused enemy's procedural body, part by part,
## colored by severity, marked with wound icons, with the aimed zone highlighted.
func _draw_body_readout(c: CanvasItem, lx: float, lw: float) -> void:
	var e := _focused_enemy()
	var top := 484.0
	c.draw_rect(Rect2(lx, top, lw, 224), Color(0.08, 0.10, 0.13, 0.9))
	c.draw_rect(Rect2(lx, top, lw, 224), COL_GRID, false, 1.0)
	if e == null:
		c.draw_string(_font, Vector2(lx + 12, top + 24), "CIAŁO — brak celu",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
		return
	var st := "śpi" if not e.aware else "ściga cię"
	c.draw_string(_font, Vector2(lx + 12, top + 22),
		"CIAŁO: %s  ·  HP %d/%d  ·  %s" % [e.name_pl, e.hp, e.max_hp, st],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
	if e.body == null:
		c.draw_string(_font, Vector2(lx + 12, top + 46),
			"(prosta istota — brak stref trafień)", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
		return
	var y := top + 48.0
	for pkey in e.body.order:
		var p: Dictionary = e.body.part(pkey)
		var sev: String = p["severity"]
		var col := _severity_color(sev)
		var aimed: bool = (pkey == _aim_zone)
		var flashing: bool = _part_flash.has("%d:%s" % [e.id, pkey])
		# Aim highlight box (click a part to aim there, no need to cycle T)
		var prect := Rect2(lx + 8, y - 13, lw - 16, 20)
		if aimed:
			c.draw_rect(prect, Color(COL_AMBER, 0.16))
		elif _hover(prect) and not p["severed"]:
			c.draw_rect(prect, Color(COL_CYAN, 0.10))
		if not p["severed"]:
			_zone(prect, "aim_part", 0, pkey)
		# Part name + severity
		var prefix := "» " if aimed else "  "
		var sev_pl: String = BodyState.SEVERITY_PL.get(sev, sev)
		var sev_txt := "—" if sev == BodyState.SEV_INTACT else sev_pl
		if p["severed"]:
			sev_txt = "odcięte"
		c.draw_string(_font, Vector2(lx + 12, y + 2), prefix + p["label_pl"],
			HORIZONTAL_ALIGNMENT_LEFT, 150, 13, COL_BRIGHT if not flashing else COL_RED)
		c.draw_string(_font, Vector2(lx + 150, y + 2), sev_txt,
			HORIZONTAL_ALIGNMENT_LEFT, 120, 13, col)
		# HP pip bar for the part
		var bx := lx + lw - 150.0
		var bw := 96.0
		var frac := float(p["hp"]) / float(maxi(1, int(p["max_hp"])))
		c.draw_rect(Rect2(bx, y - 9, bw, 10), Color(0.15, 0.15, 0.18))
		if not p["severed"]:
			c.draw_rect(Rect2(bx, y - 9, bw * clampf(frac, 0.0, 1.0), 10), col)
		# Wound icons
		var wx := bx + bw + 8.0
		for w in p["wounds"]:
			c.draw_string(_font, Vector2(wx, y + 2), _wound_glyph(w),
				HORIZONTAL_ALIGNMENT_LEFT, -1, 14, _wound_color(w))
			wx += 16.0
		y += 22.0
	# Aim hint
	c.draw_string(_font, Vector2(lx + 12, top + 210),
		"kliknij część lub [T] — celuj (teraz: %s)" % (_aim_zone_label(e)),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_AMBER)

func _severity_color(sev: String) -> Color:
	match sev:
		BodyState.SEV_INTACT:   return COL_GREEN
		BodyState.SEV_DAMAGED:  return COL_AMBER
		BodyState.SEV_CRIPPLED: return COL_GAS
		BodyState.SEV_BROKEN:   return COL_RED
	return COL_DIM

func _wound_glyph(wound: String) -> String:
	match wound:
		"burn":    return "▲"
		"shock":   return "ϟ"
		"corrode": return "≈"
		"freeze":  return "❄"
		"bleed":   return "✦"
		"sever":   return "✂"
	return "•"

func _aim_zone_label(e: CombatEntity) -> String:
	if _aim_zone == "" or e.body == null:
		return "korpus"
	var p: Dictionary = e.body.part(_aim_zone)
	return p.get("label_pl", "korpus") if not p.is_empty() else "korpus"

# ── Craft panel ───────────────────────────────────────────────────────────────

func _draw_craft_panel(c: CanvasItem) -> void:
	var W := 1160.0; var H := 560.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	# Background
	_panel(c, Rect2(px, py, W, H), COL_CYAN)
	# Title + mode tabs
	var mode_bench := _craft_mode == "bench"
	c.draw_string(_font, Vector2(px + 16, py + 24), "WARSZTAT", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_CYAN)
	var tab1_col := COL_BRIGHT if mode_bench else COL_DIM
	var tab2_col := COL_BRIGHT if not mode_bench else COL_DIM
	c.draw_string(_font, Vector2(px + 200, py + 24), "Stół",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, tab1_col)
	_zone(Rect2(px + 196, py + 6, 90, 26), "tab_bench")
	c.draw_string(_font, Vector2(px + 300, py + 24), "Kieszeń",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, tab2_col)
	_zone(Rect2(px + 296, py + 6, 110, 26), "tab_items")
	# Close button
	c.draw_string(_font, Vector2(px + W - 24, py + 24), "✕  zamknij",
		HORIZONTAL_ALIGNMENT_RIGHT, -1, 14, COL_DIM)
	_zone(Rect2(px + W - 130, py + 6, 120, 26), "craft_close")
	c.draw_line(Vector2(px + 12, py + 42), Vector2(px + W - 12, py + 42), COL_GRID, 1.0)

	if mode_bench:
		_draw_bench_panel(px, py, W, H)
	else:
		_draw_items_panel(px, py, W, H)

func _draw_bench_panel(px: float, py: float, W: float, H: float) -> void:
	var mat_keys := sim.materials.keys()
	# Left: materials list
	draw_string(_font, Vector2(px + 16, py + 54), "MATERIAŁY",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_AMBER)
	draw_string(_font, Vector2(px + 16, py + 70), "(kliknij lub cyfra = dorzuć na stół)",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 11, COL_DIM)
	for i in mat_keys.size():
		var mat: String = mat_keys[i]
		var yy := py + 90 + i * 46
		var tags := Crafting.material_tags(mat)
		var mrect := Rect2(px + 12, yy - 16, 300, 42)
		if _hover(mrect):
			draw_rect(mrect, Color(COL_CYAN, 0.10))
		draw_string(_font, Vector2(px + 16, yy),
			"%d. %s x%d" % [i + 1, mat, int(sim.materials[mat])],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 15, COL_BRIGHT)
		_zone(mrect, "bench_mat", i)
		var tag_x := px + 20
		for t in tags:
			var tw := float(_font.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x) + 16
			draw_rect(Rect2(tag_x, yy + 18, tw, 18), Color(0.12, 0.18, 0.24, 0.8), true, 0.0, false)
			draw_rect(Rect2(tag_x, yy + 18, tw, 18), COL_CYAN, false, 1.0)
			draw_string(_font, Vector2(tag_x + 8, yy + 31), t,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_CYAN)
			tag_x += tw + 4

	# Center: bench slots
	var bx := px + 340.0
	draw_string(_font, Vector2(bx, py + 54), "STÓŁ  (max 6 slotów)",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_CYAN)
	draw_string(_font, Vector2(bx, py + 70), "kliknij slot = zdejmij   ·   Wytwórz / Enter = spróbuj",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 11, COL_DIM)
	for i in 6:
		var sx := bx + (i % 3) * 150.0
		var sy := py + 90.0 + (i / 3) * 80.0
		var filled := i < _bench_slots.size()
		var srect := Rect2(sx, sy, 140, 68)
		var hot := filled and _hover(srect)
		var bc := (COL_RED if hot else COL_CYAN) if filled else COL_GRID
		draw_rect(srect, Color(0.20, 0.12, 0.14, 0.9) if hot else Color(0.10, 0.14, 0.20, 0.9))
		draw_rect(srect, bc, false, 2.0)
		if filled:
			draw_string(_font, Vector2(sx + 70, sy + 34), _bench_slots[i],
				HORIZONTAL_ALIGNMENT_CENTER, -1, 15, COL_BRIGHT)
			draw_string(_font, Vector2(sx + 70, sy + 54), "(zdejmij)" if hot else "",
				HORIZONTAL_ALIGNMENT_CENTER, -1, 11, COL_RED)
			_zone(srect, "bench_remove", i)
		else:
			draw_string(_font, Vector2(sx + 70, sy + 38), "pusty",
				HORIZONTAL_ALIGNMENT_CENTER, -1, 13, COL_DIM)
	# Wytwórz button (bottom-left, clear of the preview column)
	if not _bench_slots.is_empty():
		var wb := Rect2(px + 16, py + H - 64, 300, 36)
		var wh := _hover(wb)
		draw_rect(wb, Color(0.12, 0.22, 0.14, 0.95) if wh else Color(0.10, 0.16, 0.11, 0.9))
		draw_rect(wb, COL_GREEN, false, 2.0)
		draw_string(_font, Vector2(px + 166, py + H - 40), "WYTWÓRZ",
			HORIZONTAL_ALIGNMENT_CENTER, -1, 18, COL_GREEN)
		_zone(wb, "bench_attempt")

	# Preview block
	var preview_y := py + 270.0
	if not _bench_preview.is_empty():
		var rule: Variant = _bench_preview.get("rule")
		var dc: int = _bench_preview.get("dc", 0)
		var stab: int = _bench_preview.get("stability_pct", 0)
		var fuzzy: String = _bench_preview.get("fuzzy_desc", "")
		var known: bool = _bench_preview.get("known", false)
		var risk: String = _bench_preview.get("risk_label", "")
		# Fuzzy description
		draw_string(_font, Vector2(bx, preview_y), fuzzy,
			HORIZONTAL_ALIGNMENT_LEFT, 440, 14, COL_BRIGHT)
		draw_string(_font, Vector2(bx, preview_y + 24),
			"Próba: k20 + INT vs DC %d%s" % [dc, "  (przepis znany)" if known else ""],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
		# Stability bar
		var bar_w := 280.0
		draw_string(_font, Vector2(bx, preview_y + 48), "Stabilność",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)
		draw_rect(Rect2(bx + 90, preview_y + 42, bar_w, 14),
			Color(0.15, 0.12, 0.10), true, 0.0, false)
		draw_rect(Rect2(bx + 90, preview_y + 42, bar_w * stab / 100.0, 14),
			COL_AMBER, true, 0.0, false)
		draw_string(_font, Vector2(bx + 90 + bar_w + 6, preview_y + 53),
			"%d%%" % stab, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_BRIGHT)
		# Risk label
		draw_string(_font, Vector2(bx, preview_y + 68),
			"Ryzyko: " + risk, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_RED)
		# Outcome tiers
		var tiers: Array = _bench_preview.get("tiers", [])
		var tier_colors := [COL_GREEN, COL_BRIGHT, COL_AMBER, COL_DIM, COL_RED]
		for i in tiers.size():
			var tier_name: String = tiers[i][0]; var tier_desc: String = tiers[i][1]
			draw_string(_font, Vector2(bx, preview_y + 96 + i * 20), tier_name,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 13, tier_colors[i], TextServer.JUSTIFICATION_NONE)
			draw_string(_font, Vector2(bx + 90, preview_y + 96 + i * 20), tier_desc,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 13, tier_colors[i])

	# Right: recipe book
	var rx := px + 820.0
	draw_string(_font, Vector2(rx, py + 54), "TWOJE RECEPTURY",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_GREEN)
	if floor.discovered_recipes.is_empty():
		draw_string(_font, Vector2(rx, py + 80), "Brak. Eksperymentuj tagami.",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	else:
		for i in floor.discovered_recipes.size():
			var rec: Dictionary = floor.discovered_recipes[i]
			var ry2 := py + 78 + i * 42
			draw_string(_font, Vector2(rx, ry2), "+ " + rec.get("name", "?"),
				HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_GREEN)
			var tag_str: String = ", ".join(rec.get("tags", []))
			draw_string(_font, Vector2(rx + 14, ry2 + 18), tag_str,
				HORIZONTAL_ALIGNMENT_LEFT, 310, 11, COL_DIM)
	draw_string(_font, Vector2(px + 14, py + H - 20),
		"Nie znasz przepisów na starcie. Eksperymentujesz tagami; co uda się raz — zapamiętujesz.",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)

func _draw_items_panel(px: float, py: float, W: float, _H: float) -> void:
	var cy := py + 60.0
	# Items
	draw_string(_font, Vector2(px + 16, cy), "PRZEDMIOTY",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_BRIGHT)
	cy += 22
	if floor.items.is_empty():
		draw_string(_font, Vector2(px + 16, cy), "Brak.", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
		cy += 20
	else:
		for i in floor.items.size():
			var item := floor.items[i] as GameItem
			var rcol := Rarity.color(item.rarity)
			var irect := Rect2(px + 12, cy - 16, W - 24, 34)
			if _hover(irect):
				draw_rect(irect, Color(rcol, 0.12))
			draw_string(_font, Vector2(px + 16, cy),
				"%d. %s   — użyj" % [i + 1, item.display_name()],
				HORIZONTAL_ALIGNMENT_LEFT, -1, 14, rcol)
			draw_string(_font, Vector2(px + 30, cy + 16), item.short_desc(),
				HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)
			_zone(irect, "item_use", i)
			cy += 36
	cy += 10
	draw_line(Vector2(px + 12, cy), Vector2(px + W - 12, cy), COL_GRID, 1.0)
	cy += 12
	# Boxes
	draw_string(_font, Vector2(px + 16, cy), "SKRZYNKI",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_AMBER)
	cy += 22
	if floor.boxes.is_empty():
		draw_string(_font, Vector2(px + 16, cy), "Brak.", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	else:
		for i in floor.boxes.size():
			var box := floor.boxes[i] as GameBox
			var bcol := Rarity.color(box.rarity)
			var brect := Rect2(px + 12, cy - 16, W - 24, 26)
			if _hover(brect):
				draw_rect(brect, Color(bcol, 0.12))
			draw_string(_font, Vector2(px + 16, cy),
				"%d. %s   — otwórz" % [i + 1 + floor.items.size(), box.display_name()],
				HORIZONTAL_ALIGNMENT_LEFT, -1, 14, bcol)
			_zone(brect, "box_open", i)
			cy += 26
	draw_string(_font, Vector2(px + 16, cy + 20),
		"kliknij przedmiot = użyj · kliknij skrzynkę = otwórz · ([1–9] / Enter też działają)",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)
