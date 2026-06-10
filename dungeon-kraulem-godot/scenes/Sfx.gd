extends Node
## Procedural audio (Phase D). Everything is SYNTHESIZED at runtime — chiptune
## SFX and short generative music loops — so the game ships with zero external
## assets and the retro-neon aesthetic gets a matching voice. Streams are
## rendered lazily on first use and cached.
##
## API:  play("hit") · music("combat") · set_volume("SFX"|"Music"|"Master", db)

const RATE := 22050

var _cache: Dictionary = {}          # name -> AudioStreamWAV
var _pool: Array = []                # AudioStreamPlayer pool for SFX
var _mus_a: AudioStreamPlayer
var _mus_b: AudioStreamPlayer
var _mus_active := ""                # current mood key
var _mus_front := true               # which player is fading IN
var _rng := RandomNumberGenerator.new()

func _ready() -> void:
	_rng.seed = 0xD0C5
	# Dedicated buses so the settings menu can mix them.
	for bus in ["Music", "SFX"]:
		if AudioServer.get_bus_index(bus) == -1:
			AudioServer.add_bus()
			AudioServer.set_bus_name(AudioServer.get_bus_count() - 1, bus)
			AudioServer.set_bus_send(AudioServer.get_bus_count() - 1, "Master")
	for i in 10:
		var p := AudioStreamPlayer.new()
		p.bus = "SFX"
		add_child(p)
		_pool.append(p)
	_mus_a = AudioStreamPlayer.new(); _mus_a.bus = "Music"; add_child(_mus_a)
	_mus_b = AudioStreamPlayer.new(); _mus_b.bus = "Music"; add_child(_mus_b)
	_mus_a.volume_db = -60.0
	_mus_b.volume_db = -60.0

func _process(dt: float) -> void:
	if _mus_a == null:
		return
	# Music crossfade: the front player rises to 0 db-ish, the back one sinks out.
	var front := _mus_a if _mus_front else _mus_b
	var back := _mus_b if _mus_front else _mus_a
	front.volume_db = minf(front.volume_db + dt * 24.0, -8.0)
	back.volume_db = maxf(back.volume_db - dt * 24.0, -60.0)
	if back.volume_db <= -59.0 and back.playing:
		back.stop()

func set_volume(bus: String, db: float) -> void:
	var i := AudioServer.get_bus_index(bus)
	if i != -1:
		AudioServer.set_bus_volume_db(i, db)
		AudioServer.set_bus_mute(i, db <= -39.0)

func get_volume(bus: String) -> float:
	var i := AudioServer.get_bus_index(bus)
	return AudioServer.get_bus_volume_db(i) if i != -1 else 0.0

# ── SFX ───────────────────────────────────────────────────────────────────────

## Segment: {w: sine|square|saw|tri|noise, f0, f1, d (sec), v0, v1}
const SFX := {
	"hit":      [{"w": "noise", "f0": 900, "f1": 300, "d": 0.07, "v0": 0.7, "v1": 0.2},
		{"w": "square", "f0": 160, "f1": 70, "d": 0.08, "v0": 0.6, "v1": 0.0}],
	"crit":     [{"w": "noise", "f0": 1400, "f1": 200, "d": 0.1, "v0": 0.9, "v1": 0.3},
		{"w": "square", "f0": 220, "f1": 50, "d": 0.16, "v0": 0.8, "v1": 0.0}],
	"whoosh":   [{"w": "noise", "f0": 500, "f1": 1800, "d": 0.12, "v0": 0.25, "v1": 0.0}],
	"death":    [{"w": "saw", "f0": 300, "f1": 40, "d": 0.3, "v0": 0.7, "v1": 0.0},
		{"w": "noise", "f0": 700, "f1": 100, "d": 0.2, "v0": 0.4, "v1": 0.0}],
	"crunch":   [{"w": "noise", "f0": 350, "f1": 120, "d": 0.16, "v0": 0.7, "v1": 0.1},
		{"w": "square", "f0": 90, "f1": 60, "d": 0.08, "v0": 0.4, "v1": 0.0}],
	"craft_ok": [{"w": "square", "f0": 440, "f1": 440, "d": 0.07, "v0": 0.4, "v1": 0.3},
		{"w": "square", "f0": 660, "f1": 660, "d": 0.07, "v0": 0.4, "v1": 0.3},
		{"w": "square", "f0": 880, "f1": 880, "d": 0.12, "v0": 0.45, "v1": 0.0}],
	"craft_bad": [{"w": "square", "f0": 300, "f1": 240, "d": 0.1, "v0": 0.4, "v1": 0.2},
		{"w": "square", "f0": 200, "f1": 120, "d": 0.18, "v0": 0.4, "v1": 0.0}],
	"explode":  [{"w": "noise", "f0": 2000, "f1": 60, "d": 0.45, "v0": 1.0, "v1": 0.0}],
	"pickup":   [{"w": "sine", "f0": 660, "f1": 990, "d": 0.09, "v0": 0.4, "v1": 0.2},
		{"w": "sine", "f0": 1320, "f1": 1320, "d": 0.07, "v0": 0.3, "v1": 0.0}],
	"tick":     [{"w": "square", "f0": 1900, "f1": 1700, "d": 0.025, "v0": 0.25, "v1": 0.0}],
	"snap":     [{"w": "square", "f0": 500, "f1": 980, "d": 0.1, "v0": 0.6, "v1": 0.3},
		{"w": "sine", "f0": 1320, "f1": 1760, "d": 0.18, "v0": 0.5, "v1": 0.0}],
	"jackpot":  [{"w": "square", "f0": 523, "f1": 523, "d": 0.08, "v0": 0.5, "v1": 0.4},
		{"w": "square", "f0": 659, "f1": 659, "d": 0.08, "v0": 0.5, "v1": 0.4},
		{"w": "square", "f0": 784, "f1": 784, "d": 0.08, "v0": 0.5, "v1": 0.4},
		{"w": "square", "f0": 1046, "f1": 1046, "d": 0.22, "v0": 0.6, "v1": 0.0}],
	"fanfare":  [{"w": "square", "f0": 392, "f1": 392, "d": 0.1, "v0": 0.5, "v1": 0.4},
		{"w": "square", "f0": 523, "f1": 523, "d": 0.1, "v0": 0.5, "v1": 0.4},
		{"w": "square", "f0": 659, "f1": 659, "d": 0.1, "v0": 0.5, "v1": 0.4},
		{"w": "square", "f0": 784, "f1": 784, "d": 0.3, "v0": 0.6, "v1": 0.0}],
	"chime":    [{"w": "sine", "f0": 880, "f1": 880, "d": 0.09, "v0": 0.4, "v1": 0.3},
		{"w": "sine", "f0": 1318, "f1": 1318, "d": 0.2, "v0": 0.4, "v1": 0.0}],
	"cast":     [{"w": "tri", "f0": 300, "f1": 1200, "d": 0.18, "v0": 0.5, "v1": 0.1},
		{"w": "noise", "f0": 2500, "f1": 3500, "d": 0.08, "v0": 0.15, "v1": 0.0}],
	"zap":      [{"w": "square", "f0": 1800, "f1": 300, "d": 0.1, "v0": 0.5, "v1": 0.1},
		{"w": "noise", "f0": 3000, "f1": 800, "d": 0.06, "v0": 0.3, "v1": 0.0}],
	"heal":     [{"w": "sine", "f0": 523, "f1": 784, "d": 0.14, "v0": 0.35, "v1": 0.2},
		{"w": "sine", "f0": 1046, "f1": 1046, "d": 0.1, "v0": 0.25, "v1": 0.0}],
	"holy":     [{"w": "tri", "f0": 392, "f1": 392, "d": 0.12, "v0": 0.4, "v1": 0.35},
		{"w": "tri", "f0": 523, "f1": 523, "d": 0.12, "v0": 0.4, "v1": 0.35},
		{"w": "tri", "f0": 659, "f1": 784, "d": 0.3, "v0": 0.45, "v1": 0.0}],
	"clang":    [{"w": "square", "f0": 740, "f1": 700, "d": 0.05, "v0": 0.6, "v1": 0.3},
		{"w": "tri", "f0": 1480, "f1": 1400, "d": 0.16, "v0": 0.3, "v1": 0.0}],
	"growl":    [{"w": "saw", "f0": 90, "f1": 55, "d": 0.3, "v0": 0.7, "v1": 0.1},
		{"w": "noise", "f0": 300, "f1": 120, "d": 0.2, "v0": 0.3, "v1": 0.0}],
	"pounce":   [{"w": "tri", "f0": 200, "f1": 700, "d": 0.1, "v0": 0.5, "v1": 0.2},
		{"w": "noise", "f0": 800, "f1": 300, "d": 0.08, "v0": 0.3, "v1": 0.0}],
	"phase":    [{"w": "sine", "f0": 800, "f1": 200, "d": 0.22, "v0": 0.3, "v1": 0.0}],
	"shove":    [{"w": "noise", "f0": 250, "f1": 90, "d": 0.12, "v0": 0.6, "v1": 0.0}],
	"deny":     [{"w": "square", "f0": 200, "f1": 150, "d": 0.09, "v0": 0.35, "v1": 0.0}],
	"click":    [{"w": "square", "f0": 1200, "f1": 900, "d": 0.03, "v0": 0.25, "v1": 0.0}],
	"open":     [{"w": "sine", "f0": 500, "f1": 900, "d": 0.07, "v0": 0.3, "v1": 0.0}],
	"close":    [{"w": "sine", "f0": 900, "f1": 500, "d": 0.07, "v0": 0.3, "v1": 0.0}],
	"gift":     [{"w": "sine", "f0": 784, "f1": 784, "d": 0.08, "v0": 0.4, "v1": 0.3},
		{"w": "sine", "f0": 988, "f1": 988, "d": 0.08, "v0": 0.4, "v1": 0.3},
		{"w": "sine", "f0": 1175, "f1": 1175, "d": 0.16, "v0": 0.4, "v1": 0.0}],
	"sting":    [{"w": "saw", "f0": 220, "f1": 233, "d": 0.4, "v0": 0.45, "v1": 0.2},
		{"w": "saw", "f0": 110, "f1": 104, "d": 0.4, "v0": 0.4, "v1": 0.0}],
	"descend":  [{"w": "tri", "f0": 500, "f1": 120, "d": 0.5, "v0": 0.5, "v1": 0.0}],
	"door":     [{"w": "noise", "f0": 200, "f1": 600, "d": 0.1, "v0": 0.3, "v1": 0.1},
		{"w": "square", "f0": 120, "f1": 120, "d": 0.06, "v0": 0.3, "v1": 0.0}],
	"blip":     [{"w": "square", "f0": 620, "f1": 660, "d": 0.045, "v0": 0.22, "v1": 0.0}],
	"speak":    [{"w": "tri", "f0": 330, "f1": 392, "d": 0.08, "v0": 0.3, "v1": 0.1}],
}

func play(name: String) -> void:
	var stream := _sfx_stream(name)
	if stream == null:
		return
	for p in _pool:
		if not p.playing:
			p.stream = stream
			p.pitch_scale = randf_range(0.94, 1.06)   # tiny variance, no machine-gun feel
			p.play()
			return

func _sfx_stream(name: String) -> AudioStreamWAV:
	if _cache.has(name):
		return _cache[name]
	if not SFX.has(name):
		return null
	var st := _render(SFX[name])
	_cache[name] = st
	return st

## Render a list of sequential segments into one 16-bit mono WAV stream.
func _render(segs: Array) -> AudioStreamWAV:
	var buf := StreamPeerBuffer.new()
	var ph := 0.0
	for seg in segs:
		var n := int(float(seg.d) * RATE)
		for i in n:
			var t := float(i) / maxf(1.0, float(n - 1))
			var f: float = lerpf(float(seg.f0), float(seg.f1), t)
			var v: float = lerpf(float(seg.v0), float(seg.v1), t)
			ph += f / RATE
			var s := 0.0
			match seg.w:
				"sine":   s = sin(TAU * ph)
				"square": s = 1.0 if fposmod(ph, 1.0) < 0.5 else -1.0
				"saw":    s = 2.0 * fposmod(ph, 1.0) - 1.0
				"tri":    s = 4.0 * absf(fposmod(ph, 1.0) - 0.5) - 1.0
				"noise":  s = _rng.randf() * 2.0 - 1.0
			buf.put_16(int(clampf(s * v, -1.0, 1.0) * 32000.0))
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = RATE
	wav.stereo = false
	wav.data = buf.data_array
	return wav

# ── Generative music ─────────────────────────────────────────────────────────
## Short seeded chiptune loops per mood, crossfaded. 4 bars of bass + lead.

const MOODS := {
	"title":   {"bpm": 92,  "root": 57, "scale": [0, 3, 5, 7, 10], "lead": "tri",  "bass": "tri",    "seed": 11},
	"explore": {"bpm": 104, "root": 55, "scale": [0, 2, 3, 7, 9],  "lead": "sine", "bass": "tri",    "seed": 23},
	"combat":  {"bpm": 136, "root": 52, "scale": [0, 3, 5, 6, 10], "lead": "square", "bass": "saw",  "seed": 37},
	"boss":    {"bpm": 144, "root": 50, "scale": [0, 1, 5, 7, 8],  "lead": "saw",  "bass": "square", "seed": 53},
}

func music(mood: String) -> void:
	if mood == _mus_active:
		return
	_mus_active = mood
	if _mus_a == null or mood == "":
		_mus_front = not _mus_front   # fade everything out
		return
	var st := _music_stream(mood)
	if st == null:
		return
	_mus_front = not _mus_front
	var front := _mus_a if _mus_front else _mus_b
	front.stream = st
	front.volume_db = -40.0
	front.play()

func _music_stream(mood: String) -> AudioStreamWAV:
	var key := "mus_" + mood
	if _cache.has(key):
		return _cache[key]
	if not MOODS.has(mood):
		return null
	var m: Dictionary = MOODS[mood]
	var rng := RandomNumberGenerator.new()
	rng.seed = int(m.seed)
	var spb := 60.0 / float(m.bpm)              # seconds per beat
	var step := spb / 2.0                       # 8th notes
	var steps := 4 * 4 * 2                      # 4 bars of 4/4 in 8ths
	var total := int(steps * step * RATE)
	var samples := PackedFloat32Array()
	samples.resize(total)
	# Bass: root/fifth alternating per beat. Lead: seeded walk over the scale.
	var scale: Array = m.scale
	var lead_deg := 0
	for s_i in steps:
		var t0 := int(s_i * step * RATE)
		var t1 := mini(int((s_i + 1) * step * RATE), total)
		# bass on every beat (even 8ths), an octave down
		var bass_midi: int = int(m.root) - 12 + (0 if (s_i / 2) % 2 == 0 else 7)
		var bass_f := 440.0 * pow(2.0, (bass_midi - 69) / 12.0)
		# lead: random walk, rests sometimes
		if rng.randf() < 0.78:
			lead_deg = clampi(lead_deg + rng.randi_range(-2, 2), 0, scale.size() * 2 - 1)
		var play_lead := rng.randf() < 0.7
		var lead_midi: int = int(m.root) + 12 + int(scale[lead_deg % scale.size()]) + 12 * (lead_deg / scale.size())
		var lead_f := 440.0 * pow(2.0, (lead_midi - 69) / 12.0)
		for i in range(t0, t1):
			var lt := float(i - t0) / maxf(1.0, float(t1 - t0))
			var env := minf(1.0, (1.0 - lt) * 4.0) * minf(1.0, lt * 24.0)
			var tm := float(i) / RATE
			var v := _wave(str(m.bass), bass_f, tm) * 0.16 * (1.0 if s_i % 2 == 0 else 0.4)
			if play_lead:
				v += _wave(str(m.lead), lead_f, tm) * 0.13 * env
			samples[i] += v
	var buf := StreamPeerBuffer.new()
	for i in total:
		buf.put_16(int(clampf(samples[i], -1.0, 1.0) * 30000.0))
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = RATE
	wav.stereo = false
	wav.data = buf.data_array
	wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
	wav.loop_begin = 0
	wav.loop_end = total
	_cache[key] = wav
	return wav

func _wave(w: String, f: float, t: float) -> float:
	var ph := f * t
	match w:
		"sine":   return sin(TAU * ph)
		"square": return 1.0 if fposmod(ph, 1.0) < 0.5 else -1.0
		"saw":    return 2.0 * fposmod(ph, 1.0) - 1.0
	return 4.0 * absf(fposmod(ph, 1.0) - 0.5) - 1.0   # tri
