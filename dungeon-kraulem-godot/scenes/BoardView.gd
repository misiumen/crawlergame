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

func _ready() -> void:
	_font = ThemeDB.fallback_font
	set_process(true)
	queue_redraw()                   # show the title; a run starts on a keypress
	set_process(true)

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
	_hint = data.get("hint", "")
	_aim_zone = ""; sim.aim_zone = ""
	_attach_bodies()
	_recenter()
	_reset_visuals()
	_spawn_safehouse()
	_maybe_spawn_crawler()
	_arm_floor_traits()            # re-arm per-floor species traits (e.g. first strike)
	sim.refill_mana()              # mana tops up each floor
	floor.objective = Objectives.pick(next_depth, _narr_rng)   # a fresh segment goal
	_log_push("Piętro %d — %s." % [next_depth, Routes.label_of(biome_key)])
	_ach_descend(next_depth)
	if next_depth >= FINAL_FLOOR: _unlock_ach("reach_final")
	_award_xp(12 + next_depth * 6)   # surviving a floor is worth real XP
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
	var bw: int = sim.board.w * TILE
	var bh: int = sim.board.h * TILE
	_origin = Vector2((1280 - bw) / 2.0 - 140, (720 - bh) / 2.0 + 10)

func _reset_visuals() -> void:
	if floor != null:
		_ach_recipes_seen = floor.discovered_recipes.size()   # baseline for recipe-goal tracking
	_vpos.clear(); _vtarget.clear(); _flash.clear(); _dying.clear(); _floaters.clear()
	for id in sim.entities:
		var c: Vector2 = _cell_px(sim.entities[id].cell)
		_vpos[id] = c
		_vtarget[id] = c
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
	_log_push("Przechodzisz do: %s." % r.get("name", "?"))

func _cell_px(c: Vector2i) -> Vector2:
	return _origin + Vector2(c.x * TILE + TILE / 2.0, c.y * TILE + TILE / 2.0)

# ── Input ─────────────────────────────────────────────────────────────────────

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_mouse = (event as InputEventMouseMotion).position
		queue_redraw()
		return
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
		if kc == KEY_ESCAPE or kc == KEY_A:
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

	# Results screen: Enter starts a fresh run.
	if not _summary.is_empty():
		if kc == KEY_ENTER or kc == KEY_KP_ENTER:
			_summary = {}; _summary_lines = []; _done = false
			_build()
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

	# Knowledge journal: scroll + close.
	if _journal_screen:
		if kc == KEY_ESCAPE or kc == KEY_J:
			_journal_screen = false; queue_redraw()
		elif kc == KEY_DOWN: _journal_scroll += 80.0; queue_redraw()
		elif kc == KEY_UP:   _journal_scroll = maxf(0.0, _journal_scroll - 80.0); queue_redraw()
		return

	# Spellbook grabs input: number keys cast, Esc closes.
	if _spellbook:
		if kc == KEY_ESCAPE or kc == KEY_Z:
			_spellbook = false; queue_redraw(); return
		var si := kc - KEY_1
		if si >= 0 and si < Spells.ORDER.size():
			_cast_spell(Spells.ORDER[si])
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
		and _safehouse.is_empty() and _crawler.is_empty() and not _spellbook and not _journal_screen

## Viewport pixel -> board cell.
func _cell_from_mouse(pos: Vector2) -> Vector2i:
	var local := pos - _origin
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
	var i: int = int(z.get("i", 0))
	match z.get("kind", ""):
		"title_continue", "title_start": _build()
		"title_new":         Save.clear(); _build()
		"summary_continue":  _summary = {}; _summary_lines = []; _done = false; _build()
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
	_animate(sim.bench_attempt(_bench_slots))
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
			"craft_attempt":
				var oc: String = e.get("outcome", "")
				if oc == "sukces" or oc == "krytyk": _unlock_ach("rzemieslnik_z_paniki")
				if oc == "krytyk": _unlock_ach("dzielo_mistrzowskie")
				if oc == "backfire": _unlock_ach("inzynieria_odwagi")
				if oc == "czesciowy": _unlock_ach("obrzydliwe_ale_dziala")
			"trap_armed":
				_unlock_ach("pulapka_z_niczego")
			"death":
				if p.run_kills >= 1: _unlock_ach("pierwsza_krew")
				var t = sim.entities.get(e.get("target"))
				if t != null and t.faction == "enemy":
					enemy_died = true
					if "boss" in t.tags: _unlock_ach("boss_padl_pierwszy")
					elif "miniboss" in t.tags: _unlock_ach("klepacz_minibossow")
			"systemic":
				if e.get("element") == "electric": sys_electric = true
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
	for it in floor.items:
		if (it as GameItem).rarity == Rarity.LEGENDARY: _unlock_ach("widzialem_legende")
		elif (it as GameItem).rarity == Rarity.EPIC: _unlock_ach("niezwykly_zbieracz")
		if (it as GameItem).category == GameItem.CAT_MEDICAL: _unlock_ach("apteka_w_plecaku")
	# a sponsor really likes you
	if floor.sponsors != null:
		for k in floor.sponsors.all_keys():
			if floor.sponsors.get_attention(k) >= 10:
				_unlock_ach("markowy_uczestnik"); break

func _ach_descend(depth: int) -> void:
	if depth >= 2: _unlock_ach("dno_jeszcze_dalej")
	if depth >= 5: _unlock_ach("piaty_set")
	if depth >= 10: _unlock_ach("dziesiate_pietro")

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
	return out

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
	_animate(sim.player_move(dir))
	_advance_floor_turn()
	_check_transition()

func handle_shove(dir: Vector2i) -> void:
	_animate(sim.player_shove(dir))
	_advance_floor_turn()

func handle_wait() -> void:
	_animate(sim.player_wait())
	_advance_floor_turn()

func handle_interact() -> void:
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
			"damage":
				var tid: int = e["target"]
				_flash[tid] = 0.24
				var col: Color = COL_CYAN if e.get("dmg_type") == "electric" else COL_RED
				_add_floater(tid, "-%d" % e["amount"], col)
				_shake = maxf(_shake, 5.0 if e["amount"] >= 12 else 2.5)
				if e.get("zone", "") != "":
					_part_flash["%d:%s" % [tid, e["zone"]]] = 0.4
			"body_hit":
				var wound: String = e.get("wound", "")
				if e.get("severed", false):
					_add_floater(e["target"], "AMPUTACJA: " + e.get("label", ""), COL_RED)
					_shake = maxf(_shake, 7.0)
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
					_shake = maxf(_shake, 6.0)
			"death":
				_dying[e["target"]] = 1.0
			"miss":
				_add_floater(e["target"], "pudło", COL_DIM)
			"salvage":
				_dying[e["target"]] = 1.0
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
					"krytyk":    _narrate("clever_craft")
					"sukces":    _narrate("craft_success")
					"czesciowy": _narrate("craft_partial")
					"porazka":   _narrate("craft_fail")
					"backfire":  _narrate("craft_critical_fail")
			"backfire_desc":
				_add_floater(sim.player_id, e.get("desc", "backfire"), COL_RED)
				_shake = maxf(_shake, 4.0)
			"coating_applied":
				_add_floater(sim.player_id, "+powłoka x%d" % e["charges"], COL_CYAN)
			"heal":
				_add_floater(sim.player_id, "+%d HP" % e["amount"], COL_GREEN)
			"weapon_upgrade":
				_add_floater(sim.player_id, "+%d obr." % e["bonus"], COL_AMBER)
			"xp":
				_add_floater(sim.player_id, "+%d XP" % e["amount"], COL_GAS)
			"level_up":
				_on_level_up(e)
			"armor_equipped":
				_add_floater(sim.player_id, "+%d AC" % e.get("ac_bonus", 1), COL_CYAN)
				_log_push("Zakładasz: %s. Pancerz +%d AC (%s)." % [
					e.get("name", "?"), e.get("ac_bonus", 1), e.get("slot", "ciało")])
			"recipe_learned":
				if not e.get("known", false):
					_add_floater(sim.player_id, "+przepis", COL_GREEN)
					_log_push("Nowy przepis: %s." % e.get("name", "?"))
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
				_log_push("Rzucasz: %s." % e.get("name", "?"))
				_shake = maxf(_shake, 3.0)
			"cast_blocked":
				_log_push(str(e.get("reason", "Nie możesz teraz rzucić.")))
			"scrap_found":
				_add_floater(sim.player_id, "+%d złom" % int(e.get("amount", 0)), COL_AMBER)
			"marked":
				if int(e.get("id", -1)) != -1:
					_add_floater(int(e["id"]), "CEL!", COL_CYAN)
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
func _add_banner(txt: String) -> void:
	_banner = txt

func _add_floater(id: int, text: String, color: Color) -> void:
	var pos: Vector2 = _vpos.get(id, _cell_px(Vector2i.ZERO))
	_floaters.append({"pos": pos, "text": text, "color": color, "age": 0.0, "ttl": 0.95})

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
	queue_redraw()

## Advance the lootbox-opening reveal through its phases.
func _tick_box_anim(dt: float) -> void:
	if _box_anim.is_empty():
		return
	_box_anim["t"] = float(_box_anim["t"]) + dt
	var t: float = _box_anim["t"]
	match _box_anim["phase"]:
		"spin":
			if t >= BOX_SPIN:
				_box_anim["phase"] = "pop"; _box_anim["t"] = 0.0
				_shake = maxf(_shake, 9.0)        # the SNAP
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

func _draw() -> void:
	_click_zones.clear()   # rebuilt below to match exactly what's drawn this frame
	if _meta_screen:
		_draw_meta_screen()
		_draw_toasts()
		return
	if _journal_screen and sim != null:
		_draw_journal()
		_draw_toasts()
		return
	if _ach_screen:
		_draw_ach_screen()
		_draw_toasts()
		return
	if _title:
		_draw_title()
		_draw_toasts()
		return
	if sim == null: return
	if not _summary.is_empty():
		_draw_run_summary()
		_draw_toasts()
		return
	draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	var sh := Vector2(randf_range(-_shake, _shake), randf_range(-_shake, _shake))
	draw_set_transform(sh, 0.0, Vector2.ONE)
	var b: Board = sim.board
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
		var fade: float = _dying.get(id, 1.0)
		var flashing := _flash.has(id)
		if e.faction == "player":      _draw_player(pos, fade)
		elif e.faction == "safehouse": _draw_safehouse_token(pos, fade)
		elif e.faction == "crawler":   _draw_crawler_token(pos, fade)
		elif e.faction == "ally":      _draw_ally(e, pos, fade)
		elif e.faction == "object":    _draw_object(e, pos, fade)
		elif e.faction == "npc":       _draw_npc(pos, fade)
		elif "boss" in e.tags:         _draw_boss(pos, fade, flashing)
		else:                          _draw_rat(pos, fade, flashing)
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

func _draw_title() -> void:
	draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	# Title
	draw_string(_font, Vector2(180, 230), "DUNGEON KRAULEM",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 72, COL_CYAN)
	draw_string(_font, Vector2(184, 274), "galaktyczne reality show z lochów",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_DIM)
	# Options (click them, or press the key)
	var has_save := Save.has_save()
	var y := 380.0
	if has_save:
		draw_string(_font, Vector2(184, y), "▶  Kontynuuj zjazd   [Enter]",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_BRIGHT)
		_zone(Rect2(176, y - 24, 520, 34), "title_continue")
		draw_string(_font, Vector2(184, y + 38), "▶  Nowy bieg (porzuca zapis)   [N]",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_AMBER)
		_zone(Rect2(176, y + 14, 520, 34), "title_new")
		y += 76
	else:
		draw_string(_font, Vector2(184, y), "▶  Zacznij bieg   [Enter]",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_BRIGHT)
		_zone(Rect2(176, y - 24, 520, 34), "title_start")
		y += 38
	# Achievements gallery entry
	draw_string(_font, Vector2(184, y + 22),
		"🏆  Osiągnięcia  (%d / %d)   [A]" % [Achievements.count_unlocked(), Achievements.total()],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_AMBER)
	_zone(Rect2(176, y - 2, 520, 32), "ach_open")
	# Loadout & meta-progression entry
	var lo := MetaCatalog.loadout()
	draw_string(_font, Vector2(184, y + 54),
		"🧬  Ekwipunek sezonu  (%s · %s)   [M]" % [
			MetaCatalog.def_of(lo["species"]).get("label", "?"),
			MetaCatalog.def_of(lo["origin"]).get("label", "?")],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_GREEN)
	_zone(Rect2(176, y + 32, 520, 30), "meta_open")
	draw_string(_font, Vector2(184, y + 82),
		"Prestiż: %d / %d pkt    ·    odblokowane opcje: %d" % [
			MetaCatalog.available_prestige(), Achievements.points_total(), Meta.unlocked_count()],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 15, ACH_TIER_COL["gold"])
	# Controls primer (mouse-first)
	draw_string(_font, Vector2(184, 632),
		"MYSZ:  lewy = atak / rozmowa / ruch / wybór opcji      prawy = pchnięcie wroga",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
	draw_string(_font, Vector2(184, 658),
		"KLAWISZE:  WSAD/strzałki ruch · Shift pchnij · Spacja czekaj · E rozbierz/rozmawiaj",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	draw_string(_font, Vector2(184, 678),
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

func _draw_minimap() -> void:
	if floor == null: return
	var n: int = floor.rooms.size()
	var bx: float = 1280 - 28 - n * 64
	for i in n:
		var rx: float = bx + i * 64
		var col: Color = COL_CYAN if i == floor.current else COL_DIM
		draw_rect(Rect2(rx, 24, 52, 30), Color(0.10, 0.12, 0.16, 0.92))
		draw_rect(Rect2(rx, 24, 52, 30), col, false, 2.0)
		draw_string(_font, Vector2(rx + 8, 44), floor.rooms[i]["name"].substr(0, 5),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 12, col)
		if i < n - 1:
			draw_line(Vector2(rx + 52, 39), Vector2(rx + 64, 39), COL_DIM, 1.0)

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

func _draw_hud() -> void:
	var p := sim.player()
	_draw_minimap()
	# Title bar
	draw_string(_font, Vector2(40, 36),
		"PIĘTRO %d — %s  ·  Runda %d  ·  tura: %s"
		% [floor.depth if floor else 1, floor.current_name() if floor else "?", sim.round_num,
		   "TY" if sim.side == "player" else "wrogowie"],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, COL_CYAN)
	# Level + XP bar (top-right of the title row)
	var xb := Rect2(640, 24, 260, 16)
	draw_rect(xb, Color(0.08, 0.10, 0.13, 0.9))
	var frac: float = clampf(float(p.xp) / maxf(1.0, float(p.xp_to_next())), 0.0, 1.0)
	draw_rect(Rect2(xb.position, Vector2(xb.size.x * frac, xb.size.y)), COL_GAS)
	draw_rect(xb, COL_GRID, false, 1.0)
	var lvl_txt := "POZIOM %d   XP %d/%d" % [p.level, p.xp, p.xp_to_next()]
	if p.skill_points > 0:
		lvl_txt += "   ·   %d pkt [L]" % p.skill_points
	draw_string(_font, Vector2(xb.position.x, 20), lvl_txt,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_AMBER if p.skill_points > 0 else COL_DIM)
	# Who you are this run (the meta loadout)
	if p.species_key != "" and p.species_key != "species_bezimienny":
		var spn: String = MetaCatalog.def_of(p.species_key).get("label", "?")
		var ogn: String = MetaCatalog.def_of(p.origin_key).get("label", "?")
		draw_string(_font, Vector2(xb.position.x, 56), "Jesteś: %s  ·  %s" % [spn, ogn],
			HORIZONTAL_ALIGNMENT_LEFT, 320, 12, META_KIND_COL["species"])
	# Controls hint (mouse-first)
	draw_string(_font, Vector2(40, 60),
		"LPM akcja · PPM pchnij · WSAD ruch · Spacja czekaj · E rozbierz · I warsztat · F klasa · G towarzysz · Z zaklęcia · J dziennik",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	# Weapon / coating / armor
	var wln := "Broń: nóż"
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
	draw_string(_font, Vector2(40, 80), wln, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
	# INT stat
	var int_str := "INT %d (+%d)" % [p.int_xp, p.int_mod()]
	draw_string(_font, Vector2(40, 98), int_str, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	# Class + active readiness — or, before you have one, your building playstyle
	# (so the eventual class offer is visibly EARNED, not a random pop-up).
	if p.class_key != "":
		var gate := ClassFeatures.can_use_active(p, floor.depth)
		var ready := "gotowa" if bool(gate[0]) else "użyta"
		var cstr := "Klasa: %s   ·   [F] %s (%s)" % [Classes.name_of(p.class_key),
			ClassFeatures.active_name(p.class_key), ready]
		var ccol := COL_AMBER if bool(gate[0]) else COL_DIM
		draw_string(_font, Vector2(220, 98), cstr, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, ccol)
	else:
		draw_string(_font, Vector2(220, 98),
			"Styl: %s   (→ klasa)" % Classes.style_summary(p, 3),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	# Materials
	var mats: Array = []
	for k in sim.materials:
		mats.append("%s x%d" % [k, sim.materials[k]])
	draw_string(_font, Vector2(40, 116),
		"Materiały: " + ("—" if mats.is_empty() else ", ".join(mats)),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_AMBER)
	# Inventory: items + boxes
	var inv_parts: Array = []
	if not floor.items.is_empty():
		inv_parts.append("Przedmioty: %d" % floor.items.size())
	if not floor.boxes.is_empty():
		inv_parts.append("Skrzynki: %d" % floor.boxes.size())
	# Companion + its ability readiness
	if floor.companion != null and floor.companion.is_alive():
		var c: CombatEntity = floor.companion
		var ready: bool = int(c.flags.get("ability_floor", -1)) != floor.depth
		inv_parts.append("Towarzysz: %s  [G] %s" % [c.name_pl, "gotów" if ready else "użyty"])
	if not inv_parts.is_empty():
		draw_string(_font, Vector2(40, 134), " | ".join(inv_parts),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_GREEN)
	# Audience + top sponsors
	if floor.audience:
		var aud := floor.audience
		var band_col := COL_DIM
		match aud.band():
			"warming": band_col = COL_AMBER
			"hot":     band_col = COL_RED
			"viral":   band_col = COL_CYAN
		draw_string(_font, Vector2(40, 152),
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
			draw_string(_font, Vector2(40, 168), "Sponsorzy: " + " | ".join(parts2),
				HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)
	# Target readout
	var rat: CombatEntity = sim.entities.get(2)
	if rat != null and rat.is_alive():
		var st := "śpi" if not rat.aware else "ściga cię"
		draw_string(_font, Vector2(40, 676),
			"%s  HP %d/%d  [%s]  ·  gruba skóra, słaby na PRĄD"
			% [rat.name_pl, rat.hp, rat.max_hp, st],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_AMBER)
	# Tracked floor objective (real, with progress + payout) — and a nav hint below.
	if floor != null and not floor.objective.is_empty():
		var done: bool = bool(floor.objective.get("done", false))
		draw_string(_font, Vector2(40, 700), "Zadanie: " + Objectives.describe(floor.objective),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_GREEN if done else COL_AMBER)
	elif _hint != "":
		draw_string(_font, Vector2(40, 700), "Wskazówka: " + _hint,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	# DZIENNIK log panel
	var lx := _origin.x + sim.board.w * TILE + 24
	var lw := 1280 - lx - 24
	draw_rect(Rect2(lx, 110, lw, 360), Color(0.08, 0.10, 0.13, 0.9))
	draw_rect(Rect2(lx, 110, lw, 360), COL_GRID, false, 1.0)
	draw_string(_font, Vector2(lx + 12, 132), "DZIENNIK",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
	for i in _log.size():
		var alpha := 0.5 + 0.5 * float(i + 1) / _log.size()
		draw_string(_font, Vector2(lx + 12, 158 + i * 22), _log[i],
			HORIZONTAL_ALIGNMENT_LEFT, lw - 24, 14, Color(COL_BRIGHT, alpha))
	if _banner != "":
		draw_string(_font, Vector2(_origin.x + 120, _origin.y + 160), _banner,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 44, COL_BRIGHT)
	_draw_body_readout(lx, lw)
	if _craft_open:
		_draw_craft_panel()
	if not _class_offer.is_empty():
		_draw_class_offer()
	if not _route_offer.is_empty():
		_draw_route_offer()
	if not _dlg.is_empty():
		_draw_dialogue()
	if not _box_anim.is_empty():
		_draw_box_open()
	if not _levelup.is_empty():
		_draw_levelup()
	if not _safehouse.is_empty():
		_draw_safehouse()
	if not _crawler.is_empty():
		_draw_crawler_modal()
	if _spellbook:
		_draw_spellbook()
	_draw_toasts()

## VS-style achievement toasts: tier-framed panels that slide in from the right,
## stack, and slide back out, with a ray-burst on entry. Gold/platinum unlocks
## also paint a brief golden vignette over the whole screen.
func _draw_toasts() -> void:
	# Rare-unlock screen-edge burst.
	if _ach_flash > 0.0:
		var fa := _ach_flash / 0.7
		var gold := Color(1.0, 0.85, 0.3)
		draw_rect(Rect2(0, 0, 1280, 14), Color(gold, 0.7 * fa))
		draw_rect(Rect2(0, 706, 1280, 14), Color(gold, 0.7 * fa))
		draw_rect(Rect2(0, 0, 14, 720), Color(gold, 0.7 * fa))
		draw_rect(Rect2(1266, 0, 14, 720), Color(gold, 0.7 * fa))
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
				draw_line(cxp, p2, Color(tcol, 0.5 * ra), 2.0)
		draw_rect(Rect2(x, y, W, H), Color(0.05, 0.05, 0.08, 0.96 * s))
		draw_rect(Rect2(x, y, W, H), Color(tcol, s), false, 2.5)
		# tier chip
		draw_rect(Rect2(x + 8, y + 8, 6, H - 16), Color(tcol, s))
		var hdr := "🏆 OSIĄGNIĘCIE — %s  ·  +%d pkt" % [_tier_label(tier), int(to.get("points", 1))]
		draw_string(_font, Vector2(x + 22, y + 22), hdr,
			HORIZONTAL_ALIGNMENT_LEFT, W - 30, 12, Color(tcol, s))
		draw_string(_font, Vector2(x + 22, y + 46), to["name"],
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
func _draw_ach_screen() -> void:
	draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	var got_n := Achievements.count_unlocked()
	var tot_n := Achievements.total()
	draw_string(_font, Vector2(60, 64), "OSIĄGNIĘCIA  —  %d / %d" % [got_n, tot_n],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 32, COL_AMBER)
	draw_string(_font, Vector2(640, 50),
		"Punkty prestiżu: %d / %d" % [Achievements.points(), Achievements.points_total()],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, ACH_TIER_COL["gold"])
	# completion bar
	var pf: float = float(got_n) / maxf(1.0, float(tot_n))
	draw_rect(Rect2(640, 60, 560, 14), Color(0.08, 0.10, 0.13, 0.9))
	draw_rect(Rect2(640, 60, 560 * pf, 14), ACH_TIER_COL["gold"])
	draw_rect(Rect2(640, 60, 560, 14), COL_GRID, false, 1.0)

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
		draw_rect(Rect2(x, y, cw, ch), Color(0.10, 0.11, 0.14, 0.96) if got else Color(0.05, 0.05, 0.07, 0.9))
		draw_rect(Rect2(x, y, cw, ch), tcol if got else COL_GRID, false, 2.0 if got else 1.0)
		draw_rect(Rect2(x, y, 5, ch), Color(tcol, 1.0 if got else 0.35))   # tier spine
		var hidden: bool = a.get("hidden", false)
		if got:
			draw_string(_font, Vector2(x + 14, y + 22), "★ " + a.get("name", key),
				HORIZONTAL_ALIGNMENT_LEFT, cw - 70, 15, COL_BRIGHT)
			draw_string(_font, Vector2(x + cw - 58, y + 22), _tier_label(tier),
				HORIZONTAL_ALIGNMENT_LEFT, 54, 10, tcol)
			draw_string(_font, Vector2(x + 14, y + 44), a.get("desc", ""),
				HORIZONTAL_ALIGNMENT_LEFT, cw - 24, 12, COL_DIM)
		else:
			var nm: String = "???" if hidden else a.get("name", key)
			draw_string(_font, Vector2(x + 14, y + 22), "☐ " + nm,
				HORIZONTAL_ALIGNMENT_LEFT, cw - 24, 15, COL_DIM)
			if not hidden:
				draw_string(_font, Vector2(x + 14, y + 44), a.get("desc", ""),
					HORIZONTAL_ALIGNMENT_LEFT, cw - 24, 12, Color(COL_DIM, 0.5))
			# progress bar for lifetime-goal achievements
			var pr := Achievements.progress(key)
			if not pr.is_empty() and not hidden:
				var frac: float = float(pr[0]) / maxf(1.0, float(pr[1]))
				draw_rect(Rect2(x + 14, y + ch - 14, cw - 90, 7), Color(0.08, 0.10, 0.13, 0.9))
				draw_rect(Rect2(x + 14, y + ch - 14, (cw - 90) * frac, 7), Color(tcol, 0.8))
				draw_string(_font, Vector2(x + cw - 70, y + ch - 8), "%d/%d" % [int(pr[0]), int(pr[1])],
					HORIZONTAL_ALIGNMENT_LEFT, 60, 11, COL_DIM)
	# scrollbar hint
	if max_scroll > 0.0:
		var bar_h := view_h * (view_h / content_h)
		var bar_y := top + (view_h - bar_h) * (_ach_scroll / max_scroll)
		draw_rect(Rect2(1240, bar_y, 5, bar_h), Color(COL_AMBER, 0.6))
	draw_string(_font, Vector2(60, 702), "[Esc] / klik — powrót   ·   kółko myszy / [↑][↓] — przewijaj",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
	_zone(Rect2(40, 692, 420, 26), "ach_back")

## Merged catalog accessor for the gallery (kept tiny so the draw loop reads clean).
func catalog_for_gallery() -> Dictionary:
	return Achievements.catalog()

## Loadout & meta-progression screen: pick an owned species + origin, spend
## achievement prestige to unlock more, and launch a fresh run with it all baked in.
func _draw_meta_screen() -> void:
	draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	var lo := MetaCatalog.loadout()
	draw_string(_font, Vector2(60, 58), "EKWIPUNEK SEZONU", HORIZONTAL_ALIGNMENT_LEFT, -1, 32, COL_AMBER)
	draw_string(_font, Vector2(60, 86),
		"Wybrane:  %s  ·  %s" % [MetaCatalog.def_of(lo["species"]).get("label", "?"),
			MetaCatalog.def_of(lo["origin"]).get("label", "?")],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, COL_BRIGHT)
	draw_string(_font, Vector2(700, 58),
		"Prestiż do wydania: %d / %d" % [MetaCatalog.available_prestige(), Achievements.points_total()],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 18, ACH_TIER_COL["gold"])
	draw_string(_font, Vector2(700, 84),
		"Zdobywaj punkty osiągnięciami, wydawaj na gatunki, atuty i biomy.",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)

	# Start button
	var start := Rect2(700, 110, 300, 36)
	var shot := _hover(start)
	draw_rect(start, Color(0.10, 0.20, 0.12, 0.96) if shot else Color(0.08, 0.13, 0.10, 0.9))
	draw_rect(start, COL_GREEN, false, 2.0 if shot else 1.5)
	draw_string(_font, Vector2(start.position.x + 16, start.position.y + 26),
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
		draw_rect(Rect2(x, y, cw, rh), Color(0.10, 0.11, 0.14, 0.96) if owned else Color(0.05, 0.05, 0.07, 0.92))
		var frame := COL_GREEN if selected else (kc if owned else COL_GRID)
		draw_rect(Rect2(x, y, cw, rh), frame, false, 2.0 if (owned or selected) else 1.0)
		draw_rect(Rect2(x, y, 5, rh), kc)
		draw_string(_font, Vector2(x + 14, y + 13), MetaCatalog.KIND_LABELS.get(kind, kind),
			HORIZONTAL_ALIGNMENT_LEFT, 200, 10, kc)
		draw_string(_font, Vector2(x + 14, y + 32), d.get("label", key),
			HORIZONTAL_ALIGNMENT_LEFT, cw - 150, 16, COL_BRIGHT if owned else COL_DIM)
		draw_string(_font, Vector2(x + 14, y + 52), d.get("reward", ""),
			HORIZONTAL_ALIGNMENT_LEFT, cw - 150, 11, COL_DIM)
		# right-side action / status
		var ax := x + cw - 132
		var btn := Rect2(ax, y + 16, 120, 34)
		if owned:
			if kind == "species" or kind == "origin":
				if selected:
					draw_string(_font, Vector2(ax, y + 30), "✓ WYBRANY", HORIZONTAL_ALIGNMENT_LEFT, 120, 13, COL_GREEN)
				else:
					var ph := _hover(btn)
					draw_rect(btn, Color(kc, 0.25 if ph else 0.12))
					draw_rect(btn, kc, false, 1.0)
					draw_string(_font, Vector2(ax + 14, y + 38), "WYBIERZ", HORIZONTAL_ALIGNMENT_LEFT, 120, 13, COL_BRIGHT)
					_zone(btn, "meta_pick", 0, key)
			else:
				draw_string(_font, Vector2(ax, y + 30), "✓ aktywne", HORIZONTAL_ALIGNMENT_LEFT, 120, 13, kc)
		else:
			var cost := MetaCatalog.cost_of(key)
			var afford := cost <= MetaCatalog.available_prestige()
			if afford:
				var bh := _hover(btn)
				draw_rect(btn, Color(ACH_TIER_COL["gold"], 0.25 if bh else 0.12))
				draw_rect(btn, ACH_TIER_COL["gold"], false, 1.0)
				draw_string(_font, Vector2(ax + 8, y + 38), "KUP: %d" % cost, HORIZONTAL_ALIGNMENT_LEFT, 120, 13, ACH_TIER_COL["gold"])
				_zone(btn, "meta_buy", 0, key)
			else:
				draw_string(_font, Vector2(ax, y + 30), "🔒 %d pkt" % cost, HORIZONTAL_ALIGNMENT_LEFT, 120, 13, COL_DIM)
	if max_scroll > 0.0:
		var bar_h := (bottom - top) * ((bottom - top) / content_h)
		var bar_y := top + ((bottom - top) - bar_h) * (_meta_scroll / max_scroll)
		draw_rect(Rect2(1244, bar_y, 5, bar_h), Color(COL_AMBER, 0.6))
	# Back button (top-right, clear of the list)
	var back := Rect2(1040, 110, 120, 36)
	var bkh := _hover(back)
	draw_rect(back, Color(0.14, 0.10, 0.10, 0.95) if bkh else Color(0.09, 0.07, 0.07, 0.9))
	draw_rect(back, COL_RED if bkh else COL_GRID, false, 1.5)
	draw_string(_font, Vector2(back.position.x + 12, back.position.y + 26), "← powrót",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 15, COL_BRIGHT)
	_zone(back, "meta_back")
	draw_string(_font, Vector2(60, 706),
		"[Esc]/[M] powrót   ·   kółko / [↑][↓] przewijaj   ·   kliknij KUP by odblokować, WYBIERZ by założyć",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)

## Vampire-Survivors-style lootbox reveal: a slot reel of rarity tiles spins and
## decelerates, SNAPS onto the box's tier with a flash, then the loot pops in.
func _draw_box_open() -> void:
	# Dim everything behind the reveal.
	draw_rect(Rect2(0, 0, 1280, 720), Color(0.02, 0.02, 0.04, 0.82))
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
	draw_string(_font, Vector2(cx - 200, 150), box.tier_label(),
		HORIZONTAL_ALIGNMENT_CENTER, 400, 30, rcol)
	draw_string(_font, Vector2(cx - 200, 182), "od: " + box.source_name,
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
		draw_rect(r, Color(col, 0.9 if centered else 0.5))
		draw_rect(r, COL_BRIGHT if centered else Color(col, 0.7), false, 3.0 if centered else 1.0)
		draw_string(_font, Vector2(r.position.x, reel_y + 4),
			Rarity.label(strip[i]).substr(0, 3), HORIZONTAL_ALIGNMENT_CENTER, r.size.x, 14,
			COL_BG if centered else Color(0, 0, 0, 0.5))
	# centre marker
	draw_rect(Rect2(cx - 52, reel_y - 60, 104, 120), Color(rcol, 0.0), false, 2.0)
	draw_string(_font, Vector2(cx - 10, reel_y - 66), "▼", HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_BRIGHT)

	# ── The snap flash (bigger for a lucky 3/5) ──
	var tier: int = int(_box_anim.get("tier", 1))
	if phase == "pop":
		var a := clampf(1.0 - t / BOX_POP, 0.0, 1.0)
		var flash_mul := 0.55 + (0.2 if tier >= 3 else 0.0) + (0.2 if tier >= 5 else 0.0)
		draw_rect(Rect2(0, 0, 1280, 720), Color(rcol, a * flash_mul))
		var sc := 30 + int((1.0 - a) * 26)
		draw_string(_font, Vector2(cx - 300, reel_y + 8), Rarity.label(box.rarity).to_upper(),
			HORIZONTAL_ALIGNMENT_CENTER, 600, sc, rcol)

	# ── The loot ──
	if phase == "reveal" or phase == "done":
		var entries: Array = _box_anim["entries"]
		var shown: int = int(_box_anim["reveal_n"])
		var header := "ZDOBYWASZ:"
		if tier >= 3:
			var tcol := COL_AMBER if tier == 3 else COL_GAS
			draw_string(_font, Vector2(cx - 300, 322),
				"SZCZĘŚCIE! ×%d" % tier, HORIZONTAL_ALIGNMENT_CENTER, 600, 30, tcol)
		draw_string(_font, Vector2(cx - 300, 360), header,
			HORIZONTAL_ALIGNMENT_CENTER, 600, 20, COL_BRIGHT)
		var y := 400.0
		for i in mini(shown, entries.size()):
			var e: Dictionary = entries[i]
			# pop-in scale for the most-recent piece
			var age := t - i * BOX_REVEAL_STEP
			var pop := clampf(age / 0.2, 0.0, 1.0)
			var ecol: Color = e["color"]; ecol.a = pop
			var rowy := y + i * 34
			draw_rect(Rect2(cx - 250, rowy - 16, 500 * pop, 28), Color(e["color"], 0.14 * pop))
			draw_string(_font, Vector2(cx - 240, rowy + 4), "✦  " + str(e["label"]),
				HORIZONTAL_ALIGNMENT_LEFT, 480, 18, ecol)
		if entries.is_empty():
			draw_string(_font, Vector2(cx - 200, 410), "(pusto — pech)",
				HORIZONTAL_ALIGNMENT_CENTER, 400, 16, COL_DIM)
	if phase == "done":
		draw_string(_font, Vector2(cx - 200, 660), "kliknij — odbierz",
			HORIZONTAL_ALIGNMENT_CENTER, 400, 16, COL_AMBER)
	else:
		draw_string(_font, Vector2(cx - 200, 660), "(kliknij — pomiń)",
			HORIZONTAL_ALIGNMENT_CENTER, 400, 13, COL_DIM)

## A dialogue-tree conversation: speaker + the node's line + the AVAILABLE options
## (numbered 1..N; skill options show your modifier vs the TT), plus the last
## skill-check result line.
func _draw_dialogue() -> void:
	var W := 1040.0; var H := 440.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	draw_rect(Rect2(px, py, W, H), Color(0.07, 0.07, 0.11, 0.98))
	draw_rect(Rect2(px, py, W, H), COL_PURPLE, false, 2.0)
	var n := Dialogue.node(_dlg)
	# Speaker + relationship standing
	var tk: String = _dlg.get("tree_key", "")
	var rel: int = int(floor.player.relationships.get(tk, 0))
	var head: String = n.get("speaker", "Ktoś")
	if rel != 0:
		head += "   (%s)" % ("przyjazny" if rel > 0 else "wrogi")
	draw_string(_font, Vector2(px + 22, py + 32), head,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_PURPLE)
	# NPC line
	draw_string(_font, Vector2(px + 22, py + 64), n.get("text", ""),
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
			draw_rect(Rect2(px + 20, cy - 18, W - 40, 28), Color(col, 0.12))
		draw_string(_font, Vector2(px + 28, cy), "%d.  %s" % [i + 1, label],
			HORIZONTAL_ALIGNMENT_LEFT, W - 56, 16, COL_BRIGHT if hot else col)
		_zone(Rect2(px + 20, cy - 18, W - 40, 28), "dlg", int(avail[i][0]))
		cy += 32.0
	# Last skill-check result
	if _dlg_info != "":
		draw_string(_font, Vector2(px + 22, py + H - 44), _dlg_info,
			HORIZONTAL_ALIGNMENT_LEFT, W - 44, 14, COL_GREEN)
	draw_string(_font, Vector2(px + 22, py + H - 18),
		"kliknij lub [1–9] wybierz   ·   [Esc] odejdź", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)

## The route gamble at the stairs: pick which biome to descend into.
func _draw_route_offer() -> void:
	var W := 1000.0; var H := 360.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	draw_rect(Rect2(px, py, W, H), Color(0.07, 0.09, 0.12, 0.98))
	draw_rect(Rect2(px, py, W, H), COL_GREEN, false, 2.0)
	draw_string(_font, Vector2(px + 20, py + 30), "SCHODY W DÓŁ — WYBIERZ TRASĘ",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_GREEN)
	draw_string(_font, Vector2(px + 20, py + 54),
		"Każda trasa to inne piętro. Wybierasz raz — i schodzisz.",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_DIM)
	var cy := py + 84.0
	for i in _route_offer.size():
		var key: String = _route_offer[i]
		var box := Rect2(px + 16, cy, W - 32, 76)
		var hot := _hover(box)
		draw_rect(box, Color(0.14, 0.18, 0.13, 0.95) if hot else Color(0.10, 0.13, 0.17, 0.9))
		draw_rect(box, COL_GREEN if hot else COL_GRID, false, 2.0 if hot else 1.0)
		draw_string(_font, Vector2(px + 28, cy + 28),
			"%d.  %s" % [i + 1, Routes.label_of(key)],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 19, COL_BRIGHT)
		draw_string(_font, Vector2(px + 28, cy + 52), Routes.blurb_of(key),
			HORIZONTAL_ALIGNMENT_LEFT, W - 60, 14, COL_AMBER)
		_zone(box, "route", i)
		cy += 84.0

## Level-up: spend banked skill points on a stat. Click a row (or press its
## number); the modal closes when the bank runs dry, or [Esc]/the button banks it.
## Knowledge journal: every clue + rumor you've collected, with a reliability read.
func _draw_journal() -> void:
	draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	var journal: Array = floor.player.flags.get("journal", [])
	draw_string(_font, Vector2(60, 60), "DZIENNIK — wiedza i plotki  (%d)" % journal.size(),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 30, COL_CYAN)
	if journal.is_empty():
		draw_string(_font, Vector2(60, 120),
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
		draw_rect(Rect2(60, y, 1160, rh - 6), Color(0.08, 0.10, 0.13, 0.92))
		draw_rect(Rect2(60, y, 1160, rh - 6), Color(tcol, 0.6), false, 1.0)
		draw_string(_font, Vector2(74, y + 18), "[%s · %s]" % [kind, Knowledge.reliability_label(truth)],
			HORIZONTAL_ALIGNMENT_LEFT, 300, 12, tcol)
		draw_string(_font, Vector2(74, y + 42), e.get("text", ""),
			HORIZONTAL_ALIGNMENT_LEFT, 1130, 14, COL_BRIGHT)
	if max_scroll > 0.0:
		draw_string(_font, Vector2(1160, 64), "▲▼", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
	draw_string(_font, Vector2(60, 702), "[J]/[Esc] zamknij   ·   kółko / [↑][↓] przewijaj",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)

## Spellbook: cast at the nearest enemy for mana. Rows greyed when you can't pay.
func _draw_spellbook() -> void:
	var p := sim.player()
	var W := 640.0; var H := 470.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	draw_rect(Rect2(px, py, W, H), Color(0.07, 0.05, 0.11, 0.98))
	draw_rect(Rect2(px, py, W, H), COL_PURPLE, false, 2.0)
	draw_string(_font, Vector2(px + 20, py + 32), "KSIĘGA ZAKLĘĆ", HORIZONTAL_ALIGNMENT_LEFT, -1, 24, COL_PURPLE)
	draw_string(_font, Vector2(px + W - 180, py + 32), "Mana: %d / %d" % [p.mana, p.max_mana],
		HORIZONTAL_ALIGNMENT_LEFT, 170, 18, COL_CYAN)
	var cy := py + 60.0
	var rh := 38.0
	for i in Spells.ORDER.size():
		var key: String = Spells.ORDER[i]
		var sp: Dictionary = Spells.SPELLS[key]
		var cost: int = int(sp.get("mana", 0))
		var hp_cost: int = int(sp.get("hp_cost", 0))
		var castable: bool = p.mana >= cost and (hp_cost == 0 or p.hp > hp_cost)
		var box := Rect2(px + 16, cy, W - 32, rh - 4)
		var hot := _hover(box) and castable
		draw_rect(box, Color(0.16, 0.12, 0.22, 0.95) if hot else Color(0.10, 0.08, 0.14, 0.9))
		draw_rect(box, COL_PURPLE if hot else (COL_GRID if castable else Color(COL_GRID, 0.5)), false, 1.0)
		var lcol := COL_BRIGHT if castable else COL_DIM
		var costtxt := "%d many" % cost if hp_cost == 0 else "%d HP" % hp_cost
		draw_string(_font, Vector2(px + 28, cy + 16), "%d. %s  —  %s" % [i + 1, sp.get("name", key), costtxt],
			HORIZONTAL_ALIGNMENT_LEFT, W - 60, 15, lcol)
		draw_string(_font, Vector2(px + 28, cy + 31), sp.get("desc", ""),
			HORIZONTAL_ALIGNMENT_LEFT, W - 60, 11, COL_DIM)
		if castable:
			_zone(box, "cast", 0, key)
		cy += rh
	draw_string(_font, Vector2(px + 20, py + H - 16), "Klik / 1–9 rzuca w najbliższego wroga   ·   [Z]/[Esc] zamknij",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)

## Rival-crawler parley: talk / rob / fight. Robbing is a DEX gamble; a hostile
## crawler only offers a fight.
func _draw_crawler_modal() -> void:
	var cr = sim.entities.get(int(_crawler.get("id", -1)))
	if cr == null:
		_crawler = {}; return
	var desc: Dictionary = cr.flags.get("crawler", {})
	var hostile: bool = desc.get("disposition", "neutral") == "hostile"
	var W := 620.0; var H := 300.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	draw_rect(Rect2(px, py, W, H), Color(0.10, 0.08, 0.05, 0.98))
	draw_rect(Rect2(px, py, W, H), COL_AMBER, false, 2.0)
	draw_string(_font, Vector2(px + 20, py + 32), "RYWAL: " + cr.name_pl,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 24, COL_AMBER)
	draw_string(_font, Vector2(px + 20, py + 58),
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
		draw_rect(box, Color(0.18, 0.14, 0.07, 0.95) if hot else Color(0.12, 0.10, 0.07, 0.9))
		draw_rect(box, COL_AMBER if hot else COL_GRID, false, 2.0 if hot else 1.0)
		draw_string(_font, Vector2(px + 28, cy + 28), r["label"],
			HORIZONTAL_ALIGNMENT_LEFT, W - 50, 16, COL_BRIGHT)
		_zone(box, "crawler_action", 0, r["action"])
		cy += 52.0

## Safehouse menu: spend scrap on heal / buy materials / sell loot / sponsor
## package / intel. Rows are clickable; cost shown + greyed if unaffordable.
func _draw_safehouse() -> void:
	var sub: String = _safehouse.get("subtype", "")
	var W := 760.0; var H := 460.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	draw_rect(Rect2(px, py, W, H), Color(0.06, 0.08, 0.10, 0.98))
	draw_rect(Rect2(px, py, W, H), COL_CYAN, false, 2.0)
	draw_string(_font, Vector2(px + 20, py + 32), Safehouse.name_of(sub).to_upper(),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 24, COL_CYAN)
	draw_string(_font, Vector2(px + 20, py + 56), Safehouse.blurb_of(sub),
		HORIZONTAL_ALIGNMENT_LEFT, W - 40, 13, COL_DIM)
	draw_string(_font, Vector2(px + W - 200, py + 32), "Złom: %d" % _zlom(),
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
		draw_rect(box, Color(0.12, 0.16, 0.18, 0.95) if hot else Color(0.09, 0.11, 0.13, 0.9))
		draw_rect(box, COL_CYAN if hot else (COL_GRID if affordable else Color(COL_GRID, 0.5)), false, 1.0)
		var lcol := COL_BRIGHT if affordable else COL_DIM
		draw_string(_font, Vector2(px + 28, cy + 21), r["label"], HORIZONTAL_ALIGNMENT_LEFT, W - 200, 15, lcol)
		var ctxt := "za darmo" if cost == 0 else ("+%d złomu" % (-cost) if cost < 0 else "−%d złomu" % cost)
		var ccol := COL_GREEN if cost < 0 else (COL_AMBER if affordable else COL_DIM)
		draw_string(_font, Vector2(px + W - 150, cy + 21), ctxt, HORIZONTAL_ALIGNMENT_LEFT, 130, 14, ccol)
		if affordable:
			_zone(box, "safe_action", int(r["arg"]), r["action"])
		cy += rh

	var close := Rect2(px + W - 150, py + H - 42, 130, 30)
	var chot := _hover(close)
	draw_rect(close, COL_GRID if chot else Color(0.10, 0.13, 0.17, 0.9))
	draw_rect(close, COL_CYAN if chot else COL_GRID, false, 1.0)
	draw_string(_font, Vector2(close.position.x + 14, close.position.y + 21), "Wyjdź [Esc]",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_BRIGHT)
	_zone(close, "safe_close")

func _draw_levelup() -> void:
	var p := sim.player()
	var W := 720.0; var H := 420.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	draw_rect(Rect2(px, py, W, H), Color(0.08, 0.07, 0.04, 0.98))
	draw_rect(Rect2(px, py, W, H), COL_AMBER, false, 2.0)
	draw_string(_font, Vector2(px + 20, py + 32),
		"AWANS — POZIOM %d" % p.level, HORIZONTAL_ALIGNMENT_LEFT, -1, 24, COL_AMBER)
	draw_string(_font, Vector2(px + 20, py + 58),
		"Punkty do rozdania: %d   ·   wybierz cechę, którą wzmocnisz." % p.skill_points,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_BRIGHT)
	var cy := py + 84.0
	for i in SKILL_STATS.size():
		var stat: String = SKILL_STATS[i][0]
		var desc: String = SKILL_STATS[i][1]
		var box := Rect2(px + 16, cy, W - 32, 52)
		var hot := _hover(box)
		draw_rect(box, Color(0.18, 0.15, 0.07, 0.95) if hot else Color(0.12, 0.11, 0.08, 0.9))
		draw_rect(box, COL_AMBER if hot else COL_GRID, false, 2.0 if hot else 1.0)
		draw_string(_font, Vector2(px + 28, cy + 22),
			"%d.  %s  —  %d" % [i + 1, desc, int(p.stats.get(stat, 0))],
			HORIZONTAL_ALIGNMENT_LEFT, W - 60, 16, COL_BRIGHT)
		draw_string(_font, Vector2(px + 28, cy + 42),
			"obecny modyfikator: +%d" % p.stat_mod(stat),
			HORIZONTAL_ALIGNMENT_LEFT, -1, 12, COL_DIM)
		_zone(box, "levelup_stat", i, stat)
		cy += 58.0
	var done := Rect2(px + W - 180, py + H - 44, 160, 30)
	var dhot := _hover(done)
	draw_rect(done, COL_GRID if dhot else Color(0.10, 0.13, 0.17, 0.9))
	draw_rect(done, COL_AMBER if dhot else COL_GRID, false, 1.0)
	draw_string(_font, Vector2(done.position.x + 14, done.position.y + 21),
		"Zachowaj punkty [Esc]", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, COL_BRIGHT)
	_zone(done, "levelup_close")

## End-of-run results screen: victory/death header, run tallies, sponsors, and
## any meta options the season unlocked.
func _draw_run_summary() -> void:
	draw_rect(Rect2(0, 0, 1280, 720), COL_BG)
	var victory: bool = _summary.get("victory", false)
	var title := "FINAŁ ODCINKA" if victory else "KONIEC TRANSMISJI"
	var tcol := COL_GREEN if victory else COL_RED
	draw_string(_font, Vector2(120, 96), title, HORIZONTAL_ALIGNMENT_LEFT, -1, 46, tcol)
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
		draw_string(_font, Vector2(140, y), ls, HORIZONTAL_ALIGNMENT_LEFT, 1000, 18, col)
		y += 26.0
	draw_string(_font, Vector2(140, 690),
		"Odblokowano łącznie opcji: %d   ·   kliknij lub [Enter] — od nowa" % Meta.unlocked_count(),
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
	_zone(Rect2(0, 0, 1280, 720), "summary_continue")   # click anywhere to restart

## The Syndicate's class pitch: 3 candidates, pick with number keys.
func _draw_class_offer() -> void:
	var W := 980.0; var H := 500.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	draw_rect(Rect2(px, py, W, H), Color(0.07, 0.08, 0.12, 0.98))
	draw_rect(Rect2(px, py, W, H), COL_AMBER, false, 2.0)
	draw_string(_font, Vector2(px + 20, py + 30), "SYNDYKAT MA PROPOZYCJĘ",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 22, COL_AMBER)
	draw_string(_font, Vector2(px + 20, py + 54),
		"Tak grałeś: %s.  Te klasy pasują najlepiej — wybierz:" %
		Classes.style_summary(floor.player, 3),
		HORIZONTAL_ALIGNMENT_LEFT, W - 40, 14, COL_DIM)
	var cy := py + 84.0
	for i in _class_offer.size():
		var key: String = _class_offer[i]
		var box := Rect2(px + 16, cy, W - 32, 118)
		var hot := _hover(box)
		draw_rect(box, Color(0.16, 0.14, 0.10, 0.95) if hot else Color(0.10, 0.12, 0.17, 0.9))
		draw_rect(box, COL_AMBER if hot else COL_GRID, false, 2.0 if hot else 1.0)
		draw_string(_font, Vector2(px + 28, cy + 26),
			"%d.  %s" % [i + 1, Classes.name_of(key)],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 19, COL_BRIGHT)
		draw_string(_font, Vector2(px + 28, cy + 48), Classes.desc_of(key),
			HORIZONTAL_ALIGNMENT_LEFT, W - 80, 14, COL_DIM)
		draw_string(_font, Vector2(px + 28, cy + 70),
			"Pasuje, bo: %s" % Classes.fit_reason(floor.player, key),
			HORIZONTAL_ALIGNMENT_LEFT, W - 80, 13, COL_GREEN)
		var pas := _passive_summary(key)
		draw_string(_font, Vector2(px + 28, cy + 92),
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
func _draw_body_readout(lx: float, lw: float) -> void:
	var e := _focused_enemy()
	var top := 484.0
	draw_rect(Rect2(lx, top, lw, 224), Color(0.08, 0.10, 0.13, 0.9))
	draw_rect(Rect2(lx, top, lw, 224), COL_GRID, false, 1.0)
	if e == null:
		draw_string(_font, Vector2(lx + 12, top + 24), "CIAŁO — brak celu",
			HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_DIM)
		return
	var st := "śpi" if not e.aware else "ściga cię"
	draw_string(_font, Vector2(lx + 12, top + 22),
		"CIAŁO: %s  ·  HP %d/%d  ·  %s" % [e.name_pl, e.hp, e.max_hp, st],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 14, COL_CYAN)
	if e.body == null:
		draw_string(_font, Vector2(lx + 12, top + 46),
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
			draw_rect(prect, Color(COL_AMBER, 0.16))
		elif _hover(prect) and not p["severed"]:
			draw_rect(prect, Color(COL_CYAN, 0.10))
		if not p["severed"]:
			_zone(prect, "aim_part", 0, pkey)
		# Part name + severity
		var prefix := "» " if aimed else "  "
		var sev_pl: String = BodyState.SEVERITY_PL.get(sev, sev)
		var sev_txt := "—" if sev == BodyState.SEV_INTACT else sev_pl
		if p["severed"]:
			sev_txt = "odcięte"
		draw_string(_font, Vector2(lx + 12, y + 2), prefix + p["label_pl"],
			HORIZONTAL_ALIGNMENT_LEFT, 150, 13, COL_BRIGHT if not flashing else COL_RED)
		draw_string(_font, Vector2(lx + 150, y + 2), sev_txt,
			HORIZONTAL_ALIGNMENT_LEFT, 120, 13, col)
		# HP pip bar for the part
		var bx := lx + lw - 150.0
		var bw := 96.0
		var frac := float(p["hp"]) / float(maxi(1, int(p["max_hp"])))
		draw_rect(Rect2(bx, y - 9, bw, 10), Color(0.15, 0.15, 0.18))
		if not p["severed"]:
			draw_rect(Rect2(bx, y - 9, bw * clampf(frac, 0.0, 1.0), 10), col)
		# Wound icons
		var wx := bx + bw + 8.0
		for w in p["wounds"]:
			draw_string(_font, Vector2(wx, y + 2), _wound_glyph(w),
				HORIZONTAL_ALIGNMENT_LEFT, -1, 14, _wound_color(w))
			wx += 16.0
		y += 22.0
	# Aim hint
	draw_string(_font, Vector2(lx + 12, top + 210),
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

func _draw_craft_panel() -> void:
	var W := 1160.0; var H := 560.0
	var px := (1280 - W) / 2.0; var py := (720 - H) / 2.0
	# Background
	draw_rect(Rect2(px, py, W, H), Color(0.08, 0.09, 0.13, 0.97))
	draw_rect(Rect2(px, py, W, H), COL_CYAN, false, 2.0)
	# Title + mode tabs
	var mode_bench := _craft_mode == "bench"
	draw_string(_font, Vector2(px + 16, py + 24), "WARSZTAT", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, COL_CYAN)
	var tab1_col := COL_BRIGHT if mode_bench else COL_DIM
	var tab2_col := COL_BRIGHT if not mode_bench else COL_DIM
	draw_string(_font, Vector2(px + 200, py + 24), "Stół",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, tab1_col)
	_zone(Rect2(px + 196, py + 6, 90, 26), "tab_bench")
	draw_string(_font, Vector2(px + 300, py + 24), "Kieszeń",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 16, tab2_col)
	_zone(Rect2(px + 296, py + 6, 110, 26), "tab_items")
	# Close button
	draw_string(_font, Vector2(px + W - 24, py + 24), "✕  zamknij",
		HORIZONTAL_ALIGNMENT_RIGHT, -1, 14, COL_DIM)
	_zone(Rect2(px + W - 130, py + 6, 120, 26), "craft_close")
	draw_line(Vector2(px + 12, py + 42), Vector2(px + W - 12, py + 42), COL_GRID, 1.0)

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
