"""Floor archetypes — parameter sets that shape procedural generation.

Each archetype tells the generator:
  - graph_shape: how rooms connect (layered/branching/hub/etc.)
  - room counts and density of various content
  - what guarantees are required for the validator

The generator picks an archetype, then uses these knobs to drive every
later step (graph build, content placement, encounter spread, secret
placement, etc.).
"""

FLOOR_ARCHETYPES = {
    "survival_sprawl": {
        "fallback_label": "Rozległa Sortownia Zawodników",
        "graph_shape": "wide_layered",
        "min_rooms": 16, "max_rooms": 20,
        "layer_size_min": 2, "layer_size_max": 4,
        "safehouse_count": 2,
        "encounter_density":   0.35,
        "hazard_density":      0.20,
        "clue_density":        0.35,
        "backtracking_density":0.30,
        "secret_chance":       0.6,
        "lock_count":          1,
        "extra_cross_edges":   2,
        "preferred_objectives":["find_keycard","broadcast_stunt"],
    },
    "maintenance_maze": {
        "fallback_label": "Sieć Korytarzy Serwisowych",
        "graph_shape": "branching_dense",
        "min_rooms": 14, "max_rooms": 18,
        "layer_size_min": 2, "layer_size_max": 4,
        "safehouse_count": 1,
        "encounter_density":   0.20,
        "hazard_density":      0.40,
        "clue_density":        0.30,
        "backtracking_density":0.40,
        "secret_chance":       0.8,
        "lock_count":          2,
        "extra_cross_edges":   3,
        "preferred_objectives":["repair_elevator","find_keycard"],
    },
    "safehouse_spokes": {
        "fallback_label": "Węzeł Bezpiecznych Stref",
        "graph_shape": "hub_spokes",
        "min_rooms": 13, "max_rooms": 17,
        "layer_size_min": 3, "layer_size_max": 5,
        "safehouse_count": 3,
        "encounter_density":   0.25,
        "hazard_density":      0.20,
        "clue_density":        0.45,
        "backtracking_density":0.20,
        "secret_chance":       0.4,
        "lock_count":          1,
        "extra_cross_edges":   1,
        "preferred_objectives":["complete_faction_favour","find_keycard"],
    },
    "trap_infrastructure": {
        "fallback_label": "Sektor Pułapek Sponsora",
        "graph_shape": "linear_branchy",
        "min_rooms": 14, "max_rooms": 18,
        "layer_size_min": 1, "layer_size_max": 3,
        "safehouse_count": 1,
        "encounter_density":   0.20,
        "hazard_density":      0.50,
        "clue_density":        0.30,
        "backtracking_density":0.20,
        "secret_chance":       0.5,
        "lock_count":          1,
        "extra_cross_edges":   1,
        "preferred_objectives":["bypass_warden","repair_elevator"],
    },
    "crawler_conflict": {
        "fallback_label": "Strefa Konfliktu Zawodników",
        "graph_shape": "branching",
        "min_rooms": 14, "max_rooms": 18,
        "layer_size_min": 2, "layer_size_max": 4,
        "safehouse_count": 2,
        "encounter_density":   0.40,
        "hazard_density":      0.15,
        "clue_density":        0.35,
        "backtracking_density":0.25,
        "secret_chance":       0.4,
        "lock_count":          1,
        "extra_cross_edges":   2,
        "crawler_density_bonus":0.3,
        "preferred_objectives":["complete_faction_favour","broadcast_stunt","find_keycard"],
    },
    "locked_route": {
        "fallback_label": "Trasa Zamknięta",
        "graph_shape": "narrow",
        "min_rooms": 12, "max_rooms": 16,
        "layer_size_min": 1, "layer_size_max": 3,
        "safehouse_count": 2,
        "encounter_density":   0.25,
        "hazard_density":      0.25,
        "clue_density":        0.40,
        "backtracking_density":0.30,
        "secret_chance":       0.5,
        "lock_count":          3,
        "extra_cross_edges":   2,
        "preferred_objectives":["find_keycard","bypass_warden"],
    },
    "secret_detour": {
        "fallback_label": "Skrót, którego nie ma na mapie",
        "graph_shape": "branching_dense",
        "min_rooms": 14, "max_rooms": 18,
        "layer_size_min": 2, "layer_size_max": 4,
        "safehouse_count": 2,
        "encounter_density":   0.25,
        "hazard_density":      0.20,
        "clue_density":        0.40,
        "backtracking_density":0.30,
        "secret_chance":       1.0,
        "secret_room_count":   2,
        "lock_count":          1,
        "extra_cross_edges":   2,
        "preferred_objectives":["find_keycard","bypass_warden"],
    },
}


def list_archetypes():
    return list(FLOOR_ARCHETYPES.keys())


def get_archetype(key: str):
    return FLOOR_ARCHETYPES.get(key)
