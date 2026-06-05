extends Node
## Run-level state + mode switch (Explore <-> Combat). Skeleton for Phase 0;
## fills out across Phases 1-5. This is the GDScript heir to the *flow* parts
## of the old game.py (NOT its embedded rules — those go to res://sim/).

enum Mode { TITLE, EXPLORE, COMBAT }

var mode: Mode = Mode.TITLE
var run_seed: int = 0
var floor_number: int = 1

func new_run(seed_value: int) -> void:
	run_seed = seed_value
	floor_number = 1
	Rng.reseed(seed_value)
	mode = Mode.EXPLORE
	Events.log_line.emit("Nowy bieg.", "system")

func enter_combat(participant_ids: Array) -> void:
	mode = Mode.COMBAT
	Events.combat_started.emit(participant_ids)

func exit_combat() -> void:
	mode = Mode.EXPLORE
	Events.combat_ended.emit()
