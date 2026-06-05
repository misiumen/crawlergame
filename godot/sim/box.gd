class_name GameBox
extends RefCounted
## An unopened lootbox. All drop pipelines produce boxes; player opens manually.
## Port of engine/handlers/boxes.py box entity + reveal logic.

# 3-line Dinniman-tone reveal per source. Matches boxes.py _REVEAL_BY_SOURCE.
const REVEAL_FLAVOR: Dictionary = {
	"boss": [
		'Pęka. Naklejka „{tier}" schodzi zbyt łatwo.',
		'{contents}',
		'Konferansjer: „Brąz za pierwszego trupa z imieniem. Srebro to wyższa półka."',
	],
	"sponsor": [
		'Pakiet {source}. Lakowana pieczęć. Pęka z sykiem.',
		'{contents}',
		'{source}: „{tagline}"',
	],
	"widownia": [
		'Z górnej rampy ktoś rzuca pakiet. Krzyczał: „TO ZA TE NAPIWKI!"',
		'{contents}',
		'Pączek się obtłucze.',
	],
	"mob": [
		'Spod trupa wypada zafoliowany prezent. Folia za krucha, za błyszcząca.',
		'{contents}',
		'Loch redystrybuuje. Statystycznie.',
	],
	"level_up": [
		'System brzęczy triumfalnie: „AWANS POTWIERDZONY".',
		'{contents}',
		'Konferansjer: „Rośniesz w siłę, zawodniku. Widownia to uwielbia."',
	],
	"chest": [
		'Zamek pęka z trzaskiem. Zapach starego żelaza.',
		'{contents}',
		'Nic nie wybuchło. Dobry znak.',
	],
}

var source: String = "mob"       # boss / sponsor / widownia / mob / level_up / chest
var source_name: String = ""     # display name (e.g. "NovaChem Biotech")
var rarity: String = Rarity.COMMON
var contents: Array = []         # [{type: "item_key"/"material"/"scroll", key, qty}]
var sponsor_tagline: String = ""
var opened: bool = false

func _init(_source: String = "mob", _source_name: String = "",
		_rarity: String = Rarity.COMMON) -> void:
	source = _source
	source_name = _source_name
	rarity = _rarity

func tier_label() -> String:
	return Rarity.box_label(rarity)

func display_name() -> String:
	var n := tier_label()
	if source_name:
		n += ' od „' + source_name + '"'
	return n

func reveal_lines(contents_line: String) -> Array:
	var template: Array = REVEAL_FLAVOR.get(source, REVEAL_FLAVOR["mob"])
	var result: Array = []
	for line in template:
		result.append(
			line.replace("{tier}", tier_label())
				.replace("{source}", source_name if source_name else "Sponsor")
				.replace("{tagline}", sponsor_tagline if sponsor_tagline else "Brak komentarza.")
				.replace("{contents}", contents_line)
		)
	return result
