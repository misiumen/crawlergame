"""Narrative templates for partial success and failure."""

PARTIAL_SUCCESS_TEMPLATES = {
    "noise_cost": [
        "Udaje się, ale dźwięk niesie się korytarzem jak zaproszenie dla rzeczy bez kalendarza.",
        "Sukces. Głośny. Protokół zaznacza, że cisza była opcją premium."
    ],
    "time_cost": [
        "Robisz to, ale zajmuje dłużej, niż rozsądek obiecywał.",
        "Udało się. Zegar piętra traktuje twoją dokładność jak darowiznę."
    ],
    "item_damage": [
        "Działa, ale przedmiot protestuje ostatnim, niepokojąco drogim trzaskiem.",
        "Sukces kosztuje cię kawałek sprzętu i trochę wiary w gwarancje."
    ]
}

FAILURE_TEMPLATES = {
    "no_effect": [
        "Nie działa. Przez sekundę wszyscy obecni solidarnie udają, że nie widzieli.",
        "Efekt jest taki, że teraz wiesz, jak to nie działa."
    ],
    "bad_position": [
        "Próbujesz. Loch odpowiada geometrią.",
        "Zły kąt, zła chwila, bardzo dobra publiczność."
    ],
    "alarm": [
        "Coś pika. Potem pika szybciej. To rzadko jest etap sukcesu.",
        "System rejestruje próbę i otwiera formularz konsekwencji."
    ]
}

CRITICAL_FAILURE_TEMPLATES = {
    "sponsor_damage": [
        "Trafiasz w sprzęt sponsora. Na ekranie pojawia się słowo: FAKTURA.",
        "Korporacyjny alarm brzmi jak kasa fiskalna w piekle."
    ],
    "self_own": [
        "Przez krótką chwilę jesteś jedyną osobą w pokoju zaskoczoną tym, jak głupi był ten pomysł.",
        "Protokół zapisuje to jako samouczek. Dla innych."
    ]
}
