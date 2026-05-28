"""P29.57d — Boss Box drop pipeline + audience bonus per rank.

Hook do kill path w game.py. Wywołuje `drop_boss_box(world, dead_boss,
killer=ch)` zaraz po `transform_to_corpse`. Jeśli boss padł z ręki
gracza (DCC canon: tylko zabójca dostaje skrzynkę) i ma tag
`boss_rank:<rank>`, produkujemy Skrzynkę odpowiedniej rangi w EQ.

Boss died not-by-player (faction crossfire / trap / hazard) — trup
zostaje, **brak skrzynki** (per design Etap A unlock przez corpses,
tu konsekwentnie).

Content per Boss Box (baseline `# TODO TUNE`):
  Brązowa     → 1× common  + 15 kred + 1 mat
  Srebrna     → 1× common  + 1× uncommon + 30 kred + 2 mat
  Złota       → 2× uncommon + 50 kred + 3 mat
  Platynowa   → 1× rare    + 1× uncommon + 100 kred + 4 mat
  Diamentowa  → 2× rare    + 1× epic + 200 kred + 5 mat
  Niebiańska  → 1× epic    + 1× legendary + 400 kred + 7 mat

Materials losowane z generic puli (`generic_scrap`, `parts`, `wire`,
`solvent`, `ammo`) — biome materials są tylko dla recept eksperymentu.
"""
from __future__ import annotations
import random
from typing import Dict, List, Optional, Tuple

from .. import boss_ranks as _br
from .. import rarity as _rar


# ── Box content recipes per rank ────────────────────────────────────


# (rarity, n_items)+ → spec krotki. Plus credits + materials_count.
# Łatwe do podstrojenia (kazdy element jest jednym wierszem).
_BOX_RECIPE: Dict[str, Dict] = {
    _br.RANK_LOKALNY: {
        "items": [("common", 1)],
        "credits": 15,
        "materials": 1,
    },
    _br.RANK_DZIELNICOWY: {
        "items": [("common", 1), ("uncommon", 1)],
        "credits": 30,
        "materials": 2,
    },
    _br.RANK_MIEJSKI: {
        "items": [("uncommon", 2)],
        "credits": 50,
        "materials": 3,
    },
    _br.RANK_REGIONALNY: {
        "items": [("uncommon", 1), ("rare", 1)],
        "credits": 100,
        "materials": 4,
    },
    _br.RANK_KRAJOWY: {
        "items": [("rare", 2), ("epic", 1)],
        "credits": 200,
        "materials": 5,
    },
    _br.RANK_BOSS_PIETRA: {
        "items": [("epic", 1), ("legendary", 1)],
        "credits": 400,
        "materials": 7,
    },
}


# Generic materials drop pool — nie-biome, bo te są dla recept
# eksperymentu (P29.56). Skrzynki dropią uniwersalny scrap.
_GENERIC_MAT_POOL = (
    "generic_scrap", "parts", "wire", "solvent", "ammo", "cloth",
)


def _pick_item_of_rarity(rng: random.Random, target_rarity: str,
                         floor_num: int) -> str:
    """Wybiera klucz itemu z puli o danym rarity. Cascade: jeśli pula
    target_rarity pusta, schodzi niżej (np. legendary → epic → rare).
    Floor jest brany pod uwagę przez fallback do
    `pick_item_key_for_floor` gdy cascade nie zadziała."""
    pool = _rar.item_keys_by_rarity(target_rarity)
    if pool:
        return rng.choice(pool)
    # Cascade down — niżej rarity = większa pula
    idx = _rar._RARITY_ORDER.get(target_rarity, 0)
    while idx > 0 and not pool:
        idx -= 1
        pool = _rar.item_keys_by_rarity(_rar.ALL_RARITIES[idx])
    if pool:
        return rng.choice(pool)
    # Last resort: floor-weighted pick
    return _rar.pick_item_key_for_floor(rng, floor_num)


def roll_boss_box_contents(rng: random.Random, rank: str,
                           floor_num: int) -> List[Dict]:
    """Zwraca listę {item_key, qty} dla skrzynki danej rangi.

    Format kompatybilny z `make_box(contents=...)`:
      * normalne item — {"item_key": "..."}
      * kredyty — {"item_key": "credits", "qty": N}
      * materiał — {"item_key": "mat:<key>", "qty": N}
    """
    recipe = _BOX_RECIPE.get(rank, _BOX_RECIPE[_br.RANK_LOKALNY])
    contents: List[Dict] = []

    # Items per rarity tier
    for tier_rarity, count in recipe["items"]:
        for _ in range(int(count)):
            key = _pick_item_of_rarity(rng, tier_rarity, floor_num)
            if key:
                contents.append({"item_key": key, "qty": 1})

    # Credits
    if recipe["credits"] > 0:
        contents.append({"item_key": "credits",
                         "qty": int(recipe["credits"])})

    # Materials — wybieramy n materiałów z generic puli, łącząc
    # duplikaty w jeden entry żeby reveal był czytelny.
    n_mats = int(recipe["materials"])
    if n_mats > 0:
        rolls: Dict[str, int] = {}
        for _ in range(n_mats):
            mat = rng.choice(_GENERIC_MAT_POOL)
            rolls[mat] = rolls.get(mat, 0) + 1
        for mat_key, qty in rolls.items():
            contents.append({"item_key": f"mat:{mat_key}", "qty": qty})

    return contents


# ── Drop on kill ────────────────────────────────────────────────────


def drop_boss_box(world, dead_boss, *, killer=None,
                  rng: Optional[random.Random] = None
                  ) -> Optional[Tuple[object, str]]:
    """Drop skrzynki bossa per rank.

    Args:
      world: WorldState
      dead_boss: Entity, świeżo zabity (lub jego corpse — i tak czytamy
                  tagi pre-transform przez snapshot w game.py)
      killer: postać która zadała zabójczy cios. Jeśli != world.character
              (np. faction crossfire, hazard) — None i SKIP per DCC canon.
      rng: opcjonalny generator (test deterministyczność). Bez = global.

    Returns:
      (box_entity, rank) gdy skrzynka spawnowana, None gdy skip.
      Drop zachodzi tylko gdy:
        * boss ma tag `boss_rank:*`
        * killer == world.character (DCC: trup zostaje, ale skrzynkę
          dostaje zabójca)
    """
    rng = rng or random.Random()

    # DCC canon: skrzynka tylko dla player kill'a
    if killer is None or killer is not getattr(world, "character", None):
        return None

    rank = _br.rank_from_entity(dead_boss)
    if not rank:
        return None

    # Floor number dla item rarity cascade
    floor_num = 1
    try:
        f = getattr(world, "current_floor", None)
        if f is not None:
            floor_num = int(getattr(f, "floor_number", 1) or 1)
    except (AttributeError, ValueError, TypeError):
        pass

    # Box contents
    contents = roll_boss_box_contents(rng, rank, floor_num)
    rarity = _br.box_rarity_for_rank(rank)
    tier_label = _br.box_tier_label_for_rank(rank)
    boss_name = ""
    try:
        boss_name = dead_boss.display_name() or ""
    except (AttributeError, TypeError):
        boss_name = ""

    # Lazy import — boxes.make_box rejestruje skrzynkę w EQ
    from .boxes import make_box
    box = make_box(world,
                   source="boss",
                   source_name=boss_name,
                   contents=contents,
                   rarity=rarity,
                   tier_label=tier_label)

    # Tag-trail dla telemetrii / późniejszych systemów (np.
    # achievement „diamentowy_lowca" — TODO).
    if box.tags is None:
        box.tags = []
    box.tags.append(_br.rank_tag(rank))

    return box, rank


def audience_bonus_for_dead_boss(dead_boss) -> int:
    """Bonus widowni po zabiciu bossa danej rangi. Wywołane z game.py
    równolegle z `drop_boss_box`. 0 jeśli entity nie jest bossem."""
    rank = _br.rank_from_entity(dead_boss)
    if not rank:
        return 0
    return _br.audience_bonus_for_kill(rank)
