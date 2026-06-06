class_name Memetics
extends RefCounted
## Freeform social engineering — a hidden third road through the Loch for the
## silver-tongued. You don't pick from a menu of scripted actions; you SAY a line
## to a mind on the floor (enemy / crawler / NPC), and the System reads your
## intent, weighs how ridiculous the claim is against reality, and rolls CHA.
##
## It never touches the audience — this is about the minds in the room: convert
## them to your faith (they fight for you and spread it), convince them you're a
## friend, turn them against their own, or break their nerve. A wild lie to a
## raging boss is a brutal check but a legendary payoff; nonsense is a pure gamble.
##
## This module is the pure brain: classify a typed line into an intent, score the
## difficulty, and hand back canned "improvised" lines for the hybrid fallback.
## BoardView owns the target, the CHA roll, and applying the emergent effect.

# Intent -> {kw (keyword stems), base_dc, kind}. kind drives the mechanical effect.
const INTENTS := {
	"befriend": {
		"kw": ["przyjac", "brat", "siostr", "swój", "swoj", "po naszej", "po twojej", "pokój", "pokoj",
			"nie wróg", "nie wrog", "spokój", "spokoj", "zaufaj", "razem", "sojusz", "kumpel", "rodzin"],
		"base_dc": 9, "kind": "charm"},
	"convert": {
		"kw": ["wiar", "bóg", "bog", "boż", "boz", "klęk", "klek", "nawróć", "nawroc", "prawd",
			"jedyn", "prorok", "święt", "swiet", "módl", "modl", "kult", "zbawien", "owce", "owca", "objawien"],
		"base_dc": 14, "kind": "convert"},
	"incite": {
		"kw": ["zdrad", "zabij", "atakuj", "wróg", "wrog", "kłam", "klam", "oszuk", "tamt",
			"on cię", "on cie", "zabić", "zabic", "zniszcz", "bunt", "przeciw", "twój dowódca", "twoj dowodca"],
		"base_dc": 12, "kind": "incite"},
	"demoralize": {
		"kw": ["uciek", "boisz", "zginiesz", "strach", "koniec", "poddaj", "przegr", "śmier", "smier",
			"bój się", "boj sie", "uciekaj", "nie masz szans", "umrzesz"],
		"base_dc": 10, "kind": "fear"},
}

## Classify a typed line into an intent key (most keyword hits wins), or "" if the
## line reads as nonsense the System can't parse.
static func classify(line: String) -> String:
	var low := line.to_lower()
	var best := ""
	var best_hits := 0
	for intent in INTENTS:
		var hits := 0
		for kw in INTENTS[intent]["kw"]:
			if low.contains(kw):
				hits += 1
		if hits > best_hits:
			best_hits = hits
			best = intent
	return best

static func base_dc(intent: String) -> int:
	return int(INTENTS.get(intent, {}).get("base_dc", 12))

static func kind_of(intent: String) -> String:
	return str(INTENTS.get(intent, {}).get("kind", ""))

## Improvised lines for the hybrid fallback (when you leave the prompt blank or
## type something unreadable). A handful of distinct, ready-to-say claims.
static func fallback_lines(rng: RandomNumberGenerator) -> Array:
	var pool := [
		{"text": "Spokojnie — jestem po waszej stronie.", "intent": "befriend"},
		{"text": "Klęknij. Poznaj Jedyną Wiarę.", "intent": "convert"},
		{"text": "Twój dowódca cię zdradził. Zabij go.", "intent": "incite"},
		{"text": "Uciekaj, póki możesz. To już koniec.", "intent": "demoralize"},
		{"text": "Tamten obok was okradł. Dorwijcie go.", "intent": "incite"},
		{"text": "Przyłącz się, a podzielę się łupem.", "intent": "befriend"},
	]
	for i in range(pool.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var t = pool[i]; pool[i] = pool[j]; pool[j] = t
	return pool.slice(0, 3)
