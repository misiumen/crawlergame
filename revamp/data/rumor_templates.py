"""Rumor templates for sandbox floor gameplay."""

RUMOR_TEMPLATES = {
    "floor_hint": [
        {
            "key": "acid_room_warning",
            "truth": 0.8,
            "text": "Crawler przy kawie twierdzi, że zielona ciecz w laboratorium reaguje na metal szybciej niż na mięso. Nie brzmi to pocieszająco, ale brzmi użytecznie.",
            "reveals_tags": ["acid", "lab", "environment_weapon"]
        },
        {
            "key": "bathroom_shortcut",
            "truth": 0.7,
            "text": "Ktoś wydrapał na lustrze w łazience: 'Wentylacja za trzecią kabiną prowadzi tam, gdzie nikt nie chce iść dwa razy.'",
            "reveals_tags": ["bathroom", "vent", "shortcut"]
        }
    ],
    "boss_hint": [
        {
            "key": "boss_likes_noise",
            "truth": 0.6,
            "text": "Ranny crawler mówi, że duży przy windzie reaguje na hałas. Potem poprawia: 'Nie reaguje. Celebruje.'",
            "reveals_tags": ["boss", "noise"]
        }
    ],
    "class_hint": [
        {
            "key": "env_class_hint",
            "truth": 1.0,
            "text": "Terminal rankingowy pokazuje klip, jak ktoś zabija potwora regałem. Podpis: 'Protokół lubi kandydatów, którzy rozumieją meble.'"
        }
    ],
    "false_or_biased": [
        {
            "key": "fake_free_loot",
            "truth": 0.2,
            "text": "Ktoś przysięga, że automat przy zamrażarce wydaje darmowe medkity, jeśli go kopnąć. Ma bandaż na stopie."
        }
    ]
}
