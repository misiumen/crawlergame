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
    fallback_description_pl="Rozebrałeś coś, co należało do toalety w kryjówce. Nikt ci tego nie zapomni.",
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


# ── P29.15 — DCC reality-TV reskin / new content ─────────────────────────
# Each carries a chyron-style PL name (the line that flashes in studio
# during a kill or a milestone). The supplemental hooks in game.py fire
# these on the relevant action sites.

# Combat milestones.
_add(AchievementDef(
    key="pierwsza_krew",
    fallback_name_pl="Pierwsza krew, sezon w toku",
    fallback_name_en="First Blood, Season Active",
    fallback_description_pl="Pierwszy zabity uczestnik. Sponsorzy odetchnęli z ulgą.",
    fallback_description_en="First kill. The sponsors exhale.",
    category="combat",
))

_add(AchievementDef(
    key="finiszer_kanalu",
    fallback_name_pl="Finiszer Kanału 7",
    fallback_name_en="Channel 7 Finisher",
    fallback_description_pl="Krytyczne trafienie na publicznym ujęciu. Kamera 4 łapie szczegół.",
    fallback_description_en="Critical hit on a live broadcast take.",
    category="combat",
))

_add(AchievementDef(
    key="rzeznia_kontrolowana",
    fallback_name_pl="Rzeźnia kontrolowana (×50)",
    fallback_name_en="Controlled Carnage (×50)",
    fallback_description_pl="Pięćdziesiąt zabitych. Producent kupuje ci drinka — symbolicznie.",
    fallback_description_en="Fifty kills. The producer buys you a drink — symbolic.",
    category="combat",
))

_add(AchievementDef(
    key="boss_padl_pierwszy",
    fallback_name_pl="Pierwszy boss pada",
    fallback_name_en="First Boss Down",
    fallback_description_pl="Pokonałeś pierwszego bossa piętra. Studio kupuje czas reklamowy.",
    fallback_description_en="First floor-boss killed. Studio sells extra ad slots.",
    category="combat",
))

# Survival / dramatics.
_add(AchievementDef(
    key="anty_host_warknal",
    fallback_name_pl="Anti-host warknął",
    fallback_name_en="Anti-Host Snarled",
    fallback_description_pl="Last-stand: pierwszy raz spadłeś do 1 HP i wstałeś. Tylko raz.",
    fallback_description_en="Last stand: dropped to 1 HP and got back up. Only once.",
    category="survival",
    hidden=True,
))

_add(AchievementDef(
    key="reklama_przerywa_walke",
    fallback_name_pl="Reklama przerywa walkę",
    fallback_name_en="Commercial Break Interrupts Combat",
    fallback_description_pl="Wszedłeś w stan defensywny pięć rund pod rząd. Studio musi puścić reklamy.",
    fallback_description_en="Five defensive rounds in a row. Studio cuts to ads.",
    category="combat",
    hidden=True,
))

_add(AchievementDef(
    key="brak_zwlok_brak_problemu",
    fallback_name_pl="Brak zwłok, brak problemu",
    fallback_name_en="No Bodies, No Problem",
    fallback_description_pl="Pierwsze piętro przeszedłeś bez zabicia nikogo. Sponsorzy pamiętają.",
    fallback_description_en="First floor cleared without killing anyone. Sponsors remember.",
    category="stealth",
    hidden=True,
))

# Floors / descent.
_add(AchievementDef(
    key="dno_jeszcze_dalej",
    fallback_name_pl="Dno, jeszcze dalej",
    fallback_name_en="Bottom, Still Going",
    fallback_description_pl="Schody w dół drugi raz. Loch zaczyna pamiętać twoje imię.",
    fallback_description_en="Second descent. The dungeon starts remembering your name.",
    category="floor",
))

_add(AchievementDef(
    key="piaty_set",
    fallback_name_pl="Piąty set",
    fallback_name_en="Fifth Set",
    fallback_description_pl="Dotarłeś na piętro 5. Sezon się rozkręca.",
    fallback_description_en="Reached floor 5. The season is heating up.",
    category="floor",
))

_add(AchievementDef(
    key="dziesiate_pietro",
    fallback_name_pl="Dziesiąte piętro",
    fallback_name_en="Floor Ten",
    fallback_description_pl="Połowa Lochu za tobą. Anti-host przeznaczył ci osobny intro.",
    fallback_description_en="Half the dungeon done. Anti-host writes you a custom intro.",
    category="floor",
))

_add(AchievementDef(
    key="finalista_sezonu",
    fallback_name_pl="Finalista sezonu",
    fallback_name_en="Season Finalist",
    fallback_description_pl="Pokonałeś Prezesa Syndykatu. Generalny dyrektor pyta o twoje plany.",
    fallback_description_en="Defeated the Syndicate Chairman. The CEO inquires about your plans.",
    category="floor",
    hidden=True,
))

# Sponsors / audience.
_add(AchievementDef(
    key="pakiet_z_sufitu",
    fallback_name_pl="Pakiet z sufitu",
    fallback_name_en="Package from the Ceiling",
    fallback_description_pl="Otwarłeś pierwszy pakiet sponsorski w pokoju. Marka cię polubiła.",
    fallback_description_en="Opened your first sponsor drop pod. The brand likes you.",
    category="sponsor",
))

_add(AchievementDef(
    key="markowy_uczestnik",
    fallback_name_pl="Markowy uczestnik",
    fallback_name_en="Branded Contestant",
    fallback_description_pl="Odblokowałeś sponsorski przepis. Logo na rękawie.",
    fallback_description_en="Unlocked a sponsor-branded recipe. Logo on the sleeve.",
    category="sponsor",
))

_add(AchievementDef(
    key="widownia_gorzej_bije",
    fallback_name_pl="Widownia gorzej bije",
    fallback_name_en="Audience Beats Harder",
    fallback_description_pl="Wskaźnik widowni przekroczył 50. Ktoś robi ci memy.",
    fallback_description_en="Audience meter crossed 50. Someone's making you into memes.",
    category="audience",
))

_add(AchievementDef(
    key="kult_jednostki",
    fallback_name_pl="Kult jednostki",
    fallback_name_en="Cult of Personality",
    fallback_description_pl="Wskaźnik widowni przekroczył 80. Ktoś sprzedaje t-shirty.",
    fallback_description_en="Audience meter crossed 80. Someone's selling t-shirts.",
    category="audience",
))

# Crafting (P29.14).
_add(AchievementDef(
    key="dzielo_mistrzowskie",
    fallback_name_pl="Dzieło mistrzowskie",
    fallback_name_en="Masterwork",
    fallback_description_pl="Wytworzyłeś przedmiot mistrzowskiej jakości. Twoje ręce już wiedzą.",
    fallback_description_en="Crafted a masterwork-quality item. Your hands have learned.",
    category="craft",
))

_add(AchievementDef(
    key="apteka_w_plecaku",
    fallback_name_pl="Apteka w plecaku",
    fallback_name_en="Apothecary in the Backpack",
    fallback_description_pl="Pierwsza nałożona warstwa wzmocnienia. Twoja broń ma teraz drugie życie.",
    fallback_description_en="First enhancement applied. Your gear has a second life.",
    category="craft",
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
