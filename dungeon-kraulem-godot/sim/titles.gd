class_name Titles
extends RefCounted
## End-of-run honorifics, ported from pygame systems/titles.py. Distinct from
## achievements (persistent unlocks) — a title is a behavioural label earned for
## HOW you played THIS run, shown on the results screen. Thresholds are tuned for
## this port's shorter (6-floor) seasons.
##
## Each: {key, label, desc, rule(p, floor, victory, zlom) -> bool}.

const TITLES := [
	{"key": "rzeznik",   "label": "Rzeźnik",          "desc": "20+ zabójstw w jednym biegu."},
	{"key": "pacyfista", "label": "Pacyfista",        "desc": "Zszedłeś głęboko, nie zabijając nikogo."},
	{"key": "gwiazdor",  "label": "Gwiazdor Kanału",  "desc": "Widownia sięgnęła poziomu VIRAL."},
	{"key": "recykler",  "label": "Recykler",         "desc": "12+ rzeczy rozebranych na żywej antenie."},
	{"key": "saper",     "label": "Saper",            "desc": "8+ rozstawionych pułapek."},
	{"key": "piwniczak", "label": "Piwniczak",        "desc": "Dotarłeś co najmniej na 5. piętro."},
	{"key": "finalista", "label": "Finalista Sezonu", "desc": "Wygrałeś sezon. Showrunner cię pamięta."},
	{"key": "tytan",     "label": "Tytan Areny",      "desc": "Wbiłeś cechę do 8."},
	{"key": "handlarz",  "label": "Handlarz Złomu",   "desc": "Skończyłeś z 30+ złomem w kieszeni."},
]

## Which titles the run earned: list of {label, desc}.
static func earned(p, floor, victory: bool, zlom: int) -> Array:
	var depth: int = floor.depth
	var peak: int = floor.audience.peak if floor.audience != null else 0
	var max_stat := 0
	for s in p.stats:
		max_stat = maxi(max_stat, int(p.stats[s]))
	var got := {
		"rzeznik": p.run_kills >= 20,
		"pacyfista": p.run_kills == 0 and depth >= 3,
		"gwiazdor": peak >= 80,
		"recykler": p.run_corpses_salvaged >= 12,
		"saper": p.run_traps_armed >= 8,
		"piwniczak": depth >= 5,
		"finalista": victory,
		"tytan": max_stat >= 8,
		"handlarz": zlom >= 30,
	}
	var out: Array = []
	for d in TITLES:
		if got.get(d["key"], false):
			out.append({"label": d["label"], "desc": d["desc"]})
	return out
