"""Prompt 29.13 — Audio asset shipping smoke suite.

Audit finding: assets/audio/ was empty — the SFX hooks wired in P27
were silently no-op because no files ever loaded. P29.13 generates
all 15 WAVs procedurally (stdlib synth) and ships them as real
assets. This test ensures every SFX/music KEY referenced in the
game code has a matching .wav on disk, and that pygame can actually
load each one.

Covers:
  * Every play_sfx("KEY") call in engine/ has a SFX file.
  * Every music key Game._music_key_for_state may return has a file.
  * Each WAV loads through pygame.mixer.Sound without error.
  * Each WAV has a sensible (>0, <2s for SFX) duration.
  * Re-running synthesize_all() is idempotent.
"""
from __future__ import annotations
import os, re, glob, wave
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame
pygame.init()
try:
    pygame.mixer.init()
    _MIXER_OK = True
except pygame.error:
    _MIXER_OK = False


PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(PKG_ROOT)
SFX_DIR = os.path.join(REPO_ROOT, "assets", "audio", "sfx")
MUSIC_DIR = os.path.join(REPO_ROOT, "assets", "audio", "music")


def _collect_sfx_keys_used_in_code() -> set:
    """Scan engine + ui + systems for play_sfx("KEY") literals."""
    keys = set()
    for sub in ("engine", "ui", "systems"):
        root = os.path.join(PKG_ROOT, sub)
        if not os.path.isdir(root):
            continue
        for p in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
            with open(p, encoding="utf-8") as f:
                text = f.read()
            for m in re.finditer(r'play_sfx\("([a-z_]+)"', text):
                keys.add(m.group(1))
    return keys


# ── File inventory matches code ─────────────────────────────────────────

def test_every_play_sfx_key_has_a_wav():
    used = _collect_sfx_keys_used_in_code()
    assert used, "scanner found zero play_sfx() calls — broken regex?"
    missing = [k for k in used if not os.path.exists(
        os.path.join(SFX_DIR, f"{k}.wav"))]
    assert not missing, \
        f"play_sfx keys without assets: {sorted(missing)}"
    print(f"  {len(used)} play_sfx keys all have .wav files: OK")


def test_music_keys_present():
    """Game._music_key_for_state can return menu/explore/victory/
    defeat. Each must exist as a .wav."""
    expected = {"menu", "explore", "victory", "defeat"}
    have = {os.path.splitext(f)[0]
            for f in os.listdir(MUSIC_DIR)
            if f.endswith(".wav")}
    missing = expected - have
    assert not missing, f"missing music files: {missing}"
    print(f"  4/4 music tracks present: OK")


# ── Each WAV is structurally valid (stdlib check, no pygame needed) ─────

def test_every_wav_is_valid():
    bad = []
    for d in (SFX_DIR, MUSIC_DIR):
        for f in sorted(os.listdir(d)):
            if not f.endswith(".wav"):
                continue
            p = os.path.join(d, f)
            try:
                with wave.open(p, "rb") as w:
                    nf = w.getnframes()
                    sr = w.getframerate()
                    ch = w.getnchannels()
                    sw = w.getsampwidth()
                    assert nf > 0
                    assert sr in (11025, 22050, 44100)
                    assert ch == 1, f"{f}: expected mono, got {ch} channels"
                    assert sw == 2
            except Exception as exc:
                bad.append((f, str(exc)))
    assert not bad, f"invalid WAVs: {bad}"
    print("  every WAV passes stdlib wave.open structural check: OK")


# ── Pygame can actually load each file ──────────────────────────────────

def test_pygame_loads_every_sfx():
    if not _MIXER_OK:
        print("  (mixer init unavailable in this env — skipping)")
        return
    loaded = 0
    for f in sorted(os.listdir(SFX_DIR)):
        if not f.endswith(".wav"):
            continue
        path = os.path.join(SFX_DIR, f)
        snd = pygame.mixer.Sound(path)
        dur = snd.get_length()
        assert 0.0 < dur < 2.0, \
            f"{f} duration suspicious: {dur:.3f}s"
        loaded += 1
    assert loaded >= 11, f"expected ≥11 SFX, got {loaded}"
    print(f"  pygame loaded {loaded} SFX, all 0<dur<2s: OK")


def test_pygame_loads_every_music():
    if not _MIXER_OK:
        print("  (mixer init unavailable — skipping)")
        return
    loaded = 0
    for f in sorted(os.listdir(MUSIC_DIR)):
        if not f.endswith(".wav"):
            continue
        path = os.path.join(MUSIC_DIR, f)
        # mixer.music.load doesn't return; failure raises.
        pygame.mixer.music.load(path)
        loaded += 1
    assert loaded == 4
    print(f"  pygame.mixer.music loaded {loaded} tracks: OK")


# ── Synth is idempotent ─────────────────────────────────────────────────

def test_synthesize_all_idempotent():
    """Running the synthesizer a second time produces byte-identical
    output. Guards against accidental dependencies on uninitialised
    RNGs / floating-point order of operations in the synth. Writes
    to a tmp dir so we don't fight pygame's file lock on Windows."""
    import tempfile, shutil
    from ..tools import synthesize_audio as _syn
    with tempfile.TemporaryDirectory() as tmp:
        sizes_a = _syn.synthesize_all(root=tmp)
        snapshot = {}
        for rel in sizes_a:
            with open(os.path.join(tmp, rel), "rb") as fh:
                snapshot[rel] = fh.read()
        sizes_b = _syn.synthesize_all(root=tmp)
        assert sizes_a == sizes_b
        for rel in sizes_b:
            with open(os.path.join(tmp, rel), "rb") as fh:
                assert fh.read() == snapshot[rel], \
                    f"{rel} changed between synth runs"
    print(f"  synthesize_all idempotent across {len(sizes_a)} files: OK")


# ── Suite ────────────────────────────────────────────────────────────────

def main():
    test_every_play_sfx_key_has_a_wav()
    test_music_keys_present()
    test_every_wav_is_valid()
    test_pygame_loads_every_sfx()
    test_pygame_loads_every_music()
    test_synthesize_all_idempotent()
    print("Prompt 29.13 audio assets smoke: OK")


if __name__ == "__main__":
    main()
