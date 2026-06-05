"""P29.57b — Skrzynki: handler otwierania + helper'y do tworzenia.

Skrzynki to entity z tagiem `"box"` + `"unopened"`. Wszystkie drop
pipeline'y (sponsor gifts, achievement boon, drop pody, boss kills,
mob drops, audience milestones) produkują skrzynki zamiast gotowych
itemów. Gracz otwiera **manualnie** w tabie „Skrzynki" UI.

DCC canon: "Wszystkie bossy zostawiają za sobą trwały łup" — drop
zachodzi automatycznie, ale **owinięty w skrzynkę** którą gracz musi
otworzyć. Vampire Survivors flavor: każda skrzynka = moment reveal.

State na skrzynce:
    box_source: "boss" | "sponsor" | "rezyser" | "widownia" |
                "drop_pod" | "mob"
    box_source_name: free-form display (np. "NovaChem-Biotech",
                     "Pyskaty Bandzior", "Reżyser", "Widownia")
    box_contents: list[{"item_key": str, "qty": int}]
    box_tier_label: PL display name (np. "Skrzynka Brązowa")
    rarity: standardowy rarity string

Reveal flavor zarządzany centralnie w `_REVEAL_BY_SOURCE` — 3 linie
per source w Dinniman tonie.
"""
from __future__ import annotations
from typing import Dict, List, Optional


# ── Reveal flavor per source (3 linie każdy) ────────────────────────


_REVEAL_BY_SOURCE = {
    'boss': [
        'Pęka. Naklejka „{tier} — odbierane przez zwycięzcę” '
        'schodzi zbyt łatwo.',
        '{contents}',
        'Konferansjer: „Brąz za pierwszego trupa z imieniem. '
        'Pamiętajcie: srebro to wyższa półka, a złoto już '
        'na sufitach.”',
    ],
    'sponsor': [
        'Pakiet {source_name}. Lakowana pieczęć. Pęka z sykiem.',
        '{contents}',
        '{source_name}: „{tagline}”',
    ],
    'rezyser': [
        'Dron-kurier reżysera zrzuca pakiet z białym hologramem '
        '„PREMIA REŻYSERA”.',
        '{contents}',
        'Reżyser mruga ci kamerą i znika.',
    ],
    'widownia': [
        'Z górnej rampy ktoś rzuca pakiet. Krzyczy: „TO ZA TE '
        'NAPIWKI!” Rzucało dwóch widzów naraz — uderzyły się '
        'w locie.',
        '{contents}',
        'Pączek się obtłucze.',
    ],
    'drop_pod': [
        'Z sufitu pada drop-pod. Czerwone światło. Klapki '
        'się otwierają.',
        '{contents}',
        '„Dziękujemy za bycie naszym partnerem reklamowym.”',
    ],
    'mob': [
        'Spod trupa wypada zafoliowany prezent. Folia za '
        'krucha, za błyszcząca.',
        '{contents}',
        'Loch redystrybuuje. Statystycznie.',
    ],
    # P29.76 — skrzynka za awans (DCC: każdy poziom = loot box).
    'level_up': [
        'System brzęczy triumfalnie: „AWANS POTWIERDZONY". Skrzynka '
        'materializuje się w smudze światła i pęka.',
        '{contents}',
        'Konferansjer: „Rośniesz w siłę, zawodniku. Widownia to uwielbia."',
    ],
}


_TIER_LABEL_PL = {
    "common":    "Skrzynka Brązowa",
    "uncommon":  "Skrzynka Srebrna",
    "rare":      "Skrzynka Złota",
    "epic":      "Skrzynka Platynowa",
    "legendary": "Skrzynka Diamentowa",
}


def tier_label_for_rarity(rarity: str) -> str:
    return _TIER_LABEL_PL.get(rarity, "Skrzynka Brązowa")


# ── Box creation ──────────────────────────────────────────────────────


def make_box(world, *, source: str, source_name: str = "",
             contents: Optional[List[Dict]] = None,
             rarity: str = "common",
             tier_label: Optional[str] = None,
             sponsor_tagline: str = ""):
    """Tworzy skrzynkę entity i wstawia ją do EQ gracza.

    Args:
      source: jeden z 6 źródeł — boss / sponsor / rezyser / widownia /
              drop_pod / mob
      source_name: free-form display (sponsor name, boss name, etc.)
      contents: list[{"item_key": str, "qty": int}] do reveal'u
      rarity: common/uncommon/rare/epic/legendary
      tier_label: opcjonalny override dla `box_tier_label`. Bez tego
                  — wywodzi z rarity.
      sponsor_tagline: tylko dla source="sponsor" — używane w 3. linii
                      reveal'u.

    Returns: stworzony Entity (`tag=["box","unopened",...]`).
    """
    from ..entity import Entity, T_ITEM
    if contents is None:
        contents = []
    label = tier_label or tier_label_for_rarity(rarity)

    name_parts = [label]
    if source_name:
        name_parts.append(f'od „{source_name}”')
    display_name = " ".join(name_parts)

    state = {
        "box_source": source,
        "box_source_name": source_name,
        "box_contents": list(contents),
        "box_tier_label": label,
        "rarity": rarity,
        "sponsor_tagline": sponsor_tagline,
    }

    ent = Entity(
        key=f"box_{source}_{rarity}",
        entity_type=T_ITEM,
        name_key="",
        fallback_name=display_name,
        desc_key="",
        fallback_desc=(f'Skrzynka w typie „{source_name or source}”. '
                       f'Otwórz w tabie Skrzynki.'),
        location_id="inventory:player",
        portable=True,
        tags=["box", "unopened", f"box_source:{source}"],
        affordances=["inspect", "open_box"],
        state=state,
    )
    world.register(ent)
    ch = world.character
    if ch.inventory_ids is None:
        ch.inventory_ids = []
    ch.inventory_ids.append(ent.entity_id)
    return ent


# ── Handler: otwórz skrzynkę ─────────────────────────────────────────


def attempt_open_box(game, intent) -> None:
    """Player intent `open_box`, targets=[box name]. Spawn contents,
    consume box, emit 3-line Dinniman reveal."""
    from ..affordances import fold as _fold
    from ...config import LOG_NORMAL, LOG_SUCCESS, LOG_WARN
    from ...content.items import make_item

    ch = game.world.character
    if ch is None:
        return
    if not getattr(intent, "targets", None):
        game.log("Co otworzyć? Składnia: otwórz <nazwa skrzynki>.",
                 LOG_WARN)
        return
    needle = _fold(intent.targets[0]).strip()

    # Resolve box by name match w inventory
    target_box = None
    for eid in list(ch.inventory_ids or []):
        ent = game.world.entities.get(eid)
        if ent is None:
            continue
        tags = ent.tags or []
        if "box" not in tags or "unopened" not in tags:
            continue
        name_f = _fold(ent.display_name())
        if needle in name_f or _fold(ent.key) == needle:
            target_box = ent
            break

    if target_box is None:
        game.log(f'Nie masz skrzynki „{intent.targets[0]}” '
                 f'w plecaku.', LOG_WARN)
        return

    state = target_box.state or {}
    source = state.get("box_source", "mob")
    source_name = state.get("box_source_name", "")
    contents_raw = state.get("box_contents") or []
    tagline = state.get("sponsor_tagline", "")

    # Spawn each content as fresh item w EQ
    spawned_names = []
    for entry in contents_raw:
        if not isinstance(entry, dict):
            continue
        item_key = entry.get("item_key", "")
        qty = int(entry.get("qty", 1))
        if not item_key:
            continue
        # Special: kredyty / credits → bezpośrednio do ch.credits
        if item_key == "credits":
            ch.credits = int(getattr(ch, "credits", 0) or 0) + qty
            spawned_names.append(f"+{qty} kredytów")
            continue
        # Special: materials
        if item_key.startswith("mat:"):
            mat_key = item_key.split(":", 1)[1]
            try:
                from ...content.materials import add_material
                add_material(ch, mat_key, qty)
                spawned_names.append(f'„{mat_key}” ×{qty}')
            except Exception:
                pass
            continue
        # Normal item
        last_made_item = None
        for _ in range(qty):
            try:
                it = make_item(item_key, location_id="inventory:player")
                game.world.register(it)
                ch.inventory_ids.append(it.entity_id)
                last_made_item = it
            except Exception:
                continue
        # P29.59 — display name z faktycznie utworzonego item entity
        # (które konsultuje item_templates fallback_name), nie surowy
        # key. Bez tego box reveal pokazywał ang. „snack bar" / „dead
        # phone" zamiast „baton energetyczny" / „martwy telefon".
        if last_made_item is not None and last_made_item.fallback_name:
            nice = last_made_item.fallback_name
        else:
            nice = item_key.replace("_", " ")
        if qty > 1:
            spawned_names.append(f'„{nice}” ×{qty}')
        else:
            spawned_names.append(f'„{nice}”')

    contents_line = "    → " + ", ".join(spawned_names) \
                    if spawned_names else "    → (pusto)"

    # Remove box from inventory
    try:
        ch.inventory_ids.remove(target_box.entity_id)
    except ValueError:
        pass
    # Mark box as opened (for save/load safety — entity already removed
    # but defensive flag).
    target_box.tags = [t for t in (target_box.tags or [])
                       if t != "unopened"]
    if "opened" not in target_box.tags:
        target_box.tags.append("opened")

    # Emit 3-line Dinniman reveal
    template = _REVEAL_BY_SOURCE.get(source, _REVEAL_BY_SOURCE["mob"])
    tier = state.get("box_tier_label", "Skrzynka")
    for line in template:
        formatted = line.format(
            tier=tier,
            source_name=source_name or "Sponsor",
            tagline=tagline or "Brak komentarza.",
            contents=contents_line,
        )
        game.log(formatted, LOG_SUCCESS)

    # P29.76 / Feature#2 — wizualny reveal w stylu VS (hybryda: modal +
    # lekka animacja). Log wyżej zostaje (dostępność + testy); overlay to
    # „moment otwarcia". Generyczny dla każdego źródła skrzynki.
    try:
        game._box_reveal = {
            "intro": template[0].format(
                tier=tier, source_name=source_name or "",
                tagline=tagline or "", contents=""),
            "title": tier,
            "rarity": state.get("rarity", "common"),
            "content_lines": list(spawned_names),
            "catchphrase": template[-1].format(
                tier=tier, source_name=source_name or "",
                tagline=tagline or "", contents=""),
            "elapsed": 0.0, "shown": 0, "done": False,
        }
        # Mini-fanfara: reuse istniejącego dzwonka nagrody (audyt
        # test_p29_13 wymaga assetu .wav dla każdego klucza play_sfx).
        from ...ui import audio as _audio
        _audio.play_sfx("sponsor_chime")
    except Exception:
        pass
