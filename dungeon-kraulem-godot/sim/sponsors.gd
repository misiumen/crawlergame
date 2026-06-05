class_name SponsorState
extends RefCounted
## Sponsor attention tracking + gift/hunter dispatch.
## Port of engine/sponsors.py. Reads catalog from data/sponsors.json via Data autoload.

const ATTENTION_MIN := -20
const ATTENTION_MAX :=  20
const GIFT_THRESHOLD_FIRST  :=  5
const GIFT_THRESHOLD_SECOND := 10
const HUNTER_THRESHOLD      := -3

var attention: Dictionary = {}      # sponsor_key -> int
var flags: Dictionary = {}          # gift-sent flags, recipe-unlock flags
var pending_boxes: Array = []       # GameBox items queued for the player
var pending_hunters: Array = []     # hunter_key strings for next combat room

# ── Data access ──────────────────────────────────────────────────────────────

func _sponsors() -> Dictionary:
	# Reach the Data autoload via the scene-tree root rather than the bare global
	# identifier: works in-game AND avoids a compile-time "Identifier not found"
	# during headless --import (where autoload globals aren't injected).
	# (Engine.has_singleton is for native singletons, NOT autoloads — it is always
	# false here, which is why this used to silently no-op in the real game.)
	var loop := Engine.get_main_loop()
	if not (loop is SceneTree):
		return {}
	var data_node := (loop as SceneTree).root.get_node_or_null("Data")
	if data_node == null or not data_node.has_method("group"):
		return {}
	var raw: Variant = data_node.call("group", "sponsors", "SPONSORS")
	return raw if raw is Dictionary else {}

func all_keys() -> Array:
	return _sponsors().keys()

func get_sponsor(key: String) -> Dictionary:
	var d: Variant = _sponsors().get(key)
	return d if d is Dictionary else {}

# ── Attention API ─────────────────────────────────────────────────────────────

func get_attention(key: String) -> int:
	return int(attention.get(key, 0))

func primary_sponsor() -> String:
	var best := ""
	var best_val := 0
	for k in all_keys():
		var v := get_attention(k)
		if v > best_val:
			best_val = v
			best = k
	return best

func top_ranked(n: int = 3) -> Array:
	var ranked: Array = all_keys().filter(func(k): return attention.get(k, 0) != 0)
	ranked.sort_custom(func(a, b):
		var va: int = abs(get_attention(a as String))
		var vb: int = abs(get_attention(b as String))
		if va != vb: return va > vb
		return get_attention(a as String) > get_attention(b as String))
	return ranked.slice(0, mini(n, ranked.size()))

func mood(key: String) -> String:
	var att := get_attention(key)
	if att >= 5:  return "zachwycony"
	if att >= 3:  return "życzliwy"
	if att >= 1:  return "uważny"
	if att == 0:  return "obojętny"
	if att >= -2: return "podejrzliwy"
	if att >= -4: return "wkurzony"
	return "wrogi"

# ── Tag routing ───────────────────────────────────────────────────────────────

## Route a gameplay tag to all sponsors. Returns list of event dicts.
func note_tag(tag: String, weight: int = 1, floor_num: int = 1) -> Array:
	var evs: Array = []
	var primary := primary_sponsor()
	var sponsors := _sponsors()
	for skey in sponsors:
		var sdata: Dictionary = sponsors[skey]
		var bump := 0
		var likes: Variant = sdata.get("likes_tags", [])
		var dislikes: Variant = sdata.get("dislikes_tags", [])
		if likes is Array and tag in likes:
			bump += weight
		if dislikes is Array and tag in dislikes:
			bump -= weight
		if bump == 0:
			continue
		# Primary doubling: the sponsor already watching notices twice as much.
		if skey == primary and primary != "":
			bump *= 2
		var old_val := get_attention(skey as String)
		var new_val := clampi(old_val + bump, ATTENTION_MIN, ATTENTION_MAX)
		attention[skey as String] = new_val
		if new_val != old_val:
			evs.append({"type": "sponsor_attention", "key": skey as String,
						"delta": new_val - old_val, "val": new_val,
						"name": sdata.get("name_fallback", skey as String)})
	evs.append_array(_check_gift_thresholds(floor_num))
	return evs

func _check_gift_thresholds(floor_num: int) -> Array:
	var evs: Array = []
	var sponsors := _sponsors()
	for skey in sponsors:
		var sdata: Dictionary = sponsors[skey]
		var v := get_attention(skey as String)
		var flag1: String = "gift1_" + (skey as String)
		var flag2: String = "gift2_" + (skey as String)
		if v >= GIFT_THRESHOLD_FIRST and not flags.get(flag1, false):
			flags[flag1] = true
			var box := _make_sponsor_box(skey, sdata, floor_num, false)
			if box:
				pending_boxes.append(box)
				evs.append({"type": "sponsor_gift", "key": skey,
							"name": sdata.get("name_fallback", skey), "second": false})
		if v >= GIFT_THRESHOLD_SECOND and not flags.get(flag2, false):
			flags[flag2] = true
			var box := _make_sponsor_box(skey, sdata, floor_num, true)
			if box:
				pending_boxes.append(box)
				evs.append({"type": "sponsor_gift", "key": skey,
							"name": sdata.get("name_fallback", skey), "second": true})
	return evs

func _make_sponsor_box(skey: String, sdata: Dictionary,
		floor_num: int, second: bool) -> GameBox:
	var pool_v: Variant = sdata.get("gift_pool", [])
	var pool: Array = pool_v if pool_v is Array else []
	if pool.is_empty():
		return null
	var idx := 1 if (second and pool.size() >= 2) else 0
	var item_key: String = pool[idx]
	var box_rarity := Rarity.COMMON
	if floor_num >= 8:   box_rarity = Rarity.RARE
	elif floor_num >= 4: box_rarity = Rarity.UNCOMMON
	var box := GameBox.new("sponsor", sdata.get("name_fallback", skey), box_rarity)
	box.contents.append({"type": "item_key", "key": item_key, "qty": 1})
	box.sponsor_tagline = sdata.get("tagline_fallback", "")
	return box

## Consume and return all pending boxes since last call.
func drain_boxes() -> Array:
	var out := pending_boxes.duplicate()
	pending_boxes.clear()
	return out
