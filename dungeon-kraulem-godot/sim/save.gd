class_name Save
extends RefCounted
## Run persistence. A save is a per-floor checkpoint: we store the run's seed +
## depth + carried state, NOT the room layout — floors are deterministic from
## (seed, depth), so on load we regenerate the floor and re-inject the run state.
## Reloading therefore drops you at the START of your current floor (a clean,
## roguelike checkpoint). Meta-progression persists separately (Meta / meta.json).

const PATH := "user://run.json"

static func has_save() -> bool:
	return FileAccess.file_exists(PATH)

static func clear() -> void:
	if FileAccess.file_exists(PATH):
		DirAccess.remove_absolute(PATH)

# ── Write ─────────────────────────────────────────────────────────────────────

static func write(floor, seed_value: int) -> void:
	var p = floor.player
	var item_dicts: Array = []
	for it in floor.items:
		item_dicts.append((it as GameItem).to_dict())
	var box_dicts: Array = []
	for b in floor.boxes:
		if not (b as GameBox).opened:
			box_dicts.append((b as GameBox).to_dict())
	var data := {
		"seed": seed_value,
		"depth": floor.depth,
		"biome": floor.biome,
		"turn": floor.turn,
		"class_offered": floor.class_offered,
		"objective": floor.objective.duplicate(true),
		"player": _player_dict(p),
		"inv": floor.inv.duplicate(true),
		"items": item_dicts,
		"boxes": box_dicts,
		"discovered": floor.discovered_recipes.duplicate(true),
		"audience": {
			"rating": floor.audience.rating, "peak": floor.audience.peak,
			"idle": floor.audience.idle_turns,
		},
		"sponsors": {
			"attention": floor.sponsors.attention.duplicate(true),
			"flags": floor.sponsors.flags.duplicate(true),
		},
	}
	var f := FileAccess.open(PATH, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(data))

static func _player_dict(p) -> Dictionary:
	return {
		"hp": p.hp, "max_hp": p.max_hp, "ac": p.ac,
		"class_key": p.class_key, "affinity": p.affinity.duplicate(true),
		"int_xp": p.int_xp, "coating": p.coating, "coating_charges": p.coating_charges,
		"bonus_damage": p.bonus_damage,
		"run_kills": p.run_kills, "run_corpses_salvaged": p.run_corpses_salvaged,
		"run_traps_armed": p.run_traps_armed,
		"stats": p.stats.duplicate(true),
		"level": p.level, "xp": p.xp, "skill_points": p.skill_points,
		"mana": p.mana, "max_mana": p.max_mana,
		"species_key": p.species_key, "origin_key": p.origin_key, "trait": p.species_trait,
		"magic_affinity": p.magic_affinity,
		"equipment": _equipment_dict(p.equipment),
		"flags": p.flags.duplicate(true),
		"relationships": p.relationships.duplicate(true),
	}

static func _equipment_dict(eq: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for slot in eq:
		if eq[slot] != null:
			out[slot] = (eq[slot] as GameItem).to_dict()
	return out

# ── Read ──────────────────────────────────────────────────────────────────────

static func read() -> Dictionary:
	if not FileAccess.file_exists(PATH):
		return {}
	var f := FileAccess.open(PATH, FileAccess.READ)
	if f == null:
		return {}
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	return parsed if parsed is Dictionary else {}

## Rebuild a Floor from a save dict by regenerating its floor and injecting the
## saved run state. `content` is the entity bundle for FloorGen. Returns null if
## the save is unusable.
static func rebuild_floor(save_dict: Dictionary, content: Dictionary):
	if save_dict.is_empty():
		return null
	var seed_value := int(save_dict.get("seed", 0))
	var depth := int(save_dict.get("depth", 1))
	var biome := str(save_dict.get("biome", ""))
	var mods: Dictionary = Routes.mods_for(biome) if biome != "" else {}
	var fdata: Dictionary = FloorGen.generate(depth, seed_value, content, mods)

	# Re-apply the saved player stats onto the freshly generated player. We set
	# class_key + max_hp DIRECTLY (no assign_class) — the passive hp bump is
	# already baked into the saved max_hp.
	var pd: Dictionary = save_dict.get("player", {})
	var p = fdata["player"]
	p.max_hp = int(pd.get("max_hp", p.max_hp))
	p.hp = int(pd.get("hp", p.hp))
	p.ac = int(pd.get("ac", p.ac))
	p.class_key = pd.get("class_key", "")
	p.affinity = (pd.get("affinity", {}) as Dictionary).duplicate(true)
	p.int_xp = int(pd.get("int_xp", 0))
	p.coating = pd.get("coating", "")
	p.coating_charges = int(pd.get("coating_charges", 0))
	p.bonus_damage = int(pd.get("bonus_damage", 0))
	p.run_kills = int(pd.get("run_kills", 0))
	p.run_corpses_salvaged = int(pd.get("run_corpses_salvaged", 0))
	p.run_traps_armed = int(pd.get("run_traps_armed", 0))
	if pd.has("stats"): p.stats = (pd["stats"] as Dictionary).duplicate(true)
	p.level = int(pd.get("level", 1))
	p.xp = int(pd.get("xp", 0))
	p.skill_points = int(pd.get("skill_points", 0))
	p.species_key = str(pd.get("species_key", ""))
	p.origin_key = str(pd.get("origin_key", ""))
	p.species_trait = str(pd.get("trait", ""))
	p.magic_affinity = str(pd.get("magic_affinity", ""))
	p.max_mana = int(pd.get("max_mana", 3))
	p.mana = int(pd.get("mana", p.max_mana))
	p.equipment = {}
	for slot in (pd.get("equipment", {}) as Dictionary):
		p.equipment[slot] = GameItem.from_dict(pd["equipment"][slot])
	p.flags = (pd.get("flags", {}) as Dictionary).duplicate(true)
	p.relationships = (pd.get("relationships", {}) as Dictionary).duplicate(true)

	# Carried run state.
	fdata["inv"] = (save_dict.get("inv", {}) as Dictionary).duplicate(true)
	var items: Array = []
	for idict in save_dict.get("items", []):
		items.append(GameItem.from_dict(idict))
	fdata["items"] = items
	var boxes: Array = []
	for bdict in save_dict.get("boxes", []):
		boxes.append(GameBox.from_dict(bdict))
	fdata["boxes"] = boxes
	fdata["discovered"] = (save_dict.get("discovered", []) as Array).duplicate(true)
	fdata["class_offered"] = bool(save_dict.get("class_offered", false))
	fdata["objective"] = (save_dict.get("objective", {}) as Dictionary).duplicate(true)

	var aud := AudienceState.new()
	var adict: Dictionary = save_dict.get("audience", {})
	aud.rating = int(adict.get("rating", 0))
	aud.peak = int(adict.get("peak", 0))
	aud.idle_turns = int(adict.get("idle", 0))
	fdata["audience"] = aud

	var spon := SponsorState.new()
	var sdict: Dictionary = save_dict.get("sponsors", {})
	spon.attention = (sdict.get("attention", {}) as Dictionary).duplicate(true)
	spon.flags = (sdict.get("flags", {}) as Dictionary).duplicate(true)
	fdata["sponsors"] = spon

	return Floor.new(fdata)
