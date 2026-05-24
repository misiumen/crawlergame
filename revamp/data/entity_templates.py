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
