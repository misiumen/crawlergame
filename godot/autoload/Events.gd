extends Node
## Signal bus. The SIM CORE emits these; PRESENTATION nodes listen and animate.
## The sim never touches a Godot node — this is the only bridge.

signal entity_moved(entity_id: int, from_cell: Vector2i, to_cell: Vector2i)
signal damage_dealt(target_id: int, amount: int, dmg_type: String, zone: String)
signal status_applied(target_id: int, status: String, turns: int)
signal status_ticked(target_id: int, status: String, amount: int)
signal limb_broken(target_id: int, zone: String)
signal entity_died(entity_id: int)

signal combat_started(participant_ids: Array)
signal combat_ended()
signal turn_advanced(side: String, round_num: int)

signal systemic_chain(source_id: int, target_id: int, element: String, result: String)
signal log_line(text: String, category: String)
signal audience_changed(delta: int, reason: String)
