"""Entity templates instantiated by the procgen seeds.

P27.6 balance pass: HP and damage dice for all MON entries are
scaled at MODULE-LOAD time via `_apply_balance_scale()` so the source
templates stay readable with their original "design" numbers while the
runtime values match the new HP-100 player scale.

Player baseline went 14 → 100 HP (×7). Monsters scale ×5 (less than
player so combat doesn't take 7× longer), damage ×4. Outcome: each hit
takes ~10-25% of the bar, fights last 4-7 turns instead of 1-3.
"""
from __future__ import annotations
import re as _re_balance

# Environmental features (env)
ENV = {
    "sponsor_camera": dict(
        name_key="ent_sponsor_camera_n", fallback_name="kamera sponsora",
        desc_key="ent_sponsor_camera_d",
        fallback_desc="Mała kamera na suficie, leniwie się obraca. Diody migają nieprzyjemnie regularnie.",
        tags=["camera","sponsor","electronic","high","fragile"],
        affordances=["inspect","throw_at","hack","perform","break"],
    ),
    "sponsor_screen": dict(
        name_key="ent_sponsor_screen_n", fallback_name="ekran sponsorski",
        desc_key="ent_sponsor_screen_d",
        fallback_desc="Płaski ekran z reklamą NovaChem. Dźwięk wyłączony. Łatwo wystąpić przed nim.",
        tags=["screen","sponsor","electronic","fragile"],
        affordances=["inspect","perform","break","hack"],
    ),
    "coffee_machine": dict(
        name_key="ent_coffee_machine_n", fallback_name="automat z kawą",
        desc_key="ent_coffee_machine_d",
        fallback_desc="Automat z napisem 'awaria — przepraszamy'. Świeci na czerwono. Zardzewiały.",
        tags=["machine","coffee","fragile"],
        affordances=["inspect","use","hack","force","break"],
    ),
    "exposed_wiring": dict(
        name_key="ent_exposed_wiring_n", fallback_name="obnażone przewody",
        desc_key="ent_exposed_wiring_d",
        fallback_desc="Pęk kabli wyrwanych ze ściany. Iskrzy. Wydaje cichy klikający dźwięk.",
        tags=["electric","spark","wire","craft_material","hazardous"],
        affordances=["inspect","use","throw_at","craft","push_into"],
    ),
    "water_pool": dict(
        name_key="ent_water_pool_n", fallback_name="kałuża wody",
        desc_key="ent_water_pool_d",
        fallback_desc="Stojąca woda. Przewodzi prąd lepiej niż ktokolwiek by chciał.",
        tags=["water","liquid"],
        affordances=["inspect","push_into"],
    ),
    "loose_grate": dict(
        name_key="ent_loose_grate_n", fallback_name="luźna krata",
        desc_key="ent_loose_grate_d",
        fallback_desc="Stalowa krata w suficie. Wisi na jednym śrubie.",
        tags=["scrap","heavy"],
        affordances=["inspect","use","force"],
    ),
    "loose_cables": dict(
        name_key="ent_loose_cables_n", fallback_name="luźne kable",
        desc_key="ent_loose_cables_d",
        fallback_desc="Pęk kabli, lekko obnażonych. Łatwo je wyrwać.",
        tags=["electric","spark","wire","craft_material"],
        affordances=["inspect","use","craft","push_into","throw_at"],
    ),
    "gas_canister": dict(
        name_key="ent_gas_canister_n", fallback_name="butla gazowa",
        desc_key="ent_gas_canister_d",
        fallback_desc="Duża butla z napisem 'NIE OTWIERAĆ PRZY OGNIU'.",
        tags=["gas","flammable","heavy","hazardous"],
        affordances=["inspect","push_into","throw_at","force"],
    ),
    "server_rack": dict(
        name_key="ent_server_rack_n", fallback_name="szafa serwerowa",
        desc_key="ent_server_rack_d",
        fallback_desc="Wysoka szafa z mrugającymi diodami. Brzęczy.",
        tags=["electronic","heavy","fragile"],
        affordances=["inspect","hack","break","push_into"],
    ),

    # ── Audit gap 2: salvageable furniture + fixtures + machines ─────────────
    "furniture_wood": dict(
        name_key="ent_wood_furn_n", fallback_name="drewniane meble",
        fallback_desc="Stary stół, krzesło albo coś z tej rodziny. Trzyma się honoru.",
        tags=["furniture","wood","heavy","salvageable"],
        affordances=["inspect","salvage","strip","push_into"],
    ),
    "furniture_metal": dict(
        name_key="ent_metal_furn_n", fallback_name="metalowe meble",
        fallback_desc="Spawane, zardzewiałe, zbyt ciężkie żeby przesunąć bez powodu.",
        tags=["furniture","metal","heavy","salvageable"],
        affordances=["inspect","salvage","strip","push_into"],
    ),
    "loose_chair": dict(
        name_key="ent_chair_n", fallback_name="luźne krzesło",
        fallback_desc="Plastik na metalowych rurkach. Idealne do rozbicia.",
        tags=["furniture","plastic","light","salvageable"],
        affordances=["inspect","salvage","throw_at"],
    ),
    "plastic_table": dict(
        name_key="ent_plastic_table_n", fallback_name="plastikowy stół",
        fallback_desc="Lekki, brudny, na trzech nogach z czterech.",
        tags=["furniture","plastic","light","salvageable"],
        affordances=["inspect","salvage","push_into"],
    ),
    "trash_bin": dict(
        name_key="ent_trash_bin_n", fallback_name="kosz na śmieci",
        fallback_desc="Coś tam jest. Coś tam zawsze jest.",
        tags=["furniture","container","salvageable"],
        affordances=["inspect","search","salvage","loot"],
    ),
    "vending_machine": dict(
        name_key="ent_vending_n", fallback_name="automat sponsorski",
        fallback_desc="Reklamuje produkty, których już nie ma. Drzwi się klinują.",
        tags=["machine","container","electrical","salvageable","sponsor"],
        affordances=["inspect","use","force","salvage","hack"],
    ),
    "coffee_machine": dict(
        name_key="ent_coffee_machine_n", fallback_name="automat z kawą",
        fallback_desc="Sykcze. Czerwona dioda mówi 'awaria'. Coś można z tego odzyskać.",
        tags=["machine","appliance","electrical","salvageable","cafe"],
        affordances=["inspect","use","salvage","hack","break"],
    ),
    "bathroom_fixture": dict(
        name_key="ent_bath_fixture_n", fallback_name="armatura łazienkowa",
        fallback_desc="Ceramika, rury, metal. Coś, czego wyrwanie ma konsekwencje.",
        tags=["bathroom","ceramic","structural","salvageable","fragile"],
        affordances=["inspect","salvage","break","force"],
    ),
    "mirror": dict(
        name_key="ent_mirror_n", fallback_name="lustro",
        fallback_desc="Popękane przez środek. Pokazuje cię z opóźnieniem.",
        tags=["bathroom","glass","fragile","salvageable"],
        affordances=["inspect","break","salvage"],
    ),
    "sink": dict(
        name_key="ent_sink_n", fallback_name="zlew",
        fallback_desc="Białoszary porcelanowy zlew. Z odpływem coś jest nie tak.",
        tags=["bathroom","ceramic","container","salvageable","plumbing"],
        affordances=["inspect","use","salvage","break"],
    ),
    "toilet_stall": dict(
        name_key="ent_stall_n", fallback_name="kabina toaletowa",
        fallback_desc="Drzwi zaryglowane od środka. Lub od zewnątrz. Trudno powiedzieć.",
        tags=["bathroom","privacy","ceramic","salvageable"],
        affordances=["inspect","force","salvage","hide"],
    ),
    "pipe_cluster": dict(
        name_key="ent_pipes_n", fallback_name="splot rur",
        fallback_desc="Stalowe rury syczą cicho, gdzieś między ciśnieniem a niedyspozycją.",
        tags=["bathroom","metal","plumbing","salvageable","mechanical"],
        affordances=["inspect","salvage","break"],
    ),
    "cleaning_cabinet": dict(
        name_key="ent_clean_cab_n", fallback_name="szafka z chemią",
        fallback_desc="Pełna płynów, których nie powinno się wąchać.",
        tags=["bathroom","chemical","container","salvageable"],
        affordances=["inspect","search","loot","salvage"],
    ),
    "medical_cabinet": dict(
        name_key="ent_med_cab_n", fallback_name="szafka medyczna",
        fallback_desc="Wisi krzywo. Środki w środku też.",
        tags=["medical","container","salvageable"],
        affordances=["inspect","search","loot","salvage"],
    ),
    "biohazard_bin": dict(
        name_key="ent_biobin_n", fallback_name="kosz biohazardowy",
        fallback_desc="Żółty. Z napisem 'NIE OTWIERAĆ' i kilkoma kreskami obok.",
        tags=["medical","container","biohazard","salvageable"],
        affordances=["inspect","search","salvage"],
    ),
    "bandage_box": dict(
        name_key="ent_bandage_box_n", fallback_name="pudełko z bandażami",
        fallback_desc="Półpuste. Ktoś tu już naprawiał sobie albo nadzieję, albo żebra.",
        tags=["medical","container","salvageable"],
        affordances=["inspect","search","loot"],
    ),
    "disinfectant_shelf": dict(
        name_key="ent_disinf_shelf_n", fallback_name="półka z dezynfekcją",
        fallback_desc="Butelki, krople, instrukcje po angielsku z literówkami.",
        tags=["medical","chemical","container","salvageable"],
        affordances=["inspect","search","loot","salvage"],
    ),
    "broken_monitor": dict(
        name_key="ent_broken_monitor_n", fallback_name="rozbity monitor",
        fallback_desc="Ekran pęknięty od krawędzi do krawędzi. Kabel cudem się trzyma.",
        tags=["electronic","glass","fragile","salvageable"],
        affordances=["inspect","salvage","break"],
    ),
    "broken_terminal": dict(
        name_key="ent_broken_term_n", fallback_name="zepsuty terminal",
        fallback_desc="Klawiatura zalana, wnętrze widoczne, ktoś już tu majstrował.",
        tags=["electronic","terminal","mechanical","salvageable"],
        affordances=["inspect","hack","salvage","break"],
    ),
    "electrical_panel": dict(
        name_key="ent_elec_panel_n", fallback_name="rozdzielnia",
        fallback_desc="Przyciski, lampki, sporo miedzi. Drukowany rok 1997.",
        tags=["electrical","mechanical","salvageable","wire"],
        affordances=["inspect","hack","salvage","force"],
    ),
    "wire_bundle_source": dict(
        name_key="ent_wires_n", fallback_name="zwój kabli",
        fallback_desc="Czysto zwinięte. Ktoś dbał. Już nie.",
        tags=["electrical","wire","salvageable"],
        affordances=["inspect","salvage"],
    ),
    "machine_scrap": dict(
        name_key="ent_machine_scrap_n", fallback_name="złom maszynowy",
        fallback_desc="Stos blachy i części, z których ktoś już wyciągnął najlepsze.",
        tags=["machine","metal","scrap","salvageable"],
        affordances=["inspect","salvage"],
    ),
    "vent_grate": dict(
        name_key="ent_vent_grate_n", fallback_name="krata wentylacyjna",
        fallback_desc="Pleciony metal. Lekko obluzowany. Wystarczy delikatnie kopnąć.",
        tags=["metal","structural","salvageable"],
        affordances=["inspect","salvage","force","break"],
    ),
    "pressure_valve": dict(
        name_key="ent_pressure_valve_n", fallback_name="zawór ciśnieniowy",
        fallback_desc="Czerwone kółko. Ostrzeżenie po polsku, niemiecku i emoji.",
        tags=["metal","mechanical","valve","salvageable"],
        affordances=["inspect","use","salvage"],
    ),
    "loose_shelf": dict(
        name_key="ent_loose_shelf_n", fallback_name="luźna półka",
        fallback_desc="Trzyma się jednym zardzewiałym śrubokrętem honoru.",
        tags=["furniture","metal","heavy","salvageable","fragile"],
        affordances=["inspect","salvage","push_into","force"],
    ),
    "broken_table": dict(
        name_key="ent_broken_table_n", fallback_name="rozbity stół",
        fallback_desc="Trzy nogi. Każda przydatna na coś innego.",
        tags=["furniture","wood","salvageable","broken"],
        affordances=["inspect","salvage"],
    ),
    "debris_pile": dict(
        name_key="ent_debris_n", fallback_name="kupa gruzu",
        fallback_desc="Cegły, drut, kawałek czyjegoś hełmu. Standard.",
        tags=["scrap","mixed","salvageable","heavy"],
        affordances=["inspect","search","salvage"],
    ),
    "exposed_wiring": dict(
        name_key="ent_exposed_wiring_n", fallback_name="obnażone kable",
        fallback_desc="Spod tynku wystają w pełnej okazałości. Iskrzą trochę.",
        tags=["electrical","wire","salvageable","hazard"],
        affordances=["inspect","salvage","push_into","throw_at"],
    ),
    "supply_crate": dict(
        name_key="ent_supply_crate_n", fallback_name="skrzynia zaopatrzenia",
        fallback_desc="Pełna albo pusta. Z zewnątrz wygląda tak samo.",
        tags=["container","wood","salvageable"],
        affordances=["inspect","search","loot","force","salvage"],
    ),
    "locker": dict(
        name_key="ent_locker_n", fallback_name="szafka pracownicza",
        fallback_desc="Plakietka 'M.K.' poczerniała od wilgoci.",
        tags=["container","metal","salvageable"],
        affordances=["inspect","search","force","loot","salvage"],
    ),
    "metal_shelf": dict(
        name_key="ent_metal_shelf_n", fallback_name="metalowa półka",
        fallback_desc="Pełna toreb, kartonów i jednego buta. Stoi tylko z przyzwyczajenia.",
        tags=["furniture","metal","salvageable","container"],
        affordances=["inspect","search","salvage","push_into"],
    ),
    "sealed_box": dict(
        name_key="ent_sealed_box_n", fallback_name="zaplombowane pudło",
        fallback_desc="Plomba sponsorska. Drzewko firmowe. Otwarcie = formularz.",
        tags=["container","sponsor","sealed","salvageable"],
        affordances=["inspect","force","hack","loot"],
    ),
}

# Hazards (haz) - similar to env but always hostile
HAZ = {
    "acid_pool": dict(
        name_key="ent_acid_pool_n", fallback_name="kałuża kwasu",
        desc_key="ent_acid_pool_d",
        fallback_desc="Zielonkawy płyn, który zjada metal cicho i z apetytem.",
        tags=["acid","liquid","hazardous"],
        affordances=["inspect","push_into","throw_at"],
        # Prompt 21: push someone in → acid damage + corroded.
        damage_type="acid",
    ),
}

# Doors (door)
DOOR = {
    # left mostly empty - room exits carry the lock state; door entity is optional
}

# Terminals (term)
TERM = {
    "storage_terminal": dict(
        name_key="ent_storage_term_n", fallback_name="terminal zaplecza",
        desc_key="ent_storage_term_d",
        fallback_desc="Stary terminal. Login miga. Pachnie kawą.",
        tags=["terminal","electronic"],
        affordances=["inspect","hack","use"],
    ),
    "office_terminal": dict(
        name_key="ent_office_term_n", fallback_name="terminal biurowy",
        desc_key="ent_office_term_d",
        fallback_desc="Monitor mruga. Klawiatura zalana czymś nieokreślonym.",
        tags=["terminal","electronic"],
        affordances=["inspect","hack","use","repair"],
    ),
}

# Safehouse service objects (svc)
SVC = {
    "coffee_counter": dict(
        name_key="ent_coffee_counter_n", fallback_name="lada kafejki",
        desc_key="ent_coffee_counter_d",
        fallback_desc="Lada z napisem 'KASA'. Za nią zmęczony zawodnik w fartuchu.",
        tags=["safehouse","service","cafe"],
        affordances=["inspect","use","talk"],
    ),
    "mirror": dict(
        name_key="ent_mirror_n", fallback_name="lustro",
        desc_key="ent_mirror_d",
        fallback_desc="Lustro pęknięte przez środek. Pokazuje cię z lekkim opóźnieniem.",
        tags=["safehouse","service","bathroom","glass","fragile"],
        affordances=["inspect","use","break"],
    ),
    "sponsor_kiosk": dict(
        name_key="ent_kiosk_n", fallback_name="kiosk sponsorski",
        desc_key="ent_kiosk_d",
        fallback_desc="Okienko z napisem 'INFO • REKLAMA • CIEKAWE OFERTY'.",
        tags=["safehouse","service","sponsor"],
        affordances=["inspect","use","talk"],
    ),
    "clinic_counter": dict(
        name_key="ent_clinic_counter_n", fallback_name="recepcja kliniki",
        desc_key="ent_clinic_counter_d",
        fallback_desc="Recepcja kliniki obsługiwana przez automat. Cennik wisi z boku.",
        tags=["safehouse","service","clinic"],
        affordances=["inspect","use","talk"],
    ),
}

# Monsters (mon)
MON = {
    "tunnel_runt": dict(
        name_key="ent_tunnel_runt_n", fallback_name="Tunelowy Szczurek",
        desc_key="ent_tunnel_runt_d",
        fallback_desc="Niski, mokry, bardzo zły. Chrupie dłoń jeśli mu pozwolisz.",
        tags=["monster","small","biting","flammable"],
        affordances=["inspect","attack","intimidate","lure","sneak"],
        hp=8, max_hp=8, ac=11, attack_bonus=3, damage_dice="1d4+1",
        # Prompt 21: small + furry = vulnerable to fire AND cold.
        vulnerable_to=["fire","cold"],
    ),
    "freezer_carver": dict(
        name_key="ent_freezer_carver_n", fallback_name="Rzeźnik z Zamrażarki",
        desc_key="ent_freezer_carver_d",
        fallback_desc="Człowiek w fartuchu, z bardzo ostrym nożem i bardzo pustymi oczami.",
        tags=["monster","humanoid","sharp"],
        affordances=["inspect","attack","talk","intimidate","lure","sneak"],
        hp=18, max_hp=18, ac=12, attack_bonus=4, damage_dice="1d8+1",
        # Lives at sub-zero — vulnerable to fire, resistant to cold.
        vulnerable_to=["fire"],
        resists=["cold"],
    ),
    "relay_warden": dict(
        name_key="ent_relay_warden_n", fallback_name="Strażnik Przekaźnika",
        desc_key="ent_relay_warden_d",
        fallback_desc="Wysoki, w hełmie, z elektryczną pałką i bardzo dobrym dressingiem.",
        tags=["monster","humanoid","armored","floor_boss"],
        affordances=["inspect","attack","intimidate","bribe","talk","sneak"],
        hp=32, max_hp=32, ac=14, attack_bonus=6, damage_dice="2d6+1",
        damage_type="electric",
        # Armored + grounded = resistant to electric, vulnerable to acid.
        resists=["electric","physical"],
        vulnerable_to=["acid"],
    ),

    # P29.0 — patrol_security / silent_response REMOVED. They were
    # only ever spawned by encounter.fire() / alarm scheduling, which
    # is gone. The dungeon doesn't dispatch responders.
    "biotech_inspector": dict(
        name_key="ent_biotech_inspector_n", fallback_name="Inspektor NovaChem",
        desc_key="ent_biotech_inspector_d",
        fallback_desc="Hełm z osłoną twarzy, kombinezon, podkładka. Notuje cię.",
        tags=["monster","humanoid","corporate","novachem","responder"],
        affordances=["inspect","attack","intimidate","talk"],
        hp=18, max_hp=18, ac=13, attack_bonus=4, damage_dice="1d6+2",
        # HazMat suit — chem-proof but a battery makes it crackle.
        immune_to=["poison"],
        resists=["acid","fire"],
        vulnerable_to=["electric"],
    ),

    # ── Prompt 18 (deferred) — sponsor hunters ──────────────────────────────
    # These were declared in `content/data/sponsors.py` but the MON
    # templates were never authored. With these in place, the
    # sponsors.maybe_intervene → pending_sponsor_hunters → combat.py
    # injection path now actually spawns enemies.
    "agent_kontroli_jakosci": dict(
        name_key="ent_qc_agent_n", fallback_name="Agent Kontroli Jakości",
        desc_key="ent_qc_agent_d",
        fallback_desc=("W białym fartuchu z planszetką. „Subiekcie, "
                       "proszę nie ruszać się — to dla danych."),
        tags=["monster","humanoid","corporate","novachem","sponsor_hunter"],
        affordances=["inspect","attack","intimidate","talk"],
        hp=16, max_hp=16, ac=12, attack_bonus=4, damage_dice="1d8",
        damage_type="poison",
        resists=["poison","acid"],
        vulnerable_to=["fire"],
    ),
    "egzekutor_ligi": dict(
        name_key="ent_league_executor_n", fallback_name="Egzekutor Ligi",
        desc_key="ent_league_executor_d",
        fallback_desc=("Numerowana tarcza, jednorazowy uśmiech, "
                       "regulamin 4.2 wytatuowany na pięści."),
        tags=["monster","humanoid","armored","sport","sponsor_hunter"],
        affordances=["inspect","attack","intimidate"],
        hp=22, max_hp=22, ac=14, attack_bonus=5, damage_dice="1d10+1",
        resists=["physical"],
        vulnerable_to=["electric","cold"],
    ),
    "windykator": dict(
        name_key="ent_collector_n", fallback_name="Windykator",
        desc_key="ent_collector_d",
        fallback_desc=("Czarny garnitur, czarny notes, czarne pytanie: "
                       "„Mamy chwilę?”"),
        tags=["monster","humanoid","cunning","czarny_rynek","sponsor_hunter"],
        affordances=["inspect","attack","talk","intimidate","bribe"],
        hp=18, max_hp=18, ac=12, attack_bonus=4, damage_dice="1d6+2",
        vulnerable_to=["psychic"],
    ),
    "redaktor_naczelny": dict(
        name_key="ent_chief_editor_n", fallback_name="Redaktor Naczelny",
        desc_key="ent_chief_editor_d",
        fallback_desc=("Okulary, tablet, dyktafon. „Co właściwie próbujesz "
                       "powiedzieć tym ludziom?"),
        tags=["monster","humanoid","memetic","ministerstwo","sponsor_hunter"],
        affordances=["inspect","attack","talk","intimidate"],
        hp=15, max_hp=15, ac=11, attack_bonus=3, damage_dice="1d6+1",
        damage_type="psychic",
        resists=["psychic"],
        vulnerable_to=["fire","acid"],
    ),
    "pielgrzym_recyklera": dict(
        name_key="ent_recycler_pilgrim_n", fallback_name="Pielgrzym Recyklera",
        desc_key="ent_recycler_pilgrim_d",
        fallback_desc=("Patchworkowa szata z odzysku, święte koła "
                       "łańcuchowe, oczy zbyt jasne."),
        tags=["monster","humanoid","cult","recykling","sponsor_hunter","flammable"],
        affordances=["inspect","attack","intimidate","talk"],
        hp=14, max_hp=14, ac=11, attack_bonus=3, damage_dice="1d8",
        vulnerable_to=["fire","psychic"],
    ),
    "anty_gospodarz": dict(
        name_key="ent_antihost_n", fallback_name="Anty-gospodarz",
        desc_key="ent_antihost_d",
        fallback_desc=("Idealne włosy, mikrofon, uśmiech wycelowany w "
                       "kamerę, której nie widać."),
        tags=["monster","humanoid","spectacle","kanal_7","sponsor_hunter"],
        affordances=["inspect","attack","talk","intimidate"],
        hp=12, max_hp=12, ac=11, attack_bonus=3, damage_dice="1d6+2",
        vulnerable_to=["acid","psychic"],
    ),

    # ── P27 — Floor 2 roster: Sponsor Bezpieczeństwa Sportu theme
    # (arena/strip-mall / faction:liga). Per DCC convention, the floor
    # has multiple minibosses + 1 main boss guarding the exit.
    # Tagged with `floor_min:2` so content_loader prefers them on F2+.
    "stadionowy_szaleniec": dict(
        name_key="ent_stadion_madman_n", fallback_name="Stadionowy Szaleniec",
        desc_key="ent_stadion_madman_d",
        fallback_desc=("Pomalowana twarz, znicz w dłoni. Krzyczy "
                       "skandujące hasła do nikogo."),
        tags=["monster","humanoid","faction:liga","floor_min:2","flammable"],
        affordances=["inspect","attack","intimidate"],
        hp=10, max_hp=10, ac=11, attack_bonus=3, damage_dice="1d6+1",
        vulnerable_to=["psychic","cold"],
    ),
    "ochroniarz_areny": dict(
        name_key="ent_arena_security_n", fallback_name="Ochroniarz Areny",
        desc_key="ent_arena_security_d",
        fallback_desc=("Czarna koszulka „SECURITY”, paralizator. "
                       "Patrzy na ciebie jak na bilet bez wejścia."),
        tags=["monster","humanoid","corporate","faction:liga","floor_min:2"],
        affordances=["inspect","attack","intimidate","bribe"],
        hp=16, max_hp=16, ac=13, attack_bonus=4, damage_dice="1d8",
        damage_type="electric",
        resists=["physical"],
        vulnerable_to=["acid"],
    ),
    "kibic_zlobiarz": dict(
        name_key="ent_hooligan_n", fallback_name="Kibic Żłobiarz",
        desc_key="ent_hooligan_d",
        fallback_desc=("Szalik, łańcuch, oddech tak gęsty że mógłby "
                       "stać samodzielnie. Nuci coś groźnego."),
        tags=["monster","humanoid","faction:liga","floor_min:2","drunk"],
        affordances=["inspect","attack","intimidate"],
        hp=12, max_hp=12, ac=10, attack_bonus=3, damage_dice="1d8+1",
        vulnerable_to=["psychic"],
    ),
    "spiker_kanalu": dict(
        name_key="ent_announcer_n", fallback_name="Spiker Kanału",
        desc_key="ent_announcer_d",
        fallback_desc=("Mikrofon, podświetlana kamizelka, oczy z "
                       "wbudowanym opóźnieniem 0,3 sekundy."),
        tags=["monster","humanoid","faction:liga","floor_min:2","memetic"],
        affordances=["inspect","attack","talk","intimidate"],
        hp=8, max_hp=8, ac=10, attack_bonus=2, damage_dice="1d6",
        damage_type="psychic",
        vulnerable_to=["physical","acid"],
    ),

    # Floor 2 MINIBOSSES (DCC convention — multiple per floor).
    "kapitan_druzyny": dict(
        name_key="ent_team_captain_n", fallback_name="Kapitan Drużyny",
        desc_key="ent_team_captain_d",
        fallback_desc=("W kapitanskiej opasce, z głową zwycięzcy i "
                       "rękami zwykłego zabójcy. Komenderuje swoim "
                       "klubem."),
        tags=["monster","humanoid","faction:liga","floor_min:2",
              "miniboss","mini_boss"],
        affordances=["inspect","attack","intimidate","talk"],
        hp=22, max_hp=22, ac=13, attack_bonus=5, damage_dice="1d10",
        resists=["physical"],
        vulnerable_to=["cold","psychic"],
    ),
    "trener_szkoleniowiec": dict(
        name_key="ent_coach_n", fallback_name="Trener Szkoleniowiec",
        desc_key="ent_coach_d",
        fallback_desc=("Dres, gwizdek, tablica taktyczna w jednej "
                       "ręce, kij baseballowy w drugiej. „Bieg po linii!”"),
        tags=["monster","humanoid","faction:liga","floor_min:2",
              "miniboss","mini_boss"],
        affordances=["inspect","attack","intimidate","talk"],
        hp=20, max_hp=20, ac=12, attack_bonus=4, damage_dice="1d8+2",
        vulnerable_to=["acid","cold"],
    ),

    # Floor 2 MAIN BOSS — guards the exit.
    "arbiter_finalowy": dict(
        name_key="ent_finals_referee_n", fallback_name="Arbiter Finałowy",
        desc_key="ent_finals_referee_d",
        fallback_desc=("Pasiasta koszulka, megafon, wzrok absolutnej "
                       "władzy regulaminowej. Za nim — wyjście. Przed "
                       "nim — ty. „Zawodniku — sprawdzimy faul.”"),
        tags=["monster","humanoid","faction:liga","floor_min:2",
              "floor_boss","boss","armored"],
        affordances=["inspect","attack","intimidate","talk","bribe"],
        hp=40, max_hp=40, ac=15, attack_bonus=6, damage_dice="2d6+2",
        damage_type="physical",
        resists=["physical","electric"],
        vulnerable_to=["acid","psychic"],
    ),
}


# ── P27.6 Balance pass ─────────────────────────────────────────────────────

# Multipliers applied to every MON entry at module-load time.
_HP_SCALE  = 5     # monster HP × 5 (player HP scaled 7x to 100, monsters
                   # less to keep fights to 4-7 turns instead of 10+)
_DMG_MULT  = 4     # damage dice constant × 4 (so 1d4+1 → 1d4+5 approx)
_DMG_DICE_BUMP = 1 # plus +1 die per `Nd` term (so 1d4 → 2d4 — wider
                   # damage curve, more variance feels alive)


def _scale_damage_dice(spec: str) -> str:
    """Apply the balance multipliers to a dice spec like '1d4+1'.
    `NdS+B` → `(N+_DMG_DICE_BUMP)dS+(B*_DMG_MULT + N*S/2)` approximation
    that lifts average damage by ~3-4×."""
    if not spec or "d" not in spec:
        return spec
    m = _re_balance.match(r"^\s*(\d+)\s*d\s*(\d+)\s*([+\-]\s*\d+)?\s*$", spec)
    if not m:
        return spec
    n = int(m.group(1))
    s = int(m.group(2))
    b = int((m.group(3) or "+0").replace(" ", ""))
    # Lift dice count and add a flat bonus matching old avg × (_DMG_MULT-1).
    new_n = n + _DMG_DICE_BUMP
    # old avg = n*(s+1)/2 + b ; we want ~4× that.
    old_avg = n * (s + 1) / 2 + b
    new_dice_avg = new_n * (s + 1) / 2
    target = old_avg * _DMG_MULT
    new_b = max(0, int(round(target - new_dice_avg)))
    return f"{new_n}d{s}+{new_b}" if new_b else f"{new_n}d{s}"


_BALANCE_APPLIED = False


def _apply_balance_scale() -> None:
    """Mutates every MON entry in place. Called once at module load.
    Idempotent via module-level `_BALANCE_APPLIED` flag (NOT stored in
    MON dict — that would pollute iterators expecting every entry to
    be a monster template)."""
    global _BALANCE_APPLIED
    if _BALANCE_APPLIED:
        return
    for key, tmpl in list(MON.items()):
        if not isinstance(tmpl, dict):
            continue
        if "hp" in tmpl:
            tmpl["hp"] = int(tmpl["hp"]) * _HP_SCALE
        if "max_hp" in tmpl:
            tmpl["max_hp"] = int(tmpl["max_hp"]) * _HP_SCALE
        if "damage_dice" in tmpl:
            tmpl["damage_dice"] = _scale_damage_dice(tmpl["damage_dice"])
        if "attack_bonus" in tmpl:
            tmpl["attack_bonus"] = int(tmpl["attack_bonus"]) + 1
    _BALANCE_APPLIED = True


_apply_balance_scale()
