"""CRAWL PROTOCOL v2 - Procedural generation."""
import random

_FIRST = [
    "Arek", "Voss", "Kael", "Mira", "Toran", "Lyss", "Daven", "Sable",
    "Oryn", "Cress", "Falke", "Nira", "Brek", "Thessy", "Venn", "Cade",
    "Juna", "Holt", "Sera", "Wren", "Dax", "Iona", "Quill", "Riven",
]
_LAST = [
    "Vance", "Thresh", "Cole", "Maren", "Tyde", "Ashford", "Crane",
    "Solis", "Vex", "Harrow", "Blaine", "Cross", "Weld", "Fenn", "Kade",
    "Morrow", "Strix", "Volke", "Dray", "Hess",
]

_ROOM_PREFIXES = [
    "Processing", "Containment", "Nexus", "Relay", "Archive",
    "Overflow", "Junction", "Transit", "Breach", "Staging",
    "Extraction", "Holding", "Amplifier", "Terminus", "Echo",
]
_ROOM_SUFFIXES = [
    "Chamber", "Bay", "Node", "Sector", "Vault", "Hub",
    "Point", "Zone", "Grid", "Array", "Block", "Ward",
]

_FLOOR_THEMES = [
    ("The Intake Level",    "Damp walls. New arrivals still screaming."),
    ("The Processing Deck", "Everything smells like disinfectant and fear."),
    ("The Industrial Ring", "Machinery that hasn't stopped in 40 years."),
    ("The Deep Archive",    "Records of everyone who came before you."),
    ("The Signal Layer",    "You can hear the broadcast from here."),
]

_SYNDICATE_COMMENTS = [
    "Audience approval is up. Do something interesting.",
    "The Protocol thanks you for your participation.",
    "Sponsors are watching. Make it count.",
    "Ratings spike confirmed. Well done, crawler.",
    "The dungeon has been recalibrated for your enjoyment.",
    "Your vitals make for compelling viewing.",
    "The Syndicate notes your creativity.",
    "Floor transition logged. Broadcast continues.",
    "Your fear response is within acceptable parameters.",
    "A viewer in Sector 7 is routing for you. Statistically unusual.",
]

_ENEMY_PREFIXES = [
    "Corroded", "Feral", "Bloated", "Augmented", "Glitching",
    "Syndicate", "Rogue", "Starved", "Mutated", "Fractured",
]
_ENEMY_TYPES = [
    "Guard", "Drone", "Crawler", "Specimen", "Unit",
    "Protocol", "Agent", "Remnant", "Subject", "Warden",
]

_LORE_FRAGMENTS = [
    "Contestant ID 4471: 'If you find this, the door on level 2 opens with 7-3-7.'",
    "SYNDICATE MEMO: Recall all Class-B containment units. Do not engage.",
    "Scrawled in blood: 'The boss has a second form. Don't celebrate early.'",
    "A sponsor advertisement plays on loop. It is for a product that no longer exists.",
    "BROADCAST FRAGMENT: '...and that's why we call it the Crawl, folks...'",
    "Someone has carved a tally into the wall. There are 47 marks.",
    "A datapad reads: 'They take your Class Box if you die. That's the deal.'",
    "SYNDICATE NOTICE: Audience engagement bonuses are non-negotiable.",
    "Scratched into the floor: 'Level 3 has a shortcut. Find the red door.'",
    "A note: 'The merchant is corrupt. Everything costs more than it says.'",
    "TECHNICAL LOG: Contestant mortality rate this season: 94.7%. Improving.",
    "Someone left a drawing of a cat. It is extremely detailed. Why.",
    # Step 12 - expanded pool
    "SYNDICATE INTERNAL: Sponsor renewals are down. Increase boss difficulty.",
    "Scratch marks count to 211. Someone gave up at 211.",
    "Burned page: '...kabel, woda i wystarczy iskra...' (PL fragment)",
    "Tape recorder: 'Mom, if you find this — I'm sorry about the chair.'",
    "AUDIO TRANSCRIPT: laughter, then static, then laughter again, longer.",
    "A perfectly preserved meal-tray. The food still warm. No one in sight.",
    "An entire wall of photos. None of them are anyone you know.",
    "Graffiti, fresh: 'Floor 4 boss eats psionics. Be human.'",
    "Datapad log: 'Acidic floor — try the locker route. Trust me.'",
    "Note nailed to wall with bone: 'I made it. I'm sorry I left you.'",
    "EMERGENCY BROADCAST: '...do not enter the broadcast layer. Repeat...'",
    "A child's drawing: a dragon with eight legs labeled 'TATA'.",
    "Vending machine receipt for 47 identical sandwiches, in three minutes.",
    "Scrawled: 'Boss F3 chce mówić. Posłuchaj. Może.' (PL fragment)",
    "A finger bone tied with red string. No body. No explanation.",
    "Pre-Crawl propaganda poster: 'Be the contestant your audience deserves.'",
    "Half a faction patch — Bleeding Chapel. Soaked through.",
    "Crawler's name carved 11 times in different scripts.",
    "Sealed letter, never delivered. The address is yours.",
    "Diagnostic display: PARTICIPANT_QUEUE = 14,238",
    "Mirror shard taped to the wall, angle suggests it watched the room.",
    "Empty stim wrappers, hundreds. Someone needed every one.",
    "Whispered into the dust: 'level 5 jest fałszywe' (PL fragment)",
    "A working broadcast camera, lens cracked. Still recording.",
    "Stack of empty contracts. None signed. All dated next Tuesday.",
    "Faded warning: 'DO NOT FEED THE BOSS.'",
    "A door painted to look like a window. The window is painted shut.",
    "Latin graffiti: 'memento mori, memento spectator' — remember death, remember the audience.",
]

_BACKGROUND_FLAVOR = {
    "Soldier":      "Military ID. Dog tags. A photo of someone you don't recognize anymore.",
    "Nurse":        "Hospital badge. Suture kit. A shift schedule from the last normal week.",
    "Electrician":  "Tool belt. Wire stripper. A note about an unfinished job.",
    "Hacker":       "Burner phone. Encrypted drive. Three fake identities.",
    "Chef":         "Knife roll. Restaurant matchbook. Muscle memory from a thousand services.",
    "Athlete":      "Sponsorship contract (voided). Knee brace. Competitive instinct.",
    "Scavenger":    "Jury-rigged pack. Merchant contacts. Eyes that miss nothing.",
    "Preacher":     "Worn scripture. A congregation that may still be waiting.",
    "Academic":     "Field notes. Reading glasses. A thesis no one will ever grade.",
    "Drifter":      "No fixed address. No attachments. Surprisingly easy to adapt.",
}

_SPONSOR_NAMES = [
    "NovaChem Biotech", "Helix-7 Augmentation", "Starfall Energy",
    "Precept Medical", "Dawnforge Arms", "Vantage Tactical",
    "Axiom Pharma", "Crucible Entertainment", "Zero-G Rations",
    "Syndicate Premium Package", "Obsidian Security Solutions",
]

_FACTION_NAMES = [
    ("The Ironclad Guild",  "acc", "Mercenary collective. They respect strength."),
    ("The Signal Corps",    "tec", "Tech-focused survivors. Knowledge is currency."),
    ("The Bleeding Chapel", "rel", "Zealots. Dangerous friends, worse enemies."),
    ("The Void Runners",    "mob", "Smugglers and scouts. They know the back paths."),
    ("The Remnants",        "sur", "Original floor inhabitants. Old grudges."),
    ("The Protocol Watch",  "syn", "Syndicate loyalists. Informants. Avoid."),
]


def random_name():
    return f"{random.choice(_FIRST)} {random.choice(_LAST)}"


def random_room_name():
    return f"{random.choice(_ROOM_PREFIXES)} {random.choice(_ROOM_SUFFIXES)}"


def random_floor_theme(floor_num):
    idx = (floor_num - 1) % len(_FLOOR_THEMES)
    return _FLOOR_THEMES[idx]


def syndicate_comment():
    return random.choice(_SYNDICATE_COMMENTS)


def random_enemy_name(base_name=None):
    if base_name:
        return f"{random.choice(_ENEMY_PREFIXES)} {base_name}"
    return f"{random.choice(_ENEMY_PREFIXES)} {random.choice(_ENEMY_TYPES)}"


def random_lore():
    return random.choice(_LORE_FRAGMENTS)


def background_flavor(bg_name):
    return _BACKGROUND_FLAVOR.get(bg_name, "Unknown origin. Promising.")


def random_sponsor():
    return random.choice(_SPONSOR_NAMES)


def random_factions(count=2):
    return random.sample(_FACTION_NAMES, min(count, len(_FACTION_NAMES)))


def stat_variance(base, spread=2):
    """Return base +/- spread, minimum 1."""
    return max(1, base + random.randint(-spread, spread))


def pick_weighted(items, weights):
    """Pick one item from items using weights list."""
    total = sum(weights)
    r = random.uniform(0, total)
    acc = 0
    for item, w in zip(items, weights):
        acc += w
        if r <= acc:
            return item
    return items[-1]


# ── Backstory data ─────────────────────────────────────────────────────────────
# Each entry: list of story variants. Each variant:
#   "paragraphs" : list of strings (shown line by line)
#   "intake_note": one-line Syndicate classification note
#   "gear_keys"  : list of item keys from items.py special catalog (or standard)
#   "credits_mod": starting credits adjustment

BACKSTORIES = {
    "Soldier": [
        {
            "paragraphs": [
                "Your unit was wiped out during the collapse of Sector 7.",
                "You were the only survivor - or so the Syndicate told you.",
                "You were still waiting for extraction orders that never came",
                "when their intake crew found you in a collapsed transit hub,",
                "eating field rations and cleaning a weapon you had no ammo for.",
                "",
                "They gave you a choice. You understood what kind of choice it was.",
            ],
            "intake_note": "INTAKE NOTE: Former military. Compliant. Possibly useful.",
            "gear_keys": ["dog_tags_item", "field_rations", "baton"],
            "credits_mod": 20,
        },
        {
            "paragraphs": [
                "Discharged. That's what the paperwork said.",
                "What it didn't say was why - or what you'd seen on the last deployment.",
                "You'd been living out of a storage unit for four months",
                "when the Syndicate's contractors came to 'discuss relocation options.'",
                "",
                "The relocation option was this dungeon.",
                "You kept your gear. Small mercy.",
            ],
            "intake_note": "INTAKE NOTE: Discharged. Classified incident on record. Do not ask.",
            "gear_keys": ["riot_remnants", "dog_tags_item", "stim_patch"],
            "credits_mod": 10,
        },
    ],
    "Nurse": [
        {
            "paragraphs": [
                "You kept the clinic running for 14 days after the city failed.",
                "Treating patients with whatever was left: tape, prayers, and will.",
                "When the last of your colleagues stopped coming back from supply runs,",
                "you made the decision to go looking for them.",
                "",
                "The Syndicate found you three blocks from the clinic,",
                "medkit in hand, covered in someone else's blood.",
                "They said you looked like you already knew how to work under pressure.",
            ],
            "intake_note": "INTAKE NOTE: Medical background. Survivability metrics above average.",
            "gear_keys": ["worn_medkit", "surgical_tape", "scrap_vest"],
            "credits_mod": 15,
        },
        {
            "paragraphs": [
                "Night shift. That's when the alarms started.",
                "You evacuated twelve patients. You went back for a thirteenth.",
                "The building came down around you. You woke up in Syndicate processing.",
                "",
                "They told you the thirteenth patient made it out.",
                "You're not sure you believe them.",
                "Either way, you're here now.",
            ],
            "intake_note": "INTAKE NOTE: High stress tolerance. Noted act of abnormal heroism. Interesting.",
            "gear_keys": ["worn_medkit", "scalpel_knife", "hospital_id"],
            "credits_mod": 10,
        },
    ],
    "Electrician": [
        {
            "paragraphs": [
                "The work order said: Sub-level 4, junction C, routine maintenance.",
                "The access tunnel sealed behind you six minutes after you arrived.",
                "The work order was a trap. The Syndicate needed someone who knew wiring.",
                "Someone who wouldn't be missed. Someone who would finish the job anyway.",
                "",
                "You finished the job anyway. Old habits.",
                "When the lights came on, so did the cameras.",
            ],
            "intake_note": "INTAKE NOTE: Acquired via contract fraud. Completed assigned task anyway. Reliable.",
            "gear_keys": ["wire_cutters", "work_belt", "shock_baton"],
            "credits_mod": 25,
        },
        {
            "paragraphs": [
                "You'd been freelancing in the outer zones since the grid collapsed.",
                "Keeping the lights on for people who couldn't pay.",
                "The Syndicate monitored those grid nodes for months before moving in.",
                "",
                "Turns out keeping the lights on in unauthorized sectors",
                "counts as infrastructure interference under Protocol law.",
                "Penalty: indefinite dungeon participation.",
            ],
            "intake_note": "INTAKE NOTE: Infrastructure offender. Practical skill set. Asset.",
            "gear_keys": ["wire_cutters", "scrap_vest", "stim_patch"],
            "credits_mod": 30,
        },
    ],
    "Hacker": [
        {
            "paragraphs": [
                "You were mid-exploit when the grid went down -",
                "fingers on a keyboard that suddenly had nothing left to connect to.",
                "Three days later the Syndicate traced 47 intrusion signatures back to your apartment.",
                "",
                "They didn't arrest you. They offered a contract.",
                "You declined. They clarified that it wasn't a question.",
                "You're still not sure what you were supposed to say yes to.",
            ],
            "intake_note": "INTAKE NOTE: Digital infiltrator. Unauthorized Syndicate network access x47. Useful.",
            "gear_keys": ["burner_phone", "cracked_tablet", "combat_knife"],
            "credits_mod": 40,
        },
        {
            "paragraphs": [
                "The door you cracked open was labeled SYNDICATE ARCHIVE - RESTRICTED.",
                "What was inside was worse than anything you'd imagined.",
                "You copied everything. Then they copied you.",
                "",
                "Into intake processing, that is.",
                "They wiped the drive. They didn't wipe you.",
                "You remember everything you saw. It hasn't helped yet.",
            ],
            "intake_note": "INTAKE NOTE: Witnessed restricted archive contents. Containment via participation.",
            "gear_keys": ["burner_phone", "cracked_tablet", "smoke_flask"],
            "credits_mod": 35,
        },
    ],
    "Chef": [
        {
            "paragraphs": [
                "Your restaurant was packed when the alarms started.",
                "You got everyone out through the kitchen.",
                "You were the last one through the back door.",
                "",
                "The Syndicate crew was waiting in the alley.",
                "You're still holding the chef's knife.",
                "You haven't put it down since.",
            ],
            "intake_note": "INTAKE NOTE: Found armed with kitchen implement. Retained it on intake. Fine.",
            "gear_keys": ["chefs_knife", "apron_vest", "emergency_rations"],
            "credits_mod": 15,
        },
        {
            "paragraphs": [
                "The last service you ran was for 200 Syndicate executives.",
                "You didn't know who they were. You just cooked.",
                "Three courses, perfect execution, standing ovation.",
                "",
                "After dessert, they told you the dungeon needed a contestant",
                "and that your skills in high-pressure environments had been noted.",
                "You asked if you could at least bring your knives.",
                "They said yes. That should have worried you more.",
            ],
            "intake_note": "INTAKE NOTE: Catered Executive Event #44. Recruited directly post-service.",
            "gear_keys": ["chefs_knife", "emergency_rations", "antidote"],
            "credits_mod": 20,
        },
    ],
    "Athlete": [
        {
            "paragraphs": [
                "You were at peak condition when the Syndicate scouts identified you.",
                "Former competitor. Notable physical metrics. Zero family to report you missing.",
                "",
                "They sedated you during what you thought was a routine medical screening.",
                "You woke up in processing, still in your training gear.",
                "Your event was cancelled anyway. The whole league was.",
            ],
            "intake_note": "INTAKE NOTE: Peak physical specimen. Acquired via medical deception. Standard.",
            "gear_keys": ["training_gear", "sports_tape", "stim_patch"],
            "credits_mod": 10,
        },
        {
            "paragraphs": [
                "You broke the record. Then you broke it again.",
                "The Syndicate broadcast your third record live to 40 million viewers.",
                "When it was over, a representative approached with a new contract.",
                "",
                "The venue. The crowds. The cameras.",
                "You signed before reading it.",
                "The venue turned out to be a megadungeon.",
            ],
            "intake_note": "INTAKE NOTE: Signed voluntarily. Technically. Contract valid under Protocol law.",
            "gear_keys": ["training_gear", "sports_tape", "combat_knife"],
            "credits_mod": 0,
        },
    ],
    "Scavenger": [
        {
            "paragraphs": [
                "You'd been working the outer zones for two years",
                "when you found a door you weren't supposed to find.",
                "Behind it: a Syndicate intake facility, mid-operation.",
                "",
                "You've been inside it ever since.",
                "The door you're looking for now is at the bottom of the dungeon.",
                "Probably.",
            ],
            "intake_note": "INTAKE NOTE: Witnessed active intake facility. Containment: immediate participation.",
            "gear_keys": ["scavenger_pack", "shiv", "antidote"],
            "credits_mod": 50,
        },
        {
            "paragraphs": [
                "You found something valuable in the ruins of Sector 9.",
                "Not credits. Not weapons. A broadcast receiver still pulling signal.",
                "You watched the Crawl for six hours before understanding what it was.",
                "",
                "You kept watching. You mapped their intake routes.",
                "You were careful. Not careful enough.",
                "The Syndicate finds people who watch too closely.",
            ],
            "intake_note": "INTAKE NOTE: Prolonged unauthorized broadcast monitoring. Recruited proactively.",
            "gear_keys": ["scavenger_pack", "combat_knife", "smoke_flask"],
            "credits_mod": 45,
        },
    ],
    "Preacher": [
        {
            "paragraphs": [
                "Your congregation dispersed during the first wave of evacuations.",
                "You stayed. Someone had to keep the building lit.",
                "The Syndicate found you two weeks later, still preaching to empty pews.",
                "",
                "They said an audience of millions was more appropriate for your gifts.",
                "You said you would preach to whoever needed it.",
                "They said the ratings would decide.",
            ],
            "intake_note": "INTAKE NOTE: Self-nominated broadcaster. Unusual. Audience response: positive.",
            "gear_keys": ["worn_scripture", "pilgrim_robe", "stim_patch"],
            "credits_mod": 10,
        },
        {
            "paragraphs": [
                "You'd been doing aid work in the restricted zones for months.",
                "Unauthorized. Officially classified as trespass.",
                "You kept going back. The people there needed someone.",
                "",
                "The Syndicate's enforcement unit came on a Tuesday.",
                "They didn't arrest you - they offered to expand your reach.",
                "40 million viewers. You accepted.",
                "You're still not sure that was a sin.",
            ],
            "intake_note": "INTAKE NOTE: Unauthorized zone aid worker. Recruited via moral leverage. Effective.",
            "gear_keys": ["worn_scripture", "pilgrim_robe", "worn_medkit"],
            "credits_mod": 5,
        },
    ],
    "Academic": [
        {
            "paragraphs": [
                "Your thesis was on Syndicate behavioral economics.",
                "They read it before your committee did.",
                "You were invited to 'consult' on their containment methodology.",
                "",
                "The consultation happened inside the dungeon.",
                "Your field notes are still in your coat pocket.",
                "You intend to publish if you get out.",
            ],
            "intake_note": "INTAKE NOTE: Theoretical knowledge of Protocol systems. Field testing arranged.",
            "gear_keys": ["field_notebook", "reading_glasses", "scrap_vest"],
            "credits_mod": 20,
        },
        {
            "paragraphs": [
                "You were cataloguing pre-collapse infrastructure when you found the access shaft.",
                "Academic curiosity. That's what you told yourself.",
                "You descended four levels before the Syndicate's automated systems found you.",
                "",
                "They reviewed your notes. Impressive documentation, they said.",
                "They suggested you continue your research from the inside.",
                "With a live audience.",
            ],
            "intake_note": "INTAKE NOTE: Unauthorized descent to Sub-4. Research background. Observational asset.",
            "gear_keys": ["field_notebook", "reading_glasses", "combat_knife"],
            "credits_mod": 15,
        },
    ],
    "Drifter": [
        {
            "paragraphs": [
                "No fixed address. No employment record. No family.",
                "No one to file a missing persons report.",
                "",
                "The Syndicate processed you in under four minutes.",
                "Easiest acquisition of the quarter, said the intake log.",
                "You've heard worse things said about you.",
            ],
            "intake_note": "INTAKE NOTE: Unaffiliated. No dependents. No complications. Ideal.",
            "gear_keys": ["worn_jacket", "shiv", "rabbit_foot"],
            "credits_mod": 60,
        },
        {
            "paragraphs": [
                "You woke up in the processing bay not remembering the last 48 hours.",
                "Your pockets had been emptied except for one thing:",
                "a handwritten note that said 'good luck - you're going to need it.'",
                "",
                "You don't know who wrote it.",
                "You still have the note.",
            ],
            "intake_note": "INTAKE NOTE: Acquired via standard sweep. Origin: unknown. Anomalous retention item.",
            "gear_keys": ["worn_jacket", "mystery_note", "stim_patch"],
            "credits_mod": 30,
        },
    ],
}


def get_backstory(background_key):
    """Return a random backstory variant for the given background."""
    variants = BACKSTORIES.get(background_key, BACKSTORIES["Drifter"])
    return random.choice(variants)
