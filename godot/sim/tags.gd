class_name Tags
extends RefCounted
## Tag -> implied-property inference. This is the FOUNDATION of the systemic
## engine: rules match on properties, not object ids, so one rule works on
## anything carrying the right tag.
##
## TODO(port): copy the FULL inference table from
##   dungeon_kraulem/engine/systemic.py  (the tag/property mapping, ~lines 75-128).
## The entries below are a starter subset to prove the shape — complete them
## against the Python source and lock with a GUT test mirroring the Python test.

const IMPLIED := {
	"robot": ["metal", "conductive"],
	"machine": ["metal", "conductive"],
	"electronic": ["conductive"],
	"water": ["wet", "conductive"],
	"liquid": ["wet"],
	"wood": ["flammable"],
	"wooden": ["flammable"],
	"furniture": ["flammable"],
	"cloth": ["flammable"],
	"oil": ["flammable"],
	"gas": ["flammable"],
	"metal": ["conductive"],
	"organic": ["flammable", "bleeds"],
}

## Returns a set-like Dictionary {property: true} for an entity's tags.
static func properties_for(tags: Array) -> Dictionary:
	var props := {}
	for t in tags:
		props[t] = true
		if IMPLIED.has(t):
			for p in IMPLIED[t]:
				props[p] = true
	return props

static func has_property(tags: Array, prop: String) -> bool:
	return properties_for(tags).has(prop)
