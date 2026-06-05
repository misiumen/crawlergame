"""Dungeon Kraulem save/load.

P29.9 — three numbered save slots: `dungeon_kraulem_save_{0,1,2}.json`.
The "active slot" is a module-level pointer set by the UI (title-screen
slot picker) before any save/load call. Older callers that just say
`save_load.save(world)` keep working because they implicitly use the
active slot (default 0).

Backward compatibility:
  * If a legacy `dungeon_kraulem_save.json` (or the original
    `revamp_save.json`) exists with no slot files, the first `load()`
    call migrates it into slot 0 and removes the legacy file.

The slot picker reads via `peek_slot(n) -> dict | None` so it can show
a card per slot without rehydrating the full WorldState.
"""
import json
import os

from .world import WorldState

SAVE_SLOT_COUNT = 3
SAVE_VERSION = 1

# Filenames (legacy + slotted).
LEGACY_SAVE_FILE = "revamp_save.json"
LEGACY_SAVE_FILE_NEW = "dungeon_kraulem_save.json"  # P29.0 single-file


def _slot_path(n: int) -> str:
    n = int(n) % SAVE_SLOT_COUNT
    return f"dungeon_kraulem_save_{n}.json"


# Module-level "active slot" pointer. UI sets this when the player
# clicks a slot card. All non-slot-aware API points read this.
_ACTIVE_SLOT = 0


def set_active_slot(n: int) -> None:
    global _ACTIVE_SLOT
    _ACTIVE_SLOT = max(0, min(int(n), SAVE_SLOT_COUNT - 1))


def active_slot() -> int:
    return _ACTIVE_SLOT


# ── Legacy migration ────────────────────────────────────────────────────────

def _maybe_migrate_legacy() -> None:
    """If no slot files exist yet but a legacy single-file save does,
    copy it into slot 0 and unlink the legacy file. Safe to call
    repeatedly — once any slot file exists, the function is a no-op.
    """
    any_slot = any(os.path.exists(_slot_path(i)) for i in range(SAVE_SLOT_COUNT))
    if any_slot:
        return
    src = None
    for p in (LEGACY_SAVE_FILE_NEW, LEGACY_SAVE_FILE):
        if os.path.exists(p):
            src = p
            break
    if src is None:
        return
    try:
        with open(src, "r", encoding="utf-8") as f:
            data = f.read()
        with open(_slot_path(0), "w", encoding="utf-8") as f:
            f.write(data)
        os.remove(src)
    except OSError:
        pass


# ── Slot-aware API ──────────────────────────────────────────────────────────

def save_to_slot(world: WorldState, n: int) -> bool:
    path = _slot_path(n)
    data = world.to_dict()
    data["version"] = SAVE_VERSION
    data["slot"] = int(n)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except (OSError, TypeError):
        return False


def load_from_slot(n: int) -> WorldState | None:
    _maybe_migrate_legacy()
    path = _slot_path(n)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    # P29.21 — accept any version <= current. WorldState.from_dict +
    # Character.from_dict already fill missing fields with safe defaults
    # (P29.8 added run_* counters with explicit `d.get(..., default)`
    # patterns), so soft-accepting older saves is safer than nuking
    # the slot. If we ever ship an incompatible version bump, add a
    # `_migrate_v<N>_to_v<N+1>(data)` chain here.
    save_v = int(data.get("version", 0) or 0)
    if save_v > SAVE_VERSION:
        # A newer save than the engine knows — refuse.
        return None
    try:
        return WorldState.from_dict(data)
    except Exception:
        return None


def exists_slot(n: int) -> bool:
    _maybe_migrate_legacy()
    return os.path.exists(_slot_path(n))


def delete_slot(n: int) -> None:
    p = _slot_path(n)
    if os.path.exists(p):
        try:
            os.remove(p)
        except OSError:
            pass


def peek_slot(n: int) -> dict | None:
    """Return a tiny preview dict for the title-screen slot picker:
    {name, background, class_key, floor, audience, hp, hp_max, dead}.
    Returns None on empty/corrupt slot. Cheap parse — we don't
    rehydrate the WorldState."""
    _maybe_migrate_legacy()
    path = _slot_path(n)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    ch = data.get("character") or {}
    f = data.get("current_floor") or {}
    return {
        "slot": int(n),
        "name": str(ch.get("name", "") or ""),
        "background": str(ch.get("background", "") or ""),
        "class_key": str(ch.get("class_key", "") or ""),
        "floor": int(f.get("floor_number", 1) or 1),
        "audience": int(ch.get("audience_rating", 0) or 0),
        "hp": int(ch.get("hp", 0) or 0),
        "hp_max": int(ch.get("max_hp", 0) or 0),
        "dead": bool(ch.get("hp", 1) <= 0),
        "class_offered": bool(ch.get("class_key")),
        "minutes": int((f.get("current_minute") or 0)),
    }


def list_slots() -> list[dict | None]:
    """Convenience: peek_slot for each slot, returned as a list."""
    return [peek_slot(i) for i in range(SAVE_SLOT_COUNT)]


# ── Back-compat API (uses active slot) ─────────────────────────────────────

def save(world: WorldState) -> bool:
    return save_to_slot(world, _ACTIVE_SLOT)


def load() -> WorldState | None:
    return load_from_slot(_ACTIVE_SLOT)


def exists() -> bool:
    # Any slot existing counts. Used by title-screen "Continue" gating.
    _maybe_migrate_legacy()
    return any(exists_slot(i) for i in range(SAVE_SLOT_COUNT))


def delete() -> None:
    """Delete the ACTIVE slot only. The post-death wipe in
    Game._check_player_dead expects single-slot semantics — it should
    clear the slot that just died, not the others. The previous global
    delete is gone; tests that want a clean global state should iterate
    every slot."""
    delete_slot(_ACTIVE_SLOT)


def delete_all() -> None:
    """Wipe every slot. Test helper / reset path."""
    for i in range(SAVE_SLOT_COUNT):
        delete_slot(i)
    # Belt-and-suspenders: legacy files too.
    for p in (LEGACY_SAVE_FILE_NEW, LEGACY_SAVE_FILE):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


