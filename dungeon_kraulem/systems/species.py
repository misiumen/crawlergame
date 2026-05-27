"""P29.36 — DCC-faithful floor-3 mutation chamber.

11 species (baseline_human + 10 mutants). On first entry to floor 3,
the game offers 4 random non-baseline species + the "stay as you are"
decline option. Choice is permanent for the run, saved on
Character.species_key.

Each species carries:
  * key                — internal slug (persisted on Character).
  * name_pl            — display name (Polish only — the game is
                          Polish-only; English locale strings are
                          legacy and not surfaced anywhere).
  * desc_pl            — short tagline shown in the offer.
  * flavor_pl          — 1-2 line mutation chamber narration on
                          apply. Read by Game._apply_species_full.
  * drawback_pl        — what you lose, displayed under the reward
                          in the offer screen.
  * stat_bonus / hp_bonus — flat additions applied by apply_species.
  * passives           — list of trait keys; each one corresponds
                          to a hook in engine/species_effects.py
                          (combat AC, audience mul, status immunity,
                          movement cost, etc.).
  * drawbacks          — list of trait keys for negative effects
                          (fragile, social penalty, scanner stamp,
                          etc.). Engine-side they're indistinguishable
                          from passives — both go through the same
                          trait-lookup API. The split is purely
                          presentation (what to show under "Zysk" vs
                          "Strata" in the offer screen).

Trait keys are documented inline in engine/species_effects.py. The
trait set on a Character is the union of its species' passives +
drawbacks, stamped into `character.flags` as `species_<trait>=True`
at apply_species time so they survive save/load.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Species:
    key: str
    name_pl: str
    desc_pl: str
    flavor_pl: str
    drawback_pl: str
    stat_bonus: Dict[str, int] = field(default_factory=dict)
    hp_bonus: int = 0
    passives: List[str] = field(default_factory=list)
    drawbacks: List[str] = field(default_factory=list)

    def all_traits(self) -> List[str]:
        return list(self.passives) + list(self.drawbacks)


# ── Catalog ─────────────────────────────────────────────────────────────

SPECIES_CATALOG: Dict[str, Species] = {

    "baseline_human": Species(
        key="baseline_human",
        name_pl="Pozostań sobą (człowiek)",
        desc_pl="Bez transformacji. Konferansjer komentuje że to tchórzostwo.",
        flavor_pl="Wychodzisz z komory taki sam, jaki wszedłeś. "
                  "Konferansjer: „No, to jakaś nuda — następny!”",
        drawback_pl="Brak bonusów. Brak wad.",
    ),

    "enhanced_human": Species(
        key="enhanced_human",
        name_pl="Wzmocniony Człowiek",
        desc_pl="DEX +1, CON +1, +4 HP. Wszystkie statystyki +1. "
                "Widownia cię uwielbia (+25%).",
        flavor_pl="NovaChem-Biotech podpisuje cię w locie. Implant w "
                  "kości udowej, znaczek korporacyjny, kontrakt na "
                  "wyłączność opcji medialnych.",
        drawback_pl="Biopsja co piętro: −1 widowni przy zejściu. Inni "
                    "sponsorzy widzą w tobie pionka NovaChem.",
        stat_bonus={"DEX": 1, "CON": 1},
        hp_bonus=4,
        passives=["all_stats_plus_one", "audience_loved"],
        drawbacks=["novachem_biopsy_drain", "sponsor_envy_non_novachem"],
    ),

    "tunnelborn": Species(
        key="tunnelborn",
        name_pl="Tunelokrwisty",
        desc_pl="WIS +2, +6 HP. „Nasłuchuj” pokazuje nazwy wrogów z "
                "pokoju obok. Ruch −1 minuta na krok.",
        flavor_pl="Komora dodaje twoim oczom dwie warstwy soczewek. "
                  "Świetnie widzisz w ciemności. Słońce piecze jak nie "
                  "wiem co.",
        drawback_pl="W jasnych / safehouse'owych pokojach: −2 do "
                    "celności. W arenach i pokojach z publicznością: "
                    "−1 do społecznego (agorafobia).",
        stat_bonus={"WIS": 2},
        hp_bonus=6,
        passives=["low_light_vision", "pathfinder"],
        drawbacks=["sun_sensitive", "crowd_shy"],
    ),

    "scrapkin": Species(
        key="scrapkin",
        name_pl="Złomokrwisty",
        desc_pl="CON +2, +8 HP, +2 AC permanentne. Zjedzenie "
                "metal_scrap leczy 5 HP.",
        flavor_pl="Skóra zaczyna lekko dzwonić. Magnesy reagują. "
                  "Wyciągasz z kieszeni dwa krawężniki śrub — wpadły "
                  "ci podczas snu.",
        drawback_pl="−2 do społecznego ze WSZYSTKIMI NPC (ludzie się "
                    "kulą). Drony sponsorów wybierają cię jako "
                    "pierwszy cel.",
        stat_bonus={"CON": 2},
        hp_bonus=8,
        passives=["metal_skin", "scrap_eater"],
        drawbacks=["npc_fear", "drones_target_first"],
    ),

    "glassblood": Species(
        key="glassblood",
        name_pl="Szklanokrwisty",
        desc_pl="INT +2, DEX +1, −4 HP. Krytyki +50%. „Nasłuchuj” "
                "pokazuje liczbę wrogów w sąsiednich pokojach.",
        flavor_pl="Skóra robi się półprzezroczysta. Widzisz własne "
                  "naczynia. Operator kamery dostaje natychmiast "
                  "podwyżkę za detal.",
        drawback_pl="+25% otrzymywanych obrażeń. Każda strata HP ma "
                    "20% szans wywołać „bleeding”.",
        stat_bonus={"INT": 2, "DEX": 1},
        hp_bonus=-4,
        passives=["crit_amplifier", "translucent_sight"],
        drawbacks=["fragile", "bleeds_easy"],
    ),

    "void_touched": Species(
        key="void_touched",
        name_pl="Naznaczony Pustką",
        desc_pl="INT +3. Telepatia: 1 ominięta dezambiguacja na "
                "piętrze. Prekognicja: pierwszy cios na piętrze "
                "auto-pudłuje.",
        flavor_pl="Komora coś z ciebie zabrała i włożyła coś innego. "
                  "Słyszysz parę zdań które nie zostały powiedziane. "
                  "Widownia milknie.",
        drawback_pl="Widownia ×0.5 (ludzie się ciebie boją). 1 na 12 "
                    "wpisywanych komend „przekłada się” na inny "
                    "rozkaz (Pustka szepcze).",
        stat_bonus={"INT": 3},
        hp_bonus=0,
        passives=["telepathy", "precog_dodge"],
        drawbacks=["audience_disturbed", "void_garble"],
    ),

    "fungal_host": Species(
        key="fungal_host",
        name_pl="Grzybica",
        desc_pl="CON +2, +6 HP. +1 HP na minutę poza walką. "
                "Wrogowie w twoim pokoju eskalują wolniej.",
        flavor_pl="Z karku wystają delikatne nitki. Z plecaka idzie "
                  "lekki zapach. Towarzysz robi krok w tył.",
        drawback_pl="Każde wejście do pokoju: 25% szans na "
                    "dodatkowego mob'a (feromony). Towarzysze "
                    "tracą −2 więzi przy każdym zejściu.",
        stat_bonus={"CON": 2},
        hp_bonus=6,
        passives=["passive_regen", "spore_intimidate"],
        drawbacks=["pheromone_attract", "companion_repel_2"],
    ),

    "chimera": Species(
        key="chimera",
        name_pl="Chimera",
        desc_pl="STR +2, DEX +1, +8 HP. Bez broni: +2 obrażeń, "
                "kostka 1d6 (zamiast 1d4). Trzecia ręka — odporność "
                "na „grappled”.",
        flavor_pl="Z prawego ramienia wyrasta dodatkowa ręka. "
                  "Sponsorzy się krzywią, Konferansjer się śmieje, "
                  "anty-anti-host łapie pierwsze ujęcie.",
        drawback_pl="Pierwsze spotkanie z dowolnym NPC: −3 do "
                    "społecznego (horror wyglądu, trwałe). Uwaga "
                    "sponsorów ograniczona do 10 (oprócz Kanału 7).",
        stat_bonus={"STR": 2, "DEX": 1},
        hp_bonus=8,
        passives=["third_arm_unarmed", "grapple_immune"],
        drawbacks=["horror_first_meet", "sponsor_goodwill_cap_10"],
    ),

    "synthetic": Species(
        key="synthetic",
        name_pl="Syntetyk",
        desc_pl="INT +2, DEX +1, +4 HP. Odporność: „poisoned”, "
                "„bleeding”. Odpoczynek leczy ×2.",
        flavor_pl="Komora wymieniła ci kawałek meatu na krzem. "
                  "Słyszysz przewody pod skórą. Smak kawy znika "
                  "kompletnie.",
        drawback_pl="Brak bonusu z gotowanego jedzenia (no taste). "
                    "+50% obrażeń od źródeł elektrycznych. "
                    "Widownia ×0.85 (uncanny valley).",
        stat_bonus={"INT": 2, "DEX": 1},
        hp_bonus=4,
        passives=["poison_immune", "bleed_immune", "double_rest"],
        drawbacks=["no_food_taste", "emp_vuln", "uncanny_valley"],
    ),

    "half_dead": Species(
        key="half_dead",
        name_pl="Pół-Martwy",
        desc_pl="CON +1, +4 HP. 50% odporność na „bleeding” i "
                "obrażenia nekrotyczne. „Zbadaj zwłoki” zawsze "
                "pokazuje ostatnie słowa, nawet zgniłe.",
        flavor_pl="Z komory wyciągają cię już zimnego. Po pięciu "
                  "minutach zaczynasz mówić. Widownia odbiera to "
                  "lepiej niż się spodziewałeś.",
        drawback_pl="Towarzysze tracą −1 więzi przy każdym "
                    "zejściu (zwierzęta cię nie lubią). "
                    "Ministerstwo Pamięci nigdy nie da ci dodatniej "
                    "uwagi. Żywe jedzenie nie daje bonusu widowni.",
        stat_bonus={"CON": 1},
        hp_bonus=4,
        passives=["necrotic_resist_50", "corpse_whisper"],
        drawbacks=["companion_repel_1", "ministerstwo_hostile",
                   "live_food_no_audience"],
    ),

    "ferromanta": Species(
        key="ferromanta",
        name_pl="Ferromanta",
        desc_pl="STR +1, CON +1, +6 HP. Trafienie w metalowo "
                "uzbrojonego wroga: 25% szans „disarmed”. Dodatkowy "
                "metal_scrap na pokój z metalem (50%). Odporność na "
                "„disarmed”.",
        flavor_pl="Krew jak rtęć, skóra jak namagnesowana stal. Z "
                  "komory wychodzisz ciężko. Każdy krok dzwoni "
                  "metalicznie. Drzwiczki kuchenne otwierają się ku "
                  "tobie. Konferansjer: „No nareszcie ktoś z "
                  "prawdziwą tożsamością materiałową.”",
        drawback_pl="Ruch +1 minuta na krok (ołowiane kroki). "
                    "Możesz rozstawiać TYLKO pułapki metalowe. "
                    "Skanery: każde wejście do safehouse'u +1 "
                    "uwagi NovaChem. Nie możesz wejść w „hidden”. "
                    "+50% obrażeń od elektryczności.",
        stat_bonus={"STR": 1, "CON": 1},
        hp_bonus=6,
        passives=["magnetic_disarm", "metal_scavenger", "iron_grip"],
        drawbacks=["leaden_steps", "metal_only_traps",
                   "scanner_attention", "em_weak"],
    ),
}


# ── Public API ──────────────────────────────────────────────────────────

def apply_species(world, species_key: str) -> bool:
    """Stamp the species onto the character: stat bonuses, HP bonus,
    flag set for every passive + drawback trait. Returns False if the
    key is unknown or the application fails.

    Idempotent guard: if the character already has this species key,
    we re-stamp flags but skip the stat/HP bonuses (otherwise repeated
    apply would compound stats — important for save/load round-trip
    safety)."""
    sp = SPECIES_CATALOG.get(species_key)
    if sp is None:
        return False
    ch = world.character
    already = (ch.species_key == sp.key)
    ch.species_key = sp.key
    ch.species_picked_at_floor = world.floor_number
    if not already:
        for stat, bonus in sp.stat_bonus.items():
            ch.stats[stat] = ch.stats.get(stat, 10) + bonus
        if sp.hp_bonus:
            ch.max_hp = max(1, ch.max_hp + sp.hp_bonus)
            ch.hp = min(ch.max_hp, ch.hp + max(0, sp.hp_bonus))
    # Stamp every trait as a character flag. Engine code reads these
    # via engine/species_effects.has_trait(ch, key).
    if ch.flags is None:
        ch.flags = {}
    for trait in sp.all_traits():
        ch.flags[f"species_trait_{trait}"] = True
    return True


def random_offer(rng, exclude_keys=()) -> List[str]:
    """Pick 4 non-baseline species keys at random for the floor-3
    mutation offer. baseline_human is always available as the decline
    option but never in the random pool. `exclude_keys` lets the
    caller drop the player's current species so they don't see
    themselves in the roll.

    Returns 4 species keys, in random order."""
    pool = [k for k in SPECIES_CATALOG
            if k != "baseline_human" and k not in (exclude_keys or ())]
    n = min(4, len(pool))
    return rng.sample(pool, n)
