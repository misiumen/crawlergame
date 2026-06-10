class_name BiomeThemes
extends RefCounted
## Per-biome VISUAL IDENTITY (Phase B.1). Each route biome gets its own palette,
## floor pattern, scattered set-dressing props, wall décor, ambient colour grade
## and light level — so Lawowe Tunele reads as black basalt cut by glowing
## cracks, Muzeum as bright marble and gilt frames, Bar as neon over dark planks.
## Pure data; BoardView paints it. When real tilesets arrive (Phase B.2) these
## palettes become the tint/selection layer, so nothing here is throwaway.
##
## Theme fields (DEFAULT supplies any a biome omits):
##   floor_a/floor_b  checkerboard base · wall/wall_hi/grid  structure colours
##   accent           biome signature colour (board frame, HUD label)
##   ambient          CanvasModulate grade (keep channels 0.7–1.0)
##   light            player-light energy (0 = none; high in dark biomes)
##   pattern/pattern_col   floor motif: tiles|planks|hatch|rubble|cracks|dots|stripes|puddles|none
##   props            [{kind, chance(%), col[, col2]}] floor set-dressing
##   wall_props       [{kind, chance(%), col[, col2]}] wall décor: frame|pipe|neon|bars|poster

const DEFAULT := {
	"floor_a": Color("161a23"), "floor_b": Color("1b202b"),
	"wall": Color("343c4e"), "wall_hi": Color("545e7a"), "grid": Color("282e3c"),
	"accent": Color("60cee9"), "ambient": Color(1, 1, 1), "light": 0.0,
	"pattern": "none", "pattern_col": Color("20242e"),
	"props": [], "wall_props": [],
}

const THEMES := {
	# Floor 1 intake — the clean corporate stage before the show gets weird.
	"": {"pattern": "tiles", "pattern_col": Color("121620")},

	"sortownia": {   # rust, scrap piles, amber work-lights
		"floor_a": Color("231d16"), "floor_b": Color("2a221a"),
		"wall": Color("4e4334"), "wall_hi": Color("7a6a54"), "grid": Color("3c3528"),
		"accent": Color("f4a24a"), "ambient": Color(0.97, 0.92, 0.86), "light": 0.25,
		"pattern": "rubble", "pattern_col": Color("3a2f22"),
		"props": [{"kind": "scrap", "chance": 11, "col": Color("8a7a5a"), "col2": Color("5e523c")},
			{"kind": "cable", "chance": 4, "col": Color("b0763c")}],
		"wall_props": [{"kind": "pipe", "chance": 8, "col": Color("6e6048")}],
	},
	"konflikt": {    # ash, scorch marks, old blood
		"floor_a": Color("1f1d1d"), "floor_b": Color("262222"),
		"wall": Color("4a3c3c"), "wall_hi": Color("766060"), "grid": Color("362e2e"),
		"accent": Color("e45656"), "ambient": Color(0.92, 0.86, 0.86), "light": 0.2,
		"pattern": "cracks", "pattern_col": Color("151313"),
		"props": [{"kind": "scorch", "chance": 9, "col": Color("0e0c0c")},
			{"kind": "bone", "chance": 3, "col": Color("cfc4b0")}],
		"wall_props": [{"kind": "poster", "chance": 6, "col": Color("7a3030"), "col2": Color("a05050")}],
	},
	"pulapki": {     # hazard-stripe industrial yellow, taped-off wiring
		"floor_a": Color("22210f"), "floor_b": Color("292813"),
		"wall": Color("4e4a20"), "wall_hi": Color("7a7434"), "grid": Color("3a3818"),
		"accent": Color("f4e04a"), "ambient": Color(1.0, 0.98, 0.85), "light": 0.15,
		"pattern": "stripes", "pattern_col": Color("2e2c12"),
		"props": [{"kind": "cable", "chance": 8, "col": Color("f4c260")},
			{"kind": "tape", "chance": 6, "col": Color("e0d24a")}],
	},
	"zamknieta": {   # cold, dusty, taped-shut quiet
		"floor_a": Color("191d22"), "floor_b": Color("1e242b"),
		"wall": Color("39434e"), "wall_hi": Color("5a6a7a"), "grid": Color("2a323c"),
		"accent": Color("9fb4c8"), "ambient": Color(0.86, 0.9, 0.97), "light": 0.1,
		"pattern": "dots", "pattern_col": Color("242c34"),
		"props": [{"kind": "tape", "chance": 6, "col": Color("6a7a8a")}],
	},
	"serwis": {      # teal service ducts, cable runs everywhere
		"floor_a": Color("14211f"), "floor_b": Color("182826"),
		"wall": Color("2e4a46"), "wall_hi": Color("4e766f"), "grid": Color("223633"),
		"accent": Color("4ad8c8"), "ambient": Color(0.88, 0.97, 0.95), "light": 0.2,
		"pattern": "hatch", "pattern_col": Color("1b2c2a"),
		"props": [{"kind": "cable", "chance": 13, "col": Color("4ad8c8")},
			{"kind": "vat", "chance": 3, "col": Color("3a5c56"), "col2": Color("4ad8c8")}],
		"wall_props": [{"kind": "pipe", "chance": 12, "col": Color("44605a")}],
	},
	"skrot": {       # off-map violet, glitchy hatching
		"floor_a": Color("1c1626"), "floor_b": Color("221a2e"),
		"wall": Color("423458"), "wall_hi": Color("68548a"), "grid": Color("302842"),
		"accent": Color("b462dc"), "ambient": Color(0.92, 0.86, 1.0), "light": 0.25,
		"pattern": "hatch", "pattern_col": Color("2a2138"),
		"props": [{"kind": "ember", "chance": 5, "col": Color("b462dc")}],
	},
	"okopy_frontowe": {   # mud, sandbags, propaganda posters
		"floor_a": Color("201a12"), "floor_b": Color("261f16"),
		"wall": Color("44382a"), "wall_hi": Color("6a5a44"), "grid": Color("322a1e"),
		"accent": Color("c8a050"), "ambient": Color(0.93, 0.88, 0.8), "light": 0.25,
		"pattern": "puddles", "pattern_col": Color("171209"),
		"props": [{"kind": "sandbag", "chance": 10, "col": Color("8a7448"), "col2": Color("a98f5c")},
			{"kind": "bone", "chance": 3, "col": Color("cfc4b0")}],
		"wall_props": [{"kind": "poster", "chance": 9, "col": Color("8a3434"), "col2": Color("c8a050")}],
	},
	"zoo_korporacyjne": {   # cage green, sawdust, paw prints
		"floor_a": Color("1a2114"), "floor_b": Color("202818"),
		"wall": Color("3c5030"), "wall_hi": Color("5e7a4c"), "grid": Color("2c3a22"),
		"accent": Color("7ed364"), "ambient": Color(0.92, 1.0, 0.88), "light": 0.15,
		"pattern": "dots", "pattern_col": Color("241f12"),
		"props": [{"kind": "paw", "chance": 11, "col": Color("54683c")}],
		"wall_props": [{"kind": "bars", "chance": 13, "col": Color("6a8a54")}],
	},
	"muzeum_spektakli": {   # bright marble + gilt frames (the LIGHT biome)
		"floor_a": Color("2a2a30"), "floor_b": Color("323239"),
		"wall": Color("56565e"), "wall_hi": Color("8a8a96"), "grid": Color("3e3e46"),
		"accent": Color("e8c878"), "ambient": Color(1.0, 1.0, 1.0), "light": 0.1,
		"pattern": "tiles", "pattern_col": Color("26262c"),
		"props": [{"kind": "pedestal", "chance": 7, "col": Color("76767e"), "col2": Color("8a8a96")}],
		"wall_props": [{"kind": "frame", "chance": 14, "col": Color("e8c878")}],
	},
	"bar_skurczybyk": {     # dark planks under magenta/cyan neon
		"floor_a": Color("16121e"), "floor_b": Color("1a1524"),
		"wall": Color("3a2a4a"), "wall_hi": Color("5e4478"), "grid": Color("281e36"),
		"accent": Color("ff5ad0"), "ambient": Color(0.8, 0.75, 0.92), "light": 0.45,
		"pattern": "planks", "pattern_col": Color("1f1830"),
		"props": [{"kind": "bottle", "chance": 8, "col": Color("5ad0ff"), "col2": Color("ff5ad0")},
			{"kind": "confetti", "chance": 4, "col": Color("ff5ad0"), "col2": Color("5ad0ff")}],
		"wall_props": [{"kind": "neon", "chance": 12, "col": Color("ff5ad0"), "col2": Color("5ad0ff")}],
	},
	"biome_oboz_goblinski": {   # palisade green-brown, bonfire embers
		"floor_a": Color("1c2012"), "floor_b": Color("222817"),
		"wall": Color("4a4424"), "wall_hi": Color("70683a"), "grid": Color("343018"),
		"accent": Color("a0c83c"), "ambient": Color(0.95, 0.97, 0.85), "light": 0.3,
		"pattern": "rubble", "pattern_col": Color("262a14"),
		"props": [{"kind": "tree", "chance": 6, "col": Color("3c5c28"), "col2": Color("5c4424")},
			{"kind": "ember", "chance": 6, "col": Color("e88a3c")}],
		"wall_props": [{"kind": "bars", "chance": 10, "col": Color("6a5a30")}],
	},
	"biome_siec_kanalizacyjna": {   # sewer green dark, puddles, pipes
		"floor_a": Color("12201a"), "floor_b": Color("162620"),
		"wall": Color("2a4a3e"), "wall_hi": Color("44705e"), "grid": Color("1e342c"),
		"accent": Color("50d890"), "ambient": Color(0.82, 0.95, 0.85), "light": 0.35,
		"pattern": "puddles", "pattern_col": Color("0e2c1e"),
		"props": [{"kind": "puddle", "chance": 10, "col": Color("1a4a34")}],
		"wall_props": [{"kind": "pipe", "chance": 15, "col": Color("4a6a5a")}],
	},
	"biome_tunel_karnawalowy": {   # night carnival: striped tiles + confetti
		"floor_a": Color("2a1620"), "floor_b": Color("321a26"),
		"wall": Color("5a2848"), "wall_hi": Color("8a4070"), "grid": Color("40203a"),
		"accent": Color("ff7ab4"), "ambient": Color(1.0, 0.9, 0.97), "light": 0.3,
		"pattern": "stripes", "pattern_col": Color("471f38"),
		"props": [{"kind": "confetti", "chance": 14, "col": Color("ff7ab4"), "col2": Color("5ad0ff")},
			{"kind": "bottle", "chance": 4, "col": Color("ffd24a"), "col2": Color("ff7ab4")}],
		"wall_props": [{"kind": "neon", "chance": 8, "col": Color("ff7ab4"), "col2": Color("ffd24a")}],
	},
	"biome_katakumby_faktur": {    # candlelit bone-brown bureaucracy crypt
		"floor_a": Color("1e1a14"), "floor_b": Color("241f18"),
		"wall": Color("463c2e"), "wall_hi": Color("6e604a"), "grid": Color("342c20"),
		"accent": Color("f0b850"), "ambient": Color(0.9, 0.85, 0.75), "light": 0.4,
		"pattern": "dots", "pattern_col": Color("181410"),
		"props": [{"kind": "candle", "chance": 9, "col": Color("f0b850")},
			{"kind": "bone", "chance": 6, "col": Color("cfc4b0")}],
		"wall_props": [{"kind": "frame", "chance": 6, "col": Color("8a7a5a")}],
	},
	"biome_farma_klonow": {        # sterile mint lab, biofluid vats
		"floor_a": Color("222a28"), "floor_b": Color("283230"),
		"wall": Color("4a6660"), "wall_hi": Color("729a92"), "grid": Color("364a46"),
		"accent": Color("6ee8d0"), "ambient": Color(0.95, 1.0, 0.98), "light": 0.1,
		"pattern": "tiles", "pattern_col": Color("1e2624"),
		"props": [{"kind": "vat", "chance": 9, "col": Color("3a6a60"), "col2": Color("6ee8d0")}],
		"wall_props": [{"kind": "pipe", "chance": 8, "col": Color("547a72")}],
	},
	"biome_elfia_kolonia": {       # forest through concrete: wood + leaves
		"floor_a": Color("18220f"), "floor_b": Color("1d2913"),
		"wall": Color("3c5424"), "wall_hi": Color("5e7e3c"), "grid": Color("2c3e1c"),
		"accent": Color("8ae060"), "ambient": Color(0.9, 1.0, 0.86), "light": 0.2,
		"pattern": "dots", "pattern_col": Color("223214"),
		"props": [{"kind": "tree", "chance": 10, "col": Color("2e5c20"), "col2": Color("6a4a2a")},
			{"kind": "leaf", "chance": 9, "col": Color("4a7a30")}],
	},
	"biome_redakcja_krawedzi": {   # newsroom blue-grey, monitor glow
		"floor_a": Color("161c24"), "floor_b": Color("1a212b"),
		"wall": Color("33445c"), "wall_hi": Color("51698a"), "grid": Color("25313f"),
		"accent": Color("5ab4ff"), "ambient": Color(0.9, 0.94, 1.0), "light": 0.2,
		"pattern": "tiles", "pattern_col": Color("121820"),
		"props": [{"kind": "desk", "chance": 8, "col": Color("3a4a5e"), "col2": Color("5ab4ff")},
			{"kind": "cable", "chance": 5, "col": Color("51698a")}],
		"wall_props": [{"kind": "neon", "chance": 8, "col": Color("5ab4ff"), "col2": Color("9fd4ff")}],
	},
	"biome_swiatynia_konferansjera": {   # gold-on-black temple of the host
		"floor_a": Color("221c10"), "floor_b": Color("281f12"),
		"wall": Color("564417"), "wall_hi": Color("8a6c28"), "grid": Color("3c3014"),
		"accent": Color("ffd24a"), "ambient": Color(1.0, 0.93, 0.78), "light": 0.3,
		"pattern": "tiles", "pattern_col": Color("1b1608"),
		"props": [{"kind": "candle", "chance": 10, "col": Color("ffd24a")},
			{"kind": "pedestal", "chance": 6, "col": Color("6a5420"), "col2": Color("8a6c28")}],
		"wall_props": [{"kind": "frame", "chance": 10, "col": Color("ffd24a")}],
	},
	"biome_lawowe_tunele": {       # black basalt split by glowing lava cracks
		"floor_a": Color("16100e"), "floor_b": Color("1b1310"),
		"wall": Color("38231c"), "wall_hi": Color("5c382a"), "grid": Color("261812"),
		"accent": Color("ff6a2a"), "ambient": Color(0.78, 0.68, 0.66), "light": 0.55,
		"pattern": "cracks", "pattern_col": Color("e84a1a"),
		"props": [{"kind": "ember", "chance": 12, "col": Color("ff6a2a")}],
	},
}

## Theme for a biome key, with every DEFAULT field guaranteed present.
static func theme_for(biome: String) -> Dictionary:
	var t := DEFAULT.duplicate(true)
	var over: Dictionary = THEMES.get(biome, {})
	for k in over:
		t[k] = over[k]
	return t
