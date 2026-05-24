"""Achievement system (Prompt 06c).

Achievements are lore + audience flavor, not numeric power-ups. They unlock
in response to player actions (salvage, craft, deploy, theft, harvest). Each
unlock is stored on Character.unlocked_achievements (already a list) and
emits a log line through the world.log_msg sink. Old saves without
the field load safely — Character serialization already defaults the list.

Public API:
    catalog()                                  -> dict[key, AchievementDef]
    get(key)                                   -> AchievementDef | None
    unlock(character_or_world, key)            -> bool   (True if newly unlocked)
    is_unlocked(character_or_world, key)       -> bool
    count_unlocked(character_or_world)         -> int
    bump_counter(character, counter_key, n=1)  -> int    (returns new value)
    counter(character, counter_key)            -> int

Counters live on Character.flags under stable keys like "salvage_ops" or
"craft_ops" so achievement gates can fire on N-th invocation. We use flags
because Character already round-trips them through save/load.

A `unlock` call is safe to wrap in `try/except` from callers; this module
itself never raises on bad input — unknown keys are ignored silently and
return False.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class AchievementDef:
    key: str
    name_key: str = ""
    fallback_name_pl: str = ""
    fallback_name_en: str = ""
    description_key: str = ""
    fallback_description_pl: str = ""
    fallback_description_en: str = ""
    category: str = "general"     # salvage, craft, deploy, theft, harvest, etc.
    hidden: bool = False           # if True, list shows "???" until unlocked
    reward: Dict[str, Any] = field(default_factory=dict)


# ── Catalog ──────────────────────────────────────────────────────────────────

_ACHIEVEMENTS: Dict[str, AchievementDef] = {}


def _add(a: AchievementDef):
    _ACHIEVEMENTS[a.key] = a
    return a


# Salvage & looting
_add(AchievementDef(
    key="wszystko_jest_surowcem",
    name_key="ach_wszystko_jest_surowcem_n",
    fallback_name_pl="Wszystko jest surowcem",
    fallback_name_en="Everything Is Material",
    description_key="ach_wszystko_jest_surowcem_d",
    fallback_description_pl="Pierwsza udana rozbiórka. Świat zaczyna wyglądać jak lista materiałów.",
    fallback_description_en="First successful salvage. The world starts to look like a parts list.",
    category="salvage",
))

_add(AchievementDef(
    key="meble_tez_krwawia",
    name_key="ach_meble_tez_krwawia_n",
    fallback_name_pl="Meble też krwawią",
    fallback_name_en="Furniture Bleeds Too",
    description_key="ach_meble_tez_krwawia_d",
    fallback_description_pl="Rozebrałeś coś, co miało służyć do siedzenia. Krzesło wnosi sprzeciw.",
    fallback_description_en="You took apart something meant for sitting. The chair objects.",
    category="salvage",
))

_add(AchievementDef(
    key="recykling_agresywny",
    name_key="ach_recykling_agresywny_n",
    fallback_name_pl="Recykling agresywny",
    fallback_name_en="Aggressive Recycling",
    description_key="ach_recykling_agresywny_d",
    fallback_description_pl="Pięć obiektów rozłożonych na części. Loch staje się tańszy.",
    fallback_description_en="Five objects stripped to parts. The dungeon gets cheaper.",
    category="salvage",
))

_add(AchievementDef(
    key="rozbiorka_zwlok",
    name_key="ach_rozbiorka_zwlok_n",
    fallback_name_pl="Rozbiórka zwłok",
    fallback_name_en="Corpse Disassembly",
    description_key="ach_rozbiorka_zwlok_d",
    fallback_description_pl="Pierwsze ciało potraktowane jak skład części. Widownia patrzy w dwie strony.",
    fallback_description_en="First body treated as a parts bin. The audience looks both ways.",
    category="harvest",
))

_add(AchievementDef(
    key="technicznie_to_loot",
    name_key="ach_technicznie_to_loot_n",
    fallback_name_pl="Technicznie to loot",
    fallback_name_en="Technically Loot",
    description_key="ach_technicznie_to_loot_d",
    fallback_description_pl="Coś, co miało być częścią ściany, jest teraz w plecaku.",
    fallback_description_en="Something that used to be a wall part is now in your bag.",
    category="salvage",
))

# Theft / sponsor / safehouse
_add(AchievementDef(
    key="kradziez_armatury",
    name_key="ach_kradziez_armatury_n",
    fallback_name_pl="Kradzież armatury",
    fallback_name_en="Plumbing Heist",
    description_key="ach_kradziez_armatury_d",
    fallback_description_pl="Rozebrałeś coś, co należało do toalety safehouse. Nikt ci tego nie zapomni.",
    fallback_description_en="You dismantled something that belonged in a safehouse bathroom.",
    category="theft",
))

_add(AchievementDef(
    key="sponsor_nie_pochwala",
    name_key="ach_sponsor_nie_pochwala_n",
    fallback_name_pl="Sponsor nie pochwala",
    fallback_name_en="Sponsor Objects",
    description_key="ach_sponsor_nie_pochwala_d",
    fallback_description_pl="Naruszyłeś własność sponsora. W przyszłym briefingu pojawi się twoje nazwisko.",
    fallback_description_en="You hit sponsor property. Your name shows up in next briefing.",
    category="theft",
    hidden=True,
))

# Crafting
_add(AchievementDef(
    key="rzemieslnik_z_paniki",
    name_key="ach_rzemieslnik_z_paniki_n",
    fallback_name_pl="Rzemieślnik z paniki",
    fallback_name_en="Panic Craftsman",
    description_key="ach_rzemieslnik_z_paniki_d",
    fallback_description_pl="Pierwsze udane wytworzenie czegokolwiek. Palce ci jeszcze pamiętają.",
    fallback_description_en="First successful craft. Your fingers remember.",
    category="craft",
))

_add(AchievementDef(
    key="przepis_jaki_przepis",
    name_key="ach_przepis_jaki_przepis_n",
    fallback_name_pl="Przepis, jaki przepis",
    fallback_name_en="Recipe, Such As It Is",
    description_key="ach_przepis_jaki_przepis_d",
    fallback_description_pl="Pierwsze udane improwizowane wytworzenie z samych tagów. Bez instrukcji.",
    fallback_description_en="First successful tag-based improvisation. No instructions.",
    category="craft",
))

_add(AchievementDef(
    key="inzynieria_odwagi",
    name_key="ach_inzynieria_odwagi_n",
    fallback_name_pl="Inżynieria odwagi",
    fallback_name_en="Engineering Under Duress",
    description_key="ach_inzynieria_odwagi_d",
    fallback_description_pl="Skraftowałeś coś podczas zagrożenia. Ręce drgały. Wyszło.",
    fallback_description_en="You crafted under threat. Hands shaking, result holding.",
    category="craft",
    hidden=True,
))

_add(AchievementDef(
    key="obrzydliwe_ale_dziala",
    name_key="ach_obrzydliwe_ale_dziala_n",
    fallback_name_pl="Obrzydliwe, ale działa",
    fallback_name_en="Disgusting But Functional",
    description_key="ach_obrzydliwe_ale_dziala_d",
    fallback_description_pl="Crafting z materiału organicznego z ciała. Działa. Lepiej o tym nie mówić.",
    fallback_description_en="You crafted with organic material from a corpse. Best not to mention it.",
    category="craft",
    hidden=True,
))

_add(AchievementDef(
    key="zlota_raczka_lochu",
    name_key="ach_zlota_raczka_lochu_n",
    fallback_name_pl="Złota rączka lochu",
    fallback_name_en="Dungeon Handyman",
    description_key="ach_zlota_raczka_lochu_d",
    fallback_description_pl="Dziesięć skraftowanych rzeczy. Loch przewija się przez twoje ręce.",
    fallback_description_en="Ten crafted items. The dungeon flows through your hands.",
    category="craft",
))

# Deploy / traps
_add(AchievementDef(
    key="pulapka_z_niczego",
    name_key="ach_pulapka_z_niczego_n",
    fallback_name_pl="Pułapka z niczego",
    fallback_name_en="Trap From Nothing",
    description_key="ach_pulapka_z_niczego_d",
    fallback_description_pl="Pierwsza rozstawiona pułapka. Loch ma teraz drugi cień.",
    fallback_description_en="First trap placed. The dungeon has a second shadow now.",
    category="deploy",
))

_add(AchievementDef(
    key="samo_sie_rozstawilo",
    name_key="ach_samo_sie_rozstawilo_n",
    fallback_name_pl="Samo się rozstawiło",
    fallback_name_en="Self-Deploying",
    description_key="ach_samo_sie_rozstawilo_d",
    fallback_description_pl="Pułapka odpaliła ci w rękach. To też jest treść.",
    fallback_description_en="The trap went off in your hands. That's also content.",
    category="deploy",
    hidden=True,
))

# Survival / utility
_add(AchievementDef(
    key="ekonomia_przetrwania",
    name_key="ach_ekonomia_przetrwania_n",
    fallback_name_pl="Ekonomia przetrwania",
    fallback_name_en="Survival Economics",
    description_key="ach_ekonomia_przetrwania_d",
    fallback_description_pl="Dwadzieścia akcji odzysku. Każdy złom liczy się raz.",
    fallback_description_en="Twenty salvage ops. Every scrap counts once.",
    category="salvage",
))

_add(AchievementDef(
    key="smiec_wartosciowy",
    name_key="ach_smiec_wartosciowy_n",
    fallback_name_pl="Śmieć wartościowy",
    fallback_name_en="Valuable Trash",
    description_key="ach_smiec_wartosciowy_d",
    fallback_description_pl="Użyłeś najtańszego materiału w poważnej akcji. Loch nie zauważył tej różnicy.",
    fallback_description_en="You used the cheapest material in a serious action. The dungeon couldn't tell.",
    category="craft",
    hidden=True,
))


# ── Public API ───────────────────────────────────────────────────────────────

def catalog() -> Dict[str, AchievementDef]:
    return dict(_ACHIEVEMENTS)


def get(key: str) -> Optional[AchievementDef]:
    return _ACHIEVEMENTS.get(key)


def _resolve_character(target):
    """Accept either a Character or a WorldState-like object with .character."""
    if target is None:
        return None
    if hasattr(target, "unlocked_achievements"):
        return target
    if hasattr(target, "character"):
        return target.character
    return None


def is_unlocked(target, key: str) -> bool:
    ch = _resolve_character(target)
    if ch is None or not key:
        return False
    return key in (ch.unlocked_achievements or [])


def unlock(target, key: str, world=None) -> bool:
    """Try to unlock `key`. Returns True only if newly unlocked.

    Safe to call from anywhere — unknown keys, missing character, or save
    objects with no achievement list are no-ops.
    """
    ch = _resolve_character(target)
    if ch is None or not key:
        return False
    ad = _ACHIEVEMENTS.get(key)
    if ad is None:
        return False
    if ch.unlocked_achievements is None:
        ch.unlocked_achievements = []
    if key in ch.unlocked_achievements:
        return False
    ch.unlocked_achievements.append(key)

    # Best-effort log line — only if a world reference is reachable.
    w = world
    if w is None and hasattr(target, "log_msg"):
        w = target
    if w is not None and hasattr(w, "log_msg"):
        try:
            from ..ui.lang import t
            name = t(ad.name_key, fallback=ad.fallback_name_pl or key)
            line = t("achievement_unlocked",
                     fallback=f"Osiągnięcie odblokowane: {name}.",
                     name=name)
            w.log_msg(line, "success")
        except Exception:
            pass
    return True


def count_unlocked(target) -> int:
    ch = _resolve_character(target)
    if ch is None:
        return 0
    return len(ch.unlocked_achievements or [])


# ── Counter helpers (for "5 furniture salvage" style gates) ────────────────

def counter(character, counter_key: str) -> int:
    if character is None or not counter_key:
        return 0
    if character.flags is None:
        return 0
    return int(character.flags.get(counter_key, 0) or 0)


def bump_counter(character, counter_key: str, n: int = 1) -> int:
    if character is None or not counter_key:
        return 0
    if character.flags is None:
        character.flags = {}
    cur = int(character.flags.get(counter_key, 0) or 0)
    new = cur + int(n)
    character.flags[counter_key] = new
    return new
