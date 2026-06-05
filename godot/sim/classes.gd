class_name Classes
extends RefCounted
## Emergent classes. Your PLAYSTYLE crystallizes into a class: every action bumps
## an affinity, and when one style dominates the Syndicate offers you a class with
## a passive + a once-per-floor active. Faithful port of systems/classes.py
## (catalog + affinity_weights + scoring + offer thresholds), adapted from the
## Python game's in-game-minutes to the board's turn count.

# The 14 playstyle affinities tracked on the player.
const AFFINITY_KINDS: Array = [
	"melee", "ranged", "stealth", "magic", "tech", "trap", "environment",
	"support", "social", "survival", "showmanship", "betrayal", "diplomacy", "crafting",
]

const AFFINITY_LABELS_PL: Dictionary = {
	"melee": "walka wręcz", "ranged": "broń dystansowa", "stealth": "skradanie",
	"magic": "okultyzm", "tech": "technika", "trap": "pułapki",
	"environment": "otoczenie", "support": "wsparcie", "social": "spryt społeczny",
	"survival": "przetrwanie", "showmanship": "show", "betrayal": "zdrada",
	"diplomacy": "dyplomacja", "crafting": "rzemiosło",
}

## The 12 emergent classes. affinity_weights decide which styles attract each class.
const CATALOG: Dictionary = {
	"bruiser": {
		"name_pl": "Bydlak",
		"desc_pl": "Bijesz mocno i pierwszy. To wystarcza częściej niż powinno.",
		"reason_pl": "Twoje pięści mówią głośniej niż rozsądek.",
		"weights": {"melee": 3, "survival": 1},
	},
	"survivor": {
		"name_pl": "Ocalały",
		"desc_pl": "Specjalność: nie umierać. Wszystko inne to bonus.",
		"reason_pl": "Wciąż żyjesz. Statystycznie to już osiągnięcie.",
		"weights": {"survival": 3, "stealth": 1},
	},
	"saboteur": {
		"name_pl": "Sabotażysta",
		"desc_pl": "Pokój sam siebie zabije, jeśli mu pomożesz.",
		"reason_pl": "Loch to dla ciebie zestaw guzików „samozniszczenie\".",
		"weights": {"environment": 3, "trap": 2},
	},
	"engineer": {
		"name_pl": "Inżynier",
		"desc_pl": "Każda maszyna wokół ciebie staje się albo użyteczna, albo nielegalna.",
		"reason_pl": "Rozbierasz świat na części i składasz lepszy.",
		"weights": {"tech": 3, "crafting": 2, "environment": 1},
	},
	"ranger": {
		"name_pl": "Tropiciel",
		"desc_pl": "Wiesz, gdzie czekać. I czym strzelać.",
		"reason_pl": "Trzymasz dystans i cierpliwość.",
		"weights": {"ranged": 3, "survival": 1, "trap": 1},
	},
	"medic": {
		"name_pl": "Medyk",
		"desc_pl": "Trzymasz innych przy życiu. Czasem przez własne korzyści.",
		"reason_pl": "Bandaże i litość — twoje główne narzędzia.",
		"weights": {"support": 3, "survival": 1},
	},
	"occultist": {
		"name_pl": "Okultysta",
		"desc_pl": "Loch szepcze, ty słuchasz. Wszyscy żałują.",
		"reason_pl": "Słyszysz w lochu rzeczy, których nie ma.",
		"weights": {"magic": 2, "betrayal": 1, "social": 1},
	},
	"negotiator": {
		"name_pl": "Negocjator",
		"desc_pl": "Twoje słowa są tańsze niż kule i równie skuteczne.",
		"reason_pl": "Wolisz gadać niż walczyć — i ci wychodzi.",
		"weights": {"diplomacy": 3, "social": 2},
	},
	"trickster": {
		"name_pl": "Krętacz",
		"desc_pl": "Mistrz drobnych zdrad i pełnych ich planów.",
		"reason_pl": "Cień i kłamstwo to twoje ulubione tła.",
		"weights": {"stealth": 2, "social": 1, "showmanship": 1, "betrayal": 1},
	},
	"demolitionist": {
		"name_pl": "Demoman",
		"desc_pl": "Jeśli istnieje, można to wysadzić. Albo zawalić.",
		"reason_pl": "Twoje rozwiązanie problemu zwykle wybucha.",
		"weights": {"environment": 2, "trap": 2, "melee": 1},
	},
	"showman": {
		"name_pl": "Showman",
		"desc_pl": "Widownia płaci. Sponsorzy podwyższają stawki.",
		"reason_pl": "Grasz pod kamerę i widownia to czuje.",
		"weights": {"showmanship": 3, "social": 1},
	},
	"scout": {
		"name_pl": "Zwiadowca",
		"desc_pl": "Widzisz pierwszy. Wracasz cały. Czasem.",
		"reason_pl": "Idziesz cicho i pierwszy widzisz kłopoty.",
		"weights": {"stealth": 2, "survival": 2, "ranged": 1},
	},
}

# ── Offer thresholds (adapted from minutes to board turns) ────────────────────
const FORCED_TOTAL := 16       # any clearly-invested run eventually gets an offer
const EARNED_TOTAL := 10       # enough signal accumulated
const EARNED_TOP := 5          # a single style is clearly dominant
const EARNED_TURN := 8         # a meaningful session has happened

# ── Scoring + suggestion ──────────────────────────────────────────────────────

## How well the player's current affinities fit a given class. Deterministic
## except a tiny per-call tie-breaker (RNG-driven so seeds reproduce).
static func class_score(player, class_key: String, rng: RandomNumberGenerator) -> float:
	var weights: Dictionary = CATALOG[class_key]["weights"]
	var score := 0.0
	for kind in weights:
		score += float(player.affinity.get(kind, 0)) * float(weights[kind])
	score += rng.randf() * 0.01   # break ties without changing ordering meaningfully
	return score

## Top-N class keys by fit, with a 20% chance the last pick is a wildcard
## (discovery — you might be nudged toward a class you didn't grind for).
static func suggest_classes(player, n: int, rng: RandomNumberGenerator) -> Array:
	var ranked: Array = CATALOG.keys()
	ranked.sort_custom(func(a, b):
		return class_score(player, a, rng) > class_score(player, b, rng))
	var top: Array = ranked.slice(0, mini(n, ranked.size()))
	if rng.randf() < 0.2 and ranked.size() > n:
		var wild: String = ranked[rng.randi_range(n, ranked.size() - 1)]
		top[top.size() - 1] = wild
	return top

# ── Offer logic ───────────────────────────────────────────────────────────────

static func total_affinity(player) -> int:
	var t := 0
	for k in player.affinity:
		t += int(player.affinity[k])
	return t

## Returns [top_kind, top_val, second_val].
static func top_two(player) -> Array:
	var best_k := ""; var best := 0; var second := 0
	for k in player.affinity:
		var v := int(player.affinity[k])
		if v > best:
			second = best; best = v; best_k = k
		elif v > second:
			second = v
	return [best_k, best, second]

## Should the Syndicate offer a class now? (player has none yet.)
static func should_offer(player, _floor_num: int, turn: int) -> bool:
	if player.class_key != "":
		return false
	var total := total_affinity(player)
	var tt := top_two(player)
	var top: int = tt[1]; var second: int = tt[2]
	if total >= FORCED_TOTAL:
		return true
	return total >= EARNED_TOTAL and top >= EARNED_TOP and top >= 2 * second and turn >= EARNED_TURN

# ── Assignment ────────────────────────────────────────────────────────────────

## Assign a class to the player and apply its passive hp_max bump (undoing any
## prior class's bump first, so re-assignment is safe).
static func assign_class(player, class_key: String) -> bool:
	if not CATALOG.has(class_key):
		return false
	if player.class_key != "":
		# Undo the prior class's HP + stat bumps so re-classing stays consistent.
		var old_hp: int = ClassFeatures.passive_bonus_for(player.class_key, "hp_max")
		player.max_hp = maxi(1, player.max_hp - old_hp)
		player.hp = mini(player.hp, player.max_hp)
		for s in ClassFeatures.class_stats_for(player.class_key):
			player.stats[s] = int(player.stats.get(s, 0)) - int(ClassFeatures.class_stats_for(player.class_key)[s])
	player.class_key = class_key
	var bump: int = ClassFeatures.passive_bonus_for(class_key, "hp_max")
	player.max_hp += bump
	player.hp += bump
	for s in ClassFeatures.class_stats_for(class_key):
		player.stats[s] = int(player.stats.get(s, 0)) + int(ClassFeatures.class_stats_for(class_key)[s])
	return true

static func name_of(class_key: String) -> String:
	return CATALOG[class_key]["name_pl"] if CATALOG.has(class_key) else class_key

static func desc_of(class_key: String) -> String:
	return CATALOG[class_key]["desc_pl"] if CATALOG.has(class_key) else ""

static func affinity_label(kind: String) -> String:
	return AFFINITY_LABELS_PL.get(kind, kind)
