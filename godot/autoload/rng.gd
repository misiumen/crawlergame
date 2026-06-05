extends Node
## Single seeded RNG so runs are reproducible. Route ALL randomness through here.
## (Note: the Python game uses a different RNG algorithm, so the GDScript port
## cannot reproduce identical seeded *sequences* — parity is checked on pure
## transforms with explicit inputs, not on whole seeded runs. See GODOT_PORT_PLAN §6.)

var _rng := RandomNumberGenerator.new()

func reseed(s: int) -> void:
	_rng.seed = s

func d(sides: int) -> int:
	return _rng.randi_range(1, sides)

func roll(n: int, sides: int, bonus: int = 0) -> int:
	var total := bonus
	for _i in n:
		total += _rng.randi_range(1, sides)
	return total

func range_i(a: int, b: int) -> int:
	return _rng.randi_range(a, b)

func chance(p: float) -> bool:
	return _rng.randf() < p

func pick(arr: Array) -> Variant:
	return arr[_rng.randi_range(0, arr.size() - 1)] if arr.size() > 0 else null
