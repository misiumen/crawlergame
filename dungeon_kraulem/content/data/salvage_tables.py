"""Salvage table templates for CRAWL PROTOCOL revamp.

These are data templates, not a full system implementation. Claude should integrate
them with entities, validation, consequences, inventory/material storage and save/load.
"""

SALVAGE_TABLES = {
    "furniture_wood": {
        "tags": ["furniture", "wood", "salvageable"],
        "stat": "STR",
        "dc": 8,
        "time_minutes": 15,
        "noise": 1,
        "drops": {
            "wood_fragments": [1, 4],
            "screws": [0, 2],
            "cloth_strips": [0, 1],
        },
        "rare": {},
        "risks": ["noise"],
    },
    "furniture_metal": {
        "tags": ["furniture", "metal", "salvageable"],
        "stat": "STR",
        "dc": 10,
        "time_minutes": 20,
        "noise": 2,
        "drops": {
            "scrap_metal": [1, 4],
            "screws": [0, 3],
            "wire_bundle": [0, 1],
        },
        "rare": {"copper_coil": 0.08},
        "risks": ["noise", "cut_hands"],
    },
    "corpse_humanoid": {
        "tags": ["corpse", "organic", "lootable", "harvestable"],
        "stat": "WIS",
        "dc": 9,
        "time_minutes": 20,
        "noise": 0,
        "drops": {
            "cloth_strips": [0, 3],
            "bone_fragments": [0, 2],
        },
        "rare": {
            "crawler_badge": 0.12,
            "random_personal_item": 0.10,
        },
        "risks": ["reputation_if_witnessed", "disease", "moral_disgust"],
    },
    "corpse_monster": {
        "tags": ["corpse", "monster", "organic", "harvestable"],
        "stat": "WIS",
        "dc": 10,
        "time_minutes": 25,
        "noise": 0,
        "drops": {
            "bone_fragments": [1, 3],
            "monster_hide": [0, 2],
            "tooth": [0, 2],
            "claw": [0, 2],
        },
        "rare": {
            "strange_organ": 0.12,
            "ichor_sample": 0.15,
        },
        "risks": ["poison", "parasite", "stench"],
    },
    "sponsor_camera": {
        "tags": ["machine", "sponsor_tech", "electrical", "salvageable"],
        "stat": "INT",
        "dc": 12,
        "time_minutes": 15,
        "noise": 1,
        "drops": {
            "glass_shards": [1, 2],
            "wire_bundle": [1, 2],
            "circuit_board": [0, 1],
        },
        "rare": {
            "camera_lens": 0.35,
            "sponsor_chip": 0.08,
        },
        "risks": ["sponsor_notice", "shock", "alarm"],
    },
    "vending_machine": {
        "tags": ["machine", "container", "electrical", "salvageable"],
        "stat": "STR",
        "dc": 13,
        "time_minutes": 30,
        "noise": 3,
        "drops": {
            "scrap_metal": [2, 5],
            "circuit_board": [0, 2],
            "broken_screen": [0, 1],
            "battery_cell": [0, 1],
        },
        "rare": {
            "snack_item": 0.45,
            "sponsor_coupon": 0.05,
        },
        "risks": ["noise", "shock", "safehouse_fine_if_owned"],
    },
    "bathroom_fixture": {
        "tags": ["bathroom", "ceramic", "structural", "salvageable"],
        "stat": "STR",
        "dc": 12,
        "time_minutes": 25,
        "noise": 3,
        "drops": {
            "ceramic_fragments": [1, 3],
            "scrap_metal": [0, 2],
            "cleaning_fluid": [0, 2],
            "disinfectant": [0, 1],
        },
        "rare": {"weird_bathroom_token": 0.03},
        "risks": ["safehouse_rule_violation", "water_leak", "audience_mockery"],
    },
    "electrical_panel": {
        "tags": ["electrical", "machine", "salvageable"],
        "stat": "INT",
        "dc": 12,
        "time_minutes": 20,
        "noise": 1,
        "drops": {
            "wire_bundle": [1, 4],
            "circuit_board": [0, 2],
            "copper_coil": [0, 2],
            "battery_cell": [0, 1],
        },
        "rare": {"sensor_module": 0.12},
        "risks": ["shock", "lights_out", "alarm"],
    },
    "chemical_hazard": {
        "tags": ["chemical", "hazard", "salvageable"],
        "stat": "DEX",
        "dc": 13,
        "time_minutes": 20,
        "noise": 0,
        "drops": {
            "acid_residue": [1, 3],
            "cleaning_fluid": [0, 2],
            "powdered_reagent": [0, 1],
        },
        "rare": {"mutation_sample": 0.08},
        "risks": ["burning", "poisoned", "contamination"],
    },
}
