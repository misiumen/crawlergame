"""P29.56 — Eksperymentalny system craftingu.

Każdy przepis (oprócz `_STARTING_RECIPES` z `content/crafting.py`) jest
domyślnie **nieznany** graczowi. Odkrywanie zachodzi na trzy sposoby:

1. `recipe_note_*` — fizyczny item-zwój znaleziony w lochu (P29.52).
2. `nauczyciel` w safehouse — opłata kredytami za jedną receptę.
3. **Eksperyment** (`eksperymentuj X, Y, Z`) — gracz wybiera 3-5
   materiałów. Jeśli ich tagi pokrywają jakąś nieznaną recepturę,
   rzut INT vs DC (zależne od liczby składników) decyduje. Crit
   produkuje UNIKAT z proceduralnym afiksem.

Format wpisu:
    {
        "key": str,                  -- internal recipe key
        "name_pl": str,              -- display name (po polsku)
        "desc_pl": str,              -- 1-2 zdaniowy flavor
        "tier": 3 | 4 | 5,           -- liczba wymaganych składników
        "material_tags": [           -- każdy tag musi się pokryć w
            (tag, min_count), ...    --   materiałach gracza, count
        ],                           --   sumarycznie po wszystkich mat.
        "result": {                  -- co się tworzy:
            "effect": "coating"|"permanent"|"weapon"|"trap"|"throwable"
                     |"food"|"medical"|"tool"|"armor"|"unique",
            "applies_to_tags": [...],  # dla coating/permanent
            "coating": {...},          # dla coating
            "permanent": {...},        # dla permanent
            "damage_dice": str,        # dla weapon
            "damage_type": str,        # dla weapon
            "tags": [...],             # dla weapon/trap/...
            "heal": int,               # dla food/medical
            "buff_status": str,        # dla food/medical
        },
        "base_rarity": "common"|"uncommon"|"rare"|"epic",
        "discipline": "chemistry"|"electronics"|"mechanics"|"bio"
                     |"alchemy"|"culinary"|"tinker",
        "biome_lock": None | str,    -- jeśli ustawione, eksperyment
                                     --   wymaga obecnego biomu (lub
                                     --   recipe_note z innego)
        "fumble_hazard": str,        -- co się stanie przy fumble (nat 1-2)
        "audience_create": int,      -- +N widowni po udanym crafcie
    }

Tagi materiałów łączą się: jeśli np. masz `cleaning_fluid` (chemical+
flammable) + `cloth_strips` (cloth+binding+absorbent+flammable), to
profile = {chemical:1, flammable:2, cloth:1, binding:1, absorbent:1}.
Receptura wymaga {chemical:1, binding:1} ⇒ MATCH.
"""
from __future__ import annotations
from typing import Dict, List, Tuple, Optional


# ── Builders (skróty żeby autorzy nie powtarzali boilerplate) ────────


def _coating(key, name, desc, tier, tags, dmg_type, hits=4, extra=1,
             rarity="uncommon", discipline="chemistry",
             biome=None, fumble="chemical_splash", aud=2):
    return {
        "key": key, "name_pl": name, "desc_pl": desc, "tier": tier,
        "material_tags": tags,
        "result": {
            "effect": "coating",
            "applies_to_tags": ["weapon"],
            "coating": {"damage_type": dmg_type, "hits_remaining": hits,
                        "extra_damage": extra},
        },
        "base_rarity": rarity, "discipline": discipline,
        "biome_lock": biome, "fumble_hazard": fumble,
        "audience_create": aud,
    }


def _permanent_weapon(key, name, desc, tier, tags, perm,
                      rarity="uncommon", discipline="mechanics",
                      biome=None, fumble="waste_materials", aud=2):
    return {
        "key": key, "name_pl": name, "desc_pl": desc, "tier": tier,
        "material_tags": tags,
        "result": {
            "effect": "permanent",
            "applies_to_tags": ["weapon"],
            "permanent": perm,
        },
        "base_rarity": rarity, "discipline": discipline,
        "biome_lock": biome, "fumble_hazard": fumble,
        "audience_create": aud,
    }


def _weapon(key, name, desc, tier, tags, dice, dmg_type, w_tags,
            rarity="uncommon", discipline="mechanics",
            biome=None, fumble="flawed_item", aud=2):
    return {
        "key": key, "name_pl": name, "desc_pl": desc, "tier": tier,
        "material_tags": tags,
        "result": {
            "effect": "weapon", "damage_dice": dice,
            "damage_type": dmg_type, "tags": list(w_tags),
        },
        "base_rarity": rarity, "discipline": discipline,
        "biome_lock": biome, "fumble_hazard": fumble,
        "audience_create": aud,
    }


def _trap(key, name, desc, tier, tags, payload,
          rarity="uncommon", discipline="tinker",
          biome=None, fumble="trap_misfire", aud=3):
    return {
        "key": key, "name_pl": name, "desc_pl": desc, "tier": tier,
        "material_tags": tags,
        "result": {"effect": "trap", "payload": payload,
                   "tags": ["trap", "deployable"] + payload.get("extra_tags", [])},
        "base_rarity": rarity, "discipline": discipline,
        "biome_lock": biome, "fumble_hazard": fumble,
        "audience_create": aud,
    }


def _throwable(key, name, desc, tier, tags, payload,
               rarity="uncommon", discipline="chemistry",
               biome=None, fumble="chemical_splash", aud=3):
    return {
        "key": key, "name_pl": name, "desc_pl": desc, "tier": tier,
        "material_tags": tags,
        "result": {"effect": "throwable", "payload": payload,
                   "tags": ["throwable", "consumable"] + payload.get("extra_tags", [])},
        "base_rarity": rarity, "discipline": discipline,
        "biome_lock": biome, "fumble_hazard": fumble,
        "audience_create": aud,
    }


def _food(key, name, desc, tier, tags, heal, buff=None,
          rarity="common", discipline="culinary",
          biome=None, fumble="food_poisoning", aud=1):
    return {
        "key": key, "name_pl": name, "desc_pl": desc, "tier": tier,
        "material_tags": tags,
        "result": {"effect": "food", "heal": heal,
                   "buff_status": buff,
                   "tags": ["food", "consumable"]},
        "base_rarity": rarity, "discipline": discipline,
        "biome_lock": biome, "fumble_hazard": fumble,
        "audience_create": aud,
    }


def _medical(key, name, desc, tier, tags, heal, cures=(), buff_status=None,
             rarity="uncommon", discipline="bio",
             biome=None, fumble="contamination", aud=1):
    return {
        "key": key, "name_pl": name, "desc_pl": desc, "tier": tier,
        "material_tags": tags,
        "result": {"effect": "medical", "heal": heal,
                   "cures_statuses": list(cures),
                   "buff_status": buff_status,
                   "tags": ["medical", "consumable"]},
        "base_rarity": rarity, "discipline": discipline,
        "biome_lock": biome, "fumble_hazard": fumble,
        "audience_create": aud,
    }


def _tool(key, name, desc, tier, tags, tool_kind,
          rarity="uncommon", discipline="electronics",
          biome=None, fumble="waste_materials", aud=1):
    return {
        "key": key, "name_pl": name, "desc_pl": desc, "tier": tier,
        "material_tags": tags,
        "result": {"effect": "tool", "tool_kind": tool_kind,
                   "tags": ["tool"]},
        "base_rarity": rarity, "discipline": discipline,
        "biome_lock": biome, "fumble_hazard": fumble,
        "audience_create": aud,
    }


def _armor(key, name, desc, tier, tags, perm,
           rarity="uncommon", discipline="mechanics",
           biome=None, fumble="waste_materials", aud=1):
    return {
        "key": key, "name_pl": name, "desc_pl": desc, "tier": tier,
        "material_tags": tags,
        "result": {"effect": "permanent",
                   "applies_to_tags": ["armor", "clothing"],
                   "permanent": perm},
        "base_rarity": rarity, "discipline": discipline,
        "biome_lock": biome, "fumble_hazard": fumble,
        "audience_create": aud,
    }


# ──────────────────────────────────────────────────────────────────────
# Katalog 110+ recept eksperymentalnych.
# Pogrupowane po kategoriach. Tier = liczba składników.
# ──────────────────────────────────────────────────────────────────────


EXPERIMENTAL_RECIPES: List[Dict] = [

    # ── COATINGS: 6 typów damage × 2 wariacje (base + amped) ──────────

    _coating("weapon_acid_coat", "olej żrący",
             "Wyciek z butelki bleach'a + chłonny materiał. Rdzewieje "
             "wszystko czego dotknie.",
             tier=3, tags=[("acid", 1), ("absorbent", 1), ("liquid", 1)],
             dmg_type="acid", hits=4, extra=1),

    _coating("weapon_acid_coat_amped", "smoła trawiąca",
             "Wybielacz + tar + rdza. Pulsuje. Dwa razy gorzej niż "
             "zwykły olej żrący.",
             tier=4, tags=[("acid", 1), ("sticky", 1), ("metal", 1), ("hazard", 1)],
             dmg_type="acid", hits=6, extra=2, rarity="rare"),

    _coating("weapon_fire_coat", "olej zapalający",
             "Fosfor zmieszany z naftą. Płonie w kontakcie z powietrzem.",
             tier=3, tags=[("incendiary", 1), ("flammable", 1), ("binding", 1)],
             dmg_type="fire", hits=4, extra=1, fumble="ignite_self"),

    _coating("weapon_fire_coat_amped", "napalm rzemieślniczy",
             "Żel + paliwo + tar. Lepi się i pali aż do dna.",
             tier=4, tags=[("flammable", 2), ("sticky", 1), ("incendiary", 1)],
             dmg_type="fire", hits=6, extra=2, rarity="rare", fumble="ignite_self"),

    _coating("weapon_shock_coat", "powłoka piorunowa",
             "Cewka miedziana + bateria + przewody. Kropi iskrami.",
             tier=3, tags=[("electrical", 2), ("metal", 1)],
             dmg_type="electric", hits=3, extra=1, discipline="electronics",
             fumble="shock_self"),

    _coating("weapon_shock_coat_amped", "kondensator bólu",
             "Pełny obwód z magnesem. Każdy cios rozładowuje kondensator.",
             tier=4, tags=[("electrical", 2), ("magnetic", 1), ("power", 1)],
             dmg_type="electric", hits=5, extra=2, rarity="rare",
             discipline="electronics", fumble="shock_self"),

    _coating("weapon_frost_coat", "powłoka mrożąca",
             "Chłodziwo + sól + szmaty. Przyciemnia stal mrozem.",
             tier=3, tags=[("cold", 1), ("chemical", 1), ("binding", 1)],
             dmg_type="cold", hits=4, extra=1),

    _coating("weapon_frost_coat_amped", "ostrze zimnej zorzy",
             "Chłodziwo + szkło pryzmatyczne + olej. Każdy cios szrony.",
             tier=4, tags=[("cold", 1), ("optical", 1), ("liquid", 1), ("sparkle", 1)],
             dmg_type="cold", hits=6, extra=2, rarity="rare"),

    _coating("weapon_psychic_coat", "kalambur szeptu",
             "Próbka mutacji + włókno grzybnicy + sól. Słychać szept "
             "z ostrza, kiedy zbliżasz je do ofiary.",
             tier=4, tags=[("weird", 1), ("organic", 1), ("preservative", 1)],
             dmg_type="psychic", hits=3, extra=2, rarity="rare", discipline="alchemy"),

    _coating("weapon_void_jadwiga", "powłoka pustki",
             "Czarne szkło + osad pustki + tar. Cios znika i wraca "
             "z innej strony.",
             tier=4, tags=[("weird", 2), ("sticky", 1), ("sharp", 1)],
             dmg_type="psychic", hits=4, extra=3, rarity="epic", discipline="alchemy",
             fumble="reality_glitch"),

    # Hybrydowe coatings (premia za pomysłowość)
    _coating("weapon_acid_fire_hybrid", "termit",
             "Kwas + fosfor + glina. Najpierw boli, potem płonie.",
             tier=4, tags=[("acid", 1), ("incendiary", 1), ("powder", 1), ("binding", 1)],
             dmg_type="acid", hits=3, extra=3, rarity="rare", aud=4,
             fumble="ignite_self"),

    _coating("weapon_frost_shock_hybrid", "promień zimnej iskry",
             "Chłodziwo + ogniwo + lustrzane szkło. Mrozi i rozłada.",
             tier=4, tags=[("cold", 1), ("electrical", 1), ("optical", 1)],
             dmg_type="cold", hits=4, extra=2, rarity="rare", discipline="electronics", aud=4,
             fumble="shock_self"),

    # ── PERMANENT weapon enhancements (8) ────────────────────────────

    _permanent_weapon("weapon_recoil_dampener", "tłumik odrzutu",
        "Sprężyna + guma + taśma. Cięższy chwyt, ale łatwiej trafić.",
        tier=3, tags=[("spring", 1), ("rubber", 1), ("binding", 1)],
        perm={"attack_bonus": 1, "tag_add": "stable"}),

    _permanent_weapon("weapon_weighted_pommel", "wyważona głowica",
        "Mosiężna łuska + ołów + tarcia. Cios pewniejszy.",
        tier=3, tags=[("metal", 2), ("handle", 1)],
        perm={"damage_bonus": 1, "tag_add": "heavy"}),

    _permanent_weapon("weapon_serrated_edge", "ząbkowany brzeg",
        "Pilnik + olej + szlif. Rany się nie zamykają.",
        tier=3, tags=[("metal", 1), ("sharp", 1), ("slick", 1)],
        perm={"damage_bonus": 1, "tag_add": "serrated"},
        discipline="mechanics", aud=3),

    _permanent_weapon("weapon_kanal7_branding", "branding Kanału 7",
        "Logo sponsora wypalone w kolbie. Audience love.",
        tier=4, tags=[("sponsor", 1), ("metal", 1), ("optical", 1), ("handle", 1)],
        perm={"tag_add": "sponsored", "audience_on_hit": 1},
        rarity="rare", discipline="tinker", aud=5),

    _permanent_weapon("weapon_bonded_grip", "wiązany chwyt",
        "Skóra + ścięgno + smoła. Broń się nie wyślizgnie.",
        tier=3, tags=[("leather", 1), ("organic", 1), ("sticky", 1)],
        perm={"tag_add": "bonded", "no_disarm": True}),

    _permanent_weapon("weapon_silenced_action", "wytłumiony mechanizm",
        "Wełna + olej + szmaty. Cios bez echa.",
        tier=3, tags=[("cloth", 2), ("slick", 1)],
        perm={"tag_add": "silent"}),

    _permanent_weapon("weapon_telescoping", "teleskopowa rękojeść",
        "Trzy rurki + sprężyna + magnes. Zasięg +1 band.",
        tier=4, tags=[("metal", 2), ("spring", 1), ("magnetic", 1)],
        perm={"tag_add": "extended_reach"}, rarity="rare"),

    _permanent_weapon("weapon_anti_armor_pick", "kolec anty-pancerny",
        "Wąski stalowy kolec dospawany do trzonu. Ignoruje 2 AC.",
        tier=4, tags=[("metal", 2), ("sharp", 2)],
        perm={"tag_add": "armor_piercing", "ac_pierce": 2}, rarity="rare"),

    # ── CRAFTED WEAPONS — elemental / unique (15) ─────────────────────

    _weapon("crafted_thermal_blade", "ostrze termiczne",
        "Fosfor wtopiony w stal. Cios parzy.",
        tier=4, tags=[("metal", 1), ("incendiary", 1), ("handle", 1), ("flammable", 1)],
        dice="1d8", dmg_type="fire",
        w_tags=["weapon", "sharp", "melee", "one_handed", "incendiary"], rarity="rare"),

    _weapon("crafted_acid_dagger", "kwasowy sztylet",
        "Ostrze maczane w bleach'u. Pamięta każdą krew którą widziało.",
        tier=4, tags=[("metal", 1), ("sharp", 1), ("acid", 1), ("handle", 1)],
        dice="1d6+1", dmg_type="acid",
        w_tags=["weapon", "sharp", "melee", "one_handed"], rarity="rare"),

    _weapon("crafted_railgun_stick", "kij gauss",
        "Cewka + ogniwo + pręt. Strzela szybko, ale jednorazowo na hit.",
        tier=5, tags=[("metal", 2), ("electrical", 2), ("power", 1)],
        dice="1d10", dmg_type="electric",
        w_tags=["weapon", "ranged", "two_handed", "electrical"], rarity="rare",
        discipline="electronics"),

    _weapon("crafted_frost_pick", "lodowy kilof",
        "Chłodziwo w stalowej tubie. Cios mrozi punkt.",
        tier=4, tags=[("metal", 1), ("cold", 1), ("handle", 1), ("sharp", 1)],
        dice="1d6+2", dmg_type="cold",
        w_tags=["weapon", "sharp", "melee", "one_handed"], rarity="rare"),

    _weapon("crafted_psychic_focus", "psychiczny fokus",
        "Próbka mutacji + szkło pryzmatyczne. Cios w głowę = afraid.",
        tier=5, tags=[("weird", 1), ("optical", 1), ("organic", 1), ("precise", 1)],
        dice="1d4", dmg_type="psychic",
        w_tags=["weapon", "melee", "one_handed", "psychic"], rarity="epic",
        discipline="alchemy"),

    _weapon("crafted_chemspray_pistol", "pistolet chem-spray",
        "Pusta puszka graffiti + rura + zapalniczka. Strzela mgłą.",
        tier=4, tags=[("container", 1), ("spray", 1), ("chemical", 1), ("metal", 1)],
        dice="1d6", dmg_type="acid",
        w_tags=["weapon", "ranged", "one_handed"], rarity="uncommon"),

    _weapon("crafted_bone_club", "kostny maczug",
        "Większa kość + ścięgno + skóra. Działa.",
        tier=3, tags=[("bone", 1), ("handle", 1), ("binding", 1)],
        dice="1d6+1", dmg_type="physical",
        w_tags=["weapon", "blunt", "melee", "one_handed"]),

    _weapon("crafted_brass_knuckles", "kastet mosiężny",
        "Łuski + skóra + tarcia. Pięść z dodatkiem.",
        tier=3, tags=[("metal", 1), ("handle", 1), ("small", 1)],
        dice="1d4+2", dmg_type="physical",
        w_tags=["weapon", "blunt", "melee", "one_handed", "subtle"]),

    _weapon("crafted_thrown_spike", "rzucany kolec",
        "Lotka + grot + ścięgno. Jednorazowy.",
        tier=3, tags=[("sharp", 1), ("light", 1), ("binding", 1)],
        dice="1d4", dmg_type="physical",
        w_tags=["weapon", "ranged", "throwable", "one_handed"]),

    _weapon("crafted_void_whisper_blade", "ostrze szeptu pustki",
        "Czarne szkło + osad pustki + ścięgno + lustrzany szard. "
        "Ostrze nie odbija światła.",
        tier=5, tags=[("weird", 2), ("sharp", 1), ("optical", 1), ("organic", 1)],
        dice="1d8+2", dmg_type="psychic",
        w_tags=["weapon", "sharp", "melee", "one_handed", "unique"],
        rarity="epic", discipline="alchemy"),

    _weapon("crafted_trench_bayonet", "okopowy bagnet",
        "Zardzewiały bagnet + nowy uchwyt + ostrzony brzeg. "
        "Historię zostawia w przeciwniku.",
        tier=3, tags=[("metal", 1), ("sharp", 1), ("handle", 1), ("biome:okopy_frontowe", 1)],
        dice="1d8", dmg_type="physical",
        w_tags=["weapon", "sharp", "melee", "two_handed"], rarity="uncommon",
        biome="okopy_frontowe"),

    _weapon("crafted_zoo_taser", "ZOO-taser",
        "Obroża + bateria + kij. Hodowca by się ucieszył.",
        tier=4, tags=[("electrical", 1), ("metal", 1), ("handle", 1), ("biome:zoo_korporacyjne", 1)],
        dice="1d6", dmg_type="electric",
        w_tags=["weapon", "melee", "one_handed", "electrical"], rarity="rare",
        biome="zoo_korporacyjne", discipline="electronics"),

    _weapon("crafted_film_garrote", "garota z taśmy filmowej",
        "Trzy metry błyszczącej taśmy + dwa drewniane uchwyty. Cicha.",
        tier=3, tags=[("plastic", 1), ("flammable", 1), ("biome:muzeum_spektakli", 1)],
        dice="1d4+1", dmg_type="physical",
        w_tags=["weapon", "silent", "melee", "one_handed"],
        rarity="uncommon", biome="muzeum_spektakli"),

    _weapon("crafted_brass_tap_mace", "buława z kranu",
        "Mosiężny kran + drewno + cocktail pick. Maczuga w stylu lokalu.",
        tier=3, tags=[("metal", 1), ("handle", 1), ("biome:bar_skurczybyk", 1)],
        dice="1d6+1", dmg_type="physical",
        w_tags=["weapon", "blunt", "melee", "one_handed"],
        rarity="uncommon", biome="bar_skurczybyk"),

    _weapon("crafted_brick_sling", "proca z cegły",
        "Cegła + pasek skóry + kij. Rzut z miłością do bloku.",
        tier=3, tags=[("ceramic", 1), ("heavy", 1), ("binding", 1), ("biome:intake_industrial", 1)],
        dice="1d6+2", dmg_type="physical",
        w_tags=["weapon", "ranged", "blunt", "one_handed"],
        rarity="uncommon", biome="intake_industrial"),

    # ── TRAPS (12) ────────────────────────────────────────────────────

    _trap("trap_acid_pit", "fosa kwasu",
        "Kanister + bleach + cloth. Otwiera się pod stopą wroga.",
        tier=4, tags=[("acid", 2), ("container", 1), ("binding", 1)],
        payload={"type": "damage_and_status", "damage": 6, "damage_type": "acid",
                 "status": "corroded", "duration": 8, "extra_tags": ["acid"]}),

    _trap("trap_napalm_brick", "cegła napalmowa",
        "Cegła + fosfor + olej. Wybucha pod ciężarem.",
        tier=4, tags=[("incendiary", 1), ("heavy", 1), ("flammable", 2)],
        payload={"type": "damage_and_status", "damage": 8, "damage_type": "fire",
                 "status": "burning", "duration": 3, "extra_tags": ["fire", "explosive"]},
        rarity="rare", fumble="ignite_self"),

    _trap("trap_static_loop", "pętla statyczna",
        "Cewka + bateria + przewody + magnes. Aktywuje się na ruchu.",
        tier=4, tags=[("electrical", 2), ("magnetic", 1), ("power", 1)],
        payload={"type": "damage_and_status", "damage": 5, "damage_type": "electric",
                 "status": "shocked", "duration": 2, "extra_tags": ["electric"]},
        discipline="electronics"),

    _trap("trap_frost_mine", "mina mrozu",
        "Chłodziwo + sprężyna + płyta. Trzaska zimno na trafionego.",
        tier=4, tags=[("cold", 1), ("spring", 1), ("metal", 1), ("liquid", 1)],
        payload={"type": "damage_and_status", "damage": 4, "damage_type": "cold",
                 "status": "chilled", "duration": 3, "extra_tags": ["cold"]}),

    _trap("trap_glue_net", "siatka kleju",
        "Cloth + tar + chemia. Łapie i unieruchamia.",
        tier=3, tags=[("cloth", 1), ("sticky", 2)],
        payload={"type": "damage_and_status", "damage": 1, "damage_type": "physical",
                 "status": "grappled", "duration": 4, "extra_tags": ["restraint"]}),

    _trap("trap_pheromone_lure", "wabik feromonowy",
        "Fiolka + cloth + bait. Przyciąga inne moby ze sąsiednich pokoi.",
        tier=4, tags=[("smell", 1), ("bait", 1), ("organic", 1), ("biome:zoo_korporacyjne", 1)],
        payload={"type": "lure_extra_mob", "duration": 0, "extra_tags": ["lure"]},
        biome="zoo_korporacyjne", rarity="rare"),

    _trap("trap_artillery_marker", "marker artyleryjski",
        "Łuska + flara + drut. Wskazuje wrogowi cel z góry.",
        tier=4, tags=[("metal", 1), ("incendiary", 1), ("biome:okopy_frontowe", 1), ("binding", 1)],
        payload={"type": "delayed_damage", "damage": 10, "delay_turns": 2,
                 "damage_type": "fire", "extra_tags": ["fire", "explosive"]},
        biome="okopy_frontowe", rarity="rare"),

    _trap("trap_film_flash", "flesz filmowy",
        "Rolka taśmy + bateria + soczewka. Oślepia i daje audience.",
        tier=4, tags=[("flammable", 1), ("optical", 1), ("power", 1), ("biome:muzeum_spektakli", 1)],
        payload={"type": "damage_and_status", "damage": 2, "damage_type": "fire",
                 "status": "blinded", "duration": 3, "extra_tags": ["fire", "light"]},
        biome="muzeum_spektakli", rarity="rare", aud=5),

    _trap("trap_drunk_glasses", "rozsypane szklanki",
        "Kosz szklanek + tar + tap. Rozsypuje się.",
        tier=3, tags=[("glass", 1), ("sticky", 1), ("biome:bar_skurczybyk", 1)],
        payload={"type": "damage_and_status", "damage": 3, "damage_type": "physical",
                 "status": "bleeding", "duration": 4, "extra_tags": ["sharp"]},
        biome="bar_skurczybyk"),

    _trap("trap_pigeon_swarm", "rój gołębi",
        "Karma + feromon + brick. Gołębie zaatakują pierwszego wroga.",
        tier=4, tags=[("organic", 2), ("bait", 1), ("biome:intake_industrial", 1)],
        payload={"type": "damage_and_status", "damage": 3, "damage_type": "physical",
                 "status": "blinded", "duration": 2, "extra_tags": ["swarm"]},
        biome="intake_industrial", rarity="rare"),

    _trap("trap_spring_caltrops", "sprężynowe gwoździe",
        "Spring + nails + metal. Strzelają na trafionego.",
        tier=3, tags=[("metal", 2), ("spring", 1), ("sharp", 1)],
        payload={"type": "damage_and_status", "damage": 4, "damage_type": "physical",
                 "status": "slowed", "duration": 3, "extra_tags": ["sharp"]}),

    _trap("trap_void_silence_zone", "strefa cichej pustki",
        "Osad pustki + woskowa figurka + sól. Negatywna aura: −audience −threat.",
        tier=5, tags=[("weird", 2), ("preservative", 1), ("wax", 1)],
        payload={"type": "zone", "audience_drain": 2, "threat_drain": 3,
                 "duration": 5, "extra_tags": ["weird"]},
        rarity="epic", discipline="alchemy", aud=4),

    # ── THROWABLES (10) ───────────────────────────────────────────────

    _throwable("throwable_acid_flask_mk2", "ulepszona fiolka żrąca",
        "Bleach + acid + glass. Splash + corroded.",
        tier=3, tags=[("acid", 2), ("glass", 1)],
        payload={"type": "aoe", "damage": 5, "damage_type": "acid",
                 "status": "corroded", "radius": 1, "extra_tags": ["acid"]}),

    _throwable("throwable_smoke_blackout", "dym pełnej ciemności",
        "Phosphor + cloth + chemical. Cały pokój blind.",
        tier=4, tags=[("powder", 1), ("flammable", 1), ("cloth", 1), ("reactive", 1)],
        payload={"type": "room_blind", "duration": 4, "extra_tags": ["smoke"]},
        rarity="rare"),

    _throwable("throwable_frost_grenade", "granat mrozu",
        "Chłodziwo + container + spring. AOE chilled.",
        tier=4, tags=[("cold", 1), ("container", 1), ("spring", 1), ("liquid", 1)],
        payload={"type": "aoe", "damage": 3, "damage_type": "cold",
                 "status": "chilled", "radius": 1, "extra_tags": ["cold"]}),

    _throwable("throwable_emp_grenade", "granat EMP",
        "Bateria + cewka + ogniwo + magnes. Rozwala elektronikę.",
        tier=5, tags=[("electrical", 2), ("power", 1), ("magnetic", 1)],
        payload={"type": "aoe_electronic", "damage": 6, "damage_type": "electric",
                 "status": "shocked", "radius": 1, "extra_tags": ["electric"]},
        rarity="rare", discipline="electronics"),

    _throwable("throwable_psychic_chime", "psychiczny dzwonek",
        "Próbka mutacji + dzwonek + pióro. Wszyscy w pokoju afraid.",
        tier=4, tags=[("weird", 1), ("metal", 1), ("light", 1)],
        payload={"type": "room_status", "status": "afraid", "duration": 3,
                 "extra_tags": ["weird", "psychic"]},
        rarity="rare", discipline="alchemy", aud=4),

    _throwable("throwable_bottle_grenade", "butelka eksplozywna",
        "Sód + woda + szkło. Eksploduje przy kontakcie z wilgocią.",
        tier=3, tags=[("explosive", 1), ("glass", 1), ("reactive", 1)],
        payload={"type": "aoe", "damage": 7, "damage_type": "fire",
                 "radius": 1, "extra_tags": ["explosive"]},
        rarity="rare", fumble="explode_self"),

    _throwable("throwable_glue_bomb", "klejowa bomba",
        "Tar + cloth + binder. Wszyscy w pokoju grappled.",
        tier=3, tags=[("sticky", 2), ("cloth", 1)],
        payload={"type": "room_status", "status": "grappled", "duration": 3,
                 "extra_tags": ["restraint"]}),

    _throwable("throwable_distraction_firecracker", "petarda odwracająca",
        "Sód + papier + cloth. Świni cały threat zegar.",
        tier=3, tags=[("reactive", 1), ("paper", 1), ("flammable", 1)],
        payload={"type": "threat_reset", "audience_gain": 3,
                 "extra_tags": ["spectacle"]}),

    _throwable("throwable_gas_canister_lob", "rzut gazem",
        "Kanister gazu + spring. Splash kwaśny + cough.",
        tier=4, tags=[("gas", 1), ("container", 1), ("hazard", 1), ("biome:okopy_frontowe", 1)],
        payload={"type": "aoe", "damage": 4, "damage_type": "acid",
                 "status": "poisoned", "radius": 2, "extra_tags": ["gas", "biome:okopy_frontowe"]},
        biome="okopy_frontowe", rarity="rare"),

    _throwable("throwable_pheromone_grenade", "granat feromonowy",
        "Fiolka feromonów + spring + cloth. Wciąga moby z sąsiednich pokoi.",
        tier=4, tags=[("smell", 1), ("organic", 1), ("spring", 1), ("biome:zoo_korporacyjne", 1)],
        payload={"type": "lure_extra_mob", "duration": 0,
                 "extra_tags": ["lure", "biome:zoo_korporacyjne"]},
        biome="zoo_korporacyjne", rarity="rare"),

    # ── ARMOR / WEARABLES (8) ─────────────────────────────────────────

    _armor("armor_chitin_plating", "chitynowa płyta",
        "Pancerz potwora + ścięgno + szmaty. +2 AC.",
        tier=3, tags=[("hide", 1), ("organic", 1), ("binding", 1)],
        perm={"ac_bonus": 2, "tag_add": "reinforced"}),

    _armor("armor_acid_lining_mk2", "wzmocnione wyłożenie kwasoodporne",
        "Guma + rubber + chemical. Imuno na acid statusy.",
        tier=4, tags=[("rubber", 2), ("chemical", 1), ("insulator", 1)],
        perm={"ac_bonus": 1, "tag_add": "acid_proof", "status_immune": "corroded"},
        rarity="rare"),

    _armor("armor_insulated_jacket", "izolowana kurtka",
        "Rubber + leather + wire mesh. Imuno na shock.",
        tier=4, tags=[("rubber", 1), ("leather", 1), ("insulator", 1), ("wire", 1)],
        perm={"ac_bonus": 1, "tag_add": "insulated", "status_immune": "shocked"},
        rarity="rare", discipline="electronics"),

    _armor("armor_fire_resistant_robe", "ognioodporna szata",
        "Salt + cloth + glina. Splash fire reduced 50%.",
        tier=4, tags=[("preservative", 1), ("cloth", 2), ("powder", 1)],
        perm={"ac_bonus": 1, "tag_add": "fire_resistant", "resist": "fire"}),

    _armor("armor_kanal7_jersey", "koszulka Kanału 7",
        "Logo sponsora wszyte. Audience x1.1 na hit.",
        tier=3, tags=[("cloth", 1), ("sponsor", 1), ("identity", 1)],
        perm={"tag_add": "sponsored", "audience_mul": 1.1}, rarity="rare", aud=4),

    _armor("armor_void_cloak", "płaszcz z osadu pustki",
        "Osad pustki + wax idol + cloth. 25% szans na auto-evade vs ranged.",
        tier=5, tags=[("weird", 1), ("wax", 1), ("cloth", 2)],
        perm={"tag_add": "void_cloaked", "ranged_evade_pct": 25},
        rarity="epic", discipline="alchemy", aud=4),

    _armor("armor_trench_overcoat", "okopowy płaszcz",
        "Glina + skóra + szmaty. +1 AC + warmth.",
        tier=3, tags=[("organic", 1), ("leather", 1), ("biome:okopy_frontowe", 1)],
        perm={"ac_bonus": 1, "tag_add": "warm"},
        biome="okopy_frontowe"),

    _armor("armor_bar_apron", "barmański fartuch",
        "Cloth + tar + brass. Splash drink reduce.",
        tier=3, tags=[("cloth", 1), ("sticky", 1), ("biome:bar_skurczybyk", 1)],
        perm={"ac_bonus": 1, "tag_add": "drinkproof"},
        biome="bar_skurczybyk"),

    # ── FOOD (8) ─────────────────────────────────────────────────────

    _food("food_rat_soup", "zupa szczura",
        "Szczur + woda + sól + ogień. Trzyma morale.",
        tier=4, tags=[("organic", 1), ("food", 1), ("preservative", 1), ("flammable", 1)],
        heal=5, buff="warmed_up"),

    _food("food_bone_broth", "wywar kostny",
        "Kości + sól + woda + glina. Krytyczny minimum.",
        tier=3, tags=[("bone", 1), ("preservative", 1), ("organic", 1)],
        heal=4),

    _food("food_synth_protein_bar", "syntetyczny baton białkowy",
        "Pellet + tar + cloth wrapper. Smakuje obrzydliwie. Działa.",
        tier=3, tags=[("food", 1), ("sticky", 1), ("cloth", 1)],
        heal=6, buff="energy_burst", aud=2),

    _food("food_mushroom_stew", "gulasz grzybowy",
        "Glow moss + fungal fiber + sól + olej. +1 audience na dłuższy czas.",
        tier=4, tags=[("fungal", 2), ("organic", 1), ("preservative", 1)],
        heal=4, buff="audience_streamer", rarity="uncommon", aud=3),

    _food("food_anomaly_truffle", "anomalny trufla",
        "Anomalny pył + grzyb + tar. Może dać +1 do INT na piętro.",
        tier=4, tags=[("weird", 1), ("fungal", 1), ("sticky", 1), ("powder", 1)],
        heal=2, buff="int_boost", rarity="rare", discipline="alchemy", aud=4),

    _food("food_beer_pretzel", "piwny precel",
        "Drożdże + sól + mąka. +2 audience za bycie miejscowym.",
        tier=3, tags=[("fungal", 1), ("preservative", 1), ("biome:bar_skurczybyk", 1)],
        heal=3, buff="audience_streamer", biome="bar_skurczybyk", aud=3),

    _food("food_pigeon_pie", "gołębi placek",
        "Gołąb + glina + cegła. Smak ulicy.",
        tier=3, tags=[("organic", 1), ("ceramic", 1), ("biome:intake_industrial", 1)],
        heal=5, biome="intake_industrial"),

    _food("food_zoo_critter_skewer", "zoo-szaszłyk",
        "Pellet + krew + drewno + ogień. Smakuje jak menedżer.",
        tier=4, tags=[("organic", 2), ("flammable", 1), ("biome:zoo_korporacyjne", 1)],
        heal=6, buff="warmed_up", biome="zoo_korporacyjne", rarity="uncommon"),

    # ── MEDICAL (8) ──────────────────────────────────────────────────

    _medical("med_clean_bandage", "czysty opatrunek",
        "Alkohol + cloth + tape. Zatrzymuje krwawienie.",
        tier=3, tags=[("medical", 1), ("cloth", 1), ("binding", 1)],
        heal=8, cures=("bleeding",)),

    _medical("med_antitoxin_kit", "zestaw antytoksyn",
        "Disinfectant + acid + organic. Imuno trucizn na turę.",
        tier=4, tags=[("medical", 1), ("chemical", 1), ("organic", 1)],
        heal=4, cures=("poisoned", "corroded"), rarity="rare"),

    _medical("med_warming_balm", "balsam rozgrzewający",
        "Alcohol + chłodziwo (odwrotnie) + tłuszcz. Curuje chilled.",
        tier=3, tags=[("medical", 1), ("chemical", 1), ("liquid", 1)],
        heal=3, cures=("chilled",)),

    _medical("med_burn_salve", "maść na oparzenia",
        "Olej + cloth + woda. Curuje burning + ból.",
        tier=3, tags=[("medical", 1), ("slick", 1), ("absorbent", 1)],
        heal=4, cures=("burning",)),

    _medical("med_emergency_stim", "awaryjny stim",
        "Battery + chem + needle. Wskakuje na 1 HP zamiast 0.",
        tier=4, tags=[("medical", 1), ("power", 1), ("reactive", 1)],
        heal=12, buff_status="prevent_death", rarity="rare",
        discipline="electronics"),

    _medical("med_shock_paddle", "doraźny defibrylator",
        "Cewka + ogniwo + drut + skóra. Resuscytuje (heal +20 jeśli HP<10).",
        tier=5, tags=[("electrical", 2), ("medical", 1), ("power", 1)],
        heal=20, cures=("shocked",), rarity="epic", discipline="electronics"),

    _medical("med_field_painkiller", "polowy lek bólu",
        "Phosphor + cloth + organic. Curuje wounded.",
        tier=3, tags=[("medical", 1), ("powder", 1), ("cloth", 1)],
        heal=2, cures=("wounded", "afraid")),

    _medical("med_void_serum", "serum pustki",
        "Osad pustki + krew + sól. Wskakuje +25 HP, ale lose 2 INT.",
        tier=5, tags=[("weird", 1), ("medical", 1), ("organic", 1), ("preservative", 1)],
        heal=25, buff_status="int_drain", rarity="epic",
        discipline="alchemy", aud=5),

    # ── TOOLS (8) ────────────────────────────────────────────────────

    _tool("tool_advanced_lockpick", "wytrychy pierwszej kategorii",
        "Spring + cienki metal + olej. +5 do hack/lock checków.",
        tier=3, tags=[("metal", 1), ("spring", 1), ("slick", 1)],
        tool_kind="lockpick", rarity="uncommon"),

    _tool("tool_signal_jammer", "zagłuszacz",
        "Bateria + cewka + ogniwo + magnes. Wyłącza kamerę/sensor w pokoju.",
        tier=4, tags=[("electrical", 2), ("magnetic", 1), ("power", 1)],
        tool_kind="jammer", rarity="rare"),

    _tool("tool_camera_drone", "drobny dron-kamera",
        "Soczewka + motor + bateria + screen. Scout sąsiedniego pokoju.",
        tier=5, tags=[("optical", 1), ("electronic", 2), ("power", 1)],
        tool_kind="scout_drone", rarity="rare"),

    _tool("tool_field_kit", "polowy zestaw narzędzi",
        "Tape + screws + leather + wire. +1 do crafting przez 1 piętro.",
        tier=4, tags=[("metal", 1), ("binding", 2), ("leather", 1)],
        tool_kind="craft_bonus", discipline="tinker"),

    _tool("tool_decoder_ring", "pierścień dekoderski",
        "Chip + soczewka + brass. Odczytuje sponsor data.",
        tier=4, tags=[("electronic", 1), ("optical", 1), ("data", 1)],
        tool_kind="decoder", rarity="rare"),

    _tool("tool_makeshift_radio", "doraźne radio",
        "Wire + battery + spring + screen. Słyszysz sąsiednie pokoje.",
        tier=4, tags=[("electrical", 1), ("electronic", 1), ("power", 1)],
        tool_kind="radio", rarity="uncommon"),

    _tool("tool_pheromone_compass", "feromonowy kompas",
        "Feromony + sensor + soczewka + biome material. Wskazuje boss room.",
        tier=5, tags=[("smell", 1), ("sensor", 1), ("optical", 1), ("biome:zoo_korporacyjne", 1)],
        tool_kind="boss_locator", biome="zoo_korporacyjne", rarity="epic"),

    _tool("tool_archive_lens", "soczewka archiwalna",
        "Prism + film + screen. Pokazuje historię pokoju.",
        tier=4, tags=[("optical", 2), ("data", 1), ("biome:muzeum_spektakli", 1)],
        tool_kind="history_lens", biome="muzeum_spektakli", rarity="rare"),

    # ── BIOME bonus content (już rozproszone wyżej, +3 dodatkowe) ─────

    _coating("weapon_okopy_acid_mud", "okopowa glina kwasowa",
        "Trench mud + acid + cloth. Rdzewieje stal w okopach.",
        tier=3, tags=[("biome:okopy_frontowe", 1), ("acid", 1), ("cloth", 1)],
        dmg_type="acid", hits=4, extra=2, biome="okopy_frontowe", rarity="uncommon", aud=3),

    _throwable("throwable_zoo_collar_bomb", "obrożowa bomba",
        "Escape collar + battery + spring. Wybucha na metal-armed mobach.",
        tier=4, tags=[("electronic", 1), ("magnetic", 1), ("biome:zoo_korporacyjne", 1)],
        payload={"type": "aoe", "damage": 8, "damage_type": "electric",
                 "radius": 1, "extra_tags": ["explosive"]},
        biome="zoo_korporacyjne", rarity="rare"),

    _throwable("throwable_intake_brick_bomb", "wybuchowa cegła",
        "Cegła + puszka graffiti + sprężyna. Spada, ląduje, robi huk.",
        tier=3, tags=[("ceramic", 1), ("explosive", 1), ("biome:intake_industrial", 1)],
        payload={"type": "aoe", "damage": 6, "damage_type": "physical",
                 "radius": 1, "extra_tags": ["explosive"]},
        biome="intake_industrial"),

    # ── BIOME: grzybica_bloom (4 unikalne recepty) ─────────────────────

    _coating("weapon_spore_coat", "powłoka zarodnikowa",
        "Kapsuła zarodników + warkocz grzybni + olej. Każdy cios "
        "rozprasza spore.",
        tier=3, tags=[("biome:grzybica_bloom", 1), ("fungal", 1), ("slick", 1)],
        dmg_type="poison", hits=5, extra=1, biome="grzybica_bloom",
        discipline="bio", aud=3),

    _throwable("throwable_spore_bomb", "bomba zarodnikowa",
        "Spore + capsule + spring. Cały pokój zatruty na 3 tury.",
        tier=4, tags=[("biome:grzybica_bloom", 1), ("fungal", 1), ("powder", 1), ("spring", 1)],
        payload={"type": "room_status", "status": "poisoned", "duration": 3,
                 "extra_tags": ["fungal"]},
        biome="grzybica_bloom", discipline="bio", rarity="rare"),

    _food("food_glow_cap_stew", "gulasz świecącego kapelusza",
        "Luminous cap + sól + olej + chłodziwo. Nocne widzenie na piętro.",
        tier=4, tags=[("biome:grzybica_bloom", 1), ("light", 1), ("organic", 1), ("preservative", 1)],
        heal=5, buff="low_light_buff", biome="grzybica_bloom", rarity="rare"),

    _medical("med_blackrot_antitoxin", "antytoksyna z czarnej zgnilizny",
        "Blackrot + alkohol + cloth. Curuje poisoned + corroded jednocześnie.",
        tier=3, tags=[("biome:grzybica_bloom", 1), ("medical", 1), ("organic", 1)],
        heal=6, cures=("poisoned", "corroded"),
        biome="grzybica_bloom", rarity="rare"),

    # ── BIOME: intake_industrial (3 unikalne recepty) ─────────────────

    _weapon("crafted_intake_pipe_mace", "intake'owa rura uderzeniowa",
        "Intake rebar + smar + skórzany chwyt. Brzęczy przy każdym ciosie.",
        tier=3, tags=[("biome:intake_industrial", 1), ("metal", 1), ("handle", 1)],
        dice="1d8", dmg_type="physical",
        w_tags=["weapon", "blunt", "melee", "two_handed"],
        biome="intake_industrial", rarity="uncommon"),

    _coating("weapon_grease_slick", "smar industrialny",
        "Smar + cloth + binding. Cios w nogi = prone wroga.",
        tier=3, tags=[("biome:intake_industrial", 1), ("slick", 1), ("binding", 1)],
        dmg_type="physical", hits=3, extra=0, biome="intake_industrial",
        discipline="mechanics"),

    _trap("trap_intake_oil_slick", "rozlany smar",
        "Smar przemysłowy + cloth + plastic. Cały pokój prone.",
        tier=3, tags=[("biome:intake_industrial", 1), ("slick", 1), ("cloth", 1)],
        payload={"type": "damage_and_status", "damage": 1, "damage_type": "physical",
                 "status": "prone", "duration": 3, "extra_tags": ["slip"]},
        biome="intake_industrial"),

    # ── Extra fillers (5) — bez biome ──────────────────────────────────

    _throwable("throwable_smoke_screen", "zasłona dymna",
        "Fosfor + cloth + container. Pokój za zasłoną.",
        tier=3, tags=[("powder", 1), ("flammable", 1), ("container", 1)],
        payload={"type": "room_blind", "duration": 2, "extra_tags": ["smoke"]}),

    _food("food_protein_loaf", "mięsny placek",
        "Mięso + sól + drewno + ogień. Po prostu.",
        tier=4, tags=[("organic", 1), ("preservative", 1), ("flammable", 1), ("handle", 1)],
        heal=5),

    _tool("tool_thermal_scanner", "skaner termiczny",
        "Bateria + soczewka + chip + dioda. Pokazuje ciepłe ciała za ścianą.",
        tier=4, tags=[("electronic", 1), ("optical", 1), ("power", 1), ("light", 1)],
        tool_kind="thermal_scout", rarity="rare", discipline="electronics"),

    _permanent_weapon("weapon_static_grip", "statyczny chwyt",
        "Magnetyczny pasek + skóra + taśma. Broń sama wraca do dłoni.",
        tier=3, tags=[("magnetic", 1), ("leather", 1), ("binding", 1)],
        perm={"tag_add": "magnetic_return", "no_disarm": True},
        rarity="uncommon"),

    _medical("med_quickseal_foam", "piana szybkozasklepiająca",
        "Fosfor + cloth + chemical. Heal 6 + curuje bleeding + wounded.",
        tier=3, tags=[("powder", 1), ("absorbent", 1), ("reactive", 1)],
        heal=6, cures=("bleeding", "wounded")),

    # ── SPONSOR-BRANDED specialties (6) ───────────────────────────────

    _medical("med_nova_chem_xpack", "NovaChem X-pack",
        "Disinfectant + reagent + chem + organic. Curuje all + audience +5.",
        tier=4, tags=[("medical", 2), ("chemical", 1), ("organic", 1)],
        heal=15, cures=("bleeding", "poisoned", "burning", "corroded"),
        rarity="rare", aud=5),

    _weapon("crafted_liga_bat", "bita Ligi Brawurowej",
        "Heavy metal + handle + sponsor logo. +2 audience na hit.",
        tier=4, tags=[("metal", 2), ("handle", 1), ("sponsor", 1)],
        dice="1d8+2", dmg_type="physical",
        w_tags=["weapon", "blunt", "melee", "two_handed", "sponsored"],
        rarity="rare", aud=4),

    _tool("tool_kanal7_microphone_mk2", "ulepszony mikrofon Kanału 7",
        "Sensor + circuit + wire + chip. Audience x1.25 na każdej rozmowie.",
        tier=4, tags=[("electronic", 2), ("data", 1), ("sponsor", 1)],
        tool_kind="audience_amp", rarity="rare", aud=4),

    _trap("trap_czarny_rynek_snare", "sidła Czarnego Rynku",
        "Tape + wire + bone + spring. Grapple + +1 credit per turn trapped.",
        tier=3, tags=[("binding", 1), ("spring", 1), ("bone", 1)],
        payload={"type": "damage_and_status", "damage": 2, "damage_type": "physical",
                 "status": "grappled", "duration": 4, "extra_tags": ["sponsor"]},
        rarity="uncommon"),

    _armor("armor_sponsor_vest_amped", "ulepszona kamizelka sponsorska",
        "Vest + sponsor logo + chip + camera. Audience x1.15 floor-wide.",
        tier=5, tags=[("cloth", 1), ("sponsor", 2), ("electronic", 1)],
        perm={"ac_bonus": 1, "audience_mul": 1.15, "tag_add": "sponsored_amp"},
        rarity="epic", aud=6),

    _throwable("throwable_propaganda_zine", "propagandowy zin",
        "Paper + ink + sponsor + chemical. Audience +10 splash + afraid.",
        tier=4, tags=[("paper", 1), ("sponsor", 1), ("chemical", 1), ("powder", 1)],
        payload={"type": "room_status", "status": "afraid", "duration": 2,
                 "audience_gain": 10, "extra_tags": ["spectacle"]},
        rarity="rare", aud=5),
]


# ── Indexing helpers ─────────────────────────────────────────────────


_BY_KEY: Dict[str, Dict] = {r["key"]: r for r in EXPERIMENTAL_RECIPES}


def get_recipe(key: str) -> Optional[Dict]:
    return _BY_KEY.get(key)


def all_recipes() -> List[Dict]:
    return list(EXPERIMENTAL_RECIPES)


def recipes_for_tier(tier: int) -> List[Dict]:
    return [r for r in EXPERIMENTAL_RECIPES if r["tier"] == tier]


def recipes_for_biome(biome_key: str) -> List[Dict]:
    return [r for r in EXPERIMENTAL_RECIPES
            if r.get("biome_lock") == biome_key]


def recipes_unlocked_for_any_biome() -> List[Dict]:
    """Recepty bez biome-lock (zawsze dostępne)."""
    return [r for r in EXPERIMENTAL_RECIPES if not r.get("biome_lock")]


# ── Matching ─────────────────────────────────────────────────────────


def match_recipe_by_tag_profile(
        tag_profile: Dict[str, int],
        *,
        tier: Optional[int] = None,
        current_biome: Optional[str] = None,
        unlocked_biomes: Optional[set] = None,
) -> List[Dict]:
    """Find every recipe whose required tags are satisfied by the given
    `tag_profile` (dict tag -> count of materials carrying that tag).

    - `tier` if given filters to recipes of that complexity.
    - `current_biome` + `unlocked_biomes`: a biome-locked recipe is
      only matchable if the player is currently in that biome OR has
      it unlocked via meta-progression / recipe_note.
    """
    out: List[Dict] = []
    for rec in EXPERIMENTAL_RECIPES:
        if tier is not None and rec["tier"] != tier:
            continue
        biome = rec.get("biome_lock")
        if biome:
            if biome != current_biome and \
                    biome not in (unlocked_biomes or set()):
                continue
        ok = True
        for tag, need in rec["material_tags"]:
            if int(tag_profile.get(tag, 0)) < int(need):
                ok = False
                break
        if ok:
            out.append(rec)
    return out


def build_tag_profile_from_materials(material_keys: List[str]) -> Dict[str, int]:
    """Given a list of material keys (one entry per *unit* used; e.g.
    using 2 cloth_strips means 'cloth_strips' appears twice), return
    `{tag: total_count}` of all tags carried."""
    from ..materials import MATERIALS
    profile: Dict[str, int] = {}
    for mk in material_keys:
        md = MATERIALS.get(mk)
        if md is None:
            continue
        for tag in md.tags:
            profile[tag] = profile.get(tag, 0) + 1
    return profile


# ── Unique-item afix table (for crit successes) ──────────────────────


UNIQUE_AFFIXES_PL = [
    ("Niepamiętane",        "audience_on_kill", 1),
    ("Krwiopijcze",         "extra_bleed_chance", 0.15),
    ("Bezsenne",            "no_rest_required", True),
    ("Złoconej Krawędzi",   "rarity_aura", "legendary"),
    ("Pamięci Sezonu",      "audience_on_hit", 1),
    ("Konferansjera",       "social_bonus", 2),
    ("Świateł Studyjnych",  "to_hit_bonus", 1),
    ("Cienia Showrunnera",  "stealth_bonus", 2),
    ("Ciszy Loch'a",        "silent", True),
    ("Niezatapialne",       "ranged_evade_pct", 10),
]


def random_unique_affix(rng):
    """Returns (affix_pl, key, value) for a crit success unique item."""
    return rng.choice(UNIQUE_AFFIXES_PL)
