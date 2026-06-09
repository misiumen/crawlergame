class_name BiomeGimmicks
extends RefCounted
## Per-biome gimmicks, ported from pygame engine/biome_gimmicks.py. Each route's
## biome has one light, distinctive quirk that fires periodically while you're on
## a floor of that biome — a flavor line + a tiny mechanical nudge (audience, a
## little HP, scrap, a stray hazard). Punctuation, not a second combat system.
##
## Fired by BoardView every few floor-turns. tick() returns event dicts; a
## "biome_gimmick" event carries {text, kind} for the log.

## Resolve the quirk for `floor`'s biome. Returns a list of events (possibly empty).
static func tick(floor, sim, rng: RandomNumberGenerator) -> Array:
	var p = sim.player()
	match floor.biome:
		"sortownia", "biome_katakumby_faktur":
			var n := rng.randi_range(1, 2)
			sim.materials["złom"] = int(sim.materials.get("złom", 0)) + n
			return [_line("Zwał złomu się osypuje — coś użytecznego wypada. (+%d złom)" % n)]
		"konflikt", "biome_oboz_goblinski", "biome_tunel_karnawalowy", "biome_redakcja_krawedzi":
			if floor.audience != null: floor.audience.change(2, "biome")
			return [_line("Widownia wyje na widok rywalizacji. (+widownia)")]
		"okopy_frontowe":
			# Trenches: distant artillery shakes loose rubble (the pygame gimmick).
			if p.hp > 1:
				p.hp -= 1
				return [{"type": "damage", "target": sim.player_id, "amount": 1, "dmg_type": "physical"},
					_line("Daleki wybuch wstrząsa stropem. Spada gruz. (−1 HP)")]
			return [_line("Artyleria dudni gdzieś nad sufitem.")]
		"zoo_korporacyjne":
			if floor.audience != null: floor.audience.change(2, "biome")
			return [_line("Klatki w korytarzu wybuchają piskiem zachwytu. (+widownia)")]
		"muzeum_spektakli":
			if floor.audience != null: floor.audience.change(1, "biome")
			return [_line("Z głośnika: nagranie najlepszych zgonów poprzednich sezonów.")]
		"bar_skurczybyk":
			if p.hp < p.max_hp:
				var bh := mini(2, p.max_hp - p.hp); p.hp += bh
				return [{"type": "heal", "target": sim.player_id, "amount": bh},
					_line("Barman „Skurczybyk” podsuwa szot. Niby bezalkoholowy. (+%d HP)" % bh)]
			return [_line("Z baru niesie się czyjeś karaoke. Ktoś cierpi.")]
		"swiatynia_konferansjera", "biome_swiatynia_konferansjera":
			if floor.audience != null: floor.audience.change(4, "biome")
			return [_line("Z głośników grzmi hymn Konferansjera. Tłum szaleje. (+widownia)")]
		"pulapki", "biome_siec_kanalizacyjna":
			# A stray hazard appears on a random walkable, empty cell.
			var c := _random_free_cell(sim, rng)
			if c != Vector2i(-1, -1):
				var kind := "fire" if floor.biome == "pulapki" else "water"
				sim.board.set_hazard(c, kind)
				return [{"type": "hazard_placed", "kind": kind, "cell": c},
					_line("Coś iskrzy w ścianach — rozlewa się %s." % kind)]
			return []
		"zamknieta":
			var ev: Array = []
			if p.hp < p.max_hp:
				var h := mini(2, p.max_hp - p.hp); p.hp += h
				ev.append({"type": "heal", "target": sim.player_id, "amount": h})
			if p.mana < p.max_mana: p.mana += 1
			ev.append(_line("Cisza trasy koi nerwy. (+HP, +mana)"))
			return ev
		"serwis", "biome_farma_klonow":
			sim.materials["przewód"] = int(sim.materials.get("przewód", 0)) + 1
			return [_line("Panel serwisowy sypie elektroniką. (+przewód)")]
		"lawowe_tunele", "biome_lawowe_tunele", "biome_elfia_kolonia":
			if rng.randf() < 0.6 and p.hp > 1:
				p.hp = maxi(1, p.hp - 1)
				return [{"type": "damage", "target": sim.player_id, "amount": 1, "dmg_type": "fire"},
					_line("Żar z głębi liże ściany. (−1 HP)")]
			return [_line("Powietrze drży od gorąca.")]
		_:
			# Unknown/quiet biome: a small crowd flicker.
			if floor.audience != null: floor.audience.change(1, "biome")
			return [_line("Coś się porusza w mroku korytarza.")]

static func _line(text: String) -> Dictionary:
	return {"type": "biome_gimmick", "text": text}

static func _random_free_cell(sim, rng: RandomNumberGenerator) -> Vector2i:
	var b = sim.board
	for _try in 12:
		var c := Vector2i(rng.randi_range(0, b.w - 1), rng.randi_range(0, b.h - 1))
		if b.in_bounds(c) and not b.is_wall(c) and b.occupant_at(c) == -1 and b.hazard_at(c) == "":
			return c
	return Vector2i(-1, -1)
