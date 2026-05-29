"""P29.71 — Workstream C/2: pipeline ilustracji (tło pokoju + portret wroga).

Decyzja user 2026-05-29: malarski styl jak w referencji = gotowe rastry
(PNG) generowane modelem obrazów, wczytywane przez grę. Ja buduję SLOTY +
loader + fallback; Ty generujesz pliki wg assets/images/ART_MANIFEST.md i
wrzucasz do assets/images/.

Łańcuch rozwiązywania (pierwszy istniejący wygrywa), inaczej fallback
proceduralny (gradient/sylwetka) — gra nigdy nie pęka bez grafiki:
  pokój:  bg_<biome> → bg_room_<typ> → bg_default → gradient per biom
  wróg:   wrog_<klucz> → wrog_<archetyp> → sylwetka proceduralna
"""
from __future__ import annotations

try:
    import pygame
    _HAS_PYGAME = True
except ImportError:  # pragma: no cover
    _HAS_PYGAME = False

from . import assets as _assets


# ── Tinty fallbacku tła per biom (gdy brak PNG) ─────────────────────
_BIOME_TINT = {
    "intake_industrial": ((18, 22, 30), (40, 48, 64)),
    "zoo_korporacyjne":  ((20, 28, 20), (44, 64, 44)),
    "muzeum_spektakli":  ((28, 22, 32), (60, 48, 70)),
    "bar_skurczybyk":    ((30, 24, 18), (70, 52, 36)),
    "grzybica_bloom":    ((22, 28, 26), (48, 70, 60)),
    "okopy_frontowe":    ((24, 22, 18), (52, 48, 38)),
    "fabryka_pary":      ((26, 22, 20), (62, 50, 42)),
    "stacja_orbital":    ((16, 20, 30), (36, 46, 70)),
    "kuznia_polorkow":   ((28, 18, 16), (70, 40, 32)),
    "biblioteka_miejska":((22, 20, 28), (50, 44, 64)),
}
_DEFAULT_TINT = ((16, 18, 24), (36, 40, 52))


def _biome_of(room) -> str:
    return (getattr(room, "biome", None)
            or getattr(room, "biome_key", None) or "") or ""


def _room_type(room) -> str:
    return (getattr(room, "actual_type", None)
            or getattr(room, "room_type", None) or "") or ""


def room_bg_keys(room):
    """Łańcuch kluczy tła pokoju (od najbardziej szczegółowego)."""
    keys = []
    b = _biome_of(room)
    t = _room_type(room)
    if b:
        keys.append(f"bg_{b}")
    if t:
        keys.append(f"bg_room_{t}")
    keys.append("bg_default")
    return keys


def _vertical_gradient(w, h, top, bot):
    surf = pygame.Surface((w, h))
    for i in range(h):
        f = i / max(1, h - 1)
        r = int(top[0] + (bot[0] - top[0]) * f)
        g = int(top[1] + (bot[1] - top[1]) * f)
        b = int(top[2] + (bot[2] - top[2]) * f)
        pygame.draw.line(surf, (r, g, b), (0, i), (w, i))
    return surf


def draw_room_background(surf, room, rect) -> bool:
    """Maluje tło pokoju w `rect`. PNG jeśli jest, inaczej gradient per
    biom. Przyciemnia, żeby tekst na wierzchu był czytelny. Zwraca True
    gdy użyto prawdziwego obrazu (a nie fallbacku)."""
    if not _HAS_PYGAME or surf is None or room is None:
        return False
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return False
    img = None
    used_real = False
    for key in room_bg_keys(room):
        img = _assets.load_image(key, w, h)
        if img is not None:
            used_real = True
            break
    if img is None:
        top, bot = _BIOME_TINT.get(_biome_of(room), _DEFAULT_TINT)
        img = _vertical_gradient(w, h, top, bot)
    surf.blit(img, (x, y))
    # Przyciemnienie dla czytelności treści.
    veil = pygame.Surface((w, h), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 150 if used_real else 90))
    surf.blit(veil, (x, y))
    return used_real


# ── Archetyp wizualny wroga (z tagów) ───────────────────────────────
_ARCHETYPE_TAGS = (
    ("robot",      {"robot", "drone", "machine", "construct", "ai"}),
    ("undead",     {"undead", "zombie", "ghost", "skeleton"}),
    ("aberration", {"aberration", "weird", "anomaly", "mutant", "eldritch"}),
    ("beast",      {"beast", "animal", "vermin", "pack"}),
    ("blob",       {"blob", "ooze", "slime", "amorphous"}),
    ("humanoid",   {"humanoid", "human", "corporate", "cult", "guard"}),
)


def enemy_archetype(entity) -> str:
    tags = set(getattr(entity, "tags", None) or [])
    for arch, keys in _ARCHETYPE_TAGS:
        if tags & keys:
            return arch
    return "humanoid"


def enemy_art_keys(entity):
    """Łańcuch kluczy portretu wroga."""
    out = []
    k = getattr(entity, "key", None)
    if k:
        out.append(f"wrog_{k}")
    out.append(f"wrog_{enemy_archetype(entity)}")
    return out


_ARCH_COLOR = {
    "robot":      (120, 140, 170),
    "undead":     (110, 120, 100),
    "aberration": (150, 90, 160),
    "beast":      (150, 120, 90),
    "blob":       (90, 160, 130),
    "humanoid":   (170, 150, 130),
}


def draw_enemy_portrait(surf, entity, rect) -> bool:
    """Portret wroga w `rect`: PNG jeśli jest, inaczej prosta sylwetka
    proceduralna wg archetypu (placeholder). Zwraca True gdy PNG."""
    if not _HAS_PYGAME or surf is None or entity is None:
        return False
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return False
    for key in enemy_art_keys(entity):
        img = _assets.load_image(key, w, h)
        if img is not None:
            surf.blit(img, (x, y))
            return True
    # Fallback proceduralny — sylwetka archetypu (placeholder do czasu PNG).
    arch = enemy_archetype(entity)
    col = _ARCH_COLOR.get(arch, (150, 150, 150))
    pygame.draw.rect(surf, (20, 22, 28), (x, y, w, h))
    pygame.draw.rect(surf, (70, 84, 104), (x, y, w, h), 1)
    cx = x + w // 2
    if arch == "robot":
        pygame.draw.rect(surf, col, (cx - w // 5, y + h // 5,
                                     2 * w // 5, 3 * h // 5))
        pygame.draw.circle(surf, (220, 90, 80), (cx, y + h // 3), max(3, w // 12))
    elif arch == "beast":
        pygame.draw.ellipse(surf, col, (x + w // 6, y + h // 3,
                                        2 * w // 3, h // 2))
        pygame.draw.circle(surf, col, (x + w // 4, y + h // 3), max(4, w // 8))
    elif arch == "blob":
        pygame.draw.ellipse(surf, col, (x + w // 6, y + h // 3,
                                        2 * w // 3, h // 2))
    elif arch == "aberration":
        pygame.draw.polygon(surf, col, [
            (cx, y + h // 6), (x + w // 6, y + 5 * h // 6),
            (x + 5 * w // 6, y + 5 * h // 6)])
    else:  # humanoid / undead
        pygame.draw.circle(surf, col, (cx, y + h // 4), max(5, w // 8))
        pygame.draw.rect(surf, col, (cx - w // 6, y + h // 3,
                                     w // 3, h // 2))
    return False
