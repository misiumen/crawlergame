class_name CombatEntity
extends RefCounted
## A combatant / actor in the sim. No nodes. Tags drive systemic properties
## (the same tag data the Python game uses), so behaviour and — later — the
## procedural body rig both read from one source.

var id: int = 0
var name_pl: String = ""
var tags: Array = []
var max_hp: int = 1
var hp: int = 1
var ac: int = 10
var cell: Vector2i = Vector2i.ZERO
var statuses: Dictionary = {}    # status name -> turns remaining
var intent: Dictionary = {}      # telegraphed next action: {kind: strike|zap|pounce, cell}
var faction: String = "enemy"    # "player" | "enemy" | "neutral" | "object"
var alive: bool = true
var aware: bool = true           # enemies: false = idle until they notice you
var affordances: Array = []      # objects: ["salvage","break","inspect",...]
var coating: String = ""         # player weapon coating: "" | "electric" | "poison" | ...
var coating_charges: int = 0     # hits remaining on the coating
var bonus_damage: int = 0        # permanent melee damage bonus
var int_xp: int = 0              # tinkering experience (dismantling + crafting)
var body: BodyState = null       # procedural breakable body (null = flat-HP actor)
var monster_key: String = ""     # content key, for body-plan resolution
var dmg_dice: String = ""        # enemy attack dice from content (e.g. "1d6+2"); "" = default
var to_hit: int = 2              # enemy attack bonus from content
var dialogue_tree_key: String = ""   # NPCs (faction "npc"): which dialogue tree to open
# RPG stat block (modifiers, D&D-ish). Dialogue skill checks roll d20 + stat_mod.
var stats: Dictionary = {"CHA": 1, "INT": 0, "WIS": 1, "DEX": 1, "STR": 1}
var flags: Dictionary = {}       # world/dialogue flags (persist in the run + save)
var relationships: Dictionary = {}   # tree_key -> standing (persist in the run + save)

## Skill modifier for a stat. INT also rides the tinkering track (int_xp).
func stat_mod(stat: String) -> int:
	var m: int = int(stats.get(stat, 0))
	if stat == "INT":
		m += int_mod()
	return m
# Meta-progression loadout this run was started with (player only) — for the HUD.
var species_key: String = ""
var origin_key: String = ""
var species_trait: String = ""   # active species trait: regen / poison_immune / salvage_heal / first_strike
var magic_affinity: String = ""  # species magic aptitude: "adept" / "" (neutral) / "mundane"
var origin_trait: String = ""    # origin perk: "preacher" (persuasion master) / ...
# Equipment (player only): slot -> GameItem. Worn armor adds to AC.
var equipment: Dictionary = {}   # "head" | "body" | "legs" | "trinket" -> GameItem
# RPG progression (player only): the level track DCC runs on.
var level: int = 1
var xp: int = 0
var skill_points: int = 0        # banked, spent to raise a stat on level-up
var mana: int = 0                # spell fuel (player); refills per floor, regens slowly
var max_mana: int = 3
# Emergent-class state (player only)
var affinity: Dictionary = {}    # playstyle kind -> points
var class_key: String = ""       # chosen emergent class, "" = none
var class_active_used_floor: int = -1  # floor index the active was last spent on
var next_attack_mult: int = 1    # bruiser charge: next hit damage multiplier
var next_attack_autohit: bool = false  # ranger: next hit always lands
# Run tallies (for the end-of-run summary + meta unlocks)
var run_kills: int = 0
var run_corpses_salvaged: int = 0
var run_traps_armed: int = 0

func int_mod() -> int:
	return int_xp / 5

## Total AC granted by worn equipment.
func armor_bonus() -> int:
	var b := 0
	for slot in equipment:
		var it = equipment[slot]
		if it != null:
			b += int((it.effect as Dictionary).get("ac_bonus", 0))
	return b

## XP needed to reach the next level (gently escalating curve).
func xp_to_next() -> int:
	return 20 + (level - 1) * 25

## Bank XP; returns the number of levels gained (0 if none). Level-up rewards
## (HP, skill points, loot) are applied by the caller so they can be narrated.
func gain_xp(amount: int) -> int:
	if amount <= 0:
		return 0
	xp += amount
	var gained := 0
	while xp >= xp_to_next():
		xp -= xp_to_next()
		level += 1
		gained += 1
	return gained

func add_affinity(kind: String, amount: int = 1) -> void:
	affinity[kind] = int(affinity.get(kind, 0)) + amount

## Attach a procedural body resolved from this entity's tags + the plan bundle.
func attach_body(bundle: Dictionary) -> void:
	body = BodyState.from_bundle(tags, monster_key, max_hp, bundle)

## Can this actor still relocate? Flat-HP actors always can; bodied ones lose it
## when their locomotion is destroyed (broken legs / propulsion).
func can_move() -> bool:
	return body == null or body.can_move()

## Hobbled = at least one locomotion part broken (slowed, no charge/flee).
func is_hobbled() -> bool:
	return body != null and body.is_hobbled()

func _init(_id: int = 0, _name: String = "", _hp: int = 1, _ac: int = 10, _tags: Array = []) -> void:
	id = _id
	name_pl = _name
	max_hp = _hp
	hp = _hp
	ac = _ac
	tags = _tags.duplicate()

func is_alive() -> bool:
	return alive and hp > 0

## Combat body class: 83 monster templates collapse into 7 archetypes that drive
## BOTH the silhouette (presentation) and the fighting style (sim AI).
func body_kind() -> String:
	if "boss" in tags: return "boss"
	if "miniboss" in tags or "mini_boss" in tags: return "elite"
	for t in ["machine", "robot", "drone", "camera", "mechanical", "construct"]:
		if t in tags: return "mech"
	for t in ["undead", "ghost"]:
		if t in tags: return "spectral"
	for t in ["robactwo", "insect"]:
		if t in tags: return "bug"
	if "humanoid" in tags: return "humanoid"
	return "beast"

func properties() -> Dictionary:
	return Tags.properties_for(tags)

func has_property(p: String) -> bool:
	return properties().has(p)

func add_status(s: String, turns: int) -> void:
	# "Mutant chemiczny" shrugs off poison entirely.
	if s == "poisoned" and species_trait == "poison_immune":
		return
	statuses[s] = max(int(statuses.get(s, 0)), turns)

func has_status(s: String) -> bool:
	return int(statuses.get(s, 0)) > 0

func tick_statuses() -> void:
	for s in statuses.keys():
		statuses[s] = int(statuses[s]) - 1
		if statuses[s] <= 0:
			statuses.erase(s)

func take_damage(amount: int) -> void:
	hp = max(0, hp - amount)
	if hp <= 0:
		alive = false
