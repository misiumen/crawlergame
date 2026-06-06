class_name MidFloorEvents
extends RefCounted
## Mid-floor "show beats", ported from pygame engine/mid_floor_events.py. Now and
## then a little decision fork interrupts the crawl. In the source the SHOWRUNNER
## picked for you by audience band; here YOU choose (more engaging, same beats),
## and the consequence lands immediately. Credits → złom (no credit economy here).
##
## Beat: {key, intro, forks:[{label, effect:{audience,zlom,hp}}]}.

## `min_audience` gates beats that only make sense once the show is watching you —
## a sponsor won't call for an interview, and camera crews won't swarm, before
## anyone cares. Beats without it can fire any time.
const BEATS := [
	{"key": "sponsor_call", "min_audience": 15, "intro": "Komunikator buczy. Sponsor chce wywiad na żywo.",
		"forks": [
			{"label": "Odmawiasz — wracasz do walki. (showrunner woli krew)", "effect": {"audience": 3}},
			{"label": "Bierzesz wywiad. Sponsor składa kondolencje.", "effect": {"audience": -2, "zlom": 8}},
		]},
	{"key": "vending_choice", "intro": "Stary automat z przekąskami mruga awaryjnym światłem.",
		"forks": [
			{"label": "Kopiesz automat — wypada batonik i alarm.", "effect": {"hp": 4, "audience": 2}},
			{"label": "Idziesz dalej. Automat zostaje urażony.", "effect": {"audience": -1}},
		]},
	{"key": "injured_crawler", "intro": "Ranny zawodnik charczy pod ścianą. Patrzy na ciebie.",
		"forks": [
			{"label": "Mijasz go. Twardo i krótko.", "effect": {"audience": -3}},
			{"label": "Dajesz opatrunek. Wzajemna ulga (i show).", "effect": {"audience": 4, "zlom": -3}},
		]},
	{"key": "camera_swarm", "min_audience": 20, "intro": "Rój kamer sponsora otacza cię w korytarzu.",
		"forks": [
			{"label": "Robisz pozę. Kliki, ujęcia, sława.", "effect": {"audience": 5}},
			{"label": "Zasłaniasz twarz, idziesz dalej.", "effect": {"audience": -1}},
		]},
]

## Pick a beat that FITS the current show state, or {} if none qualifies (e.g. an
## ignored nobody on floor 1 gets no sponsor cameras). `audience` is the rating.
static func pick(rng: RandomNumberGenerator, audience: int) -> Dictionary:
	var pool: Array = []
	for b in BEATS:
		if audience >= int(b.get("min_audience", 0)):
			pool.append(b)
	if pool.is_empty():
		return {}
	return (pool[rng.randi_range(0, pool.size() - 1)] as Dictionary).duplicate(true)
