class_name Recipes
extends RefCounted
## Craftable recipes for the slice. Tag-light for now; this is where the Python
## crafting tables get ported in full later. cost = materials dict.

static func all() -> Array:
	return [
		{
			"id": "coat_electric",
			"name": "Powłoka prądowa",
			"cost": {"przewód": 1},
			"effect": "coating", "coating": "electric", "charges": 3,
			"desc": "Broń razi PRĄDEM przez 3 ciosy — omija grubą skórę.",
		},
		{
			"id": "reinforce",
			"name": "Wzmocniony chwyt",
			"cost": {"złom": 2},
			"effect": "bonus_damage", "amount": 2,
			"desc": "Trwałe +2 do obrażeń w zwarciu.",
		},
	]
