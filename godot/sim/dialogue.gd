class_name Dialogue
extends RefCounted
## Lightweight board dialogue. A NPC offers a single exchange: a line + a few
## options, each with effects (audience / sponsor attention / a material trade /
## flavor). A board-appropriate distillation of engine/dialogue.py (full branching
## trees with skill checks are a later extension). All player-facing text Polish.
##
## An option: {label, audience, sponsor_tag, material, mat_qty, reply, requires_mat}
##   audience    — int delta to the audience rating
##   sponsor_tag — a gameplay tag routed to all sponsors (attention)
##   material/mat_qty — add (or, negative, spend) a run material
##   requires_mat — if true the option only resolves when you can pay mat_qty
##   reply       — the NPC's Polish response line

const NPC_POOL: Array = [
	{
		"speaker": "Zgubiony Zawodnik",
		"text": "Mierzy cię wzrokiem, dłoń blisko pasa. „Masz coś, czego ja nie mam?”",
		"options": [
			{"label": "Dorzuć mu złom. (-1 złom, widownia +1)",
				"material": "złom", "mat_qty": -1, "requires_mat": true, "audience": 1,
				"reply": "Kiwa głową. „Następnym razem ja stawiam. Pewnie.”"},
			{"label": "Zagraj pod kamerę. (widownia +3)",
				"audience": 3, "sponsor_tag": "showmanship",
				"reply": "Przewraca oczami, ale kamera nad wami to łyka w całości."},
			{"label": "Wyminij go bez słowa.",
				"reply": "Wzrusza ramionami i znika w bocznym korytarzu."},
		],
	},
	{
		"speaker": "Handlarz z Bocznej Rampy",
		"text": "Rozkłada szmatę z drobiazgami. „Złom za przewód. Uczciwie, jak na loch.”",
		"options": [
			{"label": "Wymień 2 złom na 1 przewód.",
				"material": "złom", "mat_qty": -2, "requires_mat": true,
				"give_material": "przewód", "give_qty": 1,
				"reply": "Znika towar, pojawia się przewód. „Wracaj, jak coś znajdziesz.”"},
			{"label": "Pochwal jego towar głośno. (widownia +2)",
				"audience": 2, "sponsor_tag": "social",
				"reply": "Uśmiecha się do obiektywu. Reklama za darmo — lubi to."},
			{"label": "Podziękuj i idź dalej.",
				"reply": "„Twoja strata.” Zwija szmatę z powrotem."},
		],
	},
	{
		"speaker": "Wierny Widz",
		"text": "Macha do ciebie zza barierki. „Jeden autograf! No weź, oglądam od pierwszego piętra!”",
		"options": [
			{"label": "Daj autograf. (widownia +4)",
				"audience": 4, "sponsor_tag": "performance",
				"reply": "Piszczy z zachwytu. Klip leci w pętli na trybunach."},
			{"label": "Sprzedaj mu sławę za złom. (+1 złom, widownia +1)",
				"give_material": "złom", "give_qty": 1, "audience": 1, "sponsor_tag": "betrayal",
				"reply": "Płaci bez mrugnięcia. Widownia nie wie, czy bić brawo, czy buczeć."},
			{"label": "Nie masz czasu na fanów.",
				"audience": -1,
				"reply": "Mina mu rzednie. Trybuny to widzą."},
		],
	},
]

## A random NPC dialogue (a deep copy so per-instance state can't leak).
static func random_npc(rng: RandomNumberGenerator) -> Dictionary:
	var pick: Dictionary = NPC_POOL[rng.randi_range(0, NPC_POOL.size() - 1)]
	return pick.duplicate(true)

## Whether option idx can be chosen right now (material gates).
static func option_available(floor, dialogue: Dictionary, idx: int) -> bool:
	var opts: Array = dialogue.get("options", [])
	if idx < 0 or idx >= opts.size():
		return false
	var o: Dictionary = opts[idx]
	if o.get("requires_mat", false):
		var mat: String = o.get("material", "")
		var qty: int = int(o.get("mat_qty", 0))
		if qty < 0 and int(floor.inv.get(mat, 0)) < -qty:
			return false
	return true

## Resolve option idx: apply its effects to the run, return {reply, events}.
static func choose(floor, dialogue: Dictionary, idx: int) -> Dictionary:
	var opts: Array = dialogue.get("options", [])
	if idx < 0 or idx >= opts.size():
		return {"reply": "", "events": []}
	var o: Dictionary = opts[idx]
	var events: Array = []

	# Material spend/gain.
	if o.has("material"):
		var mat: String = o["material"]
		var qty: int = int(o.get("mat_qty", 0))
		floor.inv[mat] = maxi(0, int(floor.inv.get(mat, 0)) + qty)
		events.append({"type": "dialogue_material", "material": mat, "qty": qty})
	if o.has("give_material"):
		var gm: String = o["give_material"]
		var gq: int = int(o.get("give_qty", 1))
		floor.inv[gm] = int(floor.inv.get(gm, 0)) + gq
		events.append({"type": "dialogue_material", "material": gm, "qty": gq})

	# Audience + sponsor attention.
	var aud: int = int(o.get("audience", 0))
	if aud != 0 and floor.audience != null:
		floor.audience.change(aud, "dialogue")
		events.append({"type": "dialogue_audience", "delta": aud})
	if o.has("sponsor_tag") and floor.sponsors != null:
		floor.sponsors.note_tag(o["sponsor_tag"], 1)

	return {"reply": o.get("reply", ""), "events": events}
