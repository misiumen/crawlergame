"""P29.13 — Procedural chiptune audio asset generator.

Why: the audio pipeline was wired in P27 (engine/ui/audio.py + 10
SFX hooks + 4 music keys) but no actual sound files were ever
shipped — assets/audio/{sfx,music}/ didn't exist. Audit called it
out. Rather than depend on external sources we can't fetch, we
synthesize chiptune-style WAVs from stdlib (math + wave + struct).
The aesthetic matches assets/README.txt's "8-bit / chiptune" hint.

Output: 11 SFX + 4 music tracks in assets/audio/{sfx,music}/.
All 22050 Hz, 16-bit signed, mono. Total ~700 KB.

Re-run with `python -m dungeon_kraulem.tools.synthesize_audio` from
the repo root. Idempotent — overwrites in place.

Design choices per SFX (key → flavor):
  sponsor_chime    : two-note rise, soft sine
  floor_descent    : descending pitch sweep, saw-ish
  player_hit       : short noise burst, mid
  player_crit_hit  : heavier noise + sub
  hit_landed       : quick noise + blip
  hit_crit         : sharper noise + rising sub
  enemy_death      : 3-note descending minor, square
  player_death     : long descending fade + rumble
  attack_miss      : high quick blip
  attack_fumble    : sad-trombone two-note descent
  limb_broken      : crunchy noise + low descending blip

Music (loopable on the mixer side):
  menu     : slow bass + chord stabs, ominous
  explore  : minimal ambient drone + pings
  victory  : major fanfare ascending
  defeat   : minor descending lament
"""
from __future__ import annotations
import math
import os
import random
import struct
import wave
from typing import Iterable, List

# Sample rate. 22050 Hz is plenty for chiptune + halves file size vs 44k.
SR = 22050
# Output dirs (resolved relative to the repo root when run as module).
SFX_DIR = os.path.join("assets", "audio", "sfx")
MUSIC_DIR = os.path.join("assets", "audio", "music")


# ── Sample primitives ────────────────────────────────────────────────────

def _clip(x: float) -> int:
    """Float [-1, 1] → 16-bit signed int, hard clipped."""
    if x > 1.0: x = 1.0
    elif x < -1.0: x = -1.0
    return int(x * 32767)


def _write_wav(path: str, samples: List[float]) -> None:
    """Write a mono 16-bit WAV from a list of floats in [-1, 1]."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        raw = b"".join(struct.pack("<h", _clip(s)) for s in samples)
        w.writeframes(raw)


def _env_ad(n: int, attack_frac: float = 0.05,
            decay_frac: float = 0.95) -> List[float]:
    """Attack-decay envelope (no sustain). Returns float list of length n."""
    a = max(1, int(n * attack_frac))
    d = max(1, int(n * decay_frac))
    env: List[float] = []
    for i in range(a):
        env.append(i / a)
    for i in range(d):
        env.append(1.0 - (i / d))
    # Pad to n with zeros.
    while len(env) < n:
        env.append(0.0)
    return env[:n]


def _sine(freq: float, dur: float) -> List[float]:
    n = int(SR * dur)
    return [math.sin(2 * math.pi * freq * (i / SR)) for i in range(n)]


def _square(freq: float, dur: float, duty: float = 0.5) -> List[float]:
    n = int(SR * dur)
    out: List[float] = []
    period = SR / freq
    for i in range(n):
        phase = (i % period) / period
        out.append(1.0 if phase < duty else -1.0)
    return out


def _saw(freq: float, dur: float) -> List[float]:
    n = int(SR * dur)
    out: List[float] = []
    period = SR / freq
    for i in range(n):
        phase = (i % period) / period
        out.append(2.0 * phase - 1.0)
    return out


def _triangle(freq: float, dur: float) -> List[float]:
    n = int(SR * dur)
    out: List[float] = []
    period = SR / freq
    for i in range(n):
        phase = (i % period) / period
        out.append(4 * abs(phase - 0.5) - 1.0)
    return out


def _noise(dur: float, seed: int = 0) -> List[float]:
    n = int(SR * dur)
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(n)]


def _lowpass(samples: List[float], cutoff_freq: float) -> List[float]:
    """Cheap single-pole low-pass. Knocks the hash off white noise so
    hit SFX feel "thumpy" instead of shrill."""
    if not samples:
        return []
    # RC filter coefficient: alpha = dt / (RC + dt); RC = 1 / (2π fc).
    dt = 1.0 / SR
    rc = 1.0 / (2 * math.pi * max(1.0, cutoff_freq))
    a = dt / (rc + dt)
    out = [samples[0] * a]
    for x in samples[1:]:
        out.append(out[-1] + a * (x - out[-1]))
    return out


def _mix(*tracks: Iterable[float]) -> List[float]:
    """Sum tracks of possibly-different lengths. Pads with zeros."""
    tracks_list = [list(t) for t in tracks]
    n = max(len(t) for t in tracks_list)
    out = [0.0] * n
    for t in tracks_list:
        for i, v in enumerate(t):
            out[i] += v
    return out


def _scale(samples: List[float], factor: float) -> List[float]:
    return [s * factor for s in samples]


def _apply_env(samples: List[float], env: List[float]) -> List[float]:
    return [s * e for s, e in zip(samples, env)]


def _glide(freq_start: float, freq_end: float, dur: float,
           shape: str = "saw") -> List[float]:
    """Frequency glide from start to end Hz. Picks waveform by `shape`."""
    n = int(SR * dur)
    out: List[float] = []
    phase = 0.0
    for i in range(n):
        t = i / n
        f = freq_start + (freq_end - freq_start) * t
        phase += 2 * math.pi * f / SR
        if shape == "sine":
            out.append(math.sin(phase))
        elif shape == "square":
            out.append(1.0 if math.sin(phase) > 0 else -1.0)
        else:  # saw
            out.append(((phase / (2 * math.pi)) % 1.0) * 2 - 1)
    return out


def _silence(dur: float) -> List[float]:
    return [0.0] * int(SR * dur)


def _concat(*chunks: Iterable[float]) -> List[float]:
    out: List[float] = []
    for c in chunks:
        out.extend(c)
    return out


# ── SFX definitions ──────────────────────────────────────────────────────

def sfx_sponsor_chime() -> List[float]:
    """Two-note rise C5 → E5, soft sine, gentle pluck envelope."""
    a = _sine(523.25, 0.16)        # C5
    b = _sine(659.25, 0.18)        # E5
    a = _apply_env(a, _env_ad(len(a), 0.05, 0.95))
    b = _apply_env(b, _env_ad(len(b), 0.05, 0.95))
    return _concat(_scale(a, 0.55), _scale(b, 0.65))


def sfx_floor_descent() -> List[float]:
    """Long descending sweep — elevator-going-down vibe."""
    sweep = _glide(440.0, 90.0, 0.7, shape="saw")
    sweep = _apply_env(sweep, _env_ad(len(sweep), 0.08, 0.92))
    return _scale(sweep, 0.45)


def sfx_player_hit() -> List[float]:
    """Short low-passed noise burst + low thump."""
    n = _noise(0.10, seed=1)
    n = _lowpass(n, 900.0)
    n = _apply_env(n, _env_ad(len(n), 0.02, 0.98))
    thump = _apply_env(_sine(110, 0.06),
                       _env_ad(int(SR * 0.06), 0.02, 0.98))
    return _scale(_mix(_scale(n, 0.6), _scale(thump, 0.7)), 0.85)


def sfx_player_crit_hit() -> List[float]:
    """Heavier — longer noise + low rumble (50 Hz square sub)."""
    n = _noise(0.22, seed=2)
    n = _lowpass(n, 700.0)
    n = _apply_env(n, _env_ad(len(n), 0.02, 0.98))
    rumble = _apply_env(_square(55, 0.22),
                        _env_ad(int(SR * 0.22), 0.05, 0.95))
    return _scale(_mix(_scale(n, 0.55), _scale(rumble, 0.8)), 0.9)


def sfx_hit_landed() -> List[float]:
    """Quick thumpy noise + 200 Hz blip — landed strike on enemy."""
    n = _noise(0.08, seed=3)
    n = _lowpass(n, 1200.0)
    n = _apply_env(n, _env_ad(len(n), 0.02, 0.98))
    blip = _apply_env(_square(220, 0.04),
                      _env_ad(int(SR * 0.04), 0.02, 0.98))
    return _scale(_mix(_scale(n, 0.5), _scale(blip, 0.55)), 0.8)


def sfx_hit_crit() -> List[float]:
    """Sharper noise + rising sub-harmonic."""
    n = _noise(0.15, seed=4)
    n = _lowpass(n, 1800.0)
    n = _apply_env(n, _env_ad(len(n), 0.02, 0.98))
    rise = _glide(60, 180, 0.15, shape="square")
    rise = _apply_env(rise, _env_ad(len(rise), 0.05, 0.95))
    return _scale(_mix(_scale(n, 0.55), _scale(rise, 0.55)), 0.85)


def sfx_enemy_death() -> List[float]:
    """3-note descending minor — square wave, kid's keyboard feel."""
    notes = [(440.0, 0.10), (370.0, 0.10), (220.0, 0.18)]
    chunks = []
    for f, d in notes:
        x = _square(f, d)
        x = _apply_env(x, _env_ad(len(x), 0.05, 0.95))
        chunks.append(_scale(x, 0.5))
    return _concat(*chunks)


def sfx_player_death() -> List[float]:
    """Long descending tone + rumble + slow fade."""
    sweep = _glide(180.0, 40.0, 0.85, shape="saw")
    sweep = _apply_env(sweep, _env_ad(len(sweep), 0.05, 0.95))
    rumble = _apply_env(_square(45, 0.85),
                        _env_ad(int(SR * 0.85), 0.05, 0.95))
    mix = _mix(_scale(sweep, 0.55), _scale(rumble, 0.4))
    # Extra slow tail fade.
    out = []
    n = len(mix)
    for i, s in enumerate(mix):
        out.append(s * (1.0 - (i / n) ** 0.6))
    return out


def sfx_attack_miss() -> List[float]:
    """High quick blip → silence — felt like 'pyk'."""
    blip = _square(1318.5, 0.04)   # E6
    blip = _apply_env(blip, _env_ad(len(blip), 0.05, 0.95))
    return _scale(blip, 0.35)


def sfx_attack_fumble() -> List[float]:
    """Sad trombone — two-note descent with wobble."""
    a = _triangle(196.0, 0.10)     # G3
    b = _triangle(146.83, 0.14)    # D3
    a = _apply_env(a, _env_ad(len(a), 0.05, 0.95))
    b = _apply_env(b, _env_ad(len(b), 0.05, 0.95))
    return _concat(_scale(a, 0.55), _scale(b, 0.6))


def sfx_limb_broken() -> List[float]:
    """Crunchy noise burst + low descending blip — bone snap."""
    crunch = _noise(0.10, seed=5)
    crunch = _apply_env(crunch, _env_ad(len(crunch), 0.01, 0.99))
    snap = _glide(180, 60, 0.10, shape="square")
    snap = _apply_env(snap, _env_ad(len(snap), 0.02, 0.98))
    return _scale(_mix(_scale(crunch, 0.7), _scale(snap, 0.5)), 0.85)


# ── Music tracks ─────────────────────────────────────────────────────────
#
# Each track is a single buffer that loops cleanly via mixer.music. We
# make the START and END samples zero to avoid click artifacts at the
# loop seam.

def _seamless_loop(samples: List[float]) -> List[float]:
    """Force-zero the first and last few ms so a hard loop is silent
    at the join point."""
    fade = int(SR * 0.020)  # 20 ms
    for i in range(min(fade, len(samples))):
        samples[i] *= i / fade
    for i in range(min(fade, len(samples))):
        samples[-1 - i] *= i / fade
    return samples


def music_menu() -> List[float]:
    """8s slow bassline + dissonant chord stabs. Ominous corporate
    surveillance vibe (matches the title screen aesthetic)."""
    dur = 8.0
    # Bassline: A1 → F1 → G1 → A1 quarter-notes (2s each).
    bass_freqs = [55.0, 43.65, 49.0, 55.0]
    bass = []
    for f in bass_freqs:
        x = _square(f, 2.0, duty=0.4)
        x = _apply_env(x, _env_ad(len(x), 0.05, 0.95))
        bass.extend(_scale(x, 0.32))
    # Chord stabs on the off-beat, dissonant minor 7th flat-5.
    stab_times = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]
    pad = _silence(dur)
    for t in stab_times:
        idx = int(t * SR)
        stab_dur = 0.20
        chord = _mix(
            _scale(_sine(220, stab_dur), 0.18),
            _scale(_sine(311, stab_dur), 0.14),   # tritone
            _scale(_sine(415, stab_dur), 0.10),
        )
        chord = _apply_env(chord, _env_ad(len(chord), 0.05, 0.95))
        for i, s in enumerate(chord):
            if idx + i < len(pad):
                pad[idx + i] += s
    mix = _mix(bass, pad)
    return _seamless_loop(_scale(mix, 0.55))


def music_explore() -> List[float]:
    """P29.50 (#151) — rozszerzony 16s loop: ambient drone + walking
    bassline w A-minor + półambientowa melodia + kick na 1 i 3.
    Wcześniej było 'pikanie w tle' (drone + 4 pingi). Teraz to
    realna industrialna pętla z rytmem i harmonią.

    Skala: A natural minor (A, B, C, D, E, F, G).
    Tempo: 60 BPM (1 sekunda = 1 ćwierćnuta), 16 taktów × 4 = 64
    ćwierćnuty? Nie — 16s / 4 = 4 takty po 4 ćwierćnuty.

    Layout:
      • Bassline: A1 → C2 → G1 → E1 (po 4 sek każdy, walking down).
      • Drum: kick na każdy 1 i 3, lekki hi-hat na 2 i 4.
      • Synth pad: stała tercja A3+C4 jako warstwa.
      • Melodia: 8-nutowy motyw (E4 G4 A4 G4 / E4 C4 D4 E4) na
        co czwarty takt.
    """
    dur = 16.0

    # ── Bass: 4 nuty po 4 sek, square z lekkim detune. ──────────────
    bass_freqs = [55.0, 65.41, 49.0, 41.20]  # A1, C2, G1, E1
    bass: List[float] = []
    for f in bass_freqs:
        x = _square(f, 4.0, duty=0.5)
        # Lekki "punch" envelope: krótki attack, długie sustain.
        env: List[float] = []
        n = len(x)
        attack = int(n * 0.02)
        for i in range(attack):
            env.append(i / attack)
        for i in range(n - attack):
            env.append(1.0 - (i / max(1, n - attack)) * 0.3)
        bass.extend(_scale(_apply_env(x, env), 0.25))

    # ── Pad: stała tercja A3 (220) + C4 (261.63) — minorowa kotwica. ──
    pad_a = _scale(_sine(220.0, dur), 0.08)
    pad_c = _scale(_sine(261.63, dur), 0.06)

    # ── Drum: kick (low thump) co 2 sek, hat (noise) na off-beats. ──
    drum = _silence(dur)
    kick_times = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0]
    for t in kick_times:
        idx = int(t * SR)
        # Kick: 100Hz sine z bardzo szybkim pitch drop + envelope.
        kdur = 0.18
        kick = _glide(110.0, 60.0, kdur, shape="sine")
        kick = _apply_env(kick, _env_ad(len(kick), 0.01, 0.99))
        for i, s in enumerate(_scale(kick, 0.55)):
            if idx + i < len(drum):
                drum[idx + i] += s
    hat_times = [1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0]
    for t in hat_times:
        idx = int(t * SR)
        hat = _noise(0.04, seed=int(t * 100))
        hat = _lowpass(hat, 6000.0)
        hat = _apply_env(hat, _env_ad(len(hat), 0.01, 0.99))
        for i, s in enumerate(_scale(hat, 0.10)):
            if idx + i < len(drum):
                drum[idx + i] += s

    # ── Melodia: 8 nut na 4. takt (sekunda 12-16). ───────────────────
    mel = _silence(dur)
    # E4=329.63, G4=392, A4=440, C4=261.63, D4=293.66.
    mel_notes = [
        (12.0, 329.63, 0.45),  # E4
        (12.5, 392.00, 0.45),  # G4
        (13.0, 440.00, 0.90),  # A4 (sustain)
        (14.0, 392.00, 0.45),  # G4
        (14.5, 329.63, 0.45),  # E4
        (15.0, 261.63, 0.30),  # C4
        (15.4, 293.66, 0.30),  # D4
        (15.7, 329.63, 0.30),  # E4
    ]
    for t, f, d in mel_notes:
        idx = int(t * SR)
        tone = _square(f, d, duty=0.3)
        tone = _apply_env(tone, _env_ad(len(tone), 0.05, 0.95))
        for i, s in enumerate(_scale(tone, 0.16)):
            if idx + i < len(mel):
                mel[idx + i] += s

    mix = _mix(bass, pad_a, pad_c, drum, mel)
    return _seamless_loop(_scale(mix, 0.55))


def music_victory() -> List[float]:
    """6s major fanfare. C5 → E5 → G5 → C6 with rhythmic hits."""
    notes = [
        (523.25, 0.30),   # C5
        (659.25, 0.30),   # E5
        (783.99, 0.30),   # G5
        (1046.50, 0.90),  # C6 (held)
    ]
    seq = []
    for f, d in notes:
        x = _square(f, d, duty=0.4)
        x = _apply_env(x, _env_ad(len(x), 0.04, 0.96))
        seq.extend(_scale(x, 0.4))
    # Tail of warm sustain.
    tail = _scale(_sine(523.25, 4.0), 0.18)
    tail = _apply_env(tail, _env_ad(len(tail), 0.05, 0.95))
    out = _concat(seq, tail)
    return _seamless_loop(out)


def music_defeat() -> List[float]:
    """6s minor descending lament. A4 → G4 → F4 → E4, slow."""
    notes = [
        (440.0, 0.6),  # A4
        (392.0, 0.6),  # G4
        (349.23, 0.6), # F4
        (329.63, 1.8), # E4 (held)
    ]
    seq = []
    for f, d in notes:
        x = _triangle(f, d)
        x = _apply_env(x, _env_ad(len(x), 0.05, 0.95))
        seq.extend(_scale(x, 0.42))
    # Low rumble underneath for gravitas.
    rumble = _scale(_sine(55, 3.6), 0.18)
    rumble = _apply_env(rumble, _env_ad(len(rumble), 0.05, 0.95))
    out = _mix(seq, rumble)
    # Pad to 6s with silence.
    while len(out) < int(6.0 * SR):
        out.append(0.0)
    return _seamless_loop(out)


# ── Driver ───────────────────────────────────────────────────────────────

SFX_REGISTRY = {
    "sponsor_chime":   sfx_sponsor_chime,
    "floor_descent":   sfx_floor_descent,
    "player_hit":      sfx_player_hit,
    "player_crit_hit": sfx_player_crit_hit,
    "hit_landed":      sfx_hit_landed,
    "hit_crit":        sfx_hit_crit,
    "enemy_death":     sfx_enemy_death,
    "player_death":    sfx_player_death,
    "attack_miss":     sfx_attack_miss,
    "attack_fumble":   sfx_attack_fumble,
    "limb_broken":     sfx_limb_broken,
}

MUSIC_REGISTRY = {
    "menu":    music_menu,
    "explore": music_explore,
    "victory": music_victory,
    "defeat":  music_defeat,
}


def synthesize_all(*, root: str = ".") -> dict:
    """Write every SFX + music WAV. Returns a dict of relative paths
    → byte size, for the test/manual reporting."""
    out = {}
    for key, fn in SFX_REGISTRY.items():
        rel = os.path.join(SFX_DIR, f"{key}.wav")
        path = os.path.join(root, rel)
        _write_wav(path, fn())
        out[rel] = os.path.getsize(path)
    for key, fn in MUSIC_REGISTRY.items():
        rel = os.path.join(MUSIC_DIR, f"{key}.wav")
        path = os.path.join(root, rel)
        _write_wav(path, fn())
        out[rel] = os.path.getsize(path)
    return out


def main() -> None:
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    sizes = synthesize_all(root=root)
    total = sum(sizes.values())
    for rel, sz in sorted(sizes.items()):
        print(f"  {sz:>8} B   {rel}")
    print(f"\n  total: {total / 1024:.1f} KB across {len(sizes)} files")


if __name__ == "__main__":
    main()
