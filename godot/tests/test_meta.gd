extends SceneTree
## Run-summary + meta-progression tests. Run:
## godot --headless --path godot -s res://tests/test_meta.gd

var _f := 0
var _n := 0

func _ck(c: bool, l: String) -> void:
	_n += 1
	print(("  OK  " if c else "  XX  ") + l)
	if not c:
		_f += 1

func _initialize() -> void:
	print("=== meta / run-summary tests ===")
	var rng := RandomNumberGenerator.new()
	rng.seed = 11

	# fresh meta state (delete any prior save so the run is deterministic)
	if FileAccess.file_exists(Meta.SAVE_PATH):
		DirAccess.remove_absolute(Meta.SAVE_PATH)

	# --- run summary build + render ---
	var data := Encounters.floor()
	var fl = Floor.new(data)
	fl.player.run_kills = 4
	fl.player.run_corpses_salvaged = 2
	fl.audience.rating = 55
	fl.audience.peak = 72
	Classes.assign_class(fl.player, "showman")
	var summary := RunSummary.build(fl, false, rng)
	_ck(int(summary["kills"]) == 4, "summary captures kills")
	_ck(int(summary["audience_peak"]) == 72, "summary captures audience peak")
	_ck(summary["class_key"] == "showman", "summary captures the class")
	_ck(summary["anti_host_line"] != "", "a death gets an anti-host line")
	var lines := RunSummary.render_lines(summary)
	_ck(lines.size() > 4, "render_lines produces a multi-line screen")
	var joined := "\n".join(lines)
	_ck(joined.contains("Zabójstwa"), "screen shows the kills stat label")
	_ck(joined.contains("Showman"), "screen shows the class name")

	# --- meta: first run unlocks the audience-peak + 'any run finished' options ---
	var newly := Meta.record_run(summary)
	_ck("Drugi cykl" in newly, "any finished run unlocks 'Drugi cykl'")
	_ck("Tunel Karnawałowy" in newly, "audience peak 72 (>=60) unlocks 'Tunel Karnawałowy'")
	_ck("Zhańbiony Showman" in newly, "audience peak 72 (>=70) unlocks 'Zhańbiony Showman'")
	_ck(not ("Dziedzic Kanału 7" in newly), "audience peak 72 (<120) does NOT unlock 'Dziedzic'")

	# --- persistence: a second run does not re-award the same unlocks ---
	var summary2 := RunSummary.build(fl, false, rng)
	var newly2 := Meta.record_run(summary2)
	_ck(not ("Drugi cykl" in newly2), "already-unlocked options are not re-awarded")
	# but total_runs climbed, so the >=3-runs option is still pending (needs run 3)
	var st := Meta.load_state()
	_ck(int(st["total_runs"]) == 2, "total_runs persisted across two recorded runs")

	# --- pacifist + sponsor conditions ---
	var fl2 = Floor.new(Encounters.floor())
	fl2.player.run_kills = 0
	fl2.audience.peak = 10
	# give a sponsor high attention so the sponsor_max unlock can fire
	fl2.sponsors.attention = {fl2.sponsors.all_keys()[0]: 22} if not fl2.sponsors.all_keys().is_empty() else {}
	var s3 := RunSummary.build(fl2, false, rng)
	var newly3 := Meta.record_run(s3)
	_ck("Mosiężny Pierścień Producenta" in newly3, "a zero-kill run unlocks the pacifist ring")

	# --- victory_class condition (occultist + victory) ---
	var fl3 = Floor.new(Encounters.floor())
	Classes.assign_class(fl3.player, "occultist")
	var s4 := RunSummary.build(fl3, true, rng)
	var newly4 := Meta.record_run(s4)
	_ck("Elfia Kolonia" in newly4, "victory as occultist unlocks 'Elfia Kolonia'")
	var sV := RunSummary.render_lines(s4)
	_ck("\n".join(sV).contains("FINAŁ"), "victory screen shows the finale line")

	# cleanup the test save
	if FileAccess.file_exists(Meta.SAVE_PATH):
		DirAccess.remove_absolute(Meta.SAVE_PATH)

	print("=== %d checks, %d failed ===" % [_n, _f])
	quit(_f)
