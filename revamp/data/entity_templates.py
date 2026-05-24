"""Entity templates instantiated by the procgen seeds."""

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
}

# Hazards (haz) - similar to env but always hostile
HAZ = {
    "acid_pool": dict(
        name_key="ent_acid_pool_n", fallback_name="kałuża kwasu",
        desc_key="ent_acid_pool_d",
        fallback_desc="Zielonkawy płyn, który zjada metal cicho i z apetytem.",
        tags=["acid","liquid","hazardous"],
        affordances=["inspect","push_into","throw_at"],
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
        tags=["monster","small","biting"],
        affordances=["inspect","attack","intimidate","lure","sneak"],
        hp=8, max_hp=8, ac=11, attack_bonus=3, damage_dice="1d4+1",
    ),
    "freezer_carver": dict(
        name_key="ent_freezer_carver_n", fallback_name="Rzeźnik z Zamrażarki",
        desc_key="ent_freezer_carver_d",
        fallback_desc="Człowiek w fartuchu, z bardzo ostrym nożem i bardzo pustymi oczami.",
        tags=["monster","humanoid","sharp"],
        affordances=["inspect","attack","talk","intimidate","lure","sneak"],
        hp=18, max_hp=18, ac=12, attack_bonus=4, damage_dice="1d8+1",
    ),
    "relay_warden": dict(
        name_key="ent_relay_warden_n", fallback_name="Strażnik Przekaźnika",
        desc_key="ent_relay_warden_d",
        fallback_desc="Wysoki, w hełmie, z elektryczną pałką i bardzo dobrym dressingiem.",
        tags=["monster","humanoid","armored","floor_boss"],
        affordances=["inspect","attack","intimidate","bribe","talk","sneak"],
        hp=32, max_hp=32, ac=14, attack_bonus=6, damage_dice="2d6+1",
    ),
}
