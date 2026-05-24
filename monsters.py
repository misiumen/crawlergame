"""CRAWL PROTOCOL v2 - Enemy definitions with procedural variance."""
import random
from utils import parse_dice, d20
from procgen import random_enemy_name, stat_variance


class Monster:
    def __init__(self, name, hp, ac, attack_bonus, damage_dice,
                 xp, cr_drop=0, condition_on_hit=None,
                 tags=None, description="", floor_min=1):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.ac = ac
        self.attack_bonus = attack_bonus
        self.damage_dice = damage_dice
        self.xp = xp
        self.cr_drop = cr_drop                     # credits
        self.condition_on_hit = condition_on_hit   # "poisoned", "burning", etc.
        self.tags = tags or []                     # "undead", "mechanical", etc.
        self.description = description
        self.floor_min = floor_min
        self.conditions: list = []
        self.is_boss: bool = False
        # Step 7 - non-combat resolution
        # Derived DCs scale with AC. Mechanical/undead enemies can't be talked to.
        self.social_dc = ac + 4
        self.stealth_dc = ac + 2
        self.skill_dc = ac + 3
        self.negotiable = not any(t in (self.tags or []) for t in ("mechanical","undead"))

    def is_alive(self):
        return self.hp > 0

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)

    def attack_roll(self):
        raw = d20()
        return raw, raw + self.attack_bonus

    def damage_roll(self):
        return max(1, parse_dice(self.damage_dice))

    def effective_ac(self):
        ac = self.ac
        if "weakened" in self.conditions:
            ac -= 2
        return ac

    def status_line(self):
        bar_total = 20
        filled = max(0, int((self.hp / self.max_hp) * bar_total))
        bar = "#" * filled + "." * (bar_total - filled)
        cond = f" [{', '.join(self.conditions)}]" if self.conditions else ""
        return f"{self.name}: [{bar}] {self.hp}/{self.max_hp}{cond}"

    def clone(self):
        m = Monster(
            name=self.name, hp=self.max_hp, ac=self.ac,
            attack_bonus=self.attack_bonus, damage_dice=self.damage_dice,
            xp=self.xp, cr_drop=self.cr_drop,
            condition_on_hit=self.condition_on_hit,
            tags=list(self.tags), description=self.description,
            floor_min=self.floor_min,
        )
        return m


def _make(name, hp, ac, atk, dmg, xp, cr=0, coh=None, tags=None, desc="", floor_min=1):
    return Monster(name, hp, ac, atk, dmg, xp, cr, coh, tags or [], desc, floor_min)


_CATALOG = [
    _make("Intake Drone",      12, 11,  3, "1d6",   20,  15, tags=["mechanical"],          desc="Repurposed security unit."),
    _make("Scrap Crawler",     10, 10,  2, "1d4",   15,  10, tags=["mechanical"],          desc="Barely functional."),
    _make("Toxic Rat",          8, 10,  3, "1d4+1", 18,   8, coh="poisoned",               desc="Bites carry infection."),
    _make("Rogue Guard",       18, 13,  4, "1d8",   35,  25,                               desc="Ex-Protocol security."),
    _make("Bloated Corpse",    14, 10,  2, "1d6",   25,  15, coh="poisoned", tags=["undead"], desc="The dungeon reanimates its dead."),
    _make("Syndicate Proxy",   20, 14,  5, "1d8+1", 40,  30, tags=["mechanical"],          desc="Corporate enforcement unit.", floor_min=2),
    _make("Feral Psych",       16, 11,  4, "1d6+2", 35,  20,                               desc="Previous contestant, unstable.", floor_min=2),
    _make("Acid Slime",        22, 9,   3, "1d8",   40,  25, coh="burning",                desc="Dissolves most materials.", floor_min=2),
    _make("Protocol Soldier",  25, 15,  6, "1d10",  55,  40, tags=["mechanical"],          desc="Syndicate front-line unit.", floor_min=2),
    _make("Void Wraith",       18, 14,  5, "1d6+3", 50,  35, tags=["undead"],              desc="Creature of the deep floors.", floor_min=3),
    _make("Augmented Brute",   35, 14,  7, "2d6",   70,  50, tags=["mechanical"],          desc="Heavy combat augments.", floor_min=3),
    _make("Signal Ghost",      20, 13,  5, "1d8+2", 60,  40, tags=["undead"],              desc="Broadcast-corrupted remnant.", floor_min=3),
    _make("Syndicate Hunter",  30, 16,  8, "1d10+2",80,  60,                               desc="Specialist sent to eliminate you.", floor_min=4),
    _make("Corrupted Mage",    22, 12,  6, "2d6+2", 75,  55,                               desc="Something went very wrong.", floor_min=4),
    _make("Protocol Titan",    50, 17,  9, "2d8",  100,  80, tags=["mechanical"],          desc="End-of-floor containment unit.", floor_min=5),
]

_BOSS_CATALOG = [
    # (floor, name, hp, ac, atk, dmg, xp, cr, tags, desc)
    (1, "The Intake Warden",    60,  14, 6, "2d6",   150, 100, ["mechanical"], "First floor overseer."),
    (2, "Signal Corruptor",     80,  15, 7, "2d6+2", 200, 150, [],             "Warps reality around it."),
    (3, "Syndicate Enforcer",  100,  16, 8, "2d8",   250, 200, ["mechanical"], "The Protocol's patience ends here."),
    (4, "The Broadcast Entity", 130, 17, 9, "2d8+3", 350, 280, [],             "It IS the signal."),
    (5, "Protocol Prime",       180, 18,11, "3d8",   500, 400, ["mechanical"], "The dungeon's final form."),
]


def get_floor_monsters(floor_num):
    return [m for m in _CATALOG if m.floor_min <= floor_num]


def get_random_monster(floor_num, use_variance=True):
    pool = get_floor_monsters(floor_num)
    if not pool:
        pool = _CATALOG
    m = random.choice(pool).clone()
    if use_variance:
        m.max_hp = stat_variance(m.max_hp, spread=max(1, m.max_hp // 5))
        m.hp = m.max_hp
        m.attack_bonus = stat_variance(m.attack_bonus, spread=1)
        m.ac = stat_variance(m.ac, spread=1)
        m.xp = stat_variance(m.xp, spread=5)
        # Occasionally rename with a procedural prefix
        if random.random() < 0.3:
            m.name = random_enemy_name(m.name)
    return m


def get_encounter(floor_num):
    """Return a list of monsters for a combat room (1-2 enemies)."""
    count = 1 if random.random() < 0.6 else 2
    return [get_random_monster(floor_num) for _ in range(count)]


def get_floor_boss(floor_num):
    for entry in _BOSS_CATALOG:
        f, name, hp, ac, atk, dmg, xp, cr, tags, desc = entry
        if f == floor_num:
            m = Monster(name, hp, ac, atk, dmg, xp, cr, None, tags, desc, floor_min=floor_num)
            m.is_boss = True
            return m
    # Fallback
    m = _CATALOG[-1].clone()
    m.name = f"Floor {floor_num} Boss"
    m.is_boss = True
    return m
