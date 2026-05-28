"""Materials catalog + character-inventory helpers (Prompt 06).

Materials are pure quantities held on Character.materials (dict[str,int]).
They are not Entities — that would explode the inventory list. Items
crafted FROM materials become Entities and live in the regular inventory.

Material defs are kept lightweight: key + display tokens + tags + rarity.
The salvage system pulls quantities from drop tables and `add_material(s)`
on the character; `consume_materials()` and `has_materials()` are used by
the crafting engine.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from ..ui.lang import t


@dataclass(frozen=True)
class MaterialDef:
    key: str
    fallback_name_pl: str
    fallback_name_en: str
    tags: tuple = ()
    rarity: str = "common"               # common | uncommon | rare | weird
    fallback_description_pl: str = ""
    value: int = 1

    @property
    def name_key(self) -> str:
        return f"mat_{self.key}_n"

    @property
    def description_key(self) -> str:
        return f"mat_{self.key}_d"

    def name(self) -> str:
        return t(self.name_key, fallback=self.fallback_name_pl)

    def description(self) -> str:
        return t(self.description_key, fallback=self.fallback_description_pl)


# ── Catalog ─────────────────────────────────────────────────────────────────

def _m(key, pl, en, tags, rarity="common", desc_pl="", value=1):
    return MaterialDef(key, pl, en, tuple(tags), rarity, desc_pl, value)


MATERIALS: Dict[str, MaterialDef] = {m.key: m for m in [
    # Common
    _m("scrap_metal",      "złom metalowy",     "scrap metal",     ("metal","scrap","binding"),                "common"),
    _m("wood_fragments",   "drewno",            "wood fragments",  ("wood","handle","flammable"),               "common"),
    _m("plastic_shards",   "kawałki plastiku",  "plastic shards",  ("plastic","scrap"),                         "common"),
    _m("cloth_strips",     "paski materiału",   "cloth strips",    ("cloth","binding","absorbent","flammable"), "common"),
    _m("glass_shards",     "odłamki szkła",     "glass shards",    ("glass","sharp","fragile"),                 "common"),
    _m("wire_bundle",      "pęk przewodów",     "wire bundle",     ("wire","electrical","binding"),             "common"),
    _m("screws",           "śrubki",            "screws",          ("metal","small","binding"),                 "common"),
    _m("tape",             "taśma",             "tape",            ("binding","adhesive","flammable"),          "common"),
    _m("rubber_strip",     "pasek gumy",        "rubber strip",    ("rubber","insulator","binding"),            "common"),
    _m("ceramic_fragments","skorupy ceramiki",  "ceramic fragments",("ceramic","sharp","fragile"),              "common"),
    _m("leather_scraps",   "skóra (skrawki)",   "leather scraps",  ("leather","cloth","binding"),               "common"),

    # Organic
    _m("bone_fragments",   "kości",             "bone fragments",  ("bone","organic","sharp","handle"),         "common"),
    _m("monster_hide",     "skóra potwora",     "monster hide",    ("hide","organic","armor","cloth"),          "uncommon"),
    _m("sinew",            "ścięgno",           "sinew",           ("organic","binding","string"),              "uncommon"),
    _m("meat_chunk",       "kawałek mięsa",     "meat chunk",      ("organic","food","bait","smell"),           "common"),
    _m("tooth",            "ząb",               "tooth",           ("bone","organic","sharp","small"),          "uncommon"),
    _m("claw",             "pazur",             "claw",            ("bone","organic","sharp"),                  "uncommon"),
    _m("strange_organ",    "dziwny narząd",     "strange organ",   ("organic","weird","chemical"),              "rare"),
    _m("fungal_fiber",     "włókno grzybnicy",  "fungal fiber",    ("organic","fungal","binding"),              "uncommon"),
    _m("ichor_sample",     "próbka posoki",     "ichor sample",    ("organic","weird","chemical","smell"),      "rare"),
    _m("contaminated_blood","skażona krew",     "contaminated blood",("organic","disease","chemical"),          "rare"),

    # Technical
    _m("battery_cell",     "ogniwo baterii",    "battery cell",    ("electrical","power","container"),          "uncommon"),
    _m("circuit_board",    "płytka drukowana",  "circuit board",   ("electronic","precise"),                    "uncommon"),
    _m("camera_lens",      "obiektyw kamery",   "camera lens",     ("optical","glass","precise","sensor"),      "uncommon"),
    _m("sensor_module",    "moduł sensoryczny", "sensor module",   ("electronic","sensor","precise"),           "uncommon"),
    _m("copper_coil",      "cewka miedziana",   "copper coil",     ("metal","electrical","wire"),               "uncommon"),
    _m("insulated_wire",   "izolowany kabel",   "insulated wire",  ("wire","electrical","insulator","binding"), "common"),
    _m("broken_screen",    "rozbity ekran",     "broken screen",   ("glass","electronic","fragile","sharp"),    "common"),
    _m("motor_unit",       "silniczek",         "motor unit",      ("electronic","heavy","precise"),            "uncommon"),
    _m("pressure_valve",   "zawór ciśnieniowy", "pressure valve",  ("metal","mechanical","valve"),              "uncommon"),
    _m("data_chip",        "chip danych",       "data chip",       ("electronic","data","small","precise"),     "rare"),

    # Chemical
    _m("cleaning_fluid",   "płyn czyszczący",   "cleaning fluid",  ("chemical","flammable","liquid"),           "common"),
    _m("acid_residue",     "osad kwasu",        "acid residue",    ("chemical","acid","liquid","hazard"),       "uncommon"),
    _m("oil_canister",     "puszka oleju",      "oil canister",    ("chemical","flammable","liquid","slick"),   "common"),
    _m("disinfectant",     "środek odkażający", "disinfectant",    ("chemical","medical","liquid"),             "common"),
    _m("flammable_gel",    "żel zapalający",    "flammable gel",   ("chemical","flammable","sticky"),           "uncommon"),
    _m("coolant",          "chłodziwo",         "coolant",         ("chemical","liquid","cold"),                "uncommon"),
    _m("powdered_reagent", "odczynnik w proszku","powdered reagent",("chemical","powder","reactive"),           "uncommon"),
    _m("medical_alcohol",  "alkohol medyczny",  "medical alcohol", ("chemical","medical","flammable","liquid"), "common"),

    # Rare / weird
    _m("sponsor_chip",     "chip sponsora",     "sponsor chip",    ("electronic","sponsor","data","rare"),      "rare"),
    _m("anomaly_dust",     "pył anomalny",      "anomaly dust",    ("weird","powder","sparkle"),                "rare"),
    _m("void_residue",     "osad pustki",       "void residue",    ("weird","cold","intangible"),               "weird"),
    _m("mutation_sample",  "próbka mutacji",    "mutation sample", ("organic","weird","chemical","rare"),       "rare"),
    _m("black_glass",      "czarne szkło",      "black glass",     ("glass","sharp","weird","rare"),            "rare"),
    _m("crawler_badge",    "odznaka zawodnika", "crawler badge",   ("badge","sponsor","identity"),              "uncommon"),
    _m("contract_scrap",   "strzęp kontraktu",  "contract scrap",  ("paper","sponsor","legal","data"),          "uncommon"),
    _m("audience_token",   "żeton widowni",     "audience token",  ("sponsor","data","rare","social"),          "rare"),

    # ── P29.56 — Volatile chemicals (krytyczne dla emergentnego craftingu) ──
    _m("phosphor",         "fosfor",            "phosphor",        ("chemical","reactive","incendiary","powder"),     "uncommon"),
    _m("mercury_drop",     "kropla rtęci",      "mercury drop",    ("chemical","metal","liquid","toxic","heavy"),     "rare"),
    _m("sodium_chunk",     "bryłka sodu",       "sodium chunk",    ("chemical","reactive","metal","explosive"),       "rare"),
    _m("bleach_sachet",    "saszetka wybielacza","bleach sachet",  ("chemical","acid","liquid","caustic"),            "common"),
    _m("ether_vial",       "fiolka eteru",      "ether vial",      ("chemical","flammable","liquid","sleep"),         "uncommon"),
    _m("salt_block",       "blok soli",         "salt block",      ("chemical","powder","binding","preservative"),    "common"),

    # ── Bio-organic ──
    _m("snake_oil",        "wężowy olej",       "snake oil",       ("chemical","liquid","slick","scam","medical"),    "uncommon"),
    _m("glow_moss",        "świecący mech",     "glow moss",       ("organic","light","fungal","sparkle"),            "uncommon"),
    _m("feather_quill",    "lotka pióra",       "feather quill",   ("organic","light","sharp","handle"),              "common"),
    _m("eyeball_specimen", "okaz oka",          "eyeball specimen",("organic","weird","optical","sensor","slick"),    "rare"),

    # ── Tech expansion ──
    _m("spring_clip",      "klips sprężynowy",  "spring clip",     ("metal","mechanical","spring","binding"),         "common"),
    _m("brass_casing",     "łuska mosiężna",    "brass casing",    ("metal","container","handle","sharp"),            "common"),
    _m("fuse_strip",       "pasek bezpiecznika","fuse strip",      ("electrical","fragile","fuse","small"),           "common"),
    _m("magnetic_strip",   "pasek magnetyczny", "magnetic strip",  ("metal","magnetic","binding"),                    "uncommon"),
    _m("prism_glass",      "szkło pryzmatyczne","prism glass",     ("glass","optical","precise","sparkle"),           "rare"),
    _m("laser_diode",      "dioda laserowa",    "laser diode",     ("electronic","optical","light","sharp","precise"),"rare"),

    # ── Biome-locked: okopy_frontowe ──
    _m("trench_mud",       "okopowa glina",     "trench mud",      ("organic","sticky","cloth","binding","biome:okopy_frontowe"),       "common"),
    _m("casing_shell",     "łuska artyleryjska","casing shell",    ("metal","heavy","container","biome:okopy_frontowe"),                "uncommon"),
    _m("gas_canister",     "kanister gazu",     "gas canister",    ("chemical","gas","container","explosive","biome:okopy_frontowe"),  "rare"),
    _m("rusted_bayonet",   "zardzewiały bagnet","rusted bayonet",  ("metal","sharp","melee","handle","biome:okopy_frontowe"),           "uncommon"),

    # ── Biome-locked: zoo_korporacyjne ──
    _m("feed_pellet",      "karma w pelletach", "feed pellet",     ("organic","food","bait","biome:zoo_korporacyjne"),                  "common"),
    _m("escape_collar",    "obroża ucieczkowa", "escape collar",   ("electronic","tracker","binding","biome:zoo_korporacyjne"),         "uncommon"),
    _m("pheromone_vial",   "fiolka feromonów",  "pheromone vial",  ("chemical","organic","smell","bait","biome:zoo_korporacyjne"),      "rare"),
    _m("plastic_mask",     "plastikowa maska",  "plastic mask",    ("plastic","face","disguise","biome:zoo_korporacyjne"),              "common"),

    # ── Biome-locked: muzeum_spektakli ──
    _m("film_reel",        "rolka taśmy filmowej","film reel",     ("plastic","flammable","data","biome:muzeum_spektakli"),             "uncommon"),
    _m("plaster_cast",     "odlew gipsowy",     "plaster cast",    ("ceramic","fragile","heavy","biome:muzeum_spektakli"),              "common"),
    _m("wax_idol",         "woskowa figurka",   "wax idol",        ("wax","flammable","sticky","biome:muzeum_spektakli"),               "uncommon"),
    _m("archive_dust",     "archiwalny pył",    "archive dust",    ("powder","weird","data","biome:muzeum_spektakli"),                  "rare"),

    # ── Biome-locked: bar_skurczybyk ──
    _m("beer_yeast",       "drożdże piwne",     "beer yeast",      ("organic","fungal","flammable","biome:bar_skurczybyk"),             "common"),
    _m("brass_tap",        "kran mosiężny",     "brass tap",       ("metal","valve","handle","biome:bar_skurczybyk"),                   "uncommon"),
    _m("cocktail_pick",    "patyczek koktajlowy","cocktail pick",  ("wood","small","sharp","biome:bar_skurczybyk"),                     "common"),
    _m("ashtray_tar",      "popielniczkowy tar","ashtray tar",     ("chemical","sticky","carcinogen","biome:bar_skurczybyk"),           "uncommon"),

    # ── Biome-locked: neighborhood ──
    _m("graffiti_can",     "puszka graffiti",   "graffiti can",    ("chemical","container","spray","biome:intake_industrial"),               "common"),
    _m("pigeon_feather",   "gołębie pióro",     "pigeon feather",  ("organic","light","biome:intake_industrial"),                            "common"),
    _m("brick_chunk",      "kawałek cegły",     "brick chunk",     ("ceramic","heavy","blunt","biome:intake_industrial"),                    "common"),
    _m("subway_grime",     "metroowa sadza",    "subway grime",    ("powder","sticky","carcinogen","biome:intake_industrial"),               "uncommon"),

    # ── Biome-locked: grzybica_bloom ──
    _m("spore_capsule",    "kapsuła zarodników","spore capsule",   ("organic","fungal","powder","sparkle","biome:grzybica_bloom"),       "uncommon"),
    _m("mycelium_braid",   "warkocz grzybni",   "mycelium braid",  ("organic","fungal","binding","biome:grzybica_bloom"),                "common"),
    _m("luminous_cap",     "świecący kapelusz", "luminous cap",    ("organic","fungal","light","biome:grzybica_bloom"),                  "uncommon"),
    _m("blackrot_paste",   "pasta czarnej zgnilizny","blackrot paste",("organic","fungal","toxic","sticky","biome:grzybica_bloom"),     "rare"),

    # ── Biome-locked: intake_industrial (F1 boss biome) ──
    _m("intake_rebar",     "intake'owy zbrojeniowy","intake rebar",("metal","heavy","handle","biome:intake_industrial"),                "common"),
    _m("industrial_grease","przemysłowy smar",  "industrial grease",("chemical","slick","flammable","liquid","biome:intake_industrial"),"common"),

    # ── P29.42c — Biome-locked: 4 nowe biomy Tier-1 ──
    # fabryka_pary / Sterling-9
    _m("boiler_scale",     "kotłowa kamień",    "boiler scale",    ("ceramic","heavy","biome:fabryka_pary"),                            "common"),
    _m("pressure_valve",   "zawór ciśnieniowy", "pressure valve",  ("metal","valve","biome:fabryka_pary"),                              "uncommon"),
    _m("furnace_coal",     "węgiel kotłowy",    "furnace coal",    ("organic","flammable","fuel","biome:fabryka_pary"),                 "common"),
    # stacja_orbital / Orbital-7
    _m("pressure_seal",    "uszczelka ciśnienia","pressure seal",  ("rubber","binding","biome:stacja_orbital"),                         "common"),
    _m("nav_chip",         "chip nawigacyjny",  "nav chip",        ("electronic","data","biome:stacja_orbital"),                        "uncommon"),
    _m("cargo_strap",      "pas transportowy",  "cargo strap",     ("cloth","binding","heavy","biome:stacja_orbital"),                  "common"),
    # kuznia_polorkow
    _m("guild_iron",       "żelazo cechowe",    "guild iron",      ("metal","heavy","biome:kuznia_polorkow"),                           "uncommon"),
    _m("polork_charcoal",  "półorkowy węgiel",  "polork charcoal", ("organic","flammable","fuel","biome:kuznia_polorkow"),              "common"),
    _m("anvil_chip",       "odłamek kowadła",   "anvil chip",      ("metal","sharp","heavy","biome:kuznia_polorkow"),                   "common"),
    # biblioteka_miejska
    _m("forbidden_page",   "zakazana strona",   "forbidden page",  ("paper","data","weird","biome:biblioteka_miejska"),                 "uncommon"),
    _m("library_seal",     "biblioteczna pieczęć","library seal",  ("wax","data","biome:biblioteka_miejska"),                           "common"),
    _m("indexer_thread",   "indeksowa nić",     "indexer thread",  ("cloth","binding","biome:biblioteka_miejska"),                      "common"),
]}


def get(key: str) -> Optional[MaterialDef]:
    return MATERIALS.get(key)


def all_keys() -> List[str]:
    return list(MATERIALS.keys())


def by_tag(tag: str) -> List[MaterialDef]:
    return [m for m in MATERIALS.values() if tag in m.tags]


# ── Character helpers ───────────────────────────────────────────────────────

def has_materials(character, needed: Dict[str, int]) -> bool:
    pool = getattr(character, "materials", None) or {}
    return all(pool.get(k, 0) >= v for k, v in needed.items())


def has_material_tag_count(character, tag: str, count: int = 1) -> bool:
    """True if the player owns at least `count` total units of materials
    whose tags include `tag` (used by improvised crafting)."""
    pool = getattr(character, "materials", None) or {}
    total = 0
    for key, qty in pool.items():
        md = MATERIALS.get(key)
        if md and tag in md.tags:
            total += qty
            if total >= count:
                return True
    return False


def consume_materials(character, needed: Dict[str, int]) -> bool:
    if not has_materials(character, needed):
        return False
    character.materials = getattr(character, "materials", None) or {}
    for k, v in needed.items():
        character.materials[k] = character.materials.get(k, 0) - v
        if character.materials[k] <= 0:
            del character.materials[k]
    return True


def consume_by_tag(character, tag: str, count: int = 1) -> int:
    """Spend up to `count` total units across any materials carrying `tag`.
    Returns how many units were actually consumed."""
    pool = getattr(character, "materials", None) or {}
    spent = 0
    # Sort: common first, rare last (cheaper materials first)
    rarity_order = {"common":0, "uncommon":1, "rare":2, "weird":3}
    matching = sorted(
        [(k, qty) for k, qty in pool.items()
         if (md := MATERIALS.get(k)) and tag in md.tags],
        key=lambda kv: rarity_order.get(MATERIALS[kv[0]].rarity, 9),
    )
    for k, qty in matching:
        if spent >= count: break
        take = min(qty, count - spent)
        pool[k] -= take
        if pool[k] <= 0:
            del pool[k]
        spent += take
    character.materials = pool
    return spent


def add_material(character, key: str, qty: int = 1) -> int:
    """Add quantity of a material. Returns the new total. Safe with old saves."""
    if qty <= 0: return 0
    character.materials = getattr(character, "materials", None) or {}
    character.materials[key] = character.materials.get(key, 0) + qty
    return character.materials[key]


def add_materials(character, drops: Dict[str, int]):
    for k, v in drops.items():
        add_material(character, k, v)


def inventory_summary(character) -> List[str]:
    """Pretty-print rows for the materials inventory screen."""
    pool = getattr(character, "materials", None) or {}
    if not pool:
        return []
    rows = []
    for k in sorted(pool.keys()):
        md = MATERIALS.get(k)
        name = md.name() if md else k
        rows.append(f"  {pool[k]:>3}x  {name}")
    return rows
