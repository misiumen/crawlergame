"""Trap system for CRAWL PROTOCOL."""
import random
from dataclasses import dataclass
from utils import d20, parse_dice, ability_modifier, press_enter


@dataclass
class Trap:
    name: str
    description: str
    detection_dc: int
    disarm_dc: int
    save_ability: str
    damage_dice: str
    condition: str          # empty string = no condition
    effect: str             # description of effect


TRAP_CATALOG = [
    Trap("Spike Plate",
         "Pressure-sensitive plate concealed under grime.",
         10, 12, "DEX", "1d6", "",
         "Metal spikes punch upward through the floor."),
    Trap("Poison Needle",
         "A spring-loaded needle hidden in a door handle.",
         12, 14, "CON", "1d4", "poisoned",
         "A needle injects a fast-acting toxin."),
    Trap("Flame Vent",
         "A vent in the wall connected to a gas reservoir.",
         11, 13, "DEX", "2d4", "burning",
         "A jet of flame erupts from the wall."),
    Trap("Collapsing Floor",
         "Rotted planks over a pit. They held for decades. Not today.",
         13, 15, "DEX", "2d6", "",
         "The floor gives way and you fall."),
    Trap("Static Burst",
         "A capacitor bank disguised as wall paneling.",
         10, 12, "CON", "1d6", "stunned",
         "An electromagnetic pulse discharges painfully."),
    Trap("Hook Chain",
         "A chain with barbed hooks suspended at neck height.",
         11, 10, "DEX", "1d8", "",
         "A swinging chain of hooks tears through the room."),
    Trap("Acid Spray",
         "A pressurized container of something that was not meant for skin.",
         12, 14, "DEX", "1d6", "weakened",
         "Corrosive liquid sprays from hidden nozzles."),
    Trap("Crushing Wall",
         "Walls on either side begin to groan inward.",
         14, 16, "STR", "2d6", "",
         "The walls squeeze inward with grinding force."),
    Trap("Memory Snare",
         "A psychic field that replays your worst memory.",
         13, 12, "WIS", "1d4", "stunned",
         "Psychic feedback locks you in a trauma loop briefly."),
    Trap("False Treasure Mimic",
         "That chest looks suspicious. Most chests don't have teeth.",
         14, 0, "DEX", "2d4+2", "weakened",
         "The container bites down with surprising force."),
]


def get_random_trap(floor=1):
    """Return a random trap, scaling DC with floor."""
    trap = random.choice(TRAP_CATALOG)
    import copy
    t = copy.deepcopy(trap)
    bonus = (floor - 1) * 1
    t.detection_dc += bonus
    t.disarm_dc = max(t.disarm_dc, t.disarm_dc + bonus)
    return t


def attempt_detect(player, trap):
    """Returns True if player detects the trap."""
    # Quick Hands passive bonus
    bonus = 0
    for feat in player.features:
        if feat.name == "Quick Hands" and feat.action_type == "passive":
            bonus += int(feat.effect_value)
    # Track feature
    for feat in player.features:
        if feat.name == "Track":
            bonus += int(feat.effect_value)
    # Mutation detect bonus
    for mut in player.mutations:
        bonus += mut.detect_bonus

    roll = d20() + ability_modifier(player.abilities["WIS"]) + bonus
    print(f"\n  Perception check: {roll} vs DC {trap.detection_dc}")
    return roll >= trap.detection_dc


def attempt_disarm(player, trap):
    """Returns True if player disarms the trap."""
    if trap.disarm_dc <= 0:
        print("  This trap cannot be disarmed once triggered.")
        return False

    # Choose best stat: DEX or INT
    dex_mod = ability_modifier(player.abilities["DEX"])
    int_mod = ability_modifier(player.abilities["INT"])
    stat_mod = max(dex_mod, int_mod)
    stat_name = "DEX" if dex_mod >= int_mod else "INT"

    bonus = 0
    for feat in player.features:
        if feat.name == "Quick Hands" and feat.action_type == "passive":
            bonus += int(feat.effect_value)
    for mut in player.mutations:
        # Clawed Hands penalty
        if mut.name == "Clawed Hands":
            bonus -= 2
        bonus += mut.detect_bonus // 2

    roll = d20() + stat_mod + player.prof_bonus() + bonus
    dc = trap.disarm_dc
    print(f"\n  Disarm check ({stat_name}): {roll} vs DC {dc}")

    if roll >= dc:
        from narrator import get_narrator
        get_narrator().say("trap_disarmed")
        if player.achievements:
            player.achievements.unlock("Disarmed")
        return True
    else:
        # Failed disarm -trap triggers anyway
        print("  Your hands slip. The trap fires.")
        if player.achievements:
            player.achievements.unlock("Wrong Lever")
        return False


def trigger_trap(player, trap):
    """Apply trap damage and conditions to the player."""
    from narrator import get_narrator
    get_narrator().say("trap_triggered")

    print(f"\n  *** TRAP: {trap.name} ***")
    print(f"  {trap.effect}")

    # Save to halve damage
    save_mod = ability_modifier(player.abilities.get(trap.save_ability, 10))
    save_roll = d20() + save_mod
    save_dc = trap.detection_dc + 2
    saved = save_roll >= save_dc
    print(f"  {trap.save_ability} save: {save_roll} vs DC {save_dc} -{'SUCCESS' if saved else 'FAIL'}")

    dmg = parse_dice(trap.damage_dice)
    if saved:
        dmg = max(0, dmg // 2)

    actual = player.take_damage(dmg)
    print(f"  You take {actual} damage. HP: {player.hp}/{player.max_hp}")

    if trap.condition and not saved:
        player.add_condition(trap.condition, duration=3)
        print(f"  You are now {trap.condition}!")

    if player.achievements:
        player.achievements.check_trap_trigger()

    press_enter()
    return player.is_alive()


def run_trap_room(player, trap):
    """
    Full trap room flow: detect → choose action → resolve.
    Returns True if player survives.
    """
    print(f"\n  *** YOU ENTER A TRAP ROOM ***")
    print(f"  Something feels wrong.")

    # Detection attempt
    detected = attempt_detect(player, trap)

    if detected:
        print(f"\n  You spot a trap: {trap.name}")
        print(f"  {trap.description}")
        print()
        print("  [1] Attempt to disarm")
        print("  [2] Carefully avoid (50% chance of partial effect)")
        print("  [3] Walk straight through (save vs full damage)")
        from utils import safe_input_choice
        choice = safe_input_choice("  Choice: ", ["1", "2", "3"])

        if choice == "1":
            if attempt_disarm(player, trap):
                print("  Trap disarmed. Barely.")
                return True
            else:
                return trigger_trap(player, trap)
        elif choice == "2":
            roll = d20() + ability_modifier(player.abilities["DEX"])
            if roll >= 12:
                print("  You navigate around it. Close call.")
                return True
            else:
                print("  Not careful enough.")
                return trigger_trap(player, trap)
        else:
            return trigger_trap(player, trap)
    else:
        from narrator import get_narrator
        get_narrator().say("bad_decision")
        return trigger_trap(player, trap)
